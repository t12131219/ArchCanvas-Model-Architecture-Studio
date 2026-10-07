import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';
import { findAnnotationBodyConflicts, suggestAnnotationPosition } from '../src/core/annotationPlacement.ts';
import { applyVisualBatch, buildScene, createDocument, createHistory, reduceHistory, renderSvg, validateDocument } from '../src/core/index.ts';
import type { Annotation, Architecture, Scene, SceneNode } from '../src/core/types.ts';

function node(id: string, x: number, y: number, width: number, height: number, parentId?: string, expanded = false): SceneNode {
  return { id, x, y, width, height, localX: x, localY: y, parentId, expanded, expandable: expanded,
    label: id, subtitle: '', headerHeight: 46, kind: 'Block', category: 'module', fill: '#ffffff', stroke: '#000000', glyph: 'module',
    pinned: false, evidence: 'source', ports: [] };
}

// Independent rectangles, deliberately unrelated to buildScene's layout rules.
function geometry(): Scene {
  return { version: '1.0', documentId: 'geometry', revision: 0, title: 'Authored rectangles',
    bounds: { x: -1000, y: -5000, width: 500000, height: 800000 },
    nodes: [node('frame', -20, 120, 800, 700, undefined, true), node('leaf', 30, 210, 100, 40, 'frame'),
      { ...node('collapsed', 270, 290, 120, 70, 'frame'), expandable: true }],
    edges: [], hiddenEdges: [], legend: [{ id: 'legend', label: 'Linear', color: '#ffffff', glyph: 'operator', x: 50, y: 900 }],
    annotations: [{ id: 'other', text: 'Existing note', x: 300, y: 1000, width: 380, height: 80 }],
    pageSpec: { widthMm: 180, background: '#ffffff', preset: 'paper' }, sourceDigest: 'source', irDigest: 'ir', diagnostics: [], sourceFacts: [] };
}

test('suggestion is below every current body, including expanded frames, legends and other notes', () => {
  const scene = geometry(), before = JSON.stringify(scene);
  assert.deepEqual(suggestAnnotationPosition(scene), { x: -20, y: 1104 }); // The last note ends at 1080.
  const note = { id: 'new', ...suggestAnnotationPosition(scene), width: 380, height: 45 };
  assert.deepEqual(findAnnotationBodyConflicts(scene, note), []);
  assert.equal(JSON.stringify(scene), before);
  scene.annotations = [];
  assert.deepEqual(suggestAnnotationPosition(scene), { x: -20, y: 928 }); // Legend swatch ends at 904.
  scene.legend = [];
  assert.deepEqual(suggestAnnotationPosition(scene), { x: -20, y: 844 }); // Frame ends at 820.
});

test('excluding the selected annotation ignores its old bounds and gives a stable repeated position', () => {
  const scene = geometry();
  scene.annotations.push({ id: 'selected', text: 'Selected note', x: -9000, y: 10000, width: 380, height: 90 });
  const before = JSON.stringify(scene), position = suggestAnnotationPosition(scene, 'selected');
  assert.deepEqual(position, { x: -20, y: 1104 });
  assert.equal(JSON.stringify(scene), before);
  scene.annotations[1] = { ...scene.annotations[1], ...position };
  // Even a stale/page-padded scene extent cannot feed the note's own body back into placement.
  scene.bounds.height += 10000;
  assert.deepEqual(suggestAnnotationPosition(scene, 'selected'), position);
  assert.equal(suggestAnnotationPosition(scene).y, 1218);
});

