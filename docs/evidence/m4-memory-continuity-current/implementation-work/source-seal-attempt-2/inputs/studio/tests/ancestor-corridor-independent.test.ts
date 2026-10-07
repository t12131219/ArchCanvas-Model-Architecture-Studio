import test from 'node:test';
import { normalizeDefaultMemoryLabels } from './historical-memory-caption-compat.ts';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import type { CanvasDocument, Scene } from '../src/core/types.ts';
// Product functions produce observations only. Expected geometry and invariants
// come from frozen bytes, literal controls and the separate independent oracle.
import { buildScene, buildExportScene, renderSvg } from '../src/core/index.ts';
import { ROUTE_REFINEMENT_BUDGET } from '../src/core/orthogonalRouter.ts';
import { assertCanonicalCoverage, assertProtectedMetrics, assertSvgAgreement, edgeFamilyMeta, familyEligible, mergedIntervalLength, metrics, parseOrthogonalPath, verifyRefinement } from '../../docs/evidence/m4-ancestor-corridor-work/ancestor-corridor-oracle.ts';

const project = new URL('../../', import.meta.url);
const evidence = new URL('../../docs/evidence/m4-ancestor-corridor-work/baseline/', import.meta.url);
type Binding = { path: string; bytes: number; sha256: string; archivedSource: { path: string; archivePath: string; bytes: number; sha256: string } };
type Record = { key: string; caseId: string; detailNodeId: string | null; input: Binding; scene: Binding; svg: Binding };
const frozen = JSON.parse(readFileSync(new URL('capture.json', evidence), 'utf8')) as { records: Record[]; bindings: Binding[]; archiveManifest: { path: string; sha256: string } };
const sha256 = (raw: string | Buffer) => createHash('sha256').update(raw).digest('hex');
const read = (binding: Binding) => readFileSync(new URL(binding.path, project));
const sceneFor = (record: Record) => JSON.parse(read(record.scene).toString()) as Scene;
const canvasFor = (record: Record) => JSON.parse(read(record.input).toString()) as CanvasDocument;
const svgFor = (record: Record) => read(record.svg).toString();
const transformerRecord = frozen.records.find(record => record.key === 'transformer-level3-paper-180')!;
const l3 = () => sceneFor(transformerRecord);
const serializable = <T>(value: T): T => JSON.parse(JSON.stringify(value));
const approximate = (actual: number, expected: number) => assert.ok(Math.abs(actual - expected) < 1e-6, `${actual} != ${expected}`);

function pathOnly(paths: string[], tensors = paths.map((_, index) => `t${index}`)) {
  const scene = l3(); scene.nodes = []; scene.edges = paths.map((path, index) => ({ ...scene.edges[0], id: `e${index}`, path, sourceId: `source${index}`, targetId: `target${index}`, tensorId: tensors[index] })); return scene;
}

function literalSharedCandidate() {
  const candidate = l3();
  candidate.edges.find(edge => edge.id === 'edge:44')!.path = 'M 237 2772 V 2778 H 467 V 397 H 621.6 V 410';
  candidate.edges.find(edge => edge.id === 'edge:55')!.path = 'M 237 2772 V 2778 H 467 V 766 H 623 V 772';
  return candidate;
}

test('independent corridor parser rejects ignored bytes, diagonal, partial, nonfinite and multiple subpaths', () => {
  for (const bad of ['M 0 0 L 10 10', 'M 0 0 V', 'M 0 0 V NaN', 'M 0 0 V 1e999', 'M 0 0 Q 1 2 3 4', 'M 0 0 H 10 garbage', 'M 0 0 H 10 M 10 10 V 20', 'm 0 0 h 10', 'M 0 0 H 0', 'M 0 0 H 10 20']) assert.throws(() => parseOrthogonalPath(bad));
  assert.deepEqual(parseOrthogonalPath('M 0 0 V 10 V 10 V 20 H 30'), [{ x: 0, y: 0 }, { x: 0, y: 10 }, { x: 0, y: 10 }, { x: 0, y: 20 }, { x: 30, y: 20 }]);
});

