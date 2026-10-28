import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import ts from 'typescript';
import { validateDocument, applyVisualBatch } from '../src/core/index.ts';
import { previewMappingCoverage, previewMappingSignature, previewNeedsPanelDocument, previewPanelDocument, projectPreviewHistory } from '../src/previewPanelDocument.ts';
import { previewAnnotationBody, previewAnnotationConflicts, previewAnnotationPosition, previewDocumentSyncOperations } from '../src/previewPresentation.ts';
import { previewSelectionNodeIds, previewSourceMatchesArchitecture } from '../src/previewInterop.ts';
import { registeredProjectionFixture, syntheticProjectionFixture } from './previewGeneralizationFixtures.ts';

const cases = ['e40ad1504991acea', '2ae45b28d78ba027', '654be40c8d6a5cc2', '0342f4170c15ba8e', '9a9263f9a6014d8a', 'dab3eabe196047ba', '39ca17212a8004c5', 'b4e7f02ce4dce8d4', 'routing-lab'];
function exactPositions(document: ReturnType<typeof previewPanelDocument>, graph: ReturnType<typeof registeredProjectionFixture>['expanded']) {
  const nodes = new Map(graph.nodes.map(node => [node.id, node]));
  for (const node of graph.nodes) {
    const parent = node.parent ? nodes.get(node.parent) : undefined;
    if (node.parent && !parent) continue;
    assert.equal(document.layout[node.id].x, node.x - (parent?.x ?? 0), node.id);
    assert.equal(document.layout[node.id].y, node.y - (parent?.y ?? 0), node.id);
  }
}

test('registered convolution, branch, tuple, graph, multiscale, single-view and routing cases project exact geometry without source changes', () => {
  for (const id of cases) {
    const fixture = registeredProjectionFixture(id), { initial, expanded } = fixture, authority = JSON.stringify(initial.document.architecture);
    if (id !== 'routing-lab') {
      assert.ok(fixture.source);
      assert.ok(Object.keys(fixture.source.files).length > 0, `${fixture.title} source corpus must be real`);
      assert.ok(Object.keys(fixture.source.files).every(path => path.endsWith('.py')));
      assert.deepEqual(initial.document.architecture.sources.map(file => [file.path, file.content]), Object.entries(fixture.source.files));
      assert.equal(previewSourceMatchesArchitecture(fixture.source, initial.document.architecture), true);
    }
    const full = projectPreviewHistory(initial, expanded, fixture.source);
    assert.doesNotThrow(() => validateDocument(full.document)); exactPositions(full.document, expanded);
    assert.equal(full.document.architecture, initial.document.architecture, `${fixture.title} must share immutable source identity`);
    assert.equal(JSON.stringify(full.document.architecture), authority);
    assert.equal(projectPreviewHistory(full, structuredClone(expanded), fixture.source), full, `${fixture.title} duplicate state must not create history`);
    const folded = projectPreviewHistory(full, fixture.overview, fixture.source);
    assert.doesNotThrow(() => validateDocument(folded.document)); exactPositions(folded.document, fixture.overview);
    const reopened = projectPreviewHistory(folded, expanded, fixture.source); exactPositions(reopened.document, expanded);
    assert.equal(JSON.stringify(reopened.document.architecture), authority);
  }
});

test('multifile shared calls and tuple output slots retain exact source identities at small and maximum import sizes', () => {
  for (const size of [12, 480]) for (const recursive of [true, false]) {
    const fixture = syntheticProjectionFixture(size, recursive), before = fixture.initial;
    const topology = JSON.stringify(before.document.architecture);
    assert.equal(previewSourceMatchesArchitecture(fixture.source, before.document.architecture), true);
    const next = projectPreviewHistory(before, fixture.expanded, fixture.source);
    exactPositions(next.document, fixture.expanded);
    assert.equal(next.document.architecture, before.document.architecture); assert.equal(JSON.stringify(next.document.architecture), topology);
    const a = next.document.architecture.nodes.find(node => node.id === 'call/a')!, b = next.document.architecture.nodes.find(node => node.id === 'call/b')!;
    assert.equal(a.instanceId, b.instanceId); assert.notEqual(a.callId, b.callId);
    assert.deepEqual(next.document.architecture.nodes.filter(node => node.outputPath).map(node => node.outputPath), [[{ kind: 'index', index: 0 }], [{ kind: 'index', index: 1 }]]);
    assert.equal(new Set(next.document.architecture.edges.slice(0, 2).map(edge => edge.tensorId)).size, 1, 'visual fork preserves one shared producer value');
    assert.equal(next.past.length, before.past.length + 1, 'many simultaneous expansions form one projection history entry');
    assert.equal(projectPreviewHistory(next, structuredClone(fixture.expanded), fixture.source), next);
  }
});

