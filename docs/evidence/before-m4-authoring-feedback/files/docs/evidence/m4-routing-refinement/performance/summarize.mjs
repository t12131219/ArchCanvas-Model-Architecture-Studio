import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const directory = dirname(fileURLToPath(import.meta.url));
const hash = value => createHash('sha256').update(value).digest('hex');
const read = name => JSON.parse(readFileSync(join(directory, name)));
const median = values => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
const baseline = [1, 2, 3].map(index => read(`baseline-process-${index}.json`));
const candidate = [1, 2, 3].map(index => read(`candidate-final-process-${index}.json`));
const budget = read('candidate-final-budget-audit.json');
const expectedPhases = ['buildScene', 'serializeInteractiveSvg', 'buildSceneAndSerialize', 'prepareMoveOnce', 'previewSceneAndSerialize',
  'guardedCommitSceneAndSerialize', 'detailExportSceneAndSerialize'];
const baselineHashes = read('baseline-manifest.json').coreFiles;
const candidateHashes = read('candidate-final-manifest.json').files;
function verifyReports(reports, hashes, expectedScript) {
  for (const report of reports) {
    assert.equal(report.status, 'completed-cpu-measurement');
    assert.equal(report.samples, 30);
    assert.equal(report.warmup, 5);
    assert.equal(report.scriptSha256, hash(readFileSync(join(directory, expectedScript))));
    assert.deepEqual(report.coreFiles, hashes);
    assert.equal(Object.keys(report.phases).length, 14);
    for (const input of report.inputFiles) {
      assert.equal(hash(readFileSync(join(directory, input.path))), input.sha256);
      assert.deepEqual(Object.keys(report.phases[input.id]), expectedPhases);
      for (const phase of Object.values(report.phases[input.id])) assert.equal(phase.samples.length, 30);
    }
  }
}
verifyReports(baseline, baselineHashes, 'benchmark.mjs');
verifyReports(candidate, candidateHashes, 'benchmark.mjs');
for (const name of readdirSync(join(directory, 'baseline-core')).filter(name => name.endsWith('.ts'))) assert.equal(hash(readFileSync(join(directory, 'baseline-core', name))), baselineHashes[name]);
for (const name of readdirSync(join(directory, 'candidate-final-core')).filter(name => name.endsWith('.ts'))) assert.equal(hash(readFileSync(join(directory, 'candidate-final-core', name))), candidateHashes[name]);
assert.equal(budget.originalRouterSha256, candidateHashes['orthogonalRouter.ts']);
assert.equal(budget.status, 'passed-bounded-work-audit');
assert.equal(budget.scriptSha256, hash(readFileSync(join(directory, 'audit-budget-final.mjs'))));
const comparisons = {};
const observedAddedCost = [];
for (const id of Object.keys(baseline[0].phases)) {
  comparisons[id] = {};
  for (const phase of expectedPhases) {
    const beforeP95 = baseline.map(report => report.phases[id][phase].p95Ms);
    const afterP95 = candidate.map(report => report.phases[id][phase].p95Ms);
    const beforeMedian = median(beforeP95), afterMedian = median(afterP95);
    const record = { baselineProcessP95Ms: beforeP95, candidateProcessP95Ms: afterP95,
      baselineMedianProcessP95Ms: beforeMedian, candidateMedianProcessP95Ms: afterMedian,
      deltaMs: afterMedian - beforeMedian, ratio: afterMedian / beforeMedian,
      baselineProcessP50Ms: baseline.map(report => report.phases[id][phase].p50Ms),
      candidateProcessP50Ms: candidate.map(report => report.phases[id][phase].p50Ms) };
    comparisons[id][phase] = record;
    // An explicit descriptive screen, never a browser acceptance gate.
    if (record.deltaMs > 2 && record.ratio > 1.25) observedAddedCost.push({ id, phase, deltaMs: record.deltaMs, ratio: record.ratio });
  }
  assert.equal(baseline[0].receipts[id].nodeCount, candidate[0].receipts[id].nodeCount);
  assert.equal(baseline[0].receipts[id].edgeCount, candidate[0].receipts[id].edgeCount);
  assert.equal(baseline[0].receipts[id].canonicalEdgeCount, candidate[0].receipts[id].canonicalEdgeCount);
}
const wideNames = ['baseline-wide-process-1.json', 'candidate-final-wide-process-1.json'];
const wideReports = wideNames.map(read);
for (let index = 0; index < wideReports.length; index++) {
  const report = wideReports[index];
  assert.equal(report.status, 'completed-cpu-measurement');
  assert.equal(report.samples, 30); assert.equal(report.warmup, 5);
  assert.equal(report.scriptSha256, hash(readFileSync(join(directory, 'benchmark-wide.mjs'))));
  assert.deepEqual(report.coreFiles, index ? candidateHashes : baselineHashes);
}
const stages = ['candidate-v1-process-1.json', 'candidate-v2-process-1.json'].map(read).map(report => ({
  label: report.label, sourceRouterSha256: report.coreFiles['orthogonalRouter.ts'], status: report.status,
  transformerL3P95Ms: Object.fromEntries(expectedPhases.map(phase => [phase, report.phases['transformer-L3'][phase].p95Ms])),
  density8P95Ms: Object.fromEntries(expectedPhases.map(phase => [phase, report.phases['synthetic-density-8'][phase].p95Ms])),
}));
const report = { schemaVersion: 1, status: 'completed-cpu-comparison-with-open-browser-gate',
  scope: 'Fixed-input CPU-only public complete scene, SVG, prepared gesture, guarded commit and detail export paths.',
  acceptance: { completeSceneSvgPreviewCommitCoherence: true, boundedAddedRefinementCounters: true,
    browserPerformanceGateCertified: false, presentedPaintCertified: false, humanReadabilityCertified: false },
  method: { samplesPerPhasePerFreshProcess: 30, warmupPerInputPerFreshProcess: 5, baselineProcesses: 3, candidateProcesses: 3,
    phasesPerInput: 7, inputsPerProcess: 14, comparison: 'median of three separately reported per-process p95 values; all raw samples retained',
    cpuAddedCostScreen: 'descriptive flag when median p95 adds >2ms and >25%; not a gate or a claim of causality',
    order: 'Sequential fresh processes, not paired alternating before/after samples. Intermediate candidates and separate wide processes were interleaved in time.' },
  processMetadata: [...baseline, ...candidate, ...wideReports].map(item => ({ label: item.label, startedAtUtc: item.startedAtUtc, endedAtUtc: item.endedAtUtc,
    environment: item.environment, finalLoadAverage: item.finalLoadAverage })),
  baselineCoreFiles: baselineHashes, candidateCoreFiles: candidateHashes, inputFiles: candidate[0].inputFiles,
  priorCandidateStages: stages, comparisons, observedAddedCost,
  wideSingleProcessComparisons: Object.fromEntries(Object.keys(wideReports[0].phases).map(id => [id, Object.fromEntries(expectedPhases.map(phase => [phase, {
    baselineP95Ms: wideReports[0].phases[id][phase].p95Ms, candidateP95Ms: wideReports[1].phases[id][phase].p95Ms,
    baselineP50Ms: wideReports[0].phases[id][phase].p50Ms, candidateP50Ms: wideReports[1].phases[id][phase].p50Ms,
  }]))])),
  budgetAudit: { path: 'candidate-final-budget-audit.json', sha256: hash(readFileSync(join(directory, 'candidate-final-budget-audit.json'))),
    publicPathCount: budget.publicPathCount, caps: budget.caps, sourceRouterSha256: budget.originalRouterSha256 },
  limitations: ['CPU timing does not certify DOM update, layout, paint, native input-to-paint, sustained presented FPS, INP, publication size or human usability.',
    'Changes in p95 between separate processes include JIT/GC and host noise; no forced gc, pinned CPU or isolated machine was used.',
    'Load averages are recorded, not proof of exclusive host access. Root deferred builds/full suites during final timing, while an existing local service remained available.',
    'Dense refinement adds real CPU work; bounds do not eliminate cost or guarantee a frame target.',
    'Inputs above refinement gates retain ordinary obstacle routes and may still contain crossings/overlaps.',
    'Wide geometry comparisons use only one fresh process per variant and must not inherit three-process confidence.',
    'Source hashes bind measured independent core copies. Live product equality must be checked again before claiming these certify a later build.'] };
writeFileSync(join(directory, 'comparison.json'), JSON.stringify(report, null, 2) + '\n');
const rows = Object.entries(comparisons).map(([id, phases]) => ({ input: id,
  buildAndSvgBefore: phases.buildSceneAndSerialize.baselineMedianProcessP95Ms, buildAndSvgAfter: phases.buildSceneAndSerialize.candidateMedianProcessP95Ms,
  previewBefore: phases.previewSceneAndSerialize.baselineMedianProcessP95Ms, previewAfter: phases.previewSceneAndSerialize.candidateMedianProcessP95Ms,
  commitBefore: phases.guardedCommitSceneAndSerialize.baselineMedianProcessP95Ms, commitAfter: phases.guardedCommitSceneAndSerialize.candidateMedianProcessP95Ms }));
console.log(JSON.stringify({ output: 'comparison.json', rows, observedAddedCost, budgetAudit: report.budgetAudit }, null, 2));
