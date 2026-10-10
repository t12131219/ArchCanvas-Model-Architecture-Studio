import test from 'node:test';
import assert from 'node:assert/strict';
import { addDraftNode, changeDraft, connectDraft, draftHistory, parseDraftCache, removeDraftNode } from '../src/authoring.ts';
import type { AuthoredDraft, DraftCatalog, DraftModule } from '../src/authoring.ts';

// Literal fixtures and boundaries come from the published draft/cache limits,
// not imported product constants. A wide input collector makes the edge limit
// reachable without violating the separate 1200-node limit or producer rules.
const input: DraftModule = {
  kind: 'Input', label: '输入', category: 'input', description: 'Independent input fixture',
  defaults: { shape: [1, 8] }, parameters: [], ports: [{ id: 'output', name: 'output', direction: 'out', type: 'tensor' }],
};
const collector: DraftModule = {
  kind: 'Collector', label: '汇合', category: 'merge', description: 'Independent wide collector fixture', defaults: {}, parameters: [],
  ports: Array.from({ length: 3601 }, (_, i) => ({ id: `input-${i}`, name: `input-${i}`, direction: 'in', type: 'tensor' })),
};
const catalog: DraftCatalog = { schemaVersion: 1, mode: 'authored-draft', modules: [input, collector], unsupported: [] };

function empty(id: string): AuthoredDraft {
  return { schemaVersion: 1, mode: 'authored-draft', id, title: '独立边界验收', revision: 7, nodes: [], edges: [] };
}
function nodes(count: number): AuthoredDraft {
  return { ...empty('draft-node-boundary'), nodes: Array.from({ length: count }, (_, i) => ({
    id: `node-${i}`, kind: 'Input', label: '输入', parameters: { shape: [1, 8] }, position: { x: i * 10, y: 0 },
  })) };
}
function edges(count: number): AuthoredDraft {
  return { ...empty('draft-edge-boundary'), nodes: [
    { id: 'source', kind: 'Input', label: '输入', parameters: { shape: [1, 8] }, position: { x: 0, y: 0 } },
    { id: 'target', kind: 'Collector', label: '汇合', parameters: {}, position: { x: 280, y: 0 } },
  ], edges: Array.from({ length: count }, (_, i) => ({
    id: `edge-${i}`, source: { nodeId: 'source', portId: 'output' }, target: { nodeId: 'target', portId: `input-${i}` },
  })) };
}
function appendEdge(draft: AuthoredDraft, index: number) {
  connectDraft(draft, catalog, { nodeId: 'source', portId: 'output' }, { nodeId: 'target', portId: `input-${index}` }, `edge-${index}`);
}
function assertCacheable(draft: AuthoredDraft) {
  const loaded = parseDraftCache({ draft, storageRevision: 3, savedRevision: draft.revision });
  assert.ok(loaded, 'accepted boundary must survive draft cache parsing');
  assert.deepEqual(loaded.draft, draft);
}

test('1200th node is accepted and cacheable; 1201th fails before any byte changes', () => {
  const draft = nodes(1199);
  addDraftNode(draft, input, 'node-1199', { x: 11990, y: 0 });
  assert.equal(draft.nodes.length, 1200);
  assertCacheable(draft);
  const bytes = JSON.stringify(draft);
  assert.throws(() => addDraftNode(draft, input, 'node-1200', { x: 12000, y: 0 }), /1200/);
  assert.equal(JSON.stringify(draft), bytes);
});

test('3600th connection is accepted and cacheable; 3601th fails before any byte changes', () => {
  const draft = edges(3599);
  appendEdge(draft, 3599);
  assert.equal(draft.nodes.length, 2, 'edge capacity is separate from node capacity');
  assert.equal(draft.edges.length, 3600);
  assertCacheable(draft);
  const bytes = JSON.stringify(draft);
  assert.throws(() => appendEdge(draft, 3600), /3600/);
  assert.equal(JSON.stringify(draft), bytes);
});

test('deleting a module or connection releases capacity for another edit', () => {
  const nodeDraft = nodes(1200);
  removeDraftNode(nodeDraft, 'node-0');
  addDraftNode(nodeDraft, input, 'replacement-node', { x: -100, y: 0 });
  assert.equal(nodeDraft.nodes.length, 1200);
  assert.ok(nodeDraft.nodes.some(node => node.id === 'replacement-node'));
  assertCacheable(nodeDraft);

  const edgeDraft = edges(3600);
  edgeDraft.edges = edgeDraft.edges.filter(edge => edge.id !== 'edge-0');
  appendEdge(edgeDraft, 3600);
  assert.equal(edgeDraft.edges.length, 3600);
  assert.ok(edgeDraft.edges.some(edge => edge.id === 'edge-3600'));
  assertCacheable(edgeDraft);
});

test('failed limit edits preserve history, revision, past and redo bytes', () => {
  for (const [draft, edit, limit] of [
    [nodes(1200), (next: AuthoredDraft) => addDraftNode(next, input, 'overflow', { x: 0, y: 0 }), /1200/],
    [edges(3600), (next: AuthoredDraft) => appendEdge(next, 3600), /3600/],
  ] as const) {
    const history = draftHistory(draft);
    history.past = [{ ...structuredClone(draft), revision: 6, title: '过去状态' }];
    history.future = [{ ...structuredClone(draft), revision: 8, title: '重做状态' }];
    const bytes = JSON.stringify(history);
    let result = history;
    assert.throws(() => { result = changeDraft(history, edit); }, limit);
    assert.equal(result, history, 'failed update must not publish a new history value');
    assert.equal(result.draft.revision, 7);
    assert.equal(JSON.stringify(history), bytes);
  }
});
