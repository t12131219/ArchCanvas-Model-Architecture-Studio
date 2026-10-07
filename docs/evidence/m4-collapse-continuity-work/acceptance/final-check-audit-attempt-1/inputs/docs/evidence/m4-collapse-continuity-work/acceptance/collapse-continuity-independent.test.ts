import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { applyVisualBatch, buildScene, createHistory, reduceHistory, validateDocument } from '../../../../studio/src/core/index.ts';
import type { ArchitectureNode, CanvasDocument, Position } from '../../../../studio/src/core/types.ts';

// The expected positions below are authored literal coordinates. No product
// constructor, auto-layout, scene or frontier-key helper supplies expectations.
const COMPACT: Record<string, Position> = {
  root: { x: 50, y: 92 }, input: { x: 30, y: 62 }, block: { x: 30, y: 162 },
  output: { x: 30, y: 362 }, spare: { x: 500, y: 62 },
};
const DEEP: Record<string, Position> = {
  root: { x: 50, y: 92 }, input: { x: 30, y: 62 }, block: { x: 30, y: 162 },
  output: { x: 30, y: 700 }, spare: { x: 500, y: 62 },
  layer: { x: 30, y: 62 }, first: { x: 30, y: 62 }, second: { x: 30, y: 162 }, other: { x: 30, y: 350 },
};
const clone = <T>(value: T): T => structuredClone(value);
const digest = (raw: Buffer | string) => createHash('sha256').update(raw).digest('hex');
function fixture(): CanvasDocument {
  const node = (id: string, parentId?: string, children: string[] = []): ArchitectureNode => ({
    id, label: id, kind: children.length ? 'Module' : 'Linear', category: children.length ? 'container' : 'linear',
    ...(parentId ? { parentId } : {}), children, parameters: {}, evidence: 'source',
    ports: [{ id: `${id}:in`, name: 'input', direction: 'in', role: 'data', ordinal: 0 },
      { id: `${id}:out`, name: 'output', direction: 'out', role: 'data', ordinal: 0 }],
  });
  const doc: CanvasDocument = {
    schemaVersion: 1, id: 'independent-collapse-fixture', title: 'Nested continuity', revision: 4,
    sourceBindingDigest: 'independent-static-source',
    architecture: { schemaVersion: 1, id: 'independent-collapse-architecture', label: 'Nested continuity',
      sourceDigest: 'independent-static-source', irDigest: 'independent-static-ir', entry: 'model:Independent',
      nodes: [node('root', undefined, ['input', 'block', 'output', 'spare']), node('input', 'root'),
        node('block', 'root', ['layer', 'other']), node('layer', 'block', ['first', 'second']),
        node('first', 'layer'), node('second', 'layer'), node('other', 'block'), node('output', 'root'), node('spare', 'root')],
      edges: [{ id: 'input-first', source: { nodeId: 'input', portId: 'input:out' }, target: { nodeId: 'first', portId: 'first:in' }, tensorId: 'input-tensor', role: 'data' },
        { id: 'first-second', source: { nodeId: 'first', portId: 'first:out' }, target: { nodeId: 'second', portId: 'second:in' }, tensorId: 'first-tensor', role: 'data' },
        { id: 'second-other', source: { nodeId: 'second', portId: 'second:out' }, target: { nodeId: 'other', portId: 'other:in' }, tensorId: 'second-tensor', role: 'data' },
        { id: 'other-output', source: { nodeId: 'other', portId: 'other:out' }, target: { nodeId: 'output', portId: 'output:in' }, tensorId: 'other-tensor', role: 'data' }],
      sources: [{ path: 'independent.py', content: '# Static continuity acceptance fixture; never executed.\n', digest: 'independent-source-file' }], diagnostics: [] },
    displayAliases: { block: 'My retained alias' }, nodeStyleOverrides: { first: { fill: '#abcdef' } },
    edgeStyleOverrides: { 'other-output': { width: 2 } }, legendItems: [], annotations: [],
    pageSpec: { widthMm: 180, background: '#ffffff', preset: 'monochrome' },
    expandedIds: ['root', 'block', 'layer'], layout: clone(DEEP), pinnedObjects: ['spare'],
    layoutByFrontier: { root: clone(COMPACT), 'block|layer|root': clone(DEEP),
      'block|root': { ...clone(DEEP), output: { x: 30, y: 550 } },
      // A retained schema1 record can contain an obsolete hidden-memory key.
      // It must not displace the actual visible frontier when memory changes.
      'layer|root': clone(DEEP) },
  };
  validateDocument(doc);
  return doc;
}
const toggle = (doc: CanvasDocument, id: string, expanded: boolean) => applyVisualBatch(doc, [{ type: 'expand', id, expanded }]);
function positions(doc: CanvasDocument, expected: Record<string, Position>) {
  for (const [id, point] of Object.entries(expected)) assert.deepEqual(doc.layout[id], point, `${id} local position`);
}
function sourceStable(before: CanvasDocument, after: CanvasDocument) {
  for (const key of ['id', 'title', 'sourceBindingDigest', 'architecture', 'displayAliases', 'nodeStyleOverrides', 'edgeStyleOverrides', 'legendItems', 'annotations', 'pageSpec', 'pinnedObjects'] as const) {
    assert.deepEqual(after[key], before[key], `${key} must survive visual hierarchy changes`);
  }
}
function visiblePositions(doc: CanvasDocument, expected: Record<string, { x: number; y: number }>) {
  const observed = buildScene(doc).nodes;
  assert.deepEqual(observed.map(n => n.id).sort(), Object.keys(expected).sort());
  for (const [id, point] of Object.entries(expected)) {
    const node = observed.find(n => n.id === id)!;
    assert.deepEqual({ x: node.x, y: node.y }, point, `${id} actual visible world position`);
  }
}