test('incomplete formal coverage projects display objects without licensing source topology or replacing source text', () => {
  const fixture = syntheticProjectionFixture(), graph = structuredClone(fixture.expanded);
  const annotation = { id: 'reviewed/tuple-annotation', x: 90, y: 160, label: 'Display tuple' };
  graph.nodes.push(annotation); graph.recursive!.authority.detail.nodes.push(annotation);
  const snapshot = { caseId: fixture.id, graph };
  assert.equal(previewNeedsPanelDocument(snapshot, fixture.initial.document.architecture, fixture.source), true);
  assert.deepEqual(previewMappingCoverage(snapshot, fixture.initial.document.architecture, fixture.source).unmapped, ['reviewed/tuple-annotation']);
  const panel = previewPanelDocument(snapshot, fixture.source), signature = previewMappingSignature(snapshot);
  assert.ok(panel.sourceBindingDigest.startsWith('preview-only:'));
  assert.ok(panel.architecture.nodes.every(node => node.evidence === 'opaque' && !node.callId && !node.instanceId && !node.outputPath));
  assert.deepEqual(panel.architecture.sources.map(file => [file.path, file.content]), fixture.source.files.map(file => [file.path, file.text]));
  const moved = structuredClone(graph); moved.nodes[0].x += 50;
  assert.equal(previewMappingSignature({ graph: moved }), signature);
  moved.recursive!.authority.detail.nodes[0].source_evidence = ['other-file-span'];
  assert.notEqual(previewMappingSignature({ graph: moved }), signature);
});

test('formal authoring presentation returns to a shared-call preview without changing operands, return slots or source bytes', () => {
  const fixture = syntheticProjectionFixture(), projected = projectPreviewHistory(fixture.initial, fixture.expanded, fixture.source);
  const architecture = JSON.stringify(projected.document.architecture);
  const edited = applyVisualBatch(projected.document, [{ type: 'alias', id: 'call/a', label: 'Display shared branch' }, { type: 'nodeStyle', id: 'call/b', style: { fill: '#deeee6' } }]);
  const operations = previewDocumentSyncOperations(projected.document, edited, fixture.expanded, fixture.source);
  const paint = operations.find(operation => operation.type === 'syncPresentation')!;
  assert.ok(paint); assert.deepEqual((paint.nodes as Record<string, unknown>)['call/a'], { alias: 'Display shared branch', pinned: false });
  const graph = { ...fixture.expanded, studioPresentation: { nodes: paint.nodes, edges: paint.edges, title: paint.title, legend: paint.legend, annotations: {}, page: paint.page }, recursive: undefined };
  const returned = projectPreviewHistory(projected, graph as any, fixture.source);
  assert.equal(returned.document.displayAliases['call/a'], 'Display shared branch');
  assert.deepEqual(returned.document.nodeStyleOverrides['call/b'], { fill: '#deeee6' });
  assert.equal(JSON.stringify(returned.document.architecture), architecture);
});

function appValue(name: string, environment: Record<string, unknown>) {
  const source = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8'), ast = ts.createSourceFile('App.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const app = ast.statements.find(item => ts.isFunctionDeclaration(item) && item.name?.text === 'App');
  assert.ok(app && ts.isFunctionDeclaration(app) && app.body);
  const declaration = app.body.statements.find(item => ts.isFunctionDeclaration(item) ? item.name?.text === name : ts.isVariableStatement(item) && item.declarationList.declarations.some(d => ts.isIdentifier(d.name) && d.name.text === name));
  assert.ok(declaration);
  const compiled = ts.transpileModule(declaration.getText(ast), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  return new Function(...Object.keys(environment), `${compiled};return ${name};`)(...Object.values(environment));
}

test('preview render and navigation have no formal Scene build; source-editor projection remains explicit', () => {
  const text = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8'), ast = ts.createSourceFile('App.tsx', text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const owners: string[] = [];
  function visit(node: ts.Node, owner = 'render') {
    const name = ts.isFunctionDeclaration(node) ? node.name?.text : undefined;
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'buildScene') owners.push(owner);
    ts.forEachChild(node, child => visit(child, name && name !== 'App' ? name : owner));
  }
  visit(ast);
  assert.deepEqual(owners, ['continueModelAuthoring'], 'formal geometry is only constructed on explicit source-editor entry');
});

