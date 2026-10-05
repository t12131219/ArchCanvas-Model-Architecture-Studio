import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { cpSync, mkdirSync, readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { performance } from 'node:perf_hooks';
import { fileURLToPath, pathToFileURL } from 'node:url';

// This oracle reads geometry independently. It imports no routing parser or
// collision helper and never uses the rendered result as an expected snapshot.
const project = fileURLToPath(new URL('../../../../', import.meta.url));
const output = fileURLToPath(new URL('./audit.json', import.meta.url));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const load = path => JSON.parse(readFileSync(`${project}${path}`, 'utf8'));
const codeDigests = directory => Object.fromEntries(readdirSync(directory).filter(name => name.endsWith('.ts')).sort().map(name => [name, sha(readFileSync(`${directory}/${name}`))]));
const liveCodeDigests = codeDigests(`${project}studio/src/core`);
const snapshot = fileURLToPath(new URL(`./source-snapshots/${sha(JSON.stringify(liveCodeDigests)).slice(0, 16)}/`, import.meta.url));
mkdirSync(snapshot, { recursive: true }); cpSync(`${project}studio/src/core`, snapshot, { recursive: true });
assert.deepEqual(codeDigests(snapshot), liveCodeDigests);
const { buildScene, buildExportScene, createDocument, applyVisualBatch, createHistory, reduceHistory, renderSvg } = await import(pathToFileURL(`${snapshot}/index.ts`).href);
const { prepareMovePreview, previewMoveScene } = await import(pathToFileURL(`${snapshot}/movePreview.ts`).href);
const { createOrthogonalRouter } = await import(pathToFileURL(`${snapshot}/orthogonalRouter.ts`).href);
const baselineCore = await import(pathToFileURL(`${project}docs/evidence/before-routing-obstacle-fix/files/studio/src/core/index.ts`).href);
function parse(path) {
  const tokens = path.match(/[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?/gi) ?? [];
  const vertices = []; let x = 0, y = 0;
  for (let i = 0; i < tokens.length;) {
    const command = tokens[i++];
    if (command === 'M' || command === 'L') { x = Number(tokens[i++]); y = Number(tokens[i++]); }
    else if (command === 'H') x = Number(tokens[i++]);
    else if (command === 'V') y = Number(tokens[i++]);
    else throw new Error(`Unsupported command ${command}`);
    assert.ok(Number.isFinite(x) && Number.isFinite(y)); vertices.push([x, y]);
  }
  assert.ok(vertices.length > 1);
  for (let i = 1; i < vertices.length; i++) assert.ok(vertices[i - 1][0] === vertices[i][0] || vertices[i - 1][1] === vertices[i][1], 'Diagonal segment');
  return vertices;
}
function intersectsInterior(a, b, rectangle, tolerance = 1e-7) {
  const left = rectangle.x + tolerance, right = rectangle.x + rectangle.width - tolerance;
  const top = rectangle.y + tolerance, bottom = rectangle.y + rectangle.height - tolerance;
  if (a[0] === b[0]) return a[0] > left && a[0] < right && Math.max(Math.min(a[1], b[1]), top) < Math.min(Math.max(a[1], b[1]), bottom);
  return a[1] > top && a[1] < bottom && Math.max(Math.min(a[0], b[0]), left) < Math.min(Math.max(a[0], b[0]), right);
}
function inspect(scene) {
  const byId = new Map(scene.nodes.map(node => [node.id, node]));
  function ancestors(id) { const ids = new Set(); let node = byId.get(id); while (node?.parentId && !ids.has(node.parentId)) { ids.add(node.parentId); node = byId.get(node.parentId); } return ids; }
  const unrelated = [], endpointBodies = [], headers = [], detached = [], clipped = [], overlaidHeaderObjects = [];
  for (const node of scene.nodes) for (const parentId of ancestors(node.id)) {
    const parent = byId.get(parentId);
    if (parent?.expanded && Math.min(node.x + node.width, parent.x + parent.width) > Math.max(node.x, parent.x) + 1e-7 &&
      Math.min(node.y + node.height, parent.y + parent.headerHeight) > Math.max(node.y, parent.y) + 1e-7) overlaidHeaderObjects.push({ node: node.id, header: parent.id });
  }
  for (const edge of scene.edges) {
    const points = parse(edge.path), parents = new Set([...ancestors(edge.sourceId), ...ancestors(edge.targetId)]);
    const endpoints = new Set([edge.sourceId, edge.targetId]);
    for (const [nodeId, direction, endpoint] of [[edge.sourceId, 'out', points[0]], [edge.targetId, 'in', points.at(-1)]]) {
      const ports = byId.get(nodeId)?.ports.filter(port => port.direction === direction && port.canonicalEdgeIds.some(id => edge.canonicalEdgeIds.includes(id))) ?? [];
      if (!ports.some(port => Math.hypot(port.x - endpoint[0], port.y - endpoint[1]) <= .151)) detached.push({ edge: edge.id, direction, endpoint });
    }
    for (const point of points) if (point[0] < scene.bounds.x - .001 || point[1] < scene.bounds.y - .001 || point[0] > scene.bounds.x + scene.bounds.width + .001 || point[1] > scene.bounds.y + scene.bounds.height + .001) clipped.push({ edge: edge.id, point });
    for (const node of scene.nodes) {
      const segments = points.slice(1).map((b, i) => [points[i], b]);
      if (segments.some(([a, b]) => intersectsInterior(a, b, node))) {
        const record = { edge: edge.id, node: node.id };
        if (endpoints.has(node.id)) endpointBodies.push(record);
        else if (!parents.has(node.id)) unrelated.push(record);
      }
      if (node.expanded && segments.some(([a, b]) => intersectsInterior(a, b, { ...node, height: node.headerHeight }))) headers.push({ edge: edge.id, header: node.id });
    }
  }
  return { unrelated, endpointBodies, headers, detached, clipped, overlaidHeaderObjects };
}
function sceneNode(id, x, y, width = 20, height = 20, parentId) {
  return { id, x, y, width, height, parentId, localX: x, localY: y, label: id, subtitle: '', headerHeight: 20,
    kind: 'Linear', category: 'linear', fill: '#fff', stroke: '#000', glyph: 'operator', expanded: false, expandable: false, pinned: false, evidence: 'source', ports: [] };
}
function routeTest(name, nodes, start, end, preferredPath) {
  const original = JSON.stringify(nodes), router = createOrthogonalRouter(nodes);
  const begin = performance.now(), route = router({ sourceId: 'a', targetId: 'b', start, end, preferredPath });
  const ms = performance.now() - begin, vertices = parse(route.path);
  assert.equal(JSON.stringify(nodes), original, `${name}: mutated nodes`);
  assert.ok(Math.hypot(vertices[0][0] - start.x, vertices[0][1] - start.y) <= .015);
  assert.ok(Math.hypot(vertices.at(-1)[0] - end.x, vertices.at(-1)[1] - end.y) <= .015);
  const hits = nodes.filter(node => vertices.slice(1).some((b, i) => intersectsInterior(vertices[i], b, node))).map(node => node.id);
  const visibleInteriorHits = nodes.filter(node => vertices.slice(1).some((b, i) => intersectsInterior(vertices[i], b, node, .02))).map(node => node.id);
  const headerHits = nodes.filter(node => node.expanded && vertices.slice(1).some((b, i) => intersectsInterior(vertices[i], b, { ...node, height: node.headerHeight }))).map(node => node.id);
  const expectedOverlaps = [];
  const byId = new Map(nodes.map(node => [node.id, node]));
  const isAncestor = (first, second) => { let node = byId.get(second), seen = new Set(); while (node?.parentId && !seen.has(node.parentId)) { if (node.parentId === first) return true; seen.add(node.parentId); node = byId.get(node.parentId); } return false; };
  for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
    const a = nodes[i], b = nodes[j];
    if (!isAncestor(a.id, b.id) && !isAncestor(b.id, a.id) && Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x) > .01 && Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y) > .01) expectedOverlaps.push([a.id, b.id].sort().join('\0'));
  }
  assert.deepEqual(router.overlaps.map(item => [item.first, item.second].sort().join('\0')).sort(), expectedOverlaps.sort(), `${name}: overlap broad-phase mismatch`);
  return { name, ms, ...route, hits, visibleInteriorHits, headerHits, overlaps: router.overlaps };
}
const counterexamples = [];
// An independent oracle must first detect the deliberately corrupt crossing.
assert.equal(intersectsInterior([10, 60], [110, 60], { x: 50, y: 40, width: 40, height: 40 }), true);
assert.equal(intersectsInterior([10, 39], [110, 39], { x: 50, y: 40, width: 40, height: 40 }), false);
counterexamples.push(routeTest('unrelated-body', [sceneNode('a', 0, 0), sceneNode('b', 100, 100), sceneNode('obstacle', 50, 40, 40, 40)], { x: 10, y: 20 }, { x: 110, y: 100 }, 'M 10 20 V 60 H 110 V 100'));
counterexamples.push(routeTest('preferred-source-body-reentry', [sceneNode('a', 0, 0), sceneNode('b', 100, 100)], { x: 10, y: 20 }, { x: 110, y: 100 }, 'M 10 20 V 10 H 110 V 100'));
const frame = { ...sceneNode('frame', -10, -10, 140, 150), expanded: true, expandable: true, headerHeight: 30 };
counterexamples.push(routeTest('preferred-ancestor-header', [frame, sceneNode('a', 0, 40, 20, 20, 'frame'), sceneNode('b', 100, 100, 20, 20, 'frame')], { x: 10, y: 60 }, { x: 110, y: 100 }, 'M 10 60 V 0 H 110 V 100'));
counterexamples.push(routeTest('decimal-negative', [sceneNode('a', -80.337, -30.771), sceneNode('b', 10.662, 70.229), sceneNode('obstacle', -39.337, 10.229, 40, 40)], { x: -70.337, y: -10.771 }, { x: 20.662, y: 70.229 }, 'M -70.337 -10.771 V 30.229 H 20.662 V 70.229'));
counterexamples.push(routeTest('covered-endpoint-honest-fallback', [sceneNode('a', 0, 0), sceneNode('b', 100, 100), sceneNode('obstacle', 0, 15, 20, 30)], { x: 10, y: 20 }, { x: 110, y: 100 }, 'M 10 20 V 60 H 110 V 100'));
const mazeNodes = [sceneNode('a', 0, 0), sceneNode('b', 100, 100), sceneNode('source-left', -20, -10, 20, 90),
  sceneNode('source-right', 20, -10, 20, 90), sceneNode('target-left', 80, 50, 20, 80), sceneNode('target-right', 120, 50, 20, 80)];
