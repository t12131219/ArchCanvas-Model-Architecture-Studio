import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { applyVisualBatch, buildExportScene, createHistory, reduceHistory } from '../src/core/index.ts';
import * as prior from '../../docs/evidence/m4-memory-continuity-current/before-change/inputs/studio/src/core/index.ts';
import type { CanvasDocument, SceneNode } from '../src/core/types.ts';
import type { RouteRequest, RouteResult } from '../src/core/orthogonalRouter.ts';
import { MEMORY_CONTINUITY_BUDGET, projectMemoryContinuity } from '../src/core/memoryContinuity.ts';
import { normalizeMemoryContinuityGeometry } from './historical-memory-continuity-compat.ts';

const source = JSON.parse(readFileSync(new URL('../../docs/evidence/m4-caption-stability-current/independent-review/source-envelope.json', import.meta.url), 'utf8')).document as CanvasDocument;
const encoder = 'repeat:instance:model.Transformer.encoder', decoder = 'call:instance:model.Transformer.decoder';
function parse(path: string) {
  const tokens = path.match(/[MHV]|[-+]?(?:\d*\.\d+|\d+\.?\d*)/g)!; const result: [number, number][] = [];
  for (let i = 0; i < tokens.length;) { const c = tokens[i++]; result.push(c === 'M' ? [+tokens[i++], +tokens[i++]]
    : c === 'H' ? [+tokens[i++], result.at(-1)![1]] : [result.at(-1)![0], +tokens[i++]]); }
  return result;
}
function routeLength(path: string) { const p = parse(path); return p.slice(1).reduce((sum, b, i) => sum + Math.abs(b[0] - p[i][0]) + Math.abs(b[1] - p[i][1]), 0); }
const serial = <T>(x: T): T => JSON.parse(JSON.stringify(x));

test('source and target signed14/15 thresholds retain endpoint continuity and exact peers across caption preset size and detail combinations', () => {
  const input = JSON.stringify(source);
  for (const owner of [encoder, decoder]) for (const mode of ['default', 'empty', 'custom'])
    for (const preset of ['paper', 'monochrome'] as const) for (const widthMm of [85, 180]) for (const scope of [{}, { nodeId: source.expandedIds[0] }]) {
      const base = structuredClone(source);
      if (mode !== 'default') for (const e of base.architecture.edges.filter(e => e.role === 'memory')) e.label = mode === 'empty' ? '' : 'memory context';
      const observations = new Map<number, { path: string; ports: [number, number][] }>();
      for (const dy of [-24, -16, -15.001, -15, -14.999, -14, 0, 14, 14.999, 15, 15.001, 16, 24]) {
        const doc = applyVisualBatch(base, [{ type: 'page', page: { preset, widthMm } }, { type: 'move', ids: [owner], dx: 0, dy }]), bytes = JSON.stringify(doc);
        const scene = buildExportScene(doc, { ...scope, widthMm }), before = prior.buildExportScene(doc, { ...scope, widthMm });
        const normalized = normalizeMemoryContinuityGeometry(doc, scene), memory = scene.edges.find(e => e.id === 'edge:44')!;
        assert.deepEqual(serial(normalized.nodes), serial(before.nodes));
        assert.deepEqual(serial(scene.edges.filter(e => e.role !== 'memory').map(({ labelX: _x, labelY: _y, ...e }) => e)),
          serial(before.edges.filter(e => e.role !== 'memory').map(({ labelX: _x, labelY: _y, ...e }) => e)));
        assert.equal(memory.label, mode === 'default' ? 'memory' : mode === 'empty' ? '' : 'memory context');
        assert.deepEqual(scene.sourceFacts, before.sourceFacts); assert.equal(scene.irDigest, before.irDigest);
        assert.deepEqual(scene, buildExportScene(structuredClone(doc), { ...scope, widthMm })); assert.equal(JSON.stringify(doc), bytes);
        const p = parse(memory.path); observations.set(dy, { path: memory.path, ports: [p[0], p.at(-1)!] });
      }
      for (const [a, b] of [[14, 15], [-14, -15]]) {
        const previous = observations.get(a)!, next = observations.get(b)!;
        assert.ok(Math.abs(routeLength(next.path) - routeLength(previous.path) - 1) < 1e-6);
        const fixed = owner === encoder ? 1 : 0, moving = owner === encoder ? 0 : 1;
        assert.deepEqual(previous.ports[fixed], next.ports[fixed]);
        assert.equal(previous.ports[moving][0], next.ports[moving][0]);
        assert.ok(Math.abs(Math.abs(next.ports[moving][1] - previous.ports[moving][1]) - 1) < 1e-6);
      }
    }
  assert.equal(JSON.stringify(source), input);
});

