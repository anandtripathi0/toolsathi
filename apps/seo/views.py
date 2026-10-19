from xml.etree.ElementTree import Element, SubElement, tostring
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.http import require_GET

@require_GET
def sitemap(request):
    from apps.tools.registry import CATEGORIES, TOOLS
    root = Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    paths = ['/', '/tools/', '/about/', '/privacy/', '/download-app/']
    paths += ['/category/' + c['id'] + '/' for c in CATEGORIES]
    paths += ['/tools/' + t['slug'] + '/' for t in TOOLS if t['status'] == 'available']
    for path in paths:
        SubElement(SubElement(root, 'url'), 'loc').text = settings.SITE_URL + path
    return HttpResponse(tostring(root, encoding='utf-8', xml_declaration=True), content_type='application/xml')

@require_GET
def robots(request):
    return HttpResponse('User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /accounts/\nDisallow: /admin/\nDisallow: /downloads/results/\nSitemap: ' + settings.SITE_URL + '/sitemap.xml\n', content_type='text/plain')