const maze = routeTest('multi-bend-maze-grid-fallback', mazeNodes, { x: 10, y: 20 }, { x: 110, y: 100 }, 'M 10 20 V 60 H 110 V 100');
assert.equal(maze.changed, true); assert.deepEqual(maze.blockedBy, []); assert.deepEqual(maze.visibleInteriorHits, []); assert.ok(maze.points.length >= 6);
counterexamples.push(maze);
// The same known clear multi-bend route still exists after adding distant
// noninterfering boxes; a grid-budget fallback must report the original clash.
const bounded = routeTest('300-box-grid-budget-honest-fallback', [...mazeNodes, ...Array.from({ length: 294 }, (_, i) => sceneNode(`distant-${i}`, 1000 + i * 13, 1000 + i * 17, 3, 3))],
  { x: 10, y: 20 }, { x: 110, y: 100 }, 'M 10 20 V 60 H 110 V 100');
assert.equal(bounded.changed, false); assert.ok(bounded.blockedBy.length); counterexamples.push(bounded);
assert.deepEqual(counterexamples[0].visibleInteriorHits, []);
assert.deepEqual(counterexamples[1].visibleInteriorHits, []);
assert.deepEqual(counterexamples[2].headerHits, []);
assert.deepEqual(counterexamples[3].visibleInteriorHits, []);
assert.deepEqual(counterexamples[4].blockedBy, ['obstacle']);
assert.deepEqual([...bounded.blockedBy].sort(), [...bounded.visibleInteriorHits].sort());
const suffixFrame = { ...frame, id: 'frame#header' };
const suffixCollision = routeTest('literal-header-suffix-identity', [suffixFrame, sceneNode('a', 0, -10, 20, 20, suffixFrame.id), sceneNode('b', 100, 100, 20, 20, suffixFrame.id)],
  { x: 10, y: 10 }, { x: 110, y: 100 }, 'M 10 10 V 60 H 110 V 100');
