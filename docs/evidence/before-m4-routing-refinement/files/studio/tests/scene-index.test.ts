import test from 'node:test';
import assert from 'node:assert/strict';
import { applyVisualBatch, buildScene, createDocument, createHistory, reduceHistory, renderSvg } from '../src/core/index.ts';
import type { Architecture, ArchitectureNode } from '../src/core/index.ts';

function architecture(): Architecture {
  const node = (id: string, category: string, parentId?: string, children: string[] = []): ArchitectureNode => ({
    id, label: id, kind: category, category, parentId, children, parameters: {}, evidence: 'source',
    ports: [{ id: 'in', name: 'input', direction: 'in', role: 'data', ordinal: 0 }, { id: 'out', name: 'output', direction: 'out', role: 'data', ordinal: 0 }],
  });
  return { schemaVersion: 1, id: 'indices', label: 'Port coverage oracle', entry: 'model:Oracle', sourceDigest: 'source', irDigest: 'ir', sources: [], diagnostics: [],
    nodes: [node('model', 'container', undefined, ['input', 'block', 'output']), node('input', 'input', 'model'), node('block', 'container', 'model', ['norm', 'linear']), node('norm', 'norm', 'block'), node('linear', 'linear', 'block'), node('output', 'output', 'model')],
    edges: [
      { id: 'first', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'norm', portId: 'in' }, tensorId: 'same', role: 'data' },
      { id: 'middle', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'norm', portId: 'in' }, tensorId: 'other', role: 'data' },
      { id: 'last', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'norm', portId: 'in' }, tensorId: 'same', role: 'data' },
      { id: 'residual', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'linear', portId: 'in' }, tensorId: 'same', role: 'residual' },
      { id: 'exit', source: { nodeId: 'linear', portId: 'out' }, target: { nodeId: 'output', portId: 'in' }, tensorId: 'output', role: 'data' },
    ] };
}

test('indexed projected ports retain non-adjacent canonical coverage and role order', () => {
  const scene = buildScene(createDocument(architecture()));
  assert.deepEqual(scene.edges[0].canonicalEdgeIds, ['first', 'last']);
  const input = scene.nodes.find(node => node.id === 'input')!;
  const port = input.ports.find(item => item.id === 'input:out:data')!;
  assert.deepEqual(port.canonicalEdgeIds, ['first', 'last', 'middle']);
  assert.deepEqual(port.canonicalBindings, Array.from({ length: 3 }, () => ({ nodeId: 'input', portId: 'out' })));
  const block = scene.nodes.find(node => node.id === 'block')!;
  assert.deepEqual(block.ports.filter(item => item.direction === 'in').map(item => [item.canonicalNodeId, item.role, item.proxy]), [['norm', 'data', true], ['linear', 'data', true]]);
  assert.equal(block.ports[0].x, block.x + block.width / 3);
  assert.equal(block.ports[1].x, block.x + block.width * 2 / 3);
});

test('parallel style groups and cycle fallback survive expand/undo/redo without mutating source', () => {
  const a = architecture();
  a.edges.push({ id: 'internal', source: { nodeId: 'norm', portId: 'out' }, target: { nodeId: 'linear', portId: 'in' }, tensorId: 'internal', role: 'data' });
  a.edges.push({ id: 'cycle', source: { nodeId: 'linear', portId: 'out' }, target: { nodeId: 'norm', portId: 'in' }, tensorId: 'cycle', role: 'data' });
  const source = JSON.stringify(a);
  const d = applyVisualBatch(createDocument(a), [{ type: 'edgeStyle', id: 'last', style: { width: 3 } }]);
  const before = renderSvg(buildScene(d));
  let history = createHistory(d);
  history = reduceHistory(history, { type: 'apply', operations: [{ type: 'expand', id: 'block', expanded: true }] });
  const expanded = buildScene(history.document);
  assert.equal(expanded.nodes.find(node => node.id === 'linear')!.y - expanded.nodes.find(node => node.id === 'norm')!.y, 100);
  assert.deepEqual(new Set(expanded.edges.flatMap(edge => edge.canonicalEdgeIds)), new Set(a.edges.map(edge => edge.id)));
  const sceneBeforeUndo = expanded;
  history = reduceHistory(history, { type: 'undo' });
  assert.equal(renderSvg({ ...buildScene(history.document), revision: d.revision }), before);
  history = reduceHistory(history, { type: 'redo' });
  assert.deepEqual({ ...buildScene(history.document), revision: sceneBeforeUndo.revision }, sceneBeforeUndo);
  assert.equal(JSON.stringify(a), source);
});
