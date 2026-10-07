// Historical M4 policy regression: this suite intentionally freezes the pre-atomic
// projection (coarse container arrows and mask top ports). Current behavior is
// independently checked by atomic-frontier-routing.test.ts; archived gold stays intact.
import test from 'node:test';
import { normalizeDefaultMemoryLabels } from './historical-memory-caption-compat.ts';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { buildScene, buildExportScene, createDocument, createHistory, reduceHistory, renderSvg, applyVisualBatch } from './historical-routing-core.ts';
import { prepareMovePreview, previewMoveScene } from './historical-routing-core.ts';
import type { CanvasDocument, Scene } from '../src/core/types.ts';
// Oracle and fixtures are authored independently. No route/parser/intersection/scoring helpers are imported.
import { metrics, parsePath, verifyRefinement, intrusions } from '../../docs/evidence/m4-routing-refinement/independent/oracle.ts';
import { architecture, placeFixture } from '../../docs/evidence/m4-routing-refinement/independent/fixtures.ts';
import { runControls } from '../../docs/evidence/m4-routing-refinement/independent/controls.ts';
import { verifyOutlineCompatibleRefinement } from '../../docs/evidence/m4-repeat-outline-work/oracle/historical-routing-adapter.ts';

const evidence = new URL('../../docs/evidence/m4-routing-refinement/independent/', import.meta.url);
type Record = { key: string; kind: 'frontier' | 'detail' | 'move'; caseId: string; nodeId?: string; dx?: number; dy?: number; inputPath?: string; inputSha256?: string };
const frozen = JSON.parse(readFileSync(new URL('before/capture.json', evidence), 'utf8')) as { records: Record[] };
const before = (key: string) => JSON.parse(readFileSync(new URL(`before/${key}.scene.json`, evidence), 'utf8')) as Scene;
const serializable = <T>(value: T): T => JSON.parse(JSON.stringify(value));
const sceneRevision = (scene: Scene) => ({ ...scene, revision: 0 });

test('historical M4: independent oracle rejects 15 corruptions including coherent graph displacement and tensor concealment', () => {
  const result = runControls(); assert.equal(result.negativeControls, 15); assert.equal(result.rejected, 15);
  assert.equal(result.positiveUnchangedControlPassed, true);
  assert.ok(result.rows.filter(row => row.coherentEndpoints).length >= 10);
});

test('historical M4: independent strict-interior oracle excludes point contact and same tensor trunks, merges collinear intervals', () => {
  const scene = JSON.parse(readFileSync(new URL('before/fixtures.json', evidence), 'utf8')).records.find((record: { kind: string }) => record.kind === 'shared-trunk').scene as Scene;
  const report = metrics(scene);
  assert.equal(report.sameTensor.overlapPairs, 1); assert.equal(report.sameTensor.overlapLength, 119);
  assert.equal(report.distinctTensor.overlapPairs, 0);
  const points = parsePath('M 0 0 V 10 V 20 H 10'); assert.equal(points.length, 4);
  const fixture = JSON.parse(readFileSync(new URL('before/fixtures.json', evidence), 'utf8')).records.find((record: { kind: string }) => record.kind === 'different-tensors').scene as Scene;
  const subdivided = structuredClone(fixture);
  subdivided.edges[0].path = fixture.edges[0].path.replace('H 397', 'H 200 H 397');
  assert.deepEqual(metrics(subdivided).distinctTensor, metrics(fixture).distinctTensor);
});