test('native annotation selection and placement inspect the visible 480-node graph without formal layout', () => {
  const fixture = syntheticProjectionFixture(480), graph = structuredClone(fixture.expanded);
  const annotation = { id: 'native-note', x: 110, y: 120, width: 90, text: 'abcdefghijklmnop\n' };
  graph.nodes.find(node => node.id === 'call/a')!.x = 100;
  graph.nodes.find(node => node.id === 'call/a')!.y = 100;
  graph.studioPresentation = { annotations: { [annotation.id]: annotation }, legend: [] };
  assert.deepEqual(previewAnnotationBody(annotation), { x: 105, y: 103, width: 100, height: 67 });
  assert.deepEqual(previewAnnotationConflicts(graph, annotation.id), [{ kind: 'node', id: 'call/a' }]);
  const source = JSON.stringify(fixture.initial.document.architecture), operations: any[] = [], focused: string[] = [];
  const move = appValue('moveAnnotationBelow', { scene: null, selectedAnnotation: annotation, previewSnapshot: { current: { graph } },
    previewAnnotationPosition, apply: (items: any[]) => operations.push(...items), focusAnnotation: (id: string) => focused.push(id),
    suggestAnnotationPosition() { throw Error('native note used formal geometry'); } });
  move();
  assert.equal(operations.length, 1); assert.equal(operations[0].type, 'annotation'); assert.deepEqual(focused, [annotation.id]);
  const moved = operations[0].annotation;
  (graph.studioPresentation as any).annotations[annotation.id] = moved;
  assert.deepEqual(previewAnnotationConflicts(graph, annotation.id), []);
  assert.deepEqual(previewAnnotationPosition(graph, annotation.id), { x: moved.x, y: moved.y }, 'repeat placement ignores the selected note');
  assert.equal(JSON.stringify(fixture.initial.document.architecture), source);
  const root = graph.nodes.find(node => node.id === 'net/root')!;
  Object.assign(root, { x: 0, y: 0, w: 2000, h: 50000 });
  (graph.studioPresentation as any).annotations[annotation.id] = { ...annotation, x: 1800, y: 300 };
  assert.deepEqual(previewAnnotationConflicts(graph, annotation.id), [], 'empty interior of expanded root remains available');
  (graph as any).canvas = [2000, 50000]; (graph.studioPresentation as any).legend = [{ id: 'legend:linear', label: 'Linear' }];
  (graph.studioPresentation as any).annotations[annotation.id] = { ...annotation, x: 1750, y: 49950 };
  assert.deepEqual(previewAnnotationConflicts(graph, annotation.id), [], 'inspector-only node legends do not occupy the canvas');
});

test('different parser IDs map two calls of one shared instance by multifile source evidence without merging tuple slots', () => {
  const fixture = syntheticProjectionFixture(), source = structuredClone(fixture.source), graph = structuredClone(fixture.expanded);
  source.evidence = {};
  source.ir = { nodes: [] };
  const locations = new Map(fixture.initial.document.architecture.nodes.map(node => [node.id, node.source!]));
  for (const id of ['call/a', 'call/b']) {
    const raw = graph.nodes.find(node => node.id === id)!, location = locations.get(id)!;
    raw.id = `parser:${id}`; raw.source_evidence = [id]; raw.kind = 'linear'; raw.instance = 'models.network:Network.shared';
    source.evidence[id] = { file: location.path, line: location.line, endLine: location.endLine, expression: location.expression };
    source.ir.nodes.push({ id: raw.id, kind: raw.kind, instance: raw.instance, source_evidence: [id] });
    for (const edge of graph.edges) { if (edge.source === id) edge.source = raw.id; if (edge.target === id) edge.target = raw.id; }
  }
  graph.recursive = undefined;
  const baseline = JSON.stringify(fixture.initial.document.architecture), projected = projectPreviewHistory(fixture.initial, graph, source);
  for (const id of ['call/a', 'call/b']) {
    const raw = graph.nodes.find(node => node.id === `parser:${id}`)!, parent = graph.nodes.find(node => node.id === raw.parent)!;
    assert.deepEqual(projected.document.layout[id], { x: raw.x - parent.x, y: raw.y - parent.y });
  }
  assert.equal(JSON.stringify(projected.document.architecture), baseline);
  assert.equal(previewSourceMatchesArchitecture(source, projected.document.architecture), true);
});

