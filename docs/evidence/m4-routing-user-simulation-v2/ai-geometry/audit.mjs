import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { buildScene, applyVisualBatch, createHistory, reduceHistory, renderSvg } from './inputs/studio/src/core/index.ts';
import { prepareMovePreview, previewMoveScene } from './inputs/studio/src/core/movePreview.ts';
import { metrics, intrusions, parsePath, verifyEndpoints } from './inputs/docs/evidence/m4-routing-refinement/independent/oracle.ts';

// The subject is the frozen formal B32ccWRJ core, never a prototype. Geometry
// is measured by an independent preexisting handwritten oracle, not router helpers.
const fixture = new URL('./inputs/docs/evidence/m4-frontier-move-current/independent/workload/pinned.canvas.json', import.meta.url);
const document = JSON.parse(readFileSync(fixture, 'utf8')), beforeBytes = JSON.stringify(document);
const selected = 'call:instance:model.DenseStress300.network.0';
const move = (dx, dy) => ({ type: 'move', ids: [selected], dx, dy, scope: 'current-frontier' });
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const serializable = value => JSON.parse(JSON.stringify(value));
const baseline = buildScene(document);
const direction = (a, b) => [Math.sign(b.x - a.x), Math.sign(b.y - a.y)];
function endpointNormals(scene) {
  const errors = [];
  for (const edge of scene.edges) {
    const points = parsePath(edge.path);
    for (const [id, point, next, out] of [[edge.sourceId, points[0], points[1], true], [edge.targetId, points.at(-1), points.at(-2), false]]) {
      const node = scene.nodes.find(node => node.id === id), port = node.ports.find(port => port.direction === (out ? 'out' : 'in') &&
        port.canonicalEdgeIds.some(id => edge.canonicalEdgeIds.includes(id)) && Math.abs(point.x - port.x) < .15 && Math.abs(point.y - port.y) < .15);
      assert.ok(port, `${edge.id} owned endpoint`);
      const side = Math.abs(port.y - node.y) < .15 ? 'top' : Math.abs(port.y - node.y - node.height) < .15 ? 'bottom' :
        Math.abs(port.x - node.x) < .15 ? 'left' : Math.abs(port.x - node.x - node.width) < .15 ? 'right' : undefined;
      const expected = side === 'top' ? [0, -1] : side === 'bottom' ? [0, 1] : side === 'left' ? [-1, 0] : [1, 0];
      if (side && !equal(direction(point, next), expected)) errors.push({ edge: edge.id, id, side, point, next });
    }
  }
  return errors;
}
function summary(scene) {
  verifyEndpoints(scene);
  const result = metrics(scene), found = intrusions(scene), leafIntrusions = found.filter(item => !scene.nodes.find(node => node.id === item.nodeId)?.expanded), bendHistogram = {};
  for (const route of result.routes) bendHistogram[route.bends] = (bendHistogram[route.bends] ?? 0) + 1;
  const normals = endpointNormals(scene);
  return {
    nodes: scene.nodes.length, leaves: scene.nodes.filter(node => !node.expanded).length, routes: scene.edges.length,
    strictCrossingPairs: result.pairs.filter(pair => pair.crossings.length).length,
    strictCrossings: result.pairs.reduce((sum, pair) => sum + pair.crossings.length, 0),
    positiveOverlapPairs: result.pairs.filter(pair => pair.overlapLength > 1e-6).length,
    distinctTensor: result.distinctTensor, sameTensor: result.sameTensor, disjointOwners: result.disjointOwners,
    totalBends: result.totalBends, totalLength: result.totalLength, totalReversals: result.totalReversals, bendHistogram,
    intrusions: found, leafIntrusions, endpointNormals: normals, pairs: result.pairs,
    layoutDiagnostics: scene.diagnostics.filter(row => row.code?.startsWith('layout-')),
    everyIntrusionReported: leafIntrusions.every(item => scene.diagnostics.some(row => row.code === 'layout-route-blocked' &&
      row.edgeId === item.edgeId && row.objectIds?.includes(item.nodeId))),
  };
}
const states = { baseline: summary(baseline) }, invariants = { inputImmutable: equal(document, JSON.parse(beforeBytes)), deterministic: equal(baseline, buildScene(document)) };
for (const [name, dx, dy] of [['right', 24, 0], ['left', -24, 0], ['up', 0, -24], ['down', 0, 24]]) {
  const operation = move(dx, dy), changed = applyVisualBatch(document, [operation]), committed = buildScene(changed);
  const history = reduceHistory(createHistory(document), { type: 'apply', baseRevision: document.revision, operations: [operation] });
  const undo = reduceHistory(history, { type: 'undo' }), redo = reduceHistory(undo, { type: 'redo' });
  const changedBodies = committed.nodes.filter(node => { const old = baseline.nodes.find(item => item.id === node.id);
    return node.x !== old.x || node.y !== old.y || node.width !== old.width || node.height !== old.height; }).map(node => node.id);
  invariants[name] = {
    architectureImmutable: equal(changed.architecture, document.architecture), sourceDigestUnchanged: committed.sourceDigest === baseline.sourceDigest,
    irDigestUnchanged: committed.irDigest === baseline.irDigest, canonicalBindingsUnchanged: equal(committed.edges.map(({ source, target, tensorId, role, canonicalEdgeIds }) =>
      ({ source, target, tensorId, role, canonicalEdgeIds })), baseline.edges.map(({ source, target, tensorId, role, canonicalEdgeIds }) => ({ source, target, tensorId, role, canonicalEdgeIds }))),
    previewCommitSame: equal(previewMoveScene(prepareMovePreview(document, [selected], 'current-frontier'), dx, dy), committed),
    historyCommitSame: equal(buildScene(history.document), committed), undoRoutesSame: equal(buildScene(undo.document).edges, baseline.edges),
    redoRoutesSame: equal(buildScene(redo.document).edges, committed.edges), changedBodies,
  };
  states[name] = summary(committed);
  assert.ok(Object.values(invariants[name]).filter(value => typeof value === 'boolean').every(Boolean), name);
  assert.deepEqual(changedBodies, [selected]); assert.equal(states[name].endpointNormals.length, 0);
}
assert.equal(JSON.stringify(document), beforeBytes);