test('direct ancestor collapse restores compact visible frontier and retains hidden expanded children', () => {
  const before = fixture(), original = JSON.stringify(before);
  const collapsed = toggle(before, 'block', false);
  positions(collapsed, COMPACT);
  positions(collapsed, { layer: DEEP.layer, first: DEEP.first, second: DEEP.second, other: DEEP.other });
  assert.deepEqual(new Set(collapsed.expandedIds), new Set(['root', 'layer']));
  visiblePositions(collapsed, { root: { x: 50, y: 92 }, input: { x: 80, y: 154 }, block: { x: 80, y: 254 }, output: { x: 80, y: 454 }, spare: { x: 550, y: 154 } });
  sourceStable(before, collapsed);
  assert.equal(JSON.stringify(before), original, 'caller document mutated');
});

test('reopen ancestor resurrects hidden expansion and exact independently supplied deep geometry', () => {
  const before = fixture(), reopened = toggle(toggle(before, 'block', false), 'block', true);
  positions(reopened, DEEP);
  assert.deepEqual(new Set(reopened.expandedIds), new Set(['root', 'block', 'layer']));
  visiblePositions(reopened, { root: { x: 50, y: 92 }, input: { x: 80, y: 154 }, block: { x: 80, y: 254 },
    layer: { x: 110, y: 316 }, first: { x: 140, y: 378 }, second: { x: 140, y: 478 }, other: { x: 110, y: 604 },
    output: { x: 80, y: 792 }, spare: { x: 550, y: 154 } });
  sourceStable(before, reopened);
});

test('changing hidden descendant expansion memory cannot replay a stale geometry into visible siblings', () => {
  const compact = fixture(); compact.expandedIds = ['root']; compact.layout = { ...clone(DEEP), ...clone(COMPACT) };
  const expandedHidden = toggle(compact, 'layer', true);
  positions(expandedHidden, COMPACT);
  assert.deepEqual(new Set(expandedHidden.expandedIds), new Set(['root', 'layer']));
  sourceStable(compact, expandedHidden);
  const collapsedHidden = toggle(expandedHidden, 'layer', false);
  positions(collapsedHidden, COMPACT);
  assert.deepEqual(collapsedHidden.expandedIds, ['root']);
});

