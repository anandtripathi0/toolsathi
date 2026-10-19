from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from apps.core.middleware import RequestGuardMiddleware, _client_ip


class PythonAnywhereClientLimitTests(TestCase):
    def setUp(self):
        self.requests = RequestFactory()
        self.middleware = RequestGuardMiddleware(lambda request: HttpResponse('ok'))
        clock = patch('apps.core.middleware.time.time', return_value=1800000001)
        clock.start()
        self.addCleanup(clock.stop)

    def request(self, **headers):
        return self.requests.post('/api/tools/json-formatter/process/', {}, REMOTE_ADDR='10.0.0.5', **headers)

    @override_settings(TRUST_PYTHONANYWHERE_PROXY=True)
    def test_distinct_visitors_do_not_share_the_proxy_limit(self):
        for _ in range(30):
            self.assertEqual(self.middleware(self.request(HTTP_X_REAL_IP='198.51.100.10')).status_code, 200)
        self.assertEqual(self.middleware(self.request(HTTP_X_REAL_IP='198.51.100.10')).status_code, 429)
        self.assertEqual(self.middleware(self.request(HTTP_X_REAL_IP='198.51.100.11')).status_code, 200)

    @override_settings(TRUST_PYTHONANYWHERE_PROXY=False)
    def test_untrusted_real_ip_and_forwarded_for_cannot_evade_limit(self):
        for index in range(30):
            response = self.middleware(self.request(HTTP_X_REAL_IP=f'198.51.100.{index}', HTTP_X_FORWARDED_FOR=f'203.0.113.{index}'))
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.middleware(self.request(HTTP_X_REAL_IP='198.51.100.99')).status_code, 429)

    @override_settings(TRUST_PYTHONANYWHERE_PROXY=True)
    def test_invalid_or_missing_real_ip_falls_back_and_never_uses_forwarded_for(self):
        for value in ('', 'not-an-ip', '198.51.100.1, 198.51.100.2', '[::1]', 'fe80::1%eth0'):
            with self.subTest(value=value):
                self.assertEqual(_client_ip(self.request(HTTP_X_REAL_IP=value, HTTP_X_FORWARDED_FOR='203.0.113.1')), '10.0.0.5')
        self.assertEqual(_client_ip(self.request()), '10.0.0.5')

    @override_settings(TRUST_PYTHONANYWHERE_PROXY=True)
    def test_ipv6_format_is_normalized_to_one_identity(self):
        first = _client_ip(self.request(HTTP_X_REAL_IP='2001:db8:0:0:0:0:0:1'))
        second = _client_ip(self.request(HTTP_X_REAL_IP='2001:db8::1'))
        self.assertEqual(first, second)
