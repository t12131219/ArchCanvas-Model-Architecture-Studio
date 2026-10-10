import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { addDraftNode, blankDraft, changeDraft, draftHistory, draftRoutes, parseDraftCache, setDraftPortLayout, travelDraft } from '../src/authoring.ts';
import type { DraftCatalog } from '../src/authoring.ts';
import { applyVisualBatch, buildScene, createDocument, createHistory, reduceHistory, renderSvg, validateDocument } from '../src/core/index.ts';
import type { Architecture, ArchitectureNode, PortLayout } from '../src/core/types.ts';
import { nearestPortLayout, portLayoutKey } from '../src/core/portRouting.ts';
import { orderedLayers } from '../src/core/layerOrdering.ts';
import { draftPresets, insertDraftPreset } from '../src/authoringPresets.ts';
import { readDraftValidation } from '../src/draftValidation.ts';
import { createGeneratedCanvas } from '../src/generatedCanvas.ts';
import { resumeGeneratedWorkspace } from '../src/generatedWorkspace.ts';

const root = fileURLToPath(new URL('../../', import.meta.url));
const run = promisify(execFile);
const catalog = JSON.parse((await run(`${root}.venv/bin/python`, ['-I', '-S', '-B', '-c', 'import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_authoring import module_catalog;print(json.dumps(module_catalog()))', root], { encoding: 'utf8' })).stdout) as DraftCatalog;
const module = (kind: string) => catalog.modules.find(module => module.kind === kind)!;
function pair(source = { x: 0, y: 200 }, target = { x: 0, y: 0 }) {
  const draft = blankDraft('draft-ports');
  addDraftNode(draft, module('Input'), 'a', source); addDraftNode(draft, module('Output'), 'b', target);
  draft.edges = [{ id: 'tensor', source: { nodeId: 'a', portId: 'output' }, target: { nodeId: 'b', portId: 'input' } }];
  return draft;
}
function document() {
  const node = (id: string, parentId?: string, children: string[] = []): ArchitectureNode => ({ id, label: id, kind: 'Linear', category: 'linear', parentId, children, parameters: {}, evidence: 'source', ports: [
    { id: 'in', name: 'input', direction: 'in', role: 'data', ordinal: 0 }, { id: 'out', name: 'output', direction: 'out', role: 'data', ordinal: 0 },
  ] });
  const architecture: Architecture = { schemaVersion: 1, id: 'port-oracle', label: 'Ports', entry: 'Model', sourceDigest: 'source', irDigest: 'ir', sources: [], diagnostics: [],
    nodes: [node('root', undefined, ['a', 'group']), node('a', 'root'), node('group', 'root', ['b']), node('b', 'group')],
    edges: [{ id: 'tensor', source: { nodeId: 'a', portId: 'out' }, target: { nodeId: 'b', portId: 'in' }, tensorId: 'tensor', role: 'data' }] };
  const d = createDocument(architecture);
  d.layout.a = { x: 0, y: 220 }; d.layout.group = { x: 400, y: 220 };
  return d;
}

test('automatic candidates replace a reverse vertical detour with a straight facing-side route, without editing bindings', () => {
  const d = pair(), bytes = JSON.stringify(d), result = draftRoutes(d, catalog);
  assert.equal(result.ports.a.output.side, 'top'); assert.equal(result.ports.b.input.side, 'bottom');
  assert.deepEqual(result.routes[0].blockedBy, []);
  assert.equal(result.routes[0].points[0].y, 200); assert.equal(result.routes[0].points.at(-1)!.y, 100);
  assert.equal(result.routes[0].points.reduce((sum, p, i, all) => sum + (i ? Math.abs(p.x - all[i - 1].x) + Math.abs(p.y - all[i - 1].y) : 0), 0), 100);
  assert.equal(JSON.stringify(d), bytes);
});

test('all four manual sides keep route endpoints on the public circle and obey source/target normals', () => {
  const vectors = { top: [0, -1], right: [1, 0], bottom: [0, 1], left: [-1, 0] };
  for (const side of Object.keys(vectors) as PortLayout['side'][]) {
    const d = pair({ x: 0, y: 0 }, { x: 400, y: 240 });
    setDraftPortLayout(d, { nodeId: 'a', portId: 'output' }, { side, offset: .3 });
    setDraftPortLayout(d, { nodeId: 'b', portId: 'input' }, { side, offset: .7 });
    const geometry = draftRoutes(d, catalog), points = geometry.routes[0].points;
    assert.deepEqual(geometry.routes[0].blockedBy, [], side);
    assert.deepEqual(points[0], { x: geometry.ports.a.output.x, y: geometry.ports.a.output.y });
    assert.deepEqual(points.at(-1), { x: geometry.ports.b.input.x, y: geometry.ports.b.input.y });
    const [dx, dy] = vectors[side], first = points[0], next = points[1], end = points.at(-1)!, prior = points.at(-2)!;
    assert.ok((next.x - first.x) * dx + (next.y - first.y) * dy >= 12 - .01, side);
    assert.ok((prior.x - end.x) * dx + (prior.y - end.y) * dy >= 12 - .01, side);
  }
});

