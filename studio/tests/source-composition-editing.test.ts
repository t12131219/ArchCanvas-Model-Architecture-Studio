import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { buildScene, createDocument, applyVisualBatch } from '../src/core/index.ts';
import type { Architecture, CanvasDocument } from '../src/core/types.ts';
import { projectSourceEditing } from '../src/sourceEditingProjection.ts';
import { createGeneratedCanvas } from '../src/generatedCanvas.ts';
import { generatedSourceView, resumeGeneratedWorkspace, readGeneratedWorkspace, writeGeneratedWorkspace } from '../src/generatedWorkspace.ts';
import type { GeneratedWorkspaceBinding } from '../src/generatedWorkspace.ts';
import { changeDraft, draftHistory, travelDraft, moveDraftNodes } from '../src/authoring.ts';
import type { AuthoredDraft } from '../src/authoring.ts';
import type { ImportedSourceDraft, GeneratedDraft } from '../src/api.ts';
import { resumeSourceAuthoring } from '../src/sourceAuthoringSession.ts';

const project = fileURLToPath(new URL('../../', import.meta.url));
function backend(expression: string, value?: unknown): Promise<any> {
  return new Promise((resolve, reject) => {
    const child = execFile(`${project}.venv/bin/python`, ['-I', '-S', '-B', '-c',
      `import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from pathlib import Path;from archcanvas_python import analyze_project,analyze_source;from archcanvas_authoring import generate_model,validate_draft,rebase_source_frontier;from archcanvas_authoring.source_import import import_editable_source_draft,import_source_draft,_retain_view_frontier;v=json.load(sys.stdin);${expression}`, project],
      { maxBuffer: 20_000_000 }, (error, stdout) => {
        if (error) reject(error); else try { resolve(JSON.parse(stdout)); } catch (error) { reject(error); }
      });
    child.stdin!.end(JSON.stringify(value ?? null));
  });
}
const fixture = async (name: string, entry: string) => createDocument(await backend('print(json.dumps(analyze_project(Path(sys.argv[1])/"fixtures"/v[0],v[1])))', [name, entry]) as Architecture);
const importEditing = (view: CanvasDocument) => {
  const editing = projectSourceEditing(view);
  return backend('print(json.dumps(import_editable_source_draft(*v)))', [view, buildScene(view), editing.document, editing.scene]) as Promise<ImportedSourceDraft>;
};

