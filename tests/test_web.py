import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings
from apps.tools.registry import TOOLS, CATEGORIES, search_tools
from .test_files import photo, document

class PublicWebTests(TestCase):
    def setUp(self):
        from django.conf import settings
        temporary_root = settings.BASE_DIR / '.runtime' / 'test-temp'
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=temporary_root)
        self.addCleanup(self.temporary.cleanup)
        self.overrides = override_settings(RESULT_DIR=Path(self.temporary.name) / 'results', APK_DIR=Path(self.temporary.name) / 'apk')
        self.overrides.enable()
        self.addCleanup(self.overrides.disable)

    def test_public_pages_and_all_tools(self):
        for path in ['/', '/tools/', '/download-app/', '/privacy/', '/about/', '/offline/', '/accounts/login/', '/accounts/signup/', '/sitemap.xml', '/robots.txt', '/manifest.webmanifest', '/sw.js']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        for tool in TOOLS:
            self.assertEqual(self.client.get('/tools/' + tool['slug'] + '/').status_code, 200, tool['slug'])
        for category in CATEGORIES:
            self.assertEqual(self.client.get('/category/' + category['id'] + '/').status_code, 200)
        self.assertEqual(self.client.get('/tools/not-real/').status_code, 404)

    def test_search_aliases_and_typos(self):
        for query, expected in [('compress photo', 'image-compressor'), ('photo 50kb', 'image-compressor'), ('join pdf', 'pdf-merger'), ('json beautify', 'json-formatter'), ('decode token', 'jwt-decoder'), ('json formater', 'json-formatter')]:
            found = self.client.get('/api/search/', {'q': query}).json()['tools']
            self.assertIn(expected, [x['slug'] for x in found[:3]], query)
        self.assertTrue(all(t['category'] == 'pdf' for t in search_tools('', 'pdf')))

    def test_all_text_examples_anonymous(self):
        for i, tool in enumerate(TOOLS):
            if tool['handler'] != 'text':
                continue
            with self.subTest(slug=tool['slug']):
                data = {f['name']: f.get('default', '') for f in tool['fields']}
                data.update(tool['example'])
                response = self.client.post('/api/tools/' + tool['slug'] + '/process/', json.dumps(data), content_type='application/json', REMOTE_ADDR=f'198.51.100.{i}')
                self.assertEqual(response.status_code, 200, response.content[:300])
                result = response.json()
                self.assertIn('text', result)
                if result.get('download_url'):
                    download = self.client.get(result['download_url'])
                    self.assertEqual(download.status_code, 200)
                    self.assertIn('attachment', download['Content-Disposition'])
                    download.close()

    def test_image_upload_result_session_and_cleanup(self):
        response = self.client.post('/api/tools/image-resizer/process/', {'files': photo(), 'width': '40', 'height': '30'})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        output = self.client.get(data['download_url'])
        self.assertEqual(output['Content-Type'], 'image/jpeg')
        self.assertEqual(output['Cache-Control'], 'no-store, private')
        self.assertEqual(output['Content-Security-Policy'], "default-src 'none'; sandbox")
        output.close()
        self.assertEqual(Client().get(data['download_url']).status_code, 404)
        self.assertEqual(self.client.get('/downloads/results/../../../secret/').status_code, 404)
        from apps.downloads.results import cleanup_results
        with patch('apps.downloads.results.time.time', return_value=99999999999):
            self.assertGreater(cleanup_results(), 0)
        self.assertEqual(self.client.get(data['download_url']).status_code, 404)

    def test_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/api/tools/json-formatter/process/', {'text': '{}'}).status_code, 403)
        client.get('/tools/json-formatter/')
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post('/api/tools/json-formatter/process/', {'text': '{}'}, HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_upload_rejection_rate_limit_and_error(self):
        self.assertEqual(self.client.post('/api/tools/image-compressor/process/', {'files': document()}).status_code, 400)
        self.assertEqual(self.client.post('/api/tools/json-formatter/process/', {'text': 'bad'}).status_code, 400)
        for _ in range(30):
            response = self.client.post('/api/tools/json-formatter/process/', {'text': '{}'}, REMOTE_ADDR='203.0.113.9')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post('/api/tools/json-formatter/process/', {'text': '{}'}, REMOTE_ADDR='203.0.113.9').status_code, 429)
        self.assertEqual(self.client.post('/api/tools/json-formatter/process/', {'text': 'a' * 230000}).status_code, 400)

    def test_apk_honest_absence_and_headers(self):
        self.assertContains(self.client.get('/download-app/'), 'coming soon')
        self.assertEqual(self.client.get('/downloads/toolsathi-latest.apk').status_code, 404)
        # Transport unit fixture only; never published and never described as an Android binary.
        from django.conf import settings
        settings.APK_DIR.mkdir(parents=True)
        (settings.APK_DIR / 'toolsathi-latest.apk').write_bytes(b'UNIT-TEST-TRANSPORT-FIXTURE')
        with patch('apps.downloads.views.apk_info', return_value={'available': True}):
            response = self.client.get('/downloads/toolsathi-latest.apk')
            self.assertEqual(response['Content-Type'], 'application/vnd.android.package-archive')
            self.assertEqual(response['Content-Disposition'], 'attachment; filename="ToolSathi.apk"')
            response.close()

    def test_optional_account_preferences(self):
        self.assertEqual(self.client.get('/api/preferences/').status_code, 401)
        response = self.client.post('/accounts/signup/', {'username': 'tester', 'password1': 'Healthy$Unique8Pass47', 'password2': 'Healthy$Unique8Pass47'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='tester').exists())
        self.assertEqual(self.client.get('/accounts/dashboard/').status_code, 200)
        pref = self.client.post('/api/preferences/', json.dumps({'favorites': ['json-formatter'], 'recent': ['image-resizer'], 'history_enabled': False}), content_type='application/json').json()
        self.assertEqual(pref['favorites'], ['json-formatter'])
        self.assertEqual(pref['recent'], [])
        self.assertEqual(self.client.post('/api/preferences/', json.dumps({'favorites': ['secret input']}), content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post('/accounts/logout/').status_code, 302)
        self.assertEqual(self.client.get('/tools/pdf-merger/').status_code, 200)

    def test_seo_and_security_headers(self):
        response = self.client.get('/tools/json-formatter/')
        self.assertContains(response, 'canonical')
        self.assertContains(response, 'application/ld+json')
        self.assertIn("frame-ancestors 'none'", response['Content-Security-Policy'])
        self.assertContains(self.client.get('/sitemap.xml'), '/tools/json-formatter/')
        self.assertContains(self.client.get('/robots.txt'), 'Disallow: /api/')

    def test_secret_results_are_never_persisted(self):
        from django.conf import settings
        for slug, data in [('secure-password-generator', {'length': 24, 'count': 1, 'alphabet': 'symbols'}), ('hash-generator', {'text': 'private-input', 'algorithm': 'sha256'})]:
            response = self.client.post('/api/tools/' + slug + '/process/', data)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('download_url', response.json())
        self.assertFalse(settings.RESULT_DIR.exists())

    def test_storage_quota_and_invalid_api_payload(self):
        with override_settings(RESULT_STORAGE_LIMIT=2):
            response = self.client.post('/api/tools/json-formatter/process/', {'text': '{"a":1}'})
            self.assertEqual(response.status_code, 400)
            self.assertIn('storage', response.json()['error'])
        self.assertEqual(self.client.post('/api/tools/json-formatter/process/', '[]', content_type='application/json').status_code, 400)

    def test_htmx_results_and_pwa_cache_policy(self):
        response = self.client.get('/search/', {'q': 'join pdf'})
        self.assertContains(response, 'PDF Merger')
        self.assertContains(response, 'hx-swap-oob')
        sw = self.client.get('/sw.js')
        self.assertContains(sw, "event.request.method !== 'GET'")
        self.assertContains(sw, "url.pathname.startsWith('/downloads/')")
