/** Public generated figure replay only; no suite or model code execution. */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { relative, resolve } from 'node:path';
import { buildScene, renderSvg } from '../../../../../studio/src/core/index.ts';
import type { CanvasDocument } from '../../../../../studio/src/core/types.ts';
import { assertCanonicalCoverage, assertSvgAgreement, metrics, parseSvg } from '../../ancestor-corridor-oracle.ts';
const root = fileURLToPath(new URL('../../../../../', import.meta.url));
const output = fileURLToPath(new URL('./', import.meta.url));
const binding = (path: string) => { const raw = readFileSync(path); return { path: relative(root, path), bytes: raw.length, sha256: createHash('sha256').update(raw).digest('hex') }; };
const files = (path: string): string[] => readdirSync(path, { withFileTypes: true }).flatMap(entry => entry.isDirectory() ? files(resolve(path, entry.name)) : [resolve(path, entry.name)]);
const browser = resolve(root, 'docs/evidence/m4-ancestor-corridor-work/browser-final-attempt-1');
const storagePath = resolve(root, '.archcanvas/m4-ancestor-corridor-session/documents/canvas-architecture-model.AuthoredModel-d97a0e89743e-7a326f80.json');
const draftPath = resolve(root, '.archcanvas/m4-ancestor-corridor-session/drafts/draft-859cef62-6bbe-45c6-a166-b5f519d7e600.json');
const sourcePath = resolve(root, '.archcanvas/m4-ancestor-corridor-session/projects/d0af06253a654c978020939ad5fe717d/source/model.py');
const sourcePaths = [...files(resolve(root, 'studio/src')), ...files(resolve(root, 'studio/tests')), sourcePath, storagePath, draftPath,
  resolve(root, 'studio/dist/assets/index-au3IB_0Q.js'), resolve(root, 'studio/dist/assets/index-B6WbMowt.css'),
  resolve(root, 'docs/evidence/m4-ancestor-corridor-work/ancestor-corridor-oracle.ts'), fileURLToPath(import.meta.url),
  ...['from-zero-generated-figure.svg', 'from-zero-generated-figure.dom.txt', 'from-zero-generated-saved.dom.txt', 'final-public.json'].map(name => resolve(browser, name))].sort();
