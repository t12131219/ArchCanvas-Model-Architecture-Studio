import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createDocument, applyVisualBatch, buildScene } from '../src/core/index.ts';
import { validateArchitecture } from '../src/core/validate.ts';
import { buildExportScene } from '../src/core/exportScene.ts';
import { renderSvg } from '../src/core/svg.ts';
import { orthogonalPathPoints } from '../src/core/orthogonalRouter.ts';
import { editorSceneBounds } from '../src/core/editorPresentation.ts';
import { projectSourceEditing } from '../src/sourceEditingProjection.ts';
import { draftSourceRelations } from '../src/draftSourceRelations.ts';
import { draftRoutes, moveDraftNodes, sourceDraftCatalog } from '../src/authoring.ts';
import { sameSourceSemantics, sourcePresentationOperations } from '../src/sourcePresentation.ts';
import type { Architecture } from '../src/core/types.ts';
import type { ImportedSourceDraft } from '../src/api.ts';

const project = fileURLToPath(new URL('../../', import.meta.url));
function backend(expression: string, value: unknown): Promise<any> {
  return new Promise((resolve, reject) => {
    const child = execFile(`${project}.venv/bin/python`, ['-I','-S','-B','-c',
      `import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_python import analyze_source;from archcanvas_authoring.source_import import import_editable_source_draft;v=json.load(sys.stdin);${expression}`, project],
      { maxBuffer: 20_000_000 }, (error, stdout) => { if (error) reject(error); else try { resolve(JSON.parse(stdout)); } catch (error) { reject(error); } });
    child.stdin!.end(JSON.stringify(value));
  });
}
const source = `from torch import nn
class FernCell(nn.Module):
 def __init__(self):
  super().__init__(); self.projection=nn.Linear(4,4); self.activation=nn.GELU(); self.head=nn.Linear(4,2)
 def forward(self,x): return self.head(self.activation(self.projection(x)))
class UnknownFern(nn.Module):
 def __init__(self,config):
  super().__init__(); self.enabled=config.alternative; self.left=FernCell(); self.right=FernCell()
 def forward(self,x):
  if self.enabled: x=self.left(x)
  else: x=self.right(x)
  return x
`;
let analyzed: Promise<Architecture>;
const architecture = () => analyzed ??= backend('print(json.dumps(analyze_source(v,"model:UnknownFern")))', source);

test('source dependency arrows restore after collapse and JSON reopen without changing tensor edges or ports', async () => {
  const a = await architecture(), view = createDocument(a), full = projectSourceEditing(view).document;
  assert.equal(a.sourceRelations!.length, 4);
  assert.equal(buildScene(view).sourceRelations?.length ?? 0, 0);
  const scene = buildScene(full), left = a.nodes.find(n => n.label === 'left')!;
  const branches = scene.nodes.filter(n => n.kind === 'SourceBranch');
  assert.equal(branches[0].y, branches[1].y, 'alternative paths are displayed side by side');
  assert.notEqual(branches[0].x, branches[1].x);
  assert.equal(scene.sourceRelations!.length, 4);
  assert.ok(scene.sourceRelations!.every(r => r.evidence.length && !('tensorId' in r)));
  assert.ok(scene.nodes.filter(n => a.nodes.find(f => f.id === n.id)?.sourceStructure).every(n => !n.ports.length));
  const collapsed = applyVisualBatch(full, [{ type: 'expand', id: left.id, expanded: false }]);
  assert.equal(buildScene(collapsed).sourceRelations!.length, 2);
  const reopened = applyVisualBatch(JSON.parse(JSON.stringify(collapsed)), [{ type: 'expand', id: left.id, expanded: true }]);
  assert.deepEqual(buildScene(reopened).sourceRelations, scene.sourceRelations);
  assert.deepEqual(reopened.architecture, a);
  assert.deepEqual(buildScene(reopened).edges, scene.edges);
  assert.deepEqual(scene.diagnostics.filter(d => d.code === 'layout-route-blocked'), []);
});

