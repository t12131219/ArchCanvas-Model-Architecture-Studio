import { sameSourceSemantics } from '../src/sourcePresentation.ts';
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import ts from 'typescript';
import { createGeneratedCanvas } from '../src/generatedCanvas.ts';
import { applyVisualBatch, buildScene, createDocument, createHistory, renderSvg } from '../src/core/index.ts';
import type { Architecture, ArchitectureNode, CanvasDocument } from '../src/core/types.ts';
import { blankDraft, changeDraft, draftHistory, travelDraft } from '../src/authoring.ts';
import type { AuthoredDraft } from '../src/authoring.ts';
import type { GeneratedDraft, ImportedSourceDraft } from '../src/api.ts';
import { ApiError } from '../src/api.ts';
import { sourceAuthoringKey } from '../src/sourceAuthoringSession.ts';
import { generatedSourceView, resumeGeneratedWorkspace, readGeneratedWorkspace, writeGeneratedWorkspace, readPersistentGeneratedWorkspace, writePersistentGeneratedWorkspace } from '../src/generatedWorkspace.ts';
import type { GeneratedWorkspaceBinding } from '../src/generatedWorkspace.ts';
import { sameGeneratedDraft } from '../src/generatedWorkspace.ts';
import { architecturePreviewRequest, previewExpansionOperations, previewSelectionNodeIds, previewUniqueNodeBindings } from '../src/previewInterop.ts';

const project = fileURLToPath(new URL('../../', import.meta.url));
const run = promisify(execFile);

test('actual edit→view rejects an unconnected Attention before source expansion, preserving draft history and a responsive event loop', async () => {
  const architecture = await sourceBackend('print(json.dumps(analyze_project(Path(sys.argv[1])/"fixtures"/"transformer", "model:Transformer")))') as Architecture;
  const document = createDocument(architecture);
  const imported = await sourceBackend('print(json.dumps(import_source_draft(v[0],v[1])))', [document, buildScene(document)]) as ImportedSourceDraft;
  let history = changeDraft(draftHistory(imported.draft), draft => {
    draft.nodes.push({ id: 'attention', kind: 'MultiheadAttention', label: 'MultiheadAttention',
      parameters: { embed_dim: 16, num_heads: 4, dropout: .1, bias: true, batch_first: true }, position: { x: 99, y: 511 } });
  });
  history = travelDraft(changeDraft(history, draft => { draft.title = 'future title'; }), 'undo');
  const bytes = JSON.stringify(history), currentRef = { current: history }, browsing = { current: false };
  const errors: ApiError[] = [], busy: boolean[] = [], submissions: AuthoredDraft[] = [];
  let opened = 0, reprojected = 0, responsive = false;
  const browse = actualCallback('AuthoringStudio.tsx', 'AuthoringStudio', 'browse', {
    busy: false, browsing, invalidFieldsRef: { current: [] }, cancel: () => {}, clearError: () => {}, currentRef,
    storageRevision: 0, savedRevision: -1, selectedIds: ['attention'], camera: { x: 0, y: 0, zoom: 1 },
    cameraViewport: { current: { width: 1000, height: 700 } }, tool: 'select', initial: {},
    browseBaseline: imported.draft, onReuseView: () => { throw new Error('modified draft reused'); }, sameGeneratedDraft, sameSourceSemantics,
    setBusy: (value: boolean) => { busy.push(value); }, setBusyOperation: () => {},
    reprojectSourceDraft: () => { reprojected++; throw new Error('UI thread expanded source before validation'); },
    api: { generateDraft: async (draft: AuthoredDraft) => {
      submissions.push(draft);
      const response = await sourceBackend('from archcanvas_authoring import DraftError\ntry: print(json.dumps(generate_model(v)))\nexcept DraftError as e: print(json.dumps({"error": str(e), "diagnostics": e.diagnostics}))', draft) as { error: string; diagnostics: unknown };
      throw new ApiError(response.error, 422, response.diagnostics);
    } },
    viewStateRef: { current: () => { throw new Error('invalid model retained as generated'); } },
    onOpen: async () => { opened++; }, reportError: (error: ApiError) => { errors.push(error); },
  });
  setImmediate(() => { responsive = true; });
  const pending = browse();
  assert.deepEqual(submissions, [history.draft], 'the edited frontier is submitted immediately');
  await pending;
  assert.equal(reprojected, 0); assert.equal(opened, 0); assert.equal(responsive, true);
  assert.equal(JSON.stringify(currentRef.current), bytes); assert.equal(currentRef.current.future.length, 1);
  assert.deepEqual(busy, [true, false]); assert.equal(browsing.current, false);
  assert.deepEqual((errors[0].diagnostics as { portId: string }[]).map(item => item.portId), ['query', 'key', 'value']);
});

