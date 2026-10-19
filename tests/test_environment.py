"""Deployment boundaries: private settings cannot become source or shell code."""
import os
import runpy
import tempfile
from pathlib import Path
from unittest import TestCase, skipUnless
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from config.environment import (
    PROJECT_ROOT, EnvironmentFileError, load_configured_environment, load_environment,
)


class PrivateEnvironmentTests(TestCase):
    def setUp(self):
        # Keep test artifacts outside the checkout, as required of real secrets.
        temporary = tempfile.TemporaryDirectory(prefix='toolsathi-env-test-', dir=PROJECT_ROOT.parent)
        self.addCleanup(temporary.cleanup)
        self.private_file = Path(temporary.name) / '.toolsathi.env'
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    def write_private(self, content):
        self.private_file.write_text(content, encoding='utf-8')
        self.private_file.chmod(0o600)

    def test_literal_values_comments_and_authoritative_file(self):
        self.write_private(
            '# private configuration\nDJANGO_DEBUG=false\n'
            'VALUE="$(do-not-execute) ${UNSET} # literal" # comment\n'
            "QUOTED='back\\slash'\nEMPTY=\nPLAIN=example # comment\n"
        )
        os.environ['DJANGO_DEBUG'] = 'true'
        values = load_environment(self.private_file)
        self.assertEqual(os.environ['DJANGO_DEBUG'], 'false')
        self.assertEqual(values['VALUE'], '$(do-not-execute) ${UNSET} # literal')
        self.assertEqual(values['QUOTED'], 'back\\slash')
        self.assertEqual(values['EMPTY'], '')
        self.assertEqual(values['PLAIN'], 'example')

    def test_opt_in_only_and_preserve_environment_option(self):
        self.write_private('VALUE=from-file\n')
        self.assertEqual(load_configured_environment(), {})
        os.environ['VALUE'] = 'inherited'
        load_environment(self.private_file, override=False)
        self.assertEqual(os.environ['VALUE'], 'inherited')
        os.environ['TOOLSATHI_ENV_FILE'] = str(self.private_file)
        load_configured_environment()
        self.assertEqual(os.environ['VALUE'], 'from-file')

    def test_management_and_wsgi_load_private_values_before_django_starts(self):
        self.write_private('DJANGO_DEBUG=false\nDJANGO_SECRET_KEY=test-only-private-value\n')
        os.environ['TOOLSATHI_ENV_FILE'] = str(self.private_file)
        for path, mocked_entry in (
            (PROJECT_ROOT / 'manage.py', 'django.core.management.execute_from_command_line'),
            (PROJECT_ROOT / 'config' / 'wsgi.py', 'django.core.wsgi.get_wsgi_application'),
        ):
            os.environ.pop('DJANGO_SECRET_KEY', None)
            def check_loaded(*args):
                self.assertEqual(os.environ['DJANGO_SECRET_KEY'], 'test-only-private-value')
                self.assertEqual(os.environ['DJANGO_DEBUG'], 'false')
                return None
            with patch(mocked_entry, side_effect=check_loaded) as mocked:
                runpy.run_path(str(path), run_name='__main__')
                mocked.assert_called_once()

    def test_malformed_and_duplicate_lines_do_not_partially_load_or_leak(self):
        for invalid in (
            'SENSITIVE=private-value\nSENSITIVE=second-value\n',
            'SENSITIVE=private-value\nexport BAD=private-value\n',
            'SENSITIVE=private-value\nBAD="private-value\n',
            'SENSITIVE=private-value\nBAD="private-value" trailing\n',
            'SENSITIVE=private-value\nBAD=private-value\x00\n',
        ):
            with self.subTest(case=invalid.splitlines()[-1].split('=')[0]):
                self.write_private(invalid)
                with self.assertRaises(EnvironmentFileError) as raised:
                    load_environment(self.private_file)
                self.assertNotIn('private-value', str(raised.exception))
                self.assertNotIn('SENSITIVE', os.environ)

    def test_relative_path_and_source_checkout_are_rejected(self):
        with self.assertRaises(EnvironmentFileError):
            load_environment('.env')
        with self.assertRaisesRegex(EnvironmentFileError, 'outside the source checkout'):
            load_environment(PROJECT_ROOT / '.env.example')

    def test_missing_non_utf8_and_oversized_files_fail_without_values(self):
        with self.assertRaises(EnvironmentFileError):
            load_environment(self.private_file)
        self.write_private('SAFE=small\n')
        for data in (b'VALUE=\xff\n', b'VALUE=' + b'x' * 65536):
            self.private_file.write_bytes(data)
            with self.assertRaises(EnvironmentFileError):
                load_environment(self.private_file)

    @skipUnless(os.name == 'posix', 'POSIX permissions are enforced on the Linux deployment host.')
    def test_public_permissions_and_symlinks_are_rejected(self):
        self.write_private('VALUE=private\n')
        self.private_file.chmod(0o644)
        with self.assertRaisesRegex(EnvironmentFileError, '0600'):
            load_environment(self.private_file)
        self.private_file.chmod(0o600)
        alias = self.private_file.with_name('alias.env')
        alias.symlink_to(self.private_file)
        with self.assertRaisesRegex(EnvironmentFileError, 'symlink'):
            load_environment(alias)


