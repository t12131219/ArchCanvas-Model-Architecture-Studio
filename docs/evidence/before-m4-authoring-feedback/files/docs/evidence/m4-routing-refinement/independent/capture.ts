import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, relative } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import type { CanvasDocument, Scene } from '../../../../studio/src/core/types.ts';

const root = resolve(fileURLToPath(new URL('../../../..', import.meta.url)));
const mode = process.argv[2];
if (!['before', 'after'].includes(mode)) throw new Error('Usage: capture.ts before|after');
const label = process.argv[3] ?? mode;
if (!/^(before|after)(?:-[a-z0-9]+)*$/.test(label)) throw new Error('Invalid capture directory label');
const destination = resolve(root, 'docs/evidence/m4-routing-refinement/independent', label);
if (existsSync(destination)) throw new Error(`Refusing to overwrite ${destination}`);
const sourceRoot = mode === 'before' ? resolve(root, 'docs/evidence/before-m4-routing-refinement/files/studio/src/core') : resolve(root, 'studio/src/core');
const core = await import(pathToFileURL(resolve(sourceRoot, 'index.ts')).href);
const previewApi = await import(pathToFileURL(resolve(sourceRoot, 'movePreview.ts')).href);
const sha = (data: string | Buffer) => createHash('sha256').update(data).digest('hex');
const sourceFiles = ['index.ts', 'document.ts', 'scene.ts', 'exportScene.ts', 'movePreview.ts', 'orthogonalRouter.ts', 'types.ts', 'validate.ts', 'nodeFacts.ts', 'svg.ts', 'tokens.ts', 'typography.ts', 'annotationPlacement.ts'];
const sourceHashesBefore = Object.fromEntries(sourceFiles.map(file => [file, sha(readFileSync(resolve(sourceRoot, file)))]));
export const frontierCases = [
  'mlp-level0-paper-180', 'mlp-level1-paper-180',
  'residual_cnn-level0-paper-180', 'residual_cnn-level1-paper-180', 'residual_cnn-level2-paper-180',
  'transformer-level0-paper-180', 'transformer-level1-paper-180', 'transformer-level2-paper-180', 'transformer-level3-paper-180',
];
export const moves = [{ name: 'left', dx: -180, dy: 0 }, { name: 'right', dx: 180, dy: 0 }, { name: 'up', dx: 0, dy: -80 }, { name: 'down', dx: 0, dy: 25 }];
mkdirSync(destination, { recursive: true });
const records: unknown[] = [];
const normalizeRevision = (scene: Scene) => ({ ...scene, revision: 0 });
function store(key: string, scene: Scene, extra: object) {
  const json = JSON.stringify(scene, null, 2) + '\n';
  writeFileSync(resolve(destination, `${key}.scene.json`), json);
  const svg = core.renderSvg(scene);
  writeFileSync(resolve(destination, `${key}.svg`), svg);
  records.push({ key, ...extra, sceneSha256: sha(json), svgSha256: sha(svg) });
}
for (const caseId of frontierCases) {
  const inputPath = resolve(root, `docs/evidence/browser-visual-matrix-boundary-final/captures/${caseId}/canvas.json`);
  const inputBytes = readFileSync(inputPath), document = JSON.parse(inputBytes.toString()) as CanvasDocument, original = JSON.stringify(document);
  const scene = core.buildScene(document);
  assert.equal(JSON.stringify(document), original);
  assert.deepEqual(scene, core.buildScene(document));
  assert.deepEqual(scene, core.buildExportScene(document));
  store(caseId, scene, { kind: 'frontier', caseId, inputPath: relative(root, inputPath), inputSha256: sha(inputBytes) });
  for (const [index, node] of scene.nodes.filter((node: Scene['nodes'][number]) => node.expanded && node.expandable).entries()) {
    const detail = core.buildExportScene(document, { nodeId: node.id });
    assert.deepEqual(detail, core.buildExportScene(document, { nodeId: node.id }));
    assert.equal(JSON.stringify(document), original);
    store(`${caseId}-detail-${index}`, detail, { kind: 'detail', caseId, nodeId: node.id });
  }
  const node = scene.nodes.find((node: Scene['nodes'][number]) => !node.pinned && !node.expanded && !['input', 'output'].includes(node.category));
  assert.ok(node, `No unpinned source-bound object in ${caseId}`);
  for (const move of moves) {
    const session = previewApi.prepareMovePreview(document, [node.id]);
    const preview = previewApi.previewMoveScene(session, move.dx, move.dy);
    assert.deepEqual(preview, previewApi.previewMoveScene(session, move.dx, move.dy));
    const committed = core.reduceHistory(core.createHistory(document), { type: 'apply', baseRevision: document.revision,
      operations: [{ type: 'move', ids: [node.id], dx: move.dx, dy: move.dy }] });
    const committedScene = core.buildScene(committed.document);
    assert.deepEqual(preview, committedScene);
    assert.equal(core.renderSvg(preview), core.renderSvg(committedScene));
    assert.equal(JSON.stringify(document), original);
    assert.deepEqual(committed.document.architecture, document.architecture);
    assert.deepEqual(committed.document.pinnedObjects, document.pinnedObjects);
    const undo = core.reduceHistory(committed, { type: 'undo' }), redo = core.reduceHistory(undo, { type: 'redo' });
    assert.deepEqual(undo.document.layout, document.layout);
    assert.deepEqual(redo.document.layout, committed.document.layout);
    assert.deepEqual(normalizeRevision(core.buildScene(undo.document)), normalizeRevision(scene));
    assert.deepEqual(normalizeRevision(core.buildScene(redo.document)), normalizeRevision(committedScene));
    store(`${caseId}-move-${move.name}`, committedScene, { kind: 'move', caseId, nodeId: node.id, ...move,
      checks: ['preview=commit', 'SVG preview=commit', 'deterministic', 'document immutable', 'architecture unchanged', 'pins unchanged', 'undo exact layout+scene', 'redo exact layout+scene'] });
  }
}
const sourceHashesAfter = Object.fromEntries(sourceFiles.map(file => [file, sha(readFileSync(resolve(sourceRoot, file)))]));
assert.deepEqual(sourceHashesAfter, sourceHashesBefore, 'source changed during scene capture');
writeFileSync(resolve(destination, 'capture.json'), JSON.stringify({ schemaVersion: 1, capturedAt: new Date().toISOString(), mode,
  sourceRoot: relative(root, sourceRoot), sourceFiles: sourceHashesAfter, sourceStableDuringCapture: true,
  scope: 'Actual public buildScene, buildExportScene, movePreview and history outputs; no model imports/execution, no browser/human/performance certification.',
  records }, null, 2) + '\n');
process.stdout.write(JSON.stringify({ mode, records: records.length, frontier: 9, move: 36, detail: records.length - 45 }) + '\n');
