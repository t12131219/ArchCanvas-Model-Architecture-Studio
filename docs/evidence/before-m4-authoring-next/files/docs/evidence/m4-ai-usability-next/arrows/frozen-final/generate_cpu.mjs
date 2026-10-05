// CPU rerender only: historical source-bound CanvasDocuments, newly frozen core.
// This script does not create browser coverage, presented timing, or human acceptance.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, relative } from 'node:path';
import { buildScene, renderSvg } from './files/studio/src/core/index.ts';

const root = fileURLToPath(new URL('../../../../../', import.meta.url));
const here = fileURLToPath(new URL('./', import.meta.url));
const sourceManifestPath = join(here, 'manifest.json');
const sourceManifest = JSON.parse(readFileSync(sourceManifestPath, 'utf8'));
const inputManifestPath = join(root, 'docs/evidence/browser-visual-matrix-boundary-final/manifest.json');
const inputManifest = JSON.parse(readFileSync(inputManifestPath, 'utf8'));
const inputRoot = join(root, 'docs/evidence/browser-visual-matrix-boundary-final');
const out = join(here, 'cpu-scenes');
mkdirSync(out, { recursive: true });
const sha = path => createHash('sha256').update(readFileSync(path)).digest('hex');
function verifyArchive() {
  for (const file of sourceManifest.files) assert.equal(sha(join(root, file.archivePath)), file.sha256, file.archivePath);
}
verifyArchive();
const cases = [];
for (const input of inputManifest.captures) {
  const canvasPath = join(inputRoot, input.files.canvas.path);
  assert.equal(sha(canvasPath), input.files.canvas.sha256, `${input.caseId}: historical input binding`);
  const document = JSON.parse(readFileSync(canvasPath, 'utf8'));
  const before = JSON.stringify(document);
  const scene = buildScene(document);
  assert.equal(JSON.stringify(document), before, `${input.caseId}: input mutated`);
  assert.deepEqual(scene.sourceFacts.map(fact => fact.id).sort(), document.architecture.nodes.map(node => node.id).sort());
  const svgPath = join(out, `${input.caseId}.svg`);
  // Match the saved-browser SVG's port-group representation so the independent
  // oracle can compare endpoints against individual canonical port dots.
  writeFileSync(svgPath, renderSvg(scene, { interactive: true }));
  cases.push({ caseId: input.caseId, inputCanvasPath: relative(root, canvasPath), inputCanvasSha256: input.files.canvas.sha256,
    svgPath: relative(root, svgPath), svgSha256: sha(svgPath), documentId: document.documentId, revision: document.revision,
    sourceDigest: document.architecture.sourceDigest, irDigest: document.architecture.irDigest,
    nodeCount: scene.nodes.length, edgeCount: scene.edges.length, bounds: scene.bounds, diagnostics: scene.diagnostics });
}
verifyArchive();
const output = { schemaVersion: 1, scope: '39 historical CanvasDocument inputs rerendered with frozen final CPU core; no new browser captures or inherited browser coverage',
  humanAcceptanceCertified: false, browserCoverageInherited: false, rendererMode: 'CPU interactive SVG; no browser involved',
  frozenSourceManifestPath: relative(root, sourceManifestPath), frozenSourceManifestSha256: sha(sourceManifestPath),
  historicalInputManifestPath: relative(root, inputManifestPath), historicalInputManifestSha256: sha(inputManifestPath),
  generatorPath: relative(root, fileURLToPath(import.meta.url)), generatorSha256: sha(fileURLToPath(import.meta.url)),
  archiveHashCheckBeforeAfter: true, cases };
writeFileSync(join(here, 'cpu-scenes.json'), JSON.stringify(output, null, 2) + '\n');
console.log(JSON.stringify({ cases: cases.length, diagnostics: cases.reduce((sum, item) => sum + item.diagnostics.length, 0), sourceManifestSha256: output.frozenSourceManifestSha256 }));