test('independent corridor metrics preserve split crossings, point contacts and pair-local interval union', () => {
  const original = pathOnly(['M 0 0 H 20', 'M 10 -10 V 10']);
  const split = pathOnly(['M 0 0 H 10 H 20', 'M 10 -10 V 0 V 10']);
  assert.equal(metrics(original).distinct.crossingPairs, 1); assert.equal(metrics(original).distinct.crossingPoints, 1);
  assert.deepEqual(metrics(split).distinct, metrics(original).distinct, 'subdivision at the crossing must not conceal it');
  assert.equal(metrics(pathOnly(['M 0 0 H 10', 'M 10 -10 V 10'])).distinct.crossingPairs, 0);
  const intervals = [{ axis: 'x' as const, coordinate: 0, low: 0, high: 10, edgeId: 'a/b' },
    { axis: 'x' as const, coordinate: 0, low: 5, high: 15, edgeId: 'a/b' }, { axis: 'x' as const, coordinate: 0, low: 0, high: 10, edgeId: 'a/b' },
    { axis: 'x' as const, coordinate: 0, low: 0, high: 10, edgeId: 'a/c' }];
  assert.equal(mergedIntervalLength(intervals), 25, 'distinct edge pairs must each contribute their geometric union');
  const three = metrics(pathOnly(['M 0 0 H 20', 'M 5 0 H 15', 'M 5 0 H 15']));
  assert.equal(three.distinct.overlapPairs, 3); assert.equal(three.distinct.overlapLength, 30);
  const reversed = metrics(pathOnly(['M 0 0 H 10 H 0 H 10', 'M 0 0 H 10']));
  assert.equal(reversed.distinct.overlapLength, 10); assert.equal(reversed.reversals, 2);
  const priorSame = metrics(pathOnly(['M 0 0 H 20', 'M 5 -10 V 10', 'M 15 10 V 30'], ['shared', 'shared', 'shared']));
  const exchangedSame = metrics(pathOnly(['M 0 20 H 20', 'M 5 -10 V 10', 'M 15 10 V 30'], ['shared', 'shared', 'shared']));
  assert.equal(priorSame.same.crossingPairs, 1); assert.equal(exchangedSame.same.crossingPairs, 1);
  assert.throws(() => assertProtectedMetrics(priorSame, exchangedSame), /new same-tensor crossing for pair/, 'removing one same-tensor crossing cannot conceal another new pair');
});

test('independent corridor frozen captures remain bound to exact archived source bytes', () => {
  assert.equal(frozen.records.length, 12); assert.equal(frozen.records.filter(record => !record.detailNodeId).length, 9); assert.equal(frozen.bindings.length, 34);
  assert.equal(sha256(readFileSync(new URL(frozen.archiveManifest.path, project))), frozen.archiveManifest.sha256);
  for (const binding of frozen.bindings) {
    const copied = read(binding), archived = readFileSync(new URL(binding.archivedSource.archivePath, project));
    assert.equal(copied.length, binding.bytes); assert.equal(sha256(copied), binding.sha256);
    assert.equal(archived.length, binding.archivedSource.bytes); assert.equal(sha256(archived), binding.archivedSource.sha256); assert.deepEqual(copied, archived);
  }
});

test('independent corridor family identity requires exact source, memory role, effective style, side and complete canonical membership', () => {
  const before = l3(), graph = canvasFor(transformerRecord).architecture;
  const first = edgeFamilyMeta(before, before.edges.find(edge => edge.id === 'edge:44')!, graph), second = edgeFamilyMeta(before, before.edges.find(edge => edge.id === 'edge:55')!, graph);
  assert.equal(familyEligible(first, second), true);
  // A resolved collapsed proxy is eligible; unresolved or mixed proxy facts are not.
  assert.equal(familyEligible({ ...first, proxy: true }, { ...second, proxy: true }), true);
  const negatives = [
    { ...second, sourceId: 'other-display-owner' }, { ...second, source: { ...second.source, nodeId: 'other-canonical-owner' } },
    { ...second, source: { ...second.source, portId: 'other-canonical-port' } }, { ...second, tensorId: 'other-tensor' },
    { ...second, role: 'data' }, { ...second, role: 'residual' }, { ...second, stroke: '#000000' }, { ...second, width: 2 }, { ...second, dashed: true },
    { ...second, displaySide: 'right' }, { ...second, start: { ...second.start, x: second.start.x + .03 } },
    { ...second, canonicalBindings: [] }, { ...second, expectedBindings: [] }, { ...second, canonicalEdgeIds: [] }, { ...second, portCanonicalEdgeIds: ['edge:44'] },
    { ...second, canonicalBindings: [{ ...second.source }, { nodeId: 'mixed-proxy', portId: 'out' }] }, { ...second, resolved: false, proxy: true },
  ];
  for (const corrupted of negatives) assert.equal(familyEligible(first, corrupted), false, JSON.stringify(corrupted));
});