test('unresolved regions expose both authored paths and nested source definitions in view and editor', async () => {
  const { validateArchitecture } = await import('../src/core/validate.ts');
  const { evidenceText } = await import('../src/core/nodeFacts.ts');
  const { sameSourceSemantics, sourcePresentationOperations } = await import('../src/sourcePresentation.ts');
  const { renderSvg } = await import('../src/core/svg.ts');
  const architecture = await backend('print(json.dumps(analyze_source(v,"model:Wisteria")))', `from torch import nn
class Rootlet(nn.Module):
 def __init__(self):
  super().__init__(); self.linear=nn.Linear(4,4)
 def forward(self,x): return self.linear(x)
class Wisteria(nn.Module):
 def __init__(self, config):
  super().__init__(); self.flag=config.alternative
  if self.flag: self.left=Rootlet()
  else: self.right=Rootlet()
 def forward(self,x):
  if self.flag: x=self.left(x)
  else: x=self.right(x)
  return x
`) as Architecture;
  validateArchitecture(architecture);
  const view = createDocument(architecture), region = architecture.nodes.find(n => n.kind === 'ConditionalRegion')!;
  const facts = new Map(architecture.nodes.map(n => [n.id, n]));
  assert.deepEqual(region.children.map(id => facts.get(id)!.label), ['if self.flag', 'else']);
  assert.ok(buildScene(view).nodes.find(n => n.id === region.id)!.expandable);
  assert.match(evidenceText(region), /展开/);
  const editing = projectSourceEditing(view);
  assert.ok(editing.scene.nodes.some(n => n.label === 'left' && n.expanded));
  assert.ok(editing.scene.nodes.some(n => n.label === 'right' && n.expanded));
  assert.ok(editing.scene.nodes.filter(n => n.label === 'linear').length === 2);
  assert.deepEqual(editing.scene.diagnostics.filter(d => ['layout-overlap', 'layout-outside-parent', 'layout-header-overlap'].includes(d.code ?? '')), []);
  const sourceNode = architecture.nodes.find(n => n.sourceStructure && n.parameters.sourceType === 'nn.Linear')!;
  assert.ok(editing.scene.nodes.find(n => n.id === sourceNode.id)!.subtitle.includes('path unresolved'));
  const before = (await importEditing(view)).draft;
  assert.equal((await backend('print(json.dumps(validate_draft(v)))', before)).complete, true);
  const after = structuredClone(before), draftNode = after.nodes.find(n => after.sourceProvenance!.nodeRefs[n.id].nodeId === sourceNode.id)!;
  draftNode.label = 'Inspected projection'; draftNode.position.x += 21;
  assert.equal(sameSourceSemantics(before, after), true);
  const updated = applyVisualBatch(view, sourcePresentationOperations(view, before, after));
  const expanded = applyVisualBatch(updated, architecture.nodes.filter(n => n.children.length).map(n => ({ type: 'expand', id: n.id, expanded: true })));
  const position = buildScene(expanded).nodes.find(n => n.id === sourceNode.id)!;
  const collapsed = applyVisualBatch(expanded, [{ type: 'expand', id: region.id, expanded: false }]);
  const reopened = applyVisualBatch(JSON.parse(JSON.stringify(collapsed)), [{ type: 'expand', id: region.id, expanded: true }]);
  const restored = buildScene(reopened).nodes.find(n => n.id === sourceNode.id)!;
  assert.equal(restored.label, 'Inspected projection'); assert.equal(restored.x, position.x); assert.equal(restored.y, position.y);
  assert.match(renderSvg(buildScene(reopened)), /Inspected projection/);
  assert.deepEqual(reopened.architecture, architecture);
  await assert.rejects(backend('print(json.dumps(generate_model(v)))', after), /Source inspection is expandable/);
  assert.deepEqual(after.sourceProvenance!.architecture.sources, architecture.sources);
  for (const field of ['ports', 'instanceId', 'callId', 'repeat', 'parameterOrigins']) {
    const invalid = structuredClone(architecture), inspection = invalid.nodes.find(n => n.id === sourceNode.id)!;
    Object.assign(inspection, { [field]: field === 'ports' ? [{ id: 'invented', name: 'output', direction: 'out', role: 'data', ordinal: 0 }] : {} });
    assert.throws(() => validateArchitecture(invalid), /sourceStructure|expected string/);
  }
});

test('all recovered source compositions recursively expose their real primitives, including unnamed nested modules and repeats', async () => {
  const custom = await backend('print(json.dumps(analyze_source(v,"model:Network")))', `from torch import nn
class Projection(nn.Module):
 def __init__(self):
  super().__init__(); self.fc=nn.Linear(4,4); self.act=nn.GELU()
 def forward(self,x): return self.act(self.fc(x))
class Network(nn.Module):
 def __init__(self):
  super().__init__(); self.body=Projection(); self.head=nn.Linear(4,2)
 def forward(self,x): return self.head(self.body(x))
`) as Architecture;
  for (const view of [await fixture('transformer', 'model:Transformer'), await fixture('residual_cnn', 'model:ResidualCNN'), createDocument(custom)]) {
    const bytes = JSON.stringify(view), { document, scene } = projectSourceEditing(view);
    const compound = view.architecture.nodes.filter(node => node.children.length && node.evidence !== 'opaque');
    assert.ok(compound.length);
    assert.ok(compound.every(node => document.expandedIds.includes(node.id)));
    assert.ok(compound.every(node => scene.nodes.some(visible => (visible.canonicalNodeId ?? visible.id) === node.id && visible.expanded)));
    assert.deepEqual(document.architecture, view.architecture);
    assert.equal(JSON.stringify(view), bytes, 'entering editing leaves the existing view untouched');
    assert.deepEqual(scene.diagnostics.filter(d => ['layout-overlap', 'layout-outside-parent', 'layout-header-overlap'].includes(d.code ?? '')), []);
    const imported = await backend('print(json.dumps(import_editable_source_draft(*v)))', [view, buildScene(view), document, scene]) as ImportedSourceDraft;
    const draft = imported.draft, source = draft.sourceProvenance!;
    assert.equal(draft.nodes.length, scene.nodes.length);
    assert.ok(draft.nodes.every(node => !compound.some(fact => fact.id === source.nodeRefs[node.id].nodeId) || node.presentation?.group));
    assert.deepEqual(draft.nodes.map(node => node.position), scene.nodes.map(node => ({ x: node.x, y: node.y })));
    assert.deepEqual(source.viewCanvas, view);
    assert.equal((await backend('print(json.dumps(validate_draft(v)))', draft)).complete, true);
    assert.deepEqual(new Set(Object.values(source.edgeRefs).flat()), new Set(scene.edges.flatMap(edge => edge.canonicalEdgeIds)));
    for (const fact of view.architecture.nodes.filter(node => node.repeat)) {
      assert.ok(Object.values(source.nodeRefs).some(ref => ref.nodeId === fact.id && JSON.stringify(ref.repeat) === JSON.stringify(fact.repeat)));
    }
  }
});

