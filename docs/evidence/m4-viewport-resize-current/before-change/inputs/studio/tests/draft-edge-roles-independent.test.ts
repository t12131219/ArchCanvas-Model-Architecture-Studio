import test from 'node:test';
import assert from 'node:assert/strict';
import { draftEdgeRoles } from '../src/draftEdgeRoles.ts';
import type { AuthoredDraft, DraftCatalog, DraftEdge, DraftModule, DraftNode } from '../src/authoring.ts';

// Handwritten graph/port contracts. Expected roles never call a product graph,
// reachability, geometry, preset, parser, or generation helper. Only the direct
// Add input from a strict ancestor producer is a structural residual branch.
type Role = 'data' | 'residual';
type Expected = Record<string, Role>;
const unary = ['Linear', 'ReLU', 'GELU', 'Identity'];
function module(kind: string): DraftModule {
  const inputs = kind === 'Input' ? [] : kind === 'Add' ? ['left', 'right'] : kind === 'Concat' ? ['a', 'b'] : ['input'];
  const outputs = kind === 'Output' ? [] : ['output'];
  return { kind, label: kind, category: 'independent-contract', description: '', defaults: {}, parameters: [],
    ports: [...inputs.map(id => ({ id, name: id, direction: 'in' as const, type: 'tensor' as const })),
      ...outputs.map(id => ({ id, name: id, direction: 'out' as const, type: 'tensor' as const }))] };
}
const catalog: DraftCatalog = { schemaVersion: 1, mode: 'authored-draft', unsupported: [],
  modules: ['Input', 'Output', ...unary, 'Add', 'Concat'].map(module) };
function node(id: string, kind: string): DraftNode {
  return { id, kind, label: `unrelated label ${id}`, parameters: {}, position: { x: 0, y: 0 } };
}
function edge(id: string, from: string, to: string, port = 'input'): DraftEdge {
  return { id, source: { nodeId: from, portId: 'output' }, target: { nodeId: to, portId: port } };
}
function draft(nodes: DraftNode[], edges: DraftEdge[]): AuthoredDraft {
  return { schemaVersion: 1, mode: 'authored-draft', id: 'draft-independent-edge-roles', title: 'Not a semantic hint',
    revision: 7, nodes, edges };
}
function skip(right = true): AuthoredDraft {
  return draft([node('x', 'Input'), node('h', 'Identity'), node('sum', 'Add'), node('out', 'Output')],
    [edge('trunk', 'x', 'h'), edge('main', 'h', 'sum', right ? 'left' : 'right'),
      edge('skip', 'x', 'sum', right ? 'right' : 'left'), edge('exit', 'sum', 'out')]);
}
const skipExpected: Expected = { trunk: 'data', main: 'data', skip: 'residual', exit: 'data' };
const ordinaryExpected: Expected = { trunk: 'data', main: 'data', skip: 'data', exit: 'data' };
function freeze(value: unknown): void {
  if (value && typeof value === 'object') { Object.freeze(value); Object.values(value).forEach(freeze); }
}
function expectRoles(value: AuthoredDraft, expected: Expected, modules: DraftCatalog = catalog): void {
  const draftBytes = JSON.stringify(value), catalogBytes = JSON.stringify(modules);
  freeze(value); freeze(modules);
  const roles = draftEdgeRoles(value, modules);
  assert.ok(roles instanceof Map, 'role projection returns a standard Map');
  assert.deepEqual([...roles.entries()].sort(([a], [b]) => a.localeCompare(b)),
    Object.entries(expected).sort(([a], [b]) => a.localeCompare(b)), 'all and only handwritten edge IDs and roles');
  assert.deepEqual([...draftEdgeRoles(value, modules).entries()], [...roles.entries()], 'repeat calls are deterministic');
  assert.equal(JSON.stringify(value), draftBytes, 'projection preserves all draft bytes, including positions/revision/labels/bindings');
  assert.equal(JSON.stringify(modules), catalogBytes, 'projection preserves every catalog contract byte');
}

test('a right Add input from a strict ancestor is the only residual edge', () => {
  expectRoles(skip(), skipExpected);
});

test('Add left/right order is symmetric; branch age is proved by bindings', () => {
  expectRoles(skip(false), skipExpected);
});

