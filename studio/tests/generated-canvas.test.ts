import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import { createGeneratedCanvas } from '../src/generatedCanvas.ts';
import { buildScene, createDocument, createHistory, renderSvg } from '../src/core/index.ts';
import type { Architecture, ArchitectureNode, CanvasDocument } from '../src/core/types.ts';
import { blankDraft, draftHistory } from '../src/authoring.ts';
import type { AuthoredDraft } from '../src/authoring.ts';
import type { GeneratedDraft, ImportedSourceDraft } from '../src/api.ts';
import { sourceFrontierDocument } from '../src/sourceDraftFrontier.ts';

const project = fileURLToPath(new URL('../../', import.meta.url));
const run = promisify(execFile);
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
  let generated: GeneratedDraft | undefined;
  const currentRef = { current: draftHistory(snapshot) };
  const reproject = async (draft: AuthoredDraft) => {
    const document = sourceFrontierDocument(draft);
    return (await sourceBackend('print(json.dumps(rebase_source_frontier(v[0],v[1],v[2])))', [draft, document, buildScene(document)]) as ImportedSourceDraft).draft;
  };
  const callback = actualCallback('AuthoringStudio.tsx', 'AuthoringStudio', 'generate', {
    busy: false, invalidFieldsRef: { current: [] }, cancel: () => {}, setBusy: () => {}, setBusyOperation: () => {}, clearError: () => {}, currentRef,
    reprojectSourceDraft: reproject, api: { generateDraft: (draft: AuthoredDraft) => sourceBackend('print(json.dumps(generate_model(v)))', draft) },
    setGenerated: (value: GeneratedDraft) => { generated = value; }, reportError: (reason: unknown) => { throw reason; },
  });
  const originalBytes = JSON.stringify(snapshot);
  await callback();
  assert.ok(generated && generated.presentationDraft);
  assert.equal(generated.presentationDraft, snapshot, 'the actual callback retains the editing snapshot');
  assert.equal(generated.draft.nodes.length, 49, 'static generation still verifies the full source graph');
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
  // Run the actual App callback as well: the generator receipt keeps the
  // complete graph, while App must pass the presentation snapshot through to
  // createGeneratedCanvas and restore current selection/camera on that scene.
  const workspace = { selection: [memoryMask.id], camera: { x: 54, y: 0, zoom: 1 }, tool: 'select' };
  let openedDocument: CanvasDocument | undefined, selected: unknown, restoredCamera: unknown;
  const appCurrent = { current: null as ReturnType<typeof createHistory> | null };
  const open = actualCallback('App.tsx', 'App', 'openGeneratedModel', {
    cancelGesture: () => {}, authoringSessionKey: { current: 'active' }, authoringSessions: { current: new Map([['active', workspace]]) },
    loadSequence: { current: 0 }, cameraOwner: { current: null }, cameraIntent: { current: 0 },
    api: { register: async (architecture: Architecture) => ({ id: 'generated-project', architecture }) }, openArchitecture: async () => {}, createGeneratedCanvas,
    createHistory, historyRef: appCurrent, setHistory: (history: ReturnType<typeof createHistory>) => { openedDocument = history.document; },
    setSelection: (value: unknown) => { selected = value; }, setProjectId: () => {}, setExampleId: () => {}, setAuthoringOpen: () => {},
    commitCamera: (camera: unknown) => { restoredCamera = camera; }, setTool: () => {}, initializeCamera: () => { throw new Error('Current camera must be retained'); }, setNotice: () => {},
  });
  await open(generated);
  assert.ok(openedDocument);
  assert.equal(buildScene(openedDocument).nodes.length, 12);
  assert.deepEqual(selected, { kind: 'node', ids: [result.nodeBindings[memoryMask.id]] });
  assert.deepEqual(restoredCamera, workspace.camera);
});