assert.deepEqual(suffixCollision.blockedBy, ['frame#header']); counterexamples.push(suffixCollision);
let randomState = 0x524f5554;
const random = limit => { randomState = (Math.imul(randomState, 1664525) + 1013904223) >>> 0; return randomState % limit; };
const randomFields = [];
for (let trial = 0; trial < 120; trial++) {
  const obstacles = Array.from({ length: 12 }, (_, i) => sceneNode(`obstacle-${i}`, 35 + random(130), 25 + random(120), 5 + random(22), 5 + random(24)));
  const route = routeTest(`seeded-integer-field-${trial}`, [sceneNode('a', 0, 0), sceneNode('b', 180, 180), ...obstacles],
    { x: 10, y: 20 }, { x: 190, y: 180 }, 'M 10 20 V 100 H 190 V 180');
  if (!route.blockedBy.length) assert.deepEqual(route.visibleInteriorHits, [], route.name);
  else assert.deepEqual([...route.blockedBy].sort(), [...route.visibleInteriorHits].sort(), route.name);
  randomFields.push(route);
}
const manifest = load('docs/evidence/browser-visual-matrix-boundary-final/manifest.json');
const matrix = [], baselineMatrix = [], details = []; let snapshots = new Set();
for (const entry of manifest.captures) {
  const path = `docs/evidence/browser-visual-matrix-boundary-final/${entry.files.canvas.path}`;
  const inputBytes = readFileSync(`${project}${path}`), document = JSON.parse(inputBytes), before = JSON.stringify(document);
  const scene = buildScene(document), baselineScene = baselineCore.buildScene(document); matrix.push({ caseId: entry.caseId, inputSha256: sha(inputBytes), ...inspect(scene) });
  baselineMatrix.push({ caseId: entry.caseId, inputSha256: sha(inputBytes), ...inspect(baselineScene) });
  assert.deepEqual(scene.sourceFacts, baselineScene.sourceFacts, `${entry.caseId}: source facts changed`);
  assert.deepEqual(scene.edges.flatMap(edge => edge.canonicalEdgeIds).concat(scene.hiddenEdges).sort(), document.architecture.edges.map(edge => edge.id).sort(), `${entry.caseId}: canonical coverage changed`);
  const semanticEdges = value => value.edges.map(({ id, sourceId, targetId, source, target, canonicalEdgeIds, tensorId, role, stroke, width, dashed, label }) => ({ id, sourceId, targetId, source, target, canonicalEdgeIds, tensorId, role, stroke, width, dashed, label }));
  assert.deepEqual(semanticEdges(scene), semanticEdges(baselineScene), `${entry.caseId}: projected binding/style changed`);
  const key = `${entry.fixture}:${JSON.stringify(document.expandedIds)}:${entry.state}`;
  if (!snapshots.has(key)) {
    snapshots.add(key);
    for (const node of scene.nodes.filter(node => node.expanded && node.expandable)) details.push({ caseId: entry.caseId, nodeId: node.id, ...inspect(buildExportScene(document, { nodeId: node.id })) });
  }
  assert.equal(JSON.stringify(document), before, `${entry.caseId}: scene/export mutated document`);
}
for (const item of [...matrix, ...details]) for (const key of ['unrelated', 'endpointBodies', 'headers', 'detached', 'clipped']) assert.deepEqual(item[key], [], `${item.caseId}:${item.nodeId ?? 'whole'}:${key}`);
const headerDocument = load('docs/evidence/browser-visual-matrix-boundary-final/captures/mlp-level1-paper-180/canvas.json');
const headerBefore = buildScene(headerDocument), child = headerBefore.nodes.find(node => node.id === 'call:instance:model.MLP.network.0');
const parent = headerBefore.nodes.find(node => node.id === child.parentId);
const manualHeader = buildScene(applyVisualBatch(headerDocument, [{ type: 'move', ids: [child.id], dx: 0, dy: parent.y + 10 - child.y }]));
const manualHeaderResult = { nodeId: child.id, ...inspect(manualHeader), diagnostics: manualHeader.diagnostics };
assert.ok(manualHeaderResult.overlaidHeaderObjects.some(item => item.node === child.id && item.header === parent.id));
assert.ok(manualHeader.diagnostics.some(diagnostic => diagnostic.message.includes(child.id) && diagnostic.message.includes('header')));
assert.ok(manualHeader.diagnostics.some(diagnostic => diagnostic.code === 'layout-header-overlap' && diagnostic.objectIds.includes(child.id) && diagnostic.objectIds.includes(parent.id)));
const stress = load('docs/evidence/m4-current-core-benchmark/architecture.json');
for (const source of stress.sources) { assert.equal(sha(source.content), source.digest); assert.equal(sha(readFileSync(`${project}fixtures/stress_300/${source.path}`)), source.digest); }
let stressDocument = createDocument(stress);
for (const node of stress.nodes.filter(node => node.children.length)) if (!stressDocument.expandedIds.includes(node.id)) stressDocument = applyVisualBatch(stressDocument, [{ type: 'expand', id: node.id, expanded: true }]);
const stressScene = buildScene(stressDocument);
const leaf = stressScene.nodes.filter(node => !node.expandable)[Math.floor(stressScene.nodes.filter(node => !node.expandable).length / 2)];
const stressOriginal = JSON.stringify(stressDocument), trials = [], session = prepareMovePreview(stressDocument, [leaf.id]);
for (let i = 0; i < 12; i++) {
  const [dx, dy] = [[-300, 0], [300, 0], [0, -180], [0, 180]][i % 4];
  const begin = performance.now(), preview = previewMoveScene(session, dx, dy), previewMs = performance.now() - begin;
  const history = reduceHistory(createHistory(stressDocument), { type: 'apply', operations: [{ type: 'move', ids: [leaf.id], dx, dy }], baseRevision: session.baseRevision });
  const committed = buildScene(history.document); assert.deepEqual(preview, committed); assert.equal(renderSvg(preview), renderSvg(committed));
  const undo = reduceHistory(history, { type: 'undo' }), redo = reduceHistory(undo, { type: 'redo' });
  assert.deepEqual(undo.document.layout, stressDocument.layout); assert.deepEqual(redo.document.layout, history.document.layout);
  assert.equal(history.past.length, 1); assert.deepEqual(history.document.architecture, stressDocument.architecture);
  const geometry = inspect(preview);
  for (const intrusion of [...geometry.unrelated, ...geometry.endpointBodies]) assert.ok(preview.diagnostics.some(diagnostic => diagnostic.code === 'layout-route-blocked' && diagnostic.edgeId === intrusion.edge && diagnostic.objectIds.includes(intrusion.node)), `Missing structured warning for ${intrusion.edge}:${intrusion.node}`);
  trials.push({ dx, dy, previewMs, diagnostics: preview.diagnostics, ...geometry });
}
assert.equal(JSON.stringify(stressDocument), stressOriginal);
const hashes = codeDigests(snapshot);
const result = { schemaVersion: 1, protocol: 'archcanvas-independent-routing-review/1', recordedAt: new Date().toISOString(),
  scope: 'CPU source geometry review. Historical matrix canvas inputs rerendered with candidate source, not browser captures. No human, publication, presented performance or aesthetic acceptance.',
  sourceHashes: hashes, candidateSourceSnapshot: snapshot, baselineSourceHashes: codeDigests(`${project}docs/evidence/before-routing-obstacle-fix/files/studio/src/core`), scriptSha256: sha(readFileSync(fileURLToPath(import.meta.url))), liveMatchesAtEnd: JSON.stringify(codeDigests(`${project}studio/src/core`)) === JSON.stringify(liveCodeDigests), matrixCases: matrix.length, baselineMatrix, matrix, details, counterexamples,
  randomFields: { seed: '0x524f5554', cases: randomFields.length, trials: randomFields }, manualHeader: manualHeaderResult,
  stress: { inputSha256: sha(readFileSync(`${project}docs/evidence/m4-current-core-benchmark/architecture.json`)), nodes: stressScene.nodes.length, edges: stressScene.edges.length, movedNode: leaf.id, initial: inspect(stressScene), trials },
  oracleCounterexampleControlsPassed: true, immutabilityPassed: true, canonicalCoverageAndSourceFactPreservationPassed: true, structuredConflictDiagnosticsPassed: true, overlapBroadPhaseVsBruteForcePassed: true, stressPreviewCommitSvgHistoryEqualityPassed: true,
  limitations: ['The router avoids bodies and expanded headers but does not minimize edge-edge crossings or reserve separate parallel corridors.',
    'The fallback search grid is capped at 40000cells. A300box constructed maze records a warning despite a known clear multi-bend route outside its single-corridor search.',
    'Geometry is serialized to0.01units and collision detection uses0.01tolerance. The fractionalnegative counterexample ends0.001inside a target body by numericalrounding; strict mathematicalzero is not claimed.',
    'The CPU trial timings include warm-up and possible host contention and are diagnostics, not browser, display, or beta performance acceptance.'],
  humanAcceptanceCertified: false, publicationAcceptanceCertified: false, browserPerformanceCertified: false };
writeFileSync(output, JSON.stringify(result, null, 2) + '\n');
for (const key of ['unrelated', 'endpointBodies', 'headers', 'detached', 'clipped']) console.log(`${key}: before=${baselineMatrix.reduce((n, x) => n + x[key].length, 0)} full=${matrix.reduce((n, x) => n + x[key].length, 0)} detail=${details.reduce((n, x) => n + x[key].length, 0)}`);
console.log(JSON.stringify({ matrixCases: matrix.length, detailCases: details.length, sourceHashes: hashes, counterexamples: counterexamples.map(({ name, changed, blockedBy, hits, ms }) => ({ name, changed, blockedBy, hits, ms })) }, null, 2));