test('decomposed Transformer edits generate a compact view and return with full structure, manual ports and undo intact', async () => {
  const view = await fixture('transformer', 'model:Transformer'), imported = await importEditing(view);
  const original = imported.draft, atom = original.nodes.find(node => original.sourceProvenance!.nodeRefs[node.id].kind === 'Linear')!;
  const edge = original.edges.find(edge => edge.source.nodeId === atom.id)!;
  const history = changeDraft(draftHistory(original), draft => {
    moveDraftNodes(draft, [atom.id], 24, 0);
    draft.nodes.find(node => node.id === atom.id)!.portLayouts = { [edge.source.portId]: { side: 'right', offset: .35 } };
    draft.title = 'Edited Transformer';
  });
  const generated = await backend('print(json.dumps(generate_model(v)))', history.draft) as GeneratedDraft;
  const retained = createGeneratedCanvas(generated.architecture, generated.draft, generated, history.draft);
  const scene = buildScene(retained.document);
  assert.equal(scene.nodes.length, buildScene(view).nodes.length);
  assert.deepEqual(retained.unmappedNodeIds, []);
  assert.ok(Object.values(retained.document.portLayoutOverrides ?? {}).some(layout => layout?.offset === .35));
  const groups = original.sourceProvenance!.viewGraph!.nodes.filter(node => !node.presentation!.group && original.sourceProvenance!.architecture.nodes.find(fact => fact.id === original.sourceProvenance!.nodeRefs[node.id].nodeId)!.children.length);
  assert.ok(groups.length >= 2);
  for (const group of groups) assert.ok(!retained.document.expandedIds.includes(({ ...generated.nodeBindings, ...generated.containerBindings })[group.id]));
  const binding: GeneratedWorkspaceBinding = { workspaceKey: 'source', documentId: retained.document.id,
    sourceDigest: retained.document.sourceBindingDigest, irDigest: retained.document.architecture.irDigest,
    draft: history.draft, nodeBindings: { ...generated.nodeBindings, ...generated.containerBindings }, edgeBindings: generated.edgeBindings, visualRevision: retained.document.revision };
  const workspace = { draft: history.draft, history, storageRevision: 0, savedRevision: -1, camera: { x: 101, y: -44, zoom: .23 }, viewport: { width: 900, height: 700 } };
  const sourceGroup = groups[0], canonical = binding.nodeBindings[sourceGroup.id];
  const revised = applyVisualBatch(retained.document, [{ type: 'move', ids: [canonical], dx: 32, dy: 16 }, { type: 'alias', id: canonical, label: 'renamed source group' }]);
  const translated = generatedSourceView(workspace, revised, binding)!;
  const compact = original.sourceProvenance!.viewGraph!.nodes.find(node => node.id === sourceGroup.id)!;
  assert.ok(!translated.expandedIds.includes(original.sourceProvenance!.nodeRefs[sourceGroup.id].nodeId));
  const cameraView = { selection: [canonical], camera: { x: 8, y: 8, zoom: .8 }, viewport: { width: 900, height: 700 }, tool: 'select' as const, sourceHistory: { past: 1, future: 0 } };
  const rebased = await resumeSourceAuthoring(workspace, translated, cameraView, async (draft, document) => {
    const editing = projectSourceEditing(document, draft.sourceProvenance!.canvas, draft.sourceProvenance!.viewCanvas);
    return backend('r=rebase_source_frontier(v[0],v[1],v[2]);w=import_source_draft(v[3],v[4]);_retain_view_frontier(r["draft"],w["draft"]);print(json.dumps(r))',
      [draft, editing.document, editing.scene, document, buildScene(document)]) as Promise<ImportedSourceDraft>;
  });
  const resumed = resumeGeneratedWorkspace(rebased, revised, binding, cameraView);
  assert.equal(resumed.draft.nodes.length, original.nodes.length);
  const group = resumed.draft.nodes.find(node => node.id === sourceGroup.id)!;
  assert.equal(group.presentation!.group, true);
  assert.ok(group.presentation!.height > compact.presentation!.height);
  assert.equal(group.label, 'renamed source group');
  assert.deepEqual(resumed.camera, workspace.camera, 'editor camera is independent of compact view');
  const layouts = resumed.draft.nodes.find(node => node.id === atom.id)!.portLayouts!;
  assert.deepEqual(Object.values(layouts), [{ side: 'right', offset: .35 }]);
  assert.deepEqual(resumed.draft.sourceProvenance!.nodeRefs[atom.id].portBindings[Object.keys(layouts)[0]], original.sourceProvenance!.nodeRefs[atom.id].portBindings[edge.source.portId]);
  assert.ok(travelDraft(resumed.history!, 'undo').draft.nodes.some(node => node.id === atom.id));
  const cache = new Map<string, string>(), storage = { getItem: (key: string) => cache.get(key) ?? null, setItem: (key: string, value: string) => { cache.set(key, value); } };
  writeGeneratedWorkspace(storage, resumed, binding);
  assert.deepEqual(readGeneratedWorkspace(storage, revised)!.workspace.draft, resumed.draft);
});