test('body conflicts include frontier leaves, legend labels and other notes, with exact touching permitted', () => {
  const scene = geometry(), note = { id: 'selected', x: 35, y: 220, width: 30, height: 20 };
  assert.deepEqual(findAnnotationBodyConflicts(scene, note), [{ kind: 'node', id: 'leaf' }]);
  assert.deepEqual(findAnnotationBodyConflicts(scene, { ...note, x: 280, y: 300 }), [{ kind: 'node', id: 'collapsed' }]);
  assert.deepEqual(findAnnotationBodyConflicts(scene, { ...note, x: 180, y: 500 }), []); // Empty space inside the frame.
  assert.deepEqual(findAnnotationBodyConflicts(scene, { ...note, x: 130, y: 220 }), []); // Touches the leaf's right edge.
  assert.deepEqual(findAnnotationBodyConflicts(scene, { ...note, y: 250 }), []); // Touches its bottom edge.
  assert.deepEqual(findAnnotationBodyConflicts(scene, { ...note, x: 50, y: 892 }), [{ kind: 'legend', id: 'legend' }]);
  // A long CJK legend extends well past the ordinary 175-unit footer allocation.
  scene.legend[0].label = '投影模块及输入输出关系的独立说明'.repeat(2);
  assert.deepEqual(findAnnotationBodyConflicts(scene, { ...note, x: 300, y: 890 }), [{ kind: 'legend', id: 'legend' }]);
  assert.deepEqual(findAnnotationBodyConflicts(scene, { ...note, x: 310, y: 1010 }), [{ kind: 'annotation', id: 'other' }]);
  assert.deepEqual(findAnnotationBodyConflicts(scene, scene.annotations[0]), []); // Self is excluded.
  assert.deepEqual(findAnnotationBodyConflicts(scene, { id: 'wide', x: 0, y: 200, width: 700, height: 900 }), [
    { kind: 'node', id: 'leaf' }, { kind: 'node', id: 'collapsed' }, { kind: 'legend', id: 'legend' }, { kind: 'annotation', id: 'other' },
  ]);
});

test('body conflict result does not assert orthogonal edge clearance', () => {
  const scene = geometry();
  scene.edges.push({ id: 'crossing', sourceId: 'leaf', targetId: 'collapsed', source: { nodeId: 'leaf', portId: 'out' },
    target: { nodeId: 'collapsed', portId: 'in' }, canonicalEdgeIds: ['crossing'], tensorId: 'tensor', role: 'data',
    path: 'M 180 480 V 560', stroke: '#000000', width: 1.5, dashed: false, label: '', labelX: 180, labelY: 480 });
  assert.deepEqual(findAnnotationBodyConflicts(scene, { id: 'on-route', x: 170, y: 500, width: 40, height: 30 }), []);
});

const project = fileURLToPath(new URL('../../', import.meta.url));
let transformer: Promise<Architecture> | undefined;
function formalTransformer(): Promise<Architecture> {
  // Static analysis imports only this formal checkout. It does not execute model source.
  transformer ??= promisify(execFile)('python3', ['-I', '-S', '-B', '-c',
    'import sys,json;from pathlib import Path;root=Path(sys.argv[1]);sys.path.insert(0,str(root/"src"));from archcanvas_python import analyze_project;print(json.dumps(analyze_project(root/"fixtures"/"transformer","model:Transformer")))', project],
  { encoding: 'utf8', maxBuffer: 2_000_000 }).then(({ stdout }) => JSON.parse(stdout));
  return transformer;
}
const expandedIds = ['repeat:instance:model.Transformer.encoder', 'call:instance:model.Transformer.encoder.0',
  'call:instance:model.Transformer.encoder.0.feedforward', 'call:instance:model.Transformer.decoder', 'call:instance:model.Transformer.decoder.feedforward'];

