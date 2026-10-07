import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { metrics, intrusions, verifyRefinement } from './oracle.ts';

const base = fileURLToPath(new URL('.', import.meta.url)), label = process.argv[2] ?? 'after';
if (!/^after(?:-[a-z0-9]+)*$/.test(label)) throw new Error('Invalid after label');
const target = resolve(base, `audit-${label}.json`);
if (existsSync(target)) throw new Error('Refusing to overwrite audit output');
const sha = (bytes: string | Buffer) => createHash('sha256').update(bytes).digest('hex');
const beforeCapture = JSON.parse(readFileSync(resolve(base, 'before/capture.json'), 'utf8'));
const afterCapture = JSON.parse(readFileSync(resolve(base, `${label}/capture.json`), 'utf8'));
assert.equal(beforeCapture.records.length, 73); assert.equal(afterCapture.records.length, 73);
const results = [], failures = [];
for (const record of beforeCapture.records) {
  const beforeBytes = readFileSync(resolve(base, `before/${record.key}.scene.json`)), afterBytes = readFileSync(resolve(base, `${label}/${record.key}.scene.json`));
  const before = JSON.parse(beforeBytes.toString()), after = JSON.parse(afterBytes.toString());
  assert.equal(sha(beforeBytes), record.sceneSha256);
  assert.equal(sha(afterBytes), afterCapture.records.find((item: { key: string }) => item.key === record.key)?.sceneSha256);
  const b = metrics(before), a = metrics(after);
  let error = null; try { verifyRefinement(before, after); } catch (failure) { error = String(failure); failures.push({ key: record.key, error }); }
  results.push({ key: record.key, kind: record.kind, nodeId: record.nodeId, beforeSha256: sha(beforeBytes), afterSha256: sha(afterBytes),
    before: b, after: a, beforeIntrusions: intrusions(before), afterIntrusions: intrusions(after),
    changedEdgeIds: after.edges.filter((edge: { id: string; path: string }, index: number) => edge.path !== before.edges[index].path).map((edge: { id: string }) => edge.id), error });
}
writeFileSync(target, JSON.stringify({ schemaVersion: 1, createdAt: new Date().toISOString(), label,
  scope: 'Independent TypeScript geometric oracle over actual public API scenes. Different tensors and disjoint projected owners reported separately. Counts are pair-level and unique point per edge-pair; overlap length is merged per pair/lane. Not browser, human, performance or physical publication certification.',
  recordCounts: { total: 73, frontier: 9, detail: 28, move: 36 }, passed: results.length - failures.length, failures, results }, null, 2) + '\n');
for (const row of results.filter(result => result.kind === 'frontier')) process.stdout.write(JSON.stringify({ key: row.key, before: row.before.distinctTensor, after: row.after.distinctTensor,
  disjointBefore: row.before.disjointOwners, disjointAfter: row.after.disjointOwners, bendsBefore: row.before.totalBends, bendsAfter: row.after.totalBends, changed: row.changedEdgeIds.length, error: row.error }) + '\n');
process.stdout.write(JSON.stringify({ records: 73, passed: results.length - failures.length, failures }) + '\n');
if (failures.length) process.exitCode = 1;
