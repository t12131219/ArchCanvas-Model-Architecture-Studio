import test from 'node:test';
import assert from 'node:assert/strict';
import { previewDocumentSyncOperations, previewEdgeAppearance, previewFormalEdgeIds, previewPresentationFields } from '../src/previewPresentation.ts';
import { previewSourceMatchesArchitecture } from '../src/previewInterop.ts';
import type { Architecture, CanvasDocument } from '../src/core/types.ts';
import type { PreviewVisualEdge } from '../src/previewPresentation.ts';

function fixture() {
  const architecture: Architecture = { schemaVersion: 1, id: 'model', label: 'Model', entry: 'model:Model', sourceDigest: 'source', irDigest: 'ir', diagnostics: [], sources: [{ path: 'model.py', content: 'class Model: pass\n', digest: 'file' }],
    nodes: ['a', 'b'].map(id => ({ id, label: id, kind: 'Linear', category: 'linear', children: [], parameters: {}, ports: [], evidence: 'source' })),
    edges: [{ id: 'formal', source: { nodeId: 'a', portId: 'out' }, target: { nodeId: 'b', portId: 'in' }, tensorId: 'value', role: 'data' }] };
  const document: CanvasDocument = { schemaVersion: 1, id: 'canvas', title: 'Model', revision: 4, sourceBindingDigest: 'source', architecture,
    displayAliases: {}, nodeStyleOverrides: {}, edgeStyleOverrides: { formal: { stroke: '#123456', dashed: true } },
    pinnedObjects: [], legendItems: [{ id: 'old', label: 'old', color: '#abcdef', glyph: 'module' }], annotations: [],
    pageSpec: { widthMm: 180, background: '#ffffff', preset: 'paper' }, layout: {}, layoutByFrontier: {}, expandedIds: [] };
  const graph = { nodes: [{ id: 'a', x: 0, y: 0 }, { id: 'b', x: 100, y: 0 }],
    edges: [{ id: 'preview', source: 'a', target: 'b' }] as PreviewVisualEdge[] };
  return { document, graph };
}

test('same-source formal visual changes sync atomically into the authoritative preview overlay', () => {
  const { document, graph } = fixture(), source = { schema: 'archcanvas-preview-source/1' as const, caseId: 'preview-case', entry: 'model:Model', files: { 'model.py': 'class Model: pass\n' } };
  assert.equal(previewSourceMatchesArchitecture(source, document.architecture), true);
  const edited = { ...document, title: 'Edited Model', displayAliases: { a: 'Input projection' }, nodeStyleOverrides: { a: { fill: '#ffe0e0' } },
    edgeStyleOverrides: { formal: { stroke: '#123456', width: 4, dashed: true } }, legendItems: [], annotations: [], pageSpec: { ...document.pageSpec, preset: 'monochrome' as const } };
  const operations = previewDocumentSyncOperations(document, edited, graph, source);
  assert.equal(operations[0].type, 'syncPresentation');
  assert.deepEqual((operations[0] as { nodes: Record<string, unknown> }).nodes.a, { alias: 'Input projection', fill: '#ffe0e0', pinned: false });
  assert.deepEqual((operations[0] as { edges: Record<string, unknown> }).edges.preview, { stroke: '#123456', width: 4, dashed: true });
  assert.equal((operations[0] as { title: string }).title, 'Edited Model');
  assert.throws(() => previewDocumentSyncOperations(document, edited, graph, { ...source, files: { 'model.py': 'class Other: pass\n' } }), /源码字节不同/);
});

test('visual draft and reconnected edges cannot select or style a formal relation sharing their endpoints', () => {
  const { document, graph } = fixture(), draft = { id: 'draft', source: 'a', target: 'b', draft: true };
  assert.deepEqual(previewFormalEdgeIds(document.architecture, graph.edges[0], graph), ['formal']);
  assert.deepEqual(previewFormalEdgeIds(document.architecture, draft, graph), []);
  assert.deepEqual(previewFormalEdgeIds(document.architecture, { ...draft, draft: false, binding: { evidence: 'visual edit draft; no source model writeback' } }, graph), []);
  const before = JSON.stringify(document.architecture);
  const fields = previewPresentationFields(document, { ...graph, edges: [draft], studioPresentation: { edges: { draft: { stroke: '#ff0000' } } } });
  assert.deepEqual(fields.edgeStyleOverrides, {}); assert.equal(JSON.stringify(document.architecture), before);
  document.architecture.edges.push({ ...document.architecture.edges[0], id: 'parallel' });
  assert.deepEqual(previewFormalEdgeIds(document.architecture, graph.edges[0], graph), [], 'parallel operands require explicit binding');
  assert.deepEqual(previewFormalEdgeIds(document.architecture, { ...graph.edges[0], binding: { semantic_edges: ['parallel'] } }, graph), ['parallel']);
});

test('presentation snapshots reset edge styles and legends on undo without changing source topology', () => {
  const { document, graph } = fixture(), before = JSON.stringify(document.architecture);
  const edited = previewPresentationFields(document, { ...graph, studioPresentation: { edges: { preview: { stroke: '#abcdef', width: 3, dashed: true } },
    legend: [{ id: 'new', label: 'Linear', color: '#abcdef', glyph: 'module' }], nodes: { a: { alias: 'Dense', pinned: true } } } });
  assert.deepEqual(edited.edgeStyleOverrides, { formal: { stroke: '#abcdef', width: 3, dashed: true } });
  assert.deepEqual(edited.pinnedObjects, ['a']); assert.equal(edited.legendItems[0].id, 'new');
  const undone = previewPresentationFields({ ...document, ...edited }, graph);
  assert.deepEqual(undone.edgeStyleOverrides, {}); assert.deepEqual(undone.legendItems, []); assert.deepEqual(undone.displayAliases, {});
  assert.deepEqual(undone.pinnedObjects, []); assert.equal(JSON.stringify(document.architecture), before);
});

test('recursive presentation wins over stale root overlay and projected edges retain original style', () => {
  const { document, graph } = fixture(), projected = { id: 'projected', source: 'collapsed-a', target: 'collapsed-b', projection: { original: 'preview' } };
  const recursive = { ...graph, edges: [projected], studioPresentation: { edges: { projected: { stroke: '#ff0000' } } },
    recursive: { authority: { detail: graph }, state: { studioPresentation: { edges: { preview: { stroke: '#00ff00', width: 3.5, dashed: true } }, page: { preset: 'monochrome' } } } } };
  assert.deepEqual(previewFormalEdgeIds(document.architecture, projected, recursive), ['formal']);
  assert.deepEqual(previewPresentationFields(document, recursive).edgeStyleOverrides, { formal: { stroke: '#00ff00', width: 3.5, dashed: true } });
  assert.deepEqual(previewEdgeAppearance(recursive, projected), { stroke: '#4b5563', width: 3.5, dashed: true });
  recursive.recursive.state.studioPresentation.page.preset = 'paper';
  assert.equal(previewEdgeAppearance(recursive, projected).stroke, '#00ff00');
});
