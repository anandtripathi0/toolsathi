"""Short-lived, session-bound output storage outside the static tree."""
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path
from django.conf import settings
from django.core import signing
from django.urls import reverse
from filelock import FileLock, Timeout

def cleanup_results():
    if not settings.RESULT_DIR.exists():
        return 0
    with FileLock(str(settings.RESULT_DIR / '.storage.lock'), timeout=5):
        return _cleanup_unlocked()

def _cleanup_unlocked():
    root = settings.RESULT_DIR
    if not root.exists():
        return 0
    count = 0
    threshold = time.time() - settings.RESULT_TTL
    for path in root.iterdir():
        if not re.fullmatch(r'[a-f0-9]{48}\.(bin|json)', path.name) or path.is_symlink():
            continue
        try:
            if path.stat().st_mtime < threshold:
                path.unlink(missing_ok=True)
                count += 1
        except (FileNotFoundError, PermissionError):
            pass
    return count

def _session_binding(request):
    if not request.session.session_key:
        request.session.create()
    return hmac.new(settings.SECRET_KEY.encode(), request.session.session_key.encode(), hashlib.sha256).hexdigest()

def save_result(request, result):
    text = result.get('text', '')
    content = result.get('data', text.encode('utf-8'))
    if len(content) > settings.MAX_RESULT_BYTES:
        raise ValueError('Result exceeds the 30 MB limit. Try fewer pages or smaller images.')
    root = settings.RESULT_DIR
    root.mkdir(parents=True, exist_ok=True)
    identifier = secrets.token_hex(24)
    filename = re.sub(r'[^A-Za-z0-9._-]', '_', result.get('filename', 'result.txt'))[:100]
    mime = result.get('mime', 'text/plain').split(';', 1)[0].strip().lower()
    allowed_mimes = {'text/plain', 'application/json', 'text/csv', 'text/html', 'text/css', 'application/javascript', 'text/javascript',
                     'application/xml', 'text/xml', 'application/yaml', 'text/yaml', 'application/pdf', 'application/zip',
                     'image/png', 'image/jpeg', 'image/webp', 'image/svg+xml', 'text/markdown', 'application/octet-stream'}
    if mime not in allowed_mimes:
        mime = 'text/plain'
    # Restrictive permissions on POSIX; configure an isolated service account/ACL on Windows.
    try:
        with FileLock(str(root / '.storage.lock'), timeout=5):
            _cleanup_unlocked()
            occupied = sum(p.stat().st_size for p in root.glob('*.bin') if p.is_file())
            if occupied + len(content) > settings.RESULT_STORAGE_LIMIT:
                raise ValueError('Temporary storage is busy. Please retry in a few minutes.')
            try:
                for suffix, payload in [('bin', content), ('json', json.dumps({'filename': filename, 'mime': mime}).encode())]:
                    path = root / (identifier + '.' + suffix)
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, 'wb') as out:
                        out.write(payload)
            except OSError:
                for suffix in ('bin', 'json'):
                    (root / (identifier + '.' + suffix)).unlink(missing_ok=True)
                raise ValueError('Unable to store the result. Please try again later.')
    except Timeout:
        raise ValueError('Temporary storage is busy. Please retry in a moment.')
    token = signing.dumps({'id': identifier, 'session': _session_binding(request)}, salt='toolsathi-result')
    url = reverse('result_download', args=[token])
    data = {'text': text, 'filename': filename, 'mime': mime, 'download_url': url,
            'is_image': mime in ('image/png', 'image/jpeg', 'image/webp'), 'is_pdf': mime == 'application/pdf',
            'expires_in': settings.RESULT_TTL}
    if data['is_image']:
        data['preview_url'] = url + '?preview=1'
    if 'preview_html' in result:
        data['preview_html'] = result['preview_html']
    return data

def load_result(request, token):
    payload = signing.loads(token, salt='toolsathi-result', max_age=settings.RESULT_TTL)
    if not request.session.session_key or not hmac.compare_digest(payload.get('session', ''), _session_binding(request)):
        raise ValueError('This download belongs to another session.')
    identifier = payload.get('id', '')
    if not re.fullmatch(r'[a-f0-9]{48}', identifier):
        raise ValueError('Invalid result ID.')
    path = settings.RESULT_DIR / (identifier + '.bin')
    if path.is_symlink():
        raise ValueError('Invalid result path.')
    metadata = json.loads((settings.RESULT_DIR / (identifier + '.json')).read_text(encoding='utf-8'))
    return path, metadata
