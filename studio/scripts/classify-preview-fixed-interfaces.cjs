#!/usr/bin/env node
/* Read-only diagnostic: classify saved matrix artifacts without executing an engine or model. */
'use strict';
const fs = require('node:fs'), path = require('node:path');
const { gunzipSync } = require('node:zlib'), { createHash } = require('node:crypto');
const project = path.resolve(__dirname, '../..'), preview = path.join(project, 'studio/public/preview');
const options = key => process.argv.includes(key) ? process.argv[process.argv.indexOf(key) + 1] : undefined;
const reportPath = options('--report');
if (!reportPath || !options('--output')) throw Error('Usage: node studio/scripts/classify-preview-fixed-interfaces.cjs --report final/standard-report.json --old-report old/standard-report.json --output evidence.json [--expect-cases 10]');
const absoluteReport = path.resolve(reportPath), reportBytes = fs.readFileSync(absoluteReport), report = JSON.parse(reportBytes);
if (!report.finished || report.results?.length !== report.testedCatalogCases || report.engineHashesStillMatch !== true)
  throw Error('The input matrix must be complete and must attest unchanged engine hashes.');
const sha = bytes => createHash('sha256').update(bytes).digest('hex'), relative = file => path.relative(project, file);
const oldPath = options('--old-report') && path.resolve(options('--old-report'));
const oldBytes = oldPath && fs.readFileSync(oldPath), oldReport = oldBytes && JSON.parse(oldBytes);
const oldCases = new Map((oldReport?.results || []).map(item => [item.id, item]));
const sourceCatalogPath = path.join(preview, 'data/catalog-sources.json'), sourceCatalogBytes = fs.readFileSync(sourceCatalogPath);
const sourceCatalog = JSON.parse(sourceCatalogBytes), EPS = 1e-5;
const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const equal = (a, b) => !!a && !!b && distance(a, b) < EPS;
const normals = { left: [-1, 0], right: [1, 0], top: [0, -1], bottom: [0, 1] };
const activeTarget = edge => edge.physicalTarget || edge.fixedTarget;
function point(node, port) {
  if (port.offset) return { x: node.x + port.offset.x, y: node.y + port.offset.y };
  const fraction = port.fraction ?? .5;
  return { x: port.side === 'left' ? node.x : port.side === 'right' ? node.x + node.w : node.x + node.w * fraction,
    y: port.side === 'top' ? node.y : port.side === 'bottom' ? node.y + node.h : node.y + node.h * fraction };
}
function record(graph, edge) {
  const targetNode = graph.nodes.find(node => node.id === edge.target), port = activeTarget(edge);
  if (!targetNode || !port || !normals[port.side]) throw Error('Missing registered target: ' + edge.id);
  const endpoint = point(targetNode, port), sign = port.inward ? -1 : 1, normal = normals[port.side];
  const minimum = edge.contract?.minimumTerminal || 0, requiredPrevious = { x: endpoint.x + normal[0] * sign * minimum, y: endpoint.y + normal[1] * sign * minimum };
  const actualEndpoint = edge.route.at(-1), actualPrevious = edge.route.at(-2);
  return { id: edge.id, source: edge.source, target: edge.target, binding: edge.binding, contract: edge.contract,
    fixedSource: edge.fixedSource, physicalSource: edge.physicalSource || null,
    fixedTarget: edge.fixedTarget, physicalTarget: edge.physicalTarget || null, targetPolicy: edge.portPolicy?.target,
    sourceNode: graph.nodes.find(node => node.id === edge.source), targetNode,
    terminalGeometry: { endpoint, requiredPrevious, requiredOutwardVector: { x: normal[0] * sign, y: normal[1] * sign },
      minimumLength: minimum, actualEndpoint, actualPrevious,
      actualLength: actualPrevious && actualEndpoint ? distance(actualEndpoint, actualPrevious) : null,
      actualEndpointMatchesRegistered: equal(endpoint, actualEndpoint), route: edge.route } };
}
function classifyPair(graph, ids) {
  const a = graph.edges.find(edge => edge.id === ids[0]), b = graph.edges.find(edge => edge.id === ids[1]);
  if (!a || !b) throw Error('Missing conflict edges ' + ids.join(' / '));
  const edges = [record(graph, a), record(graph, b)], ports = [activeTarget(a), activeTarget(b)];
  const sameTarget = a.target === b.target, samePoint = equal(edges[0].terminalGeometry.endpoint, edges[1].terminalGeometry.endpoint);
  const sameRay = ports[0].side === ports[1].side && !!ports[0].inward === !!ports[1].inward;
  const fixed = [a, b].every(edge => (edge.portPolicy?.target?.mode || 'fixed') === 'fixed'
    && JSON.stringify(activeTarget(edge)) === JSON.stringify(edge.fixedTarget));
  const approach = [a, b].every(edge => !edge.draft && edge.style === 'orthogonal' && edge.arrow !== 'none'
    && edge.contract?.enforcePortApproach && edge.contract.minimumTerminal > EPS);
  const independent = a.contract?.wire !== b.contract?.wire, overlap = Math.min(...edges.map(edge => edge.terminalGeometry.minimumLength));
  if (!(sameTarget && samePoint && sameRay && fixed && approach && independent))
    throw Error('Saved preflight pair does not prove an independent fixed final-ray conflict: ' + ids.join(' / '));
  const endpoint = edges[0].terminalGeometry.endpoint, normal = edges[0].terminalGeometry.requiredOutwardVector;
  return { edges, sameTarget, identicalFixedTarget: JSON.stringify(a.fixedTarget) === JSON.stringify(b.fixedTarget),
    bothTargetPoliciesFixed: fixed, bothEnforcePortApproach: approach, independentWireIdentities: [a.contract.wire, b.contract.wire],
    sharedMinimumFinalRay: { start: endpoint, end: { x: endpoint.x + normal.x * overlap, y: endpoint.y + normal.y * overlap }, length: overlap },
    conclusion: 'Distinct source values are required to share this positive final ray by the recorded fixed target policies; exterior detours cannot remove that terminal overlap.' };
}
const cases = [];
for (const item of report.results || []) {
  const failedStages = (item.stages || []).filter(stage => stage.fixedTargetConflicts?.length);
  if (!failedStages.length) continue;
  const stages = failedStages.map(stage => {
    if (!stage.failureGraph) throw Error('Missing failure graph ' + item.id + '/' + stage.name);
    const artifactPath = path.resolve(project, stage.failureGraph), bytes = fs.readFileSync(artifactPath), decoded = gunzipSync(bytes), value = JSON.parse(decoded);
    if (value.case.id !== item.id || value.stage.name !== stage.name) throw Error('Failure artifact identity mismatch');
    const pairs = stage.fixedTargetConflicts.map(ids => classifyPair(value.graph, ids));
    return { name: stage.name, artifact: relative(artifactPath), artifactSha256: sha(bytes), decodedSha256: sha(decoded),
      routingReason: stage.routingReason, validatorViolations: stage.layout?.violations || [], pairs };
  });
  const selected = stages.find(stage => stage.name === 'all-open') || stages[0], old = oldCases.get(item.id);
  const sources = sourceCatalog.cases?.[item.id];
  cases.push({ id: item.id, title: item.title, historical: !!item.historical,
    classification: 'recorded-independent-values-share-fixed-target-ray', authoritySha256: item.authoritySha256,
    registeredInputHashes: item.inputHashes, sourceEntry: sources?.entry || null,
    sourceFiles: (sources?.files || []).map(file => ({ path: file.path, asset: file.asset, declaredSha256: file.sha256,
      actualSha256: fs.existsSync(path.join(preview, file.asset)) ? sha(fs.readFileSync(path.join(preview, file.asset))) : null })),
    oldReportComparison: old ? { status: old.status, presentationVersion: old.presentationVersion,
      stages: (old.stages || []).filter(stage => !stage.passed).map(stage => ({ name: stage.name, failed: stage.failed,
        routingReason: stage.routingReason, validatorViolations: stage.layout?.violations || [],
        fixedTargetConflicts: stage.fixedTargetConflicts || [], failureGraph: stage.failureGraph })) } : null,
    artifact: selected.artifact, artifactSha256: selected.artifactSha256, pairs: selected.pairs,
    allFixedConflictStages: stages.map(({ pairs, ...stage }) => ({ ...stage, pairCount: pairs.length,
      edgePairs: pairs.map(pair => pair.edges.map(edge => edge.id)) })) });
}
if (options('--expect-cases') && cases.length !== +options('--expect-cases')) throw Error('Expected ' + options('--expect-cases') + ' cases; found ' + cases.length);
const result = { schema: 'archcanvas-historical-fixed-interface-conflicts/2', diagnosticOnly: true,
  sourceModelExecuted: false, engineExecuted: false, generated: new Date().toISOString(),
  classifier: { path: relative(__filename), sha256: sha(fs.readFileSync(__filename)) },
  inputReport: relative(absoluteReport), inputReportSha256: sha(reportBytes), inputEngineHashes: report.engineHashes,
  inputReportCompleted: report.finished, inputEngineHashesStillMatch: report.engineHashesStillMatch,
  oldReport: oldPath ? { path: relative(oldPath), sha256: sha(oldBytes), engineHashes: oldReport.engineHashes } : null,
  sourceCatalog: { path: relative(sourceCatalogPath), sha256: sha(sourceCatalogBytes) },
  counts: { cases: cases.length, historical: cases.filter(item => item.historical).length,
    uniquePairsAtSelectedStages: cases.reduce((sum, item) => sum + item.pairs.length, 0),
    fixedConflictStages: cases.reduce((sum, item) => sum + item.allFixedConflictStages.length, 0) }, cases };
const output = path.resolve(options('--output')); fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, JSON.stringify(result, null, 2) + '\n');
process.stdout.write(JSON.stringify({ output: relative(output), counts: result.counts }) + '\n');
