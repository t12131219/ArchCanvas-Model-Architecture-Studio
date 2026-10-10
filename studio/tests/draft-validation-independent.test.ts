import test from 'node:test';
import assert from 'node:assert/strict';
import type { AuthoredDraft } from '../src/authoring.ts';
import { draftTensorLabel, draftValidationKey, readDraftValidation } from '../src/draftValidation.ts';

// The declared widths and response facts below are handwritten from the
// backend's static contract. No product helper supplies expected dimensions,
// inferred completeness, target identities, or key contents for these cases.
function graph(): AuthoredDraft {
  return { schemaVersion: 1, mode: 'authored-draft', id: 'draft-shape-contract', title: '独立声明检查', revision: 7,
    nodes: [
      { id: 'input', kind: 'Input', label: '相同显示名', parameters: { shape: [2, 4], dtype: 'float32' }, position: { x: 20, y: 40 } },
      { id: 'projection', kind: 'Linear', label: '相同显示名', parameters: { in_features: 4, out_features: 3, bias: true }, position: { x: 280, y: 40 } },
      { id: 'output', kind: 'Output', label: '相同显示名', parameters: {}, position: { x: 540, y: 40 } },
    ], edges: [
      { id: 'input-projection', source: { nodeId: 'input', portId: 'output' }, target: { nodeId: 'projection', portId: 'input' } },
      { id: 'projection-output', source: { nodeId: 'projection', portId: 'output' }, target: { nodeId: 'output', portId: 'input' } },
    ] };
}
function response() {
  return { draft: graph(), draftDigest: 'c'.repeat(64), complete: true, issues: [] as Record<string, unknown>[],
    tensors: { input: { shape: [2, 4], dtype: 'float32' }, projection: { shape: [2, 3], dtype: 'float32' }, output: { shape: [2, 3], dtype: 'float32' } } as Record<string, { shape: number[]; dtype: string }>,
    order: ['input', 'projection', 'output'], verification: 'static-declared-tensors; no model execution' };
}
function partial() {
  const result = response(); result.complete = false; result.draft.edges.pop();
  result.issues = [{ code: 'unbound-input', message: 'Output 的输入端口 input 尚未连接，请连接上游模块。', technical: '相同显示名: connect input.', nodeId: 'output', portIds: ['input'], portId: 'input' },
    { code: 'unused-node', message: '这些模块尚未通向命名输出。', technical: 'Every module must contribute to a named Output before generating Python.', nodeIds: ['input', 'projection'] }];
  delete result.tensors.output;
  // Stable topological order follows initial queue (input, disconnected output),
  // then projection, whose only producer is input.
  result.order = ['input', 'output', 'projection']; return result;
}
function rejected(value: unknown) { assert.throws(() => readDraftValidation(value), /检查响应格式/); }

test('equal revision and labels never allow one draft identity or node identity/kind/set to inherit another draft check', () => {
  const initial = graph(), key = draftValidationKey(initial);
  const mutations: ((draft: AuthoredDraft) => void)[] = [
    draft => { draft.id = 'draft-another'; }, draft => { draft.nodes[1].id = 'other-projection'; },
    draft => { draft.nodes[1].kind = 'Identity'; }, draft => { draft.nodes.pop(); },
    draft => { draft.nodes.push({ id: 'extra', kind: 'Identity', label: '相同显示名', parameters: {}, position: { x: 1, y: 1 } }); },
  ];
  for (const mutate of mutations) {
    const next = structuredClone(initial); mutate(next);
    assert.equal(next.revision, initial.revision); assert.notEqual(draftValidationKey(next), key);
  }
});

