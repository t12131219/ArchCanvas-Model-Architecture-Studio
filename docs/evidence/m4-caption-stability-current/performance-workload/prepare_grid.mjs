// Source-backed 300-object view preparation, using ordinary typed moves only.
// This is workload preparation, never a performance or presented-FPS result.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { applyVisualBatch, buildScene, renderSvg, validateDocument } from '../before-change/inputs/studio/src/core/index.ts';
import { fitCameraToBounds } from '../before-change/inputs/studio/src/cameraProjection.ts';

const directory = path.dirname(new URL(import.meta.url).pathname);
const source = '/tmp/archcanvas-m4-next-20261006/documents/canvas-architecture-model.DenseStress300-24baae6df5c3-d01ce879.json';
const sourceBytes = fs.readFileSync(source);
const original = JSON.parse(sourceBytes).document;
const draft = structuredClone(original);
const network = draft.architecture.nodes.find(node => node.id.endsWith('.network'));
if (!network || network.children.length !== 300 || draft.pinnedObjects.length) throw new Error('Expected unpinned source-backed 300-child workload');
const operations = network.children.map((id, index) => {
  const row = Math.floor(index / 20), column = row % 2 ? 19 - index % 20 : index % 20;
  const prior = draft.layout[id];
  if (!prior) throw new Error('Every source-backed leaf must already be materialized');
  return { type: 'move', ids: [id], dx: 30 + column * 218 - prior.x, dy: 62 + row * 92 - prior.y };
});
fs.writeFileSync(path.join(directory, 'source-envelope.json'), sourceBytes, { flag: 'wx' });
fs.writeFileSync(path.join(directory, 'typed-moves.json'), JSON.stringify(operations, null, 2) + '\n', { flag: 'wx' });
const document = applyVisualBatch(draft, operations);
validateDocument(document);
if (JSON.stringify(document.architecture) !== JSON.stringify(original.architecture)) throw new Error('Workload changed source architecture');
if (document.sourceBindingDigest !== original.sourceBindingDigest) throw new Error('Workload changed source binding');
const scene = buildScene(document), actualLeaves = scene.nodes.filter(node => network.children.includes(node.id));
if (actualLeaves.length !== 300) throw new Error('Not all source-backed objects are visible in the scene');
const coverages = [{ width: 672, height: 641 }, { width: 3400, height: 1900 }, { width: 3800, height: 2100 }].map(viewport => {
  const camera = fitCameraToBounds(scene.bounds, viewport);
  const bodies = actualLeaves.map(node => ({ id: node.id, x: camera.x + node.x * camera.zoom,
    y: camera.y + node.y * camera.zoom, width: node.width * camera.zoom, height: node.height * camera.zoom }));
  const intersecting = bodies.filter(body => body.x < viewport.width && body.y < viewport.height && body.x + body.width > 0 && body.y + body.height > 0);
  const full = bodies.filter(body => body.x >= 0 && body.y >= 0 && body.x + body.width <= viewport.width && body.y + body.height <= viewport.height);
  return { viewport, camera, intersecting: intersecting.length, fullyInside: full.length,
    minBodyWidthPx: Math.min(...bodies.map(body => body.width)), minBodyHeightPx: Math.min(...bodies.map(body => body.height)),
    nominalNodeFontPx: 13 * camera.zoom, bodies };
});
const hash = raw => crypto.createHash('sha256').update(raw).digest('hex');
const report = { schema: 'archcanvas-source-backed-grid-preparation/1', source, sourceSha256: hash(sourceBytes),
  sourceArchitectureDigest: hash(JSON.stringify(original.architecture)), sourceBindingDigest: document.sourceBindingDigest,
  irDigest: document.architecture.irDigest, operations: operations.length, canonicalLeafObjects: 300,
  visibleSceneObjects: scene.nodes.length, bounds: scene.bounds, edges: scene.edges.length,
  diagnostics: scene.diagnostics, coverages,
  scope: 'Pure typed visual move workload preparation from a frozen source-backed document. No model execution, browser capture, timed interaction, font/hardware proof, human user or presented FPS.' };
fs.writeFileSync(path.join(directory, 'grid.canvas.json'), JSON.stringify(document, null, 2) + '\n', { flag: 'wx' });
fs.writeFileSync(path.join(directory, 'grid.scene.json'), JSON.stringify(scene, null, 2) + '\n', { flag: 'wx' });
fs.writeFileSync(path.join(directory, 'grid.svg'), renderSvg(scene), { flag: 'wx' });
fs.writeFileSync(path.join(directory, 'preparation-report.json'), JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
process.stdout.write(JSON.stringify({ sceneObjects: scene.nodes.length, leaves: 300, edges: scene.edges.length,
  bounds: scene.bounds, coverages: coverages.map(({ bodies, ...item }) => item), warnings: scene.diagnostics.filter(item => item.level === 'warning').length }, null, 2) + '\n');
