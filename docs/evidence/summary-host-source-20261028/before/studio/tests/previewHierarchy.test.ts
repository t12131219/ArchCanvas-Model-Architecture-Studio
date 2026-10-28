import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
import { previewFrontier, previewHierarchy, previewHierarchyExpansion } from '../src/previewHierarchy.ts';
import type { PreviewSnapshot } from '../src/PreviewStudio.tsx';

function fixture(): PreviewSnapshot {
  const detail = { nodes: [
    { id: 'root', label: 'Model', kind: 'group', x: 0, y: 0 },
    { id: 'wrapper', parent: 'root', label: 'Inspection', x: 20, y: 20 },
    { id: 'condition', parent: 'wrapper', label: 'if enabled', kind: 'source_structure', x: 40, y: 40 },
    { id: 'yes', parent: 'condition', label: 'if enabled', x: 60, y: 60 },
    { id: 'inner', parent: 'yes', label: 'Linear', x: 80, y: 80 },
    { id: 'no', parent: 'condition', label: 'else', x: 60, y: 160 },
    { id: 'other', parent: 'root', label: 'Other', x: 20, y: 320 },
    { id: 'junction', parent: 'root', junction: true, x: 0, y: 0 },
    { id: 'after-junction', parent: 'junction', label: 'Output', x: 0, y: 0 },
  ] };
  return { caseId: 'unfamiliar-model', graph: {
    nodes: [{ ...detail.nodes[0], expanded: true }, { ...detail.nodes[1], expanded: false }, { ...detail.nodes[6], expanded: false }],
    edges: [{ id: 'edge-1', source: 'root', target: 'wrapper' }, { id: 'edge-2', source: 'wrapper', target: 'other' }], frontierPreset: 'overview',
    recursive: { authority: { detail, mandatory: ['root'] },
      state: { open: ['root', 'yes'], folded: ['wrapper'], studioPresentation: { nodes: { condition: { alias: 'Decision', pinned: true } } } } },
  } };
}

test('preview navigation retains unmapped wrappers and branch identities, with renderer ordering and no invented source facts', () => {
  const snapshot = fixture(), before = JSON.stringify(snapshot), hierarchy = previewHierarchy(snapshot)!;
  assert.deepEqual(hierarchy.nodes.map(n => n.id), ['root', 'wrapper', 'condition', 'yes', 'inner', 'no', 'other', 'after-junction']);
  assert.deepEqual(hierarchy.nodes.find(n => n.id === 'condition')?.children, ['yes', 'no']);
  assert.equal(hierarchy.nodes.find(n => n.id === 'after-junction')?.parentId, 'root');
  assert.deepEqual(hierarchy.expandedIds, ['root', 'yes']);
  assert.deepEqual(hierarchy.displayAliases, { condition: 'Decision' });
  assert.deepEqual(hierarchy.pinnedObjects, ['condition']);
  assert.ok(hierarchy.nodes.every(n => !('source' in n) && !('evidence' in n)));
  assert.equal(JSON.stringify(snapshot), before);
});

test('expanding a hidden search result opens its ancestors in order and preserves other branches', () => {
  const hierarchy = previewHierarchy(fixture())!;
  const before = JSON.stringify(hierarchy);
  assert.deepEqual(previewHierarchyExpansion(hierarchy, 'yes', true), [
    { type: 'expand', id: 'wrapper', expanded: true }, { type: 'expand', id: 'condition', expanded: true },
  ]);
  assert.deepEqual(previewHierarchyExpansion(hierarchy, 'yes', false), [{ type: 'expand', id: 'yes', expanded: false }]);
  for (const id of ['root', 'inner', 'unknown']) assert.deepEqual(previewHierarchyExpansion(hierarchy, id, true), []);
  assert.equal(JSON.stringify(hierarchy), before);
  assert.equal(previewHierarchy(null), null);
});

test('frontier summary counts the committed preview and exposes F0/F1 state without mutating it', () => {
  const snapshot = fixture(), hierarchy = previewHierarchy(snapshot)!;
  const overview = previewFrontier(snapshot, hierarchy)!;
  assert.equal(overview.preset, 'overview');
  assert.equal(overview.label, '架构概览（F0）');
  assert.equal(overview.visibleNodeCount, 3);
  assert.equal(overview.visibleEdgeCount, 2);
  assert.equal(overview.expandableCount, 1);
  const detail = { ...snapshot, frontierPreset: 'detail', graph: { ...(snapshot.graph as Record<string, unknown>), frontierPreset: undefined } };
  assert.equal(previewFrontier(detail, previewHierarchy(detail))?.label, '架构详图（F1）');
});

