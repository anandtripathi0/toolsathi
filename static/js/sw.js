/* Cache only the public offline page and static assets. Never tool inputs or results. */
const CACHE = 'toolsathi-interface-v2';
const OFFLINE = '/offline/';
const ASSETS = [OFFLINE, '/static/css/site.css', '/static/js/site.js', '/static/js/vendor/lucide.min.js', '/static/js/vendor/htmx.min.js', '/static/icons/icon192.png', '/static/icons/icon512.png', '/static/icons/icon.svg'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(async cache => {
    for (const path of ASSETS) {
      const response = await fetch(path, {credentials: 'omit', cache: 'reload'});
      if (response.ok) await cache.put(path, response);
    }
    await self.skipWaiting();
  }));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('toolsathi-interface-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(caches.open(CACHE).then(async cache => {
      const cached = await cache.match(event.request);
      if (cached) return cached;
      const response = await fetch(event.request);
      if (response.ok) await cache.put(event.request, response.clone());
      return response;
    }));
  } else if (event.request.mode === 'navigate' && !url.pathname.startsWith('/downloads/') && !url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(event.request).catch(async () => (await caches.match(OFFLINE)) || new Response('You are offline. Reconnect to use ToolSathi.', {status: 503, headers: {'Content-Type': 'text/plain'}})));
  }
});