test('manual offset, automatic reset, undo/redo and JSON reopen retain an independent draft', () => {
  const h = draftHistory(pair()), moved = changeDraft(h, d => setDraftPortLayout(d, { nodeId: 'a', portId: 'output' }, { side: 'left', offset: .25 }));
  assert.equal(moved.past.length, 1); assert.equal(h.draft.nodes[0].portLayouts, undefined);
  assert.deepEqual(travelDraft(travelDraft(moved, 'undo'), 'redo').draft.nodes, moved.draft.nodes);
  const restored = parseDraftCache(JSON.parse(JSON.stringify({ draft: moved.draft, storageRevision: 1, savedRevision: 1 })))!;
  assert.deepEqual(draftRoutes(restored.draft, catalog), draftRoutes(moved.draft, catalog));
  const automatic = changeDraft(moved, d => setDraftPortLayout(d, { nodeId: 'a', portId: 'output' }, null));
  assert.equal(draftRoutes(automatic.draft, catalog).ports.a.output.side, 'top');
});

test('canvas manual proxy attachment survives collapse/reexpand, export, validation and history', () => {
  const base = document(), operation = { type: 'portLayout' as const, ownerId: 'group', nodeId: 'b', portId: 'in', role: 'data' as const, layout: { side: 'left' as const, offset: .7 } };
  const moved = applyVisualBatch(base, [operation]), before = buildScene(moved), port = before.nodes.find(n => n.id === 'group')!.ports[0];
  const reexpanded = applyVisualBatch(applyVisualBatch(moved, [{ type: 'expand', id: 'group', expanded: true }]), [{ type: 'expand', id: 'group', expanded: false }]);
  assert.deepEqual(buildScene(reexpanded).nodes.find(n => n.id === 'group')!.ports, before.nodes.find(n => n.id === 'group')!.ports);
  assert.ok(port.manual); assert.equal(port.side, 'left');
  const points = before.edges[0].path.match(/[-+]?[\d.]+/g)!;
  assert.ok(points.length >= 4); assert.ok(renderSvg(before).includes(`cx="${Math.round(port.x * 100) / 100}" cy="${Math.round(port.y * 100) / 100}"`));
  validateDocument(JSON.parse(JSON.stringify(moved)));
  const history = reduceHistory(createHistory(base), { type: 'apply', operations: [operation] });
  assert.deepEqual(reduceHistory(history, { type: 'undo' }).document.architecture, base.architecture);
  assert.deepEqual(reduceHistory(reduceHistory(history, { type: 'undo' }), { type: 'redo' }).document.portLayoutOverrides, moved.portLayoutOverrides);
});

test('source diagram auto mode is opt-in and canonical bindings and node coordinates stay exact', () => {
  const d = document(), initial = buildScene(d), a = initial.nodes.find(n => n.id === 'a')!;
  const auto = applyVisualBatch(d, [{ type: 'portLayout', ownerId: 'a', nodeId: 'a', portId: 'out', role: 'data', layout: null }]);
  const scene = buildScene(auto);
  assert.deepEqual(scene.nodes.map(n => [n.id, n.x, n.y]), initial.nodes.map(n => [n.id, n.x, n.y]));
  assert.deepEqual(scene.edges.map(e => [e.id, e.source, e.target, e.canonicalEdgeIds]), initial.edges.map(e => [e.id, e.source, e.target, e.canonicalEdgeIds]));
  assert.equal(auto.portLayoutOverrides![portLayoutKey('a', 'a', 'out', 'data')], null);
  assert.equal(d.portLayoutOverrides, undefined); assert.ok(a.ports.length);
});