test('editing and view frontiers cannot be paired across document revisions', async () => {
  const view = await fixture('mlp', 'model:MLP'), editing = projectSourceEditing(view);
  editing.document.revision++;
  editing.scene.revision++;
  await assert.rejects(backend('print(json.dumps(import_editable_source_draft(*v)))', [view, buildScene(view), editing.document, editing.scene]), /same source document revision/);
});

test('unseen opaque models accept edits on the same source canvas with save/reopen, undo and export', async () => {
  const { sameSourceSemantics, sourcePresentationOperations } = await import('../src/sourcePresentation.ts');
  const { createHistory, reduceHistory, validateDocument } = await import('../src/core/index.ts');
  const { renderSvg } = await import('../src/core/svg.ts');
  for (const name of ['OrchardSignal', 'CobaltMixer', 'UnlistedForecast']) {
    const architecture = await backend('print(json.dumps(analyze_source(v[0],v[1])))', [`from torch import nn
class ${name}(nn.Module):
 def __init__(self):
  super().__init__(); self.proj=nn.Linear(5,5)
 def forward(self,x,mask): return external_operation(self.proj(x),mask)
raise RuntimeError("must never execute")
`, `model:${name}`]) as Architecture;
    const view = createDocument(architecture), before = (await importEditing(view)).draft;
    const opaque = before.nodes.find(node => before.sourceProvenance!.nodeRefs[node.id].evidence === 'opaque')!;
    assert.ok(opaque);
    const after = structuredClone(before), target = after.nodes.find(node => node.id === opaque.id)!;
    after.title = 'Edited unknown model'; target.label = 'External operation'; target.position.x += 31; target.position.y += 17;
    target.visual = { ...target.presentation!, fill: '#d9e8f7', stroke: '#334455' };
    const portId = Object.keys(before.sourceProvenance!.nodeRefs[target.id].portBindings)[0];
    target.portLayouts = { [portId]: { side: 'bottom', offset: .37 } };
    assert.equal(sameSourceSemantics(before, after), true);
    const history = reduceHistory(createHistory(view), { type: 'apply', operations: sourcePresentationOperations(view, before, after) });
    assert.equal(history.past.length, 1); assert.equal(history.document.id, view.id);
    assert.deepEqual(history.document.architecture, architecture);
    const restored = JSON.parse(JSON.stringify(history.document)) as CanvasDocument;
    validateDocument(restored); assert.equal(restored.title, 'Edited unknown model');
    const node = buildScene(restored).nodes.find(node => node.id === before.sourceProvenance!.nodeRefs[target.id].nodeId)!;
    assert.equal(node.label, 'External operation'); assert.equal(node.fill, '#d9e8f7');
    assert.match(renderSvg(buildScene(restored)), /External operation/);
    const undone = reduceHistory(history, { type: 'undo' });
    assert.deepEqual(undone.document.layout, view.layout);
    assert.deepEqual(undone.document.displayAliases, view.displayAliases);
    assert.deepEqual(reduceHistory(undone, { type: 'redo' }).document.layout, history.document.layout);
    for (const mutate of [(draft: AuthoredDraft) => { draft.nodes[0].parameters.changed = 1; },
      (draft: AuthoredDraft) => { draft.edges.pop(); }, (draft: AuthoredDraft) => { draft.nodes.pop(); }]) {
      const semantic = structuredClone(after); mutate(semantic);
      assert.equal(sameSourceSemantics(before, semantic), false);
      assert.throws(() => sourcePresentationOperations(view, before, semantic));
    }
  }
});

