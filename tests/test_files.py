import io
import json
import zipfile
from django.test import SimpleTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from pypdf import PdfReader, PdfWriter
from tools_logic.file_tools import process, page_indices, BoundedBuffer

def photo(fmt='PNG', size=(320, 160)):
    out = io.BytesIO()
    Image.new('RGB', size, '#777777').save(out, fmt)
    return SimpleUploadedFile('image.' + fmt.lower(), out.getvalue(), content_type='application/octet-stream')

def document(widths=(100, 200, 300)):
    writer = PdfWriter()
    for width in widths:
        writer.add_blank_page(width=width, height=400)
    out = io.BytesIO()
    writer.write(out)
    return SimpleUploadedFile('document.pdf', out.getvalue())

class ImageTests(SimpleTestCase):
    def test_all_transformations(self):
        cases = [('image-compressor', 'PNG', {}, 'JPEG', (320, 160)),
                 ('image-resizer', 'PNG', {'width': 100, 'height': 100, 'keep_aspect': 'on'}, 'JPEG', (100, 50)),
                 ('jpg-to-png', 'JPEG', {}, 'PNG', (320, 160)), ('png-to-jpg', 'PNG', {}, 'JPEG', (320, 160)),
                 ('image-to-webp', 'PNG', {}, 'WEBP', (320, 160)), ('webp-to-png', 'WEBP', {}, 'PNG', (320, 160)),
                 ('image-cropper', 'PNG', {'left': 10, 'top': 10, 'width': 50, 'height': 40}, 'JPEG', (50, 40)),
                 ('image-rotator', 'PNG', {'angle': 90}, 'JPEG', (160, 320)),
                 ('image-quality-reducer', 'PNG', {'quality': 20}, 'JPEG', (320, 160)),
                 ('signature-resizer', 'PNG', {}, 'PNG', (300, 100))]
        for slug, fmt, data, output_format, dimensions in cases:
            with self.subTest(slug=slug):
                result = process(slug, data, [photo(fmt)])
                image = Image.open(io.BytesIO(result['data']))
                self.assertEqual(image.format, output_format)
                self.assertEqual(image.size, dimensions)

    def test_target_size(self):
        result = process('image-compressor', {'target_kb': 1}, [photo(size=(2000, 1000))])
        self.assertLessEqual(len(result['data']), 1024)

    def test_metadata_and_dimensions(self):
        for slug in ('image-dimension-checker', 'image-metadata-viewer'):
            result = json.loads(process(slug, {}, [photo()])['text'])
            self.assertEqual(result['width'], 320)
            self.assertEqual(result['format'], 'PNG')

    def test_invalid_uploads(self):
        for inputs in ([], [SimpleUploadedFile('fake.png', b'<script>bad</script>')], [photo(), photo()]):
            with self.assertRaises(ValueError):
                process('image-compressor', {}, inputs)
        with self.assertRaises(ValueError):
            process('image-cropper', {'width': 9999, 'height': 50}, [photo()])
        with self.assertRaises(ValueError):
            process('jpg-to-png', {}, [photo('PNG')])

class PDFTests(SimpleTestCase):
    def test_generated_output_has_streaming_limit(self):
        buffer = BoundedBuffer()
        buffer.limit = 10
        buffer.write(b'12345678')
        with self.assertRaises(ValueError):
            buffer.write(b'901')
        self.assertLessEqual(len(buffer.getvalue()), 10)

    def test_merge(self):
        result = process('pdf-merger', {}, [document((100,)), document((200, 300))])
        pdf = PdfReader(io.BytesIO(result['data']))
        self.assertEqual([int(p.mediabox.width) for p in pdf.pages], [100, 200, 300])

    def test_extract_reorder_rotate(self):
        result = process('pdf-page-extractor', {'pages': '1,3'}, [document()])
        self.assertEqual(len(PdfReader(io.BytesIO(result['data'])).pages), 2)
        result = process('pdf-page-reorder', {'pages': '3,1,2'}, [document()])
        self.assertEqual([int(p.mediabox.width) for p in PdfReader(io.BytesIO(result['data'])).pages], [300, 100, 200])
        result = process('pdf-rotator', {'angle': 90}, [document()])
        self.assertEqual(PdfReader(io.BytesIO(result['data'])).pages[0].rotation, 90)
        with self.assertRaises(ValueError):
            process('pdf-page-reorder', {'pages': '1,2'}, [document()])

    def test_split_and_metadata(self):
        result = process('pdf-splitter', {}, [document()])
        with zipfile.ZipFile(io.BytesIO(result['data'])) as archive:
            self.assertEqual(len(archive.namelist()), 3)
            self.assertEqual(len(PdfReader(io.BytesIO(archive.read('page-002.pdf'))).pages), 1)
        result = json.loads(process('pdf-metadata-viewer', {}, [document()])['text'])
        self.assertEqual(result['pages'], 3)

    def test_image_to_pdf(self):
        for slug, fmt in [('jpg-to-pdf', 'JPEG'), ('png-to-pdf', 'PNG')]:
            result = process(slug, {}, [photo(fmt), photo(fmt)])
            self.assertEqual(len(PdfReader(io.BytesIO(result['data'])).pages), 2)

    def test_pages_and_encryption(self):
        for value in ('0', '4', '2-1', '../file', '1,1'):
            with self.assertRaises(ValueError):
                page_indices(value, 3)
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt('password')
        out = io.BytesIO()
        writer.write(out)
        with self.assertRaises(ValueError):
            process('pdf-splitter', {}, [SimpleUploadedFile('locked.pdf', out.getvalue())])
        with self.assertRaises(ValueError):
            process('pdf-splitter', {}, [SimpleUploadedFile('fake.pdf', b'Not a PDF')])