test('manual container and downstream moves survive compact restoration and deep reopening; unrelated pin remains exact', () => {
  const before = fixture();
  const moved = applyVisualBatch(before, [{ type: 'move', ids: ['block'], dx: 17, dy: 23 },
    { type: 'move', ids: ['output'], dx: 7, dy: 11 }, { type: 'move', ids: ['spare'], dx: 99, dy: 99 }]);
  const collapsed = toggle(moved, 'block', false);
  positions(collapsed, { ...COMPACT, block: { x: 47, y: 185 }, output: { x: 37, y: 373 } });
  const reopened = toggle(collapsed, 'block', true);
  positions(reopened, { ...DEEP, block: { x: 47, y: 185 }, output: { x: 37, y: 711 } });
  assert.deepEqual(reopened.pinnedObjects, ['spare']);
  assert.deepEqual(reopened.layout.spare, { x: 500, y: 62 });
});

test('pinned downstream position and pinned hidden leaf are protected rather than rolled back to a compact cache', () => {
  const before = applyVisualBatch(fixture(), [{ type: 'pin', ids: ['output', 'first'], pinned: true }]);
  const collapsed = toggle(before, 'block', false);
  positions(collapsed, { ...COMPACT, output: { x: 30, y: 700 }, first: { x: 30, y: 62 } });
  assert.deepEqual(collapsed.pinnedObjects, ['spare', 'output', 'first']);
  assert.deepEqual(collapsed.layout.block, { x: 30, y: 162 });
  const reopened = toggle(collapsed, 'block', true);
  positions(reopened, DEEP);
  sourceStable(before, reopened);
});

test('undo and redo restore compact/deep states, hidden memory and exact positions independently of revision', () => {
  const before = fixture();
  let h = createHistory(before);
  h = reduceHistory(h, { type: 'apply', operations: [{ type: 'expand', id: 'block', expanded: false }] });
  positions(h.document, COMPACT);
  const collapsed = clone(h.document);
  h = reduceHistory(h, { type: 'undo' });
  positions(h.document, DEEP); assert.deepEqual(new Set(h.document.expandedIds), new Set(['root', 'block', 'layer']));
  h = reduceHistory(h, { type: 'redo' });
  positions(h.document, COMPACT); assert.deepEqual(h.document.expandedIds, collapsed.expandedIds);
  assert.deepEqual(h.document.layoutByFrontier, collapsed.layoutByFrontier);
  assert.equal(h.document.revision, before.revision + 3);
});

test('JSON save/reload of collapsed canvas retains nested expansion memory and exact deep reopening', () => {
  const before = fixture(), collapsed = toggle(before, 'block', false);
  const serialized = JSON.stringify(collapsed), loaded = validateDocument(JSON.parse(serialized));
  assert.equal(JSON.stringify(loaded), serialized);
  positions(loaded, COMPACT);
  const reopened = toggle(loaded, 'block', true);
  positions(reopened, DEEP);
  assert.deepEqual(new Set(reopened.expandedIds), new Set(['root', 'block', 'layer']));
  sourceStable(before, reopened);
});

test('manual hidden-leaf memory remains exact through direct ancestor collapse, JSON reload and reopen', () => {
  const before = applyVisualBatch(fixture(), [{ type: 'move', ids: ['first'], dx: 13, dy: 17 }]);
  const collapsed = toggle(before, 'block', false);
  positions(collapsed, { ...COMPACT, first: { x: 43, y: 79 } });
  const reloaded = validateDocument(JSON.parse(JSON.stringify(collapsed)));
  const reopened = toggle(reloaded, 'block', true);
  positions(reopened, { ...DEEP, first: { x: 43, y: 79 } });
  assert.deepEqual(new Set(reopened.expandedIds), new Set(['root', 'block', 'layer']));
});

