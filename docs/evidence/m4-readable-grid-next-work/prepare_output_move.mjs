// One source-backed typed visual operation; finite workload preparation only.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { applyVisualBatch, buildScene, renderSvg, validateDocument } from './inputs/formal-core/index.ts';
import { fitCameraToBounds } from './inputs/cameraProjection.ts';

const directory = path.dirname(new URL(import.meta.url).pathname);
const original = JSON.parse(fs.readFileSync(path.join(directory, 'inputs/previous-workload/grid.canvas.json'), 'utf8'));
const beforeScene = buildScene(original);
const network = original.architecture.nodes.find(node => node.id.endsWith('.network'));
const root = original.architecture.nodes.find(node => !node.parentId);
const output = original.architecture.nodes.find(node => node.id.startsWith('output:'));
const networkScene = beforeScene.nodes.find(node => node.id === network?.id);
const rootScene = beforeScene.nodes.find(node => node.id === root?.id);
const outputScene = beforeScene.nodes.find(node => node.id === output?.id);
if (!network || network.children.length !== 300 || !output || !networkScene || !rootScene || !outputScene || original.pinnedObjects.length) throw new Error('Frozen grid identity/frontier mismatch');
const targetAbsolute = { x: networkScene.x, y: networkScene.y + networkScene.height + 60 };
const operation = { type: 'move', ids: [output.id], dx: targetAbsolute.x - outputScene.x, dy: targetAbsolute.y - outputScene.y };
const document = applyVisualBatch(original, [operation]);
validateDocument(document);
const expected = structuredClone(original);
expected.revision += 1;
expected.layout[output.id].x += operation.dx;
expected.layout[output.id].y += operation.dy;
let changedFrontierLayouts = 0;
for (const snapshot of Object.values(expected.layoutByFrontier)) if (snapshot[output.id]) {
  snapshot[output.id].x += operation.dx;
  snapshot[output.id].y += operation.dy;
  changedFrontierLayouts += 1;
}
if (JSON.stringify(expected) !== JSON.stringify(document)) throw new Error('Unexpected mutation beyond output/revision');
if (JSON.stringify(original.architecture) !== JSON.stringify(document.architecture)) throw new Error('Canonical architecture changed');
const scene = buildScene(document);
const leaves = scene.nodes.filter(node => network.children.includes(node.id));
if (leaves.length !== 300) throw new Error('Workload lost a source-backed leaf');
const coverages = [{ width: 672, height: 711 }, { width: 3400, height: 1900 }, { width: 3800, height: 2100 }].map(viewport => {
  const camera = fitCameraToBounds(scene.bounds, viewport);
  const bodies = leaves.map(node => ({ id: node.id, x: camera.x + node.x * camera.zoom,
    y: camera.y + node.y * camera.zoom, width: node.width * camera.zoom, height: node.height * camera.zoom }));
  return { viewport, camera,
    intersecting: bodies.filter(b => b.x < viewport.width && b.y < viewport.height && b.x + b.width > 0 && b.y + b.height > 0).length,
    fullyInside: bodies.filter(b => b.x >= 0 && b.y >= 0 && b.x + b.width <= viewport.width && b.y + b.height <= viewport.height).length,
    minBodyWidthPx: Math.min(...bodies.map(b => b.width)), minBodyHeightPx: Math.min(...bodies.map(b => b.height)),
    nominalNodeFontPx: 13 * camera.zoom, bodies };
});
const changedRoutes = scene.edges.filter(edge => beforeScene.edges.find(e => e.id === edge.id)?.path !== edge.path).map(edge => ({ id: edge.id, before: beforeScene.edges.find(e => e.id === edge.id).path, after: edge.path, sourceId: edge.sourceId, targetId: edge.targetId }));
const hash = raw => crypto.createHash('sha256').update(raw).digest('hex');
const report = {
  schema: 'archcanvas-readable-grid-output-move-preparation/1',
  input: 'inputs/previous-workload/grid.canvas.json', inputSha256: hash(fs.readFileSync(path.join(directory, 'inputs/previous-workload/grid.canvas.json'))),
  sourceBindingDigest: document.sourceBindingDigest, irDigest: document.architecture.irDigest,
  operation, originalRevision: original.revision, revision: document.revision,
  outputId: output.id, rootId: root.id, networkId: network.id, changedFrontierLayouts,
  documentExactExceptOutputAndRevision: true, canonicalArchitectureExact: true,
  leafObjects: 300, sceneObjects: scene.nodes.length, edges: scene.edges.length,
  beforeBounds: beforeScene.bounds, bounds: scene.bounds,
  beforeRoot: rootScene, root: scene.nodes.find(node => node.id === root.id),
  network: scene.nodes.find(node => node.id === network.id), beforeOutput: outputScene,
  output: scene.nodes.find(node => node.id === output.id), changedRoutes,
  diagnostics: scene.diagnostics, coverages,
  scope: 'Frozen formal-core single typed output move only. Source-backed300 leaves preserved; nominal pixel arithmetic is not measured browser/font readability. No model execution, browser capture/timing, hardware/font proof, presented FPS, human participation, physical publication or performance gate.'
};
for (const [name, value] of [['typed-operation.json', operation], ['candidate.canvas.json', document], ['candidate.scene.json', scene], ['preparation-report.json', report]]) {
  fs.writeFileSync(path.join(directory, name), JSON.stringify(value, null, 2) + '\n', { flag: 'wx' });
}
fs.writeFileSync(path.join(directory, 'candidate.svg'), renderSvg(scene), { flag: 'wx' });
process.stdout.write(JSON.stringify({ beforeBounds: report.beforeBounds, bounds: report.bounds, rootHeight: report.root.height,
  output: { x: report.output.x, y: report.output.y }, changedRoutes: changedRoutes.length,
  diagnostics: report.diagnostics, coverages: coverages.map(({ bodies, ...rest }) => rest) }, null, 2) + '\n');