async function sourceBackend(expression: string, value?: unknown) {
  const args = ['-I', '-S', '-B', '-c',
    `import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from pathlib import Path;from archcanvas_python import analyze_project;from archcanvas_authoring import import_source_draft,rebase_source_frontier,generate_model;v=json.load(sys.stdin);${expression}`, project];
  return new Promise((resolve, reject) => {
    const child = execFile(`${project}.venv/bin/python`, args, { maxBuffer: 6_000_000 }, (error, stdout) => {
      if (error) reject(error); else try { resolve(JSON.parse(stdout)); } catch (error) { reject(error); }
    });
    child.stdin!.end(JSON.stringify(value ?? null));
  });
}
function actualCallback(file: string, componentName: string, callbackName: string, environment: Record<string, unknown>) {
  const text = readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8');
  const ast = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const component = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === componentName);
  assert.ok(component && ts.isFunctionDeclaration(component) && component.body);
  const callback = component.body.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === callbackName);
  assert.ok(callback);
  const js = ts.transpileModule(callback.getText(ast), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  return new Function(...Object.keys(environment), `${js};return ${callbackName}`)(...Object.values(environment)) as (...args: unknown[]) => Promise<void>;
}
function operation(id: string, parentId?: string): ArchitectureNode {
  return { id, label: id, kind: 'ReLU', category: 'activation', parentId, children: [], parameters: {}, evidence: 'contract',
    ports: [{ id: 'input', name: 'input', direction: 'in', role: 'data', ordinal: 0 }, { id: 'output', name: 'output', direction: 'out', role: 'data', ordinal: 0 }] };
}
function grouped(): Architecture {
  const root = { ...operation('root'), kind: 'Model', category: 'module', children: ['block'] };
  const block = { ...operation('block', 'root'), kind: 'Block', category: 'module', children: ['a', 'b'] };
  return { schemaVersion: 1, id: 'new-architecture', label: 'New model', sourceDigest: 'new-source', irDigest: 'new-ir', entry: 'generated:Model', sources: [], diagnostics: [],
    nodes: [root, block, operation('a', 'block'), operation('b', 'block')], edges: [{ id: 'binding', source: { nodeId: 'a', portId: 'output' }, target: { nodeId: 'b', portId: 'input' }, tensorId: 'data', role: 'data' }] };
}

test('generated source view retains absolute draft anchors through real nested containers and faithful SVG export', () => {
  const architecture = grouped(), draft = blankDraft('draft-retained');
  draft.nodes = [{ id: 'first', kind: 'ReLU', label: '第一层', parameters: {}, position: { x: -920, y: -510 } },
    { id: 'second', kind: 'ReLU', label: '第二层', parameters: {}, position: { x: -470, y: 120 } }];
  const before = JSON.stringify({ architecture, draft });
  const result = createGeneratedCanvas(architecture, draft, { nodeBindings: { first: 'a', second: 'b' } });
  const scene = buildScene(result.document);
  for (const [id, position] of [['a', draft.nodes[0].position], ['b', draft.nodes[1].position]] as const) {
    const actual = scene.nodes.find(node => node.id === id)!;
    assert.deepEqual({ x: actual.x, y: actual.y }, position);
  }
  for (const container of scene.nodes.filter(node => node.expanded)) for (const child of scene.nodes.filter(node => node.parentId === container.id)) {
    assert.ok(child.x >= container.x && child.y >= container.y + container.headerHeight);
    assert.ok(child.x + child.width <= container.x + container.width && child.y + child.height <= container.y + container.height);
  }
  assert.deepEqual(result.unmappedNodeIds, []);
  assert.equal(JSON.stringify({ architecture, draft }), before);
  assert.equal(scene.irDigest, architecture.irDigest);
  assert.equal(scene.sourceDigest, architecture.sourceDigest);
  assert.match(renderSvg(scene), /第一层/);
  assert.match(renderSvg(scene), /<rect x="-920" y="-510" width=/);
});

test('source presentation, pin, annotations and edge style follow exact generated identities without changing source facts', () => {
  const architecture = grouped(), sourceCanvas = createDocument(architecture);
  sourceCanvas.expandedIds = ['root', 'block'];
  sourceCanvas.annotations.push({ id: 'note', text: '保留说明', x: -810, y: 380, width: 240 });
  sourceCanvas.pageSpec.widthMm = 85;
  sourceCanvas.nodeStyleOverrides.a = { fill: '#ffffff', stroke: '#8899aa', glyph: 'tensor' };
  sourceCanvas.pinnedObjects = ['a'];
  sourceCanvas.edgeStyleOverrides.binding = { stroke: '#ee3399', width: 3, dashed: true };
  const draft: AuthoredDraft = { ...blankDraft('draft-source'), nodes: [{ id: 'source-a', kind: 'Source_A', label: '我的部件', parameters: {}, position: { x: -500, y: 210 },
    presentation: { width: 240, height: 130, fill: '#dcebf6', stroke: '#223344', group: false, ports: {} } },
    { id: 'source-b', kind: 'Source_B', label: '下一层', parameters: {}, position: { x: -40, y: 520 } }],
    edges: [{ id: 'source-edge', source: { nodeId: 'source-a', portId: 'output' }, target: { nodeId: 'source-b', portId: 'input' } }],
    sourceProvenance: { schemaVersion: 1, digest: 'provenance', documentId: sourceCanvas.id, visualRevision: 0, sourceDigest: architecture.sourceDigest, irDigest: architecture.irDigest,
      architecture, canvas: sourceCanvas, modules: [], nodeRefs: {
        'source-a': { nodeId: 'a', sceneNodeId: 'a', kind: 'ReLU', category: 'activation', evidence: 'contract', originalParameters: {}, group: false, portBindings: {} },
        'source-b': { nodeId: 'b', sceneNodeId: 'b', kind: 'ReLU', category: 'activation', evidence: 'contract', originalParameters: {}, group: false, portBindings: {} } },
      edgeRefs: { 'source-edge': ['binding'] }, originalGraph: { nodes: [], edges: [] } } };
  const before = JSON.stringify(draft);
  const { document } = createGeneratedCanvas(architecture, draft, { nodeBindings: { 'source-a': 'a', 'source-b': 'b' }, edgeBindings: { 'source-edge': ['binding'] } });
  const scene = buildScene(document), a = scene.nodes.find(node => node.id === 'a')!;
  assert.deepEqual({ x: a.x, y: a.y, width: a.width, height: a.height, fill: a.fill, stroke: a.stroke, glyph: a.glyph },
    { x: -500, y: 210, width: 240, height: 130, fill: '#dcebf6', stroke: '#223344', glyph: 'tensor' });
  assert.deepEqual(document.pinnedObjects, ['a']);
  assert.deepEqual(document.annotations, sourceCanvas.annotations);
  assert.equal(document.pageSpec.widthMm, 85);
  assert.deepEqual(document.edgeStyleOverrides.binding, sourceCanvas.edgeStyleOverrides.binding);
  assert.equal(JSON.stringify(draft), before);
});

