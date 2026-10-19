"""Production-origin SEO and optional ownership-verification regression checks."""
from html.parser import HTMLParser
from unittest.mock import patch
from xml.etree import ElementTree

from django.test import SimpleTestCase, override_settings

from apps.tools.registry import CATEGORIES, TOOLS


SITE_URL = 'https://anandtrip22.pythonanywhere.com'


class HeadParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.in_head = False
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'head':
            self.in_head = True
        if self.in_head:
            self.tags.append((tag, dict(attrs)))

    def handle_endtag(self, tag):
        if tag == 'head':
            self.in_head = False

    def attributes(self, tag, attribute, value):
        return [attrs for name, attrs in self.tags if name == tag and attrs.get(attribute) == value]


@override_settings(SITE_URL=SITE_URL, ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False)
class DeploymentSeoTests(SimpleTestCase):
    def test_sitemap_has_exact_public_inventory_on_production_origin(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        locations = [node.text for node in ElementTree.fromstring(response.content).iter(
            '{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        paths = ['/', '/tools/', '/about/', '/privacy/', '/download-app/']
        paths += [f"/category/{category['id']}/" for category in CATEGORIES]
        paths += [f"/tools/{tool['slug']}/" for tool in TOOLS if tool['status'] == 'available']
        self.assertEqual(set(locations), {SITE_URL + path for path in paths})
        self.assertEqual(len(locations), len(set(locations)))
        self.assertEqual(len([tool for tool in TOOLS if tool['status'] == 'available']), 83)

    def test_sitemap_omits_unavailable_tools(self):
        with patch('apps.tools.registry.TOOLS', [*TOOLS, {'slug': 'not-launched', 'status': 'coming-soon'}]):
            self.assertNotContains(self.client.get('/sitemap.xml'), 'not-launched')

    def test_robots_advertises_correct_sitemap_and_private_exclusions(self):
        response = self.client.get('/robots.txt')
        self.assertContains(response, f'Sitemap: {SITE_URL}/sitemap.xml')
        for path in ('/api/', '/accounts/', '/admin/', '/downloads/results/'):
            self.assertContains(response, 'Disallow: ' + path)
        self.assertNotContains(response, 'Disallow: /\n')

    def test_tool_metadata_is_unique_and_canonical_ignores_query_parameters(self):
        titles, descriptions = [], []
        for tool in TOOLS:
            path = f"/tools/{tool['slug']}/"
            with self.subTest(slug=tool['slug']):
                response = self.client.get(path, {'source': 'search'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['canonical'], SITE_URL + path)
                head = HeadParser(response.content.decode())
                self.assertEqual(head.attributes('link', 'rel', 'canonical'), [
                    {'rel': 'canonical', 'href': SITE_URL + path}])
                descriptions.append(head.attributes('meta', 'name', 'description')[0]['content'])
                titles.append(response.context['page_title'])
        self.assertEqual(len(titles), len(set(titles)))
        self.assertEqual(len(descriptions), len(set(descriptions)))
        self.assertTrue(all(titles) and all(descriptions))

    def test_blank_verification_is_omitted(self):
        for value in ('', '   '):
            with self.subTest(value=value), override_settings(GOOGLE_SITE_VERIFICATION=value):
                self.assertNotContains(self.client.get('/'), 'name="google-site-verification"')

    def test_configured_verification_is_in_head_and_autoescaped(self):
        value = 'test-verification-value"><script>not-executable</script>&'
        with override_settings(GOOGLE_SITE_VERIFICATION=value):
            response = self.client.get('/')
        head = HeadParser(response.content.decode())
        self.assertEqual(head.attributes('meta', 'name', 'google-site-verification'), [
            {'name': 'google-site-verification', 'content': value}])
        self.assertNotContains(response, '<script>not-executable</script>')