test('independent corridor rejects coherent semantic, branch, circle, style, body and same-tensor crossing corruptions', () => {
  const before = l3(), svg = svgFor(transformerRecord);
  verifyRefinement(before, before, svg, svg);
  const reject = (mutate: (scene: Scene) => void) => {
    const after = structuredClone(before); mutate(after); assert.throws(() => verifyRefinement(before, after, renderSvg(after), svg));
  };
  reject(scene => { scene.edges[0].source.portId = 'forged-source-port'; });
  reject(scene => { scene.edges[0].tensorId = 'concealed-tensor'; });
  reject(scene => { const removed = scene.edges.pop()!; scene.hiddenEdges.push(...removed.canonicalEdgeIds); });
  reject(scene => { scene.edges[0].canonicalEdgeIds = []; });
  reject(scene => { scene.edges[0].width += .5; });
  reject(scene => { const edge = scene.edges.find(edge => edge.id === 'edge:44')!, port = scene.nodes.find(node => node.id === edge.sourceId)!.ports.find(port => port.canonicalEdgeIds.includes(edge.id))!;
    port.y += .03; for (const member of scene.edges.filter(member => member.sourceId === edge.sourceId && member.canonicalEdgeIds.some(id => port.canonicalEdgeIds.includes(id)))) member.path = member.path.replace(/^M\s+[-\d.]+\s+[-\d.]+/, `M ${port.x} ${port.y}`); });
  reject(scene => { const edge = scene.edges.find(edge => edge.id === 'edge:44')!; edge.path = 'M 237 2772 V 2780 H 242 V 2730 H 855 V 397 H 621.6 V 410';
    scene.diagnostics.push({ level: 'warning', code: 'layout-route-blocked', edgeId: edge.id, objectIds: [edge.sourceId], message: 'A warning cannot authorize a newly introduced intrusion.' }); });
  const single = structuredClone(before); single.edges.find(edge => edge.id === 'edge:44')!.path = 'M 237 2772 V 2785 H 462 V 397 H 621.6 V 410';
  assert.equal(metrics(single).distinct.overlapPairs, 17, 'counterexample improves the headline overlap count');
  assert.throws(() => verifyRefinement(before, single, renderSvg(single), svg), /same-tensor/);
  const published = renderSvg(before).replace('data-edge-id="edge:44"', 'data-edge-id="hidden-branch"');
  assert.throws(() => assertSvgAgreement(before, published), /missing|differs/);
});

test('independent corridor literal shared-family improvement retains each branch and exposes crossing exchanges', () => {
  const before = l3(), candidate = literalSharedCandidate(), report = verifyRefinement(before, candidate, renderSvg(candidate), svgFor(transformerRecord));
  assert.deepEqual(report.before.distinct, { crossingPairs: 20, crossingPoints: 23, overlapPairs: 19, overlapLength: 4314.21 });
  assert.equal(report.before.disjoint.crossingPairs, 17); assert.equal(report.before.disjoint.crossingPoints, 20); assert.equal(report.before.disjoint.overlapPairs, 13);
  assert.equal(report.after.distinct.crossingPairs, 20); assert.equal(report.after.distinct.crossingPoints, 23); assert.equal(report.after.distinct.overlapPairs, 17); approximate(report.after.distinct.overlapLength, 4068.81);
  approximate(report.before.routeLength - report.after.routeLength, 480.8);
  for (const second of ['edge:45', 'edge:46']) assert.ok(!report.after.pairs.some(pair => pair.first === 'edge:44' && pair.second === second && pair.overlaps.length));
  const oldPairs = new Set(report.before.pairs.filter(pair => !pair.sameTensor && pair.points.length).map(pair => `${pair.first}/${pair.second}`));
  const newPairs = new Set(report.after.pairs.filter(pair => !pair.sameTensor && pair.points.length).map(pair => `${pair.first}/${pair.second}`));
  assert.ok([...newPairs].some(pair => !oldPairs.has(pair)), 'literal controls retain real crossing exchanges rather than a pairwise monotonicity claim');
});