test('formal complex expansion keeps the existing absolute note and recommends a clear new note below the new frontier', async () => {
  const architecture = await formalTransformer();
  let document = createDocument(architecture);
  const note: Annotation = { id: 'absolute-note', text: 'Encoder context is reused by cross-attention.',
    ...suggestAnnotationPosition(buildScene(document)), width: 380, height: 55 };
  document = applyVisualBatch(document, [{ type: 'annotation', annotation: note }]);
  const overviewNote = buildScene(document).annotations[0], sourceBytes = JSON.stringify(document.architecture);
  for (const id of expandedIds) document = applyVisualBatch(document, [{ type: 'expand', id, expanded: true }]);
  assert.deepEqual(document.annotations, [note]);
  const scene = buildScene(document);
  assert.ok(scene.nodes.length > 20);
  assert.deepEqual(scene.annotations[0], overviewNote);
  const position = suggestAnnotationPosition(scene), newNote = { id: 'new', text: 'New note', ...position, width: 380, height: 45 };
  for (const body of [...scene.nodes, ...scene.annotations]) assert.ok(position.y > body.y + body.height);
  for (const legend of scene.legend) assert.ok(position.y > legend.y + 4);
  assert.deepEqual(findAnnotationBodyConflicts(scene, newNote), []);
  document = applyVisualBatch(document, [{ type: 'annotation', annotation: newNote }]);
  assert.deepEqual(document.annotations.find(annotation => annotation.id === note.id), note);
  assert.equal(JSON.stringify(document.architecture), sourceBytes);
  // Cached frontiers restore model layout without relocating either manual note.
  const layout = structuredClone(document.layout), annotations = structuredClone(document.annotations);
  const id = expandedIds[2];
  document = applyVisualBatch(document, [{ type: 'expand', id, expanded: false }]);
  document = applyVisualBatch(document, [{ type: 'expand', id, expanded: true }]);
  assert.deepEqual(document.layout, layout);
  assert.deepEqual(document.annotations, annotations);
});

test('explicit move below diagram is one annotation history operation and preserves save/export fields', async () => {
  let document = createDocument(await formalTransformer());
  for (const id of expandedIds) document = applyVisualBatch(document, [{ type: 'expand', id, expanded: true }]);
  const leaf = buildScene(document).nodes.find(item => item.id === 'call:instance:model.Transformer.encoder.0.feedforward.activation')!;
  const note: Annotation = { id: 'selected', text: 'Keep this explanation\nwith its chosen width.', x: leaf.x, y: leaf.y, width: 380, height: 75 };
  document = applyVisualBatch(document, [{ type: 'annotation', annotation: note }]);
  const scene = buildScene(document);
  assert.ok(findAnnotationBodyConflicts(scene, scene.annotations[0]).some(conflict => conflict.id === leaf.id));
  const moved = { ...note, ...suggestAnnotationPosition(scene, note.id) };
  const history = createHistory(document), after = reduceHistory(history, { type: 'apply', operations: [{ type: 'annotation', annotation: moved }], baseRevision: document.revision });
  assert.equal(after.past.length, 1);
  assert.equal(after.document.revision, document.revision + 1);
  assert.deepEqual(after.document.annotations, [moved]);
  assert.deepEqual(after.document.layout, document.layout);
  assert.deepEqual(after.document.layoutByFrontier, document.layoutByFrontier);
  assert.deepEqual(after.document.architecture, document.architecture);
  assert.deepEqual(findAnnotationBodyConflicts(buildScene(after.document), buildScene(after.document).annotations[0]), []);
  assert.deepEqual(suggestAnnotationPosition(buildScene(after.document), note.id), { x: moved.x, y: moved.y });
  const undone = reduceHistory(after, { type: 'undo' }), redone = reduceHistory(undone, { type: 'redo' });
  assert.deepEqual(undone.document.annotations, [note]);
  assert.deepEqual(redone.document.annotations, [moved]);
  const reopened = validateDocument(JSON.parse(JSON.stringify(redone.document)));
  assert.deepEqual(reopened.annotations, [moved]);
  assert.deepEqual(buildScene(reopened).annotations[0], { ...moved, width: 380, height: 75 });
  assert.equal(renderSvg(buildScene(reopened)), renderSvg(buildScene(redone.document)));
  assert.match(renderSvg(buildScene(reopened)), /data-annotation-id="selected"/);
});
