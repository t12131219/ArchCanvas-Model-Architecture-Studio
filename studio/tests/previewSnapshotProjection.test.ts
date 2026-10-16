import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHistory, reduceHistory, validateDocument } from '../src/core/index.ts';
import { previewMappingSignature, previewPanelDocument, projectPreviewHistory } from '../src/previewPanelDocument.ts';
import type { PreviewVisualGraph } from '../src/previewInterop.ts';

function transformer() {
  const base = new URL('../public/preview/data/cases/', import.meta.url);
  const overview = JSON.parse(readFileSync(new URL('01093cc06a87b35a-overview.json', base), 'utf8'));
  const detail = JSON.parse(readFileSync(new URL('01093cc06a87b35a-detailed.json', base), 'utf8'));
  overview.recursive = { authority: { detail } };
  const children = new Set(detail.nodes.map((node: { parent?: string }) => node.parent));
  const expanded = structuredClone(detail);
  for (const node of expanded.nodes) node.expanded = children.has(node.id);
  expanded.recursive = { authority: { detail } };
  return { overview, detail, expanded };
}

test('actual Transformer snapshot projects its completed layout once without formal expansion displacement or source copies', () => {
  const { overview, detail, expanded } = transformer();
  const before = createHistory(previewPanelDocument({ caseId: 'transformer', graph: overview }));
  const baseline = JSON.stringify(before);
  const next = projectPreviewHistory(before, expanded);
  assert.equal(next.document.architecture, before.document.architecture, 'source architecture is immutable and shared');
  assert.equal(next.past.length, 1); assert.equal(next.past[0], before.document);
  assert.equal(next.document.revision, before.document.revision + 1);
  assert.equal(JSON.stringify(before), baseline, 'the entire original history remains untouched');
  assert.doesNotThrow(() => validateDocument(next.document));
  const positions = new Map<string, { x: number; y: number }>(detail.nodes.map((node: any) => [node.id, node]));
  for (const node of expanded.nodes) {
    const parent = node.parent ? positions.get(node.parent) : undefined;
    assert.deepEqual(next.document.layout[node.id], { x: node.x - (parent?.x ?? 0), y: node.y - (parent?.y ?? 0) }, node.id);
    const canonical = next.document.architecture.nodes.find(item => item.id === node.id)!;
    if (canonical.children.length) assert.equal(next.document.expandedIds.includes(node.id), node.expanded);
  }
  assert.equal(projectPreviewHistory(next, structuredClone(expanded)), next, 'repeated busy/tool/selection state has no document/history revision');
  const undo = reduceHistory(next, { type: 'undo' });
  assert.deepEqual(undo.document.layout, before.document.layout);
  assert.deepEqual(undo.document.expandedIds, before.document.expandedIds);
  const redo = reduceHistory(undo, { type: 'redo' });
  assert.deepEqual(redo.document.layout, next.document.layout);
  assert.deepEqual(redo.document.expandedIds, next.document.expandedIds);
});

test('a preview-pinned child follows an authoritative parent movement and snapshot paint failures are atomic', () => {
  const graph = { nodes: [{ id: 'root', x: 10, y: 20, expanded: true }, { id: 'child', parent: 'root', x: 30, y: 60 }], edges: [] };
  const history = createHistory(previewPanelDocument({ caseId: 'pin', graph }));
  const pinned = { ...graph, studioPresentation: { nodes: { child: { pinned: true } } } };
  const current = projectPreviewHistory(history, pinned);
  const moved = structuredClone(pinned); moved.nodes[0].x += 100; moved.nodes[1].x += 100;
  const next = projectPreviewHistory(current, moved);
  assert.equal(next.document.layout.root.x, 110);
  assert.equal(next.document.layout.child.x, 20);
  assert.deepEqual(next.document.pinnedObjects, ['child']);
  const baseline = JSON.stringify(next);
  const malformed = structuredClone(moved); (malformed.studioPresentation.nodes.child as any).fill = 'invalid-color';
  assert.throws(() => projectPreviewHistory(next, malformed), /hexadecimal color/);
  assert.equal(JSON.stringify(next), baseline);
});

test('coverage fingerprints ignore layout and visual labels while invalidating source identity evidence changes', () => {
  const { expanded } = transformer(), snapshot = { graph: expanded };
  const before = previewMappingSignature(snapshot), moved = structuredClone(expanded);
  moved.nodes[0].x += 12; moved.nodes[0].label = 'Display alias';
  moved.recursive.authority.detail.nodes[0].x += 8;
  assert.equal(previewMappingSignature({ graph: moved }), before);
  const node = moved.recursive.authority.detail.nodes[0];
  const semantic = node.semantic ?? node;
  (semantic as any).sourceStructure = true;
  (semantic as any).sourceParameters = { callSites: [{ path: 'model.py', line: 3, endLine: 3, expression: 'self.cell(x)' }] };
  const called = previewMappingSignature({ graph: moved });
  assert.notEqual(called, before);
  (semantic as any).sourceParameters.callSites[0].line = 4;
  assert.notEqual(previewMappingSignature({ graph: moved }), called, 'call evidence invalidates the binding cache');
  if (node.semantic) node.semantic.source_evidence = ['another-source-span']; else node.source_evidence = ['another-source-span'];
  assert.notEqual(previewMappingSignature({ graph: moved }), before);
});