test('child bridge maps F0/F1 presets to the same recursive identities', async () => {
  const engine = readFileSync(new URL('../public/preview/yworks_edge_router_lab/app.js', import.meta.url), 'utf8');
  const command = engine.slice(engine.indexOf('  async function studioCommand('), engine.indexOf("  $('showSourceImport').onclick"));
  const nodes = [{ id: 'root', parent: null }, { id: 'module', parent: 'root' }, { id: 'leaf', parent: 'module' }, { id: 'other', parent: 'root' }];
  const operations: unknown[][] = [];
  const toggles: Record<string, { checked: boolean }> = { showGhost: { checked: false }, showObstacles: { checked: false } };
  let mode = '';
  const context = vm.createContext({
    graph: { recursive: { authority: { detail: { nodes }, mandatory: ['root'] } } }, busy: false, drag: null,
    F: { containers: (authority: any) => authority.detail.nodes.filter((node: any) => nodes.some(child => child.parent === node.id)).map((node: any) => node.id),
      children: (authority: any, id: string) => authority.detail.nodes.filter((node: any) => node.parent === id) },
    studioVisual: async (message: { operations: unknown[] }) => { operations.push(message.operations); }, studioBridge: { state() {} },
    $: (id: string) => toggles[id], render() {}, setInteractionMode: (value: string) => { mode = value; },
    sourceNodes: () => [],
  });
  vm.runInContext(command, context);
  await context.studioCommand('set-frontier', { preset: 'overview' });
  assert.deepEqual(JSON.parse(JSON.stringify(operations[0])), [{ type: 'expand', id: 'root', expanded: true }, { type: 'expand', id: 'module', expanded: false }]);
  await context.studioCommand('set-frontier', { preset: 'detail' });
  assert.deepEqual(JSON.parse(JSON.stringify(operations[1])), [{ type: 'expand', id: 'root', expanded: true }, { type: 'expand', id: 'module', expanded: true }]);
  await context.studioCommand('show-ghost', { enabled: true });
  await context.studioCommand('show-obstacles', { enabled: true });
  await context.studioCommand('interaction-mode', { mode: 'realtime' });
  assert.equal(toggles.showGhost.checked, true); assert.equal(toggles.showObstacles.checked, true); assert.equal(mode, 'realtime');
  assert.equal(nodes[1].id, 'module');
});

test('preview state publishes a recursive revision and source identity for panel synchronization', () => {
  const engine = readFileSync(new URL('../public/preview/yworks_edge_router_lab/app.js', import.meta.url), 'utf8');
  const documentFunction = engine.slice(engine.indexOf('  function studioDocument('), engine.indexOf('  function studioState('));
  const context = vm.createContext({
    graph: { recursive: { revision: 9 }, irSha256: 'ir-9' }, current: { id: 'case-9', title: 'Case', collection: 'models' }, view: { key: 'unified' },
    frontierPreset: 'detail', interactionMode: 'compat', tool: 'select', canvasGridVisible: true, dirty: false, busy: false, drag: null,
    history: [], future: [], importedPackages: new Map(), importedDocuments: new Map(), catalogSources: null, selectedNodes: new Set(), selectedEdges: new Set(),
    window: {}, N: { inspector: () => null }, camera: { x: 10, y: 20, w: 800, h: 500 },
    $: () => ({ checked: false }), studioSelection: () => ({ nodes: [], edges: [] }), E: { clone: (value: unknown) => value },
  });
  vm.runInContext(documentFunction, context);
  const document = context.studioDocument();
  assert.equal(document.snapshotRevision, 9);
  assert.deepEqual(JSON.parse(JSON.stringify(document.sourceIdentity)), { caseId: 'case-9', sourceSha256: null, irSha256: 'ir-9' });
  assert.equal(document.frontierPreset, 'detail');
  assert.equal(document.graph.studioCamera, undefined, 'legacy camera remains outside the graph snapshot');
  context.graph.generic = {};
  assert.deepEqual(JSON.parse(JSON.stringify(context.studioDocument().graph.studioCamera)), { x: 10, y: 20, w: 800, h: 500 });
});

