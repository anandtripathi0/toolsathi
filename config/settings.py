"""Environment-driven settings. Production fails closed without explicit secrets/hosts."""
import os
import ipaddress
from pathlib import Path
from urllib.parse import urlparse
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv('DJANGO_DEBUG', 'true').lower() == 'true'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY in production.')
    SECRET_KEY = 'local-development-only-toolsathi-not-for-deployment-4729'
ALLOWED_HOSTS = [s.strip() for s in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]').split(',') if s.strip()]
SITE_URL = os.getenv('SITE_URL', 'http://127.0.0.1:8000').strip().rstrip('/')
if not DEBUG:
    try:
        origin = urlparse(SITE_URL)
        host = origin.hostname or ''
        normalized_host = host.rstrip('.')
        invalid_origin = (
            origin.scheme != 'https' or not host or origin.username is not None or origin.password is not None
            or bool(origin.path or origin.params or origin.query or origin.fragment)
            or origin.port not in (None, 443) or any(character.isspace() for character in SITE_URL)
            or '?' in SITE_URL or '#' in SITE_URL
            or normalized_host == 'localhost' or normalized_host.endswith('.localhost')
            or 'DJANGO_ALLOWED_HOSTS' not in os.environ or host not in ALLOWED_HOSTS
            or '*' in ALLOWED_HOSTS
        )
        try:
            invalid_origin = invalid_origin or ipaddress.ip_address(normalized_host).is_loopback
        except ValueError:
            pass
        if invalid_origin:
            raise ValueError
    except ValueError:
        raise ImproperlyConfigured('Production needs an HTTPS SITE_URL origin with an explicit matching DJANGO_ALLOWED_HOSTS hostname.') from None
GOOGLE_SITE_VERIFICATION = os.getenv('GOOGLE_SITE_VERIFICATION', '').strip()
# PythonAnywhere overwrites X-Real-IP; enable only on that managed proxy.
TRUST_PYTHONANYWHERE_PROXY = os.getenv('TRUST_PYTHONANYWHERE_PROXY', 'false').lower() == 'true'
INSTALLED_APPS = ['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
                  'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
                  'apps.core', 'apps.tools', 'apps.accounts', 'apps.downloads', 'apps.seo']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware',
              'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware',
              'apps.core.middleware.RequestGuardMiddleware', 'django.middleware.csrf.CsrfViewMiddleware',
              'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware',
              'django.middleware.clickjacking.XFrameOptionsMiddleware', 'apps.core.middleware.PrivacyHeadersMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
              'OPTIONS': {'context_processors': ['django.template.context_processors.request', 'django.contrib.auth.context_processors.auth',
                                                'django.contrib.messages.context_processors.messages', 'apps.core.context.site_context']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': dj_database_url.config(default='sqlite:///' + str(BASE_DIR / 'db.sqlite3'), conn_max_age=60)}
if DATABASES['default']['ENGINE'].endswith('sqlite3'):
    DATABASES['default']['OPTIONS'] = {'timeout': 20}
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
                            {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
                            {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
                            {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage' if not DEBUG else 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_REDIRECT_URL = '/accounts/dashboard/'
LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/accounts/login/'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
CSRF_TRUSTED_ORIGINS = [SITE_URL] if SITE_URL.startswith('https://') else []
# Enable ONLY behind a trusted proxy that replaces the incoming header.
if os.getenv('TRUST_PROXY_HTTPS', 'false').lower() == 'true':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 22 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 512 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 20
DATA_UPLOAD_MAX_NUMBER_FIELDS = 80
MAX_RESULT_BYTES = 30 * 1024 * 1024
RESULT_TTL = 600
RESULT_DIR = Path(os.getenv('RESULT_DIR', str(BASE_DIR / '.runtime' / 'results')))
RESULT_STORAGE_LIMIT = int(os.getenv('RESULT_STORAGE_LIMIT', str(256 * 1024 * 1024)))
APK_DIR = Path(os.getenv('APK_DIR', str(BASE_DIR / 'artifacts')))
LOGGING = {'version': 1, 'disable_existing_loggers': False,
           'handlers': {'console': {'class': 'logging.StreamHandler'}},
           'loggers': {'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
                       'pypdf': {'handlers': [], 'level': 'CRITICAL', 'propagate': False}}}
