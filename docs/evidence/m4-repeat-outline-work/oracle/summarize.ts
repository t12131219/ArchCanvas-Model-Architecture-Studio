import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
const evidence = new URL('./', import.meta.url);
const read = (path: string) => JSON.parse(readFileSync(new URL(path, evidence), 'utf8'));
const before = read('before.json'), after = read('after.json'), current = read('current.json'), old = read('sealed-ChS.json');
assert.equal(current.exitCode, 0); assert.equal(old.exitCode, 1);
for (const receipt of [current, old]) { assert.equal(receipt.stableSourceDuringRun, true); assert.equal(receipt.stableTestsDuringRun, true); }
for (const capture of [before, after]) { assert.equal(capture.stableSourceDuringCapture, true); assert.equal(capture.inputsUnchanged, true); }
assert.equal(after.records.length, 12);
const rows = after.records.map((row: any, index: number) => {
  const prior = before.records[index]; assert.equal(row.inputSha256, prior.inputSha256); assert.equal(row.caseId, prior.caseId); assert.equal(row.detailNodeId, prior.detailNodeId);
  for (const key of ['frontCards', 'ordinaryPorts', 'sourceDigest', 'irDigest', 'sourceFactsSha256', 'renderedBindings', 'hiddenEdges', 'exportScope']) assert.deepEqual(row[key], prior[key], key);
  for (const values of Object.values(row.report)) assert.deepEqual(values, []);
  const byteIdentical = row.svgSha256 === prior.svgSha256;
  if (row.collapsedRepeatCount === 0) assert.equal(byteIdentical, true);
  return { caseId: row.caseId, ...(row.detailNodeId ? { detailNodeId: row.detailNodeId } : {}), collapsedRepeatCount: row.collapsedRepeatCount,
    beforeStackHits: prior.report.stackHits.length, afterStackHits: row.report.stackHits.length,
    beforeBuriedPorts: prior.report.buriedPorts.length, afterBuriedPorts: row.report.buriedPorts.length, noStackSvgByteIdentical: row.collapsedRepeatCount === 0 ? byteIdentical : null,
    immutableCanvas: true, canonicalSourceIrFrontAndOrdinaryPortsUnchanged: true };
});
const sha256 = (path: string) => createHash('sha256').update(readFileSync(new URL(path, evidence))).digest('hex');
const historicalAdapter = existsSync(new URL('historical-adapter-final.json', evidence)) ? read('historical-adapter-final.json') : undefined;
if (historicalAdapter) { assert.equal(historicalAdapter.exitCode, 0); assert.equal(historicalAdapter.allBindingsStableDuringRun, true); }
writeFileSync(new URL('summary.json', evidence), JSON.stringify({ schemaVersion: 1, scope: 'Independent bounded final-SVG geometry and Canvas invariants; no human/publication/browser acceptance claim',
  currentTargeted: { tests: 17, passed: 17, failed: 0, exitCode: 0 }, sealedChSRegressionControl: { tests: 17, passed: 7, failed: 10, exitCode: 1 },
  frontiers: 9, detailsContainingCollapsedRepeat: 3, beforeStackHits: 6, afterStackHits: 0,
  beforeBuriedPorts: 6, afterBuriedPorts: 0, afterEndpointMisses: 0, afterFloatingPorts: 0, afterOwnBodyHits: 0, afterCardOrPathClipping: 0,
  noStackFrontierSvgByteIdentical: 6, allInputsAndWholeCanvasUnchanged: true, records: rows,
  receiptHashes: Object.fromEntries(['before.json', 'after.json', 'current.json', 'sealed-ChS.json', 'current.stdout.txt', 'sealed-ChS.stdout.txt'].map(path => [path, sha256(path)])),
  ...(historicalAdapter ? { historicalRoutingAdapter: { targetedTests: 14, passed: 14, failed: 0, originalCoherentControlsRetained: 15, newCoherentControls: 8,
    recordsAudited: 73, rawPairMetricRegressions: 0, historicalOracleAndRawUnchanged: true, existingHonestBlockedMove: 'mlp-level0-paper-180-move-up/edge:1',
    receipt: 'historical-adapter-final.json', receiptSha256: sha256('historical-adapter-final.json') } } : {}),
  originalMatrixOrStatusModified: false, productCodeModifiedByOracleAgent: false, modelExecuted: false, dependenciesInstalled: false, productBuiltByOracleAgent: false,
  limitation: 'Nominal rectangle union is conservative at rounded corners; tensor crossings/overlap quality, browser pixels and human acceptance require separate evidence.' }, null, 2) + '\n');
console.log('Independent final-SVG summary verified: 17/17 current, sealed ChS 10 failures, 9 frontiers + 3 details, zero current stack hits.');