test('ambiguous mappings are refused and unmapped presentation objects are explicitly reported', () => {
  const architecture = grouped(), draft = blankDraft('draft-ambiguous');
  draft.nodes = [{ id: 'one', kind: 'ReLU', label: 'a', parameters: {}, position: { x: 0, y: 0 } },
    { id: 'two', kind: 'ReLU', label: 'b', parameters: {}, position: { x: 500, y: 500 } }];
  assert.throws(() => createGeneratedCanvas(architecture, draft, { nodeBindings: { one: 'a', two: 'a' } }), /映射/);
  assert.throws(() => createGeneratedCanvas(architecture, draft, { nodeBindings: { one: 'absent' } }), /映射/);
  assert.throws(() => createGeneratedCanvas(architecture, draft, { nodeBindings: { absent: 'a' } }), /映射/);
  assert.deepEqual(createGeneratedCanvas(architecture, draft, { nodeBindings: { one: 'a' } }).unmappedNodeIds, ['two']);
});

test('a real backend generated model reopens with edited draft positions and labels while retaining its complete binding facts', async () => {
  const draft = blankDraft('draft-roundtrip'), parameters: Array<Record<string, import('../src/authoring.ts').DraftValue>> = [{ shape: [1, 16], dtype: 'float32' }, { in_features: 16, out_features: 4, bias: true }, {}];
  draft.nodes = ['Input', 'Linear', 'Output'].map((kind, i) => ({ id: `n_${i}`, kind, label: `我的 ${kind}`, parameters: parameters[i], position: { x: -880 + 400 * i, y: -470 + 120 * i } }));
  draft.edges = [0, 1].map(i => ({ id: `e_${i}`, source: { nodeId: `n_${i}`, portId: 'output' }, target: { nodeId: `n_${i + 1}`, portId: 'input' } }));
  const response = await run(`${project}.venv/bin/python`, ['-I', '-S', '-B', '-c',
    'import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_authoring import generate_model;print(json.dumps(generate_model(json.loads(sys.argv[2]))))', project, JSON.stringify(draft)]);
  const generated = JSON.parse(response.stdout), { document } = createGeneratedCanvas(generated.architecture, draft, generated);
  const scene = buildScene(document);
  assert.equal(generated.verification.status, 'passed');
  assert.deepEqual(document.architecture, generated.architecture);
  for (const node of draft.nodes) {
    const actual = scene.nodes.find(item => item.id === generated.nodeBindings[node.id])!;
    assert.deepEqual({ x: actual.x, y: actual.y, label: actual.label }, { ...node.position, label: node.label });
  }
  assert.deepEqual(new Set(scene.edges.flatMap(edge => edge.canonicalEdgeIds)), new Set(generated.architecture.edges.filter((edge: { id: string }) => !scene.hiddenEdges.includes(edge.id)).map((edge: { id: string }) => edge.id)));
});

