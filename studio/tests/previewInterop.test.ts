import test from 'node:test';
import assert from 'node:assert/strict';
import { architecturePreviewFocus, architecturePreviewRequest, assertPreviewBundleMatchesArchitecture, bundlePreviewRequest,
  documentPreviewIdentity, PreviewRequestGate, previewCanvasOperations, previewExpansionOperations, previewNodeLayoutOperation, previewSelectionDraftIds, previewSelectionNodeIds,
  previewSourceIdentity, previewSourceLocation, rawPreviewSourceRequest } from '../src/previewInterop.ts';
import { previewUniqueNodeBindings } from '../src/previewInterop.ts';
import type { PreviewSelection, PreviewSourceBundle, RawPreviewSource } from '../src/previewInterop.ts';
import type { Architecture, ArchitectureNode, CanvasDocument } from '../src/core/types.ts';
import type { AuthoredDraft, SourceDraftRef } from '../src/authoring.ts';

const source = 'from torch import nn\nclass Model(nn.Module):\n def __init__(self): pass\n def forward(self, features):\n  left = self.shared(features)\n  right = self.alias(features)\n  return left + right\n';
function node(id: string, kind: string, category: string, line: number, endLine = line, expression = 'self.shared(features)'): ArchitectureNode {
  return { id, label: kind, kind, category, parentId: id === 'root' ? undefined : 'root', children: [], ports: [], parameters: {}, evidence: 'source',
    source: { path: 'models/net.py', line, endLine, expression } };
}
function architecture(): Architecture {
  const root = node('root', 'Model', 'container', 2, 7, 'class Model(nn.Module): ...'); root.children = ['input', 'left', 'right'];
  const left = node('left', 'Linear', 'linear', 5); left.instanceId = 'instance:models.net.Model.shared';
  const right = node('right', 'Linear', 'linear', 6, 6, 'self.alias(features)'); right.instanceId = left.instanceId;
  const input = node('input', 'Input', 'input', 4, 7, 'def forward(self, features): ...'); input.label = 'features';
  return { schemaVersion: 1, id: 'source-model', label: 'Model', sourceDigest: 'formal-source-manifest', irDigest: 'formal-ir',
    entry: 'models.net:Model', diagnostics: [], sources: [{ path: 'models/net.py', content: source, digest: 'file-hash' },
      { path: 'models/__init__.py', content: '', digest: 'empty-file-hash' }], nodes: [root, input, left, right], edges: [] };
}
function document(arch = architecture()): CanvasDocument {
  return { schemaVersion: 1, id: 'canvas-model', title: 'Model', revision: 2, sourceBindingDigest: arch.sourceDigest, architecture: arch,
    displayAliases: {}, nodeStyleOverrides: {}, edgeStyleOverrides: {}, legendItems: [], annotations: [], pageSpec: { widthMm: 180, background: 'white', preset: 'paper' },
    expandedIds: [], layout: {}, layoutByFrontier: {}, pinnedObjects: [] };
}
function bundle(): PreviewSourceBundle {
  return { schema: 'summary-source-adapter/1', id: 'source-1234567890abcdef', entry: 'models.net:Model', sourceSha256: 'preview-source-manifest', irSha256: 'preview-ir',
    files: [{ path: 'models/net.py', text: source, sha256: 'file-hash' }, { path: 'models/__init__.py', text: '', sha256: 'empty-file-hash' }],
    evidence: { left: { file: 'models/net.py', line: 5, endLine: 5, column: 9, endColumn: 30, expression: 'self.shared(features)' },
      right: { file: 'models/net.py', line: 6, endLine: 6, column: 10, endColumn: 30, expression: 'self.alias(features)' },
      input: { file: 'models/net.py', line: 4, endLine: 4, column: 19, endColumn: 27, expression: 'features' } },
    ir: { nodes: [{ id: 'preview-left', kind: 'linear', label: 'Linear', instance: 'models.net:Model.shared', source_evidence: ['left'] },
      { id: 'preview-right', kind: 'linear', label: 'Linear', instance: 'models.net:Model.shared', source_evidence: ['right'] },
      { id: 'preview-input', kind: 'input', label: 'features', source_evidence: ['input'] }] } };
}

