/** Read-only renderer replay and public capture comparison; no suite rerun. */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { relative, resolve } from 'node:path';
import { buildScene, renderSvg } from '../../../../../studio/src/core/index.ts';
import type { CanvasDocument, Scene } from '../../../../../studio/src/core/types.ts';
import { assertCanonicalCoverage, assertSvgAgreement, metrics, parseSvg } from '../../ancestor-corridor-oracle.ts';
const root = fileURLToPath(new URL('../../../../../', import.meta.url));
const output = fileURLToPath(new URL('./', import.meta.url));
const sha = (raw: Buffer | string) => createHash('sha256').update(raw).digest('hex');
const bind = (path: string) => { const raw = readFileSync(path); return { path: relative(root, path), bytes: raw.length, sha256: sha(raw) }; };
const paths = (path: string): string[] => readdirSync(path, { withFileTypes: true }).flatMap(entry => entry.isDirectory() ? paths(resolve(path, entry.name)) : [resolve(path, entry.name)]);
const browser = resolve(root, 'docs/evidence/m4-ancestor-corridor-work/browser-final-attempt-1');
const capture = resolve(root, 'docs/evidence/m4-ancestor-corridor-work/root/capture-attempt-3');
const sessionInput = resolve(root, 'docs/evidence/m4-ancestor-corridor-work/root/session-inputs.json');
const inputs = JSON.parse(readFileSync(sessionInput, 'utf8'));
const record = inputs.records.find((item: { case: string }) => item.case === 'transformer-level3-paper-180');
const storagePath = resolve(root, record.storedPath), fixturePath = resolve(root, record.inputPath);
const actualSvgPath = resolve(root, '.archcanvas/m4-ancestor-corridor-session/exports/72f21096acbc4dc1a3d98e1193baa8c9/figure.svg');
const sourcePaths = [...paths(resolve(root, 'studio/src')), resolve(root, 'studio/dist/index.html'), resolve(root, 'studio/dist/assets/index-au3IB_0Q.js'),
  resolve(root, 'studio/dist/assets/index-B6WbMowt.css'), resolve(root, 'docs/evidence/m4-ancestor-corridor-work/ancestor-corridor-oracle.ts'), fileURLToPath(import.meta.url),
  storagePath, fixturePath, sessionInput, ...['l3-public.json', 'l3.svg', 'l3-export-preview.svg', 'l3-export-browser.svg', 'export-links.json'].map(name => resolve(browser, name)), actualSvgPath,
  resolve(capture, 'transformer-level3-paper-180.scene.json'), resolve(capture, 'transformer-level3-paper-180.svg')].sort();