test('horizontal gap guards retain complete baseline when two six-unit leads are unavailable', () => {
  for (const dx of [22.9, 23, 23.1, 34, 35, 36, 41, 42, 43]) {
    const doc = applyVisualBatch(source, [{ type: 'move', ids: [encoder], dx, dy: 15 }]), before = prior.buildExportScene(doc), scene = buildExportScene(doc);
    assert.deepEqual(scene.edges.filter(e => e.role !== 'memory').map(e => e.path), before.edges.filter(e => e.role !== 'memory').map(e => e.path));
    const memory = scene.edges.find(e => e.role === 'memory')!, old = before.edges.find(e => e.id === memory.id)!;
    if (dx > 23) assert.equal(memory.path, old.path);
    normalizeMemoryContinuityGeometry(doc, scene);
  }
});

test('continuity is detached and one typed move survives undo redo and JSON reopen', () => {
  const initial = createHistory(source), before = JSON.stringify(initial);
  const moved = reduceHistory(initial, { type: 'apply', operations: [{ type: 'move', ids: [encoder], dx: 0, dy: 24 }] });
  const undone = reduceHistory(moved, { type: 'undo' }), redone = reduceHistory(undone, { type: 'redo' });
  assert.equal(JSON.stringify(initial), before); assert.deepEqual({ ...undone.document, revision: source.revision }, source);
  assert.deepEqual(buildExportScene(redone.document), buildExportScene(serial(redone.document)));
  assert.deepEqual(moved.document.architecture, source.architecture); assert.equal(moved.past.length, 1);
});

function literal() {
  const node = (id: string, x: number, y: number): SceneNode => ({ id, x, y, width: 100, height: 100, localX: x, localY: y, label: id, subtitle: '',
    headerHeight: 20, kind: 'Block', category: 'container', fill: '#fff', stroke: '#444', glyph: 'module', expanded: false, expandable: true, pinned: false, evidence: 'source', ports: [] });
  const nodes = [node('a', 0, 0), node('b', 160, 10)];
  const request: RouteRequest = { sourceId: 'a', targetId: 'b', role: 'memory', tensorId: 'one', appearance: { stroke: '#333', width: 2, dashed: false },
    start: { x: 50, y: 100 }, end: { x: 210, y: 10 }, preferredPath: 'M 50 100 V 140 H 240 V 0 H 210 V 10' };
  const baseline: RouteResult = { path: request.preferredPath, points: parse(request.preferredPath).map(([x, y]) => ({ x, y })), changed: false, blockedBy: [] };
  return { nodes, requests: [request], baseline: [baseline] };
}
test('literal guards reject joint and same-tensor peers close strokes invalid widths gap bodies and exhausted checks', () => {
  const initial = literal(); assert.equal(projectMemoryContinuity(initial.nodes, initial.requests, initial.baseline).get(0)?.path, 'M 100 55 H 130 V 65 H 160');
  for (const path of ['M 130 30 V 55 H 145', 'M 105 56.9 H 125', 'M 100 55 H 160']) {
    const input = literal(); input.requests.push({ ...input.requests[0], role: 'data', preferredPath: path });
    input.baseline.push({ path, points: parse(path).map(([x, y]) => ({ x, y })), changed: false, blockedBy: [] });
    const bytes = JSON.stringify(input); assert.equal(projectMemoryContinuity(input.nodes, input.requests, input.baseline).size, 0); assert.equal(JSON.stringify(input), bytes);
  }
  for (const width of [0, NaN, Infinity]) { const input = literal(); input.requests[0].appearance!.width = width; assert.equal(projectMemoryContinuity(input.nodes, input.requests, input.baseline).size, 0); }
  for (const key of ['maxPairChecks', 'maxSegmentChecks', 'maxObstacleChecks', 'maxCandidates'] as const) {
    const input = literal(); assert.equal(projectMemoryContinuity(input.nodes, input.requests, input.baseline, { ...MEMORY_CONTINUITY_BUDGET, [key]: 0 }).size, 0);
  }
  for (const key of Object.keys(MEMORY_CONTINUITY_BUDGET) as (keyof typeof MEMORY_CONTINUITY_BUDGET)[]) {
    const input = literal(), incomplete = { ...MEMORY_CONTINUITY_BUDGET } as Partial<typeof MEMORY_CONTINUITY_BUDGET>;
    delete incomplete[key];
    assert.equal(projectMemoryContinuity(input.nodes, input.requests, input.baseline, incomplete as typeof MEMORY_CONTINUITY_BUDGET).size, 0);
  }
  const input = literal(); input.nodes.push({ ...input.nodes[0], id: 'obstacle', x: 120, y: 50, width: 20, height: 30 });
  assert.equal(projectMemoryContinuity(input.nodes, input.requests, input.baseline).size, 0);
});

