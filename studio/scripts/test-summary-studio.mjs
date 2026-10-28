import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const args = process.argv.slice(2), option = (key, fallback) => args.includes(key) ? args[args.indexOf(key) + 1] : fallback;
const { chromium } = await import(option('--playwright') ? pathToFileURL(option('--playwright')).href : 'playwright');
const base = option('--base', 'http://127.0.0.1:8789'), output = option('--output', '/tmp/summary-studio-smoke.json');
const browser = await chromium.launch({ headless: true, ...(option('--chromium') ? { executablePath: option('--chromium') } : {}), args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
const errors = [], checks = [], requests = [];
page.setDefaultNavigationTimeout(120000);
page.on('pageerror', error => errors.push(error.message));
page.on('request', request => { if (request.url().endsWith('/api/preview/analyze')) requests.push(request.postDataJSON()); });
const source = "from torch import nn\nclass FFN(nn.Module):\n def __init__(self):\n  super().__init__()\n  self.up=nn.Linear(4,8)\n  self.relu=nn.ReLU()\n  self.down=nn.Linear(8,4)\n def forward(self,x):\n  return self.down(self.relu(self.up(x)))\nclass Cell(nn.Module):\n def __init__(self):\n  super().__init__()\n  self.ffn=FFN()\n  self.norm=nn.LayerNorm(4)\n def forward(self,x):\n  return self.norm(x+self.ffn(x))\nclass Model(nn.Module):\n def __init__(self):\n  super().__init__()\n  self.cell=Cell()\n  self.drop=nn.Dropout(0.15)\n def forward(self,x):\n  return self.drop(self.cell(x))\n";
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
async function waitPreset(preset) {
  await page.waitForFunction(preset => [...document.querySelectorAll('.semantic-frontier .segmented button')].some(button => button.classList.contains('active') && button.textContent.startsWith(preset)), preset);
  return snapshot();
}
try {
  await page.goto(base, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => { const button = document.querySelector('.semantic-frontier .segmented button'); return button && !button.disabled; }, { timeout: 60000 });
  await page.locator('.workspace-menu > summary').click();
  await page.getByRole('button', { name: '导入 Python 源码', exact: true }).click();
  await page.getByLabel('模型入口类名').fill('Model');
  await page.getByLabel('源文件名').fill('native_model.py');
  await page.getByLabel('Python 源码', { exact: true }).fill(source);
  const analyzed = page.waitForResponse(response => response.url().endsWith('/api/preview/analyze') && response.status() === 200);
  await page.getByRole('button', { name: '分析并打开', exact: true }).click();
  const bundle = await (await analyzed).json();
  assert.equal(requests.at(-1).semanticMode, 'summary');
  assert.equal(bundle.ir.semantic_ir.schema, 'archcanvas-source-semantic/2');
  await page.getByRole('dialog', { name: '打开模型', exact: true }).waitFor({ state: 'hidden', timeout: 60000 });
  await page.locator('.summary-semantic > summary').waitFor();
  await page.getByRole('button', { name: 'F0 概览', exact: true }).waitFor({ state: 'visible' });
  await page.waitForFunction(() => !document.querySelector('.semantic-frontier .segmented button').disabled);
  let doc = await snapshot();
  const original = JSON.stringify(doc.graph.generic.ir);
  const sourceBefore = await command('request-source');
  assert.equal(sourceBefore.bundle.ir.semantic_ir.ir_digest, bundle.ir.semantic_ir.ir_digest);
  checks.push('Studio imports through Summary semantic v2 and the native canvas retains its exact source bundle');

  await page.locator('.summary-semantic > summary').click();
  assert.match(await page.locator('.summary-semantic').innerText(), /模型执行\s*否/);
  assert.match(await page.locator('.summary-semantic').innerText(), /语义契约/);
  await page.getByRole('tree', { name: '模型层级' }).waitFor();
  checks.push('Studio keeps its hierarchy and folding inspector while exposing native Summary evidence');
  await page.getByRole('button', { name: 'F0 概览', exact: true }).click();
  await waitPreset('F0');
  await command('zoom', { factor: 1.4 });
  const f0 = await snapshot();
  await page.getByRole('button', { name: 'F1 详图', exact: true }).click();
  const f1 = await waitPreset('F1');
  assert.ok(f1.graph.nodes.length > f0.graph.nodes.length, 'nested modules must refine at F1');
  await command('zoom', { factor: 1.2 });
  const f1Camera = (await snapshot()).graph.studioCamera;
  await command('undo'); assert.equal((await snapshot()).frontierPreset, 'overview');
  await command('redo'); assert.equal((await snapshot()).frontierPreset, 'detail');
  assert.deepEqual((await snapshot()).graph.studioCamera, f1Camera);
  checks.push('native frontier undo/redo restores preset and live camera');
  assert.equal(JSON.stringify(f1.graph.generic.ir), original);
  await page.getByRole('button', { name: 'F0 概览', exact: true }).click();
  const returned = await waitPreset('F0');
  assert.deepEqual(returned.graph.nodes.map(node => [node.id,node.x,node.y,node.w,node.h]), f0.graph.nodes.map(node => [node.id,node.x,node.y,node.w,node.h]));
  assert.deepEqual(returned.graph.studioCamera, f0.graph.studioCamera);
  checks.push('returning to a native cut restores exact layout and its own viewport');
  assert.equal(JSON.stringify(returned.graph.generic.ir), original);
  assert.ok(f1.semanticView.recipe.role_paths.length + f1.semanticView.recipe.stage_requests.length > 0);
  await page.locator('.summary-view > summary').click();
  await page.getByLabel('Summary 语义切面', {exact:true}).selectOption('detailed');
  await page.waitForFunction(() => document.querySelector('[aria-label="Summary 语义切面"]').value === 'detailed' && !document.querySelector('[aria-label="Summary 语义切面"]').disabled);
  const detailed = await snapshot();
  assert.equal(detailed.semanticView.granularity, 'detailed');
  assert.equal(JSON.stringify(detailed.graph.generic.ir), original);
  await page.getByRole('button', {name:'F0 概览',exact:true}).click();await waitPreset('F0');
  checks.push('host certified F0 → F1 → F0 and semantic granularity changes preserve canonical nodes, operands and accounting');

  await command('set-frontier', { preset: 'detail' });
  const roleDoc = await snapshot(), role = roleDoc.semanticView.roleOptions.find(role => roleDoc.graph.nodes.some(node => node.id === role.node));
  assert.ok(role, 'fixture must expose a certified role in the visible frontier');
  await command('focus', { nodeId: role.node });
  const roleButton = page.getByRole('button', { name: '细化路径 · ' + role.label, exact: true });
  await roleButton.waitFor();
  const beforeRole = await snapshot();
  await roleButton.click();
  let roleAfter;
  for (let attempt=0; attempt<100; attempt++) { roleAfter=await snapshot(); if (!roleAfter.busy && roleAfter.snapshotRevision>beforeRole.snapshotRevision) break; await page.waitForTimeout(100); }
  assert.ok(roleAfter.semanticView.roleRequests.some(request => request.certificate === role.certificate && JSON.stringify(request.role) === JSON.stringify(role.role)), JSON.stringify({role,requests:roleAfter.semanticView.roleRequests,before:beforeRole.snapshotRevision,after:roleAfter.snapshotRevision}));
  checks.push('the Studio folding inspector sends a real certified role-path request');
  await command('set-frontier', { preset: 'overview' });
  const latentDoc = await snapshot();
  const latent = latentDoc.graph.generic.ir.nodes.find(node => !latentDoc.graph.nodes.some(visible => visible.id === node.id) && latentDoc.graph.semanticHierarchy.nodes.some(item => item.id === node.id));
  assert.ok(latent); await command('focus', { nodeId: latent.id });
  assert.equal((await snapshot()).selection.nodeId, latent.id);
  checks.push('latent source navigation opens the native frontier and selects the exact source object');
  await command('expand-all'); const atomic = await snapshot();
  assert.equal(atomic.graph.generic.state.paperCanonical, true);
  assert.deepEqual(atomic.graph.nodes.map(node => node.id).sort(), bundle.ir.semantic_ir.nodes.map(node => node.id).sort());
  assert.deepEqual(atomic.graph.edges.map(edge => edge.id).sort(), bundle.ir.semantic_ir.edges.map(edge => edge.id).sort());
  checks.push('source-unit expand-all retains every native node, dependency and operand');
  const outputNode = atomic.graph.nodes.filter(node => node.semantic.kind === 'interface' && node.semantic.label === 'return').at(-1);
  assert.ok(outputNode);
  const bindingsBefore = JSON.stringify(atomic.graph.edges.map(edge => [edge.id,edge.binding,edge.fixedSource,edge.fixedTarget]));
  await command('visual', {operations:[{type:'portLayout',ownerId:outputNode.id,nodeId:outputNode.id,role:'data',layout:{side:'left',offset:.5}}]});
  const portDoc = await snapshot();
  assert.equal(portDoc.graph.edges.find(edge=>edge.target===outputNode.id).physicalTarget.side,'left');
  assert.equal(JSON.stringify(portDoc.graph.edges.map(edge => [edge.id,edge.binding,edge.fixedSource,edge.fixedTarget])),bindingsBefore);
  await command('undo');
  checks.push('native port layout reroutes the affected wire and preserves canonical producers and operand slots');
  await command('fit'); await command('connect-tool');
  const nativeFrame = page.frameLocator('iframe'), nativeHits = nativeFrame.locator('[data-node-id] .node-hit');
  await nativeHits.nth(0).click({position:{x:8,y:8}}); await nativeHits.nth(1).click({position:{x:8,y:8}});
  const draft = (await snapshot()).graph.edges.find(edge=>edge.draft); assert.ok(draft);
  assert.match(draft.binding.evidence,/no source model writeback/);
  await command('visual',{operations:[{type:'edgeStyle',id:draft.id,style:{stroke:'#c32f52',width:3,dashed:true}}]});
  const withDraft=(await command('save')).document;
  await command('load',{bundle:withDraft});
  assert.ok((await snapshot()).graph.edges.some(edge=>edge.id===draft.id && edge.draft));
  assert.equal(JSON.stringify((await snapshot()).graph.generic.ir),original);
  await command('undo'); // a restored document starts with an empty visual history
  await command('select-tool');
  checks.push('native connect gestures create a portable visual draft while exact source dependencies remain unchanged');
  const visualId = atomic.graph.nodes.find(node => !node.modelHeading && node.parent).id;
  await command('visual', { operations: [{type:'alias',id:visualId,label:'原生显示别名'},{type:'nodeStyle',id:visualId,style:{fill:'#ffeedd'}},{type:'annotation',annotation:{id:'native-note',text:'保留 Studio 面板',x:20,y:20,width:200}}] });
  await command('set-frontier', { preset: 'overview' });
  assert.equal((await snapshot()).graph.studioPresentation.nodes[visualId].alias, '原生显示别名');
  checks.push('Studio aliases, styles and annotations survive native semantic frontier changes');
  const portable = (await command('save')).document;
  await command('load', { bundle: portable });
  assert.equal((await snapshot()).graph.studioPresentation.nodes[visualId].alias, '原生显示别名');
  assert.equal(portable.graph.generic.ir, portable.adapter.ir.semantic_ir);
  const aliased = structuredClone(portable); aliased.graph.generic.ir.nodes[0].label = 'forged source';
  await assert.rejects(command('load', { bundle: aliased }), /IR 与校验内容不一致/);
  // Portable JSON separates shared references; independently changing only
  // its rendered graph must also reject against the intact source adapter.
  const forged = JSON.parse(JSON.stringify(portable)); forged.graph.generic.ir.nodes[0].label = 'forged source';
  await assert.rejects(command('load', { bundle: forged }), /原始语义|契约/);
  assert.equal(JSON.stringify((await snapshot()).graph.generic.ir), original);
  checks.push('portable native editing JSON roundtrips while altered canonical semantics reject');

  const frameBefore = await page.locator('iframe').elementHandle();
  await page.locator('.workspace-menu > summary').click();
  await page.getByRole('button', { name: '正式源码工作副本', exact: true }).click();
  const editorMode = page.locator('.authoring-studio').getByRole('group', { name: '工作区模式' });
  await editorMode.getByRole('button', { name: '视图', exact: true }).waitFor({ state: 'visible' });
  await editorMode.getByRole('button', { name: '视图', exact: true }).click();
  await page.locator('.summary-semantic > summary').waitFor();
  assert.equal(await frameBefore.evaluate(frame => frame.isConnected), true);
  assert.equal(JSON.stringify((await snapshot()).graph.generic.ir), original);
  assert.deepEqual((await command('request-source')).source.files, sourceBefore.source.files);
  checks.push('view → formal editor → view keeps the iframe mounted and source bytes unchanged');

  // The deliberate tamper rejection above must not obscure the final UI evidence.
  const dismissFeedback = page.getByRole('button', { name: '关闭操作反馈' });
  if (await dismissFeedback.isVisible()) await dismissFeedback.click();
  await command('fit');
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await page.getByText(/画布已保存到正式工程|当前预览已保存到浏览器/).waitFor();
  const saved = await snapshot();
  await page.screenshot({ path: output.replace(/\.json$/, '.png'), fullPage: true });
  await page.reload({ waitUntil: 'networkidle' });
  await page.locator('.summary-semantic > summary').waitFor();
  await page.waitForFunction(() => !document.querySelector('.semantic-frontier .segmented button').disabled);
  const restored = await snapshot();
  assert.equal(JSON.stringify(restored.graph.generic.ir), original);
  assert.equal(restored.graph.frontierPreset, saved.graph.frontierPreset);
  assert.deepEqual(restored.graph.studioCamera, saved.graph.studioCamera);
  assert.equal(restored.graph.studioPresentation.nodes[visualId].alias, '原生显示别名');
  assert.deepEqual((await command('request-source')).source.files, sourceBefore.source.files);
  checks.push('top-level save and real page reload restore the native bundle, source and frontier');
  const svg = await command('svg');
  assert.match(svg.svg, /<svg/); assert.match(svg.svg, /wire-path/);
  assert.doesNotMatch(svg.svg, /id="handleLayer"|class="wire-hit"/);
  checks.push('native Summary view exports SVG without editor hit targets');
  await command('show-evidence');
  const frame = page.frameLocator('iframe');
  const [download] = await Promise.all([page.waitForEvent('download'), frame.locator('#currentSourceEvidence').getByRole('button', { name: '下载 Summary 语义 IR v2', exact: true }).click()]);
  const downloaded = await fs.readFile(await download.path(), 'utf8');
  assert.equal(downloaded, bundle.ir.canonicalSemanticIR.slice(0, -1) + ',"ir_digest":' + JSON.stringify(bundle.ir.semantic_ir.ir_digest) + '}');
  checks.push('evidence drawer downloads the original native JSON bytes and digest');
  assert.deepEqual(errors, []);
  const result = { ok: true, checks, browserErrors: errors, semanticDigest: bundle.ir.semantic_ir.ir_digest, counts: { nativeNodes: bundle.ir.semantic_ir.nodes.length, nativeEdges: bundle.ir.semantic_ir.edges.length, f0: f0.graph.nodes.length, f1: f1.graph.nodes.length } };
  await fs.writeFile(output, JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify(result));
} catch (error) {
  await page.screenshot({ path: output.replace(/\.json$/, '-failed.png'), fullPage: true });
  await fs.writeFile(output, JSON.stringify({ ok: false, checks, browserErrors: errors, error: String(error), body: await page.locator('body').innerText() }, null, 2));
  throw error;
} finally { await browser.close(); }
