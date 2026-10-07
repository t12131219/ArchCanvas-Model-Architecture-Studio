import test from 'node:test';
import assert from 'node:assert/strict';
import { applyVisualBatch, buildScene, createHistory, reduceHistory, renderSvg, RevisionConflict, validateDocument } from '../src/core/index.ts';
import { prepareMovePreview, previewMoveScene } from '../src/core/movePreview.ts';
import { planLayoutRecovery } from '../src/core/layoutRecovery.ts';
import type { ArchitectureNode, CanvasDocument, Position, VisualOperation } from '../src/core/types.ts';

// Literal independent positions and keys. No createDocument, frontier, cache,
// auto-placement or preparation helper supplies the expected arrangements.
const COMPACT_KEY = 'visible-frontier/1:["root"]';
const DEEP_KEY = 'visible-frontier/1:["network","root"]';
const COMPACT: Record<string, Position> = { root: { x: 50, y: 92 }, input: { x: 30, y: 62 }, network: { x: 30, y: 162 },
  output: { x: 30, y: 262 }, spare: { x: 500, y: 62 } };
const DEEP: Record<string, Position> = { ...COMPACT, output: { x: 30, y: 30254 }, first: { x: 30, y: 62 }, second: { x: 30, y: 162 } };
const clone = <T>(value: T): T => structuredClone(value);
const node = (id: string, category: string, parentId?: string, children: string[] = []): ArchitectureNode => ({
  id, label: id, kind: category, category, ...(parentId ? { parentId } : {}), children, parameters: {}, evidence: 'source',
  ports: [{ id: 'in', name: 'input', direction: 'in', role: 'data', ordinal: 0 }, { id: 'out', name: 'output', direction: 'out', role: 'data', ordinal: 0 }],
});
function fixture(): CanvasDocument {
  return { schemaVersion: 1, id: 'literal-frontier-move', title: 'Independent two-frontier move', revision: 4,
    sourceBindingDigest: 'independent-frontier-source',
    architecture: { schemaVersion: 1, id: 'literal-frontier-architecture', label: 'Independent hierarchy', entry: 'model:Literal',
      sourceDigest: 'independent-frontier-source', irDigest: 'independent-frontier-ir', diagnostics: [],
      sources: [{ path: 'literal.py', content: '# Source-bound facts only; no execution.\n', digest: 'literal-source-file' }],
      nodes: [node('root', 'container', undefined, ['input', 'network', 'output', 'spare']), node('input', 'input', 'root'),
        node('network', 'container', 'root', ['first', 'second']), node('first', 'linear', 'network'),
        node('second', 'activation', 'network'), node('output', 'output', 'root'), node('spare', 'module', 'root')],
      edges: [{ id: 'entry', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'first', portId: 'in' }, tensorId: 'input-tensor', role: 'data' },
        { id: 'inside', source: { nodeId: 'first', portId: 'out' }, target: { nodeId: 'second', portId: 'in' }, tensorId: 'first-tensor', role: 'data' },
        { id: 'exit', source: { nodeId: 'second', portId: 'out' }, target: { nodeId: 'output', portId: 'in' }, tensorId: 'second-tensor', role: 'data' }] },
    displayAliases: { network: '手工网络' }, nodeStyleOverrides: { first: { fill: '#abcdef' } }, edgeStyleOverrides: { exit: { width: 2 } },
    legendItems: [], annotations: [], pageSpec: { widthMm: 180, background: '#ffffff', preset: 'paper' },
    expandedIds: ['root', 'network'], layout: clone(DEEP), layoutByFrontier: { [COMPACT_KEY]: clone(COMPACT), [DEEP_KEY]: clone(DEEP) }, pinnedObjects: ['spare'] };
}
type Scope = 'all-frontiers' | 'current-frontier';
const move = (ids: string[], dx: number, dy: number, scope?: Scope): VisualOperation => ({ type: 'move', ids, dx, dy, ...(scope ? { scope } : {}) });
const toggle = (d: CanvasDocument, expanded: boolean) => applyVisualBatch(d, [{ type: 'expand', id: 'network', expanded }]);
const at = (d: CanvasDocument, id: string) => buildScene(d).nodes.find(n => n.id === id)!;
function stable(before: CanvasDocument, after: CanvasDocument) {
  for (const field of ['id', 'title', 'sourceBindingDigest', 'architecture', 'displayAliases', 'nodeStyleOverrides', 'edgeStyleOverrides',
    'legendItems', 'annotations', 'pageSpec', 'pinnedObjects', 'expandedIds'] as const) assert.deepEqual(after[field], before[field], field);
}

