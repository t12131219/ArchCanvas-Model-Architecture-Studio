import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { applyVisualBatch, buildScene, createHistory, reduceHistory } from '../src/core/index.ts';
import { prepareMovePreview, previewMoveScene } from '../src/core/movePreview.ts';
import { createOrthogonalRouter, ROUTE_COMPONENT_BUDGET } from '../src/core/orthogonalRouter.ts';
import type { RouteRequest } from '../src/core/orthogonalRouter.ts';
import { intrusions, metrics, parsePath, verifyEndpoints } from '../../docs/evidence/m4-routing-refinement/independent/oracle.ts';

const fixturePath = new URL('../../docs/evidence/m4-frontier-move-current/independent/workload/pinned.canvas.json', import.meta.url);
const selected = 'call:instance:model.DenseStress300.network.0';
const document = JSON.parse(readFileSync(fixturePath, 'utf8'));
const move = (dx: number, dy: number) => ({ type: 'move' as const, ids: [selected], dx, dy, scope: 'current-frontier' as const });
const overlapPairs = (scene: ReturnType<typeof buildScene>) => metrics(scene).pairs.filter(pair => pair.overlapLength > 1e-6).length;

function requestsFor(scene: ReturnType<typeof buildScene>): RouteRequest[] {
  return scene.edges.map(edge => {
    const points = parsePath(edge.path);
    return {
      sourceId: edge.sourceId, targetId: edge.targetId, start: points[0], end: points.at(-1)!, preferredPath: edge.path,
      tensorId: edge.tensorId, canonicalSource: edge.source, canonicalTarget: edge.target, canonicalEdgeIds: edge.canonicalEdgeIds,
      role: edge.role, appearance: { stroke: edge.stroke, width: edge.width, dashed: edge.dashed, dashPattern: edge.dashPattern },
    };
  });
}

test('DenseStress300 component routing keeps bounded crossings, overlap and endpoint ownership', () => {
  const scene = buildScene(document), summary = metrics(scene);
  verifyEndpoints(scene);
  assert.ok(summary.distinctTensor.crossingPairs <= 38, `crossings ${summary.distinctTensor.crossingPairs}`);
  assert.ok(overlapPairs(scene) <= 1, `overlap pairs ${overlapPairs(scene)}`);
  assert.equal(summary.totalReversals, 0);
  assert.equal(scene.nodes.length, 304);
  assert.equal(scene.edges.length, 301);
  assert.ok(scene.hiddenEdges.includes('edge:1'));
  assert.deepEqual([...scene.hiddenEdges, ...scene.edges.flatMap(edge => edge.canonicalEdgeIds)].sort(), document.architecture.edges.map((edge: { id: string }) => edge.id).sort());
});

test('four directional moves preserve architecture, preview/commit, history and endpoints', () => {
  const baseline = buildScene(document), baselineArchitecture = JSON.stringify(document.architecture);
  for (const [dx, dy] of [[24, 0], [-24, 0], [0, -24], [0, 24]]) {
    const operation = move(dx, dy), committedDocument = applyVisualBatch(document, [operation]);
    const committed = buildScene(committedDocument), preview = previewMoveScene(prepareMovePreview(document, [selected], 'current-frontier'), dx, dy);
    assert.deepEqual(preview, committed, `preview mismatch for ${dx},${dy}`);
    assert.equal(JSON.stringify(committedDocument.architecture), baselineArchitecture);
    verifyEndpoints(committed);
    const history = reduceHistory(createHistory(document), { type: 'apply', baseRevision: document.revision, operations: [operation] });
    assert.deepEqual(buildScene(history.document), committed);
    assert.deepEqual(buildScene(reduceHistory(history, { type: 'undo' }).document).edges, baseline.edges);
    assert.deepEqual(buildScene(reduceHistory(reduceHistory(history, { type: 'undo' }), { type: 'redo' }).document).edges, committed.edges);
    const moved = committed.nodes.filter(node => {
      const original = baseline.nodes.find(item => item.id === node.id)!;
      return node.x !== original.x || node.y !== original.y || node.width !== original.width || node.height !== original.height;
    });
    assert.deepEqual(moved.map(node => node.id), [selected]);
  }
});

