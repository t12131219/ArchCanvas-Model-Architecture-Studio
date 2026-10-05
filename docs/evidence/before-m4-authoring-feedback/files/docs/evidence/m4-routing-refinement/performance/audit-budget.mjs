import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { cpSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const directory = dirname(fileURLToPath(import.meta.url));
const args = new Map();
for (let index = 2; index < process.argv.length; index += 2) args.set(process.argv[index], process.argv[index + 1]);
const sourceCore = resolve(args.get('--core'));
const copiedCore = resolve(args.get('--trace-core'));
const output = resolve(args.get('--output'));
assert.equal(existsSync(copiedCore), false, 'refuse overwrite of trace source');
cpSync(sourceCore, copiedCore, { recursive: true });
const hash = value => createHash('sha256').update(value).digest('hex');
const path = join(copiedCore, 'orthogonalRouter.ts'), original = readFileSync(path, 'utf8');
const resultsAnchor = '    const results = requests.map(route);';
const budgetAnchor = '    const budget = { segmentChecks: 0, obstacleChecks: 0, pairChecks: 0, candidates: 0, refinedRoutes: 0 };';
assert.equal(original.split(resultsAnchor).length, 2, 'one public batch result instrumentation anchor');
assert.equal(original.split(budgetAnchor).length, 2, 'one local budget instrumentation anchor');
const traced = original.replace(resultsAnchor, resultsAnchor + '\n    const auditCall: any = { nodes: nodes.length, routes: requests.length, routePoints: results.reduce((total, result) => total + result.points.length, 0) };\n    (globalThis as any).__ARCHCANVAS_ROUTE_CPU_TRACE__.push(auditCall);')
  .replace(budgetAnchor, budgetAnchor + '\n    auditCall.budget = budget;');
writeFileSync(path, traced);
globalThis.__ARCHCANVAS_ROUTE_CPU_TRACE__ = [];
const core = await import(pathToFileURL(join(sourceCore, 'index.ts')).href);
const tracedCoreApi = await import(pathToFileURL(join(copiedCore, 'index.ts')).href);
const directRouter = await import(pathToFileURL(join(sourceCore, 'orthogonalRouter.ts')).href);
const tracedRouter = await import(pathToFileURL(join(copiedCore, 'orthogonalRouter.ts')).href);
const preview = await import(pathToFileURL(join(sourceCore, 'movePreview.ts')).href);
const tracedPreview = await import(pathToFileURL(join(copiedCore, 'movePreview.ts')).href);
const caps = directRouter.ROUTE_REFINEMENT_BUDGET;
assert.deepEqual(caps, tracedRouter.ROUTE_REFINEMENT_BUDGET);
const inputRecords = ['baseline-manifest.json', 'density-inputs.json', 'wide-inputs.json'].flatMap(name => JSON.parse(readFileSync(join(directory, name))).inputFiles);
const records = [];
const checkCounters = calls => {
  for (const call of calls) {
    if (!call.budget) continue;
    assert.ok(call.nodes <= caps.maxNodes && call.routes <= caps.maxRoutes && call.routePoints <= caps.maxRoutePoints, 'gates precede budgeted refinement');
    for (const [name, cap] of [['pairChecks', 'maxPairChecks'], ['segmentChecks', 'maxSegmentChecks'], ['obstacleChecks', 'maxObstacleChecks'], ['candidates', 'maxCandidates']]) {
      assert.ok(call.budget[name] <= caps[cap] + 1, `${name} cap plus single rejected attempt`);
    }
    assert.ok(call.budget.refinedRoutes <= caps.maxRefinedRoutes);
  }
};
const capture = (name, operation) => {
  globalThis.__ARCHCANVAS_ROUTE_CPU_TRACE__ = [];
  const value = operation();
  const calls = structuredClone(globalThis.__ARCHCANVAS_ROUTE_CPU_TRACE__);
  checkCounters(calls);
  records.push({ name, calls });
  return value;
};
for (const input of inputRecords) {
  const bytes = readFileSync(join(directory, input.path));
  assert.equal(hash(bytes), input.sha256);
  const document = JSON.parse(bytes);
  const scene = core.buildScene(document);
  assert.deepEqual(capture(`${input.id}:buildScene`, () => tracedCoreApi.buildScene(document)), scene);
  const leaf = scene.nodes.find(node => !node.expandable && !node.pinned && !node.boundary);
  const detail = [...scene.nodes].reverse().find(node => node.expanded && node.expandable);
  const session = preview.prepareMovePreview(document, [leaf.id]);
  const tracedSession = capture(`${input.id}:prepare`, () => tracedPreview.prepareMovePreview(document, [leaf.id]));
  for (const [dx, dy, direction] of [[16, 0, 'right'], [-16, 0, 'left'], [0, 16, 'down'], [0, -16, 'up']]) {
    const expected = preview.previewMoveScene(session, dx, dy);
    assert.deepEqual(capture(`${input.id}:preview-${direction}`, () => tracedPreview.previewMoveScene(tracedSession, dx, dy)), expected);
    const actualCommit = capture(`${input.id}:commit-${direction}`, () => {
      const history = tracedCoreApi.reduceHistory(tracedCoreApi.createHistory(document), { type: 'apply', operations: [{ type: 'move', ids: [leaf.id], dx, dy }] });
      return tracedCoreApi.buildScene(history.document);
    });
    assert.deepEqual(actualCommit, expected);
  }
  assert.deepEqual(capture(`${input.id}:detail`, () => tracedCoreApi.buildExportScene(document, { nodeId: detail.id })), core.buildExportScene(document, { nodeId: detail.id }));
}

// Explicit geometry-only public API gates, including one budget saturation.
const density = JSON.parse(readFileSync(join(directory, 'inputs/synthetic-density-4.canvas.json')));
const scene = core.buildScene(density), edge = scene.edges[0];
const points = directRouter.orthogonalPathPoints(edge.path);
const request = { sourceId: edge.sourceId, targetId: edge.targetId, start: points[0], end: points.at(-1), preferredPath: edge.path };
const requests = count => Array.from({ length: count }, () => ({ ...request }));
const gateResults = [];
function gate(name, nodes, reqs, requireNoBudget) {
  const expected = directRouter.createOrthogonalRouter(nodes).batch(reqs);
  const actual = capture(name, () => tracedRouter.createOrthogonalRouter(nodes).batch(reqs));
  assert.deepEqual(actual, expected, 'trace instrumentation does not change entire public batch result');
  const calls = records.at(-1).calls;
  assert.equal(calls.length, 1);
  if (requireNoBudget) assert.equal(calls[0].budget, undefined, 'oversize input returns baseline routes before refinement');
  gateResults.push({ name, calls, wholeResultSha256: hash(JSON.stringify(actual)) });
}
gate('maxRoutes-plus-one', scene.nodes, requests(caps.maxRoutes + 1), true);
const extraNodes = Array.from({ length: caps.maxNodes + 1 - scene.nodes.length }, (_, index) => ({ ...scene.nodes[1], id: `far-${index}`,
  parentId: undefined, x: 10000, y: 2000 + index * 100, width: 50, height: 40, expanded: false, ports: [] }));
gate('maxNodes-plus-one', [...scene.nodes, ...extraNodes], requests(2), true);
const repeatedPath = `M ${points[0].x} ${points[0].y} ` + Array.from({ length: caps.maxRoutePoints }, () => `V ${points[0].y}`).join(' ') +
  ` H ${points.at(-1).x} V ${points.at(-1).y}`;
gate('maxRoutePoints-plus-one', scene.nodes, [{ ...request, preferredPath: repeatedPath }, { ...request }], true);
gate('maxRoutes-dense-pair-saturation', scene.nodes, requests(caps.maxRoutes), false);
assert.ok(gateResults.at(-1).calls[0].budget.pairChecks >= caps.maxPairChecks || gateResults.at(-1).calls[0].budget.segmentChecks >= caps.maxSegmentChecks,
  'adversarial dense batch reaches an explicit broad-phase or segment cap');
writeFileSync(output, JSON.stringify({ schemaVersion: 1, status: 'passed-bounded-work-audit', caps,
  sourceCore, traceCore: copiedCore, originalRouterSha256: hash(original), instrumentedRouterSha256: hash(traced),
  scriptSha256: hash(readFileSync(fileURLToPath(import.meta.url))), inputFiles: inputRecords, publicPathCount: records.length,
  records, gateResults, limitations: ['Counters come from a separately instrumented source copy and are excluded from CPU timing.',
    'Instrumentation only stores references to existing local counters; entire Scene and batch outputs are checked against the unmodified measured core.',
    'Caps bound added batch refinement; they do not cap the existing obstacle router, document validation, layout, rendering or browser work.',
    'A capped exit retains obstacle-router results and may leave crossings/overlaps unresolved.'] }, null, 2) + '\n');
console.log(JSON.stringify({ output, publicPathCount: records.length, caps, gateResults }, null, 2));
