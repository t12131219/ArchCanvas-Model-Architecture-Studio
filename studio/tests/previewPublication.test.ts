import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { promisify } from 'node:util';
import ts from 'typescript';
import { PreviewPublicationRequestGate, previewPublicationCacheKey, readPreviewPublicationCache, writePreviewPublicationCache } from '../src/previewPublication.ts';

test('publication cache binds complete SVG paint and geometry, source generation, range and physical output', () => {
  const binding = { caseId: 'source-fixture', sourceDigest: 'a'.repeat(64), irDigest: 'b'.repeat(64), revision: 3 };
  const options = { scope: 'detail', nodeId: 'layer', widthMm: 180, format: 'png', dpi: 300 }, svg = '<svg viewBox="0 0 20 30"/>',
    artifact = { id: 'file', format: 'png', url: '/api/exports/file/figure.png', receiptUrl: '/api/exports/file/receipt', receipt: {} };
  const key = previewPublicationCacheKey(svg, binding, options), cache = writePreviewPublicationCache(artifact, key);
  assert.deepEqual(readPreviewPublicationCache(cache, key), artifact);
  for (const changed of [previewPublicationCacheKey(svg + ' ', binding, options), previewPublicationCacheKey(svg, { ...binding, revision: 4 }, options),
    previewPublicationCacheKey(svg, { ...binding, caseId: 'other-case' }, options), ...[{ widthMm: 85 }, { dpi: 600 }, { format: 'pdf' }, { scope: 'document' }, { nodeId: 'another-layer' }]
      .map(option => previewPublicationCacheKey(svg, binding, { ...options, ...option }))]) assert.equal(readPreviewPublicationCache(cache, changed), null);
});

test('an out-of-order SVG or conversion response cannot replace the latest requested range', async () => {
  const gate = new PreviewPublicationRequestGate(), first = gate.begin();
  let finishOld!: (value: string) => void;
  const old = new Promise<string>(resolve => { finishOld = resolve; });
  const latest = gate.begin(), published: string[] = [];
  const pending = old.then(svg => { if (gate.isCurrent(first)) published.push(svg); });
  if (gate.isCurrent(latest)) published.push('latest detail SVG');
  finishOld('old full graph SVG'); await pending;
  assert.deepEqual(published, ['latest detail SVG']);
  const conversion = gate.begin(); gate.invalidate(); assert.equal(gate.isCurrent(conversion), false);
});

function browserPath(): string | undefined {
  const installed = process.env.ARCHCANVAS_TEST_BROWSER;
  if (installed && existsSync(installed)) return installed;
  for (const path of ['/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome']) if (existsSync(path)) return path;
  const cache = `${process.env.HOME}/.cache/ms-playwright`;
  if (existsSync(cache)) for (const version of readdirSync(cache).filter(name => name.startsWith('chromium-')).sort().reverse()) {
    const path = `${cache}/${version}/chrome-linux64/chrome`; if (existsSync(path)) return path;
  }
  return undefined;
}