test('source arrows and separate legend appear in publication/editor SVG and stay inside fit bounds', async () => {
  const full = projectSourceEditing(createDocument(await architecture())).document, scene = buildScene(full);
  const svg = renderSvg(scene), editor = renderSvg(scene, { presentation: 'editor' });
  assert.equal((svg.match(/data-source-relation-id=/g) ?? []).length, 4);
  assert.equal((editor.match(/data-source-relation-id=/g) ?? []).length, 4);
  assert.match(svg, /Source data dependency/); assert.match(svg, /renderedSourceRelations/);
  const bounds = editorSceneBounds(scene);
  for (const relation of scene.sourceRelations!) for (const point of orthogonalPathPoints(relation.path)) {
    for (const box of [scene.bounds, bounds]) assert.ok(point.x >= box.x && point.x <= box.x + box.width && point.y >= box.y && point.y <= box.y + box.height);
  }
  const mono = buildScene({ ...full, pageSpec: { ...full.pageSpec, preset: 'monochrome' } });
  assert.ok(mono.sourceRelations!.every(r => r.stroke === '#56616b'));
  assert.match(renderSvg(mono), /stroke-dasharray="2 4"/);
});

test('detail export includes only dependencies inside its selected source subtree', async () => {
  const a = await architecture(), full = projectSourceEditing(createDocument(a)).document;
  const left = a.nodes.find(n => n.label === 'left')!, detail = buildExportScene(full, { nodeId: left.id });
  assert.equal(detail.sourceRelations!.length, 2);
  assert.ok(detail.sourceRelations!.every(r => r.evidence.every(e => detail.exportScope!.canonicalNodeIds.includes(e.sourceId) && detail.exportScope!.canonicalNodeIds.includes(e.targetId))));
  const right = a.nodes.find(n => n.label === 'right')!;
  assert.equal(buildExportScene(full, { nodeId: right.id }).sourceRelations!.length, 2);
  assert.equal((renderSvg(detail).match(/data-source-relation-id=/g) ?? []).length, 2);
  assert.deepEqual(detail.edges.flatMap(e => e.canonicalEdgeIds), [], 'inspection detail cannot invent tensor edges');
});

test('source relations reject tensor endpoints, self loops, extra bindings and duplicate identities', async () => {
  const a = await architecture(); validateArchitecture(a);
  for (const change of [
    (r: any) => { r.sourceId = a.nodes.find(n => n.kind === 'Input')!.id; },
    (r: any) => { r.sourceId = r.targetId; },
    (r: any) => { r.tensorId = 'invented'; },
    (r: any) => { r.source.line = 0; },
  ]) {
    const invalid = structuredClone(a); change(invalid.sourceRelations![0]);
    assert.throws(() => validateArchitecture(invalid), /sourceRelation/);
  }
  const duplicate = structuredClone(a); duplicate.sourceRelations!.push(duplicate.sourceRelations![0]);
  assert.throws(() => validateArchitecture(duplicate), /duplicate identity/);
  const oversized = structuredClone(a);
  oversized.sourceRelations = Array.from({ length: 1441 }, (_, i) => ({ ...a.sourceRelations![0], id: `relation-${i}` }));
  assert.throws(() => validateArchitecture(oversized), /1440 relation budget/);
});

test('editor derives source arrows from actual moved geometry and persists facts through source presentation edits', async () => {
  const a = await architecture(), view = createDocument(a), editing = projectSourceEditing(view);
  const imported = await backend('print(json.dumps(import_editable_source_draft(*v)))', [view, buildScene(view), editing.document, editing.scene]) as ImportedSourceDraft;
  const before = imported.draft, catalog = sourceDraftCatalog(before, { schemaVersion: 1, mode: 'authored-draft', modules: [], unsupported: [] })!;
  const initial = draftSourceRelations(before, catalog);
  const tensorRoutes = draftRoutes(before, catalog);
  assert.equal(tensorRoutes.routes.length, before.edges.length, 'expanded opaque boundary retains its tensor routes');
  assert.ok(tensorRoutes.routes.every(route => !route.blockedBy.length));
  assert.equal(initial.relations.length, 4);
  const after = structuredClone(before), head = after.nodes.find(n => n.label === 'head')!;
  moveDraftNodes(after, [head.id], 36, 12); head.label = 'Edited head';
  const moved = draftSourceRelations(after, catalog), canonical = after.sourceProvenance!.nodeRefs[head.id].nodeId;
  assert.notDeepEqual(moved.relations.find(r => r.targetId === canonical)!.path, initial.relations.find(r => r.targetId === canonical)!.path);
  assert.deepEqual(draftSourceRelations(JSON.parse(JSON.stringify(after)), catalog).relations, moved.relations);
  assert.equal(sameSourceSemantics(before, after), true);
  const updated = applyVisualBatch(view, sourcePresentationOperations(view, before, after));
  assert.deepEqual(updated.architecture, a);
  assert.deepEqual(before.edges, after.edges);
  assert.deepEqual(after.sourceProvenance!.architecture.sourceRelations, a.sourceRelations);
});