const down = buildScene(applyVisualBatch(document, [move(0, 24)]));
const nodeById = new Map(down.nodes.map(node => [node.id, node]));
const rectangles = down.nodes.filter(node => !node.expanded);
const strictInside = (point, node, padding = 0) => point.x > node.x - padding && point.x < node.x + node.width + padding &&
  point.y > node.y - padding && point.y < node.y + node.height + padding;
function segmentEnters(a, b, node) {
  return a.x === b.x ? a.x > node.x && a.x < node.x + node.width && Math.max(Math.min(a.y, b.y), node.y) < Math.min(Math.max(a.y, b.y), node.y + node.height) :
    a.y > node.y && a.y < node.y + node.height && Math.max(Math.min(a.x, b.x), node.x) < Math.min(Math.max(a.x, b.x), node.x + node.width);
}
const gapAnalysis = ['edge:3', 'edge:41'].map(id => {
  const edge = down.edges.find(edge => edge.id === id), points = parsePath(edge.path), start = points[0], end = points.at(-1);
  const first = direction(start, points[1]), last = direction(end, points.at(-2));
  const sourceLead6 = { x: start.x + first[0] * 6, y: start.y + first[1] * 6 }, targetLead6 = { x: end.x + last[0] * 6, y: end.y + last[1] * 6 };
  const foreign = rectangles.filter(node => ![edge.sourceId, edge.targetId].includes(node.id));
  return {
    edgeId: id, sourceId: edge.sourceId, targetId: edge.targetId, currentPath: edge.path, start, end, sourceLead6, targetLead6,
    endpointCoveredByForeignBody: foreign.filter(node => strictInside(start, node) || strictInside(end, node)).map(node => node.id),
    actualSourceLead6Intrusions: foreign.filter(node => segmentEnters(start, sourceLead6, node)).map(node => node.id),
    actualTargetLead6Intrusions: foreign.filter(node => segmentEnters(targetLead6, end, node)).map(node => node.id),
    paddedSourceLead6Inside: foreign.filter(node => strictInside(sourceLead6, node, 6)).map(node => node.id),
    paddedTargetLead6Inside: foreign.filter(node => strictInside(targetLead6, node, 6)).map(node => node.id),
    currentIntrusionSegments: intrusions(down).filter(item => item.edgeId === id).map(item => {
      const obstacle = nodeById.get(item.nodeId);
      return { ...item, body: { x: obstacle.x, y: obstacle.y, width: obstacle.width, height: obstacle.height },
        segments: points.slice(1).map((b, i) => ({ a: points[i], b, segmentIndex: i + 1 })).filter(({ a, b }) => segmentEnters(a, b, obstacle)) };
    }),
  };
});
// These paths are independent geometric counterexamples only. They are never
// written to CanvasDocument, buildScene or the product runtime.
const counterexamples = {};
for (const [name, paths] of [
  ['halfGapSharedLane', { 'edge:3': 'M 207 402 V 405 H 316 V 310 H 425 V 316', 'edge:41': 'M 425 470 V 476 H 316 V 405 H 207 V 408' }],
  ['separateTwoUnitLeads', { 'edge:3': 'M 207 402 V 404 H 316 V 310 H 425 V 316', 'edge:41': 'M 425 470 V 476 H 316 V 406 H 207 V 408' }],
]) {
  const proposed = serializable(down);
  for (const edge of proposed.edges) if (paths[edge.id]) edge.path = paths[edge.id];
  const result = summary(proposed);
  counterexamples[name] = { hypotheticalOnly: true, paths, strictCrossings: result.strictCrossings,
    positiveOverlapPairs: result.positiveOverlapPairs, distinctTensor: result.distinctTensor, sameTensor: result.sameTensor,
    intrusions: result.intrusions, endpointNormals: result.endpointNormals,
    changedPairGeometry: result.pairs.filter(pair => ['edge:3', 'edge:41'].includes(pair.first) || ['edge:3', 'edge:41'].includes(pair.second)) };
}
const upper = nodeById.get(selected), lower = nodeById.get('call:instance:model.DenseStress300.network.39');
const svg = renderSvg(down), marker = svg.match(/<marker[^>]*viewBox="0 0 10 10"[^>]*refX="8\.5"[^>]*refY="5"[^>]*markerWidth="5\.5"[^>]*markerHeight="5\.5"[^>]*><path d="M 1 1 L 9 5 L 1 9 Z"/);
assert.ok(marker, 'actual marker contract changed');
const edge41 = down.edges.find(edge => edge.id === 'edge:41'), end41 = parsePath(edge41.path).at(-1), markerScale = edge41.width * 5.5 / 10;
// SVG markerUnits defaults to strokeWidth. Rotate local marker x into the
// actual downward arrival direction; no product marker geometry is imported.
const triangle41 = [[1, 1], [9, 5], [1, 9]].map(([x, y]) => ({ x: end41.x - (y - 5) * markerScale, y: end41.y + (x - 8.5) * markerScale }));
const markerBase = Math.min(...triangle41.map(point => point.y)), markerTip = Math.max(...triangle41.map(point => point.y));
const penetration = Math.max(0, upper.y + upper.height - markerBase), baseWidth = 8 * markerScale;
const clippedArea = (baseWidth + baseWidth * (1 - penetration / (markerTip - markerBase))) * penetration / 2;
const markerAnalysis = {
  source: 'Frozen formal renderSvg marker contract: viewBox 10x10, refX=8.5/refY=5, markerWidth/Height=5.5, default markerUnits=strokeWidth',
  edgeId: 'edge:41', strokeWidth: edge41.width, scale: markerScale, end: end41, triangle: triangle41,
  foreignNode: upper.id, foreignBottom: upper.y + upper.height, penetrationDepth: penetration, positiveIntersectionArea: clippedArea,
  fixedEndpointAndNormal: 'The marker triangle is identical for every route ending at (207,408) with the existing downward normal. Centerline shortening cannot remove this marker intrusion.',
};
assert.ok(penetration > 0 && clippedArea > 0, 'fixed arrow triangle enters the foreign body');
const report = {
  schema: 'archcanvas-ai-geometry-review/1', actor: 'Independent AI geometry reviewer, not a human participant', build: 'index-B32ccWRJ.js',
  scope: 'Frozen formal core rebuild and independent geometry. Browser screenshots are separately reviewed; this is not human usability, physical publication or presented performance acceptance.',
  invariants, states, narrowGap: { upper: { id: upper.id, bottom: upper.y + upper.height }, lower: { id: lower.id, top: lower.y },
    gap: lower.y - upper.y - upper.height, endpointBodiesOverlap: upper.y + upper.height > lower.y, gapAnalysis },
  counterexamples, markerAnalysis,
  conclusions: {
    currentDownCause: 'No foreign body covers either endpoint and the two facing bodies do not overlap. Exact six-unit endpoint leads touch opposite body boundaries, while required six-unit padding blocks the middle search. Retained thirteen-unit preferred escapes and right-side corridors enter six unrelated leaf bodies.',
    halfGapIsInsufficient: 'Uniform three-unit leads both use y=405 and create a new 109-unit different-tensor horizontal trunk; body clearance alone would miss this regression.',
    geometricPossibility: 'Two-unit separated lead lanes at y=404 and y=406 provide a body-safe orthogonal counterexample, so the current failure is not proved topologically impossible. These paths do not certify stroke separation, padded clearance, publication size or guarded product acceptance.',
    markerLimit: 'The actual edge:41 arrow triangle enters the selected node body by 0.1875 world units with positive fill area. This persists for a shortened body-clear centerline at the fixed target/normal; routing alone cannot certify all rendered geometry clear.',
    visualRisk: '38 strict baseline crossings, four bends on 286 of 302 routes, and 44 crossings plus six body intrusions after down movement remain visually complex. Reduced crossings alone does not establish an attractive or readable dense research figure.',
    acceptance: 'M4 remains partial; all observations are AI simulation evidence and add zero real human trials.',
  },
};
writeFileSync(new URL('./report.json', import.meta.url), JSON.stringify(report, null, 2));
console.log(JSON.stringify({ states: Object.fromEntries(Object.entries(states).map(([name, value]) => [name, {
  strictCrossings: value.strictCrossings, overlapPairs: value.positiveOverlapPairs, intrusions: value.leafIntrusions.length,
  bendHistogram: value.bendHistogram, endpointNormalErrors: value.endpointNormals.length }])) , gapAnalysis, counterexamples, conclusions: report.conclusions }, null, 2));
