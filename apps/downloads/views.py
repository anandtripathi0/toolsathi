import hashlib
import json
import zipfile
from django.conf import settings
from django.core.signing import BadSignature
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET
from .results import load_result

def apk_info():
    path = settings.APK_DIR / 'toolsathi-latest.apk'
    manifest = settings.APK_DIR / 'release.json'
    try:
        meta = json.loads(manifest.read_text(encoding='utf-8'))
        with path.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        if not meta.get('verified') or meta.get('sha256') != digest or not meta.get('version'):
            return {'available': False}
        with zipfile.ZipFile(path) as apk:
            if not {'AndroidManifest.xml', 'classes.dex'}.issubset(set(apk.namelist())):
                return {'available': False}
        size = path.stat().st_size
        return {'available': True, 'version': meta['version'], 'size': size, 'size_mb': round(size / 1048576, 2),
                'sha256': digest, 'url': '/downloads/toolsathi-latest.apk'}
    except (OSError, ValueError, zipfile.BadZipFile):
        return {'available': False}

@require_GET
def app(request):
    return render(request, 'downloads/app.html', {'apk': apk_info(), 'page_title': 'ToolSathi for Android & PWA | ToolSathi'})

@require_GET
def apk_download(request):
    if not apk_info()['available']:
        raise Http404('Android app coming soon. A verified APK has not been published.')
    response = FileResponse((settings.APK_DIR / 'toolsathi-latest.apk').open('rb'), as_attachment=True,
                            filename='ToolSathi.apk', content_type='application/vnd.android.package-archive')
    response['Cache-Control'] = 'public, max-age=300'
    return response

@require_GET
def result_download(request, token):
    try:
        path, metadata = load_result(request, token)
        inline = request.GET.get('preview') == '1' and metadata['mime'] in ('image/png', 'image/jpeg', 'image/webp')
        response = FileResponse(path.open('rb'), as_attachment=not inline, filename=metadata['filename'], content_type=metadata['mime'])
        response['Cache-Control'] = 'no-store, private'
        response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        response['Content-Security-Policy'] = "default-src 'none'; sandbox"
        return response
    except (BadSignature, ValueError, OSError, KeyError):
        raise Http404('This result has expired or belongs to a different browser session.')
