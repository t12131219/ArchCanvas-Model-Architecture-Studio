import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { buildScene, buildExportScene, createDocument, createHistory, reduceHistory, renderSvg, applyVisualBatch } from '../src/core/index.ts';
import { prepareMovePreview, previewMoveScene } from '../src/core/movePreview.ts';
import type { CanvasDocument, Scene } from '../src/core/types.ts';
// Oracle and fixtures are authored independently. No route/parser/intersection/scoring helpers are imported.
import { metrics, parsePath, verifyRefinement, intrusions } from '../../docs/evidence/m4-routing-refinement/independent/oracle.ts';
import { architecture, placeFixture } from '../../docs/evidence/m4-routing-refinement/independent/fixtures.ts';
import { runControls } from '../../docs/evidence/m4-routing-refinement/independent/controls.ts';

const evidence = new URL('../../docs/evidence/m4-routing-refinement/independent/', import.meta.url);
type Record = { key: string; kind: 'frontier' | 'detail' | 'move'; caseId: string; nodeId?: string; dx?: number; dy?: number; inputPath?: string; inputSha256?: string };
const frozen = JSON.parse(readFileSync(new URL('before/capture.json', evidence), 'utf8')) as { records: Record[] };
const before = (key: string) => JSON.parse(readFileSync(new URL(`before/${key}.scene.json`, evidence), 'utf8')) as Scene;
const serializable = <T>(value: T): T => JSON.parse(JSON.stringify(value));
const sceneRevision = (scene: Scene) => ({ ...scene, revision: 0 });

test('independent oracle rejects 15 corruptions including coherent graph displacement and tensor concealment', () => {
  const result = runControls(); assert.equal(result.negativeControls, 15); assert.equal(result.rejected, 15);
  assert.equal(result.positiveUnchangedControlPassed, true);
  assert.ok(result.rows.filter(row => row.coherentEndpoints).length >= 10);
});

test('independent strict-interior oracle excludes point contact and same tensor trunks, merges collinear intervals', () => {
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

for (const record of frozen.records.filter(record => record.kind === 'frontier')) {
  test(`independent source-bound frontier/detail/four-direction history invariants: ${record.caseId}`, () => {
    const path = new URL(`../../${record.inputPath!}`, import.meta.url), raw = readFileSync(path, 'utf8'), document = JSON.parse(raw) as CanvasDocument;
    assert.equal(createHash('sha256').update(raw).digest('hex'), record.inputSha256, 'source-bound input changed since before capture');
    const original = JSON.stringify(document), scene = buildScene(document);
    verifyRefinement(before(record.key), serializable(scene));
    assert.deepEqual(scene, buildScene(document)); assert.deepEqual(scene, buildExportScene(document));
    assert.equal(renderSvg(scene), renderSvg(buildScene(document)));
    for (const detail of frozen.records.filter(item => item.caseId === record.caseId && item.kind === 'detail')) {
      const exported = buildExportScene(document, { nodeId: detail.nodeId });
      verifyRefinement(before(detail.key), serializable(exported));
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
      verifyRefinement(before(move.key), serializable(committed));
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

test('real public source-bound Transformer metrics improve while preserving unresolved complex crossings', () => {
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

test('public differing-tensor geometry reduces overlap length while shared tensor trunk remains byte-identical', () => {
  const initial = JSON.parse(readFileSync(new URL('before/fixtures.json', evidence), 'utf8'));
  for (const kind of ['different-tensors', 'shared-trunk', 'unavoidable-stub'] as const) {
    const document = placeFixture(createDocument(architecture(kind))), original = JSON.stringify(document), scene = buildScene(document), prior = initial.records.find((row: { kind: string }) => row.kind === kind).scene as Scene;
    const result = verifyRefinement(prior, serializable(scene)); assert.equal(JSON.stringify(document), original);
    assert.deepEqual(intrusions(scene), []);
    if (kind === 'shared-trunk') { assert.deepEqual(scene.edges.map(edge => edge.path), prior.edges.map(edge => edge.path)); assert.equal(result.after.sameTensor.overlapLength, 119); }
    else { assert.ok(result.after.distinctTensor.overlapLength < result.before.distinctTensor.overlapLength); assert.equal(result.after.distinctTensor.overlapPairs, 1, 'fixed endpoints retain some overlap'); }
  }
});
