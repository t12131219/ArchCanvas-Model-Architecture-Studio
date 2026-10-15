#!/usr/bin/env node
/* Static source-grounded catalog matrix. Formal or explicitly frozen browser engines. */
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { spawn } = require('node:child_process'), { createHash } = require('node:crypto');
const { gzipSync } = require('node:zlib');
const studio = path.resolve(__dirname, '..'), project = path.dirname(studio), preview = path.join(studio, 'public/preview');
const argumentsFor = key => process.argv[process.argv.indexOf(key) + 1];
const option = (key, fallback) => process.argv.includes(key) ? argumentsFor(key) : fallback;
const runtime = path.resolve(option('--runtime-dir', path.join(preview, 'yworks_edge_router_lab')));
const contactHelper = option('--contact-metric-helper', '') ? path.resolve(option('--contact-metric-helper', '')) : null;
const engineFiles = ['router.js', 'physical-ports.js', 'junction-markers.js', 'route-labels.js',
  'source-contracts.js', 'semantic-constraints.js', 'graph-engine.js', 'recursive-graph.js'];
const hash = value => createHash('sha256').update(value).digest('hex');
const catalog = JSON.parse(fs.readFileSync(path.join(preview, 'data/catalog.json')));
const output = path.resolve(option('--output', path.join(project, 'docs/evidence/preview-generalization-20261014')));
const phase = option('--phase', 'mixed');
const includeHistorical = process.argv.includes('--include-historical');

