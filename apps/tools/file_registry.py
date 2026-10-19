"""Only executable image and PDF tools are published."""
def field(name, label, type='number', default='', **kwargs):
    return dict(name=name, label=label, type=type, default=default, **kwargs)

def choice(name, label, options, default):
    return field(name, label, 'select', default, options=[{'value': str(x), 'label': str(x)} for x in options])

IMAGE_UPLOAD = field('files', 'Choose image', 'file', required=True, accept='image/jpeg,image/png,image/webp', multiple=False,
                     help='JPEG, PNG or WebP. Up to 20 MB per request; maximum 25 million pixels.')
PDF_UPLOAD = field('files', 'Choose PDF', 'file', required=True, accept='application/pdf', multiple=False,
                   help='Unencrypted PDF, up to 20 MB. Maximum 200 pages per request.')
QUALITY = field('quality', 'Quality (1–95)', default=80, min=1, max=95)
WIDTH = field('width', 'Width in pixels', default=1200, min=1, max=10000)
HEIGHT = field('height', 'Height in pixels', default=800, min=1, max=10000)
FORMAT = choice('format', 'Output format', ['JPEG', 'PNG', 'WEBP'], 'JPEG')
PAGES = field('pages', 'Pages (1-based ranges)', 'text', '1', help='For example: 1,3-5. Use commas and inclusive ranges.')
FILE_TOOLS = {}

def add(slug, name, category, description, controls=None, keywords=(), extension='txt', multiple=False, example=None):
    upload = dict(IMAGE_UPLOAD if category == 'image' or slug in ('jpg-to-pdf', 'png-to-pdf') else PDF_UPLOAD)
    upload['multiple'] = multiple
    if multiple:
        upload['label'] += ' files (selection order is preserved)'
    is_pdf = category == 'pdf'
    sample = '/static/examples/sample.' + ('jpg' if slug in ('jpg-to-png', 'jpg-to-pdf') else 'webp' if slug == 'webp-to-png' else 'png')
    if is_pdf and slug not in ('jpg-to-pdf', 'png-to-pdf'):
        sample = '/static/examples/sample-three-pages.pdf'
    examples = {'_files': [sample]}
    if slug == 'pdf-merger':
        examples['_files'].append('/static/examples/sample-one-page.pdf')
    if slug in ('jpg-to-pdf', 'png-to-pdf'):
        examples['_files'].append(sample)
    if slug == 'image-cropper':
        examples.update({'left': 20, 'top': 20, 'width': 200, 'height': 120})
    if slug == 'pdf-page-reorder':
        examples['pages'] = '3,1,2'
    examples.update(example or {})
    FILE_TOOLS[slug] = {'id': slug, 'slug': slug, 'name': name, 'category': category, 'description': description,
        'keywords': list(keywords), 'icon': 'files' if is_pdf else 'image', 'status': 'available', 'handler': 'files',
        'download_type': extension, 'seo_title': f'{name} — Free Online | ToolSathi', 'seo_description': description,
        'related_tools': [], 'fields': [upload] + (controls or []), 'example': examples,
        'instructions': 'Choose your file' + ('s in the order you want them processed' if multiple else '') +
          ', adjust the controls, and select Process. Download the result within 10 minutes. Uploads are processed temporarily; no account is required.',
        'faqs': [{'question': 'Do I need an account?', 'answer': 'No. Processing and downloads are free without registration.'},
                {'question': 'How long is my result available?', 'answer': 'Download links expire after 10 minutes and are restricted to this browser session.'}]}

add('image-compressor', 'Image Compressor', 'image', 'Compress photos to JPEG or WebP, with an optional target file size.',
    [QUALITY, choice('format', 'Output format', ['JPEG', 'WEBP'], 'JPEG'), field('target_kb', 'Target size in KB (0 = no target)', default=0, min=0, max=20000)],
    ['compress photo', 'photo 50kb', 'reduce image size'], 'jpg')
add('image-resizer', 'Image Resizer', 'image', 'Resize an image to a bounding box or exact dimensions.',
    [WIDTH, HEIGHT, field('keep_aspect', 'Preserve aspect ratio', 'checkbox', True), FORMAT, QUALITY], ['resize photo'], 'jpg')
add('jpg-to-png', 'JPG to PNG', 'image', 'Convert a JPEG photo into a lossless PNG image.', extension='png')
add('png-to-jpg', 'PNG to JPG', 'image', 'Convert PNG images to JPEG, flattening transparency on white.', [QUALITY], extension='jpg')
add('image-to-webp', 'Image to WebP', 'image', 'Convert images to compact WebP files.', [QUALITY], extension='webp')
add('webp-to-png', 'WebP to PNG', 'image', 'Convert a WebP image to PNG.', extension='png')
add('image-cropper', 'Image Cropper', 'image', 'Crop an image using exact pixel coordinates.',
    [field('left', 'Left coordinate', default=0, min=0), field('top', 'Top coordinate', default=0, min=0), WIDTH, HEIGHT, FORMAT], extension='jpg')
add('image-rotator', 'Image Rotator', 'image', 'Rotate an image clockwise by 90, 180 or 270 degrees.',
    [choice('angle', 'Clockwise rotation', [90, 180, 270], 90), FORMAT], extension='jpg')
add('image-quality-reducer', 'Image Quality Reducer', 'image', 'Reduce JPEG or WebP encoding quality to make smaller files.',
    [QUALITY, choice('format', 'Output format', ['JPEG', 'WEBP'], 'JPEG')], extension='jpg')
add('signature-resizer', 'Signature Resizer', 'image', 'Fit a signature inside an exact white canvas without stretching.',
    [field('width', 'Canvas width', default=300, min=1, max=10000), field('height', 'Canvas height', default=100, min=1, max=10000)], extension='png')
add('image-dimension-checker', 'Image Dimension Checker', 'image', 'Inspect image dimensions, format and file size.', extension='json')
add('image-metadata-viewer', 'Image Metadata Viewer', 'image', 'View image format, dimensions and embedded EXIF metadata.', extension='json')
for kind in ('jpg', 'png'):
    add(f'{kind}-to-pdf', f'{kind.upper()} to PDF', 'pdf', f'Combine {kind.upper()} images into a PDF in selection order.',
        keywords=['image to pdf', 'photo to pdf'], extension='pdf', multiple=True)
add('pdf-merger', 'PDF Merger', 'pdf', 'Join multiple PDFs into one file in selection order.', keywords=['join pdf', 'combine pdf'], extension='pdf', multiple=True)
add('pdf-splitter', 'PDF Splitter', 'pdf', 'Split a PDF into individual one-page PDFs, packaged as a ZIP file.', extension='zip')
add('pdf-page-extractor', 'PDF Page Extractor', 'pdf', 'Extract selected PDF pages and ranges into a new PDF.', [PAGES], extension='pdf')
add('pdf-page-reorder', 'PDF Page Reorder', 'pdf', 'Reorder every PDF page by entering a complete page sequence.',
    [field('pages', 'New page order', 'text', '2,1', help='List each original page exactly once, for example: 3,1,2.')], extension='pdf')
add('pdf-rotator', 'PDF Rotator', 'pdf', 'Rotate all pages in a PDF clockwise.', [choice('angle', 'Clockwise rotation', [90, 180, 270], 90)], extension='pdf')
add('pdf-metadata-viewer', 'PDF Metadata Viewer', 'pdf', 'Inspect PDF page count, page sizes and document metadata.', extension='json')