test('new source operations reveal every return occurrence and reflow their truthful hierarchy while retaining the source draft', async () => {
  const architecture = await sourceBackend('from archcanvas_python import analyze_source;print(json.dumps(analyze_source(v,"model:Cedar")))', `from torch import nn
class Cedar(nn.Module):
 def __init__(self):
  super().__init__()
  self.head=nn.Linear(4,4)
 def forward(self,x,flag):
  if flag:
   return self.head(x)
  else:
   return x
`) as Architecture;
  const original = createDocument(architecture), originalScene = buildScene(original);
  original.annotations.push({ id: 'source-note', text: '保留原说明', x: 20, y: -90, width: 200 });
  original.pageSpec.widthMm = 85;
  const imported = await sourceBackend('print(json.dumps(import_source_draft(v[0],v[1])))', [original, originalScene]) as ImportedSourceDraft;
  const draft = imported.draft, refs = draft.sourceProvenance!.nodeRefs;
  const boundary = draft.nodes.find(node => refs[node.id].kind === 'ConditionalRegion')!;
  assert.equal(boundary.presentation!.group, false, 'the real source overview keeps the unresolved branch folded');
  boundary.label = '用户条件区域';
  boundary.visual = { width: 260, height: 110, fill: '#f5eedd', stroke: '#556677' };
  const definition = (await sourceBackend('from archcanvas_authoring import preview_custom_module;print(json.dumps(preview_custom_module(v)))', {
    source: 'from torch import nn\nclass PersonalPass(nn.Module):\n def forward(self,features): return features\n',
    entry: 'PersonalPass', label: '用户模块', constructorValues: {},
  }) as { definition: NonNullable<AuthoredDraft['customModules']>[number] }).definition;
  draft.customModules = [definition];
  const output = draft.nodes.find(node => refs[node.id].kind === 'Output')!;
  const edge = draft.edges.find(edge => edge.target.nodeId === output.id)!;
  const upstream = structuredClone(edge.source);
  draft.nodes.push({ id: 'inserted-identity', kind: 'Identity', label: '新基础模块', parameters: {}, position: { x: 12000, y: -8000 },
    visual: { width: 220, height: 100, fill: '#ccddee', stroke: '#334455' } },
    { id: 'inserted-custom', kind: definition.kind, label: '新源码模块', parameters: {}, position: { x: -6000, y: 9000 },
      visual: { width: 220, height: 100, fill: '#ddeeff', stroke: '#223344' } });
  draft.edges.push({ id: 'into-identity', source: upstream, target: { nodeId: 'inserted-identity', portId: 'input' } },
    { id: 'into-custom', source: { nodeId: 'inserted-identity', portId: 'output' }, target: { nodeId: 'inserted-custom', portId: definition.inputs[0].id } });
  edge.source = { nodeId: 'inserted-custom', portId: definition.outputs[0].id };
  const draftBytes = JSON.stringify(draft), originalBytes = JSON.stringify(original);
  const generated = await sourceBackend('print(json.dumps(generate_model(v)))', draft) as GeneratedDraft;
  const generationBytes = JSON.stringify(generated);
  const retained = createGeneratedCanvas(generated.architecture, generated.draft, generated, draft), scene = buildScene(retained.document);
  assert.equal(retained.hierarchyReflowed, true);
  assert.deepEqual(retained.unmappedNodeIds, []);
  assert.deepEqual(retained.document.architecture, generated.architecture);
  assert.equal(retained.document.pageSpec.widthMm, 85);
  assert.deepEqual(retained.document.annotations, original.annotations);
  const occurrences = generated.verification.operationOccurrences as { nodeId: string; canonicalIds: string[]; binding: string }[];
  assert.equal(occurrences.length, 2);
  for (const occurrence of occurrences) {
    assert.equal(occurrence.binding, 'source-inspection');
    assert.equal(occurrence.canonicalIds.length, 2, 'each edited module is present in both source return paths');
    const authored = draft.nodes.find(node => node.id === occurrence.nodeId)!;
    for (const id of occurrence.canonicalIds) {
      const node = scene.nodes.find(node => node.id === id)!;
      assert.ok(node, 'every independently recovered return occurrence is visible');
      assert.equal(node.label, authored.label);
      assert.equal(node.fill, authored.visual!.fill);
      assert.equal(node.stroke, authored.visual!.stroke);
      assert.deepEqual(generated.architecture.nodes.find(node => node.id === id)!.ports, [], 'source occurrences acquire no tensor ports');
      assert.equal(retained.document.architecture.nodes.find(node => node.id === id)!.sourceStructure, true);
    }
  }
  const visibleBoundary = scene.nodes.find(node => node.id === retained.nodeBindings[boundary.id])!;
  assert.equal(visibleBoundary.expanded, true);
  assert.equal(visibleBoundary.label, '用户条件区域');
  assert.equal(visibleBoundary.fill, boundary.visual.fill);
  assert.deepEqual(scene.diagnostics.filter(item => ['layout-overlap', 'layout-header-overlap', 'layout-outside-parent'].includes(item.code ?? '')), []);
  for (const parent of scene.nodes.filter(node => node.expanded)) for (const child of scene.nodes.filter(node => node.parentId === parent.id)) {
    assert.ok(child.x >= parent.x && child.y >= parent.y + parent.headerHeight);
    assert.ok(child.x + child.width <= parent.x + parent.width && child.y + child.height <= parent.y + parent.height);
  }
  assert.equal(JSON.stringify(draft), draftBytes);
  assert.equal(JSON.stringify(original), originalBytes);
  assert.equal(JSON.stringify(generated), generationBytes);
  const reopened = JSON.parse(JSON.stringify(retained.document)) as CanvasDocument;
  assert.deepEqual(buildScene(reopened).nodes.map(node => [node.id, node.x, node.y]), scene.nodes.map(node => [node.id, node.x, node.y]));
  const stored = new Map<string, string>(), storage = { getItem: (key: string) => stored.get(key) ?? null, setItem: (key: string, value: string) => { stored.set(key, value); } };
  writeGeneratedWorkspace(storage, { draft, history: draftHistory(draft), storageRevision: 0, savedRevision: -1 }, {
    workspaceKey: 'cedar-source-edits', documentId: reopened.id, sourceDigest: reopened.sourceBindingDigest, irDigest: reopened.architecture.irDigest,
    visualRevision: reopened.revision, draft, nodeBindings: retained.nodeBindings, edgeBindings: generated.edgeBindings,
  });
  assert.equal(JSON.stringify(readGeneratedWorkspace(storage, reopened)!.workspace.draft), draftBytes, 'the old layout and complete editable source draft remain recoverable');

  const restored = readGeneratedWorkspace(storage, reopened)!;
  const editedId = occurrences[0].canonicalIds[0];
  const viewedAgain = applyVisualBatch(reopened, [{ type: 'alias', id: editedId, label: '生成视图中的名称' },
    { type: 'nodeStyle', id: editedId, style: { fill: '#d1e2f3', stroke: '#123456' } }]);
  assert.equal(generatedSourceView(restored.workspace, viewedAgain, restored.binding), null,
    'new source occurrence ancestors cannot replace the original edited frontier on reload');
  const resumed = resumeGeneratedWorkspace(restored.workspace, viewedAgain, restored.binding, {
    selection: [editedId], camera: { x: 0, y: 0, zoom: 1 }, tool: 'select', sourceHistory: { past: 2, future: 0 },
  });
  assert.deepEqual(resumed.draft.edges, draft.edges, 'all materialized surgery edges remain live');
  assert.deepEqual(resumed.draft.sourceCache, draft.sourceCache, 'presentation changes cannot create hidden structural edits');
  assert.deepEqual(resumed.draft.sourceProvenance, draft.sourceProvenance, 'source anchors and the original editing frontier stay fixed');
  assert.deepEqual(resumed.draft.nodes.map(node => [node.id, node.position]), draft.nodes.map(node => [node.id, node.position]),
    'generated hierarchy reflow cannot turn old editing anchors into new parent coordinates');
  const resumedEdited = resumed.draft.nodes.find(node => node.id === occurrences[0].nodeId)!;
  assert.equal(resumedEdited.label, '生成视图中的名称');
  assert.equal(resumedEdited.visual!.fill, '#d1e2f3');
  const generationCheck = await sourceBackend('from archcanvas_authoring import validate_draft;print(json.dumps(validate_draft(v)))', resumed.draft) as { generation: { supported: boolean; limitations: string[] } };
  assert.equal(generationCheck.generation.supported, true, generationCheck.generation.limitations.join('; '));
  const regenerated = await sourceBackend('print(json.dumps(generate_model(v)))', resumed.draft) as GeneratedDraft;
  assert.deepEqual(regenerated.architecture.sources, generated.architecture.sources, 'saving and resuming the edited graph can regenerate the same source');
  assert.equal(JSON.stringify(draft), draftBytes);

  // Exercise the actual second parser and recursive preview rather than
  // accepting the formal tree as evidence that the iframe can display edits.
  const bundle = await sourceBackend(`import tempfile
from archcanvas_preview import analyze
from archcanvas_adapters.registry import AdapterRegistry
with tempfile.TemporaryDirectory(prefix="archcanvas-generated-preview-") as registry:
 print(json.dumps(AdapterRegistry(Path(registry)).preview(analyze(v["files"],v["entry"],v["config"]),v["files"])))`,
    architecturePreviewRequest(generated.architecture)) as any;
  const bundleBytes = JSON.stringify(bundle), context = vm.createContext({ TextEncoder, TextDecoder });
  for (const file of ['router.js', 'physical-ports.js', 'junction-markers.js', 'route-labels.js',
    'source-contracts.js', 'semantic-constraints.js', 'graph-engine.js', 'recursive-graph.js', 'source-adapter.js']) {
    vm.runInContext(readFileSync(new URL(`../public/preview/yworks_edge_router_lab/${file}`, import.meta.url), 'utf8'), context, { filename: file });
  }
  const F = context.SummaryRecursive, E = context.SummaryEngine, S = context.SummarySourceAdapter;
  let preview = F.build(F.create(S.sources(bundle)));
  const detail = preview.recursive.authority.detail, authorityBytes = JSON.stringify(preview.recursive.authority);
  const occurrenceIds = new Set(occurrences.flatMap(item => item.canonicalIds));
  const previewOccurrences = detail.nodes.filter((node: any) => node.semantic?.sourceKind === 'SourceModule' &&
    previewSelectionNodeIds(generated.architecture, { nodeId: node.id, node }, bundle).some(id => occurrenceIds.has(id)));
  assert.equal(previewOccurrences.length, 4, 'both edited modules have independent preview cards in both return paths');
  const opaqueBoundary = detail.nodes.find((node: any) => node.semantic?.kind === 'opaque' &&
    previewSelectionNodeIds(generated.architecture, { nodeId: node.id, node }, bundle).includes(retained.nodeBindings[boundary.id]));
  assert.ok(opaqueBoundary);
  assert.equal(previewUniqueNodeBindings(generated.architecture, detail, bundle).has(opaqueBoundary.id), false,
    'a shared opaque/inspection binding cannot carry unique geometry');
  const replay = previewExpansionOperations(retained.document, detail, bundle);
  for (const operation of replay) preview = F.toggle(preview, operation.id, operation.expanded) ?? preview;
  for (const node of previewOccurrences) {
    assert.ok(preview.nodes.some((visible: any) => visible.id === node.id), `generated source occurrence is visible after expansion replay: ${node.id}`);
    assert.equal(node.semantic.sourceStructure, true);
    assert.equal(node.semantic.generationContract, null);
  }
  assert.equal(F.route(preview).failed, 0);
  const previewValidation = E.validateView(preview);
  assert.equal(previewValidation.source.ok, true, previewValidation.source.violations.join('; '));
  assert.equal(previewValidation.layout.ok, true, previewValidation.layout.violations.join('; '));
  assert.equal(JSON.stringify(preview.recursive.authority), authorityBytes, 'expansion replay cannot change preview source facts');
  assert.equal(JSON.stringify(bundle), bundleBytes, 'source adapters stay empty and the preview corpus remains immutable');
  for (const corrupt of [
    (items: typeof occurrences) => { items[0].canonicalIds.push('missing-source-occurrence'); },
    (items: typeof occurrences) => { items[0].canonicalIds.push(items[0].canonicalIds[0]); },
    (items: typeof occurrences) => { items[0].binding = 'operation'; },
  ]) {
    const broken = structuredClone(generated);
    corrupt(broken.verification.operationOccurrences as typeof occurrences);
    assert.throws(() => createGeneratedCanvas(broken.architecture, broken.draft, broken, draft), /源码出现位置/);
  }
});

