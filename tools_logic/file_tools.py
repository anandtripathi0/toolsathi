import io
import json
import warnings
import zipfile
from PIL import Image, ImageOps, ExifTags, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter

MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 25_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

class BoundedBuffer(io.BytesIO):
    """Fail during generation, before repeated PDF resources can exhaust RAM."""
    limit = 30 * 1024 * 1024

    def write(self, data):
        if self.tell() + len(data) > self.limit:
            raise ValueError('Generated output exceeds 30 MB. Process fewer pages or smaller images.')
        return super().write(data)

def integer(data, name, default, minimum=1, maximum=10000):
    try:
        value = int(data.get(name, default))
    except (ValueError, TypeError):
        raise ValueError(f'{name.replace("_", " ").title()} must be a whole number.')
    if not minimum <= value <= maximum:
        raise ValueError(f'{name.replace("_", " ").title()} must be between {minimum} and {maximum}.')
    return value

def image_open(raw):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(raw))
            if image.format not in ('JPEG', 'PNG', 'WEBP'):
                raise ValueError('Only genuine JPEG, PNG and WebP images are supported.')
            if image.width * image.height > MAX_PIXELS:
                raise ValueError('Image exceeds the 25-million-pixel limit.')
            if getattr(image, 'n_frames', 1) != 1:
                raise ValueError('Animated images are not supported. Upload a single-frame image.')
            image.load()
            return image
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('Invalid, damaged or excessively large image.')

def rgb(image):
    if image.mode in ('RGBA', 'LA', 'P'):
        rgba = image.convert('RGBA')
        background = Image.new('RGB', image.size, 'white')
        background.paste(rgba, mask=rgba.getchannel('A'))
        return background
    return image.convert('RGB')

def encoded(image, fmt, quality=80):
    image = rgb(image) if fmt == 'JPEG' else image.convert('RGBA' if 'A' in image.getbands() or image.mode == 'P' else 'RGB')
    image.info = {}
    out = BoundedBuffer()
    options = {'quality': quality, 'optimize': True} if fmt in ('JPEG', 'WEBP') else {'optimize': True}
    image.save(out, fmt, **options)
    return out.getvalue()

def text_result(value, filename='metadata.json'):
    return {'text': json.dumps(value, indent=2, ensure_ascii=False, default=str), 'filename': filename, 'mime': 'application/json'}

