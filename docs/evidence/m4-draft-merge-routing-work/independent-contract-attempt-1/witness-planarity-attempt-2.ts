import test from 'node:test';
import assert from 'node:assert/strict';
import { blankDraft, changeDraft, draftHistory, draftRoutes, parseDraftCache, travelDraft } from './before/studio/src/authoring.ts';
import type { AuthoredDraft, DraftCatalog, DraftEdge, DraftFlow, DraftNode } from './before/studio/src/authoring.ts';

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


const witnessCases = [
  { name: 'actual-horizontal-fixed-port', draft: actualMerge(), flow: 'horizontal' as const, polylines: {
    'a-left': 'M226146 H288 V220 H350',
    'b-right': 'M226316 H288 V232 H350',
    'add-a': 'M526226 H573 V220 H620',
    'a-b': 'M226146 H240 V186 H44 V370 H608 V232 H620',
    'concat-out': 'M796226 H890',
  } },
  { name: 'vertical-fixed-ordered-port', draft: verticalMerge(), flow: 'vertical' as const, polylines: {
    'a-left': 'M138150 V200 H218.66666666666666 V250',
    'b-right': 'M388150 V200 H277.3333333333333 V250',
    'add-a': 'M248350 V400 H218.66666666666666 V460',
    'a-b': 'M138150 V156 H44 V20 H490 V430 H277.3333333333333 V460',
    'concat-out': 'M248560 V680',
  } },
];
const result = witnessCases.map(item => {
  // Expand compact human notation with unambiguous M x y separators.
  const paths = new Map(Object.entries(item.polylines).map(([id, path]) => [id, decode(path.replace(/M(\d{3})(\d{3})/, 'M $1 $2'))]));
  const bodyPenetrations: string[] = [];
  for (const edge of item.draft.edges) {
    const points = paths.get(edge.id)!;
    const source = item.draft.nodes.find(node => node.id === edge.source.nodeId)!;
    const target = item.draft.nodes.find(node => node.id === edge.target.nodeId)!;
    assert.ok(samePoint(points[0], anchor(source, edge.source.portId, item.flow)), edge.id);
    assert.ok(samePoint(points.at(-1)!, anchor(target, edge.target.portId, item.flow)), edge.id);
    const start = points[0], first = points[1], last = points.at(-1)!, prior = points.at(-2)!;
    assert.ok(item.flow === 'horizontal' ? near(start.y, first.y) && first.x > start.x : near(start.x, first.x) && first.y > start.y);
    assert.ok(item.flow === 'horizontal' ? near(last.y, prior.y) && last.x > prior.x : near(last.x, prior.x) && last.y > prior.y);
    for (const node of item.draft.nodes) if (segments(points).some(segment => bodyHits(segment, node))) bodyPenetrations.push(`${edge.id}:${node.id}`);
  }
  const conflicts = differentProducerConflicts(item.draft, paths);
  assert.deepEqual(bodyPenetrations, []); assert.deepEqual(conflicts, []);
  return { name: item.name, bodyPenetrations, differentProducerConflicts: conflicts, nodes: item.draft.nodes, edges: item.draft.edges, pointsByEdge: Object.fromEntries(paths) };
});
console.log(JSON.stringify({ protocol: 'archcanvas-independent-planar-witness/1', basis: 'Hand-drawn existence witnesses. No product routing output, helpers or model facts are altered. Polylines are not prescribed output assertions; multiple clear solutions may satisfy the tests.', dependenciesInstalled: false, modelsExecuted: false, result }, null, 2));