function executeCase(item) {
  const context = vm.createContext({ performance });
  for (const name of engineFiles) vm.runInContext(fs.readFileSync(path.join(runtime, name), 'utf8'), context, { filename: name });
  if (contactHelper) vm.runInContext(fs.readFileSync(contactHelper, 'utf8'), context, { filename: contactHelper });
  const F = context.SummaryRecursive, E = context.SummaryEngine, C = context.SummaryConstraints, R = context.EdgeRouterLabRouting;
  // An archived router may predate this diagnostic. A standalone helper is
  // loaded into a separate namespace; routing and validation remain frozen.
  const wireContacts = contactHelper ? context.ArchCanvasContactMetric?.wireContacts : R.wireContacts;
  if (typeof wireContacts !== 'function') throw Error('Runtime has no wireContacts diagnostic; provide --contact-metric-helper');
  const sources = Object.fromEntries(item.views.filter(view => view.json).map(view => [view.key,
    C.initialize(JSON.parse(fs.readFileSync(path.join(preview, view.json))))]));
  const doc = F.create(sources), initial = F.build(doc), baseline = hash(JSON.stringify(doc.authority));
  const result = { id: item.id, title: item.title, collection: item.collection, historical: !!item.historical, phase,
    presentationVersion: doc.presentationVersion, authoritySha256: baseline,
    inputHashes: Object.fromEntries(item.views.filter(view => view.json).map(view => [view.json, hash(fs.readFileSync(path.join(preview, view.json)))])),
    stages: [], status: 'passed' };
  const depth = id => { let node = doc.authority.detail.nodes.find(node => node.id === id), depth = 0; while (node?.parent) { depth++; node = doc.authority.detail.nodes.find(parent => parent.id === node.parent); } return depth; };
  const containers = F.containers(doc.authority).filter(id => !doc.authority.mandatory.includes(id));
  const recorded = Object.entries(sources).map(([key, graph]) => {
    const check = E.validateView(graph);
    return { view: key, source: check.source.ok, layout: check.layout.ok, invalidEdges: check.edges.filter(([, check]) => !check.ok), contacts: check.routing.contacts };
  });
  result.recordedViews = recorded;
  const progressFile = path.join(output, 'cases', phase + '-' + item.id + '.progress.json');
  fs.mkdirSync(path.dirname(progressFile), { recursive: true });
  function quality(graph) {
    const stats = R.stats(graph.edges); let unrelatedCrossings = 0, unrelatedContacts = 0, unrelatedTouches = 0,
      nearParallelRuns = 0, nearParallelLength = 0, minimumParallelGap = null;
    for (let k = 0; k < graph.edges.length; k++) for (let l = k + 1; l < graph.edges.length; l++) {
      const a = graph.edges[k], b = graph.edges[l];
      if (a.contract?.wire === b.contract?.wire || E.sharesPresentation(graph, a, b)) continue;
      const contacts = wireContacts(a.route, b.route);
      unrelatedContacts += contacts.length; unrelatedTouches += contacts.filter(contact => contact.kind === 'touch').length;
      for (let i = 1; i < a.route.length; i++) for (let j = 1; j < b.route.length; j++) {
        const p = a.route[i - 1], q = a.route[i], u = b.route[j - 1], v = b.route[j];
        if (R.crossing(p, q, u, v)) unrelatedCrossings++;
        if (i === 1 || i === a.route.length - 1 || j === 1 || j === b.route.length - 1) continue;
        const vertical = Math.abs(p.x - q.x) < 1e-5, horizontal = Math.abs(p.y - q.y) < 1e-5;
        if ((!vertical && !horizontal) || (vertical ? Math.abs(u.x - v.x) >= 1e-5 : Math.abs(u.y - v.y) >= 1e-5)) continue;
        const axis = vertical ? 'x' : 'y', along = vertical ? 'y' : 'x', gap = Math.abs(p[axis] - u[axis]);
        const overlap = Math.min(Math.max(p[along], q[along]), Math.max(u[along], v[along])) - Math.max(Math.min(p[along], q[along]), Math.min(u[along], v[along]));
        if (gap < 10 - 1e-5 && overlap > 1e-5) { nearParallelRuns++; nearParallelLength += overlap; minimumParallelGap = Math.min(minimumParallelGap ?? Infinity, gap); }
      }
    }
    return { ...stats, unrelatedCrossings, unrelatedContacts, unrelatedTouches, nearParallelRuns, nearParallelLength, minimumParallelGap,
      nearParallelScope: 'Unrelated interior painted segments below 10px; includes source-constrained gate approaches; diagnostic only' };
  }
  function check(graph, name, expandedId) {
    result.activeStage = { name, expandedId, started: new Date().toISOString(), nodes: graph.nodes.length, edges: graph.edges.length };
    fs.writeFileSync(progressFile, JSON.stringify(result));
    if (option('--capture-stage', '') === name) fs.writeFileSync(path.join(output, 'cases', item.id + '-' + name + '-before.json.gz'),
      gzipSync(JSON.stringify(graph, (key, value) => key === 'frontiers' ? {} : value)));
    const started = performance.now(), routed = F.route(graph), validation = E.validateView(graph);
    const labels = graph.nodes.filter(node => node.expanded || node.glyphPresentation).flatMap(node => (node.labelObstacles || []).map(box =>
      ({ id: node.id, x: node.x + box.x, y: node.y + box.y, w: box.w, h: box.h })));
    const labelContacts = graph.edges.flatMap(edge => labels.filter(box => edge.route.slice(1).some((point, index) => R.intersectsRect(edge.route[index], point, box)))
      .map(box => ({ edge: edge.id, labelOwner: box.id })));
    const stage = { name, expandedId, milliseconds: performance.now() - started, nodes: graph.nodes.length, edges: graph.edges.length,
      routed: routed.routed, failed: routed.failed, ...(routed.reason ? { routingReason: routed.reason } : {}),
      ...(routed.fixedTargetConflicts ? { fixedTargetConflicts: routed.fixedTargetConflicts } : {}), source: validation.source, layout: validation.layout,
      invalidEdges: validation.edges.filter(([, check]) => !check.ok), contacts: validation.routing.contacts,
      constrained: validation.routing.constrained, labelContacts, quality: quality(graph), authorityUnchanged: hash(JSON.stringify(graph.recursive.authority)) === baseline };
    stage.passed = !stage.failed && stage.source.ok && stage.layout.ok && !stage.invalidEdges.length
      && !stage.contacts.length && !stage.constrained.length && !labelContacts.length && stage.authorityUnchanged;
    result.stages.push(stage);
    fs.writeFileSync(progressFile, JSON.stringify(result));
    if (!stage.passed) {
      result.status = 'failed';
      const failure = path.join(output, 'failures', item.id + '-' + name.replace(/[^\w-]/g, '_') + '.json.gz');
      fs.mkdirSync(path.dirname(failure), { recursive: true });
      fs.writeFileSync(failure, gzipSync(JSON.stringify({ case: item, stage, graph }, (key, value) => key === 'frontiers' ? {} : value)));
      stage.failureGraph = path.relative(project, failure);
    }
    return graph;
  }
  check(initial, 'initial');
  const fullyOpen = check(F.all(E.clone(initial), true), 'all-open');
  const fullGeometry = JSON.stringify(fullyOpen.nodes), fullRoutes = JSON.stringify(fullyOpen.edges.map(edge => [edge.id, edge.route]));
  const collapsed = check(F.all(E.clone(fullyOpen), false), 'all-collapse');
  const restored = check(F.all(collapsed, true), 'all-reopen');
  result.fullReopenGeometryRestored = JSON.stringify(restored.nodes) === fullGeometry;
  result.fullReopenRoutesRestored = JSON.stringify(restored.edges.map(edge => [edge.id, edge.route])) === fullRoutes;
  if (!result.fullReopenGeometryRestored || !result.fullReopenRoutesRestored) result.status = 'failed';
  if (phase === 'mixed' && containers.length) {
    // Choose actual nested containers by depth and branching, independent of
    // model names and fixture-specific ids. Toggle each ancestor through the
    // same public API as the UI; never put leaf ids into the open state.
    const targets = [...containers].sort((a, b) => depth(b) - depth(a)
      || F.children(doc.authority, b).length - F.children(doc.authority, a).length || a.localeCompare(b));
    const sampled = targets.slice(0, +option('--single-limit', '2'));
    let mixed = E.clone(initial);
    for (const [index, id] of sampled.entries()) {
      let graph = E.clone(initial), source = doc.authority.detail.nodes.find(node => node.id === id), chain = [];
      while (source) { if (F.children(doc.authority, source.id).length && !doc.authority.mandatory.includes(source.id)) chain.unshift(source.id); source = doc.authority.detail.nodes.find(parent => parent.id === source.parent); }
      for (const [level, owner] of chain.entries()) {
        if (!F.opened(graph.recursive, owner)) graph = check(F.toggle(graph, owner, true), `single-${index}-depth-${level}`, owner);
        if (!F.opened(mixed.recursive, owner)) mixed = check(F.toggle(mixed, owner, true), `mixed-${index}-depth-${level}`, owner);
      }
      const geometry = JSON.stringify(graph.nodes), routes = JSON.stringify(graph.edges.map(edge => [edge.id, edge.route]));
      graph = check(F.toggle(graph, chain[0], false), `single-${index}-close`, chain[0]);
      graph = check(F.toggle(graph, chain[0], true), `single-${index}-reopen`, chain[0]);
      const restored = JSON.stringify(graph.nodes) === geometry && JSON.stringify(graph.edges.map(edge => [edge.id, edge.route])) === routes;
      result.stages.at(-1).geometryAndRoutesRestored = restored;
      if (!restored) result.status = 'failed';
    }
  }
  delete result.activeStage;
  fs.rmSync(progressFile, { force: true });
  return result;
}