def image_process(slug, data, raw):
    source = image_open(raw)
    original_format = source.format
    image = ImageOps.exif_transpose(source)
    if slug in ('image-dimension-checker', 'image-metadata-viewer'):
        metadata = {'width': image.width, 'height': image.height, 'stored_width': source.width, 'stored_height': source.height,
                    'format': original_format, 'mode': image.mode, 'size_bytes': len(raw)}
        if slug == 'image-metadata-viewer':
            metadata['exif'] = {ExifTags.TAGS.get(k, str(k)): str(v)[:2000] for k, v in source.getexif().items()}
        return text_result(metadata)
    expected = {'jpg-to-png': 'JPEG', 'png-to-jpg': 'PNG', 'webp-to-png': 'WEBP'}.get(slug)
    if expected and original_format != expected:
        raise ValueError(f'This converter requires a {expected} input file.')
    forced = {'jpg-to-png': 'PNG', 'png-to-jpg': 'JPEG', 'image-to-webp': 'WEBP', 'webp-to-png': 'PNG', 'signature-resizer': 'PNG'}
    fmt = forced.get(slug, str(data.get('format', 'JPEG')).upper())
    if fmt not in ('JPEG', 'PNG', 'WEBP'):
        raise ValueError('Choose JPEG, PNG or WEBP as the output format.')
    quality = integer(data, 'quality', 80, 1, 95)
    if slug in ('image-resizer', 'image-cropper', 'signature-resizer'):
        width = integer(data, 'width', 300 if slug == 'signature-resizer' else 1200)
        height = integer(data, 'height', 100 if slug == 'signature-resizer' else 800)
        if width * height > MAX_PIXELS:
            raise ValueError('Output exceeds the 25-million-pixel limit.')
        if slug == 'image-cropper':
            left = integer(data, 'left', 0, 0)
            top = integer(data, 'top', 0, 0)
            if left + width > image.width or top + height > image.height:
                raise ValueError('Crop rectangle extends beyond the image. Check its dimensions first.')
            image = image.crop((left, top, left + width, top + height))
        elif slug == 'signature-resizer':
            resized = ImageOps.contain(rgb(image), (width, height), Image.Resampling.LANCZOS)
            image = Image.new('RGB', (width, height), 'white')
            image.paste(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
        elif str(data.get('keep_aspect', '')).lower() in ('true', 'on', '1'):
            image = ImageOps.contain(image, (width, height), Image.Resampling.LANCZOS)
        else:
            image = image.resize((width, height), Image.Resampling.LANCZOS)
    elif slug == 'image-rotator':
        angle = integer(data, 'angle', 90, 90, 270)
        if angle not in (90, 180, 270):
            raise ValueError('Rotation must be 90, 180 or 270 degrees.')
        image = image.rotate(-angle, expand=True)
    result = encoded(image, fmt, quality)
    if slug == 'image-compressor':
        target = integer(data, 'target_kb', 0, 0, 20000) * 1024
        if target:
            if fmt == 'PNG':
                raise ValueError('Target-size compression requires JPEG or WEBP.')
            q = quality
            # Bounded search: lower quality first, then dimensions; report actual dimensions.
            for _ in range(35):
                if len(result) <= target:
                    break
                if q > 20:
                    q = max(20, q - 10)
                else:
                    if min(image.size) < 16:
                        break
                    image = image.resize((max(1, int(image.width * .8)), max(1, int(image.height * .8))), Image.Resampling.LANCZOS)
                result = encoded(image, fmt, q)
            if len(result) > target:
                raise ValueError('The requested target is too small for this image.')
    ext, mime = {'JPEG': ('jpg', 'image/jpeg'), 'PNG': ('png', 'image/png'), 'WEBP': ('webp', 'image/webp')}[fmt]
    return {'data': result, 'text': f'{image.width} × {image.height} pixels · {len(result):,} bytes · {fmt}', 'filename': slug + '.' + ext, 'mime': mime}

def pdf_reader(raw):
    if not raw.lstrip().startswith(b'%PDF-'):
        raise ValueError('Upload a genuine PDF document.')
    try:
        reader = PdfReader(io.BytesIO(raw), strict=True)
        if reader.is_encrypted:
            raise ValueError('Password-protected PDFs are not supported. Unlock your own file before uploading.')
        if not 1 <= len(reader.pages) <= 200:
            raise ValueError('PDFs must have between 1 and 200 pages.')
        return reader
    except ValueError:
        raise
    except Exception:
        raise ValueError('This PDF is damaged or unsupported.')

def page_indices(spec, total):
    result = []
    if not str(spec).strip():
        raise ValueError('Enter the pages to include, for example 1,3-5.')
    for part in str(spec).split(','):
        part = part.strip()
        try:
            if '-' in part:
                a, b = map(int, part.split('-'))
            else:
                a = b = int(part)
        except ValueError:
            raise ValueError('Use page numbers and inclusive ranges, for example 1,3-5.')
        if not 1 <= a <= b <= total:
            raise ValueError(f'Page numbers must be between 1 and {total}; ranges must ascend.')
        result.extend(range(a - 1, b))
        if len(result) > 200:
            raise ValueError('Select at most 200 pages.')
    if len(set(result)) != len(result):
        raise ValueError('Each page may be included only once.')
    return result

def write_pdf(writer):
    output = BoundedBuffer()
    writer.write(output)
    return output.getvalue()

def pdf_process(slug, data, raws):
    if slug in ('jpg-to-pdf', 'png-to-pdf'):
        images = []
        pixels = 0
        for raw in raws:
            image = image_open(raw)
            if image.format != ('JPEG' if slug == 'jpg-to-pdf' else 'PNG'):
                raise ValueError('Every input must match the selected image format.')
            pixels += image.width * image.height
            if pixels > 50_000_000:
                raise ValueError('Combined images exceed 50 million pixels. Resize them first.')
            images.append(rgb(ImageOps.exif_transpose(image)))
        output = BoundedBuffer()
        images[0].save(output, 'PDF', save_all=True, append_images=images[1:], resolution=150)
        return {'data': output.getvalue(), 'filename': slug + '.pdf', 'mime': 'application/pdf', 'text': f'Created {len(images)} PDF pages.'}
    readers = [pdf_reader(raw) for raw in raws]
    total = sum(len(r.pages) for r in readers)
    if total > 200:
        raise ValueError('Combined PDFs exceed the 200-page limit.')
    reader = readers[0]
    if slug == 'pdf-metadata-viewer':
        return text_result({'pages': len(reader.pages), 'metadata': {str(k): str(v)[:2000] for k, v in (reader.metadata or {}).items()},
                            'page_sizes_points': [{'width': float(p.mediabox.width), 'height': float(p.mediabox.height)} for p in reader.pages]})
    if slug == 'pdf-splitter':
        output = BoundedBuffer()
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for index, page in enumerate(reader.pages, 1):
                writer = PdfWriter()
                writer.add_page(page)
                archive.writestr(f'page-{index:03d}.pdf', write_pdf(writer))
        return {'data': output.getvalue(), 'text': f'{len(reader.pages)} individual PDFs in a ZIP archive.', 'filename': 'pdf-pages.zip', 'mime': 'application/zip'}
    writer = PdfWriter()
    if slug == 'pdf-merger':
        for source in readers:
            for page in source.pages:
                writer.add_page(page)
    elif slug in ('pdf-page-extractor', 'pdf-page-reorder'):
        indices = page_indices(data.get('pages', ''), len(reader.pages))
        if slug == 'pdf-page-reorder' and len(indices) != len(reader.pages):
            raise ValueError('Reordering requires every page exactly once.')
        for index in indices:
            writer.add_page(reader.pages[index])
    elif slug == 'pdf-rotator':
        angle = integer(data, 'angle', 90, 90, 270)
        if angle not in (90, 180, 270):
            raise ValueError('Rotation must be 90, 180 or 270 degrees.')
        for page in reader.pages:
            writer.add_page(page).rotate(angle)
    else:
        raise ValueError('Unknown PDF operation.')
    return {'data': write_pdf(writer), 'text': f'Created {len(writer.pages)} PDF pages.', 'filename': slug + '.pdf', 'mime': 'application/pdf'}

def process(slug, data, uploads):
    from apps.tools.file_registry import FILE_TOOLS
    tool = FILE_TOOLS.get(slug)
    if not tool:
        raise ValueError('Unknown file tool.')
    if not uploads or len(uploads) > 20:
        raise ValueError('Choose between 1 and 20 files.')
    if not tool['fields'][0]['multiple'] and len(uploads) != 1:
        raise ValueError('This tool accepts exactly one file.')
    if slug == 'pdf-merger' and len(uploads) < 2:
        raise ValueError('Choose at least two PDFs to merge.')
    if sum(file.size for file in uploads) > MAX_BYTES:
        raise ValueError('Total upload size must not exceed 20 MB.')
    raws = []
    for uploaded in uploads:
        raw = uploaded.read(MAX_BYTES + 1)
        if not raw or len(raw) > MAX_BYTES:
            raise ValueError('Empty or oversized file.')
        raws.append(raw)
    return image_process(slug, data, raws[0]) if tool['category'] == 'image' else pdf_process(slug, data, raws)
