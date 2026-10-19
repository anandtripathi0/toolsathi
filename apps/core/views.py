from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.conf import settings

@require_GET
def home(request):
    from apps.tools.registry import REGISTRY, TOOLS
    popular = ['json-formatter', 'image-compressor', 'pdf-merger', 'qr-code-generator', 'word-counter', 'secure-password-generator', 'base64-encoder-decoder', 'image-resizer']
    return render(request, 'core/home.html', {'tools': TOOLS, 'popular_tools': [REGISTRY[s] for s in popular if s in REGISTRY]})

@require_GET
def static_page(request, page):
    titles = {'privacy': 'Privacy', 'about': 'About ToolSathi', 'offline': 'You are offline'}
    return render(request, f'core/{page}.html', {'page_title': titles[page] + ' | ToolSathi', 'title': titles[page]})

@require_GET
def health(request):
    return JsonResponse({'status': 'ok'})

@require_GET
def manifest(request):
    return JsonResponse({'name': 'ToolSathi', 'short_name': 'ToolSathi', 'description': 'Every Tool. One Place.',
                         'start_url': '/', 'scope': '/', 'display': 'standalone', 'background_color': '#FFFFFF', 'theme_color': '#FFFFFF',
                         'icons': [{'src': f'/static/icons/icon{n}.png', 'sizes': f'{n}x{n}', 'type': 'image/png', 'purpose': 'any maskable'} for n in (192, 512)]}, content_type='application/manifest+json')

@require_GET
def service_worker(request):
    response = HttpResponse((settings.BASE_DIR / 'static' / 'js' / 'sw.js').read_text(encoding='utf-8'), content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response