test('actual generate callback keeps the collapsed Transformer frontier and anchors when complete source generation is reopened', async () => {
  const architecture = await sourceBackend('print(json.dumps(analyze_project(Path(sys.argv[1])/"fixtures"/"transformer", "model:Transformer")))') as Architecture;
  const sourceDocument = createDocument(architecture), sourceScene = buildScene(sourceDocument);
  assert.equal(sourceScene.nodes.length, 12, 'the real initial Transformer frontend is the source overview');
  assert.equal(sourceScene.diagnostics.filter(item => item.code === 'layout-overlap').length, 0);
  const imported = await sourceBackend('print(json.dumps(import_source_draft(v[0],v[1])))', [sourceDocument, sourceScene]) as ImportedSourceDraft;
  const snapshot = imported.draft;
  const memoryMask = snapshot.nodes.find(node => snapshot.sourceProvenance!.nodeRefs[node.id].nodeId === 'input:model.Transformer:memory_mask')!;
  // Same small move seen in the browser: preserve the exact editable card.
  memoryMask.position.y -= 4;
  const maskPort = Object.keys(memoryMask.presentation!.ports)[0];
  memoryMask.portLayouts = { [maskPort]: { side: 'top', offset: .25 } };
  const tokens = snapshot.nodes.find(node => node.label === 'source_tokens')!;
  const tokensPort = Object.keys(tokens.presentation!.ports)[0];
  tokens.portLayouts = { [tokensPort]: null };
  let generated: GeneratedDraft | undefined;
  const currentRef = { current: draftHistory(snapshot) };
  // Generation must never route a sequence of fully expanded source scenes
  // on the UI thread; canonical materialization belongs to the server.
  const reproject = async () => { throw new Error('generation attempted synchronous source expansion'); };
  const callback = actualCallback('AuthoringStudio.tsx', 'AuthoringStudio', 'generate', {
    busy: false, invalidFieldsRef: { current: [] }, cancel: () => {}, setBusy: () => {}, setBusyOperation: () => {}, clearError: () => {}, currentRef,
    reprojectSourceDraft: reproject, api: { generateDraft: (draft: AuthoredDraft) => sourceBackend('print(json.dumps(generate_model(v)))', draft) },
    setGenerated: (value: GeneratedDraft) => { generated = value; }, reportError: (reason: unknown) => { throw reason; },
  });
  const originalBytes = JSON.stringify(snapshot);
  await callback();
  assert.ok(generated && generated.presentationDraft);
  assert.equal(generated.presentationDraft, snapshot, 'the actual callback retains the editing snapshot');
  assert.deepEqual(generated.draft, snapshot, 'the response binds to the edited frontier after verifying hidden facts');
  assert.equal(generated.architecture.nodes.length, 49, 'static generation still verifies the full source graph');
  assert.deepEqual(Object.keys(generated.edgeBindings ?? {}).sort(), snapshot.edges.map(edge => edge.id).sort());
  const result = createGeneratedCanvas(generated.architecture, generated.draft, generated, generated.presentationDraft), scene = buildScene(result.document);
  assert.equal(scene.nodes.length, 12, 'opening generation must not expand hidden encoder/decoder modules');
  assert.deepEqual(result.unmappedNodeIds, []);
  assert.deepEqual(new Set(result.document.expandedIds), new Set([result.nodeBindings[snapshot.nodes.find(node => node.presentation?.group)!.id]]));
  const rootDraft = snapshot.nodes.find(node => node.presentation?.group)!, root = scene.nodes.find(node => node.id === result.nodeBindings[rootDraft.id])!;
  assert.equal(root.parentId, undefined, 'the imported root maps to the truthful AuthoredModel root');
  for (const node of snapshot.nodes) {
    const actual = scene.nodes.find(item => item.id === result.nodeBindings[node.id])!;
    assert.deepEqual({ x: actual.x, y: actual.y, label: actual.label }, { ...node.position, label: node.label });
    assert.equal(actual.expanded, !!node.presentation?.group);
    if (node.id !== rootDraft.id) assert.equal(actual.parentId, root.id, 'source overview siblings retain their actual parent boundary');
  }
  assert.deepEqual(scene.diagnostics.filter(item => ['layout-overlap', 'layout-header-overlap', 'layout-outside-parent'].includes(item.code ?? '')), [], 'generated overview introduces no frame/input sibling overlap');
  assert.equal(JSON.stringify(snapshot), originalBytes);
  assert.deepEqual(result.document.architecture, generated.architecture, 'presentation projection cannot rewrite generation IR');
  assert.match(renderSvg(scene), /memory_mask/);
  const mask = scene.nodes.find(node => node.id === result.nodeBindings[memoryMask.id])!;
  assert.equal(mask.ports.find(port => port.manual)!.y, mask.y, 'manual top-side port survives canonical generation');
  assert.ok(Object.values(result.document.portLayoutOverrides ?? {}).some(layout => layout === null), 'automatic port reset survives generation');
  const stored = new Map<string, string>(), storage = { getItem: (key: string) => stored.get(key) ?? null, setItem: (key: string, value: string) => { stored.set(key, value); } };
  const cacheBinding: GeneratedWorkspaceBinding = { workspaceKey: 'transformer-session', documentId: result.document.id,
    sourceDigest: result.document.sourceBindingDigest, irDigest: result.document.architecture.irDigest,
    visualRevision: result.document.revision, draft: snapshot, nodeBindings: result.nodeBindings, edgeBindings: generated.edgeBindings };
  writeGeneratedWorkspace(storage, { draft: snapshot, history: currentRef.current, storageRevision: 0, savedRevision: -1 }, cacheBinding);
  const recovered = readGeneratedWorkspace(storage, result.document);
  assert.ok(recovered, 'reloading the generated view retains edge IDs distinct from node IDs');
  assert.deepEqual(recovered.binding.edgeBindings, generated.edgeBindings);
  // Run the actual App callback as well: the generator receipt keeps the
  // complete graph, while App must pass the presentation snapshot through to
  // createGeneratedCanvas and restore current selection/camera on that scene.
  const workspace = { draft: snapshot, history: currentRef.current, selection: [memoryMask.id], camera: { x: 54, y: 0, zoom: 1 }, tool: 'select' as const };
  let openedDocument: CanvasDocument | undefined, selected: unknown, restoredCamera: unknown, selectedProject: unknown, updatedUrl: unknown;
  const saves: unknown[][] = [], versions: number[] = [];
  const appCurrent = { current: null as ReturnType<typeof createHistory> | null };
  const generatedWorkspaces = { current: new Map<string, GeneratedWorkspaceBinding>() };
  const open = actualCallback('App.tsx', 'App', 'openGeneratedModel', {
    cancelGesture: () => {}, authoringSessionKey: { current: 'active' }, authoringSessions: { current: new Map([['active', workspace]]) },
    generatedWorkspaces, sourceDraftKey: sourceAuthoringKey,
    cacheGeneratedWorkspace: () => {},
    loadSequence: { current: 0 }, cameraOwner: { current: null }, cameraIntent: { current: 0 },
    api: { open: async () => ({ projectId: 'generated-project', documentId: result.document.id, revision: 3 }),
      save: async (...values: unknown[]) => { saves.push(values); return { revision: 4 }; } }, createGeneratedCanvas,
    createHistory, historyRef: appCurrent, setHistory: (history: ReturnType<typeof createHistory>) => { openedDocument = history.document; },
    setSelection: (value: unknown) => { selected = value; }, setProjectId: (value: unknown) => { selectedProject = value; }, setExampleId: () => {}, setAuthoringOpen: () => {},
    setStorageRevision: (value: number) => { versions.push(value); }, setSavedVisualRevision() {}, setReview() {},
    localStorage: { removeItem() {} }, REVIEW: 'review', setPreview() {}, setSourceOpen() {}, updateDocumentUrl: (value: unknown) => { updatedUrl = value; },
    commitCamera: (camera: unknown) => { restoredCamera = camera; }, setTool: () => {}, initializeCamera: () => { throw new Error('Current camera must be retained'); }, setNotice: () => {},
  });
  await open(generated);
  assert.ok(openedDocument);
  assert.equal(buildScene(openedDocument).nodes.length, 12);
  assert.deepEqual(selected, { kind: 'node', ids: [result.nodeBindings[memoryMask.id]] });
  assert.deepEqual(restoredCamera, workspace.camera);
  assert.equal(selectedProject, 'generated-project'); assert.equal(updatedUrl, openedDocument.id); assert.deepEqual(versions, [4]);
  assert.equal(saves.length, 1); assert.equal(saves[0][1], 3); assert.deepEqual(saves[0][0], openedDocument);
  assert.deepEqual((saves[0][2] as ReturnType<typeof createHistory>).document, openedDocument, 'server persistence retains the generated presentation before navigation');
  const binding = generatedWorkspaces.current.get(sourceAuthoringKey(openedDocument));
  assert.ok(binding, 'the actual opening callback links this new view to the exact retained draft workspace');
  assert.equal(binding.workspaceKey, 'active'); assert.deepEqual(binding.draft, snapshot);
  assert.deepEqual(binding.nodeBindings, { ...generated.nodeBindings, ...(generated.containerBindings ?? {}), ...result.nodeBindings });
  assert.equal(binding.visualRevision, openedDocument.revision);
  const generatedCache = new Map<string, unknown>(), cache = { get: async (key: string) => generatedCache.get(key), put: async (key: string, value: unknown) => { generatedCache.set(key, structuredClone(value)); } };
  await writePersistentGeneratedWorkspace({ ...workspace, storageRevision: 0, savedRevision: -1 }, binding, cache);
  const resumed = await readPersistentGeneratedWorkspace(openedDocument, cache, { getItem: () => null, setItem() {} });
  assert.ok(resumed, 'the exact bindings retained by App remain recoverable after reload');
  assert.deepEqual(resumed.workspace.history, currentRef.current);
});