if (process.argv.includes('--worker-case')) {
  const item = catalog.cases.find(item => item.id === argumentsFor('--worker-case'));
  let result;
  try { result = executeCase(item); }
  catch (error) { result = { id: item.id, title: item.title, status: 'error', error: error.stack }; }
  if (process.argv.includes('--result-file')) fs.writeFileSync(argumentsFor('--result-file'), JSON.stringify(result));
  else process.stdout.write(JSON.stringify(result));
} else {
  fs.mkdirSync(output, { recursive: true });
  const filter = option('--cases', '').split(',').filter(Boolean), selectionPath = option('--selection', '');
  let selection = null;
  if (selectionPath) {
    const filename = path.resolve(selectionPath), bytes = fs.readFileSync(filename), document = JSON.parse(bytes);
    if (!Array.isArray(document.cases) || !document.cases.length) throw Error('Selection must contain a nonempty cases array');
    const ids = document.cases.map(item => item?.id);
    for (const id of ids) if (typeof id !== 'string' || !catalog.cases.some(item => item.id === id && item.views.some(view => view.json)))
      throw Error('Selection ID has no registered graph: ' + String(id));
    filter.push(...ids);
    selection = { path: path.relative(project, filename), sha256: hash(bytes), ids: [...new Set(ids)] };
  }
  let cases = catalog.cases.filter(item => (includeHistorical || !item.historical) && item.views.some(view => view.json)
    && (!filter.length || filter.includes(item.id) || filter.includes(item.title)));
  cases = cases.slice(0, +option('--limit', String(cases.length)));
  const names = engineFiles.map(name => [name, hash(fs.readFileSync(path.join(runtime, name)))]);
  const helperReceipt = contactHelper ? { path: path.relative(project, contactHelper), sha256: hash(fs.readFileSync(contactHelper)),
    namespace: 'ArchCanvasContactMetric.wireContacts', routingEngineModified: false } : null;
  const report = { schema: 'archcanvas-preview-generalized-frontiers/1', phase,
    runtime: runtime === path.join(preview, 'yworks_edge_router_lab') ? 'formal studio/public/preview only' : 'explicit archived browser engine',
    runtimePath: path.relative(project, runtime), contactMetricHelper: helperReceipt,
    sourceModelExecuted: false, started: new Date().toISOString(), engineHashes: Object.fromEntries(names),
    catalogSha256: hash(fs.readFileSync(path.join(preview, 'data/catalog.json'))), selection,
    activeCatalogCases: catalog.cases.filter(item => !item.historical).length, includeHistorical,
    testedCatalogCases: cases.length,
    skippedWithoutRegisteredGraph: catalog.cases.filter(item => (includeHistorical || !item.historical) && !item.views.some(view => view.json)).map(item => ({ id: item.id, title: item.title })),
    results: [] };
  let next = 0;
  const summaryPath = path.join(output, phase + '-report.json');
  const save = () => fs.writeFileSync(summaryPath, JSON.stringify(report, null, 2));
  const timeout = +option('--timeout-ms', '90000');
  async function run() {
    while (next < cases.length) {
      const item = cases[next++], started = performance.now();
      const value = await new Promise(resolve => {
        const resultFile = path.join(output, 'cases', phase + '-' + item.id + '.json');
        fs.mkdirSync(path.dirname(resultFile), { recursive: true });
        if (fs.existsSync(resultFile)) fs.unlinkSync(resultFile);
        const child = spawn(process.execPath, [__filename, '--worker-case', item.id, '--phase', phase, '--output', output,
          '--single-limit', option('--single-limit', '2'), '--capture-stage', option('--capture-stage', ''), '--result-file', resultFile,
          '--runtime-dir', runtime, ...(contactHelper ? ['--contact-metric-helper', contactHelper] : [])], { stdio: ['ignore', 'pipe', 'pipe'] });
        let stdout = '', stderr = '', timedOut = false;
        const timer = setTimeout(() => { timedOut = true; child.kill('SIGKILL'); }, timeout);
        child.stdout.on('data', data => { stdout += data; }); child.stderr.on('data', data => { stderr += data; });
        child.on('close', code => { clearTimeout(timer); try { resolve(JSON.parse(fs.readFileSync(resultFile))); }
          catch (_) {
            let partial = {}; try { partial = JSON.parse(fs.readFileSync(path.join(output, 'cases', phase + '-' + item.id + '.progress.json'))); } catch (_) {}
            resolve({ ...partial, id: item.id, title: item.title, status: timedOut ? 'timeout' : 'error', code, stderr, stdout: stdout.slice(-1000) });
          } });
      });
      value.totalMilliseconds = performance.now() - started; report.results.push(value); save();
      process.stdout.write(`${report.results.length}/${cases.length} ${item.title}: ${value.status} (${Math.round(value.totalMilliseconds)}ms)\n`);
    }
  }
  Promise.all(Array.from({ length: +option('--concurrency', '1') }, run)).then(() => {
    report.finished = new Date().toISOString();
    report.engineHashesStillMatch = engineFiles.every(name => report.engineHashes[name] === hash(fs.readFileSync(path.join(runtime, name))));
    report.contactMetricHelperHashStillMatches = !contactHelper || helperReceipt.sha256 === hash(fs.readFileSync(contactHelper));
    report.counts = { cases: report.results.length, stages: report.results.reduce((n, item) => n + (item.stages?.length || 0), 0),
      passedCases: report.results.filter(item => item.status === 'passed').length,
      failedCases: report.results.filter(item => item.status !== 'passed').length,
      failedStages: report.results.reduce((n, item) => n + (item.stages?.filter(stage => !stage.passed).length || 0), 0) };
    save(); process.stdout.write(JSON.stringify(report.counts) + '\n');
    process.exitCode = report.counts.failedCases || !report.engineHashesStillMatch || !report.contactMetricHelperHashStillMatches ? 1 : 0;
  });
}