test('generated view port edits return to the authored endpoint and preserve an explicit automatic reset', () => {
  const draft = blankDraft('draft-generated-ports');
  addDraftNode(draft, module('Input'), 'first', { x: 0, y: 0 }); addDraftNode(draft, module('Output'), 'second', { x: 320, y: 0 });
  draft.edges = [{ id: 'binding', source: { nodeId: 'first', portId: 'output' }, target: { nodeId: 'second', portId: 'input' } }];
  const generated = createGeneratedCanvas(document().architecture, draft, { nodeBindings: { first: 'a', second: 'b' }, edgeBindings: { binding: ['tensor'] } });
  const binding = { workspaceKey: 'generated-ports', documentId: generated.document.id, sourceDigest: generated.document.sourceBindingDigest,
    irDigest: generated.document.architecture.irDigest, draft, nodeBindings: generated.nodeBindings, edgeBindings: generated.edgeBindings, visualRevision: generated.document.revision };
  const workspace = { draft, history: draftHistory(draft) };
  const moved = applyVisualBatch(generated.document, [{ type: 'portLayout', ownerId: 'a', nodeId: 'a', portId: 'out', role: 'data', layout: { side: 'bottom', offset: .4 } }]);
  const view = { selection: [], camera: { x: 0, y: 0, zoom: 1 }, tool: 'select' as const, sourceHistory: { past: 0, future: 0 } };
  const resumed = resumeGeneratedWorkspace(workspace, moved, binding, view);
  assert.deepEqual(resumed.draft.nodes.find(node => node.id === 'first')!.portLayouts, { output: { side: 'bottom', offset: .4 } });
  const reset = applyVisualBatch(moved, [{ type: 'portLayout', ownerId: 'a', nodeId: 'a', portId: 'out', role: 'data', layout: null }]);
  const automatic = resumeGeneratedWorkspace(workspace, reset, binding, view);
  assert.deepEqual(automatic.draft.nodes.find(node => node.id === 'first')!.portLayouts, { output: null });
});

test('invalid offsets, sides and unknown canonical ports are rejected before a visual history change', () => {
  const d = document(), bytes = JSON.stringify(d);
  for (const layout of [{ side: 'left', offset: NaN }, { side: 'left', offset: 1.1 }, { side: 'inside', offset: .5 }]) assert.throws(() => applyVisualBatch(d, [{ type: 'portLayout', ownerId: 'a', nodeId: 'a', portId: 'out', role: 'data', layout } as never]));
  assert.throws(() => applyVisualBatch(d, [{ type: 'portLayout', ownerId: 'a', nodeId: 'a', portId: 'missing', role: 'data', layout: null }]));
  assert.equal(JSON.stringify(d), bytes);
  assert.deepEqual(nearestPortLayout({ x: 0, y: 0, width: 176, height: 100, expanded: false, headerHeight: 0 }, { x: -20, y: 25 }), { side: 'left', offset: .171 });
});

test('layer ordering removes a reversed downstream crossing without rewriting ranks', () => {
  const ranks = new Map([['a', 0], ['b', 0], ['d', 1], ['c', 1]]), bytes = JSON.stringify([...ranks]);
  const ordered = orderedLayers(['a', 'b', 'd', 'c'], ranks, [['a', 'c'], ['b', 'd']]);
  assert.deepEqual(ordered.get(1), ['c', 'd']); assert.equal(JSON.stringify([...ranks]), bytes);
});

test('every catalog module and every inserted preset keeps English module text while user aliases remain untouched', () => {
  for (const m of catalog.modules) {
    assert.equal(m.label, m.kind); assert.ok(m.description.length); assert.doesNotMatch(m.description, /[\u4e00-\u9fff]/);
    const d = blankDraft('draft-English'); addDraftNode(d, m, 'a', { x: 0, y: 0 }); assert.equal(d.nodes[0].label, m.label);
  }
  for (const preset of draftPresets) {
    const d = blankDraft('draft-English'); let id = 0;
    insertDraftPreset(d, catalog, preset.id, { x: 0, y: 0 }, prefix => `${prefix}_${++id}`);
    for (const node of d.nodes) assert.doesNotMatch(node.label, /[\u4e00-\u9fff]/, `${preset.id}: ${node.label}`);
  }
  const d = pair(); d.nodes[0].label = '用户的自定义名称';
  const edited = changeDraft(draftHistory(d), d => setDraftPortLayout(d, { nodeId: 'a', portId: 'output' }, { side: 'left', offset: .5 }));
  assert.equal(edited.draft.nodes[0].label, '用户的自定义名称');
});

test('real backend normalization and response reader preserve manual ports, with identical generated model source', async () => {
  const d = pair({ x: 0, y: 0 }, { x: 300, y: 0 });
  setDraftPortLayout(d, { nodeId: 'a', portId: 'output' }, { side: 'bottom', offset: .4 });
  const promise = run(`${root}.venv/bin/python`, ['-I', '-S', '-B', '-c', 'import sys,json,copy;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_authoring import validate_draft,generate_model;d=json.load(sys.stdin);v=validate_draft(d);other=copy.deepcopy(d);[n.pop("portLayouts",None) for n in other["nodes"]];assert generate_model(d)["source"]==generate_model(other)["source"];print(json.dumps(v))', root], { encoding: 'utf8' });
  promise.child.stdin!.end(JSON.stringify(d));
  const result = JSON.parse((await promise).stdout);
  const parsed = readDraftValidation(result);
  assert.deepEqual(parsed.draft.nodes[0].portLayouts, d.nodes[0].portLayouts); assert.ok(parsed.complete);
});