class ProductionOriginTests(TestCase):
    def settings_for(self, **overrides):
        environment = {
            'DJANGO_DEBUG': 'false',
            'DJANGO_SECRET_KEY': 'test-only-secret-' * 5,
            'DJANGO_ALLOWED_HOSTS': 'anandtrip22.pythonanywhere.com',
            'SITE_URL': 'https://anandtrip22.pythonanywhere.com',
        }
        environment.update(overrides)
        with patch.dict(os.environ, environment, clear=True):
            return runpy.run_path(str(PROJECT_ROOT / 'config' / 'settings.py'))

    def test_production_origin_cookies_csrf_and_proxy_are_explicit(self):
        settings = self.settings_for(GOOGLE_SITE_VERIFICATION=' issued-token ')
        self.assertEqual(settings['CSRF_TRUSTED_ORIGINS'], ['https://anandtrip22.pythonanywhere.com'])
        self.assertTrue(settings['SESSION_COOKIE_SECURE'])
        self.assertTrue(settings['CSRF_COOKIE_SECURE'])
        self.assertTrue(settings['SECURE_SSL_REDIRECT'])
        self.assertEqual(settings['GOOGLE_SITE_VERIFICATION'], 'issued-token')
        self.assertNotIn('SECURE_PROXY_SSL_HEADER', settings)
        self.assertFalse(settings['TRUST_PYTHONANYWHERE_PROXY'])
        self.assertTrue(self.settings_for(TRUST_PYTHONANYWHERE_PROXY='true')['TRUST_PYTHONANYWHERE_PROXY'])
        self.assertEqual(self.settings_for(TRUST_PROXY_HTTPS='true')['SECURE_PROXY_SSL_HEADER'],
                         ('HTTP_X_FORWARDED_PROTO', 'https'))

    def test_invalid_origins_and_host_mismatch_fail_closed(self):
        for origin in (
            'http://anandtrip22.pythonanywhere.com',
            'https://anandtrip22.pythonanywhere.com/tools/',
            'https://anandtrip22.pythonanywhere.com?query=value',
            'https://anandtrip22.pythonanywhere.com#fragment',
            'https://anandtrip22.pythonanywhere.com?',
            'https://anandtrip22.pythonanywhere.com#',
            'https://user:private-value@anandtrip22.pythonanywhere.com',
            'https://anandtrip22.pythonanywhere.com:8443',
            'https://other.example', 'https://', 'https://[invalid',
        ):
            with self.subTest(origin=origin.split('@')[-1]):
                with self.assertRaises(ImproperlyConfigured) as raised:
                    self.settings_for(SITE_URL=origin)
                self.assertNotIn('private-value', str(raised.exception))
        for local in ('localhost', 'localhost.', 'sub.localhost', 'sub.localhost.', '127.0.0.1', '127.0.0.1.', '[::1]'):
            with self.subTest(local=local):
                with self.assertRaises(ImproperlyConfigured):
                    self.settings_for(SITE_URL='https://' + local, DJANGO_ALLOWED_HOSTS=local.strip('[]'))

    def test_missing_secret_and_empty_allowed_hosts_fail_closed(self):
        with self.assertRaises(ImproperlyConfigured):
            self.settings_for(DJANGO_SECRET_KEY='')
        with self.assertRaises(ImproperlyConfigured):
            self.settings_for(DJANGO_ALLOWED_HOSTS='')
        with self.assertRaises(ImproperlyConfigured):
            self.settings_for(DJANGO_ALLOWED_HOSTS='anandtrip22.pythonanywhere.com,*')