test('preview analysis receives the complete managed corpus and cloned constructor config', () => {
  const arch = architecture(), config = { width: 16, nested: { stride: 2 } }, before = JSON.stringify(arch);
  const request = architecturePreviewRequest(arch, config);
  assert.deepEqual(request.files, { 'models/__init__.py': '', 'models/net.py': source });
  assert.equal(request.entry, 'models.net:Model');
  (request.config.nested as { stride: number }).stride = 9;
  assert.equal(config.nested.stride, 2); assert.equal(JSON.stringify(arch), before);
  const adapted = bundle(); adapted.config = { width: 24 };
  assert.deepEqual(bundlePreviewRequest(adapted).config, { width: 24 });
  assert.notEqual(arch.sourceDigest, adapted.sourceSha256);
  assert.doesNotThrow(() => assertPreviewBundleMatchesArchitecture(adapted, arch));
  adapted.files[0].text += '# changed';
  assert.throws(() => assertPreviewBundleMatchesArchitecture(adapted, arch), /工作副本不同/);
});

test('raw catalog source preserves module paths and rejects invalid paths, duplicates and UTF-8 overflow', () => {
  const raw: RawPreviewSource = { schema: 'archcanvas-preview-source/1', caseId: 'catalog-model', entry: 'models.net:Model', files: { 'models\\net.py': source } };
  assert.deepEqual(rawPreviewSourceRequest(raw).files, { 'models/net.py': source });
  for (const path of ['/tmp/net.py', '../net.py', 'models/../../net.py', 'C:\\net.py', 'weights.bin']) {
    assert.throws(() => rawPreviewSourceRequest({ ...raw, files: { [path]: source } }), /路径|Python/);
  }
  assert.throws(() => rawPreviewSourceRequest({ ...raw, files: { 'models/net.py': source, './models/net.py': source } }), /重复/);
  assert.throws(() => rawPreviewSourceRequest({ ...raw, files: { 'net.py': '模型'.repeat(400_000) } }), /2 MB/);
  assert.throws(() => rawPreviewSourceRequest({ ...raw, files: {} }), /1–80/);
});

test('source-generation tickets reject a slow old response, repeated requests and model switches', async () => {
  const gate = new PreviewRequestGate(), identity = previewSourceIdentity(architecture(), 'canvas-model');
  const old = gate.begin(identity), sameSource = gate.begin(identity);
  await Promise.resolve();
  assert.equal(gate.isCurrent(old), false); assert.equal(gate.isCurrent(sameSource, identity), true);
  const changed = { ...identity, sourceDigest: 'new-source' }, current = gate.begin(changed);
  assert.equal(gate.isCurrent(sameSource), false); assert.equal(gate.isCurrent(current, identity), false);
  assert.equal(gate.isCurrent(current, changed), true);
  gate.invalidate(); assert.equal(gate.isCurrent(current), false);
  const canvas = document(); assert.deepEqual(documentPreviewIdentity(canvas), identity);
  canvas.sourceBindingDigest = 'stale'; assert.throws(() => documentPreviewIdentity(canvas), /绑定摘要/);
});

test('source evidence maps repeated shared calls individually and broad editor input evidence by kind', () => {
  const arch = architecture(), adapted = bundle();
  assert.deepEqual(previewSelectionNodeIds(arch, { caseId: adapted.id, nodeId: 'preview-left' }, adapted), ['left']);
  assert.deepEqual(previewSelectionNodeIds(arch, { caseId: adapted.id, nodeId: 'preview-right' }, adapted), ['right']);
  assert.deepEqual(previewSelectionNodeIds(arch, { nodeId: 'preview-input' }, adapted), ['input']);
  assert.deepEqual(previewSelectionNodeIds(arch, { caseId: 'different-model', nodeId: 'left' }, adapted), []);
  assert.deepEqual(previewSelectionNodeIds(arch, { nodeId: 'unknown' }, adapted), []);
  assert.deepEqual(previewSelectionNodeIds(arch, { sourcePath: 'elsewhere.py', line: 5 }), []);
  assert.equal(previewSourceLocation({ span: { file: '../model.py', line: 1 } }), null);
  assert.deepEqual(previewSourceLocation({ nodeId: 'preview-right' }, adapted), {
    path: 'models/net.py', line: 6, endLine: 6, column: 10, endColumn: 30, expression: 'self.alias(features)' });
  assert.deepEqual(architecturePreviewFocus(arch, 'right'), { nodeId: 'right', sourcePath: 'models/net.py', line: 6, endLine: 6, expression: 'self.alias(features)' });
});

