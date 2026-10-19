import json
import logging
from django.conf import settings
from django.http import JsonResponse, Http404
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from apps.downloads.results import save_result

@require_GET
def directory(request, category_id=None):
    from .registry import search_tools, CATEGORIES
    category = next((x for x in CATEGORIES if x['id'] == category_id), None)
    if category_id and not category:
        raise Http404
    query = request.GET.get('q', '')[:200]
    tools = search_tools(query, category_id or request.GET.get('category', ''))
    title = (category['name'] if category else 'All free tools') + ' | ToolSathi'
    return render(request, 'tools/directory.html', {'tools': tools, 'category': category, 'query': query, 'page_title': title, 'title': title})

@require_GET
@ensure_csrf_cookie
def detail(request, slug):
    from .registry import REGISTRY
    tool = REGISTRY.get(slug)
    if not tool or tool.get('status') != 'available':
        raise Http404
    schema = {'@context': 'https://schema.org', '@type': 'WebApplication', 'name': tool['name'], 'applicationCategory': 'UtilitiesApplication',
              'operatingSystem': 'Any', 'url': settings.SITE_URL + request.path, 'offers': {'@type': 'Offer', 'price': '0', 'priceCurrency': 'USD'}}
    return render(request, 'tools/detail.html', {'tool': tool, 'example': tool.get('example'), 'instructions': tool.get('instructions'), 'related_tools': [REGISTRY[s] for s in tool.get('related_tools', []) if s in REGISTRY],
                 'page_title': tool.get('seo_title', tool['name'] + ' | ToolSathi'), 'meta_description': tool.get('seo_description', tool['description']),
                 'structured_data': json.dumps(schema).replace('<', '\\u003c')})

@require_GET
def search(request):
    from .registry import search_tools
    found = search_tools(request.GET.get('q', '')[:200], request.GET.get('category', ''))
    return JsonResponse({'tools': [{k: t[k] for k in ('slug', 'name', 'description', 'category', 'icon')} for t in found[:200]], 'count': len(found)})

@require_GET
def search_partial(request):
    from .registry import search_tools
    query = request.GET.get('q', '')[:200]
    return render(request, 'tools/_search_results.html', {'tools': search_tools(query, request.GET.get('category', '')), 'query': query})

@require_POST
def process(request, slug):
    from .registry import REGISTRY
    tool = REGISTRY.get(slug)
    if not tool or tool.get('status') != 'available':
        raise Http404
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            if not isinstance(data, dict) or any(not isinstance(v, (str, int, float, bool)) for v in data.values()):
                raise ValueError('Submit a JSON object containing simple input values.')
        else:
            data = request.POST.dict()
        if sum(len(str(v)) for v in data.values()) > 220_000:
            raise ValueError('Text input must be no more than 200,000 characters.')
        if tool['handler'] == 'files':
            from tools_logic.file_tools import process as handler
            result = handler(slug, data, request.FILES.getlist('files'))
        else:
            from tools_logic.text_tools import process as handler
            result = handler(slug, data)
        if slug in ('jwt-decoder', 'secure-password-generator', 'hash-generator'):
            return JsonResponse({k: result[k] for k in ('text', 'filename', 'mime')})
        return JsonResponse(save_result(request, result))
    except (ValueError, UnicodeError, TypeError, json.JSONDecodeError) as error:
        # Error messages from our validation are bounded; never log input or uploaded file contents.
        return JsonResponse({'error': str(error)[:500] or 'Invalid input. Check the fields and try again.'}, status=400)
    except Exception:
        # Detailed exception objects may contain submitted content; deliberately omit them.
        logging.getLogger(__name__).error('Tool processing failed for registered tool %s', slug)
        return JsonResponse({'error': 'This input could not be processed. Check its format and size, then try again.'}, status=400)
