#!/usr/bin/env node
/* Compare completed receipts, without replaying either source or engine. */
const fs = require('node:fs'), path = require('node:path'), { createHash } = require('node:crypto');
const project = path.resolve(__dirname, '../..');
const evidence = path.join(project, 'docs/evidence/preview-generalization-20261014');
const option = (key, fallback) => process.argv.includes(key) ? process.argv[process.argv.indexOf(key) + 1] : fallback;
const baseline = path.resolve(option('--baseline', path.join(evidence, 'pre-v15-v14-final')));
const current = path.resolve(option('--current', path.join(evidence, 'final')));
const output = path.resolve(option('--output', path.join(current, 'quality-comparison.json')));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const fields = ['length', 'bends', 'crossings', 'unrelatedCrossings', 'unrelatedContacts', 'unrelatedTouches', 'nearParallelRuns', 'nearParallelLength', 'minimumParallelGap'];
const improves = (key, delta) => delta !== null && (key === 'minimumParallelGap' ? delta > 1e-5 : delta < -1e-5);
const worsens = (key, delta) => delta !== null && (key === 'minimumParallelGap' ? delta < -1e-5 : delta > 1e-5);
const engine = path.join(project, 'studio/public/preview/yworks_edge_router_lab');
const phases = [], stages = [];
for (const phase of ['standard', 'mixed']) {
  const previousPath = path.join(baseline, phase + '-report.json'), latestPath = path.join(current, phase + '-report.json');
  const previousBytes = fs.readFileSync(previousPath), latestBytes = fs.readFileSync(latestPath);
  const previous = JSON.parse(previousBytes), latest = JSON.parse(latestBytes);
  if (!previous.finished || !latest.finished || previous.engineHashesStillMatch !== true || latest.engineHashesStillMatch !== true)
    throw Error('Only completed current-runtime receipts can be compared: ' + phase);
  for (const [role, receipt] of [['baseline', previous], ['current', latest]]) {
    if (receipt.runtimePath) for (const [name, expected] of Object.entries(receipt.engineHashes))
      if (sha(fs.readFileSync(path.resolve(project, receipt.runtimePath, name))) !== expected)
        throw Error(role + ' matrix runtime changed: ' + name);
    if (receipt.contactMetricHelper && (receipt.contactMetricHelperHashStillMatches !== true
      || sha(fs.readFileSync(path.resolve(project, receipt.contactMetricHelper.path))) !== receipt.contactMetricHelper.sha256))
      throw Error(role + ' contact metric helper changed');
  }
  if (previous.catalogSha256 !== latest.catalogSha256) throw Error('Catalog changed: ' + phase);
  for (const [name, expected] of Object.entries(latest.engineHashes))
    if (sha(fs.readFileSync(path.join(engine, name))) !== expected) throw Error('Current matrix runtime changed: ' + name);
  const before = new Map(previous.results.map(item => [item.id, item])), unmatched = [];
  for (const item of latest.results) {
    const old = before.get(item.id);
    if (!old) { unmatched.push({ id: item.id, reason: 'case-missing-in-baseline' }); continue; }
    if (JSON.stringify(item.inputHashes) !== JSON.stringify(old.inputHashes)) throw Error('Case source data changed: ' + item.id);
    const oldStages = new Map((old.stages || []).map(stage => [stage.name, stage]));
    for (const stage of item.stages || []) {
      const previousStage = oldStages.get(stage.name);
      if (!previousStage?.quality || !stage.quality) { unmatched.push({ id: item.id, name: stage.name, reason: 'stage-or-quality-missing' }); continue; }
      const deltas = Object.fromEntries(fields.map(key => [key,
        typeof stage.quality[key] === 'number' && typeof previousStage.quality[key] === 'number'
          ? stage.quality[key] - previousStage.quality[key] : null]));
      const unavailableMetrics = fields.filter(key => !Object.hasOwn(stage.quality, key) || !Object.hasOwn(previousStage.quality, key))
        .map(key => ({ metric: key, baselineAvailable: Object.hasOwn(previousStage.quality, key), currentAvailable: Object.hasOwn(stage.quality, key) }));
      stages.push({ phase, id: item.id, title: item.title, historical: !!item.historical, name: stage.name,
        baselinePassed: previousStage.passed, currentPassed: stage.passed,
        baseline: previousStage.quality, current: stage.quality, deltas, unavailableMetrics,
        improved: fields.filter(key => improves(key, deltas[key])), worsened: fields.filter(key => worsens(key, deltas[key])) });
    }
  }
  phases.push({ phase, baselineReport: path.relative(project, previousPath), baselineReportSha256: sha(previousBytes),
    currentReport: path.relative(project, latestPath), currentReportSha256: sha(latestBytes),
    baselineEngineHashes: previous.engineHashes, currentEngineHashes: latest.engineHashes,
    baselineRuntime: previous.runtime, baselineRuntimePath: previous.runtimePath ?? null,
    baselineContactMetricHelper: previous.contactMetricHelper ?? null,
    currentRuntime: latest.runtime, currentRuntimePath: latest.runtimePath ?? null,
    currentContactMetricHelper: latest.contactMetricHelper ?? null, unmatched });
}
const changed = stages.filter(stage => stage.improved.length || stage.worsened.length);
const comparable = stages.filter(stage => stage.baselinePassed && stage.currentPassed);
const countFields = values => Object.fromEntries(fields.map(key => [key,
  { comparableStages: values.filter(stage => stage.deltas[key] !== null).length,
    unavailableStages: values.filter(stage => stage.unavailableMetrics.some(metric => metric.metric === key)).length,
    improved: values.filter(stage => improves(key, stage.deltas[key])).length,
    worsened: values.filter(stage => worsens(key, stage.deltas[key])).length,
    totalDelta: values.reduce((sum, stage) => sum + (stage.deltas[key] ?? 0), 0) }]));
