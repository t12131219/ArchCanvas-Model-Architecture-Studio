#!/usr/bin/env node
/* Classify every actual matrix failure; retain all stage-level violations. */
const fs = require('node:fs'), path = require('node:path'), { createHash } = require('node:crypto');
const project = path.resolve(__dirname, '../..');
const option = (key, fallback) => process.argv.includes(key) ? process.argv[process.argv.indexOf(key) + 1] : fallback;
const reportPath = path.resolve(option('--report', path.join(project, 'docs/evidence/preview-generalization-20261014/final/standard-report.json')));
const output = path.resolve(option('--output', path.join(path.dirname(reportPath), 'failure-classification.json')));
const reportBytes = fs.readFileSync(reportPath), report = JSON.parse(reportBytes);
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const engine = path.join(project, 'studio/public/preview/yworks_edge_router_lab');
if (!report.finished || report.engineHashesStillMatch !== true) throw Error('Only completed, unchanged-runtime matrix reports can be classified');
for (const [name, expected] of Object.entries(report.engineHashes))
  if (sha(fs.readFileSync(path.join(engine, name))) !== expected) throw Error('Matrix runtime changed: ' + name);

function stageCategory(stage) {
  if (stage.geometryAndRoutesRestored === false) return 'frontier-restoration-failed';
  if (stage.fixedTargetConflicts?.length) return 'conflicting-independent-fixed-targets';
  if (stage.source?.ok === false) return 'invalid-recorded-source-or-containment';
  if (stage.layout?.wires?.length) return 'recorded-or-projected-wire-overlap';
  return 'routing-or-layout-repair-required';
}
const cases = report.results.filter(item => item.status !== 'passed').map(item => {
  const failedStages = (item.stages || []).filter(stage => !stage.passed || stage.geometryAndRoutesRestored === false).map(stage => {
    const artifact = stage.failureGraph ? path.resolve(project, stage.failureGraph) : null;
    if (artifact && !fs.existsSync(artifact)) throw Error('Failure graph is missing: ' + artifact);
    return { name: stage.name, category: stageCategory(stage), routingReason: stage.routingReason || null,
      sourceViolations: stage.source?.violations || [], layoutViolations: stage.layout?.violations || [],
      invalidEdges: stage.invalidEdges || [], nodeConflicts: stage.layout?.nodes || [], wireConflicts: stage.layout?.wires || [],
      junctionViolations: stage.layout?.junctions?.violations || [], fixedTargetConflicts: stage.fixedTargetConflicts || [],
      frameContacts: stage.contacts || [], constrained: stage.constrained || [], labelContacts: stage.labelContacts || [],
      authorityUnchanged: stage.authorityUnchanged, geometryAndRoutesRestored: stage.geometryAndRoutesRestored,
      failureGraph: stage.failureGraph || null,
      failureGraphSha256: artifact ? sha(fs.readFileSync(artifact)) : null };
  });
  const categories = [...new Set(failedStages.map(stage => stage.category))];
  const category = item.status === 'timeout' ? 'timeout' : item.status === 'error' ? 'runtime-error'
    : categories.includes('invalid-recorded-source-or-containment') ? 'invalid-recorded-source-or-containment'
    : categories.includes('conflicting-independent-fixed-targets') ? 'conflicting-independent-fixed-targets'
    : categories[0] || 'routing-or-layout-repair-required';
  return { id: item.id, title: item.title, historical: !!item.historical, status: item.status,
    category, stageCategories: categories, runtimeError: item.error || null, activeStage: item.activeStage || null,
    inputHashes: item.inputHashes || {}, recordedViews: item.recordedViews || [], failedStages };
});
const classifications = { schema: 'archcanvas-preview-final-failure-classification/2',
  inputReport: path.relative(project, reportPath), inputReportSha256: sha(reportBytes), inputEngineHashes: report.engineHashes,
  sourceModelExecuted: false, diagnosticOnly: true,
  reportingNote: 'Primary case categories are for counts. Every failing stage retains its own category and complete violations; a source-invalid case can also have separate wire overlaps in another frontier.',
  counts: { failedCases: cases.length, failedStages: cases.reduce((sum, item) => sum + item.failedStages.length, 0),
    active: cases.filter(item => !item.historical).length, historical: cases.filter(item => item.historical).length,
    categories: Object.fromEntries([...new Set(cases.map(item => item.category))].map(category => [category, cases.filter(item => item.category === category).length])) }, cases };
fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, JSON.stringify(classifications, null, 2) + '\n');
console.log(JSON.stringify(classifications.counts));
