import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { addDraftNode, arrangeDraft, blankDraft, changeDraft, draftHistory, draftRoutes, nextDraftPosition, portPoint, travelDraft } from '../src/authoring.ts';
import type { DraftCatalog, DraftModule, DraftNode, DraftPort } from '../src/authoring.ts';
import { draftModuleSize, draftNodeBounds, draftNodeSize, draftPortSpacing } from '../src/draftNodeGeometry.ts';
import { draftPortPresentation } from '../src/draftPortPresentation.ts';
import { draftCanvasTextScale } from '../src/draftTextReadability.ts';
import { fitDraftCamera } from '../src/authoringFeedback.ts';
import { draftPresets, draftPresetSize, insertDraftPreset } from '../src/authoringPresets.ts';

// Real catalog data comes from the formal nonexecuting package. The fixed
// dimensions, anchors, text advances and obstacle rectangles below are written
// independently; none use the geometry/routing helpers as their oracle.
const project = fileURLToPath(new URL('../../', import.meta.url));
const result = await promisify(execFile)(`${project}.venv/bin/python`, ['-I', '-S', '-B', '-c',
  'import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_authoring import module_catalog;print(json.dumps(module_catalog()))', project]);
const catalog = JSON.parse(result.stdout) as DraftCatalog;
function module(kind: string) { const value = catalog.modules.find(item => item.kind === kind); assert.ok(value, kind); return value; }
function node(kind: string, x = 20, y = 30): DraftNode { return { id: `sample-${kind}`, kind, label: kind, parameters: structuredClone(module(kind).defaults), position: { x, y } }; }
const registered = ['Input', 'Output', 'Linear', 'ReLU', 'GELU', 'SiLU', 'Identity', 'Dropout', 'Flatten', 'Conv2d', 'MaxPool2d', 'AdaptiveAvgPool2d', 'BatchNorm2d', 'LayerNorm', 'Embedding', 'Add', 'Concat'];
const close = (actual: number, expected: number) => assert.ok(Math.abs(actual - expected) < 1e-9, `${actual} != ${expected}`);

test('all17 actual kinds keep unary cards stable and give two-input cards their independent140world body', () => {
  assert.deepEqual(catalog.modules.map(item => item.kind), registered);
  for (const kind of registered) {
    const height = kind === 'Add' || kind === 'Concat' ? 140 : 100;
    const sample = node(kind), original = JSON.stringify([sample, module(kind)]);
    assert.deepEqual(draftModuleSize(module(kind)), { width: 176, height }, kind);
    assert.deepEqual(draftNodeSize(sample, catalog), { width: 176, height }, kind);
    assert.deepEqual(draftNodeBounds(sample, catalog), { x: 20, y: 30, width: 176, height }, kind);
    for (const port of module(kind).ports) {
      const output = port.direction === 'out', second = port.id === 'right' || port.id === 'b';
      assert.deepEqual(portPoint(sample, module(kind), port.id, 'horizontal'), { x: output ? 196 : 20, y: second ? 128 : 96 });
      const doubleInput = !output && (kind === 'Add' || kind === 'Concat');
      const vertical = portPoint(sample, module(kind), port.id, 'vertical');
      close(vertical.x, 20 + (doubleInput ? second ? 352 / 3 : 176 / 3 : 88));
      close(vertical.y, output ? 30 + height : 30);
    }
    assert.equal(JSON.stringify([sample, module(kind)]), original, 'projection preserves catalog and model facts');
  }
});

test('53percent side labels reach8.1CSSpx while both names and dot hits remain separate', () => {
  const font = 9 * draftCanvasTextScale(.53);
  for (const [kind, ids, advances] of [['Add', ['left', 'right'], [2, 2.56]], ['Concat', ['a', 'b'], [.56, .56]]] as const) {
    const definition = module(kind), sample = node(kind, 0, 0);
    assert.equal(draftPortSpacing(definition, 'in', 'horizontal'), 32);
    const rows = ids.map((id, index) => {
      const port = definition.ports.find(item => item.id === id)!;
      const anchor = portPoint(sample, definition, id, 'horizontal');
      assert.deepEqual(anchor, { x: 0, y: index ? 98 : 66 });
      const row = draftPortPresentation(port, anchor.x, anchor.y, 'horizontal', 32, font);
      close(row.labelFontSize * .53, 8.1);
      assert.ok(row.hit.x <= -5 && row.hit.x + row.hit.width >= row.labelX + advances[index] * font, 'dot, gap and complete label share one hit');
      assert.ok(row.labelY - font >= row.hit.y && row.labelY <= row.hit.y + row.hit.height, 'one-em text bounds remain inside the hit');
      return row;
    });
    assert.equal(rows[0].hit.y + rows[0].hit.height + 4, rows[1].hit.y, '4world gap between transparent peer hits');
    assert.ok(rows[0].labelY < rows[1].labelY - rows[1].labelFontSize, 'peer label line boxes do not overlap');
    assert.ok(rows[0].labelY - font > 49, 'first input text clears the tensor baseline');
    assert.ok(rows[1].labelY < 132 - 10 * draftCanvasTextScale(.53), 'second input text clears the kind line');
  }
  assert.ok(9 * draftCanvasTextScale(.4) * .4 < 8, 'bounded compensation does not certify arbitrary overview zoom');
});