const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8');
function callback(name: string, environment: Record<string, unknown>) {
  const ast = ts.createSourceFile('App.tsx', app, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const root = ast.statements.find(n => ts.isFunctionDeclaration(n) && n.name?.text === 'App') as ts.FunctionDeclaration;
  const statement = root.body!.statements.find(n => ts.isVariableStatement(n) && n.declarationList.declarations.some(d => ts.isIdentifier(d.name) && d.name.text === name));
  assert.ok(statement);
  const code = ts.transpileModule(statement.getText(ast), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  return new Function(...Object.keys(environment), `${code}; return ${name};`)(...Object.values(environment)) as (...args: any[]) => void;
}

test('actual tree callbacks operate on preview-only wrappers without requiring formal mapping or changing source history', () => {
  const snapshot = fixture(), focused: unknown[] = [], visual: unknown[] = [], failure: string[] = [];
  const environment = { useCallback: (fn: unknown) => fn, graphFromSnapshot: () => snapshot.graph, previewSnapshot: { current: snapshot },
    previewNodeId: () => { throw Error('a display identity must not require formal matching'); },
    previewEngine: { current: { focus: (message: unknown) => focused.push(message), visual: async (operations: unknown) => { visual.push(operations); } } },
    setFailure: (text: string) => failure.push(text), setPanel() {}, readyPreview: () => true, loadSequence: { current: 2 },
    previewHierarchy, previewHierarchyExpansion, apply: () => { throw Error('navigation must not replace or mutate formal source facts'); } };
  const select = callback('selectHierarchyNode', environment), expand = callback('expandHierarchyNode', environment);
  select('condition'); select('no', true); expand('yes', true);
  assert.deepEqual(focused, [{ nodeId: 'condition', additive: false }, { nodeId: 'no', additive: true }]);
  assert.deepEqual(visual, [[{ type: 'expand', id: 'wrapper', expanded: true }, { type: 'expand', id: 'condition', expanded: true }]]);
  assert.ok(failure.every(text => text === ''));
});

test('actual focus reveals a hidden node and toggles the same selection set used by canvas and tree', async () => {
  const engine = readFileSync(new URL('../public/preview/yworks_edge_router_lab/app.js', import.meta.url), 'utf8');
  const focus = engine.slice(engine.indexOf('  async function studioFocus('), engine.indexOf('  function selectedLayoutNodes('));
  const selection = readFileSync(new URL('../public/preview/yworks_edge_router_lab/studio-selection.js', import.meta.url), 'utf8');
  const nodes = [{ id: 'root' }, { id: 'condition', parent: 'root' }, { id: 'inner', parent: 'condition', x: 50, y: 80, w: 100, h: 50 }];
  const opened: unknown[] = [];
  let visible = false;
  const context = vm.createContext({ graph: { recursive: { authority: { detail: { nodes } } } }, busy: false, drag: null,
    selectedNodes: new Set(['other']), selectedEdges: new Set(['edge']), selectedAnnotation: 'note',
    N: { nodes: () => nodes },
    sourceNodes: () => [nodes[2]], node: (id: string) => visible ? nodes.find(n => n.id === id) : undefined,
    changeFrontier: async (operation: unknown) => { opened.push(JSON.parse(JSON.stringify(operation))); visible = true; },
    $: () => ({clientWidth: 800, clientHeight: 500}), camera: { w: 100, h: 100 }, cameraUpdate() {}, render() {}, studioBridge: { state() {} } });
  vm.runInContext(selection, context); context.window = context;
  vm.runInContext(readFileSync(new URL('../public/preview/yworks_edge_router_lab/view-navigation.js', import.meta.url), 'utf8'), context);
  vm.runInContext(focus, context);
  await context.studioFocus({ nodeId: 'inner', additive: true });
  assert.deepEqual(opened, [{ type: 'expand', ids: ['root', 'condition'], expanded: true }]);
  assert.deepEqual([...context.selectedNodes], ['other', 'inner']);
  assert.equal(context.selectedEdges.size, 0); assert.equal(context.selectedAnnotation, null);
  await context.studioFocus({ nodeId: 'inner', additive: true }); assert.deepEqual([...context.selectedNodes], ['other']);
  await context.studioFocus({ nodeId: 'inner' }); assert.deepEqual([...context.selectedNodes], ['inner']);
  assert.equal(context.camera.w,800,'tree focus opens a readable view at 100% instead of retaining tiny overview zoom');
});