test('instance identities distinguish Sequential children that share a single call source span', () => {
  const arch = architecture(), first = node('first', 'Linear', 'linear', 5), second = node('second', 'Linear', 'linear', 5);
  first.instanceId = 'instance:models.net.Model.layers.0'; second.instanceId = 'instance:models.net.Model.layers.1';
  arch.nodes = [first, second];
  const selection: PreviewSelection = { node: { id: 'summary-child', kind: 'linear', instance: 'models.net:Model.layers.1' },
    span: { file: 'models/net.py', line: 5, endLine: 5, expression: 'self.shared(features)' } };
  assert.deepEqual(previewSelectionNodeIds(arch, selection), ['second']);
});

test('inspection constructors bridge exact call locations without guessing labels or choosing repeated calls', () => {
  const arch = architecture(), adapted = bundle();
  adapted.evidence!.construction = { file: 'models/net.py', line: 3, endLine: 3, expression: 'ReviewCell()' };
  const card = { id: 'inspection-cell', kind: 'source_structure', label: 'arbitrary display title', sourceStructure: true,
    source_evidence: ['construction'], sourceParameters: { callSites: [adapted.evidence!.left] } };
  adapted.ir!.nodes = [card];
  assert.deepEqual(previewSelectionNodeIds(arch, { node: card }, adapted), ['left']);
  assert.equal(previewUniqueNodeBindings(arch, { nodes: [{ ...card, x: 0, y: 0 }] }, adapted).get(card.id), 'left');
  assert.equal(previewSourceLocation({ node: card }, adapted)?.line, 3, 'source inspection still opens its constructor first');
  card.sourceParameters.callSites.push(adapted.evidence!.right);
  assert.deepEqual(previewSelectionNodeIds(arch, { node: card }, adapted), ['left', 'right']);
  assert.equal(previewUniqueNodeBindings(arch, { nodes: [{ ...card, x: 0, y: 0 }] }, adapted).size, 0,
    'a shared definition cannot silently choose one runtime invocation');
  card.sourceParameters.callSites = [{ file: '../outside.py', line: 5, endLine: 5, expression: 'self.shared(features)' }];
  assert.deepEqual(previewSelectionNodeIds(arch, { node: card }, adapted), []);
});

test('reviewed catalog nodes use every evidence span and normalization aliases without matching display names', () => {
  const arch = architecture(), norm = node('formal-norm', 'LayerNorm', 'norm', 6), sameSpan = node('other-norm', 'LayerNorm', 'norm', 6);
  norm.label = 'source label'; sameSpan.label = 'Pretty label'; arch.nodes = [norm, sameSpan];
  const adapted = bundle(); adapted.evidence!.outside = { file: 'helper.py', line: 1, endLine: 1, expression: 'helper' };
  adapted.evidence!.norm = { file: 'models/net.py', line: 6, endLine: 6, expression: 'self.shared(features)' };
  const selection = { node: { id: 'reviewed-norm', kind: 'normalization', label: 'Pretty label', source_evidence: ['outside', 'norm'] } };
  assert.deepEqual(previewSelectionNodeIds(arch, selection, adapted), ['formal-norm', 'other-norm'], 'a matching alias cannot claim a unique source identity');
  arch.nodes = [norm, node('linear', 'Linear', 'linear', 6)];
  assert.deepEqual(previewSelectionNodeIds(arch, selection, adapted), ['formal-norm']);
});

test('preview selections follow live source and generated draft bindings without reviving removed objects', () => {
  const arch = architecture(), canvas = document(arch);
  const ref = (id: string): SourceDraftRef => ({ nodeId: id, sceneNodeId: id, kind: 'Linear', category: 'linear', evidence: 'source', portBindings: {}, originalParameters: {}, group: false });
  const draft: AuthoredDraft = { schemaVersion: 1, mode: 'authored-draft', id: 'draft', title: 'Model', revision: 1,
    nodes: [{ id: 'draft-left', kind: 'Linear', label: 'Linear', parameters: {}, position: { x: 0, y: 0 } }], edges: [],
    sourceProvenance: { schemaVersion: 1, digest: 'provenance', documentId: canvas.id, visualRevision: 2, sourceDigest: arch.sourceDigest, irDigest: arch.irDigest,
      architecture: arch, canvas, modules: [], nodeRefs: { 'draft-left': ref('left'), 'removed-right': ref('right') }, edgeRefs: {}, originalGraph: { nodes: [], edges: [] } } };
  assert.deepEqual(previewSelectionDraftIds(draft, { nodeId: 'preview-left' }, arch, bundle()), ['draft-left']);
  assert.deepEqual(previewSelectionDraftIds(draft, { nodeId: 'preview-right' }, arch, bundle()), []);
  const generated = { ...draft, sourceProvenance: undefined };
  assert.deepEqual(previewSelectionDraftIds(generated, { nodeId: 'preview-left' }, arch, bundle(), { 'draft-left': 'left' }), ['draft-left']);
  assert.deepEqual(previewSelectionDraftIds(generated, { nodeId: 'preview-left' }), []);
});