const report = { schema: 'archcanvas-preview-frontier-quality-comparison/1', sourceModelExecuted: false, engineReplayed: false,
  reportingNote: 'Stages are paired by phase, case ID and stage name using identical catalog/source bytes. Positive deltas increase measured cost except minimumParallelGap, where a decrease is worse. A nullable gap is comparable only when both versions have near-parallel pairs; new or disappearing pairs are recorded by run/length metrics. Missing metrics are explicitly unavailable and never treated as zero. Unrelated contacts include internal bends and T touches, exclude coincident terminal pairs, equal wire identities and licensed shared presentation. Every worsening is retained. Legal routing can trade length, bends and crossings, so a single cost increase is evidence for review rather than automatic invalidity. Near-parallel metrics include licensed source interface approaches and remain diagnostic. Concurrent matrix timing is intentionally excluded.',
  phases, counts: { matchedStages: stages.length, stagesLegalInBothVersions: comparable.length, changedStages: changed.length,
    changedActiveStages: changed.filter(stage => !stage.historical).length, changedHistoricalStages: changed.filter(stage => stage.historical).length,
    stagesWithAnyWorsening: changed.filter(stage => stage.worsened.length).length,
    legalToInvalid: stages.filter(stage => stage.baselinePassed && !stage.currentPassed).length,
    invalidToLegal: stages.filter(stage => !stage.baselinePassed && stage.currentPassed).length,
    allMatchedMetricChanges: countFields(stages), legalInBothMetricChanges: countFields(comparable) },
  changedStages: changed, stagesWithAnyWorsening: changed.filter(stage => stage.worsened.length),
  stagesWithUnavailableMetrics: stages.filter(stage => stage.unavailableMetrics.length).map(stage => ({phase:stage.phase,id:stage.id,name:stage.name,metrics:stage.unavailableMetrics})) };
fs.mkdirSync(path.dirname(output), { recursive: true }); fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report.counts));
