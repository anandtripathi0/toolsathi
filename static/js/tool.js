/* Tool inputs and results remain in page memory, never local storage. */
(() => {
  'use strict';
  const workspace = document.querySelector('[data-tool]'); if (!workspace) return;
  const $ = selector => document.querySelector(selector);
  const slug = workspace.dataset.tool, form = $('#tool-form');
  const api = window.ToolSathi || {toast: () => {}, icons: () => {}, csrf: () => ''};
  const localTools = new Set(['json-formatter', 'json-validator', 'json-minifier', 'jwt-decoder', 'secure-password-generator', 'random-string-generator', 'uuid-generator', 'hash-generator', 'word-counter', 'character-counter', 'base64-encoder-decoder', 'url-encoder-decoder', 'html-playground', 'css-playground']);
  let result = null, blobUrl = null, controller = null, requestNumber = 0;
  const isLocal = localTools.has(slug);
  $('#processing-note').lastChild.textContent = isLocal ? 'Processed in your browser' : 'Temporary server processing';
  $('#tool-privacy-note').replaceChildren();
  const privacy = document.createElement('span'); privacy.textContent = isLocal ? 'This tool processes your content in this browser. Inputs are not sent to the server. ' : 'Inputs are processed temporarily on the server. Generated result links expire after 10 minutes. ';
  const privacyLink = document.createElement('a'); privacyLink.href = '/privacy/'; privacyLink.textContent = 'How we handle data';
  $('#tool-privacy-note').append(privacy, privacyLink);
  const number = (data, key, min, max) => { const n = Number(data.get(key)); if (!Number.isSafeInteger(n) || n < min || n > max) throw new Error(`${key[0].toUpperCase() + key.slice(1)} must be a whole number from ${min} to ${max}.`); return n; };
  const jsonResult = value => ({text: JSON.stringify(value, null, 2), filename: `${slug}.json`, mime: 'application/json'});
  const textResult = (text, extension = 'txt', mime = 'text/plain;charset=utf-8') => ({text, filename: `${slug}.${extension}`, mime});
  function secureIndex(limit) {
    if (!window.crypto?.getRandomValues) throw new Error('Secure randomness is unavailable in this browser. Open ToolSathi over HTTPS in a current browser.');
    const maximum = Math.floor(0x100000000 / limit) * limit;
    const values = new Uint32Array(1); let value;
    do { crypto.getRandomValues(values); value = values[0]; } while (value >= maximum);
    return value % limit;
  }
  function readBase64(value, urlSafe = false) {
    let normalized = value.replace(/\s/g, '');
    if (urlSafe) { normalized = normalized.replace(/-/g, '+').replace(/_/g, '/'); normalized += '='.repeat((4 - normalized.length % 4) % 4); }
    if (!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(normalized)) throw new Error('Enter valid Base64-encoded UTF-8 text.');
    try { return new TextDecoder('utf-8', {fatal: true}).decode(Uint8Array.from(atob(normalized), char => char.charCodeAt(0))); } catch { throw new Error('The Base64 input is invalid or does not contain UTF-8 text.'); }
  }
  function formatJSON(input, pretty) {
    JSON.parse(input); // Validate only. Preserve numeric lexemes, duplicate keys, and key order.
    let insideString = false, escaped = false, compact = '';
    for (const char of input) { if (insideString) { compact += char; if (escaped) escaped = false; else if (char === '\\') escaped = true; else if (char === '"') insideString = false; } else if (char === '"') { insideString = true; compact += char; } else if (!/[\t\r\n ]/.test(char)) compact += char; }
    if (!pretty) return compact;
    let output = '', depth = 0; insideString = false; escaped = false;
    for (let index = 0; index < compact.length; index++) {
      const char = compact[index];
      if (insideString) { output += char; if (escaped) escaped = false; else if (char === '\\') escaped = true; else if (char === '"') insideString = false; }
      else if (char === '"') { insideString = true; output += char; }
      else if (char === '{' || char === '[') { depth++; if (depth > 100) throw new Error('JSON formatting supports up to 100 nested levels.'); output += char; if (compact[index + 1] !== (char === '{' ? '}' : ']')) output += '\n' + '  '.repeat(depth); }
      else if (char === '}' || char === ']') { depth--; if (compact[index - 1] !== (char === '}' ? '{' : '[')) output += '\n' + '  '.repeat(depth); output += char; }
      else if (char === ',') output += ',\n' + '  '.repeat(depth);
      else if (char === ':') output += ': ';
      else output += char;
      if (output.length > 2_000_000) throw new Error('The formatted output is too large. Reduce the input or use JSON Minifier.');
    }
    return output;
  }
  async function processLocally(data) {
    const text = String(data.get('text') || '');
    if (Array.from(text).length > 200000 || String(data.get('second') || '').length > 200000) throw new Error('Text inputs are limited to 200,000 characters.');
    if (slug.startsWith('json-')) {
      if (slug === 'json-validator') { JSON.parse(text); return textResult('Valid JSON. Your input has valid JSON syntax.'); }
      return textResult(formatJSON(text, slug === 'json-formatter'), 'json', 'application/json');
    }
    if (slug === 'jwt-decoder') {
      const parts = text.trim().split('.'); if (parts.length !== 3 || parts.some(part => !part)) throw new Error('A JWT must contain three non-empty dot-separated sections.');
      if (parts.some(part => !/^[A-Za-z0-9_-]+$/.test(part))) throw new Error('JWT sections must use Base64URL characters.');
      let header, payload;
      try { header = JSON.parse(readBase64(parts[0], true)); payload = JSON.parse(readBase64(parts[1], true)); } catch { throw new Error('The JWT header or payload is not valid Base64URL JSON.'); }
      if (!header || typeof header !== 'object' || Array.isArray(header) || !payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error('JWT header and payload must be JSON objects.');
      return jsonResult({header, payload, warning: 'Decoded only. The signature has NOT been verified. Never trust these values for authentication.'});
    }
    if (slug === 'secure-password-generator' || slug === 'random-string-generator') {
      const secure = slug === 'secure-password-generator'; const length = number(data, 'length', secure ? 4 : 1, 1024); const count = number(data, 'count', 1, 100);
      const groups = {symbols: ['abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', '0123456789', '!@#$%^&*()-_=+[]{}:,.?'], alphanumeric: ['abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', '0123456789'], letters: ['abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'], digits: ['0123456789'], hex: ['0123456789abcdef']}[data.get('alphabet')];
      if (!groups) throw new Error('Select a supported character alphabet.');
      const alphabet = groups.join(''); const values = [];
      for (let row = 0; row < count; row++) { const chars = Array.from({length}, () => alphabet[secureIndex(alphabet.length)]); if (secure) { groups.forEach((group, i) => { chars[i] = group[secureIndex(group.length)]; }); for (let i = chars.length - 1; i > 0; i--) { const j = secureIndex(i + 1); [chars[i], chars[j]] = [chars[j], chars[i]]; } } values.push(chars.join('')); }
      return textResult(values.join('\n'));
    }
    if (slug === 'uuid-generator') { const count = number(data, 'count', 1, 1000); const values = Array.from({length: count}, () => { const bytes = new Uint8Array(16); if (!window.crypto?.getRandomValues) throw new Error('Secure randomness is unavailable. Use an HTTPS connection.'); crypto.getRandomValues(bytes); bytes[6] = bytes[6] & 15 | 64; bytes[8] = bytes[8] & 63 | 128; const hex = [...bytes].map(x => x.toString(16).padStart(2, '0')).join(''); return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`; }); return textResult(values.join('\n')); }
    if (slug === 'hash-generator') { if (!crypto.subtle) throw new Error('Browser hashing requires HTTPS or localhost. Your text has not been sent anywhere.'); const algorithm = {sha256: 'SHA-256', sha512: 'SHA-512'}[data.get('algorithm')]; if (!algorithm) throw new Error('Choose SHA-256 or SHA-512.'); const digest = await crypto.subtle.digest(algorithm, new TextEncoder().encode(text)); return textResult([...new Uint8Array(digest)].map(x => x.toString(16).padStart(2, '0')).join('')); }
    if (slug === 'word-counter' || slug === 'character-counter') { const words = text.match(/[\p{L}\p{N}_][\p{L}\p{M}\p{N}_]*(?:['’][\p{L}\p{M}\p{N}_]+)*/gu) || []; const lines = text ? text.split(/\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/) : []; if (text && /[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]$/.test(text)) lines.pop(); return jsonResult({words: words.length, characters: Array.from(text).length, characters_without_whitespace: Array.from(text).filter(c => !/\s/u.test(c)).length, lines: lines.length, paragraphs: text.trim() ? text.trim().split(/\n\s*\n/).filter(x => x.trim()).length : 0, estimated_reading_seconds_at_200_wpm: Math.ceil(words.length * .3), note: 'Characters count Unicode code points; words use Unicode letters, numbers, and underscores.'}); }
    if (slug === 'base64-encoder-decoder') { if (data.get('operation') === 'decode') return textResult(readBase64(text)); const bytes = new TextEncoder().encode(text); let binary = ''; for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192)); return textResult(btoa(binary)); }
    if (slug === 'url-encoder-decoder') { if (data.get('operation') === 'decode') { try { return textResult(decodeURIComponent(text)); } catch { throw new Error('Enter valid percent-encoded UTF-8 text.'); } } return textResult(encodeURIComponent(text).replace(/[!'()*]/g, c => '%' + c.charCodeAt(0).toString(16).toUpperCase())); }
    if (slug === 'html-playground' || slug === 'css-playground') { const output = slug === 'css-playground' ? `<!doctype html><html><head><meta charset="utf-8"><style>${text}</style></head><body>${String(data.get('second') || '')}</body></html>` : text; return {...textResult(output, 'html', 'text/html;charset=utf-8'), preview_html: output}; }
    throw new Error('This browser tool is unavailable.');
  }
  function clearOutput() { result = null; if (blobUrl) { URL.revokeObjectURL(blobUrl); blobUrl = null; } $('#copy-output').disabled = true; $('#download-output').disabled = true; $('#text-output').hidden = true; $('#text-output').textContent = ''; $('#visual-output').hidden = true; $('#visual-output').replaceChildren(); $('#tool-error').hidden = true; $('#tool-error').textContent = ''; $('#output-empty').hidden = false; $('#output-status').textContent = 'Ready when you are'; $('#result-meta').textContent = ''; }
  function showError(message) { clearOutput(); $('#output-empty').hidden = true; $('#tool-error').textContent = message; $('#tool-error').hidden = false; $('#output-status').textContent = 'Check your input'; }
  function safeResultUrl(value) { if (!value) return null; try { const url = new URL(value, location.origin); return url.origin === location.origin && ['http:', 'https:'].includes(url.protocol) ? url.href : null; } catch { return null; } }
  function showResult(data) {
    clearOutput(); result = data; $('#output-empty').hidden = true; $('#output-status').textContent = 'Done';
    const hasText = typeof data.text === 'string';
    if (hasText) { $('#text-output').textContent = data.text; $('#text-output').hidden = false; $('#copy-output').disabled = false; }
    const visual = $('#visual-output'); const previewUrl = safeResultUrl(data.preview_url);
    if (data.preview_html !== undefined) { const iframe = document.createElement('iframe'); iframe.title = 'Isolated output preview'; iframe.setAttribute('sandbox', ''); iframe.setAttribute('referrerpolicy', 'no-referrer'); iframe.srcdoc = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: blob:; style-src 'unsafe-inline'; font-src data:; form-action 'none'; base-uri 'none'"><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{font-family:system-ui;color:#111;padding:16px;overflow-wrap:anywhere}pre{white-space:pre-wrap}img{max-width:100%}</style>` + String(data.preview_html); visual.append(iframe); visual.hidden = false; }
    else if (previewUrl && (data.is_image || String(data.mime).startsWith('image/'))) { const img = document.createElement('img'); img.alt = 'Processed image result'; img.src = previewUrl; img.addEventListener('error', () => { img.remove(); const p = document.createElement('p'); p.textContent = 'Preview unavailable. You can still download the result.'; visual.append(p); }); visual.append(img); visual.hidden = false; }
    else if (previewUrl && (data.is_pdf || data.mime === 'application/pdf')) { const iframe = document.createElement('iframe'); iframe.title = 'PDF output preview'; iframe.src = previewUrl; visual.append(iframe); visual.hidden = false; }
    const downloadUrl = safeResultUrl(data.download_url); result.download_url = downloadUrl;
    if (!downloadUrl && hasText) { result.blob = new Blob([data.text], {type: data.mime || 'text/plain;charset=utf-8'}); blobUrl = URL.createObjectURL(result.blob); }
    $('#download-output').disabled = !downloadUrl && !blobUrl;
    if (!hasText && !previewUrl && data.preview_html === undefined) { const p = document.createElement('p'); p.textContent = 'Your file is ready. Select Download to save it.'; p.className = 'empty-personal'; visual.append(p); visual.hidden = false; }
    $('#result-meta').textContent = data.filename || '';
  }
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (!form.reportValidity()) return;
    controller?.abort(); controller = new AbortController(); const run = ++requestNumber; clearOutput(); const process = $('#process-button'); const caption = process.querySelector('span'); const originalCaption = caption.textContent; process.disabled = true; caption.textContent = 'Processing…'; $('#output-status').textContent = 'Working…'; workspace.setAttribute('aria-busy', 'true');
    try {
      const data = new FormData(form); let responseData;
      if (isLocal) responseData = await processLocally(data);
      else { const response = await fetch(form.action, {method: 'POST', body: data, headers: {'X-CSRFToken': api.csrf(), 'Accept': 'application/json'}, signal: controller.signal}); if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error(response.status === 403 ? 'Your session security token expired. Refresh this page and try again.' : 'The server could not process this request. Please try again.'); responseData = await response.json(); if (!response.ok || responseData.error) throw new Error(responseData.error || 'Unable to process this input.'); }
      if (run === requestNumber) showResult(responseData);
    } catch (error) { if (error.name !== 'AbortError' && run === requestNumber) showError(error instanceof SyntaxError ? `Invalid JSON: ${error.message}` : error.message || 'Something went wrong. Please try again.'); }
    finally { if (run === requestNumber) { process.disabled = false; caption.textContent = originalCaption; workspace.setAttribute('aria-busy', 'false'); } }
  });
  $('#reset-tool').addEventListener('click', () => { controller?.abort(); requestNumber++; form.reset(); clearOutput(); $('#process-button').disabled = false; $('#process-button span').textContent = 'Run tool'; workspace.setAttribute('aria-busy', 'false'); document.querySelectorAll('.file-list').forEach(list => { list.textContent = ''; }); updateUnits(); api.toast('Input and output reset'); });
  $('#load-example')?.addEventListener('click', async event => {
    const el = $('#tool-example'); if (!el) return;
    const button = event.currentTarget; button.disabled = true;
    try {
      const values = JSON.parse(el.textContent);
      if (values._files) {
        const transfer = new DataTransfer();
        for (const url of values._files) {
          if (!url.startsWith('/static/examples/')) throw new Error('Invalid example file.');
          const response = await fetch(url); if (!response.ok) throw new Error('Example unavailable.');
          const blob = await response.blob(); transfer.items.add(new File([blob], url.split('/').pop(), {type:blob.type}));
        }
        const upload = form.elements.namedItem('files'); upload.files = transfer.files;
        upload.dispatchEvent(new Event('change', {bubbles:true}));
      }
      Object.entries(values).forEach(([key, value]) => { const field = form.elements.namedItem(key); if (!field || field.type === 'file') return; if (field.type === 'checkbox') field.checked = Boolean(value); else field.value = String(value); });
      updateUnits(); clearOutput(); api.toast('Example loaded. Run the tool to see the result.');
    } catch { api.toast('This example could not be loaded. Check your connection and try again.'); }
    finally { button.disabled = false; }
  });
  $('#copy-output').addEventListener('click', async () => { if (typeof result?.text !== 'string') return; try { if (!navigator.clipboard?.writeText) throw new Error(); await navigator.clipboard.writeText(result.text); api.toast('Copied to clipboard'); } catch { const area = document.createElement('textarea'); area.value = result.text; area.style.cssText = 'position:fixed;left:-9999px;top:0'; document.body.append(area); area.select(); let success = false; try { success = document.execCommand('copy'); } catch {} area.remove(); api.toast(success ? 'Copied to clipboard' : 'Select the output and copy it manually.'); } });
  const pendingDownloads = new Map();
  function installNativeDownloadHandler() { if (!window.ToolSathiAndroid?.postMessage) return false; window.ToolSathiAndroid.onmessage = event => { try { const reply = JSON.parse(event.data); const pending = pendingDownloads.get(reply.id); if (!pending) return; clearTimeout(pending); pendingDownloads.delete(reply.id); api.toast(reply.ok ? `Saved ${reply.filename || 'your file'} to Downloads` : reply.error || 'Android could not save this file.'); } catch {} }; return true; }
  $('#download-output').addEventListener('click', async () => {
    if (!result) return;
    if (result.blob && installNativeDownloadHandler()) { if (result.blob.size > 8 * 1024 * 1024) { api.toast('This local download is too large for the Android bridge. Use your browser to download it.'); return; } const reader = new FileReader(); const filename = result.filename || 'toolsathi-result.txt'; const mime = result.blob.type; reader.onload = () => { const id = `${Date.now()}-${secureIndex(1000000)}`; const timeout = setTimeout(() => { pendingDownloads.delete(id); api.toast('Android has not confirmed the download. Check your Downloads folder.'); }, 30000); pendingDownloads.set(id, timeout); window.ToolSathiAndroid.postMessage(JSON.stringify({type: 'saveFile', id, filename, mime, base64: String(reader.result).split(',')[1]})); }; reader.onerror = () => api.toast('The file could not be read for download.'); reader.readAsDataURL(result.blob); return; }
    const url = result.download_url || blobUrl; if (!url) return; const a = document.createElement('a'); a.href = url; a.download = result.filename || 'toolsathi-result.txt'; a.rel = 'noopener'; document.body.append(a); a.click(); a.remove();
  });
  document.querySelectorAll('.file-drop').forEach(drop => { const input = drop.querySelector('input[type=file]'); const list = drop.querySelector('.file-list'); const describe = () => { list.replaceChildren(); [...input.files].forEach((file, i) => { const line = document.createElement('div'); line.textContent = `${i + 1}. ${file.name} · ${(file.size / 1024).toFixed(1)} KB`; list.append(line); }); }; input.addEventListener('change', describe); ['dragenter', 'dragover'].forEach(name => drop.addEventListener(name, event => { event.preventDefault(); drop.classList.add('drag-active'); })); ['dragleave', 'drop'].forEach(name => drop.addEventListener(name, () => drop.classList.remove('drag-active'))); drop.addEventListener('drop', event => { event.preventDefault(); const files = [...event.dataTransfer.files]; if (!input.multiple && files.length > 1) { api.toast('This tool accepts one file at a time.'); return; } const transfer = new DataTransfer(); files.forEach(file => transfer.items.add(file)); input.files = transfer.files; describe(); }); });
  function updateUnits() { if (slug !== 'unit-converter') return; const kind = form.elements.namedItem('kind').value.toLowerCase(); ['from_unit', 'to_unit'].forEach(key => { const field = form.elements.namedItem(key); [...field.options].forEach(option => { const available = option.textContent.split('·')[0].trim().toLowerCase() === kind; option.hidden = !available; option.disabled = !available; }); if (field.selectedOptions[0]?.disabled || !field.value) field.value = [...field.options].find(option => !option.disabled)?.value || ''; }); }
  form.elements.namedItem('kind')?.addEventListener('change', updateUnits); updateUnits();
  window.addEventListener('pagehide', () => { if (blobUrl) URL.revokeObjectURL(blobUrl); });
})();