test('independent corridor current nine frontiers and three details preserve source, cards, ports, canonical branches and protected geometry', () => {
  for (const record of frozen.records) {
    const document = canvasFor(record), untouched = JSON.stringify(document), before = sceneFor(record);
    const current = record.detailNodeId ? buildExportScene(document, { nodeId: record.detailNodeId }) : buildScene(document), svg = renderSvg(current);
    assertSvgAgreement(current, svg);
    const historical = normalizeDefaultMemoryLabels(document, serializable(current), before);
    verifyRefinement(before, historical, renderSvg(historical), svgFor(record)); assertCanonicalCoverage(current, document.architecture);
    assert.deepEqual(current, record.detailNodeId ? buildExportScene(document, { nodeId: record.detailNodeId }) : buildScene(document), 'routing must be deterministic');
    if (!record.detailNodeId) assert.equal(renderSvg(buildExportScene(document)), svg, 'full export and canvas disagree');
    assert.equal(JSON.stringify(document), untouched, 'rendering modified Canvas/source facts');
  }
});

test('independent corridor current L3 cannot trade overlap for crosses or lose named canonical fanout branches', () => {
  const before = l3(), document = canvasFor(transformerRecord), current = buildScene(document);
  assertSvgAgreement(current, renderSvg(current));
  const historical = normalizeDefaultMemoryLabels(document, serializable(current), before);
  const report = verifyRefinement(before, historical, renderSvg(historical), svgFor(transformerRecord));
  assert.equal(report.after.distinct.overlapPairs, 17); assert.equal(report.after.distinct.crossingPairs, 20); assert.equal(report.after.distinct.crossingPoints, 23);
  assert.ok(report.after.disjoint.overlapPairs <= 13); assert.ok(report.after.distinct.overlapLength <= 4314.21 + 1e-6);
  for (const id of ['edge:44', 'edge:55']) {
    const old = before.edges.find(edge => edge.id === id)!, edge = current.edges.find(edge => edge.id === id)!;
    assert.ok(edge); assert.deepEqual(edge.canonicalEdgeIds, old.canonicalEdgeIds); assert.deepEqual(edge.source, old.source); assert.deepEqual(edge.target, old.target);
    assert.equal(edge.role, 'memory'); assert.notEqual(edge.path, old.path, 'both canonical family branches must participate in the corridor change');
  }
  for (const second of ['edge:45', 'edge:46']) assert.ok(!report.after.pairs.some(pair => pair.first === 'edge:44' && pair.second === second && pair.overlaps.length), 'the two named mask overlaps must disappear');
  const shared = report.after.pairs.find(pair => pair.first === 'edge:44' && pair.second === 'edge:55')!;
  const oldShared = report.before.pairs.find(pair => pair.first === 'edge:44' && pair.second === 'edge:55')!;
  assert.equal(shared.sameTensor, true); assert.equal(shared.points.length, 0); assert.ok(shared.overlapLength > oldShared.overlapLength, 'the family retains a common trunk instead of hiding either branch');
});

test('independent corridor work caps remain their literal approved bounds', () => {
  assert.deepEqual(ROUTE_REFINEMENT_BUDGET, { maxNodes: 1024, maxRoutes: 512, maxRoutePoints: 4096, maxPairChecks: 32768, maxSegmentChecks: 150000,
    maxObstacleChecks: 60000, maxCandidates: 384, maxCandidatesPerRoute: 80, maxRefinedRoutes: 8, passes: 2 });
});