test('ordinary large output move retains the existing all-frontier arithmetic', () => {
  const d = fixture(), bytes = JSON.stringify(d), next = applyVisualBatch(d, [move(['output'], 0, -28590)]);
  assert.deepEqual(next.layout.output, { x: 30, y: 1664 });
  assert.deepEqual(next.layoutByFrontier[DEEP_KEY].output, { x: 30, y: 1664 });
  assert.deepEqual(next.layoutByFrontier[COMPACT_KEY].output, { x: 30, y: -28328 });
  assert.equal(at(next, 'output').y, 1756); assert.equal(at(toggle(next, false), 'output').y, -28236);
  stable(d, next); assert.equal(JSON.stringify(d), bytes);
});
test('omitted and explicit all-frontiers scopes produce identical complete documents', () => {
  const d = fixture(), implicit = applyVisualBatch(d, [move(['output', 'output'], 13, 17)]);
  const explicit = applyVisualBatch(d, [move(['output', 'output'], 13, 17, 'all-frontiers')]);
  assert.deepEqual(explicit, implicit); assert.deepEqual(explicit.layoutByFrontier[COMPACT_KEY].output, { x: 43, y: 279 });
});
test('current deep output compaction preserves compact view and repeated toggles restore distinct exact positions', () => {
  const d = fixture(), original = JSON.stringify(d), next = applyVisualBatch(d, [move(['output'], 0, -28590, 'current-frontier')]);
  assert.deepEqual(next.layoutByFrontier[COMPACT_KEY], COMPACT); assert.deepEqual(next.layout.output, { x: 30, y: 1664 });
  assert.deepEqual(next.layoutByFrontier[DEEP_KEY], { ...DEEP, output: { x: 30, y: 1664 } });
  stable(d, next); assert.equal(JSON.stringify(d), original);
  let current = next;
  for (let i = 0; i < 3; i++) {
    current = toggle(current, false); assert.equal(at(current, 'output').y, 354);
    assert.deepEqual(current.layout.output, { x: 30, y: 262 });
    for (const id of ['root', 'input', 'network', 'spare']) assert.deepEqual(current.layout[id], COMPACT[id]);
    current = toggle(current, true); assert.equal(at(current, 'output').y, 1756);
    assert.deepEqual(current.layout.output, { x: 30, y: 1664 });
    assert.deepEqual(current.layout.first, DEEP.first); assert.deepEqual(current.layout.second, DEEP.second);
  }
});
test('four current-frontier directions and duplicate IDs change only the literal current object/cache', () => {
  for (const [dx, dy, x, y] of [[-24, 0, 6, 30254], [24, 0, 54, 30254], [0, -24, 30, 30230], [0, 24, 30, 30278]]) {
    const d = fixture(), next = applyVisualBatch(d, [move(['output', 'output'], dx, dy, 'current-frontier')]);
    assert.deepEqual(next.layout.output, { x, y }); assert.deepEqual(next.layoutByFrontier[DEEP_KEY].output, { x, y });
    assert.deepEqual(next.layoutByFrontier[COMPACT_KEY], COMPACT);
    for (const id of ['root', 'input', 'network', 'first', 'second', 'spare']) {
      assert.deepEqual(next.layout[id], DEEP[id]); assert.deepEqual(next.layoutByFrontier[DEEP_KEY][id], DEEP[id]);
    }
    stable(d, next); assert.equal(next.revision, 5);
  }
});
test('a later ordinary move still applies one delta to both differently edited saved frontiers', () => {
  const scoped = applyVisualBatch(fixture(), [move(['output'], 0, -28590, 'current-frontier')]);
  const next = applyVisualBatch(scoped, [move(['output'], 7, 11)]);
  assert.deepEqual(next.layoutByFrontier[COMPACT_KEY].output, { x: 37, y: 273 });
  assert.deepEqual(next.layoutByFrontier[DEEP_KEY].output, { x: 37, y: 1675 });
  assert.deepEqual(next.layout.output, { x: 37, y: 1675 });
});
test('missing or legacy-only current cache establishes canonical visible cache without altering old bytes', () => {
  for (const legacy of [false, true]) {
    const d = fixture(); d.layoutByFrontier = legacy ? { root: clone(COMPACT), 'network|root': clone(DEEP) } : {};
    const originalCaches = clone(d.layoutByFrontier), next = applyVisualBatch(d, [move(['output'], 13, 17, 'current-frontier')]);
    assert.deepEqual(next.layoutByFrontier[DEEP_KEY], { ...DEEP, output: { x: 43, y: 30271 } });
    for (const [key, value] of Object.entries(originalCaches)) assert.deepEqual(next.layoutByFrontier[key], value);
    assert.deepEqual(Object.keys(next.layoutByFrontier).sort(), [...Object.keys(originalCaches), DEEP_KEY].sort());
    if (legacy) assert.deepEqual(toggle(toggle(next, false), true).layout.output, { x: 43, y: 30271 });
  }
});
test('effective compact frontier ignores retained hidden layer flags and preserves deep cache', () => {
  const d = fixture(); d.architecture.nodes.find(n => n.id === 'network')!.children = ['layer'];
  d.architecture.nodes.push(node('layer', 'container', 'network', ['first', 'second']));
  for (const id of ['first', 'second']) d.architecture.nodes.find(n => n.id === id)!.parentId = 'layer';
  const nested = { ...DEEP, layer: { x: 30, y: 62 } };
  d.expandedIds = ['root', 'layer']; d.layout = { ...clone(nested), ...clone(COMPACT) };
  d.layoutByFrontier = { [COMPACT_KEY]: clone(COMPACT), 'visible-frontier/1:["layer","network","root"]': clone(nested),
    'layer|root': { ...clone(COMPACT), output: { x: 30, y: 987 } } };
  const beforeCaches = clone(d.layoutByFrontier), next = applyVisualBatch(d, [move(['output'], 9, 11, 'current-frontier')]);
  assert.deepEqual(next.layout.output, { x: 39, y: 273 }); assert.deepEqual(next.expandedIds, ['root', 'layer']);
  assert.deepEqual(next.layoutByFrontier[COMPACT_KEY], { ...COMPACT, output: { x: 39, y: 273 } });
  for (const key of ['visible-frontier/1:["layer","network","root"]', 'layer|root']) assert.deepEqual(next.layoutByFrontier[key], beforeCaches[key]);
  assert.deepEqual(toggle(next, true).layout.output, { x: 30, y: 30254 });
});
test('ambiguous delimiter cache remains intact while explicit current edit creates its literal canonical key', () => {
  const d = fixture();
  d.architecture.nodes.find(n => n.id === 'root')!.children = ['input', 'a', 'b', 'a|b', 'output', 'spare'];
  d.architecture.nodes.find(n => n.id === 'network')!.id = 'a|b';
  for (const id of ['first', 'second']) d.architecture.nodes.find(n => n.id === id)!.parentId = 'a|b';
  d.architecture.nodes.push(node('a', 'container', 'root', ['a-leaf']), node('b', 'container', 'root', ['b-leaf']),
    node('a-leaf', 'linear', 'a'), node('b-leaf', 'linear', 'b'));
  d.displayAliases = { 'a|b': 'Literal delimiter branch' }; d.expandedIds = ['root', 'a|b'];
  delete d.layout.network; Object.assign(d.layout, { 'a|b': { x: 30, y: 162 }, a: { x: 300, y: 162 }, b: { x: 600, y: 162 } });
  const ambiguous = { ...clone(d.layout), output: { x: 30, y: 777 } };
  d.layoutByFrontier = { 'a|b|root': clone(ambiguous) };
  const next = applyVisualBatch(d, [move(['output'], 0, 8, 'current-frontier')]);
  assert.deepEqual(next.layoutByFrontier['a|b|root'], ambiguous);
  assert.deepEqual(next.layoutByFrontier['visible-frontier/1:["a|b","root"]'], { ...d.layout, output: { x: 30, y: 30262 } });
  assert.deepEqual(Object.keys(next.layoutByFrontier).sort(), ['a|b|root', 'visible-frontier/1:["a|b","root"]'].sort());
});
test('selected parent and child translate once; selected pins and pinned descendants retain protection', () => {
  const d = fixture(), next = applyVisualBatch(d, [move(['network', 'first', 'first'], 17, 23, 'current-frontier')]);
  assert.deepEqual(next.layout.network, { x: 47, y: 185 }); assert.deepEqual(next.layout.first, { x: 30, y: 62 });
  assert.equal(at(next, 'first').x, 127); assert.equal(at(next, 'first').y, 339);
  assert.deepEqual(next.layoutByFrontier[COMPACT_KEY], COMPACT);
  for (const pinned of [['network'], ['first']]) {
    const protectedDoc = fixture(); protectedDoc.pinnedObjects.push(...pinned);
    const moved = applyVisualBatch(protectedDoc, [move(['network', 'first'], 17, 23, 'current-frontier')]);
    assert.deepEqual(moved.layout, protectedDoc.layout); assert.deepEqual(moved.layoutByFrontier, protectedDoc.layoutByFrontier);
  }
});
test('current hidden selection is rejected atomically while default established-hidden-layout behavior survives', () => {
  const d = fixture(); d.expandedIds = ['root']; d.layout = { ...clone(DEEP), ...clone(COMPACT) }; const original = JSON.stringify(d);
  assert.throws(() => applyVisualBatch(d, [move(['output'], 1, 2, 'current-frontier'), move(['first'], 4, 5, 'current-frontier')]), /visible|hidden/i);
  assert.throws(() => prepareMovePreview(d, ['first'], 'current-frontier'), /visible|hidden/i);
  assert.equal(JSON.stringify(d), original);
  assert.deepEqual(applyVisualBatch(d, [move(['first'], 4, 5)]).layout.first, { x: 34, y: 67 });
});
test('intentional negative manual positions are neither clamped nor migrated to other frontiers', () => {
  const d = fixture(), next = applyVisualBatch(d, [move(['output'], -130, -30400, 'current-frontier')]);
  assert.deepEqual(next.layout.output, { x: -100, y: -146 }); assert.deepEqual(next.layoutByFrontier[COMPACT_KEY], COMPACT);
  assert.equal(at(next, 'output').x, -50); assert.equal(at(next, 'output').y, -54); validateDocument(next);
});
test('one scoped history entry supports exact cache undo/redo and rejects stale revisions', () => {
  const d = fixture(), h = createHistory(d), op = move(['output'], 0, -28590, 'current-frontier');
  const applied = reduceHistory(h, { type: 'apply', operations: [op], baseRevision: 4 });
  assert.equal(applied.past.length, 1); assert.equal(applied.document.revision, 5);
  const undo = reduceHistory(applied, { type: 'undo' }), redo = reduceHistory(undo, { type: 'redo' });
  assert.deepEqual(undo.document.layout, DEEP); assert.deepEqual(undo.document.layoutByFrontier, d.layoutByFrontier);
  assert.deepEqual(redo.document.layout, applied.document.layout); assert.deepEqual(redo.document.layoutByFrontier, applied.document.layoutByFrontier);
  const original = JSON.stringify(applied); assert.throws(() => reduceHistory(applied, { type: 'apply', operations: [op], baseRevision: 4 }), RevisionConflict);
  assert.equal(JSON.stringify(applied), original);
});
test('JSON reload preserves distinct current-edited and compact positions with full model/source facts', () => {
  const next = applyVisualBatch(fixture(), [move(['output'], 0, -28590, 'current-frontier')]);
  const collapsed = toggle(next, false), bytes = JSON.stringify(collapsed), loaded = validateDocument(JSON.parse(bytes));
  assert.equal(JSON.stringify(loaded), bytes); assert.equal(at(loaded, 'output').y, 354);
  const reopened = toggle(loaded, true); assert.equal(at(reopened, 'output').y, 1756);
  assert.deepEqual(reopened.architecture, next.architecture); assert.deepEqual(reopened.pinnedObjects, ['spare']);
});
test('preview scope is frozen and complete scene/SVG equals corresponding real commit without document mutation', () => {
  for (const scope of ['all-frontiers', 'current-frontier'] as const) {
    const d = fixture(), bytes = JSON.stringify(d), session = prepareMovePreview(d, ['output'], scope);
    assert.equal(session.scope, scope); assert.equal(Object.isFrozen(session), true);
    assert.throws(() => { (session as { scope: string }).scope = 'changed'; }, TypeError);
    for (const [dx, dy] of [[24, 0], [-24, 0], [0, 24], [0, -28590]]) {
      const preview = previewMoveScene(session, dx, dy), committed = buildScene(applyVisualBatch(d, [move(['output'], dx, dy, scope)]));
      assert.deepEqual(preview, committed); assert.equal(renderSvg(preview, { interactive: true }), renderSvg(committed, { interactive: true }));
    }
    assert.equal(JSON.stringify(d), bytes);
  }
  assert.equal(prepareMovePreview(fixture(), ['output']).scope, 'all-frontiers');
});
test('unknown scopes are rejected by move and preview before any document mutation', () => {
  const d = fixture(), bytes = JSON.stringify(d);
  assert.throws(() => applyVisualBatch(d, [{ type: 'move', ids: ['output'], dx: 1, dy: 2, scope: 'invented' } as never]), /scope/);
  assert.throws(() => prepareMovePreview(d, ['output'], 'invented' as never), /scope/);
  assert.equal(JSON.stringify(d), bytes);
});
test('editing already malformed revision5 with current scope does not silently migrate its other cache', () => {
  const d = fixture(); d.revision = 5; d.layout.output = { x: 30, y: 1664 };
  d.layoutByFrontier[DEEP_KEY].output = { x: 30, y: 1664 }; d.layoutByFrontier[COMPACT_KEY].output = { x: 30, y: -28328 };
  const next = applyVisualBatch(d, [move(['output'], 3, 4, 'current-frontier')]);
  assert.deepEqual(next.layoutByFrontier[COMPACT_KEY].output, { x: 30, y: -28328 });
  assert.deepEqual(next.layout.output, { x: 33, y: 1668 }); assert.equal(next.revision, 6);
});
test('scoped recovery preserves the other frontier and proposed scene equals committed active scene', () => {
  const d = fixture(), moved = applyVisualBatch(d, [move(['first'], -52, 0, 'current-frontier')]), bytes = JSON.stringify(moved);
  const plan = planLayoutRecovery(moved, 'first', 'current-frontier'); assert.equal(plan.status, 'ready');
  if (plan.status !== 'ready') assert.fail('Expected literal left-boundary recovery');
  assert.equal(plan.operation.scope, 'current-frontier'); assert.deepEqual(plan.operation.ids, ['first']);
  const next = applyVisualBatch(moved, [plan.operation]); assert.deepEqual(next.layoutByFrontier[COMPACT_KEY], COMPACT);
  assert.deepEqual(next.layout.first, { x: 30, y: 62 }); assert.deepEqual(buildScene(next), plan.scene);
  assert.equal(renderSvg(buildScene(next)), renderSvg(plan.scene)); assert.equal(JSON.stringify(moved), bytes);
  const defaultPlan = planLayoutRecovery(moved, 'first'); assert.equal(defaultPlan.status, 'ready');
  if (defaultPlan.status !== 'ready') assert.fail('Expected default recovery');
  assert.equal(Object.hasOwn(defaultPlan.operation, 'scope'), false, 'default recovery operation retains its old shape');
});
test('recovery validates unknown scope even on unneeded or unavailable early return paths', () => {
  const d = fixture(), bytes = JSON.stringify(d);
  assert.throws(() => planLayoutRecovery(d, 'output', 'invented' as never), /scope/);
  assert.throws(() => planLayoutRecovery(d, 'missing-id', 'invented' as never), /scope/);
  assert.throws(() => planLayoutRecovery(d, 'spare', 'invented' as never), /scope/);
  assert.equal(JSON.stringify(d), bytes);
});