test('real DOM SVG sanitization preserves path, transform, marker and physical proportions, and passes the publication validator', async context => {
  const browser = browserPath();
  if (!browser) { context.skip('A local Chromium executable is required for the independent browser DOM check.'); return; }
  const runtime = `${process.env.HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs`;
  let automation: string;
  try { automation = process.env.ARCHCANVAS_TEST_PLAYWRIGHT ?? createRequire(import.meta.url).resolve('playwright'); }
  catch { automation = runtime; }
  if (!existsSync(automation)) { context.skip('Playwright is required for the independent browser DOM check.'); return; }
  const fixture = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="-10 20 400 200"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M 0 0 L 10 5 L 0 10 Z" fill="black"/></marker></defs><style>.wire-path {fill:none;stroke:#123456;stroke-width:2;stroke-linejoin:round}.scene-node text{font-family:Arial;font-size:12px}.hidden-label{display:none}</style><g class="scene-node" transform="translate(30,40)"><rect x="0" y="0" width="100" height="60" fill="white" stroke="#222222"/><text x="10" y="25" font-weight="600">Readable node</text></g><text font-size=".001" class="hidden-label">Hidden label</text><text font-size=".001" opacity="0">Hidden transparent label</text><path class="wire-path" d="M 120 80 L 200 80 L 200 150" marker-end="url(#arrow)"/><g id="handleLayer"><circle r="10"/></g><rect class="node-hit" x="0" y="0" width="100" height="100"/><foreignObject><div xmlns="http://www.w3.org/1999/xhtml">HTML</div></foreignObject><script>alert('unsafe')</script></svg>`;
  const module = ts.transpileModule(readFileSync(new URL('../src/previewPublication.ts', import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  }).outputText.replace(/^export /gm, '');
  const { chromium } = await import(pathToFileURL(automation).href);
  let instance;
  try { instance = await chromium.launch({ executablePath: browser, headless: true, args: ['--no-sandbox'], timeout: 10_000 }); }
  catch (error) {
    if (/Operation not permitted|不允许的操作|Failed to create headless user data/i.test(String(error))) {
      context.skip('The current sandbox prevents Chromium startup; run the browser check outside that sandbox.'); return;
    }
    throw error;
  }
  context.after(() => instance.close());
  const page = await instance.newPage();
  const sourceControls = `<g id="source-controls" data-source-control-id="branch-control" data-source-control-owner="predicate" data-source-control-target="if-arm"><path d="M 180 35 H 240 V 75" fill="none" stroke="#8a6a46" stroke-width="1.5" stroke-dasharray="4 4"/><text x="185" y="30" font-size="12">条件成立 · true</text></g><g id="source-decision" data-source-control-owner="predicate" data-source-control-decision="true"><path d="M 170 29 L 176 35 L 170 41 L 164 35 Z" fill="#ffffff" stroke="#8a6a46"/></g><g id="source-control-legend" data-source-control-legend="true"><path d="M 250 170 H 280" stroke="#8a6a46" stroke-dasharray="4 4"/><text x="285" y="174" font-size="12">条件分支 · 非张量</text></g>`;
  const parsed = await page.evaluate(({ module, fixture }: { module: string; fixture: string }) => {
    const sanitize = new Function(`${module}\nreturn sanitizePreviewPublication;`)();
    const output = sanitize(fixture, 180), xml = new DOMParser().parseFromString(output.svg, 'image/svg+xml');
    return { output, path: xml.querySelector('svg>path')!.getAttribute('d'), transform: xml.querySelector('g')!.getAttribute('transform'),
      marker: xml.querySelector('svg>path')!.getAttribute('marker-end'), wireFill: xml.querySelector('svg>path')!.getAttribute('fill'), font: xml.querySelector('text')!.getAttribute('font-size'),
      unsafe: xml.querySelectorAll('script,foreignObject,style,.node-hit,#handleLayer').length,
      controlAttributes: [...xml.querySelectorAll('*')].flatMap(node => [...node.attributes].filter(attribute => attribute.name.startsWith('data-source-control'))).length,
      controlPath: xml.querySelector('#source-controls path')!.getAttribute('d'), controlDash: xml.querySelector('#source-controls path')!.getAttribute('stroke-dasharray'),
      decisionPath: xml.querySelector('#source-decision path')!.getAttribute('d'), controlLabel: xml.querySelector('#source-controls text')!.textContent,
      controlLegend: xml.querySelector('#source-control-legend text')!.textContent };
  }, { module, fixture: fixture.replace('</svg>', sourceControls + '</svg>') });
  assert.equal(parsed.unsafe, 0);
  assert.equal(parsed.path, 'M 120 80 L 200 80 L 200 150'); assert.equal(parsed.transform, 'translate(30,40)');
  assert.equal(parsed.marker, 'url(#arrow)'); assert.equal(parsed.wireFill, 'none'); assert.equal(parsed.font, '12');
  assert.equal(parsed.controlAttributes, 0, 'export strips editor control metadata before the unchanged server publication contract');
  assert.equal(parsed.controlPath, 'M 180 35 H 240 V 75'); assert.equal(parsed.controlDash, '4 4');
  assert.equal(parsed.decisionPath, 'M 170 29 L 176 35 L 170 41 L 164 35 Z');
  assert.equal(parsed.controlLabel, '条件成立 · true'); assert.equal(parsed.controlLegend, '条件分支 · 非张量');
  assert.deepEqual(parsed.output.viewBox, [-10, 20, 400, 200]); assert.equal(parsed.output.physical.heightMm, 90);
  assert.ok(Math.abs(parsed.output.physical.minTextPt - 12 * 180 * 72 / 25.4 / 400) < 1e-10);
  const project = new URL('../../', import.meta.url).pathname;
  const validated = await promisify(execFile)('python3', ['-I', '-S', '-B', '-c',
    'import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_publication.exporter import export_svg;print(json.dumps(export_svg(sys.argv[2],"svg",180,300)["receipt"]))', project, parsed.output.svg], { timeout: 10_000 });
  const receipt = JSON.parse(validated.stdout); assert.deepEqual(receipt.viewBox, [-10, 20, 400, 200]); assert.equal(receipt.widthMm, 180); assert.equal(receipt.heightMm, 90);
});
