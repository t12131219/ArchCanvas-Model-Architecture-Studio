/** Captures only public Canvas/Scene/SVG data; does not execute model code. */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { relative, resolve } from 'node:path';
import type { CanvasDocument, Scene } from '../../../../studio/src/core/types.ts';
import { buildScene, buildExportScene, renderSvg } from '../../../../studio/src/core/index.ts';
import { assertCanonicalCoverage, metrics, verifyRefinement } from '../ancestor-corridor-oracle.ts';

const root = fileURLToPath(new URL('../../../../', import.meta.url));
const output = fileURLToPath(new URL('current-attempt-1/', import.meta.url));
mkdirSync(output);
const sha = (raw: Buffer | string) => createHash('sha256').update(raw).digest('hex');
const binding = (path: string) => { const raw = readFileSync(path); return { path: relative(root, path), bytes: raw.length, sha256: sha(raw) }; };
const files = (path: string): string[] => readdirSync(path, { withFileTypes: true }).flatMap(entry => entry.isDirectory() ? files(resolve(path, entry.name)) : [resolve(path, entry.name)]);
const stablePaths = [...files(resolve(root, 'studio/src')), ...files(resolve(root, 'studio/tests')),
  resolve(root, 'docs/evidence/m4-ancestor-corridor-work/ancestor-corridor-oracle.ts'), fileURLToPath(import.meta.url),
  ...files(resolve(root, 'docs/evidence/m4-ancestor-corridor-work/baseline'))].sort();
const sourceBefore = stablePaths.map(binding);
const frozen = JSON.parse(readFileSync(resolve(root, 'docs/evidence/m4-ancestor-corridor-work/baseline/capture.json'), 'utf8')) as { records: { key: string; detailNodeId: string | null; input: { path: string }; scene: { path: string }; svg: { path: string } }[] };
const records = [];
for (const record of frozen.records) {
  const document = JSON.parse(readFileSync(resolve(root, record.input.path), 'utf8')) as CanvasDocument;
  const untouched = JSON.stringify(document), before = JSON.parse(readFileSync(resolve(root, record.scene.path), 'utf8')) as Scene;
  const scene = record.detailNodeId ? buildExportScene(document, { nodeId: record.detailNodeId }) : buildScene(document);
  const svg = renderSvg(scene), priorSvg = readFileSync(resolve(root, record.svg.path), 'utf8');
  const verified = verifyRefinement(before, scene, svg, priorSvg); assertCanonicalCoverage(scene, document.architecture);
  assert.equal(JSON.stringify(document), untouched);
  const scenePath = resolve(output, record.key + '.scene.json'), svgPath = resolve(output, record.key + '.svg');
  writeFileSync(scenePath, JSON.stringify(scene, null, 2) + '\n', { flag: 'wx' }); writeFileSync(svgPath, svg, { flag: 'wx' });
  const summary = (result: ReturnType<typeof metrics>) => ({ distinct: result.distinct, disjoint: result.disjoint, same: result.same,
    routeLength: result.routeLength, bends: result.bends, reversals: result.reversals });
  const pairKey = (pair: ReturnType<typeof metrics>['pairs'][number]) => JSON.stringify([pair.first, pair.second]);
  const oldCrosses = new Set(verified.before.pairs.filter(pair => !pair.sameTensor && pair.points.length).map(pairKey));
  const newCrosses = new Set(verified.after.pairs.filter(pair => !pair.sameTensor && pair.points.length).map(pairKey));
  records.push({ key: record.key, input: binding(resolve(root, record.input.path)), baselineScene: binding(resolve(root, record.scene.path)), baselineSvg: binding(resolve(root, record.svg.path)),
    scene: binding(scenePath), svg: binding(svgPath), unchangedScene: JSON.stringify(before) === JSON.stringify(JSON.parse(JSON.stringify(scene))), unchangedSvg: priorSvg === svg,
    before: summary(verified.before), after: summary(verified.after), changedEdgeIds: scene.edges.filter((edge, index) => edge.path !== before.edges[index].path).map(edge => edge.id),
    removedDistinctCrossingPairs: [...oldCrosses].filter(pair => !newCrosses.has(pair)), addedDistinctCrossingPairs: [...newCrosses].filter(pair => !oldCrosses.has(pair)),
    noNewSameTensorPairCrossings: true, immutableNodesPortsSourceAndSemantics: true, newBodyBackplateHeaderHits: [], retainedBlockedHits: verified.afterHits });
}
const sourceAfter = stablePaths.map(binding); assert.deepEqual(sourceAfter, sourceBefore);
const priorFailure = resolve(root, 'docs/evidence/m4-ancestor-corridor-work/root/capture-attempt-1');
const rejectedScene = JSON.parse(readFileSync(resolve(priorFailure, 'transformer-level3-paper-180.scene.json'), 'utf8')) as Scene;
const record = frozen.records.find(record => record.key === 'transformer-level3-paper-180')!;
const old = JSON.parse(readFileSync(resolve(root, record.scene.path), 'utf8')) as Scene;
let rejection = '';
try { verifyRefinement(old, rejectedScene, readFileSync(resolve(priorFailure, 'transformer-level3-paper-180.svg'), 'utf8'), readFileSync(resolve(root, record.svg.path), 'utf8')); }
catch (error) { rejection = error instanceof Error ? error.message : String(error); }
assert.ok(rejection); assert.equal(metrics(rejectedScene).distinct.overlapPairs, 20); assert.equal(metrics(rejectedScene).disjoint.overlapPairs, 16);
const report = { schemaVersion: 1, scope: 'AI independent public-data verification; no human or pixel acceptance claim',
  referenceReuse: 'No prototype code reused. Archived formal BG files are read-only observed baselines; the oracle independently parses and measures their public data.',
  checkedViews: records.length, records, sourceBeforeAfterExact: true, sourceBefore, sourceAfter,
  negativeCapturedAttempt: { scene: binding(resolve(priorFailure, 'transformer-level3-paper-180.scene.json')), svg: binding(resolve(priorFailure, 'transformer-level3-paper-180.svg')),
    rejected: true, reason: rejection, distinct: metrics(rejectedScene).distinct, disjoint: metrics(rejectedScene).disjoint },
  limitations: ['Geometry checks do not establish human readability or publication quality.', 'Routing budgets are literal deterministic work caps, not performance measurements.',
    'Different-tensor strict crossing pairs can be exchanged while protected aggregate counts do not increase.', 'The independent same-tensor pair gate validates captured results; the product family stage applies that gate, while the existing generic stage is unchanged.'] };
writeFileSync(resolve(output, 'report.json'), JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify({ checkedViews: records.length, sourceBeforeAfterExact: true, report: relative(root, resolve(output, 'report.json')) }));