test('source frontier collapse retains opaque visual changes and hidden local placement without regenerating Python', async () => {
  const { sourceFrontierDocument } = await import('../src/sourceDraftFrontier.ts');
  const { sameSourceSemantics, sourcePresentationOperations } = await import('../src/sourcePresentation.ts');
  const a = await backend('print(json.dumps(analyze_source(v,"model:Canopy")))', `from torch import nn
class Branch(nn.Module):
 def __init__(self):
  super().__init__(); self.proj=nn.Linear(5,5)
 def forward(self,x): return external_call(self.proj(x))
class Canopy(nn.Module):
 def __init__(self):
  super().__init__(); self.branch=Branch()
 def forward(self,x): return self.branch(x)
`) as Architecture;
  const view = createDocument(a), before = (await importEditing(view)).draft;
  const opaque = before.nodes.find(n => before.sourceProvenance!.nodeRefs[n.id].evidence === 'opaque')!;
  const group = before.nodes.find(n => before.sourceProvenance!.nodeRefs[n.id].nodeId.endsWith('.branch'))!;
  const edited = structuredClone(before); edited.nodes.find(n => n.id === opaque.id)!.position.x += 29;
  edited.nodes.find(n => n.id === opaque.id)!.label = 'Preserved opaque step';
  const collapsedView = sourceFrontierDocument(edited, group.id, false);
  const collapsed = await backend('print(json.dumps(rebase_source_frontier(v[0],v[1],v[2])))', [edited, collapsedView, buildScene(collapsedView)]) as ImportedSourceDraft;
  assert.equal(sameSourceSemantics(before, collapsed.draft), true);
  const document = applyVisualBatch(view, sourcePresentationOperations(view, before, collapsed.draft));
  assert.equal(document.id, view.id); assert.deepEqual(document.architecture, a);
  const canonical = before.sourceProvenance!.nodeRefs[opaque.id].nodeId;
  assert.equal(document.displayAliases[canonical], 'Preserved opaque step');
  assert.ok(document.layout[canonical], 'hidden position is stored on the original canvas');
  const expanded = applyVisualBatch(document, [{ type: 'expand', id: before.sourceProvenance!.nodeRefs[group.id].nodeId, expanded: true }]);
  assert.ok(buildScene(expanded).nodes.some(n => n.id === canonical && n.label === 'Preserved opaque step'));
});