test('vertical labels stay fully exterior to every card, clearing the kind caption and preserving dot hits', () => {
  const font = 9 * draftCanvasTextScale(.53);
  for (const kind of registered) for (const port of module(kind).ports) {
    const sample = node(kind, 0, 0), anchor = portPoint(sample, module(kind), port.id, 'vertical');
    const row = draftPortPresentation(port, anchor.x, anchor.y, 'vertical', draftPortSpacing(module(kind), port.direction, 'vertical'), font);
    assert.equal(row.hit.y, anchor.y - 14); assert.equal(row.hit.height, 28, 'dot hit remains centred on the actual endpoint');
    if (port.direction === 'in') { assert.equal(row.labelY, -4); assert.ok(row.labelY < 0); }
    else { close(row.labelY - font, anchor.y + 4); assert.ok(row.labelY - font > (kind === 'Add' || kind === 'Concat' ? 140 : 100)); }
  }
  const definition = module('Add'), sample = node('Add', 0, 0);
  const rows = ['left', 'right'].map(id => {
    const port = definition.ports.find(item => item.id === id)!, anchor = portPoint(sample, definition, id, 'vertical');
    return draftPortPresentation(port, anchor.x, anchor.y, 'vertical', 176 / 3, font);
  });
  assert.ok(rows[0].labelX + 2 * font < rows[1].hit.x, 'left label paint does not enter the later hit');
  assert.ok(rows[0].hit.x + rows[0].hit.width <= rows[1].hit.x);
  // Vertical rectangles intentionally reserve peer space; the exterior text
  // receives pointer events on its owning g. No full-label rectangle claim.
});

test('dimensions and ordered anchors follow declared ports rather than an Add name shortcut', () => {
  const input = (id: string): DraftPort => ({ id, name: id, direction: 'in', type: 'tensor' });
  const custom: DraftModule = { ...structuredClone(module('Identity')), kind: 'ThreeInputs', ports: [input('one'), input('two'), input('three'), { id: 'output', name: 'output', direction: 'out', type: 'tensor' }] };
  const sample: DraftNode = { id: 'custom', kind: 'ThreeInputs', label: 'three', parameters: {}, position: { x: 10, y: 20 } };
  assert.deepEqual(draftModuleSize(custom), { width: 176, height: 172 });
  assert.deepEqual(['one', 'two', 'three'].map(id => portPoint(sample, custom, id)), [{ x: 10, y: 86 }, { x: 10, y: 118 }, { x: 10, y: 150 }]);
  assert.deepEqual(portPoint(sample, custom, 'output', 'vertical'), { x: 98, y: 192 });
  const namedAdd = { ...structuredClone(module('Identity')), kind: 'Add' };
  assert.deepEqual(draftModuleSize(namedAdd), { width: 176, height: 100 });
  assert.deepEqual(draftNodeSize({ kind: 'ExternalUnknown' }, catalog), { width: 176, height: 100 });
  assert.throws(() => portPoint(sample, custom, 'foreign'), /未知端口/);
});

test('fit includes the complete taller body and exterior routes without changing draft or camera-independent facts', () => {
  const draft = blankDraft('draft-independent-tall-fit'); draft.nodes = [node('Add')];
  const before = JSON.stringify(draft), camera = fitDraftCamera(draft, { width: 400, height: 120 }, catalog);
  close(camera.zoom, 90 / 204);
  for (const y of [30, 170]) assert.ok(y * camera.zoom + camera.y >= 15 && y * camera.zoom + camera.y <= 105);
  const points = [{ x: -180, y: -70 }, { x: 800, y: 500 }], originals = JSON.stringify(points);
  const routedCamera = fitDraftCamera(draft, { width: 400, height: 240 }, catalog, points);
  for (const point of [...points, { x: 20, y: 30 }, { x: 196, y: 170 }]) {
    const x = point.x * routedCamera.zoom + routedCamera.x, y = point.y * routedCamera.zoom + routedCamera.y;
    assert.ok(x >= 0 && x <= 400 && y >= 0 && y <= 240);
  }
  assert.equal(JSON.stringify(draft), before); assert.equal(JSON.stringify(points), originals);
});