test('historical M4: outline compatibility rejects eight coherent corruptions while preserving the frozen routing oracle', () => {
  const cnn = frozen.records.find(record => record.key === 'residual_cnn-level0-paper-180')!;
  const transformer = frozen.records.find(record => record.key === 'transformer-level0-paper-180')!;
  const load = (record: Record) => buildScene(JSON.parse(readFileSync(new URL(`../../${record.inputPath!}`, import.meta.url), 'utf8')) as CanvasDocument);
  const original = load(cnn), old = before(cnn.key), svg = renderSvg(original);
  verifyOutlineCompatibleRefinement(old, serializable(original), svg);
  const reject = (mutate: (scene: Scene) => void, expected: RegExp, prior = old, base = original) => {
    const altered = structuredClone(base); mutate(altered);
    assert.throws(() => verifyOutlineCompatibleRefinement(prior, serializable(altered), renderSvg(altered)), expected);
  };
  const output = (scene: Scene) => scene.nodes.find(node => node.repeat && !node.expanded)!.ports.find(port => port.direction === 'out')!;
  reject(scene => { const port = output(scene); port.y += .03; const edge = scene.edges.find(edge => edge.canonicalEdgeIds.some(id => port.canonicalEdgeIds.includes(id)))!;
    const points = parsePath(edge.path); points[0].y += .03; edge.path = points.map((point, index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`).join(' '); }, /Only exact card-ray/);
  reject(scene => { scene.nodes.find(node => node.repeat && !node.expanded)!.ports.find(port => port.direction === 'in')!.y += 7; }, /Only exact card-ray/);
  reject(scene => { output(scene).canonicalPortId = 'forged-canonical-port'; }, /Only exact card-ray/);
  reject(scene => { scene.edges[0].tensorId = 'concealed-tensor'; }, /altered edge semantics/);
  reject(scene => { const node = scene.nodes.find(node => node.repeat && !node.expanded)!; node.x += .03; node.localX += .03; for (const port of node.ports) port.x += .03; }, /Front\/stack geometry changed/);
  const memoryBase = load(transformer), memoryPrior = before(transformer.key);
  reject(scene => { scene.nodes.flatMap(node => node.ports).find(port => port.id.endsWith(':right'))!.id += ':arbitrary'; }, /Only exact card-ray/, memoryPrior, memoryBase);
  reject(scene => { const node = scene.nodes.find(node => node.repeat && !node.expanded)!, port = output(scene), edge = scene.edges.find(edge => edge.canonicalEdgeIds.some(id => port.canonicalEdgeIds.includes(id)))!;
    const end = parsePath(edge.path).at(-1)!;
    edge.path = `M ${port.x} ${port.y} V ${port.y + 10} H ${node.x + node.width + 4} V ${node.y + node.height - 3} H ${end.x} V ${end.y}`;
    scene.diagnostics.push({ level: 'warning', code: 'layout-route-blocked', edgeId: edge.id, objectIds: [node.id], message: 'Forged blocked report cannot authorize a new intrusion.' });
  }, /New backplate-only intrusion/);
  const moved = frozen.records.find(record => record.key === 'mlp-level0-paper-180-move-up')!, frontier = frozen.records.find(record => record.key === moved.caseId)!;
  const movedDocument = JSON.parse(readFileSync(new URL(`../../${frontier.inputPath!}`, import.meta.url), 'utf8')) as CanvasDocument;
  const blocked = buildScene(reduceHistory(createHistory(movedDocument), { type: 'apply', baseRevision: movedDocument.revision, operations: [{ type: 'move', ids: [moved.nodeId!], dx: moved.dx!, dy: moved.dy! }] }).document);
  reject(scene => { scene.diagnostics = scene.diagnostics.filter(diagnostic => diagnostic.code !== 'layout-route-blocked'); }, /must remain explicitly blocked/, before(moved.key), blocked);
  assert.equal(JSON.stringify(old), JSON.stringify(before(cnn.key)), 'Adapter or controls changed the frozen baseline');
});

for (const record of frozen.records.filter(record => record.kind === 'frontier')) {
  test(`historical M4: independent source-bound frontier/detail/four-direction history invariants: ${record.caseId}`, () => {
    const path = new URL(`../../${record.inputPath!}`, import.meta.url), raw = readFileSync(path, 'utf8'), document = JSON.parse(raw) as CanvasDocument;
    assert.equal(createHash('sha256').update(raw).digest('hex'), record.inputSha256, 'source-bound input changed since before capture');
    const original = JSON.stringify(document), scene = buildScene(document);
    const historical = normalizeDefaultMemoryLabels(document, serializable(scene), before(record.key));
    verifyOutlineCompatibleRefinement(before(record.key), historical, renderSvg(historical));
    assert.deepEqual(scene, buildScene(document)); assert.deepEqual(scene, buildExportScene(document));
    assert.equal(renderSvg(scene), renderSvg(buildScene(document)));
    for (const detail of frozen.records.filter(item => item.caseId === record.caseId && item.kind === 'detail')) {
      const exported = buildExportScene(document, { nodeId: detail.nodeId });
      const historicalDetail = normalizeDefaultMemoryLabels(document, serializable(exported), before(detail.key));
      verifyOutlineCompatibleRefinement(before(detail.key), historicalDetail, renderSvg(historicalDetail));
      assert.deepEqual(exported, buildExportScene(document, { nodeId: detail.nodeId }));
      const scope = exported.exportScope!;
      assert.deepEqual([...scope.internalEdgeIds, ...scope.boundaryEdges.map(edge => edge.edgeId), ...scope.omittedEdgeIds].sort(), document.architecture.edges.map(edge => edge.id).sort());
    }
    for (const move of frozen.records.filter(item => item.caseId === record.caseId && item.kind === 'move')) {
      const session = prepareMovePreview(document, [move.nodeId!]), preview = previewMoveScene(session, move.dx!, move.dy!);
      const history = reduceHistory(createHistory(document), { type: 'apply', baseRevision: document.revision,
        operations: [{ type: 'move', ids: [move.nodeId!], dx: move.dx!, dy: move.dy! }] });
      const committed = buildScene(history.document);
      assert.deepEqual(preview, committed); assert.equal(renderSvg(preview), renderSvg(committed));
      const historicalMove = normalizeDefaultMemoryLabels(history.document, serializable(committed), before(move.key));
      verifyOutlineCompatibleRefinement(before(move.key), historicalMove, renderSvg(historicalMove));
      assert.deepEqual(preview, previewMoveScene(session, move.dx!, move.dy!));
      assert.deepEqual(history.document.architecture, document.architecture); assert.deepEqual(history.document.pinnedObjects, document.pinnedObjects);
      const undo = reduceHistory(history, { type: 'undo' }), redo = reduceHistory(undo, { type: 'redo' });
      assert.deepEqual(undo.document.layout, document.layout); assert.deepEqual(undo.document.layoutByFrontier, document.layoutByFrontier);
      assert.deepEqual(redo.document.layout, history.document.layout); assert.deepEqual(redo.document.layoutByFrontier, history.document.layoutByFrontier);
      assert.deepEqual(sceneRevision(buildScene(undo.document)), sceneRevision(scene));
      assert.deepEqual(sceneRevision(buildScene(redo.document)), sceneRevision(committed));
      const pinned = applyVisualBatch(document, [{ type: 'pin', ids: [move.nodeId!], pinned: true }]);
      const pinnedScene = buildScene(pinned), pinnedMove = previewMoveScene(prepareMovePreview(pinned, [move.nodeId!]), move.dx!, move.dy!);
      assert.deepEqual(pinnedMove.nodes, pinnedScene.nodes); assert.deepEqual(pinnedMove.edges, pinnedScene.edges);
    }
    assert.equal(JSON.stringify(document), original); assert.equal(readFileSync(path, 'utf8'), raw);
    const rootId = scene.nodes.find(node => node.expanded && node.expandable)?.id;
    if (rootId) {
      const pinnedNodeId = frozen.records.find(item => item.caseId === record.caseId && item.kind === 'move')!.nodeId!;
      const pinned = applyVisualBatch(document, [{ type: 'pin', ids: [pinnedNodeId], pinned: true }]);
      const baseline = buildScene(pinned), preview = previewMoveScene(prepareMovePreview(pinned, [rootId]), 37, -29);
      assert.deepEqual(preview.nodes, baseline.nodes, 'a pinned descendant protects ancestor movement');
      assert.deepEqual(preview.edges, baseline.edges);
    }
  });
}

test('historical M4: real public source-bound Transformer metrics improve while preserving unresolved complex crossings', () => {
  for (const level of [1, 2, 3]) {
    const caseId = `transformer-level${level}-paper-180`, record = frozen.records.find(item => item.key === caseId)!;
    const document = JSON.parse(readFileSync(new URL(`../../${record.inputPath!}`, import.meta.url), 'utf8')) as CanvasDocument;
    const old = metrics(before(caseId)), current = metrics(buildScene(document));
    assert.ok(current.distinctTensor.overlapLength < old.distinctTensor.overlapLength);
    if (level === 1) assert.ok(current.distinctTensor.crossingPairs < old.distinctTensor.crossingPairs);
    else assert.ok(current.distinctTensor.overlapPairs < old.distinctTensor.overlapPairs);
    assert.ok(current.distinctTensor.crossingPairs > 0, 'complex source-bound scene remains honestly unresolved');
    assert.ok(current.totalBends <= old.totalBends); assert.equal(current.totalReversals, 0);
  }
});

test('historical M4: public differing-tensor geometry reduces overlap length while shared tensor trunk remains byte-identical', () => {
  const initial = JSON.parse(readFileSync(new URL('before/fixtures.json', evidence), 'utf8'));
  for (const kind of ['different-tensors', 'shared-trunk', 'unavoidable-stub'] as const) {
    const document = placeFixture(createDocument(architecture(kind))), original = JSON.stringify(document), scene = buildScene(document), prior = initial.records.find((row: { kind: string }) => row.kind === kind).scene as Scene;
    const result = verifyRefinement(prior, serializable(scene)); assert.equal(JSON.stringify(document), original);
    assert.deepEqual(intrusions(scene), []);
    if (kind === 'shared-trunk') { assert.deepEqual(scene.edges.map(edge => edge.path), prior.edges.map(edge => edge.path)); assert.equal(result.after.sameTensor.overlapLength, 119); }
    else { assert.ok(result.after.distinctTensor.overlapLength < result.before.distinctTensor.overlapLength); assert.equal(result.after.distinctTensor.overlapPairs, 1, 'fixed endpoints retain some overlap'); }
  }
});