test('generated workspace restores from async storage without touching localStorage quota and rejects stale identities', async () => {
  const architecture = grouped(), document = createDocument(architecture), draft = blankDraft('draft-async-cache');
  draft.nodes = [{ id: 'first', kind: 'ReLU', label: 'first', parameters: {}, position: { x: 20, y: 40 } }];
  const history = changeDraft(draftHistory(draft), value => { value.title = 'retained edit'; });
  const workspace = { draft: history.draft, history, storageRevision: 8, savedRevision: 1,
    selection: ['first'], camera: { x: -45, y: 13, zoom: .75 }, tool: 'select' as const };
  const binding: GeneratedWorkspaceBinding = { workspaceKey: 'cached', documentId: document.id, sourceDigest: document.sourceBindingDigest,
    irDigest: document.architecture.irDigest, draft, nodeBindings: { first: 'a' }, edgeBindings: {}, visualRevision: document.revision };
  const records = new Map<string, unknown>(), cache = { get: async (key: string) => records.get(key), put: async (key: string, value: unknown) => { records.set(key, structuredClone(value)); } };
  let legacyReads = 0;
  const legacy = { getItem: () => { legacyReads++; throw new Error('localStorage quota unavailable'); }, setItem: () => { throw new Error('must not write full workspace to localStorage'); } };
  await writePersistentGeneratedWorkspace(workspace, binding, cache);
  const restored = await readPersistentGeneratedWorkspace(document, cache, legacy);
  assert.ok(restored); assert.equal(legacyReads, 0);
  assert.deepEqual(restored.binding, binding); assert.deepEqual(restored.workspace.history, history);
  assert.deepEqual(restored.workspace.selection, workspace.selection); assert.deepEqual(restored.workspace.camera, workspace.camera);
  const invalid = structuredClone(records.get(sourceAuthoringKey(document))) as { binding: GeneratedWorkspaceBinding };
  invalid.binding.sourceDigest = 'stale-source'; records.set(sourceAuthoringKey(document), invalid);
  assert.equal(await readPersistentGeneratedWorkspace(document, cache, legacy), null, 'async records retain the full source-generation gates');
});

