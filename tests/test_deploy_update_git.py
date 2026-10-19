"""Exercise the deployment merge against disposable repositories, never GitHub."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
from unittest import TestCase, skipUnless


ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which('git')


@skipUnless(GIT, 'Git is required for the isolated update regression test.')
class DeploymentGitPreservationTests(TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='toolsathi-git-test-', dir=ROOT.parent)
        self.addCleanup(temporary.cleanup)
        self.fixture = Path(temporary.name)
        self.upstream = self.fixture / 'upstream'
        self.deployed = self.fixture / 'deployed'
        # An inherited GIT_DIR or GIT_WORK_TREE must never redirect these fixtures.
        self.environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        self.environment.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT='0')
        self.git(self.fixture, 'init', '--initial-branch=main', str(self.upstream))
        (self.upstream / '.gitignore').write_text('db.sqlite3\n', encoding='utf-8')
        (self.upstream / 'application.txt').write_text('version one\n', encoding='utf-8')
        self.git(self.upstream, 'add', '.gitignore', 'application.txt')
        self.git(self.upstream, 'commit', '-m', 'Initial fixture')
        self.git(self.fixture, 'clone', '--no-hardlinks', str(self.upstream), str(self.deployed))
        self.database = self.deployed / 'db.sqlite3'
        self.database.write_bytes(b'EXISTING_DATABASE_TEST_FIXTURE')
        script = (ROOT / 'scripts' / 'update_pythonanywhere.sh').read_text(encoding='utf-8')
        merge_line = next(line for line in script.splitlines() if line.startswith('git merge --ff-only '))
        self.merge_arguments = shlex.split(merge_line)[1:]

    def git(self, directory, *arguments, check=True):
        return subprocess.run(
            [GIT, '-c', 'user.name=ToolSathi Deployment Test', '-c', 'user.email=fixture@example.invalid',
             '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=' + os.devnull, *arguments],
            cwd=directory, env=self.environment, check=check, capture_output=True, text=True, timeout=30,
        )

    def test_upstream_database_collision_aborts_without_changing_live_bytes(self):
        original_head = self.git(self.deployed, 'rev-parse', 'HEAD').stdout.strip()
        (self.upstream / 'db.sqlite3').write_bytes(b'ACCIDENTALLY_COMMITTED_DATABASE_FIXTURE')
        self.git(self.upstream, 'add', '--force', 'db.sqlite3')
        self.git(self.upstream, 'commit', '-m', 'Simulate accidental upstream database')
        self.git(self.deployed, 'fetch', '--no-tags', 'origin', 'main')
        result = self.git(self.deployed, *self.merge_arguments, check=False)
        self.assertNotEqual(result.returncode, 0, 'An update must refuse to overwrite ignored SQLite data.')
        self.assertEqual(self.database.read_bytes(), b'EXISTING_DATABASE_TEST_FIXTURE')
        self.assertEqual(self.git(self.deployed, 'rev-parse', 'HEAD').stdout.strip(), original_head)

    def test_normal_fast_forward_keeps_the_ignored_database(self):
        (self.upstream / 'application.txt').write_text('version two\n', encoding='utf-8')
        self.git(self.upstream, 'add', 'application.txt')
        self.git(self.upstream, 'commit', '-m', 'Normal source update')
        self.git(self.deployed, 'fetch', '--no-tags', 'origin', 'main')
        self.git(self.deployed, *self.merge_arguments)
        self.assertEqual((self.deployed / 'application.txt').read_text(encoding='utf-8'), 'version two\n')
        self.assertEqual(self.database.read_bytes(), b'EXISTING_DATABASE_TEST_FIXTURE')