test('transitive ancestry marks the direct skip, never any trunk edge or Add output', () => {
  const value = draft([node('x', 'Input'), node('a', 'Linear'), node('b', 'ReLU'), node('c', 'Linear'), node('sum', 'Add'), node('out', 'Output')],
    [edge('x-a', 'x', 'a'), edge('a-b', 'a', 'b'), edge('b-c', 'b', 'c'), edge('main', 'c', 'sum', 'left'),
      edge('skip', 'x', 'sum', 'right'), edge('exit', 'sum', 'out')]);
  expectRoles(value, { 'x-a': 'data', 'a-b': 'data', 'b-c': 'data', main: 'data', skip: 'residual', exit: 'data' });
});

test('nested Adds retain distinct local skip roles without styling all ancestors', () => {
  const value = draft([node('x', 'Input'), node('h', 'Identity'), node('sum', 'Add'), node('g', 'GELU'), node('sum2', 'Add'), node('out', 'Output')],
    [edge('trunk', 'x', 'h'), edge('main1', 'h', 'sum', 'left'), edge('skip1', 'x', 'sum', 'right'),
      edge('to-g', 'sum', 'g'), edge('main2', 'g', 'sum2', 'right'), edge('skip2', 'sum', 'sum2', 'left'), edge('exit', 'sum2', 'out')]);
  expectRoles(value, { trunk: 'data', main1: 'data', skip1: 'residual', 'to-g': 'data', main2: 'data', skip2: 'residual', exit: 'data' });
});

test('two independent producers remain ordinary even when labels say residual', () => {
  const value = draft([node('x', 'Input'), node('y', 'Input'), node('sum', 'Add'), node('out', 'Output')],
    [edge('left', 'x', 'sum', 'left'), edge('right', 'y', 'sum', 'right'), edge('exit', 'sum', 'out')]);
  value.nodes.forEach(item => { item.label = 'residual skip memory 残差'; });
  expectRoles(value, { left: 'data', right: 'data', exit: 'data' });
});

test('a shared ancestor does not make either sibling input residual', () => {
  const value = draft([node('x', 'Input'), node('a', 'Identity'), node('b', 'ReLU'), node('sum', 'Add'), node('out', 'Output')],
    [edge('x-a', 'x', 'a'), edge('x-b', 'x', 'b'), edge('left', 'a', 'sum', 'left'), edge('right', 'b', 'sum', 'right'), edge('exit', 'sum', 'out')]);
  expectRoles(value, { 'x-a': 'data', 'x-b': 'data', left: 'data', right: 'data', exit: 'data' });
});

test('the same tensor producer bound to both Add slots is x+x, not a skip', () => {
  const value = draft([node('x', 'Input'), node('sum', 'Add'), node('out', 'Output')],
    [edge('left', 'x', 'sum', 'left'), edge('right', 'x', 'sum', 'right'), edge('exit', 'sum', 'out')]);
  expectRoles(value, { left: 'data', right: 'data', exit: 'data' });
});

test('Concat stays ordinary even when its first producer is an ancestor of the second', () => {
  const value = draft([node('x', 'Input'), node('h', 'Identity'), node('cat', 'Concat'), node('out', 'Output')],
    [edge('trunk', 'x', 'h'), edge('a', 'x', 'cat', 'a'), edge('b', 'h', 'cat', 'b'), edge('exit', 'cat', 'out')]);
  expectRoles(value, { trunk: 'data', a: 'data', b: 'data', exit: 'data' });
});

test('ancestry through a registered merge is structural, not a unary-only heuristic', () => {
  const value = draft([node('x', 'Input'), node('y', 'Input'), node('cat', 'Concat'), node('sum', 'Add'), node('out', 'Output')],
    [edge('x-cat', 'x', 'cat', 'a'), edge('y-cat', 'y', 'cat', 'b'), edge('main', 'cat', 'sum', 'left'),
      edge('skip', 'x', 'sum', 'right'), edge('exit', 'sum', 'out')]);
  // This is a role projection only. It does not claim that the declared shapes
  // of a specific Concat result and x would pass the separate Add validator.
  expectRoles(value, { 'x-cat': 'data', 'y-cat': 'data', main: 'data', skip: 'residual', exit: 'data' });
});

test('rename, geometry, and node/edge array order cannot manufacture or remove a role', () => {
  const variants: AuthoredDraft[] = [];
  for (const [dx, dy] of [[-64, 0], [64, 0], [0, -64], [0, 64]]) {
    const value = skip(); value.nodes[1].position = { x: dx, y: dy }; variants.push(value);
  }
  const renamed = skip(); renamed.title = '普通数据流'; renamed.nodes.forEach(item => { item.label = '无残差'; }); variants.push(renamed);
  const reordered = skip(); reordered.nodes.reverse(); reordered.edges.reverse(); variants.push(reordered);
  for (const value of variants) expectRoles(value, skipExpected);
});

