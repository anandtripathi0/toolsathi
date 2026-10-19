"""Safety boundaries of repeatable deployment, independent of remote access."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from config.environment import EnvironmentFileError, load_environment
from scripts import pythonanywhere_support as deploy


class DeploymentSafetyTests(TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='toolsathi-deploy-test-', dir=deploy.ROOT.parent)
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.project = self.home / 'toolsathi'
        self.project.mkdir()
        self.private = self.home / '.local/share/toolsathi'
        self.envfile = self.home / '.toolsathi.env'
        environment = patch.dict(os.environ, {}, clear=False)
        environment.start()
        self.addCleanup(environment.stop)

    def create_environment(self):
        return deploy.create_environment(self.envfile, self.project, self.private)

    def test_repeated_setup_retains_secret_database_and_artifacts(self):
        database = self.project / 'db.sqlite3'
        database.write_bytes(b'existing-database')
        self.assertTrue(self.create_environment())
        original = self.envfile.read_bytes()
        values = load_environment(self.envfile)
        self.assertGreaterEqual(len(values['DJANGO_SECRET_KEY']), 80)
        self.assertEqual(values['TRUST_PROXY_HTTPS'], 'false')
        self.assertEqual(values['TRUST_PYTHONANYWHERE_PROXY'], 'true')
        self.assertEqual(values['RESULT_STORAGE_LIMIT'], str(32 * 1024 * 1024))
        artifact = self.private / 'apk' / 'private-release.apk'
        artifact.write_bytes(b'existing-artifact')
        self.assertFalse(self.create_environment())
        self.assertEqual(self.envfile.read_bytes(), original)
        self.assertEqual(database.read_bytes(), b'existing-database')
        self.assertEqual(artifact.read_bytes(), b'existing-artifact')

    def test_existing_invalid_configuration_is_preserved(self):
        self.envfile.write_text('MALFORMED PRIVATE CONTENT', encoding='utf-8')
        self.envfile.chmod(0o600)
        with self.assertRaises(EnvironmentFileError):
            self.create_environment()
        self.assertEqual(self.envfile.read_text(), 'MALFORMED PRIVATE CONTENT')

    def test_relative_or_symlink_paths_fail_before_writing(self):
        with self.assertRaisesRegex(ValueError, 'absolute'):
            deploy.check_no_symlinks(Path('relative'))
        # Simulate a symlink component even on Windows without symlink privileges.
        with patch.object(Path, 'is_symlink', side_effect=lambda: True):
            with self.assertRaisesRegex(ValueError, 'symlink'):
                self.create_environment()
        self.assertFalse(self.envfile.exists())

    def test_environment_validation_checks_actual_target_without_secret_output(self):
        self.create_environment()
        output = io.StringIO()
        with patch.multiple(deploy, ENV_FILE=self.envfile, PROJECT=self.project, PRIVATE=self.private):
            with contextlib.redirect_stdout(output):
                deploy.validate_environment()
            values = load_environment(self.envfile)
            self.assertNotIn(values['DJANGO_SECRET_KEY'], output.getvalue())
            altered = self.envfile.read_text().replace(deploy.ORIGIN, 'https://other.example')
            self.envfile.write_text(altered)
            with self.assertRaisesRegex(ValueError, 'SITE_URL'):
                deploy.validate_environment()

    def test_quota_headroom_blocks_install_without_deleting_files(self):
        usage = SimpleNamespace(stdout=str(450 * deploy.MIB) + '\t/home/anandtrip22\n')
        with patch.object(deploy.subprocess, 'run', return_value=usage), \
             patch.object(deploy.shutil, 'disk_usage', return_value=SimpleNamespace(free=1024 * deploy.MIB)), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'headroom'):
                deploy.disk_check(existing_venv=True)
            with self.assertRaisesRegex(ValueError, 'headroom'):
                deploy.disk_check(existing_venv=True, after_install=True)

    def test_filesystem_headroom_is_checked_even_when_account_is_small(self):
        usage = SimpleNamespace(stdout=str(10 * deploy.MIB) + '\t/home/anandtrip22\n')
        with patch.object(deploy.subprocess, 'run', return_value=usage), \
             patch.object(deploy.shutil, 'disk_usage', return_value=SimpleNamespace(free=20 * deploy.MIB)), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'headroom'):
                deploy.disk_check()

    def test_quota_check_accepts_sufficient_headroom(self):
        usage = SimpleNamespace(stdout=str(100 * deploy.MIB) + '\t/home/anandtrip22\n')
        with patch.object(deploy.subprocess, 'run', return_value=usage), \
             patch.object(deploy.shutil, 'disk_usage', return_value=SimpleNamespace(free=1024 * deploy.MIB)), \
             contextlib.redirect_stdout(io.StringIO()):
            deploy.disk_check()
