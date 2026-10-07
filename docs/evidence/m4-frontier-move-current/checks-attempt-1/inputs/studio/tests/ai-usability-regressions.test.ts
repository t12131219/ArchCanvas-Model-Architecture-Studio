import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { createDocument, buildScene, applyVisualBatch, validateDocument } from '../src/core/index.ts';
import type { Architecture, ArchitectureNode } from '../src/core/index.ts';
import { viewportToWorld, zoomCameraAtPoint } from '../src/cameraProjection.ts';
import { arrangeDraft, blankDraft, changeDraft, draftHistory, draftRoutes, travelDraft } from '../src/authoring.ts';
import type { DraftCatalog } from '../src/authoring.ts';
import { fitDraftCamera } from '../src/authoringFeedback.ts';

test('toolbar zoom preserves the viewed world centre at fit, reset and zoom limits', () => {
  for (const camera of [{ x: 321.099, y: 46, zoom: .236641 }, { x: -900, y: -460, zoom: .15 }, { x: 72, y: 340, zoom: 3 }]) {
    for (const zoom of [.15, .5, 1, 3]) {
      const centre = { x: 347, y: 263 }, before = viewportToWorld(camera, centre), next = zoomCameraAtPoint(camera, zoom, centre);
      const after = viewportToWorld(next, centre);
      assert.ok(Math.abs(after.x - before.x) < 1e-9 && Math.abs(after.y - before.y) < 1e-9);
      assert.equal(next.zoom, zoom);
    }
  }
  assert.throws(() => zoomCameraAtPoint({ x: 0, y: 0, zoom: 1 }, 0, { x: 0, y: 0 }));
});

// Independent four-module source contract with the long generated symbols
// that produced short, unnecessary offsets after adding Chinese aliases.
function architecture(): Architecture {
  const leaf = (id: string, label: string, category: string, kind: string): ArchitectureNode => ({ id, label, kind, category,
    parentId: 'root', children: [], evidence: 'source', parameters: {}, ports: [
      ...(kind === 'Input' ? [] : [{ id: 'input', name: 'input', direction: 'in' as const, ordinal: 0, role: 'data' as const }]),
      ...(kind === 'Output' ? [] : [{ id: 'output', name: 'output', direction: 'out' as const, ordinal: 0, role: 'data' as const }]),
    ] });
  return { schemaVersion: 1, id: 'architecture-ai-chain', label: 'AuthoredModel', entry: 'model:AuthoredModel', sourceDigest: 'ai-source', irDigest: 'ai-ir', sources: [], diagnostics: [], nodes: [
    { id: 'root', label: 'AuthoredModel', kind: 'Module', category: 'container', children: ['input', 'linear', 'relu', 'output'], parameters: {}, ports: [], evidence: 'source' },
    leaf('input', 'node_3e6f96bec2d42448', 'input', 'Input'), leaf('linear', 'node_d4bf2f6427a4da3f', 'linear', 'Linear'),
    leaf('relu', 'node_eecf269a39206102', 'activation', 'ReLU'), { ...leaf('output', 'return["n_3e15b27e1d654fd5a641aa8d704ca6d1"]', 'output', 'Output'), outputPath: [{ kind: 'key', key: 'n_3e15b27e1d654fd5a641aa8d704ca6d1' }] },
  ], edges: ['input', 'linear', 'relu'].map((source, i) => ({ id: `edge-${i}`, source: { nodeId: source, portId: 'output' }, target: { nodeId: ['linear', 'relu', 'output'][i], portId: 'input' }, tensorId: `tensor-${i}`, role: 'data' })) };
}