test('parameters, array contents and every binding identity/endpoint invalidate checked shapes even before a revision increment', () => {
  const initial = graph(), key = draftValidationKey(initial);
  const mutations: ((draft: AuthoredDraft) => void)[] = [
    draft => { draft.nodes[1].parameters.out_features = 6; }, draft => { draft.nodes[1].parameters.bias = false; },
    draft => { draft.nodes[0].parameters.shape = [3, 4]; }, draft => { draft.nodes[0].parameters.dtype = 'float64'; },
    draft => { draft.edges[0].id = 'replacement-binding'; }, draft => { draft.edges[0].source.nodeId = 'projection'; },
    draft => { draft.edges[0].source.portId = 'another-output'; }, draft => { draft.edges[0].target.nodeId = 'output'; },
    draft => { draft.edges[0].target.portId = 'another-input'; }, draft => { draft.edges.pop(); },
    draft => { draft.edges.push({ id: 'extra', source: { nodeId: 'input', portId: 'output' }, target: { nodeId: 'output', portId: 'input' } }); },
  ];
  for (const mutate of mutations) { const next = structuredClone(initial); mutate(next); assert.notEqual(draftValidationKey(next), key); }
  assert.throws(() => draftValidationKey({ ...initial, nodes: [{ ...initial.nodes[0], parameters: { shape: [NaN] } }] }), /检查响应格式/, 'nonfinite values must not alias JSON null');
});

test('four-direction placement, display aliases, title and revision retain the same checked static graph without mutation', () => {
  const initial = graph(), key = draftValidationKey(initial), bytes = JSON.stringify(initial);
  for (const [dx, dy] of [[16, 0], [-16, 0], [0, 16], [0, -16]]) {
    const next = structuredClone(initial); next.nodes[1].position.x += dx; next.nodes[1].position.y += dy;
    next.nodes[1].label = '用户自定义投影'; next.title = '用户自定义名称'; next.revision = 9;
    assert.equal(draftValidationKey(next), key);
  }
  assert.equal(JSON.stringify(initial), bytes);
  const read = readDraftValidation(response());
  assert.equal(draftValidationKey(read.draft), key);
  assert.equal(draftTensorLabel(read.tensors.projection), '声明 float32 · 2×3');
});

test('parameter field order is irrelevant while graph-array order remains significant for backend topological/output ordering', () => {
  const first = graph(), key = draftValidationKey(first), second = graph();
  second.nodes[0].parameters = { dtype: 'float32', shape: [2, 4] };
  second.nodes[1].parameters = { bias: true, out_features: 3, in_features: 4 };
  assert.equal(draftValidationKey(second), key);
  second.nodes.reverse(); assert.notEqual(draftValidationKey(second), key);
  second.nodes.reverse(); second.edges.reverse(); assert.notEqual(draftValidationKey(second), key);
  const fields = JSON.parse(key);
  assert.deepEqual(Object.keys(fields), ['allowUnusedNodes', 'schemaVersion', 'mode', 'id', 'nodes', 'edges']);
  assert.deepEqual(Object.keys(fields.nodes[1]), ['id', 'kind', 'parameters']);
  const retained = { ...first, allowUnusedNodes: true };
  assert.notEqual(draftValidationKey(retained), key, 'retention changes require a fresh check');
  assert.equal(draftValidationKey({ ...first, allowUnusedNodes: false }), key);
});

test('complete static response preserves tensor declarations and identities while isolating them from mutable response data', () => {
  const raw = response(), bytes = JSON.stringify(raw), result = readDraftValidation(raw);
  assert.equal(result.complete, true); assert.deepEqual(result.issues, []); assert.equal(result.verification, 'static-declared-tensors; no model execution');
  assert.deepEqual(result.tensors, { input: { shape: [2, 4], dtype: 'float32' }, projection: { shape: [2, 3], dtype: 'float32' }, output: { shape: [2, 3], dtype: 'float32' } });
  assert.deepEqual(result.order, ['input', 'projection', 'output']); assert.equal(JSON.stringify(raw), bytes);
  raw.tensors.projection.shape[1] = 999; raw.draft.nodes[0].parameters.shape = [9, 9];
  assert.deepEqual(result.tensors.projection.shape, [2, 3]); assert.deepEqual(result.draft.nodes[0].parameters.shape, [2, 4]);
});