test('visual projection copies expansion and local positions while preserving source topology and ignoring unmapped objects', () => {
  const canvas = document(), before = JSON.stringify(canvas);
  const graph = { nodes: [{ id: 'root', x: 300, y: 100, expanded: true }, { id: 'preview-left', parent: 'root', x: 350, y: 220 },
    { id: 'preview-right', parent: 'unmapped-parent', x: 900, y: 500 }, { id: 'unmapped', x: 20, y: 20 },
    { id: 'input', parent: 'root', x: NaN, y: 200 }] };
  assert.deepEqual(previewCanvasOperations(canvas, graph, bundle()), [
    { type: 'expand', id: 'root', expanded: true }, { type: 'nodeLayout', id: 'root', position: { x: 300, y: 100 } },
    { type: 'nodeLayout', id: 'left', position: { x: 50, y: 120 } },
  ]);
  assert.equal(JSON.stringify(canvas), before);
});

test('editor layout replay converts local positions to the matching preview parent without borrowing legacy renderer positions', () => {
  const canvas = document(), graph = { nodes: [{ id: 'root', x: 300, y: 100, expanded: true }, { id: 'preview-left', parent: 'root', x: 350, y: 220 }] };
  assert.deepEqual(previewNodeLayoutOperation(canvas, { type: 'nodeLayout', id: 'left', position: { x: 80, y: 140, width: 200 } }, graph, bundle()),
    { type: 'nodeLayout', id: 'preview-left', position: { x: 380, y: 240, width: 200 } });
  assert.deepEqual(previewExpansionOperations(canvas, graph, bundle()), [{ type: 'expand', id: 'root', expanded: false }]);
  canvas.layout.left = { x: 9000, y: 9000 };
  assert.deepEqual(previewExpansionOperations(canvas, graph, bundle()), [{ type: 'expand', id: 'root', expanded: false }], 'expansion replay contains no old layout coordinates');
  graph.nodes[1].parent = 'another-root';
  assert.throws(() => previewNodeLayoutOperation(canvas, { type: 'nodeLayout', id: 'left', position: { x: 80, y: 140 } }, graph, bundle()), /父容器不同/);
});

test('required preview wrappers open regardless of authority traversal order while unrelated collapsed modules stay folded', () => {
  const arch = architecture(), root = arch.nodes.find(node => node.id === 'root')!;
  const folded = node('folded', 'Block', 'container', 3), hidden = node('hidden', 'Linear', 'linear', 3);
  const unrelated = node('unrelated', 'Block', 'container', 3), otherHidden = node('other-hidden', 'Linear', 'linear', 3);
  folded.children = [hidden.id]; hidden.parentId = folded.id;
  unrelated.children = [otherHidden.id]; otherHidden.parentId = unrelated.id;
  root.children = ['left', folded.id, unrelated.id];
  arch.nodes = [root, arch.nodes.find(node => node.id === 'left')!, folded, hidden, unrelated, otherHidden];
  const canvas = document(arch); canvas.expandedIds = ['root'];
  // The preview parser can place a formal sibling inside a source wrapper.
  // That wrapper must open to reveal the sibling even when its own formal
  // counterpart is folded; this must not depend on the detail array order.
  const detail = { nodes: [{ id: 'root', x: 0, y: 0 }, { id: 'folded', parent: 'root', x: 0, y: 0 },
    { id: 'left', parent: 'folded', x: 0, y: 0 }, { id: 'unrelated', parent: 'root', x: 0, y: 0 },
    { id: 'other-hidden', parent: 'unrelated', x: 0, y: 0 }] };
  const expected = [['folded', true], ['root', true], ['unrelated', false]];
  const before = JSON.stringify({ canvas, detail });
  for (const nodes of [detail.nodes, [...detail.nodes].reverse()]) {
    const replay = previewExpansionOperations(canvas, { nodes, recursive: { authority: { detail: { nodes } } } } as typeof detail);
    assert.deepEqual(replay.map(op => [op.id, op.expanded]).sort(([a], [b]) => String(a).localeCompare(String(b))), expected);
    assert.ok(replay.every(op => op.type === 'expand' && !('position' in op)));
  }
  assert.equal(JSON.stringify({ canvas, detail }), before);
});

