import json
from django.conf import settings

def site_context(request):
    from apps.tools.registry import CATEGORIES, TOOLS
    return {'categories': CATEGORIES, 'all_tools': TOOLS, 'total_tools': len(TOOLS),
            'canonical': settings.SITE_URL + request.path, 'site_url': settings.SITE_URL,
            'google_site_verification': getattr(settings, 'GOOGLE_SITE_VERIFICATION', '').strip(),
            'page_title': 'ToolSathi — Every Tool. One Place.',
            'meta_description': 'Free developer tools, converters, image editors, PDF utilities and everyday essentials. No signup required.',
            'structured_data': json.dumps({'@context': 'https://schema.org', '@type': 'WebSite', 'name': 'ToolSathi', 'url': settings.SITE_URL})}
