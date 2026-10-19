import hashlib
import hmac
import ipaddress
import time
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from apps.accounts.models import RateBucket


def _client_ip(request):
    """Trust a validated X-Real-IP only on the explicitly configured PA proxy.

    https://help.pythonanywhere.com/pages/WebAppClientIPAddresses
    Other deployments keep REMOTE_ADDR; arbitrary X-Forwarded-For is ignored.
    """
    if settings.TRUST_PYTHONANYWHERE_PROXY:
        forwarded = request.META.get('HTTP_X_REAL_IP', '').strip()
        try:
            if '%' in forwarded:
                raise ValueError
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return request.META.get('REMOTE_ADDR', '')


class RequestGuardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST':
            try:
                size = int(request.META.get('CONTENT_LENGTH') or 0)
            except ValueError:
                return JsonResponse({'error': 'Invalid request size.'}, status=400)
            if size > settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
                return JsonResponse({'error': 'Upload limit is 20 MB per request.'}, status=413)
            is_tool = request.path.startswith('/api/tools/')
            is_auth = request.path in ('/accounts/login/', '/accounts/signup/', '/admin/login/')
            if is_tool or is_auth:
                now = int(time.time())
                window, limit = (60, 30) if is_tool else (300, 10)
                identity = f"{_client_ip(request)}:{now // window}:{'tool' if is_tool else 'auth'}"
                key = hmac.new(settings.SECRET_KEY.encode(), identity.encode(), hashlib.sha256).hexdigest()
                RateBucket.objects.filter(expires__lt=now).delete()
                bucket, _ = RateBucket.objects.get_or_create(key=key, defaults={'expires': (now // window + 1) * window})
                from django.db.models import F
                admitted = RateBucket.objects.filter(pk=key, count__lt=limit).update(count=F('count') + 1)
                if not admitted:
                    response = JsonResponse({'error': 'Too many requests. Please try again in a minute.'}, status=429)
                    response['Retry-After'] = str(window - now % window)
                    return response
        return self.get_response(request)

class PrivacyHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.setdefault('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; frame-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
        if request.path.startswith(('/api/', '/downloads/results/', '/accounts/')):
            response['Cache-Control'] = 'no-store, private'
        return response
