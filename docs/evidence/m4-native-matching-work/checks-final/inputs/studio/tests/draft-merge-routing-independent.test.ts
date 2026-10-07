import test from 'node:test';
import assert from 'node:assert/strict';
import { blankDraft, changeDraft, draftHistory, draftRoutes, parseDraftCache, travelDraft } from '../src/authoring.ts';
import type { AuthoredDraft, DraftCatalog, DraftEdge, DraftFlow, DraftNode } from '../src/authoring.ts';

// Independent acceptance geometry: the published draft card is 176 x 100.
// These fixtures and sensors do not call the product's path, port, collision,
// flow-selection, refinement, or scoring helpers as their expected values.
const catalog: DraftCatalog = { schemaVersion: 1, mode: 'authored-draft', unsupported: [], modules: [
  { kind: 'Input', label: 'Input', category: 'io', description: '', defaults: { shape: [1, 16] }, parameters: [], ports: [{ id: 'output', name: 'output', direction: 'out', type: 'tensor' }] },
  { kind: 'Output', label: 'Output', category: 'io', description: '', defaults: {}, parameters: [], ports: [{ id: 'input', name: 'input', direction: 'in', type: 'tensor' }] },
  { kind: 'Identity', label: 'Identity', category: 'operator', description: '', defaults: {}, parameters: [], ports: [{ id: 'input', name: 'input', direction: 'in', type: 'tensor' }, { id: 'output', name: 'output', direction: 'out', type: 'tensor' }] },
  { kind: 'Add', label: 'Add', category: 'operator', description: '', defaults: {}, parameters: [], ports: [{ id: 'left', name: 'left', direction: 'in', type: 'tensor' }, { id: 'right', name: 'right', direction: 'in', type: 'tensor' }, { id: 'output', name: 'output', direction: 'out', type: 'tensor' }] },
  { kind: 'Concat', label: 'Concat', category: 'operator', description: '', defaults: { dim: 1 }, parameters: [], ports: [{ id: 'a', name: 'a', direction: 'in', type: 'tensor' }, { id: 'b', name: 'b', direction: 'in', type: 'tensor' }, { id: 'output', name: 'output', direction: 'out', type: 'tensor' }] },
] };
type Point = { x: number; y: number };
type Segment = { a: Point; b: Point };
type Intersection = { kind: 'contact' | 'overlap'; x: number; y: number; length: number };
const EPS = .025;
const near = (a: number, b: number) => Math.abs(a - b) < EPS;
const samePoint = (a: Point, b: Point) => near(a.x, b.x) && near(a.y, b.y);
const between = (p: number, a: number, b: number) => p >= Math.min(a, b) - EPS && p <= Math.max(a, b) + EPS;
function decode(path: string): Point[] {
  const tokens = path.match(/[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?/g) ?? [];
  const result: Point[] = [];
  for (let index = 0; index < tokens.length;) {
    const command = tokens[index++], prior = result.at(-1); let point: Point;
    if (command === 'M' || command === 'L') point = { x: Number(tokens[index++]), y: Number(tokens[index++]) };
    else if (command === 'H' && prior) point = { x: Number(tokens[index++]), y: prior.y };
    else if (command === 'V' && prior) point = { x: prior.x, y: Number(tokens[index++]) };
    else throw new Error(`Unsupported route command: ${command}`);
    assert.ok(Number.isFinite(point.x) && Number.isFinite(point.y), 'finite route coordinates');
    assert.ok(!prior || prior.x !== point.x || prior.y !== point.y, 'no exactly zero-length segment'); result.push(point);
  }
  assert.ok(result.length >= 2, 'a complete polyline');
  return result;
}
const segments = (points: Point[]): Segment[] => points.slice(1).map((b, index) => ({ a: points[index], b }));
function intersect(first: Segment, second: Segment): Intersection | undefined {
  const av = near(first.a.x, first.b.x), bv = near(second.a.x, second.b.x);
  if (av !== bv) {
    const v = av ? first : second, h = av ? second : first;
    return between(v.a.x, h.a.x, h.b.x) && between(h.a.y, v.a.y, v.b.y)
      ? { kind: 'contact', x: v.a.x, y: h.a.y, length: 0 } : undefined;
  }
  if (!near(av ? first.a.x : first.a.y, bv ? second.a.x : second.a.y)) return;
  const low = Math.max(Math.min(av ? first.a.y : first.a.x, av ? first.b.y : first.b.x), Math.min(bv ? second.a.y : second.a.x, bv ? second.b.y : second.b.x));
  const high = Math.min(Math.max(av ? first.a.y : first.a.x, av ? first.b.y : first.b.x), Math.max(bv ? second.a.y : second.a.x, bv ? second.b.y : second.b.x));
  if (high < low - EPS) return;
  return { kind: high - low > EPS ? 'overlap' : 'contact', x: av ? first.a.x : low, y: av ? low : first.a.y, length: Math.max(0, high - low) };
}
function bodyHits(segment: Segment, node: DraftNode) {
  const { x, y } = node.position, vertical = near(segment.a.x, segment.b.x);
  assert.ok(vertical || near(segment.a.y, segment.b.y), 'axis-aligned segment');
  if (vertical) return segment.a.x > x + EPS && segment.a.x < x + 176 - EPS &&
    Math.max(Math.min(segment.a.y, segment.b.y), y + EPS) < Math.min(Math.max(segment.a.y, segment.b.y), y + 100 - EPS);
  return segment.a.y > y + EPS && segment.a.y < y + 100 - EPS &&
    Math.max(Math.min(segment.a.x, segment.b.x), x + EPS) < Math.min(Math.max(segment.a.x, segment.b.x), x + 176 - EPS);
}
function anchor(node: DraftNode, port: string, flow: DraftFlow): Point {
  const output = port === 'output', doubleInput = node.kind === 'Add' || node.kind === 'Concat';
  const second = port === 'right' || port === 'b';
  // These values come from the independently frozen card/ordered-port contract.
  if (flow === 'horizontal') return { x: node.position.x + (output ? 176 : 0), y: node.position.y + (!output && doubleInput ? second ? 72 : 60 : 66) };
  return { x: node.position.x + (!output && doubleInput ? second ? 352 / 3 : 176 / 3 : 88), y: node.position.y + (output ? 100 : 0) };
}
function makeDraft(id: string, nodes: [string, string, number, number][], edges: [string, string, string, string][]): AuthoredDraft {
  const draft = blankDraft(id); draft.title = 'Independent fixed-port routing';
  draft.nodes = nodes.map(([nodeId, kind, x, y]) => ({ id: nodeId, kind, label: nodeId, parameters: structuredClone(catalog.modules.find(module => module.kind === kind)!.defaults), position: { x, y } }));
  draft.edges = edges.map(([edgeId, sourceId, targetId, port]) => ({ id: edgeId, source: { nodeId: sourceId, portId: 'output' }, target: { nodeId: targetId, portId: port } }));
  return draft;
}
const mergeBindings: [string, string, string, string][] = [
  ['a-left', 'a', 'add', 'left'], ['b-right', 'b', 'add', 'right'], ['add-a', 'add', 'concat', 'a'], ['a-b', 'a', 'concat', 'b'], ['concat-out', 'concat', 'out', 'input'],
];
function actualMerge() { return makeDraft('draft-independent-merge', [
  ['a', 'Input', 50, 80], ['b', 'Input', 50, 250], ['add', 'Add', 350, 160], ['concat', 'Concat', 620, 160], ['out', 'Output', 890, 160],
], mergeBindings); }
function verticalMerge() { return makeDraft('draft-independent-vertical', [
  ['a', 'Input', 50, 50], ['b', 'Input', 300, 50], ['add', 'Add', 160, 250], ['concat', 'Concat', 160, 460], ['out', 'Output', 160, 680],
], mergeBindings); }
function pureRoutes(draft: AuthoredDraft, flow: DraftFlow) {
  const bytes = JSON.stringify(draft), result = draftRoutes(draft, catalog), decoded = new Map<string, Point[]>();
  assert.equal(JSON.stringify(draft), bytes, 'routing must preserve every draft byte including positions, schema, facts and revision');
  assert.equal(result.routes.length, draft.edges.length, 'every binding has a retained route');
  assert.equal(new Set(result.routes.map(route => route.id)).size, draft.edges.length, 'branch IDs remain distinct');
  for (const edge of draft.edges) {
    const route = result.routes.find(item => item.id === edge.id); assert.ok(route, edge.id);
    const points = decode(route.path), source = draft.nodes.find(node => node.id === edge.source.nodeId)!, target = draft.nodes.find(node => node.id === edge.target.nodeId)!;
    assert.ok(samePoint(points[0], anchor(source, edge.source.portId, flow)), `exact source anchor ${edge.id}`);
    assert.ok(samePoint(points.at(-1)!, anchor(target, edge.target.portId, flow)), `exact ordered target anchor ${edge.id}`);
    const first = points[1], start = points[0], last = points.at(-1)!, prior = points.at(-2)!;
    assert.ok(flow === 'horizontal' ? near(start.y, first.y) && first.x > start.x : near(start.x, first.x) && first.y > start.y, `outward source normal ${edge.id}`);
    assert.ok(flow === 'horizontal' ? near(last.y, prior.y) && last.x > prior.x : near(last.x, prior.x) && last.y > prior.y, `inward target normal ${edge.id}`);
    for (let index = 1; index < points.length - 1; index++) {
      const a = points[index - 1], b = points[index], c = points[index + 1];
      assert.ok((b.x - a.x) * (c.x - b.x) + (b.y - a.y) * (c.y - b.y) >= -EPS, `no immediate retracing ${edge.id}`);
    }
    const hitIds = draft.nodes.filter(node => segments(points).some(segment => bodyHits(segment, node))).map(node => node.id);
    assert.deepEqual(hitIds, [], `no source, target, or unrelated body penetration ${edge.id}`);
    assert.deepEqual(route.blockedBy, [], `no hidden obstruction ${edge.id}`); decoded.set(edge.id, points);
  }
  assert.deepEqual(result.overlaps, [], 'fixtures intentionally have nonoverlapping cards');
  return decoded;
}
function differentProducerConflicts(draft: AuthoredDraft, paths: Map<string, Point[]>) {
  const conflicts: { first: string; second: string; intersection: Intersection }[] = [];
  for (let i = 0; i < draft.edges.length; i++) for (let j = i + 1; j < draft.edges.length; j++) {
    const a = draft.edges[i], b = draft.edges[j];
    if (a.source.nodeId === b.source.nodeId && a.source.portId === b.source.portId) continue;
    for (const first of segments(paths.get(a.id)!)) for (const second of segments(paths.get(b.id)!)) {
      const intersection = intersect(first, second); if (intersection) conflicts.push({ first: a.id, second: b.id, intersection });
    }
  }
  return conflicts;
}
function assertClear(draft: AuthoredDraft, flow: DraftFlow) {
  const paths = pureRoutes(draft, flow);
  assert.deepEqual(differentProducerConflicts(draft, paths), [], 'different producers may not cross, touch at an intermediate vertex, or overlap');
  return paths;
}
const facts = (draft: AuthoredDraft) => ({ schemaVersion: draft.schemaVersion, mode: draft.mode, id: draft.id, title: draft.title, edges: draft.edges, nodes: draft.nodes.map(({ position, ...node }) => node) });

test('independent sensor rejects interior/vertex crossings and positive overlaps, while separated or point-only collinear contacts differ', () => {
  const line = (x1: number, y1: number, x2: number, y2: number): Segment => ({ a: { x: x1, y: y1 }, b: { x: x2, y: y2 } });
  assert.equal(intersect(line(0, 5, 10, 5), line(5, 0, 5, 10))?.kind, 'contact');
  assert.equal(intersect(line(0, 5, 5, 5), line(5, 5, 5, 10))?.kind, 'contact', 'bend-vertex touch must not evade the sensor');
  assert.equal(intersect(line(0, 5, 10, 5), line(4, 5, 12, 5))?.length, 6);
  assert.equal(intersect(line(0, 5, 4, 5), line(4, 5, 12, 5))?.kind, 'contact');
  assert.equal(intersect(line(0, 5, 4, 5), line(5, 5, 12, 5)), undefined);
  assert.equal(intersect(line(0, 5, 10, 5), line(0, 6, 10, 6)), undefined);
  const draft = actualMerge(), fake = new Map(draft.edges.map(edge => [edge.id, [{ x: 1, y: 1 }, { x: 5, y: 1 }]]));
  assert.ok(differentProducerConflicts(draft, fake).some(conflict => conflict.first === 'a-left' && conflict.second === 'b-right'));
  assert.ok(!differentProducerConflicts(draft, fake).some(conflict => conflict.first === 'a-left' && conflict.second === 'a-b'), 'shared source-port trunk is allowed, independently of route metadata');
});

test('actual five-binding merge keeps every endpoint, outward/inward normal, and card body clear', () => {
  const draft = actualMerge();
  assert.deepEqual(draft.edges.map(edge => [edge.id, edge.source.nodeId, edge.source.portId, edge.target.nodeId, edge.target.portId]), [
    ['a-left', 'a', 'output', 'add', 'left'], ['b-right', 'b', 'output', 'add', 'right'], ['add-a', 'add', 'output', 'concat', 'a'], ['a-b', 'a', 'output', 'concat', 'b'], ['concat-out', 'concat', 'output', 'out', 'input'],
  ]); pureRoutes(draft, 'horizontal');
});

test('actual merge removes the different-producer crossing and Concat inlet overlay without changing the five bindings', () => {
  assertClear(actualMerge(), 'horizontal');
});

test('same-source fanout keeps two complete branch IDs and separately ordered destination ports', () => {
  const draft = actualMerge(), paths = pureRoutes(draft, 'horizontal');
  const first = paths.get('a-left')!, second = paths.get('a-b')!;
  assert.ok(samePoint(first[0], { x: 226, y: 146 })); assert.ok(samePoint(first[0], second[0]));
  assert.ok(samePoint(first.at(-1)!, { x: 350, y: 220 })); assert.ok(samePoint(second.at(-1)!, { x: 620, y: 232 }));
  assert.notDeepEqual(first, second, 'a shared trunk never substitutes one edge for another');
  assert.equal(draft.edges.filter(edge => edge.source.nodeId === 'a').length, 2);
});

test('four-direction merge moves, undo/redo and JSON reopen reproduce stable routes and preserve semantic facts', () => {
  const initial = actualMerge(), original = JSON.stringify(initial), initialPaths = assertClear(initial, 'horizontal');
  for (const [dx, dy] of [[-16, 0], [16, 0], [0, -16], [0, 16]]) {
    const history = draftHistory(initial), historyBytes = JSON.stringify(history);
    const changed = changeDraft(history, draft => { const node = draft.nodes.find(item => item.id === 'add')!; node.position.x += dx; node.position.y += dy; });
    assert.equal(JSON.stringify(history), historyBytes); assert.equal(changed.past.length, 1); assert.equal(changed.draft.revision, 1);
    assert.deepEqual(facts(changed.draft), facts(initial));
    assert.deepEqual(changed.draft.nodes.find(node => node.id === 'add')!.position, { x: 350 + dx, y: 160 + dy });
    for (const id of ['a', 'b', 'concat', 'out']) assert.deepEqual(changed.draft.nodes.find(node => node.id === id), initial.nodes.find(node => node.id === id));
    const movedPaths = assertClear(changed.draft, 'horizontal');
    const undo = travelDraft(changed, 'undo'), redo = travelDraft(undo, 'redo');
    assert.deepEqual(undo.draft.nodes, initial.nodes); assert.deepEqual(redo.draft.nodes, changed.draft.nodes);
    assert.equal(undo.draft.revision, 2); assert.equal(redo.draft.revision, 3);
    assert.deepEqual(assertClear(undo.draft, 'horizontal'), initialPaths); assert.deepEqual(assertClear(redo.draft, 'horizontal'), movedPaths);
    const envelope = JSON.parse(JSON.stringify({ draft: redo.draft, storageRevision: 2, savedRevision: redo.draft.revision }));
    const reopened = parseDraftCache(envelope); assert.ok(reopened); assert.deepEqual(reopened.draft, redo.draft);
    assert.deepEqual(assertClear(reopened.draft, 'horizontal'), movedPaths);
    assert.deepEqual(draftRoutes(reopened.draft, catalog), draftRoutes(reopened.draft, catalog), 'deterministic repeated evaluation');
  }
  assert.equal(JSON.stringify(initial), original);
});

test('aligned horizontal and vertical chains retain their minimum straight paths', () => {
  for (const flow of ['horizontal', 'vertical'] as const) {
    const nodes: [string, string, number, number][] = flow === 'horizontal'
      ? [['in', 'Input', 50, 70], ['mid', 'Identity', 320, 70], ['out', 'Output', 590, 70]]
      : [['in', 'Input', 50, 70], ['mid', 'Identity', 50, 224], ['out', 'Output', 50, 378]];
    const draft = makeDraft(`draft-independent-straight-${flow}`, nodes, [['one', 'in', 'mid', 'input'], ['two', 'mid', 'out', 'input']]);
    for (const points of assertClear(draft, flow).values()) assert.equal(points.length, 2, 'no gratuitous bends in an unobstructed aligned chain');
  }
});

test('an unrelated intervening card is avoided without moving it or hiding either independently produced route', () => {
  const draft = makeDraft('draft-independent-obstacle', [
    ['a', 'Input', 50, 80], ['a-out', 'Output', 810, 80], ['b', 'Input', 50, 310], ['b-out', 'Output', 810, 310], ['obstacle', 'Identity', 410, 80],
  ], [['a-edge', 'a', 'a-out', 'input'], ['b-edge', 'b', 'b-out', 'input']]);
  const points = assertClear(draft, 'horizontal'); assert.ok(points.get('a-edge')!.length > 2, 'the body blocks the direct corridor');
  assert.deepEqual(points.get('b-edge'), [{ x: 226, y: 376 }, { x: 810, y: 376 }]);
});

test('reverse-directed independent bindings route outside their own cards and an intervening body with correct normals', () => {
  const draft = makeDraft('draft-independent-reverse', [
    ['a', 'Input', 720, 80], ['a-out', 'Output', 50, 300], ['b', 'Input', 720, 340], ['b-out', 'Output', 50, 560], ['obstacle', 'Identity', 370, 220],
  ], [['a-edge', 'a', 'a-out', 'input'], ['b-edge', 'b', 'b-out', 'input']]);
  const points = assertClear(draft, 'horizontal');
  for (const edge of draft.edges) assert.ok(points.get(edge.id)!.length >= 4, 'reversed endpoints require an external detour');
});

test('a vertical multi-input merge preserves left/right and a/b slot ordering while avoiding every different-producer contact', () => {
  assertClear(verticalMerge(), 'vertical');
});

test('a real forward multi-input merge with an extra obstacle retains full facts and clear branch geometry', () => {
  const draft = actualMerge(); draft.nodes.push({ id: 'lower-obstacle', kind: 'Identity', label: 'lower obstacle', parameters: {}, position: { x: 430, y: 290 } });
  assertClear(draft, 'horizontal');
});

test('a larger draft keeps all bindings, card positions and ordered anchors when global crossing removal is best effort', () => {
  const draft = actualMerge();
  for (let index = 0; index < 20; index++) draft.nodes.push({ id: `remote-${index}`, kind: 'Identity', label: `remote-${index}`, parameters: {}, position: { x: 1800, y: 40 + index * 150 } });
  assert.equal(draft.nodes.length, 25);
  const original = JSON.stringify(draft), paths = pureRoutes(draft, 'horizontal');
  assert.equal(paths.size, 5); assert.equal(JSON.stringify(draft), original);
  assert.deepEqual([...paths.keys()], ['a-left', 'b-right', 'add-a', 'a-b', 'concat-out']);
  // The fixed graph is kept visible even when the bounded global refinement
  // does not run or cannot find a solution. We neither require a crossing nor
  // claim a crossing-free result from this scope-boundary fixture.
  for (const contact of differentProducerConflicts(draft, paths)) {
    assert.ok(paths.has(contact.first) && paths.has(contact.second), 'every unresolved contact still has both visible branch identities');
  }
});
