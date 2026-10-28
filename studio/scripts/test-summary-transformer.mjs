import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const args = process.argv.slice(2), option = (key, fallback) => args.includes(key) ? args[args.indexOf(key) + 1] : fallback;
const { chromium } = await import(option('--playwright') ? pathToFileURL(option('--playwright')).href : 'playwright');
const base = option('--base', 'http://127.0.0.1:8789'), output = option('--output', '/tmp/summary-transformer-smoke.json');
const browser = await chromium.launch({ headless: true, ...(option('--chromium') ? { executablePath: option('--chromium') } : {}), args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
const errors = [], checks = [], requests = [];
page.on('pageerror', error => errors.push(error.message));
page.on('request', request => { if (request.url().endsWith('/api/preview/analyze')) requests.push(request.postDataJSON()); });
async function command(name, payload = {}) {
  return page.evaluate(({ name, payload }) => new Promise((resolve, reject) => {
    const child = document.querySelector('iframe').contentWindow, requestId = 'smoke-' + crypto.randomUUID();
    const timer = setTimeout(() => { window.removeEventListener('message', listener); reject(new Error('Bridge timeout: ' + name)); }, 60000);
    function listener(event) {
      if (event.source !== child || event.origin !== location.origin || event.data?.requestId !== requestId) return;
      clearTimeout(timer); window.removeEventListener('message', listener);
      if (event.data.type.endsWith(':error')) reject(new Error(JSON.stringify(event.data))); else resolve(event.data);
    }
    window.addEventListener('message', listener);
    child.postMessage({ type: 'archcanvas:preview:' + name, requestId, ...payload }, location.origin);
  }), { name, payload });
}
async function snapshot() { return (await command('snapshot')).document; }
const fixture = new URL('../../fixtures/transformer/', import.meta.url);
const files = Object.fromEntries(await Promise.all(['model.py','blocks.py'].map(async name => [name, await fs.readFile(new URL(name, fixture),'utf8')])));
const cuts = [];
try {
  await page.goto(base, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => { const button = document.querySelector('.semantic-frontier .segmented button'); return button && !button.disabled; }, null, { timeout: 60000 });
  const response = await page.request.post(base + '/api/preview/analyze', { data: { files, entry: 'model:Transformer', semanticMode: 'summary' } });
  assert.equal(response.status(), 200);
  const bundle = await response.json(), ir = bundle.ir.semantic_ir, canonical = JSON.stringify(ir);
  assert.equal(ir.nodes.length, 102); assert.equal(ir.edges.length, 105);
  await command('load', { bundle });
  for (const cut of ['overview','detail','source-unit']) {
    if (cut === 'source-unit') await command('expand-all');
    else {
      await page.getByRole('button', {name: cut === 'overview' ? 'F0 概览' : 'F1 详图', exact: true}).click();
      await page.waitForFunction(label => [...document.querySelectorAll('.semantic-frontier .segmented button')].some(button => button.classList.contains('active') && button.textContent.startsWith(label)), cut === 'overview' ? 'F0' : 'F1', {timeout:60000});
    }
    await page.waitForFunction(() => !document.querySelector('.semantic-frontier .segmented button').disabled, null, {timeout:60000});
    let doc = await snapshot(), attempts = 0;
    for (; attempts < 5 && !doc.graph.nativeRouting.complete; attempts++) {
      await command('continue-routing'); doc = await snapshot();
    }
    assert.equal(JSON.stringify(doc.graph.generic.ir), canonical);
    assert.match(await page.locator('.document-summary').innerText(), /102\s*源码对象\s*105\s*依赖关系/);
    assert.equal(doc.graph.nativeRouting.complete, true, JSON.stringify(doc.graph.nativeRouting));
    const frame = page.frame({url:/index.html\?embed=1/});
    const validation = await frame.evaluate(graph => {
      const v = globalThis.SummaryEngine.validateView(graph);
      return {source:v.source,layout:v.layout,invalid:v.edges.filter(([,e])=>!e.ok)};
    }, doc.graph);
    assert.equal(validation.source.ok, true, JSON.stringify(validation));
    assert.equal(validation.layout.ok, true, JSON.stringify(validation));
    assert.deepEqual(validation.invalid, []);
    assert.equal(await frame.locator('[data-node-id]').count(), doc.graph.nodes.length);
    for (const [ledger, objects] of [[doc.graph.generic.receipts.node_accounting,ir.nodes],[doc.graph.generic.receipts.edge_accounting,ir.edges]]) {
      const ids = Object.values(ledger).flat();
      assert.deepEqual(ids.sort(), objects.map(n=>n.id).sort());
      assert.equal(new Set(ids).size, ids.length);
    }
    if (cut === 'detail') assert.equal(doc.semanticView.recipe.schema,'certified-detail-frontier/1');
    cuts.push({cut,nodes:doc.graph.nodes.length,edges:doc.graph.edges.length,continuations:attempts,routing:doc.graph.nativeRouting,validation});
    checks.push('Transformer '+cut+': exact native accounting, rendered glyphs and all source/geometry/route guards pass');
  }
  assert.deepEqual((await command('request-source')).source.files, files);
  await command('set-frontier',{preset:'detail'});
  await command('fit');
  await page.screenshot({path:output.replace(/\.json$/,'.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  const result={ok:true,checks,browserErrors:errors,semanticDigest:ir.ir_digest,cuts};
  await fs.writeFile(output,JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
} catch(error) {
  await page.screenshot({path:output.replace(/\.json$/,'-failed.png'),fullPage:true});
  await fs.writeFile(output,JSON.stringify({ok:false,checks,cuts,browserErrors:errors,error:String(error)},null,2)+'\n');
  throw error;
} finally { await browser.close(); }