test('restored opaque panels preserve remembered hidden branch expansion without interpreting source edits', () => {
  const fixture = syntheticProjectionFixture(), detail = structuredClone(fixture.detail);
  const root = { ...detail.nodes.find(node => node.id === 'net/root')!, expanded: false };
  const graph = { nodes: [root], edges: [], recursive: { authority: { detail, mandatory: [] }, state: { open: ['net/root', 'branch/a', 'branch/b'], folded: ['branch/b'] } } };
  const panel = previewPanelDocument({ caseId: fixture.id, graph }, fixture.source);
  assert.deepEqual(panel.expandedIds, ['branch/a']);
  assert.ok(panel.architecture.nodes.every(node => node.evidence === 'opaque'));
  assert.equal(panel.architecture.sources.length, 3);
  assert.doesNotThrow(() => validateDocument(panel));
});

test('actual formal AST parsers preserve multifile shared calls and keep ambiguous nested evidence opaque', () => {
  const files = {
    'net/__init__.py': '',
    'net/ops.py': 'from torch import nn\nraise RuntimeError("Source text must never execute")\nclass Branch(nn.Module):\n def __init__(self):\n  super().__init__()\n  self.proj = nn.Linear(4,4)\n  self.act = nn.ReLU()\n def forward(self,x):\n  return self.act(self.proj(x))\n',
    'net/model.py': 'from torch import nn\nfrom .ops import Branch\nclass Model(nn.Module):\n def __init__(self):\n  super().__init__()\n  self.shared = Branch()\n def forward(self,x):\n  a = self.shared(x)\n  b = self.shared(x)\n  return a,b\n',
  };
  const src = fileURLToPath(new URL('../../src', import.meta.url));
  const parsed = JSON.parse(readFileSync(new URL('./fixtures/preview-formal-ast.json', import.meta.url), 'utf8'));
  assert.equal(parsed.schema, 'archcanvas-preview-formal-ast-fixture/1');
  assert.deepEqual(parsed.inputs, { files, entry: 'net.model:Model' });
  for (const [path, digest] of Object.entries(parsed.implementation)) {
    assert.equal(createHash('sha256').update(readFileSync(new URL('../../' + path, import.meta.url))).digest('hex'), digest, `Stale formal AST fixture; rerun generate-preview-ast-fixture.py: ${path}`);
  }
  assert.ok(parsed.parser.startsWith(src + '/archcanvas_preview/'));
  assert.equal(parsed.modelExecuted, false); assert.equal(parsed.torchLoaded, false);
  assert.equal(parsed.bundle.ir.modelExecuted, false);
  assert.deepEqual(parsed.bundle.diagnostics, []);
  const graph = { caseId: parsed.bundle.id, nodes: parsed.bundle.ir.nodes.map((raw: any, i: number) => ({ ...raw, parent: raw.parent || undefined, x: i * 210, y: i * 90, w: 180, h: 64, expanded: raw.kind === 'group' })), edges: parsed.bundle.ir.edges };
  const shared = graph.nodes.filter((node: any) => node.instance === 'net.model:Model.shared');
  assert.equal(shared.length, 2);
  const mapped = shared.map((node: any) => previewSelectionNodeIds(parsed.architecture, { nodeId: node.id, node }, parsed.bundle));
  assert.ok(mapped.every((ids: string[]) => ids.length === 1)); assert.notDeepEqual(mapped[0], mapped[1]);
  const calls = mapped.map((ids: string[]) => parsed.architecture.nodes.find((node: any) => node.id === ids[0]));
  assert.equal(calls[0].instanceId, calls[1].instanceId); assert.notEqual(calls[0].callId, calls[1].callId);
  const coverage = previewMappingCoverage({ caseId: parsed.bundle.id, graph }, parsed.architecture, parsed.bundle);
  assert.ok(coverage.ambiguous.length + coverage.shared.length + coverage.unmapped.length > 0, 'same-span nested calls cannot become unique source facts');
  const panel = previewPanelDocument({ caseId: parsed.bundle.id, graph }, parsed.bundle), topology = JSON.stringify(panel.architecture);
  assert.deepEqual(Object.fromEntries(panel.architecture.sources.map(file => [file.path, file.content])), files);
  assert.ok(panel.architecture.nodes.every(node => node.evidence === 'opaque' && !node.callId && !node.instanceId));
  const shifted = structuredClone(graph); shifted.nodes.forEach((node: any) => { node.x += 40; node.y += 60; });
  const projected = projectPreviewHistory({ document: panel, past: [], future: [] }, shifted, parsed.bundle);
  assert.equal(JSON.stringify(projected.document.architecture), topology); assert.equal(projected.document.architecture, panel.architecture);
  assert.doesNotThrow(() => validateDocument(projected.document));
});
