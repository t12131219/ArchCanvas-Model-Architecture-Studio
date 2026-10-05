import assert from 'node:assert/strict';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { architecture, placeFixture } from './fixtures.ts';
import { metrics, intrusions, verifyRefinement } from './oracle.ts';

const root = resolve(fileURLToPath(new URL('../../../..', import.meta.url))), mode = process.argv[2], label = process.argv[3] ?? mode;
if (!['before', 'after'].includes(mode) || !/^(before|after)(?:-[a-z0-9]+)*$/.test(label)) throw new Error('Usage capture-fixtures.ts before|after [label]');
const sourceRoot = mode === 'before' ? resolve(root, 'docs/evidence/before-m4-routing-refinement/files/studio/src/core') : resolve(root, 'studio/src/core');
const core = await import(pathToFileURL(resolve(sourceRoot, 'index.ts')).href);
const target = resolve(root, `docs/evidence/m4-routing-refinement/independent/${label}/fixtures.json`);
if (existsSync(target)) throw new Error('Refusing to overwrite fixtures output');
const cases = ['different-tensors', 'shared-trunk', 'unavoidable-stub'] as const;
const records = cases.map(kind => {
  const document = placeFixture(core.createDocument(architecture(kind))), before = JSON.stringify(document);
  const scene = core.buildScene(document);
  assert.equal(JSON.stringify(document), before); assert.deepEqual(scene, core.buildScene(document));
  const report = mode === 'after' ? verifyRefinement(JSON.parse(readFileSync(resolve(root, 'docs/evidence/m4-routing-refinement/independent/before/fixtures.json'), 'utf8')).records.find((row: { kind: string }) => row.kind === kind).scene, scene) : null;
  return { kind, document, scene, svg: core.renderSvg(scene), metrics: metrics(scene), intrusions: intrusions(scene), report };
});
writeFileSync(target, JSON.stringify({ schemaVersion: 1, mode, createdAt: new Date().toISOString(),
  sourceHashes: Object.fromEntries(['scene.ts', 'orthogonalRouter.ts'].map(file => [file, createHash('sha256').update(readFileSync(resolve(sourceRoot, file))).digest('hex')])),
  scope: 'Hand-written semantic edge fixtures via actual public createDocument/buildScene; no model imported/executed. Shared tensor trunks are separately measured; endpoint-shared different tensors may retain unavoidable departure overlap.', records }, null, 2) + '\n');
for (const row of records) process.stdout.write(JSON.stringify({ kind: row.kind, distinct: row.metrics.distinctTensor, shared: row.metrics.sameTensor, bends: row.metrics.totalBends }) + '\n');