test('an incomplete graph may retain upstream declared tensors, but never reports complete or invents a missing downstream shape', () => {
  const result = readDraftValidation(partial());
  assert.equal(result.complete, false); assert.deepEqual(Object.keys(result.tensors).sort(), ['input', 'projection']);
  assert.equal(result.tensors.output, undefined); assert.equal(draftTensorLabel(result.tensors.projection), '声明 float32 · 2×3');
  assert.deepEqual(result.issues[0], { code: 'unbound-input', message: 'Output 的输入端口 input 尚未连接，请连接上游模块。', technical: '相同显示名: connect input.', nodeId: 'output', portIds: ['input'], portId: 'input' });
  const two = partial(); two.draft.nodes[1] = { ...two.draft.nodes[1], kind: 'Add', parameters: {} }; two.draft.edges = [];
  two.order = ['input', 'projection', 'output']; delete two.tensors.projection;
  two.issues[0] = { code: 'unbound-input', message: 'Add 的输入端口 left, right 尚未连接。', technical: '相同显示名: connect left, right.', nodeId: 'projection', portIds: ['left', 'right'] };
  const multi = readDraftValidation(two).issues[0]; assert.deepEqual(multi.portIds, ['left', 'right']); assert.equal(multi.portId, undefined, 'a two-port problem has no fabricated single blame target');
});

test('execution claims, generated-source receipts and inconsistent complete/issue or missing-tensor claims are rejected', () => {
  for (const verification of ['runtime-verified', 'static-declared-tensors; no model import or execution', { status: 'passed', modelExecution: 'not_run' }, null, true]) rejected({ ...response(), verification });
  rejected({ ...response(), source: 'import torch' }); rejected({ ...response(), draftDigest: 'not-a-digest' });
  const incomplete = partial(); incomplete.complete = true; rejected(incomplete);
  const complete = response(); complete.complete = false; rejected(complete);
  const missing = response(); delete missing.tensors.output; rejected(missing);
  rejected({ ...response(), complete: 'true' }); rejected({ ...response(), tensors: null });
});

test('malformed tensor shapes, dtype, extra runtime flags and oversized declarations cannot reach a displayed shape label', () => {
  for (const shape of [[], [0, 4], [-2, 4], [2.5, 4], [2, '4'], [2, null], [NaN], [Infinity], Array(9).fill(1), [1_000_000, 1_001], [Number.MAX_SAFE_INTEGER + 1]]) {
    rejected({ ...response(), tensors: { ...response().tensors, projection: { shape, dtype: 'float32' } } });
  }
  for (const dtype of ['float16', 'tensor', 32, null]) rejected({ ...response(), tensors: { ...response().tensors, projection: { shape: [2, 3], dtype } } });
  rejected({ ...response(), tensors: { ...response().tensors, projection: { shape: [2, 3], dtype: 'float32', runtimeVerified: true } } });
  assert.equal(draftTensorLabel({ shape: [1_000_000_000], dtype: 'float32' }), '声明 float32 · 1000000000', 'an inferred Flatten dimension may exceed the input-axis limit while meeting the total-element budget');
  assert.equal(draftTensorLabel({ shape: [1, 7], dtype: 'int64' }), '声明 int64 · 1×7');
});

test('unregistered tensor/node references, repeated or nontopological order and malformed diagnostics are rejected without target inference', () => {
  rejected({ ...response(), tensors: { ...response().tensors, foreign: { shape: [2, 3], dtype: 'float32' } } });
  for (const order of [['input', 'projection'], ['input', 'projection', 'projection'], ['input', 'projection', 'foreign'], ['projection', 'input', 'output']]) rejected({ ...response(), order });
  for (const issue of [null, 'wrong', { code: 'unbound-input', message: 5 }, { code: 'unbound-input', message: '相同显示名', nodeId: 'foreign' },
    { code: 'unbound-input', message: '未连接', nodeId: ['output'] }, { code: 'unbound-input', message: '未连接', portIds: ['input', 'input'] },
    { code: 'unbound-input', message: '未连接', endpoint: 'left' }]) rejected({ ...partial(), issues: [issue] });
  const duplicate = response(); duplicate.draft.nodes[1].id = 'input'; rejected(duplicate);
  const malformed = response(); malformed.draft.nodes[0].position.x = Infinity; rejected(malformed);
  for (const value of [null, false, [], {}, new Date()]) rejected(value);
});