test('literal node identities containing delimiter characters do not discard latent expansion memory or visible geometry', () => {
  const before = fixture(), identities: Record<string, string> = { root: 'root|Ω', block: 'block|nested', layer: 'layer|深层' };
  const id = (value: string) => identities[value] ?? value;
  before.architecture.nodes = before.architecture.nodes.map(n => ({ ...n, id: id(n.id), ...(n.parentId ? { parentId: id(n.parentId) } : {}), children: n.children.map(id) }));
  before.architecture.edges = before.architecture.edges.map(e => ({ ...e, source: { ...e.source, nodeId: id(e.source.nodeId) }, target: { ...e.target, nodeId: id(e.target.nodeId) } }));
  const remap = (values: Record<string, Position>) => Object.fromEntries(Object.entries(values).map(([key, point]) => [id(key), clone(point)]));
  before.layout = remap(DEEP);
  before.displayAliases = { [id('block')]: 'My retained alias' };
  before.expandedIds = ['root', 'block', 'layer'].map(id);
  const fullLegacyKey = [...before.expandedIds].sort().join('|');
  before.layoutByFrontier = { [id('root')]: remap(COMPACT), [fullLegacyKey]: remap(DEEP) };
  validateDocument(before);
  const collapsed = toggle(before, id('block'), false);
  positions(collapsed, remap(COMPACT));
  assert.deepEqual(new Set(collapsed.expandedIds), new Set(['root', 'layer'].map(id)));
  const reopened = toggle(validateDocument(JSON.parse(JSON.stringify(collapsed))), id('block'), true);
  positions(reopened, remap(DEEP));
  sourceStable(before, reopened);
});

test('two different valid expanded sets with the same legacy delimiter string cannot share frontier geometry', () => {
  const before = fixture();
  const node = (id: string, parentId?: string, children: string[] = []): ArchitectureNode => ({
    id, label: id, kind: children.length ? 'Module' : 'Linear', category: children.length ? 'container' : 'linear',
    ...(parentId ? { parentId } : {}), children, ports: [], parameters: {}, evidence: 'source',
  });
  before.id = 'delimiter-collision-fixture'; before.architecture.id = 'delimiter-collision-architecture';
  before.architecture.nodes = [node('root', undefined, ['a|b', 'a', 'b', 'output']), node('a|b', 'root', ['packedChild']),
    node('a', 'root', ['aChild']), node('b', 'root', ['bChild']), node('packedChild', 'a|b'), node('aChild', 'a'), node('bChild', 'b'), node('output', 'root')];
  before.architecture.edges = []; before.displayAliases = {}; before.nodeStyleOverrides = {}; before.edgeStyleOverrides = {};
  before.pinnedObjects = []; before.expandedIds = ['root']; before.layoutByFrontier = {};
  before.layout = { root: { x: 50, y: 92 }, 'a|b': { x: 30, y: 62 }, a: { x: 330, y: 62 }, b: { x: 630, y: 62 },
    output: { x: 30, y: 262 }, packedChild: { x: 30, y: 562 }, aChild: { x: 30, y: 62 }, bChild: { x: 30, y: 62 } };
  validateDocument(before);
  const packed = toggle(before, 'a|b', true);
  assert.ok(packed.layout.output.y > 262, 'tall packed branch should require downward clearance');
  const collapsed = toggle(packed, 'a|b', false);
  assert.deepEqual(collapsed.layout.output, { x: 30, y: 262 });
  // a and b are independent parallel columns outside the output column. Their
  // short growth cannot justify replaying the tall packed branch's output gap.
  const twoBranches = toggle(toggle(collapsed, 'a', true), 'b', true);
  assert.deepEqual(new Set(twoBranches.expandedIds), new Set(['root', 'a', 'b']));
  assert.deepEqual(twoBranches.layout.output, { x: 30, y: 262 });
  assert.equal(buildScene(twoBranches).nodes.some(n => n.id === 'packedChild'), false);
  assert.equal(buildScene(twoBranches).nodes.some(n => n.id === 'aChild'), true);
  assert.equal(buildScene(twoBranches).nodes.some(n => n.id === 'bChild'), true);
});