test('down move retains the five atomic intrusions and matching blocked diagnostics', () => {
  const scene = buildScene(applyVisualBatch(document, [move(0, 24)])), found = intrusions(scene);
  assert.equal(found.length, 5);
  for (const item of found) {
    const diagnostic = scene.diagnostics.find(row => row.code === 'layout-route-blocked' && row.edgeId === item.edgeId && row.objectIds?.includes(item.nodeId));
    assert.ok(diagnostic, `missing blocked diagnostic for ${item.edgeId}/${item.nodeId}`);
  }
});

test('narrow-gap centerline proposal is geometrically better but fixed target arrow remains inside the upper card', () => {
  const scene = buildScene(applyVisualBatch(document, [move(0, 24)]));
  const candidate = structuredClone(scene);
  const edge3 = candidate.edges.find(edge => edge.id === 'edge:3')!, edge41 = candidate.edges.find(edge => edge.id === 'edge:41')!;
  // Keep the exact public endpoints and their downward/upward port normals;
  // only shorten the two local escapes to the available two-unit clearance.
  edge3.path = 'M 207 402 V 404 H 316 V 310 H 425 V 316';
  edge41.path = 'M 425 470 V 476 H 316 V 406 H 207 V 408';
  assert.deepEqual(intrusions(candidate), [], 'the literal centerline proposal clears every non-endpoint body');
  const before = metrics(scene).distinctTensor, after = metrics(candidate).distinctTensor;
  assert.ok(after.crossingPairs < before.crossingPairs, 'centerline proposal removes crossings');
  assert.ok(after.overlapPairs < before.overlapPairs, 'centerline proposal removes the narrow-gap overlap');
  assert.deepEqual([edge3.path.split(' ').slice(0, 3), edge41.path.split(' ').slice(0, 3)], [
    ['M', '207', '402'], ['M', '425', '470'],
  ]);
  const upper = candidate.nodes.find(node => node.id === 'call:instance:model.DenseStress300.network.0')!;
  // svg.ts marker: viewBox 10, markerWidth 5.5, markerUnits=strokeWidth,
  // refX=8.5 and the path base x=1. With stroke 1.5, the base is 6.1875
  // world units behind a downward target endpoint and spans ±3.3 laterally.
  const markerScale = 5.5 * edge41.width / 10, baseDepth = (8.5 - 1) * markerScale, halfWidth = 4 * markerScale;
  const target = { x: 207, y: 408 }, baseY = target.y - baseDepth;
  assert.ok(baseY < upper.y + upper.height && baseY > upper.y, 'target arrow base overlaps the upper-card vertical interval');
  assert.ok(target.x - halfWidth > upper.x && target.x + halfWidth < upper.x + upper.width, 'target arrow base spans inside the upper-card width');
  assert.ok(baseY < upper.y + upper.height, 'the fixed arrow geometry prevents a visual-clear claim');
});

test('component routing budgets are frozen and over-cap batches keep deterministic per-route fallback', () => {
  assert.equal(Object.isFrozen(ROUTE_COMPONENT_BUDGET), true);
  assert.deepEqual(ROUTE_COMPONENT_BUDGET, {
    maxNodes: 1_024, maxRoutes: 512, maxRoutePoints: 4_096, maxComponentRoutes: 8, maxComponents: 128,
    maxPointsPerRoute: 64, maxCoordinatesPerAxis: 24, maxGeneratedPerRoute: 384, maxCandidatesPerRoute: 64,
    maxCandidates: 2_048, maxRefinedRoutes: 128, maxPairChecks: 32_768, maxSegmentChecks: 400_000, maxObstacleChecks: 150_000,
  });
  const scene = buildScene(document), router = createOrthogonalRouter(scene.nodes), requests = requestsFor(scene);
  const oversized = [...requests, ...Array.from({ length: ROUTE_COMPONENT_BUDGET.maxRoutes + 1 - requests.length }, () => requests[0])];
  assert.equal(oversized.length, ROUTE_COMPONENT_BUDGET.maxRoutes + 1);
  const result = router.batch(oversized), single = router(oversized[0]);
  assert.equal(result.length, oversized.length);
  assert.equal(result[0].path, single.path, 'over-cap batch must retain the route() fallback');
  assert.equal(result.at(-1)!.path, single.path, 'duplicate over-cap route must stay deterministic');
});