test('version adapter rejects coherent geometry canonical nonmemory and consumer-coverage corruptions', () => {
  const doc = applyVisualBatch(source, [{ type: 'move', ids: [encoder], dx: 0, dy: 15 }]), scene = buildExportScene(doc);
  normalizeMemoryContinuityGeometry(doc, scene);
  const reject = (mutate: (s: typeof scene) => void) => { const forged = structuredClone(scene); mutate(forged); assert.throws(() => normalizeMemoryContinuityGeometry(doc, forged)); };
  reject(s => { s.edges.find(e => e.role === 'memory')!.path = 'M 281 459.1 H 300 V 444.1 H 316'; });
  reject(s => { s.edges.find(e => e.role !== 'memory')!.path = 'M 1 1 H 2'; });
  reject(s => { s.nodes.flatMap(n => n.ports).find(p => p.canonicalEdgeIds.includes('edge:44'))!.x += .01; });
  reject(s => { s.nodes.flatMap(n => n.ports).find(p => p.canonicalEdgeIds.includes('edge:44'))!.canonicalEdgeIds = ['edge:44']; });
  reject(s => { s.edges.find(e => e.role === 'memory')!.source.portId = 'wrong'; });
});

test('detail mixed consumers keep retained port coverage and architecture-order bindings after memory projection', () => {
  const document = JSON.parse(readFileSync(new URL('../../docs/evidence/m4-memory-continuity-current/implementation-work/detail-consumer-literal.json', import.meta.url), 'utf8')) as CanvasDocument;
  const before = prior.buildExportScene(document, { nodeId: 'owner' }), current = buildExportScene(document, { nodeId: 'owner' });
  const expectedBindings = (ids: string[], direction: 'in' | 'out') => document.architecture.edges.filter(e => ids.includes(e.id))
    .map(e => direction === 'out' ? e.source : e.target);
  for (const node of current.nodes) for (const port of node.ports) assert.deepEqual(port.canonicalBindings, expectedBindings(port.canonicalEdgeIds, port.direction));
  const bottom = current.nodes.find(n => n.id === 'a')!.ports.find(p => p.direction === 'out' && p.id.endsWith(':memory'))!;
  const old = before.nodes.find(n => n.id === 'a')!.ports.find(p => p.id === bottom.id)!;
  assert.deepEqual([bottom.x, bottom.y], [old.x, old.y]);
  assert.deepEqual(bottom.canonicalBindings, expectedBindings(bottom.canonicalEdgeIds, 'out'));
  assert.deepEqual(current.edges.filter(e => e.role !== 'memory').map(e => e.path), before.edges.filter(e => e.role !== 'memory').map(e => e.path));
  normalizeMemoryContinuityGeometry(document, current);
});