const cnnRaw = readFileSync(new URL('before/actual-cnn-deep-rev12.json', import.meta.url));
const cnnId = (suffix: string) => `call:instance:model.ResidualCNN${suffix}`;
const CNN_COMPACT: Record<string, Position> = {
  [cnnId('')]: { x: 50, y: 92 }, 'input:model.ResidualCNN:image': { x: 30, y: 62 }, [cnnId('.stem')]: { x: 30, y: 162 },
  'repeat:instance:model.ResidualCNN.blocks': { x: 30, y: 262 }, [cnnId('.pool')]: { x: 30, y: 362 },
  [cnnId('.flatten')]: { x: 30, y: 462 }, [cnnId('.classifier')]: { x: 30, y: 562 }, 'output:model.ResidualCNN:0': { x: 30, y: 662 },
};
test('actual frozen CNN deep canvas collapses repeat directly to literal compact root positions while retaining both block memories', () => {
  const before = validateDocument(JSON.parse(cnnRaw.toString())), source = JSON.stringify(before.architecture);
  assert.equal(before.revision, 12, 'wrong actual evidence generation');
  const collapsed = toggle(before, 'repeat:instance:model.ResidualCNN.blocks', false);
  positions(collapsed, CNN_COMPACT);
  assert.deepEqual(new Set(collapsed.expandedIds), new Set([cnnId(''), cnnId('.blocks.0'), cnnId('.blocks.1')]));
  const scene = buildScene(collapsed), pool = scene.nodes.find(n => n.id === cnnId('.pool'))!, blocks = scene.nodes.find(n => n.id === 'repeat:instance:model.ResidualCNN.blocks')!;
  assert.equal(pool.y, 454); assert.equal(blocks.y, 354);
  assert.ok(pool.y - blocks.y - blocks.height <= 38, 'large post-collapse empty corridor remains');
  assert.equal(JSON.stringify(collapsed.architecture), source);
  const loaded = validateDocument(JSON.parse(JSON.stringify(collapsed)));
  const reopened = toggle(loaded, 'repeat:instance:model.ResidualCNN.blocks', true);
  positions(reopened, before.layout); // Frozen actual input invariance, not newly constructed layout.
  assert.deepEqual(new Set(reopened.expandedIds), new Set(before.expandedIds));
  assert.equal(digest(readFileSync(new URL('before/actual-cnn-deep-rev12.json', import.meta.url))), digest(cnnRaw));
});

test('actual already-bad collapsed CNN cannot overwrite its earlier compact cache before reopening and recollapsing', () => {
  const raw = readFileSync(new URL('before/actual-cnn-collapsed-rev14.json', import.meta.url));
  const before = validateDocument(JSON.parse(raw.toString()));
  assert.equal(before.revision, 14);
  assert.deepEqual(before.layout[cnnId('.pool')], { x: 30, y: 1938 }, 'wrong frozen failed browser canvas');
  // This fixture is an observed failure input; the compact literal expectation
  // comes from the independent ordered architecture and its earlier root cache.
  const reopened = toggle(before, 'repeat:instance:model.ResidualCNN.blocks', true);
  assert.deepEqual(reopened.layout[cnnId('.pool')], { x: 30, y: 1938 });
  const collapsed = toggle(reopened, 'repeat:instance:model.ResidualCNN.blocks', false);
  positions(collapsed, CNN_COMPACT);
  const serialized = JSON.stringify(collapsed), loaded = validateDocument(JSON.parse(serialized));
  positions(loaded, CNN_COMPACT);
  assert.deepEqual(new Set(loaded.expandedIds), new Set([cnnId(''), cnnId('.blocks.0'), cnnId('.blocks.1')]));
  sourceStable(before, loaded);
  assert.equal(digest(readFileSync(new URL('before/actual-cnn-collapsed-rev14.json', import.meta.url))), digest(raw));
});
