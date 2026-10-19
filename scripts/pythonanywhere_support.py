"""Account-specific deployment checks. Never print private environment values."""
import argparse
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.environment import load_environment

HOME = Path('/home/anandtrip22')
PROJECT = HOME / 'toolsathi'
ENV_FILE = HOME / '.toolsathi.env'
PRIVATE = HOME / '.local/share/toolsathi'
ORIGIN = 'https://anandtrip22.pythonanywhere.com'
HOST = 'anandtrip22.pythonanywhere.com'
MIB = 1024 * 1024
DISK_LIMIT = 512 * MIB
RESULT_LIMIT = 32 * MIB


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_no_symlinks(path):
    path = Path(path)
    require(path.is_absolute(), 'Deployment paths must be absolute.')
    for component in (path, *path.parents):
        require(not component.is_symlink(), 'Deployment paths must not traverse symlinks.')


def private_directory(path):
    """Only used for the three application-owned persistent directories."""
    path = Path(path)
    check_no_symlinks(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.stat()
    require(stat.S_ISDIR(info.st_mode), 'Private storage must be a directory.')
    if os.name == 'posix':
        require(info.st_uid == os.getuid(), 'Private storage must belong to the current account.')
        path.chmod(0o700)
    require(os.access(path, os.R_OK | os.W_OK | os.X_OK), 'Private storage is not writable.')


def create_environment(path=ENV_FILE, project=PROJECT, private=PRIVATE):
    """Exclusive creation retains an existing secret and never evaluates shell text."""
    path, project, private = Path(path), Path(project), Path(private)
    check_no_symlinks(path)
    if path.exists():
        load_environment(path, override=True)
        return False
    for directory in (private, private / 'results', private / 'apk'):
        private_directory(directory)
    values = {
        'DJANGO_DEBUG': 'false',
        'DJANGO_SECRET_KEY': secrets.token_urlsafe(64),
        'DJANGO_ALLOWED_HOSTS': HOST,
        'SITE_URL': ORIGIN,
        # PythonAnywhere supplies the WSGI HTTPS scheme; do not trust client headers.
        'TRUST_PROXY_HTTPS': 'false',
        'TRUST_PYTHONANYWHERE_PROXY': 'true',
        'DATABASE_URL': 'sqlite:///' + (project / 'db.sqlite3').as_posix(),
        'RESULT_DIR': (private / 'results').as_posix(),
        'APK_DIR': (private / 'apk').as_posix(),
        'RESULT_STORAGE_LIMIT': str(RESULT_LIMIT),
    }
    data = '# Private ToolSathi configuration. Do not commit, print or shell-source.\n'
    data += ''.join(f'{key}={value}\n' for key, value in values.items())
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    return True


def validate_environment():
    values = load_environment(ENV_FILE, override=True)
    expected = {
        'DJANGO_DEBUG': 'false', 'DJANGO_ALLOWED_HOSTS': HOST, 'SITE_URL': ORIGIN,
        'TRUST_PROXY_HTTPS': 'false',
        'TRUST_PYTHONANYWHERE_PROXY': 'true',
        'DATABASE_URL': 'sqlite:///' + (PROJECT / 'db.sqlite3').as_posix(),
        'RESULT_DIR': (PRIVATE / 'results').as_posix(),
        'APK_DIR': (PRIVATE / 'apk').as_posix(),
        'RESULT_STORAGE_LIMIT': str(RESULT_LIMIT),
    }
    for key, required in expected.items():
        require(values.get(key) == required, f'Private configuration {key} does not match the reviewed account configuration; inspect it without printing secrets.')
    require(len(values.get('DJANGO_SECRET_KEY', '')) >= 50, 'Production secret must contain at least 50 characters.')
    print('Private environment validated; values are not displayed.')


def disk_check(existing_venv=False, after_install=False):
    # statvfs alone reports the shared server disk, not this account's quota.
    result = subprocess.run(['du', '-sx', '--block-size=1', str(HOME)], check=True, capture_output=True, text=True)
    used = int(result.stdout.split()[0])
    remaining = min(DISK_LIMIT - used, shutil.disk_usage(HOME).free)
    required = (64 if after_install else 96 if existing_venv else 192) * MIB
    print(f'Estimated home usage: {used / MIB:.1f} / 512 MiB; usable headroom: {max(remaining, 0) / MIB:.1f} MiB.')
    require(remaining >= required, f'Need at least {required // MIB} MiB headroom for this stage. Check the account quota and existing files; no cleanup/deletion is performed.')
    print('Account dashboard quota is authoritative; this check estimates home-directory blocks.')


def django_setup():
    validate_environment()
    os.environ['TOOLSATHI_ENV_FILE'] = str(ENV_FILE)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    import django
    django.setup()
    return django


def validate_settings():
    django_setup()
    from django.conf import settings
    from django.db import connection
    require(not settings.DEBUG, 'DEBUG must be false.')
    require(settings.SITE_URL == ORIGIN and settings.ALLOWED_HOSTS == [HOST], 'Production origin/host mismatch.')
    require(settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE and settings.SECURE_SSL_REDIRECT, 'Production HTTPS settings are incomplete.')
    require(settings.CSRF_TRUSTED_ORIGINS == [ORIGIN], 'CSRF trusted origin mismatch.')
    require(getattr(settings, 'SECURE_PROXY_SSL_HEADER', None) is None, 'Do not trust forwarded HTTPS headers without a separately reviewed proxy configuration.')
    require(settings.TRUST_PYTHONANYWHERE_PROXY, 'Enable the verified PythonAnywhere X-Real-IP client-address handling.')
    database = settings.DATABASES['default']
    require(database['ENGINE'] == 'django.db.backends.sqlite3', 'This free-account deployment expects persistent SQLite.')
    require(Path(database['NAME']) == PROJECT / 'db.sqlite3', 'Database path must preserve the project SQLite database.')
    require(settings.RESULT_DIR == PRIVATE / 'results' and settings.APK_DIR == PRIVATE / 'apk', 'Private storage locations do not match the account configuration.')
    require(settings.RESULT_STORAGE_LIMIT == RESULT_LIMIT, 'Temporary storage quota must be 32 MiB.')
    for directory in (PRIVATE, settings.RESULT_DIR, settings.APK_DIR):
        private_directory(directory)
    db_path = Path(database['NAME'])
    check_no_symlinks(db_path)
    if db_path.exists():
        require(db_path.is_file(), 'SQLite path must be a regular file.')
        if os.name == 'posix':
            require(db_path.stat().st_uid == os.getuid(), 'SQLite must belong to the current account.')
            db_path.chmod(0o600)
    with connection.cursor() as cursor:
        cursor.execute('PRAGMA quick_check')
        require(cursor.fetchall() == [('ok',)], 'SQLite quick_check failed; inspect and back up the existing database before changes.')
    connection.close()
    if os.name == 'posix':
        db_path.chmod(0o600)
    print('Production settings, persistent SQLite and private storage validated.')


def static_permissions():
    django_setup()
    from django.conf import settings
    root = Path(settings.STATIC_ROOT)
    require(root == PROJECT / 'staticfiles', 'Unexpected static root; refusing permission changes.')
    check_no_symlinks(root)
    require(root.is_dir(), 'Run collectstatic before checking public static permissions.')
    paths = [root, *root.rglob('*')]
    require(all(not path.is_symlink() for path in paths), 'Collected static files must not contain symlinks.')
    for path in paths:
        require(path.is_dir() or path.is_file(), 'Unexpected non-regular static entry.')
        path.chmod(0o755 if path.is_dir() else 0o644)
    print('Only collected public static assets set readable for the static server.')


def verify_site():
    validate_settings()
    from django.conf import settings
    from django.test import Client
    from django.templatetags.static import static
    from apps.tools.registry import CATEGORIES, TOOLS
    client = Client(HTTP_HOST=HOST)
    sitemap = client.get('/sitemap.xml', secure=True)
    require(sitemap.status_code == 200, 'In-process sitemap request failed.')
    locations = [item.text for item in ET.fromstring(sitemap.content).iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
    expected_paths = {'/', '/tools/', '/about/', '/privacy/', '/download-app/'}
    expected_paths.update('/category/' + item['id'] + '/' for item in CATEGORIES)
    available = [item for item in TOOLS if item['status'] == 'available']
    expected_paths.update('/tools/' + item['slug'] + '/' for item in available)
    require(len(locations) == len(set(locations)), 'Sitemap contains duplicate URLs.')
    require(set(locations) == {ORIGIN + path for path in expected_paths}, 'Sitemap origins or available-tool URLs do not match.')
    robots = client.get('/robots.txt', secure=True)
    require(robots.status_code == 200 and 'Sitemap: ' + ORIGIN + '/sitemap.xml' in robots.content.decode(), 'robots.txt does not reference the public sitemap.')
    homepage = client.get('/', secure=True)
    require(homepage.status_code == 200, 'In-process anonymous homepage request failed.')
    require(f'<link rel="canonical" href="{ORIGIN}/">' in homepage.content.decode(), 'Homepage canonical URL does not match the public origin.')
    redirect = client.get('/', secure=False)
    require(redirect.status_code in (301, 308) and redirect['Location'] == ORIGIN + '/', 'In-process HTTP-to-HTTPS redirect failed.')
    for asset in ('css/site.css', 'js/site.js'):
        url = static(asset)
        require((Path(settings.STATIC_ROOT) / url.removeprefix('/static/')).is_file(), 'A versioned public static asset is missing.')
    print(f'In-process anonymous homepage, HTTPS redirect, robots, canonical, static assets and {len(available)} sitemap tools passed.')
    print('These checks do not verify the live platform proxy, certificate or Web tab configuration.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init-env', 'validate-env', 'disk-check', 'settings', 'static-permissions', 'verify'])
    parser.add_argument('--existing-venv', choices=['0', '1'], default='0')
    parser.add_argument('--after-install', action='store_true')
    arguments = parser.parse_args()
    require(ROOT == PROJECT, 'Run the account-specific helper from /home/anandtrip22/toolsathi.')
    require(Path.home() == HOME, 'Run in the existing anandtrip22 account.')
    check_no_symlinks(PROJECT)
    if arguments.command == 'init-env':
        created = create_environment()
        print('Private environment created securely.' if created else 'Existing private environment retained.')
    elif arguments.command == 'validate-env':
        validate_environment()
    elif arguments.command == 'disk-check':
        disk_check(arguments.existing_venv == '1', arguments.after_install)
    elif arguments.command == 'settings':
        validate_settings()
    elif arguments.command == 'static-permissions':
        static_permissions()
    else:
        verify_site()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Known validation errors are designed not to contain private values.
        # Dependency/OS exception text might contain a URL or secret; omit it.
        if isinstance(exc, ValueError):
            print(f'ERROR: {exc}', file=sys.stderr)
        else:
            print(f'ERROR: Deployment helper failed ({type(exc).__name__}); inspect local configuration without exposing secrets.', file=sys.stderr)
        raise SystemExit(1)