test('a missing Add input has no complete pair from which to infer a residual role', () => {
  const value = skip(); value.edges = value.edges.filter(item => item.id !== 'main');
  expectRoles(value, { trunk: 'data', skip: 'data', exit: 'data' });
});

test('ambiguous or invalid Add bindings stay ordinary without throwing', () => {
  const duplicate = skip(); duplicate.nodes.push(node('other', 'Input')); duplicate.edges.push(edge('duplicate', 'other', 'sum', 'right'));
  expectRoles(duplicate, { ...ordinaryExpected, duplicate: 'data' });
  const badPort = skip(); badPort.edges[1].target.portId = 'a'; expectRoles(badPort, ordinaryExpected);
  const extraPort = skip(); extraPort.edges.push(edge('extra', 'x', 'sum', 'extra')); expectRoles(extraPort, { ...ordinaryExpected, extra: 'data' });
});

test('missing producers and incorrect source/output direction cannot prove ancestry', () => {
  const missing = skip(); missing.edges[0].source.nodeId = 'absent'; expectRoles(missing, ordinaryExpected);
  const badSource = skip(); badSource.edges[0].source.portId = 'input'; expectRoles(badSource, ordinaryExpected);
  const outputProducer = skip(); outputProducer.nodes[0].kind = 'Output'; expectRoles(outputProducer, ordinaryExpected);
});

test('opaque, unknown, and removed catalog contracts do not imply a known path', () => {
  for (const kind of ['Opaque', 'FutureAttention']) {
    const value = skip(); value.nodes[1].kind = kind; value.nodes[1].label = 'Identity residual skip'; expectRoles(value, ordinaryExpected);
  }
  const reduced = structuredClone(catalog); reduced.modules = reduced.modules.filter(item => item.kind !== 'Identity');
  expectRoles(skip(), ordinaryExpected, reduced);
});

test('catalog direction and tensor-type contradictions disable affected role inference', () => {
  const reversed = structuredClone(catalog); reversed.modules.find(item => item.kind === 'Identity')!.ports.find(item => item.id === 'input')!.direction = 'out';
  expectRoles(skip(), ordinaryExpected, reversed);
  const nonTensor = structuredClone(catalog);
  // Malformed external catalog data must not be trusted merely because its
  // static TypeScript consumer normally calls this field a tensor.
  (nonTensor.modules.find(item => item.kind === 'Identity')!.ports[0] as { type: string }).type = 'control';
  expectRoles(skip(), ordinaryExpected, nonTensor);
});

test('a directed cycle in the relevant component cannot create a strict-ancestor proof', () => {
  const value = draft([node('a', 'Identity'), node('b', 'Identity'), node('sum', 'Add'), node('out', 'Output')],
    [edge('a-b', 'a', 'b'), edge('b-a', 'b', 'a'), edge('left', 'a', 'sum', 'left'), edge('right', 'b', 'sum', 'right'), edge('exit', 'sum', 'out')]);
  expectRoles(value, { 'a-b': 'data', 'b-a': 'data', left: 'data', right: 'data', exit: 'data' });
});

test('unrelated unknown and cyclic components do not alter an independently known skip', () => {
  const value = skip(); value.nodes.push(node('u', 'Opaque'), node('v', 'Identity'), node('a', 'Identity'), node('b', 'Identity'));
  value.edges.push(edge('unknown', 'u', 'v'), edge('a-b', 'a', 'b'), edge('b-a', 'b', 'a'));
  expectRoles(value, { ...skipExpected, unknown: 'data', 'a-b': 'data', 'b-a': 'data' });
});

test('parallel known components keep their local roles and ordinary branches', () => {
  const value = skip(); value.nodes.push(node('x2', 'Input'), node('h2', 'Identity'), node('sum2', 'Add'), node('out2', 'Output'));
  value.edges.push(edge('trunk2', 'x2', 'h2'), edge('main2', 'h2', 'sum2', 'right'), edge('skip2', 'x2', 'sum2', 'left'), edge('exit2', 'sum2', 'out2'));
  expectRoles(value, { ...skipExpected, trunk2: 'data', main2: 'data', skip2: 'residual', exit2: 'data' });
});
