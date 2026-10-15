import test from 'node:test';
import assert from 'node:assert/strict';
import type { Architecture, ArchitectureNode } from '../src/core/types.ts';
import { createDocument, effectiveVisibleFrontier } from '../src/core/document.ts';
import { projectSourceEditing, sourceEditingDocument } from '../src/sourceEditingProjection.ts';

function inspectionTree(size: number): Architecture {
  const root: ArchitectureNode = { id: 'root', label: 'Unknown model', kind: 'Module', category: 'container', children: ['region'], ports: [], parameters: {}, evidence: 'source' };
  const region: ArchitectureNode = { id: 'region', label: 'Configuration branch', kind: 'ConditionalRegion', category: 'opaque', parentId: 'root', children: ['body'], ports: [], parameters: {}, evidence: 'opaque' };
  const nodes: ArchitectureNode[] = [root, region];
  for (let index = 0; index < size; index++) nodes.push({
    id: index ? `body-${index}` : 'body', label: `Source definition ${index}`, kind: 'SourceModule', category: 'container',
    parentId: index ? 'body' : 'region', children: index ? [] : Array.from({ length: size - 1 }, (_, at) => `body-${at + 1}`),
    ports: [], parameters: index === 1 ? { sourceType: 'Linear', construction: 'nn.Linear(4, 3)' } : {}, evidence: 'source', sourceStructure: true,
    source: { path: 'unknown.py', line: index + 1, endLine: index + 1, expression: `source_${index}` },
  });
  return { schemaVersion: 1, id: 'architecture:unknown.Tree', label: 'UnknownTree', entry: 'unknown:Tree', sourceDigest: 'a'.repeat(64), irDigest: 'b'.repeat(64),
    nodes, edges: [], diagnostics: [], sources: [{ path: 'unknown.py', content: 'source', digest: 'c'.repeat(64) }] };
}

test('large unresolved editor starts with bounded inspection cards and retains every source fact', () => {
  const view = createDocument(inspectionTree(160));
  const before = JSON.stringify(view);
  const editing = projectSourceEditing(view);
  assert.equal(JSON.stringify(view), before);
  assert.deepEqual(editing.document.architecture, view.architecture);
  assert.deepEqual(new Set(editing.document.expandedIds), new Set(['root', 'region']));
  assert.equal(editing.scene.nodes.length, 3);
  assert.equal(editing.scene.nodes.find(node => node.id === 'body')?.expandable, true);
  assert.equal(editing.scene.nodes.find(node => node.id === 'body')?.expanded, false);
  assert.equal(editing.document.architecture.nodes.find(node => node.id === 'body-1')?.parameters.construction, 'nn.Linear(4, 3)');
  assert.equal(effectiveVisibleFrontier(editing.document).visibleIds.size, 3);
});

test('explicit inspection expansion survives re-entry without changing the source view or hidden facts', () => {
  const view = createDocument(inspectionTree(160));
  const editing = sourceEditingDocument(view);
  editing.expandedIds.push('body');
  const reopened = sourceEditingDocument(editing);
  assert.ok(reopened.expandedIds.includes('body'));
  assert.equal(effectiveVisibleFrontier(reopened).visibleIds.size, 162);
  assert.equal(view.expandedIds.includes('body'), false);
  assert.deepEqual(reopened.architecture, view.architecture);
});

test('small inspection examples and fully proven compositions retain recursive editable primitives', () => {
  const small = sourceEditingDocument(createDocument(inspectionTree(6)));
  assert.ok(small.expandedIds.includes('body'));
  const proven = inspectionTree(160);
  for (const node of proven.nodes) { delete node.sourceStructure; node.kind = 'Module'; node.evidence = 'source'; }
  const editing = sourceEditingDocument(createDocument(proven));
  assert.ok(editing.expandedIds.includes('body'));
  assert.equal(effectiveVisibleFrontier(editing).visibleIds.size, 162);
});