test('new figure measures initial aliases before materializing and keeps its straight chain through reopen and re-expansion', () => {
  const source = architecture(), original = JSON.stringify(source), aliases = { input: '输入', linear: '全连接', relu: 'ReLU 激活', output: '输出' };
  const document = createDocument(source, '模拟新手模型', aliases), scene = buildScene(document);
  const centres = scene.nodes.filter(node => node.id !== 'root').map(node => node.x + node.width / 2);
  assert.ok(centres.every(centre => Math.abs(centre - centres[0]) < 1e-9));
  for (const edge of scene.edges) {
    const commands = edge.path.match(/[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)/g)!;
    let x = 0, firstX = NaN;
    for (let i = 0; i < commands.length;) {
      const command = commands[i++];
      if (command === 'M') { x = +commands[i++]; i++; firstX = x; }
      else if (command === 'H') x = +commands[i++];
      else if (command === 'V') i++;
      else assert.fail(`unexpected path command ${command}`);
      assert.equal(x, firstX, 'single chains need no horizontal detour');
    }
  }
  assert.equal(scene.nodes.find(node => node.id === 'output')!.subtitle, 'model output');
  assert.equal(JSON.stringify(source), original);
  aliases.linear = 'caller mutation'; assert.equal(document.displayAliases.linear, '全连接');
  const reopened = JSON.parse(JSON.stringify(document)); validateDocument(reopened);
  const toggled = applyVisualBatch(applyVisualBatch(reopened, [{ type: 'expand', id: 'root', expanded: false }]), [{ type: 'expand', id: 'root', expanded: true }]);
  assert.deepEqual(toggled.layout, document.layout);
  assert.deepEqual(buildScene(toggled).edges.map(edge => edge.path), scene.edges.map(edge => edge.path));
  assert.equal(JSON.stringify(toggled.architecture), original);
});

test('initial alias validation rejects foreign identities and keeps default creation compatible', () => {
  const source = architecture();
  assert.deepEqual(createDocument(source), createDocument(source, source.label, {}));
  assert.throws(() => createDocument(source, source.label, { foreign: '未知节点' }));
  assert.throws(() => createDocument(source, source.label, { linear: 42 } as never));
  const long = createDocument(source, source.label, { linear: '需要多行完整显示的全连接模块名称'.repeat(5) });
  validateDocument(long); assert.ok(buildScene(long).nodes.find(node => node.id === 'linear')!.height > 62);
});

const project = fileURLToPath(new URL('../../', import.meta.url));
const result = await promisify(execFile)(`${project}.venv/bin/python`, ['-I', '-S', '-B', '-c',
  'import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_authoring import module_catalog;print(json.dumps(module_catalog()))', project]);
const catalog = JSON.parse(result.stdout) as DraftCatalog;
function cnn() {
  const draft = blankDraft('draft-ai-cnn');
  draft.nodes = ['Input', 'Conv2d', 'ReLU', 'MaxPool2d', 'AdaptiveAvgPool2d', 'Flatten', 'Linear', 'Output'].map((kind, index) => ({
    id: `n${index}`, kind, label: kind, parameters: structuredClone(catalog.modules.find(module => module.kind === kind)!.defaults), position: { x: 0, y: 0 },
  }));
  draft.edges = draft.nodes.slice(1).map((node, index) => ({ id: `e${index}`, source: { nodeId: `n${index}`, portId: 'output' }, target: { nodeId: node.id, portId: 'input' } }));
  return draft;
}

test('viewport arrangement folds an eight-module chain, preserves facts/history and avoids body intrusions', () => {
  const draft = cnn(), viewport = { width: 738, height: 500 }, wide = structuredClone(draft); arrangeDraft(wide, catalog);
  const arranged = changeDraft(draftHistory(draft), value => arrangeDraft(value, catalog, viewport));
  assert.deepEqual(arranged.draft.edges, draft.edges);
  assert.deepEqual(arranged.draft.nodes.map(({ position, ...fact }) => fact), draft.nodes.map(({ position, ...fact }) => fact));
  assert.ok(new Set(arranged.draft.nodes.map(node => node.position.y)).size > 1);
  const geometry = draftRoutes(arranged.draft, catalog);
  assert.deepEqual(geometry.overlaps, []); assert.ok(geometry.routes.every(route => !route.blockedBy.length));
  const camera = fitDraftCamera(arranged.draft, viewport, catalog, geometry.routes.flatMap(route => route.points));
  assert.ok(camera.zoom > fitDraftCamera(wide, viewport, catalog).zoom * 1.4, 'folding must materially improve the complete-scene fit');
  assert.deepEqual(travelDraft(arranged, 'undo').draft.nodes, draft.nodes);
  assert.deepEqual(travelDraft(travelDraft(arranged, 'undo'), 'redo').draft.nodes, arranged.draft.nodes);
});

test('viewport folding cannot turn a branch or merge into a unary chain', () => {
  const draft = cnn(); draft.edges.push({ id: 'skip', source: { nodeId: 'n0', portId: 'output' }, target: { nodeId: 'n6', portId: 'input' } });
  const wide = structuredClone(draft); arrangeDraft(wide, catalog); arrangeDraft(draft, catalog, { width: 738, height: 500 });
  assert.deepEqual(draft.nodes, wide.nodes);
});