const before = sourcePaths.map(bind), fixture = JSON.parse(readFileSync(fixturePath, 'utf8')) as CanvasDocument;
assert.equal(bind(fixturePath).bytes, record.inputBytes); assert.equal(bind(fixturePath).sha256, record.inputSha256);
assert.equal(bind(storagePath).sha256, record.storedSha256);
const storage = JSON.parse(readFileSync(storagePath, 'utf8')) as { document: CanvasDocument; revision: number };
assert.equal(storage.revision, record.storageRevision); assert.equal(storage.document.revision, record.documentRevision);
assert.deepEqual(storage.document, fixture, 'saved Canvas differs from source-bound fixture');
const untouched = JSON.stringify(storage), scene = buildScene(storage.document), staticSvg = renderSvg(scene), interactiveSvg = renderSvg(scene, { interactive: true });
assert.equal(JSON.stringify(storage), untouched, 'renderer mutated saved Canvas');
const archivedScene = JSON.parse(readFileSync(resolve(capture, 'transformer-level3-paper-180.scene.json'), 'utf8')) as Scene;
assert.deepEqual(JSON.parse(JSON.stringify(scene)), archivedScene, 'current renderer replay differs from final bound capture');
assert.equal(staticSvg, readFileSync(resolve(capture, 'transformer-level3-paper-180.svg'), 'utf8'));
assertCanonicalCoverage(scene, storage.document.architecture);
const publicCapture = JSON.parse(readFileSync(resolve(browser, 'l3-public.json'), 'utf8')) as { scripts: string[]; css: string[]; footer: string; svg: string };
assert.deepEqual(publicCapture.scripts, ['/assets/index-au3IB_0Q.js']); assert.deepEqual(publicCapture.css, ['/assets/index-B6WbMowt.css']);
assert.equal(bind(resolve(root, 'studio/dist/assets/index-au3IB_0Q.js')).sha256, 'dca15460bc9ed8def5ff80c9da5dfcf16bb49f7a230986e0ffeef1a6b0e7548b');
assert.equal(bind(resolve(root, 'studio/dist/assets/index-B6WbMowt.css')).sha256, '172a09a8c147e53c3bef426cf76b59b8cc4893e891eb6e920aa7b25a0bb024e0');
const publicSvg = readFileSync(resolve(browser, 'l3.svg'), 'utf8'); assert.equal(publicCapture.svg, publicSvg);
const actualSvg = readFileSync(actualSvgPath, 'utf8'), browserExport = readFileSync(resolve(browser, 'l3-export-browser.svg'), 'utf8');
const geometries = [assertSvgAgreement(scene, staticSvg), assertSvgAgreement(scene, interactiveSvg), assertSvgAgreement(scene, publicSvg), assertSvgAgreement(scene, actualSvg), assertSvgAgreement(scene, browserExport)];
const mapped = (geometry: ReturnType<typeof parseSvg>) => ({ cards: [...geometry.cards], circles: [...geometry.circles], paths: [...geometry.paths], styles: [...geometry.styles], metadata: geometry.metadata, bounds: geometry.bounds });
for (const geometry of geometries.slice(1)) assert.deepEqual(mapped(geometry), mapped(geometries[0]), 'interactive/static/public/actual export geometry or metadata differs');
const metric = metrics(scene); assert.equal(metric.distinct.overlapPairs, 17); assert.equal(metric.distinct.crossingPairs, 20); assert.equal(metric.distinct.crossingPoints, 23);
const after = sourcePaths.map(bind); assert.deepEqual(after, before);
writeFileSync(resolve(output, 'renderer-replay.scene.json'), JSON.stringify(scene, null, 2) + '\n', { flag: 'wx' });
writeFileSync(resolve(output, 'renderer-replay-static.svg'), staticSvg, { flag: 'wx' });
writeFileSync(resolve(output, 'renderer-replay-interactive.svg'), interactiveSvg, { flag: 'wx' });
const report = { schemaVersion: 1, scope: 'Read-only public browser/SVG/source replay; no suite, model, browser or service run',
  sourceBeforeAfterExact: true, sourceBefore: before, sourceAfter: after, savedCanvasEqualsSourceBoundInput: true,
  storageRevision: storage.revision, canvasRevision: scene.revision, documentId: scene.documentId, sourceDigest: scene.sourceDigest, irDigest: scene.irDigest,
  currentBundleBound: true, publicCaptureFooter: publicCapture.footer, rootFinalCaptureSceneAndStaticSvgExact: true,
  wholeArchitectureAndCanonicalCoverageExact: true, interactiveStaticPublicExportGeometryAndMetadataExact: true,
  visibleNodes: scene.nodes.length, visibleEdges: scene.edges.length, visiblePorts: scene.nodes.reduce((n, node) => n + node.ports.length, 0),
  distinct: metric.distinct, same: metric.same, disjoint: metric.disjoint,
  previewRaw: { binding: bind(resolve(browser, 'l3-export-preview.svg')), architecturePreview: false, reason: 'Raw capture is the 18x18 modal close icon; it carries no architecture Scene metadata.' },
  replayArtifacts: ['renderer-replay.scene.json', 'renderer-replay-static.svg', 'renderer-replay-interactive.svg'].map(name => bind(resolve(output, name))),
  limitations: ['14% fit panorama does not prove publication clarity.', 'Actual export screenshot covers the top region only.', 'No new full visual matrix or human review was performed.', 'Port raw source readback and fresh persistence check have separate scope.'] };
writeFileSync(resolve(output, 'renderer-readback.json'), JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify({ sourceBeforeAfterExact: true, visibleNodes: scene.nodes.length, visibleEdges: scene.edges.length, staticSvgSha256: sha(staticSvg) }));
