#!/usr/bin/env node
/* Prove that a diagnostic-only replay preserves its archived routing receipts. */
const fs = require('node:fs'), path = require('node:path'), { createHash } = require('node:crypto');
const project = path.resolve(__dirname, '../..');
const evidence = path.join(project, 'docs/evidence/preview-generalization-20261014');
const option = (key, fallback) => process.argv.includes(key) ? process.argv[process.argv.indexOf(key) + 1] : fallback;
const baseline = path.resolve(option('--baseline', path.join(evidence, 'pre-v15-v14-final')));
const replay = path.resolve(option('--replay', path.join(evidence, 'baseline-v14-contact-audit')));
const output = path.resolve(option('--output', path.join(replay, 'routing-replay-integrity.json')));
const sha = value => createHash('sha256').update(value).digest('hex');
const fields = ['length', 'bends', 'crossings', 'unrelatedCrossings', 'nearParallelRuns', 'nearParallelLength', 'minimumParallelGap'];
const stageFields = ['name', 'expandedId', 'nodes', 'edges', 'routed', 'failed', 'routingReason', 'fixedTargetConflicts',
  'source', 'layout', 'invalidEdges', 'contacts', 'constrained', 'labelContacts', 'authorityUnchanged', 'passed', 'geometryAndRoutesRestored'];
const phases = [], differences = [];
let checkedCases = 0, checkedStages = 0;
for (const phase of ['standard', 'mixed']) {
  const previousPath = path.join(baseline, phase + '-report.json'), currentPath = path.join(replay, phase + '-report.json');
  const previousBytes = fs.readFileSync(previousPath), currentBytes = fs.readFileSync(currentPath);
  const previous = JSON.parse(previousBytes), current = JSON.parse(currentBytes);
  if (!previous.finished || !current.finished || !previous.engineHashesStillMatch || !current.engineHashesStillMatch
      || !current.contactMetricHelper || !current.contactMetricHelperHashStillMatches)
    throw Error('Completed unchanged-runtime diagnostic receipts required: ' + phase);
  const compare = (location, a, b) => {
    if (JSON.stringify(a) !== JSON.stringify(b)) differences.push({ phase, location, baseline: a ?? null, replay: b ?? null });
  };
  compare('engineHashes', previous.engineHashes, current.engineHashes);
  compare('catalogSha256', previous.catalogSha256, current.catalogSha256);
  compare('counts', previous.counts, current.counts);
  for (const [name, expected] of Object.entries(current.engineHashes))
    if (sha(fs.readFileSync(path.resolve(project, current.runtimePath, name))) !== expected) throw Error('Frozen runtime changed: ' + name);
  if (sha(fs.readFileSync(path.resolve(project, current.contactMetricHelper.path))) !== current.contactMetricHelper.sha256)
    throw Error('Contact metric helper changed');
  const oldCases = new Map(previous.results.map(item => [item.id, item]));
  for (const item of current.results) {
    const old = oldCases.get(item.id);
    if (!old) { differences.push({ phase, location: item.id, reason: 'case-missing-in-archive' }); continue; }
    oldCases.delete(item.id); checkedCases++;
    for (const key of ['status', 'authoritySha256', 'inputHashes', 'recordedViews', 'fullReopenGeometryRestored', 'fullReopenRoutesRestored'])
      compare(item.id + '.' + key, old[key], item[key]);
    const oldStages = new Map((old.stages || []).map(stage => [stage.name, stage]));
    for (const stage of item.stages || []) {
      const before = oldStages.get(stage.name), location = item.id + '.' + stage.name;
      if (!before) { differences.push({ phase, location, reason: 'stage-missing-in-archive' }); continue; }
      oldStages.delete(stage.name); checkedStages++;
      for (const key of stageFields) compare(location + '.' + key, before[key], stage[key]);
      for (const key of fields) compare(location + '.quality.' + key, before.quality?.[key], stage.quality?.[key]);
      for (const key of ['unrelatedContacts', 'unrelatedTouches']) if (typeof stage.quality?.[key] !== 'number')
        differences.push({ phase, location: location + '.quality.' + key, reason: 'contact-metric-missing' });
    }
    for (const name of oldStages.keys()) differences.push({ phase, location: item.id + '.' + name, reason: 'stage-missing-in-replay' });
  }
  for (const id of oldCases.keys()) differences.push({ phase, location: id, reason: 'case-missing-in-replay' });
  phases.push({ phase, archiveReport: path.relative(project, previousPath), archiveReportSha256: sha(previousBytes),
    replayReport: path.relative(project, currentPath), replayReportSha256: sha(currentBytes), engineHashes: current.engineHashes,
    runtimePath: current.runtimePath, contactMetricHelper: current.contactMetricHelper,
    contactTotals: ['unrelatedContacts', 'unrelatedTouches'].map(metric => ({metric,
      total: current.results.reduce((sum,item) => sum+(item.stages || []).reduce((sum,stage) => sum+stage.quality[metric],0),0)})) });
}
const report = { schema: 'archcanvas-preview-diagnostic-replay-integrity/1', sourceModelExecuted: false,
  routingEngineModified: false, timingsCompared: false,
  note: 'The independently namespaced contact helper adds diagnostics only. Every archived metric, stage legality result, source authority/input hash, restoration receipt and frozen runtime hash is compared. Failure artifact paths and timing are intentionally excluded.',
  phases, checkedCases, checkedStages, passed: !differences.length, differences };
fs.mkdirSync(path.dirname(output), { recursive: true }); fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({passed:report.passed,checkedCases,checkedStages,differences:differences.length}));
process.exitCode = report.passed ? 0 : 1;