test('single insertion and explicit arrange avoid the newly occupied lower40world band', () => {
  const draft = blankDraft('draft-independent-tall-insertion'); draft.nodes = [node('Add', 100, 100)];
  const before = JSON.stringify(draft);
  assert.deepEqual(nextDraftPosition(draft, { x: 100, y: 225 }, module('Input'), catalog), { x: 100, y: 268 });
  assert.equal(JSON.stringify(draft), before, 'old manual positions do not move');
  const incoming = blankDraft('draft-independent-incoming-tall'); incoming.nodes = [node('Input', 100, 300)];
  assert.deepEqual(nextDraftPosition(incoming, { x: 100, y: 175 }, module('Add'), catalog), { x: 100, y: 428 });
  const stacked = blankDraft('draft-independent-tall-arrange'); stacked.nodes = [node('Add'), node('Concat'), node('Input')];
  const facts = stacked.nodes.map(({ position, ...value }) => value);
  arrangeDraft(stacked, catalog);
  assert.deepEqual(stacked.nodes.map(item => item.position), [{ x: 50, y: 70 }, { x: 50, y: 264 }, { x: 50, y: 458 }]);
  assert.deepEqual(stacked.nodes.map(({ position, ...value }) => value), facts);
  assert.deepEqual(draftRoutes(stacked, catalog).overlaps, []);
});

test('transparent preset bounds and old-card collisions include taller merge modules atomically', () => {
  const expected = new Map([['mlp', { width: 1168, height: 100 }], ['cnn', { width: 848, height: 280 }], ['residual-mlp', { width: 1416, height: 140 }]]);
  for (const preset of draftPresets) assert.deepEqual(draftPresetSize(preset, catalog), expected.get(preset.id));
  for (const [kind, x, y, preferred, expectedY] of [
    ['Add', 100, 100, { x: 50, y: 225 }, 268],
    ['Input', 1042, 170, { x: 50, y: 50 }, 298],
  ] as const) {
    const draft = blankDraft(`draft-independent-preset-${kind}`); draft.nodes = [node(kind, x, y)];
    const old = structuredClone(draft.nodes[0]); let count = 0;
    const inserted = insertDraftPreset(draft, catalog, 'residual-mlp', preferred, prefix => `${prefix}-tall-${++count}`);
    assert.deepEqual(inserted.position, { x: 50, y: expectedY });
    assert.deepEqual(draft.nodes[0], old); assert.equal(inserted.nodeIds.length, 6); assert.equal(inserted.edgeIds.length, 6);
    assert.deepEqual(draftRoutes(draft, catalog).overlaps, []);
  }
});

test('router treats the new lower band as a real obstacle and preserves bindings through history', () => {
  const draft = blankDraft('draft-independent-tall-obstacle');
  addDraftNode(draft, module('Input'), 'source', { x: 50, y: 100 });
  addDraftNode(draft, module('Output'), 'target', { x: 650, y: 100 });
  addDraftNode(draft, module('Add'), 'barrier', { x: 350, y: 55 });
  draft.edges = [{ id: 'binding', source: { nodeId: 'source', portId: 'output' }, target: { nodeId: 'target', portId: 'input' } }];
  const original = JSON.stringify(draft), history = draftHistory(draft);
  for (const [dx, dy] of [[0, 0], [-16, 0], [16, 0], [0, -16], [0, 16]]) {
    const moved = changeDraft(history, value => { value.nodes[2].position.x += dx; value.nodes[2].position.y += dy; });
    const bytes = JSON.stringify(moved), geometry = draftRoutes(moved.draft, catalog), route = geometry.routes[0];
    assert.deepEqual(route.points[0], { x: 226, y: 166 }); assert.deepEqual(route.points.at(-1), { x: 650, y: 166 });
    assert.ok(route.points.length > 2, 'the straight y166 route would cross the taller card');
    const left = 350 + dx, right = 526 + dx, top = 55 + dy, bottom = 195 + dy;
    for (const [index, b] of route.points.slice(1).entries()) {
      const a = route.points[index]; assert.ok(a.x === b.x || a.y === b.y);
      const hits = a.x === b.x ? a.x > left && a.x < right && Math.max(Math.min(a.y, b.y), top) < Math.min(Math.max(a.y, b.y), bottom)
        : a.y > top && a.y < bottom && Math.max(Math.min(a.x, b.x), left) < Math.min(Math.max(a.x, b.x), right);
      assert.equal(hits, false, 'route may not enter the actual lower band');
    }
    assert.deepEqual(route.blockedBy, []); assert.deepEqual(moved.draft.edges, draft.edges); assert.equal(JSON.stringify(moved), bytes);
    if (dx || dy) {
      const undo = travelDraft(moved, 'undo'), redo = travelDraft(undo, 'redo');
      assert.deepEqual(undo.draft.nodes, draft.nodes); assert.deepEqual(redo.draft.nodes, moved.draft.nodes);
      assert.deepEqual(draftRoutes(redo.draft, catalog), geometry);
    }
  }
  assert.equal(JSON.stringify(draft), original);
});