const before = sourcePaths.map(binding);
const storage = JSON.parse(readFileSync(storagePath, 'utf8')) as { document: CanvasDocument; revision: number };
const draft = JSON.parse(readFileSync(draftPath, 'utf8')).draft;
assert.equal(storage.revision, 1); assert.equal(storage.document.revision, 0);
const document = storage.document, original = JSON.stringify(document), architecture = document.architecture;
assert.equal(architecture.entry, 'model:AuthoredModel'); assert.equal(architecture.nodes.length, 5); assert.equal(architecture.edges.length, 4);
assert.equal(architecture.sources.length, 1); assert.equal(architecture.sources[0].path, 'model.py');
assert.equal(architecture.sources[0].content, readFileSync(sourcePath, 'utf8')); assert.equal(architecture.sources[0].digest, binding(sourcePath).sha256);
assert.equal(document.sourceBindingDigest, architecture.sourceDigest);
const scene = buildScene(document), staticSvg = renderSvg(scene), interactiveSvg = renderSvg(scene, { interactive: true });
assert.equal(JSON.stringify(document), original, 'renderer mutated saved generated Canvas');
const publicSvg = readFileSync(resolve(browser, 'from-zero-generated-figure.svg'), 'utf8');
const geometries = [assertSvgAgreement(scene, publicSvg), assertSvgAgreement(scene, staticSvg), assertSvgAgreement(scene, interactiveSvg)];
const geometryFacts = (geometry: ReturnType<typeof parseSvg>) => ({ cards: [...geometry.cards], circles: [...geometry.circles], paths: [...geometry.paths], styles: [...geometry.styles], metadata: geometry.metadata, bounds: geometry.bounds });
for (const geometry of geometries.slice(1)) assert.deepEqual(geometryFacts(geometry), geometryFacts(geometries[0]), 'saved generated Canvas replay/public SVG facts differ');
assertCanonicalCoverage(scene, architecture);
assert.equal(scene.nodes.length, 5); assert.equal(scene.edges.length, 3); assert.deepEqual(scene.hiddenEdges, ['edge:0']);
assert.deepEqual(scene.edges.map(edge => edge.id), ['edge:1', 'edge:2', 'edge:3']);
const kindNode = (kind: string) => { const members = scene.nodes.filter(node => node.kind === kind); assert.equal(members.length, 1); return members[0]; };
const leafNodes = ['Input', 'Linear', 'ReLU', 'Output'].map(kindNode);
for (let index = 0; index < 4; index++) {
  assert.equal(leafNodes[index].label, draft.nodes[index].label);
  assert.equal(document.displayAliases[leafNodes[index].id], draft.nodes[index].label);
}
for (let index = 0; index < 3; index++) {
  assert.equal(scene.edges[index].sourceId, leafNodes[index].id); assert.equal(scene.edges[index].targetId, leafNodes[index + 1].id); assert.equal(scene.edges[index].role, 'data');
}
const final = JSON.parse(readFileSync(resolve(browser, 'final-public.json'), 'utf8'));
assert.deepEqual(final.scripts, ['/assets/index-au3IB_0Q.js']); assert.deepEqual(final.styles, ['/assets/index-B6WbMowt.css']);
assert.equal(binding(resolve(root, 'studio/dist/assets/index-au3IB_0Q.js')).sha256, 'dca15460bc9ed8def5ff80c9da5dfcf16bb49f7a230986e0ffeef1a6b0e7548b');
assert.equal(binding(resolve(root, 'studio/dist/assets/index-B6WbMowt.css')).sha256, '172a09a8c147e53c3bef426cf76b59b8cc4893e891eb6e920aa7b25a0bb024e0');
const measured = metrics(scene); assert.equal(measured.distinct.crossingPairs, 0); assert.equal(measured.distinct.overlapPairs, 0);
const after = sourcePaths.map(binding); assert.deepEqual(after, before);
for (const [name, raw] of [['generated-replay.scene.json', JSON.stringify(scene, null, 2) + '\n'], ['generated-replay-static.svg', staticSvg], ['generated-replay-interactive.svg', interactiveSvg]])
  writeFileSync(resolve(output, name), raw, { flag: 'wx' });
const report = { schemaVersion: 1, scope: 'Readonly saved generated working-copy Canvas/source/public SVG replay, no tests or user model execution',
  sourceBeforeAfterExact: true, sourceBefore: before, sourceAfter: after, storageRevision: storage.revision, canvasRevision: document.revision,
  documentId: document.id, sourceDigest: architecture.sourceDigest, irDigest: architecture.irDigest, sourceTextAndDirectSourceDigestExact: true,
  canonicalIrNodes: 5, canonicalIrEdges: 4, displayedNodes: 5, displayedLeafNodes: 4, displayedEdges: 3, hiddenRootInputEdges: scene.hiddenEdges,
  draftToGeneratedLeafKindsLabelsAndBindingsMatch: true, generatedPublicAndSavedReplayGeometryMetadataExact: true, currentAuB6AssetsBound: true,
  distinct: measured.distinct, same: measured.same, disjoint: measured.disjoint,
  artifacts: ['generated-replay.scene.json', 'generated-replay-static.svg', 'generated-replay-interactive.svg'].map(name => binding(resolve(output, name))),
  limitations: ['Aliases shown are initialized from this authored Draft; no imported Canvas alias editing/reopen retest was done.',
    'Input [1,16]/float32 is a Draft declaration, not a source/static IR inferred runtime input shape.', 'IR preserves torch.float32 constructor expression with unknown origin; no numerical dtype/shape execution is certified.',
    'Five displayed nodes include a root container; the authored computational leaf graph remains four nodes/three edges.', 'Source/model code was read as text only.', 'No new test suite, install, full matrix, browser operation or human visual acceptance here.'] };
writeFileSync(resolve(output, 'generated-figure-readback.json'), JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify({ sourceBeforeAfterExact: true, publicAndSavedReplayGeometryMetadataExact: true, canonicalIr: '5/4', leafGraph: '4/3' }));
