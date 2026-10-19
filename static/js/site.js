/* ToolSathi: tiny interactions, non-sensitive preferences, and accessible search. */
(() => {
  'use strict';
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const icons = () => window.lucide?.createIcons({attrs: {'aria-hidden': 'true'}});
  const icon = name => { const el = document.createElement('i'); el.dataset.lucide = name || 'wrench'; return el; };
  let toastTimer;
  function toast(message) { const el = $('#toast'); if (!el) return; el.textContent = message; el.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { el.hidden = true; }, 3500); }
  const csrf = () => $('input[name=csrfmiddlewaretoken]')?.value || '';
  const storage = {
    get(key, fallback) { try { const result = JSON.parse(localStorage.getItem(`toolsathi:${key}`)); return result === null ? fallback : result; } catch { return fallback; } },
    set(key, value) { try { localStorage.setItem(`toolsathi:${key}`, JSON.stringify(value)); return true; } catch { return false; } }
  };
  const cleanIds = value => Array.isArray(value) ? [...new Set(value.filter(x => typeof x === 'string' && /^[a-z0-9-]{1,100}$/.test(x)))].slice(0, 100) : [];
  let favorites = cleanIds(storage.get('favorites', []));
  let recent = cleanIds(storage.get('recent', []));
  let historyEnabled = false;
  let preferencesLoaded = document.body.dataset.authenticated !== 'true';
  let preferenceDirty = false;
  let syncTimer;
  let catalogPromise;
  const accountKey = document.body.dataset.accountId || '';
  const getCatalog = () => catalogPromise ||= fetch('/api/search/?q=', {headers: {'Accept': 'application/json'}}).then(r => { if (!r.ok) throw new Error(); return r.json(); }).then(data => data.tools || []).catch(() => { catalogPromise = null; return []; });
  function updateStars() { $$('[data-favorite]').forEach(button => { const saved = favorites.includes(button.dataset.favorite); button.setAttribute('aria-pressed', String(saved)); const label = button.closest('[data-tool-slug]')?.querySelector('h3')?.textContent || document.querySelector('.tool-intro h1')?.textContent || 'tool'; button.setAttribute('aria-label', `${saved ? 'Remove' : 'Add'} ${label} ${saved ? 'from' : 'to'} favorites`); }); }
  async function renderPersonal() {
    updateStars();
    if (!$('[data-favorite-list], [data-recent-list]')) return;
    const catalog = await getCatalog(); const byId = new Map(catalog.map(t => [t.slug, t]));
    for (const [selector, ids, empty] of [['[data-favorite-list]', favorites, 'Make this space yours. Tap the star on a tool to keep it close.'], ['[data-recent-list]', recent, 'Your recently used tools appear here. Only tool names are remembered, never your content.']]) {
      $$(selector).forEach(list => { list.replaceChildren(); const tools = ids.slice(0, 6).map(slug => byId.get(slug)).filter(Boolean); if (!tools.length) { const p = document.createElement('p'); p.className = 'empty-personal'; p.textContent = empty; list.append(p); return; } tools.forEach(tool => { const a = document.createElement('a'); a.className = 'saved-tool'; a.href = `/tools/${tool.slug}/`; a.append(icon(tool.icon)); const name = document.createElement('span'); name.textContent = tool.name; a.append(name, icon('arrow-up-right')); list.append(a); }); });
    }
    icons();
  }
  async function syncPreferences() {
    if (document.body.dataset.authenticated !== 'true') return;
    if (!preferencesLoaded) { preferenceDirty = true; return; }
    try {
      const r = await fetch('/api/preferences/', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()}, body: JSON.stringify({favorites, history_enabled: historyEnabled, recent: historyEnabled ? recent : []})});
      if (!r.ok) throw new Error();
      if ($('#sync-status')) $('#sync-status').textContent = 'Synced to your account';
    } catch { if ($('#sync-status')) $('#sync-status').textContent = 'Saved locally · sync unavailable'; }
  }
  function savePreferences() { storage.set('favorites', favorites); storage.set('recent', recent); clearTimeout(syncTimer); syncTimer = setTimeout(syncPreferences, 250); }
  async function loadPreferences() {
    if (document.body.dataset.authenticated !== 'true') return;
    try {
      const r = await fetch('/api/preferences/'); if (!r.ok) throw new Error(); const data = await r.json();
      const imported = storage.get('imported-accounts', []).includes(accountKey);
      // Import anonymous favorites once; thereafter server state wins so removals sync.
      favorites = preferenceDirty ? favorites : imported ? cleanIds(data.favorites) : cleanIds([...favorites, ...cleanIds(data.favorites)]);
      historyEnabled = data.history_enabled === true;
      if (historyEnabled) recent = cleanIds([...(currentTool ? [currentTool] : []), ...cleanIds(data.recent), ...recent]);
      const accounts = storage.get('imported-accounts', []); if (!accounts.includes(accountKey)) storage.set('imported-accounts', [...accounts, accountKey].slice(-20));
      preferencesLoaded = true; if ($('#history-sync')) $('#history-sync').checked = historyEnabled;
      storage.set('favorites', favorites); storage.set('recent', recent); renderPersonal();
      await syncPreferences(); preferenceDirty = false;
    } catch { preferencesLoaded = false; if ($('#sync-status')) $('#sync-status').textContent = 'Saved locally · sync unavailable'; }
  }
  document.addEventListener('click', event => {
    const favorite = event.target.closest('[data-favorite]');
    if (favorite) { const id = favorite.dataset.favorite; const wasSaved = favorites.includes(id); favorites = wasSaved ? favorites.filter(x => x !== id) : [id, ...favorites].slice(0, 100); savePreferences(); renderPersonal(); toast(wasSaved ? 'Removed from favorites' : 'Added to your favorites'); }
    if (event.target.closest('.clear-recent')) { recent = []; savePreferences(); renderPersonal(); toast('Recently used tools cleared'); }
    if (event.target.closest('.back-to-top')) { event.preventDefault(); window.scrollTo({top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'}); }
  });
  $('#history-sync')?.addEventListener('change', event => { historyEnabled = event.target.checked; savePreferences(); toast(historyEnabled ? 'Tool history sync enabled. Only tool IDs are saved.' : 'Tool history sync disabled.'); });
  const currentTool = $('[data-tool]')?.dataset.tool;
  if (currentTool) { recent = [currentTool, ...recent.filter(x => x !== currentTool)].slice(0, 20); storage.set('recent', recent); }
  window.addEventListener('storage', event => { if (event.key?.startsWith('toolsathi:')) { favorites = cleanIds(storage.get('favorites', [])); recent = cleanIds(storage.get('recent', [])); renderPersonal(); } });
  $('.mobile-toggle')?.addEventListener('click', event => { const btn = event.currentTarget; const nav = $('.mobile-nav'); nav.hidden = !nav.hidden; btn.setAttribute('aria-expanded', String(!nav.hidden)); btn.setAttribute('aria-label', nav.hidden ? 'Open navigation' : 'Close navigation'); });
  $('.nav-categories')?.addEventListener('click', event => { const menu = event.currentTarget.closest('.nav-dropdown'); const open = menu.classList.toggle('open'); event.currentTarget.setAttribute('aria-expanded', String(open)); });
  document.addEventListener('click', event => { if (!event.target.closest('.nav-dropdown')) { $('.nav-dropdown')?.classList.remove('open'); $('.nav-categories')?.setAttribute('aria-expanded', 'false'); } });

  function connectSearch(input, results, alwaysVisible = false) {
    if (!input || !results) return;
    let controller, timer, selected = -1, matches = [];
    function select(index) { if (!matches.length) return; selected = (index + matches.length) % matches.length; matches.forEach((el, i) => el.setAttribute('aria-selected', String(i === selected))); input.setAttribute('aria-activedescendant', matches[selected].id); matches[selected].scrollIntoView({block: 'nearest'}); }
    function close() { if (!alwaysVisible) results.hidden = true; input.setAttribute('aria-expanded', 'false'); input.removeAttribute('aria-activedescendant'); }
    async function search() {
      controller?.abort(); controller = new AbortController(); const value = input.value.trim();
      try {
        const response = await fetch(`/api/search/?q=${encodeURIComponent(value)}`, {signal: controller.signal, headers: {'Accept': 'application/json'}});
        if (!response.ok) throw new Error(); const data = await response.json(); results.replaceChildren(); selected = -1;
        const tools = (data.tools || []).slice(0, 8);
        if (!tools.length) { const p = document.createElement('p'); p.className = 'search-empty'; p.textContent = 'No matches yet. Try a different keyword.'; results.append(p); }
        tools.forEach((tool, index) => { const a = document.createElement('a'); a.href = `/tools/${tool.slug}/`; a.className = 'search-result'; a.id = `${input.id}-result-${index}`; a.setAttribute('role', 'option'); a.setAttribute('aria-selected', 'false'); a.tabIndex = -1; const content = document.createElement('span'); const title = document.createElement('strong'); title.textContent = tool.name; const description = document.createElement('small'); description.textContent = tool.description; content.append(title, description); const arrow = icon('arrow-up-right'); arrow.classList.add('result-arrow'); a.append(icon(tool.icon), content, arrow); results.append(a); });
        matches = $$('.search-result', results); results.hidden = false; input.setAttribute('aria-expanded', 'true'); icons();
      } catch (error) { if (error.name === 'AbortError') return; results.replaceChildren(); const p = document.createElement('p'); p.className = 'search-empty'; p.textContent = 'Search is unavailable. Try the All Tools directory.'; results.append(p); results.hidden = false; input.setAttribute('aria-expanded', 'true'); }
    }
    input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(search, 150); });
    input.addEventListener('focus', search);
    input.addEventListener('keydown', event => { if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); if (results.hidden) search(); else select(selected + (event.key === 'ArrowDown' ? 1 : -1)); } else if (event.key === 'Enter' && selected >= 0 && matches[selected]) { event.preventDefault(); window.location.assign(matches[selected].href); } else if (event.key === 'Escape') close(); });
    if (!alwaysVisible) document.addEventListener('click', event => { if (!input.closest('.hero-search-wrap')?.contains(event.target)) close(); });
    return {search, close};
  }
  const heroSearch = connectSearch($('#hero-search'), $('#hero-results'));
  const palette = $('#command-palette'); const commandInput = $('#command-search');
  const commandSearch = connectSearch(commandInput, $('#command-results'), true);
  function openSearch() { if (!palette || palette.open) return; heroSearch?.close(); palette.showModal(); commandInput.focus(); }
  $$('.search-trigger, .search-shortcut').forEach(btn => btn.addEventListener('click', openSearch));
  $('.command-close')?.addEventListener('click', () => palette.close());
  palette?.addEventListener('click', event => { const bounds = palette.getBoundingClientRect(); if (event.target === palette && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) palette.close(); });
  document.addEventListener('keydown', event => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); openSearch(); } });
  if (/Mac|iPhone|iPad/.test(navigator.platform)) { const key = $('.search-shortcut kbd'); if (key) key.textContent = '⌘'; }
  let filterRequest = 0;
  $$('[data-directory-filters] [data-category]').forEach(button => button.addEventListener('click', async () => {
    const requestId = ++filterRequest;
    $$('[data-directory-filters] [data-category]').forEach(btn => { btn.classList.toggle('active', btn === button); btn.setAttribute('aria-pressed', String(btn === button)); });
    const list = $('#home-directory'); list.setAttribute('aria-busy', 'true');
    try {
      const r = await fetch(`/api/search/?q=&category=${encodeURIComponent(button.dataset.category)}`); if (!r.ok) throw new Error(); const data = await r.json(); if (requestId !== filterRequest) return;
      list.replaceChildren(); (data.tools || []).slice(0, 12).forEach(tool => { const a = document.createElement('a'); a.className = 'directory-item'; a.href = `/tools/${tool.slug}/`; const visual = document.createElement('span'); visual.className = 'directory-icon'; visual.append(icon(tool.icon)); const copy = document.createElement('span'); const title = document.createElement('strong'); title.textContent = tool.name; const subtitle = document.createElement('small'); subtitle.textContent = tool.description; copy.append(title, subtitle); const arrow = icon('arrow-up-right'); arrow.classList.add('directory-arrow'); a.append(visual, copy, arrow); list.append(a); }); icons();
    } catch { if (requestId === filterRequest) toast('Unable to load this category. Please try again.'); }
    finally { if (requestId === filterRequest) list.setAttribute('aria-busy', 'false'); }
  }));
  let installPrompt;
  window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); installPrompt = event; $$('.pwa-install').forEach(button => { button.hidden = false; }); });
  $$('.pwa-install').forEach(button => button.addEventListener('click', async () => { if (!installPrompt) return; await installPrompt.prompt(); const choice = await installPrompt.userChoice; if (choice.outcome === 'accepted') toast('ToolSathi is being added to your device.'); installPrompt = null; $$('.pwa-install').forEach(btn => { btn.hidden = true; }); }));
  window.addEventListener('appinstalled', () => { installPrompt = null; $$('.pwa-install').forEach(btn => { btn.hidden = true; }); });
  if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')) window.addEventListener('load', () => { navigator.serviceWorker.register('/sw.js').catch(() => {}); });
  document.body.addEventListener('htmx:afterSwap', icons);
  window.ToolSathi = {toast, icons, csrf};
  icons(); renderPersonal(); loadPreferences();
})();
