/* Run against a local server: BASE_URL=http://127.0.0.1:8000 node tests/browser.cjs */
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const base = process.env.BASE_URL || 'http://127.0.0.1:8000';
const output = process.env.QA_OUTPUT || path.join(process.cwd(), '.runtime', 'browser-qa');
fs.mkdirSync(output, {recursive:true});
const checks = [];
(async () => {
  const browser = await chromium.launch({headless:true, ...(process.env.BROWSER_CHANNEL ? {channel:process.env.BROWSER_CHANNEL} : {})});
  const context = await browser.newContext({viewport:{width:1440,height:1000}, acceptDownloads:true});
  const page = await context.newPage();
  const errors = []; const requests = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {if(request.method() === 'POST' && request.url().includes('/api/tools/')) requests.push(request.url());});
  try {
    await page.goto(base, {waitUntil:'networkidle'});
    assert.equal(await page.title(), 'ToolSathi — Every Tool. One Place.');
    assert.equal(await page.locator('.tool-card').count(), 8);
    await page.screenshot({path:path.join(output, 'homepage-desktop.png')});
    checks.push('Homepage, eight working popular tools, desktop screenshot');
    await page.locator('#hero-search').fill('join pdf');
    await page.waitForFunction(() => document.querySelector('#hero-results .search-result')?.textContent.includes('PDF Merger'));
    await page.locator('#hero-search').press('ArrowDown');
    await page.locator('#hero-search').press('Enter');
    await page.waitForURL('**/tools/pdf-merger/');
    checks.push('Alias autocomplete and keyboard selection');
    await page.keyboard.press('Control+k');
    await page.locator('#command-search').fill('json formater');
    await page.waitForFunction(() => document.querySelector('#command-results .search-result')?.textContent.includes('JSON Formatter'));
    await page.locator('#command-search').press('ArrowDown');
    await page.locator('#command-search').press('Enter');
    await page.waitForURL('**/tools/json-formatter/');
    await page.locator('#load-example').click(); await page.locator('#process-button').click();
    await page.waitForFunction(() => document.querySelector('#output-status').textContent === 'Done');
    assert.match(await page.locator('#text-output').textContent(), /ToolSathi/);
    await page.locator('#field-text').fill('{"integer":9007199254740993,"empty":{},"a":[1,2]}');
    await page.locator('#process-button').click();
    assert.match(await page.locator('#text-output').textContent(), /9007199254740993/);
    assert.equal(requests.length, 0);
    const downloadEvent = page.waitForEvent('download'); await page.locator('#download-output').click();
    const download = await downloadEvent; assert.match(download.suggestedFilename(), /\.json$/);
    checks.push('Command search, local JSON processing, exact integers, native JSON download');
    await page.locator('.tool-favorite').click();
    await page.goto(base); await page.locator('[data-favorite-list] a[href="/tools/json-formatter/"]').waitFor();
    assert.match(await page.locator('[data-recent-list]').textContent(), /JSON Formatter/);
    checks.push('Local favorites and recent tool IDs');
    await page.goto(`${base}/category/pdf/`);
    await page.locator('#directory-query').fill('join pdf');
    await page.waitForFunction(() => document.querySelector('#directory-count').textContent.includes('join pdf'));
    assert.match(await page.locator('.directory-grid .tool-card').first().textContent(), /PDF Merger/);
    assert.match(await page.locator('#directory-count').textContent(), new RegExp(`${await page.locator('.directory-grid .tool-card').count()} tools?`));
    checks.push('HTMX directory search updates cards and count without navigation');
    for (const slug of ['secure-password-generator','jwt-decoder','hash-generator','word-counter','uuid-generator','unit-converter','markdown-editor','json-to-csv','contrast-checker','qr-code-generator']) {
      await page.goto(`${base}/tools/${slug}/`); await page.locator('#load-example').click(); await page.locator('#process-button').click();
      await page.waitForFunction(() => ['Done', 'Check your input'].includes(document.querySelector('#output-status').textContent));
      assert.equal(await page.locator('#output-status').textContent(), 'Done', slug + ': ' + await page.locator('#tool-error').textContent());
      assert.equal(await page.locator('#download-output').isEnabled(), true, slug);
    }
    assert(!requests.some(url => /secure-password-generator|jwt-decoder|hash-generator/.test(url)));
    checks.push('Ten representative tools including secret tools processed only in browser');
    await page.goto(`${base}/tools/html-playground/`);
    await page.locator('#field-text').fill('<h1>Hello</h1><script>parent.hacked=true</script><img src="https://example.invalid/leak">');
    await page.locator('#process-button').click();
    assert.equal(await page.locator('#visual-output iframe').getAttribute('sandbox'), '');
    assert.equal(await page.evaluate(() => window.hacked), undefined);
    checks.push('HTML preview has isolated script-disabled sandbox');
    await page.goto(`${base}/tools/image-resizer/`);
    await page.locator('input[type=file]').setInputFiles(path.join(process.cwd(), 'static', 'icons', 'icon192.png'));
    await page.locator('#field-width').fill('100'); await page.locator('#field-height').fill('100');
    await page.locator('#process-button').click(); await page.waitForFunction(() => document.querySelector('#output-status').textContent === 'Done');
    await page.locator('#visual-output img').waitFor();
    await page.waitForFunction(() => document.querySelector('#visual-output img').naturalWidth === 100);
    const fileDownload = page.waitForEvent('download'); await page.locator('#download-output').click();
    assert.match((await fileDownload).suggestedFilename(), /\.jpg$/);
    checks.push('Image upload, resize, real preview and file download');
    const fileTools = ['image-compressor','image-resizer','jpg-to-png','png-to-jpg','image-to-webp','webp-to-png','image-cropper','image-rotator','image-quality-reducer','signature-resizer','image-dimension-checker','image-metadata-viewer','jpg-to-pdf','png-to-pdf','pdf-merger','pdf-splitter','pdf-page-extractor','pdf-page-reorder','pdf-rotator','pdf-metadata-viewer'];
    for (const slug of fileTools) {
      await page.goto(`${base}/tools/${slug}/`); await page.locator('#load-example').click();
      await page.waitForFunction(() => document.querySelector('input[type=file]').files.length > 0 && !document.querySelector('#load-example').disabled);
      await page.locator('#process-button').click();
      await page.waitForFunction(() => ['Done', 'Check your input'].includes(document.querySelector('#output-status').textContent));
      assert.equal(await page.locator('#output-status').textContent(), 'Done', slug + ': ' + await page.locator('#tool-error').textContent());
      assert(await page.locator('#download-output').isEnabled(), slug);
    }
    checks.push('All 20 image/PDF tools process their genuine sample files in the browser');
    const saved = await page.evaluate(() => JSON.stringify({...localStorage}));
    assert(!saved.includes('9007199254740993') && !saved.includes('eyJhbGci'));
    checks.push('No tool contents stored in localStorage');
    await page.goto(`${base}/download-app/`);
    assert.match(await page.locator('.coming-soon').textContent(), /coming soon/);
    assert.equal(await page.locator('a[href="/downloads/toolsathi-latest.apk"]').count(), 0);
    checks.push('APK absent state contains no broken download button');
    for (const width of [360,390,768,1024,1440]) {
      await page.setViewportSize({width,height:900});
      for(const route of ['/', '/tools/', '/tools/json-formatter/', '/tools/image-resizer/', '/download-app/']) {
        await page.goto(base+route);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
        assert.equal(overflow, false, `${width}px ${route} has horizontal overflow`);
      }
    }
    await page.setViewportSize({width:390,height:844}); await page.goto(base);
    await page.locator('.mobile-toggle').click(); assert.equal(await page.locator('.mobile-nav').isVisible(), true);
    await page.locator('.mobile-toggle').click(); await page.screenshot({path:path.join(output, 'homepage-mobile.png'),fullPage:true});
    await page.goto(`${base}/tools/json-formatter/`); await page.locator('#load-example').click(); await page.locator('#process-button').click();
    await page.screenshot({path:path.join(output, 'tool-mobile.png'),fullPage:true});
    checks.push('25 responsive route/viewport combinations, mobile navigation and screenshots');
    await page.emulateMedia({reducedMotion:'reduce'});
    assert.equal(await page.locator('.ambient-grid').evaluate(el => getComputedStyle(el).animationName), 'none');
    checks.push('Reduced-motion setting respected');
    await page.goto(base); await page.evaluate(() => navigator.serviceWorker.ready);
    await context.setOffline(true); await page.goto(`${base}/tools/`);
    assert.match(await page.locator('body').textContent(), /offline|connection/i); await context.setOffline(false);
    checks.push('Service-worker offline fallback');
    assert.deepEqual(errors, []);
    checks.push('No uncaught JavaScript errors');
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify({passed:true, checks}, null, 2));
    console.log(JSON.stringify({passed:true,checks}, null, 2));
  } catch(error) {
    await page.screenshot({path:path.join(output, 'failure.png'),fullPage:true}).catch(()=>{});
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify({passed:false,checks,error:String(error),errors},null,2));
    throw error;
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