test('legacy workspace migrates to async storage without a synchronous write and remains recoverable if migration fails', async () => {
  const document = createDocument(grouped()), draft = blankDraft('draft-legacy');
  const binding: GeneratedWorkspaceBinding = { workspaceKey: 'legacy', documentId: document.id, sourceDigest: document.sourceBindingDigest,
    irDigest: document.architecture.irDigest, draft, nodeBindings: {}, visualRevision: 0 };
  const strings = new Map<string, string>(), legacy = { getItem: (key: string) => strings.get(key) ?? null, setItem: (key: string, value: string) => { strings.set(key, value); }, removeItem: (key: string) => { strings.delete(key); } };
  writeGeneratedWorkspace(legacy, { draft, storageRevision: 0, savedRevision: -1 }, binding);
  const puts: unknown[] = [], cache = { get: async () => undefined, put: async (_key: string, value: unknown) => { puts.push(value); } };
  assert.ok(await readPersistentGeneratedWorkspace(document, cache, legacy)); assert.equal(puts.length, 1);
  assert.equal(strings.size, 0, 'release the old synchronous quota only after migration commits');
  writeGeneratedWorkspace(legacy, { draft, storageRevision: 0, savedRevision: -1 }, binding);
  assert.ok(await readPersistentGeneratedWorkspace(document, { get: async () => { throw Error('unavailable'); }, put: async () => { throw Error('unavailable'); } }, legacy));
  assert.equal(strings.size, 1, 'a failed migration keeps its recoverable original');
});