test('source branch context rejects a missing or conflicting occurrence even when source evidence leaves a single candidate', () => {
  const arch = architecture(), adapted = bundle();
  const expression = 'if flag:\n return self.shared(features)\nelse:\n return self.alias(features)';
  adapted.evidence!.branch = { file: 'models/net.py', line: 4, endLine: 7, expression };
  adapted.evidence!.construction = { file: 'models/net.py', line: 3, endLine: 3, expression: 'ReviewCell()' };
  const branch = (id: string, condition: string): ArchitectureNode => ({ ...node(id, 'SourceBranch', 'module', 4, 7, expression),
    sourceStructure: true, parameters: { condition } });
  const module = (id: string, parentId: string): ArchitectureNode => ({ ...node(id, 'SourceModule', 'module', 3, 3, 'ReviewCell()'),
    parentId, sourceStructure: true });
  const rawBranch = { id: 'preview-else', kind: 'source_structure', sourceKind: 'SourceBranch', sourceStructure: true,
    source_evidence: ['branch'], sourceParameters: { condition: 'not (flag)' } };
  const rawModule = { id: 'preview-cell', parent: rawBranch.id, kind: 'source_structure', sourceKind: 'SourceModule',
    sourceStructure: true, source_evidence: ['construction'] };
  adapted.ir!.nodes = [rawBranch, rawModule];

  arch.nodes = [branch('only-if', 'flag')];
  assert.deepEqual(previewSelectionNodeIds(arch, { node: rawBranch }, adapted), [], 'an absent else branch cannot bind to the only if branch');
  arch.nodes = [branch('first-if', 'flag'), branch('second-if', 'flag')];
  assert.deepEqual(previewSelectionNodeIds(arch, { node: rawBranch }, adapted), [], 'conflicting alternatives cannot survive as an ambiguous fallback');
  arch.nodes = [branch('only-if', 'flag'), module('only-if-call', 'only-if')];
  assert.deepEqual(previewSelectionNodeIds(arch, { node: rawModule }, adapted), [], 'a constructor shared across branches does not authorize the wrong singleton occurrence');
  arch.nodes.push(module('second-if-call', 'only-if'));
  assert.deepEqual(previewSelectionNodeIds(arch, { node: rawModule }, adapted), [], 'all conflicting constructor candidates are excluded');
  arch.nodes.push(branch('correct-else', 'not (flag)'), module('correct-else-call', 'correct-else'));
  assert.deepEqual(previewSelectionNodeIds(arch, { node: rawBranch }, adapted), ['correct-else']);
  assert.deepEqual(previewSelectionNodeIds(arch, { node: rawModule }, adapted), ['correct-else-call']);
});

test('a branch-local inspection constructor still bridges an actual model operation through exact call evidence', () => {
  const arch = architecture(), adapted = bundle();
  adapted.evidence!.branch = { file: 'models/net.py', line: 4, endLine: 7, expression: 'if flag: ...' };
  adapted.evidence!.construction = { file: 'models/net.py', line: 3, endLine: 3, expression: 'ReviewCell()' };
  const rawBranch = { id: 'preview-else', kind: 'source_structure', sourceKind: 'SourceBranch', sourceStructure: true,
    source_evidence: ['branch'], sourceParameters: { condition: 'not (flag)' } };
  const card = { id: 'inspection-cell', parent: rawBranch.id, kind: 'source_structure', sourceKind: 'SourceModule',
    sourceStructure: true, source_evidence: ['construction'], sourceParameters: { callSites: [adapted.evidence!.right] } };
  adapted.ir!.nodes = [rawBranch, card];
  assert.deepEqual(previewSelectionNodeIds(arch, { node: card }, adapted), ['right'],
    'a real model operation uses exact call evidence even though the formal parser has no inspection branch wrapper');
  assert.equal(previewUniqueNodeBindings(arch, { nodes: [{ ...card, x: 0, y: 0 }] }, adapted).get(card.id), 'right');
});