test('opening a generated model keeps the editor and current document intact if server persistence fails or becomes stale', async () => {
  const draft = blankDraft('draft-generation-save-failure'), architecture = grouped();
  const generated = { draft, architecture, nodeBindings: {}, edgeBindings: {} } as GeneratedDraft;
  const retained = createGeneratedCanvas(architecture, draft, generated);
  for (const stale of [false, true]) {
    const original = { document: createDocument(architecture), past: [], future: [] }, historyRef = { current: original }, loadSequence = { current: 0 };
    let saves = 0;
    const open = actualCallback('App.tsx', 'App', 'openGeneratedModel', {
      cancelGesture() {}, authoringSessionKey: { current: null }, authoringSessions: { current: new Map() }, loadSequence, createGeneratedCanvas,
      api: { open: async () => { if (stale) loadSequence.current++; return { documentId: retained.document.id, projectId: 'project', revision: 1 }; },
        save: async () => { saves++; throw Error('server unavailable'); } },
      createHistory, historyRef,
      setHistory: () => { throw Error('must retain current editor'); }, updateDocumentUrl: () => { throw Error('must retain current URL'); },
    });
    if (stale) await open(generated); else await assert.rejects(() => open(generated), /server unavailable/);
    assert.equal(historyRef.current, original); assert.equal(saves, stale ? 0 : 1);
  }
});
