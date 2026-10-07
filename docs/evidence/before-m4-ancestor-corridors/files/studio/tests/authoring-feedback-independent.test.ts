import test from 'node:test';
import assert from 'node:assert/strict';
import { arrangeDraft, blankDraft } from '../src/authoring.ts';
import type { AuthoredDraft, DraftCatalog, DraftNode, DraftParameter } from '../src/authoring.ts';
import { fitDraftCamera, parseDraftField, resolveDraftFeedback } from '../src/authoringFeedback.ts';
import { ApiError, api, request } from '../src/api.ts';

// Hand-authored user scenes and registry. No snapshot of the fit/feedback
// implementation supplies expected geometry, targets or text here.
const catalog: DraftCatalog = { schemaVersion: 1, mode: 'authored-draft', unsupported: [], modules: [
  { kind: 'Input', label: '输入', category: 'io', description: '输入', defaults: { shape: [1, 16], dtype: 'float32' }, parameters: [
    { name: 'shape', type: 'integer-array', default: [1, 16] }, { name: 'dtype', type: 'choice', default: 'float32', options: ['float32', 'int64'] },
  ], ports: [{ id: 'output', name: '输出', direction: 'out', type: 'tensor' }] },
  { kind: 'Linear', label: '全连接', category: 'dense', description: '投影', defaults: { in_features: 16, out_features: 32, bias: true }, parameters: [
    { name: 'in_features', type: 'integer', default: 16 }, { name: 'out_features', type: 'integer', default: 32 }, { name: 'bias', type: 'boolean', default: true },
  ], ports: [{ id: 'input', name: '输入', direction: 'in', type: 'tensor' }, { id: 'output', name: '输出', direction: 'out', type: 'tensor' }] },
  { kind: 'Add', label: '相加', category: 'merge', description: '两路相加', defaults: {}, parameters: [], ports: [
    { id: 'left', name: '左', direction: 'in', type: 'tensor' }, { id: 'right', name: '右', direction: 'in', type: 'tensor' }, { id: 'output', name: '输出', direction: 'out', type: 'tensor' },
  ] },
  { kind: 'Output', label: '输出', category: 'io', description: '输出', defaults: {}, parameters: [], ports: [{ id: 'input', name: '输入', direction: 'in', type: 'tensor' }] },
] };
function node(id: string, kind: string, x: number, y: number, label = '重复显示名'): DraftNode {
  return { id, kind, label, parameters: structuredClone(catalog.modules.find(item => item.kind === kind)!.defaults), position: { x, y } };
}
function branch(): AuthoredDraft {
  const draft = blankDraft('draft-independent-feedback');
  draft.nodes = [node('exit', 'Output', 8_000, -900), node('projection-b', 'Linear', -640, 930), node('merge', 'Add', 40, -50), node('entry', 'Input', -950, -770), node('projection-a', 'Linear', 950, 280)];
  draft.edges = [
    { id: 'entry-a', source: { nodeId: 'entry', portId: 'output' }, target: { nodeId: 'projection-a', portId: 'input' } },
    { id: 'entry-b', source: { nodeId: 'entry', portId: 'output' }, target: { nodeId: 'projection-b', portId: 'input' } },
    { id: 'a-merge', source: { nodeId: 'projection-a', portId: 'output' }, target: { nodeId: 'merge', portId: 'left' } },
    { id: 'b-merge', source: { nodeId: 'projection-b', portId: 'output' }, target: { nodeId: 'merge', portId: 'right' } },
    { id: 'merge-exit', source: { nodeId: 'merge', portId: 'output' }, target: { nodeId: 'exit', portId: 'input' } },
  ];
  return draft;
}
function screenBoxes(draft: AuthoredDraft, width: number, height: number) {
  const before = JSON.stringify(draft), camera = fitDraftCamera(draft, { width, height });
  assert.equal(JSON.stringify(draft), before, 'fitting cannot mutate a model or its layout/history revision');
  assert.ok(Number.isFinite(camera.x) && Number.isFinite(camera.y) && Number.isFinite(camera.zoom) && camera.zoom > 0 && camera.zoom <= 1);
  for (const box of draft.nodes) {
    // These are the UI's actual declared module rectangles, independently
    // projected at all four corners instead of repeating a fit formula.
    for (const [x, y] of [[box.position.x, box.position.y], [box.position.x + 176, box.position.y], [box.position.x, box.position.y + 100], [box.position.x + 176, box.position.y + 100]]) {
      const sx = x * camera.zoom + camera.x, sy = y * camera.zoom + camera.y;
      assert.ok(sx >= -1e-7 && sx <= width + 1e-7, `${box.id} horizontal corner ${sx} lies outside ${width}`);
      assert.ok(sy >= -1e-7 && sy <= height + 1e-7, `${box.id} vertical corner ${sy} lies outside ${height}`);
    }
  }
  return camera;
}

test('independent from-zero chain arrangement can fit its previously offscreen output with all module boxes visible', () => {
  const draft = blankDraft('draft-output-visible');
  draft.nodes = [node('out', 'Output', -700, -100), node('second', 'Linear', 500, 820), node('first', 'Linear', 20, 50), node('input', 'Input', 2_000, 4_000)];
  draft.edges = [
    { id: 'one', source: { nodeId: 'input', portId: 'output' }, target: { nodeId: 'first', portId: 'input' } },
    { id: 'two', source: { nodeId: 'first', portId: 'output' }, target: { nodeId: 'second', portId: 'input' } },
    { id: 'three', source: { nodeId: 'second', portId: 'output' }, target: { nodeId: 'out', portId: 'input' } },
  ];
  const facts = draft.nodes.map(({ position: _position, ...fact }) => fact), bindings = structuredClone(draft.edges);
  arrangeDraft(draft);
  assert.deepEqual(draft.nodes.map(({ position: _position, ...fact }) => fact), facts); assert.deepEqual(draft.edges, bindings);
  assert.equal(draft.nodes.find(item => item.id === 'out')!.position.x, 794, 'output is fourth rank, beyond the novice viewport');
  screenBoxes(draft, 630, 440);
});

test('independent fit handles negative manual placements, merge branches, aspect ratios and the full128module contract', () => {
  const manual = branch();
  for (const [width, height] of [[630, 440], [350, 650], [1_024, 300], [96, 64]]) screenBoxes(manual, width, height);
  const arranged = branch(), prior = JSON.stringify(arranged.edges); arrangeDraft(arranged); assert.equal(JSON.stringify(arranged.edges), prior);
  for (const [width, height] of [[630, 440], [350, 650]]) screenBoxes(arranged, width, height);
  const chain = blankDraft('draft-wide128');
  for (let i = 127; i >= 0; i--) chain.nodes.push(node(`module-${i}`, i === 0 ? 'Input' : i === 127 ? 'Output' : 'Linear', -800 + i, -900));
  for (let i = 1; i < 128; i++) chain.edges.push({ id: `link-${i}`, source: { nodeId: `module-${i - 1}`, portId: 'output' }, target: { nodeId: `module-${i}`, portId: 'input' } });
  arrangeDraft(chain); assert.equal(chain.nodes.find(item => item.id === 'module-127')!.position.x, 31_546);
  assert.ok(screenBoxes(chain, 630, 440).zoom < .15, 'fit must not preserve the manual zoom floor and strand a valid long draft');
});

test('empty and unmeasured viewports return finite camera state and keep the blank draft intact', () => {
  const draft = blankDraft('draft-empty-fit'), before = JSON.stringify(draft);
  for (const viewport of [{ width: 630, height: 440 }, { width: 0, height: 0 }, { width: NaN, height: Infinity }, { width: -10, height: 50 }]) {
    const camera = fitDraftCamera(draft, viewport);
    assert.ok([camera.x, camera.y, camera.zoom].every(Number.isFinite)); assert.ok(camera.zoom > 0);
  }
  assert.equal(JSON.stringify(draft), before);
});

test('manual off-body route waypoints fit along with node rectangles without changing either model or route', () => {
  const draft = branch(), points = [{ x: -1_750, y: -2_050 }, { x: 9_400, y: -2_050 }, { x: 9_400, y: 2_650 }];
  const before = JSON.stringify({ draft, points });
  for (const [width, height] of [[630, 440], [320, 800]]) {
    const camera = fitDraftCamera(draft, { width, height }, points);
    const all = [...points, ...draft.nodes.flatMap(item => [{ x: item.position.x, y: item.position.y }, { x: item.position.x + 176, y: item.position.y + 100 }])];
    for (const point of all) {
      const sx = point.x * camera.zoom + camera.x, sy = point.y * camera.zoom + camera.y;
      assert.ok(sx >= 0 && sx <= width && sy >= 0 && sy <= height, 'the complete manually declared visible scene must fit');
    }
  }
  assert.equal(JSON.stringify({ draft, points }), before);
});

test('raw numerical field input rejects empty tokens, invalid dimensions, nonfinite values and out-of-contract lengths', () => {
  const features: DraftParameter = { name: 'in_features', type: 'integer', default: 16, min: 1, max: 512 };
  for (const text of ['', ' ', '0', '-1', '513', '3.5', 'Infinity', '-Infinity', 'NaN', '1e309', '16,32']) assert.equal(parseDraftField(text, features), null, `reject invalid feature count ${JSON.stringify(text)}`);
  assert.equal(parseDraftField(' 512 ', features), 512);
  assert.equal(parseDraftField('32', features), 32, 'a corrected value is the value committed, without falling back to the default16');
  const probability: DraftParameter = { name: 'p', type: 'number', default: .5, min: 0, max: 1 };
  for (const text of ['-.01', '1.01', 'Infinity', 'NaN', '']) assert.equal(parseDraftField(text, probability), null);
  assert.equal(parseDraftField('0', probability), 0); assert.equal(parseDraftField('0.25', probability), .25); assert.equal(parseDraftField('1', probability), 1);
  const shape: DraftParameter = { name: 'shape', type: 'integer-array', default: [1, 16], length: 2, min: 1, max: 4096 };
  for (const text of ['', ',', '1,', ',16', '1,,16', '1, ,16', '16', '1,16,32', '1,0', '1,-16', '1,4097', '1,2.5', '1,Infinity', '1,NaN', '1,1e309']) assert.equal(parseDraftField(text, shape), null, `reject malformed tensor shape ${JSON.stringify(text)}`);
  assert.deepEqual(parseDraftField(' 2 , 4096 ', shape), [2, 4096]);
  assert.deepEqual(parseDraftField('1,32', shape), [1, 32], 'the corrected final shape replaces the previous valid shape');
  const axes: DraftParameter = { name: 'axes', type: 'integer-array', default: [0], minLength: 1, maxLength: 3, min: 0, max: 7 };
  for (const text of ['', '0,1,2,3', '0,8']) assert.equal(parseDraftField(text, axes), null);
  assert.deepEqual(parseDraftField('0', axes), [0]); assert.deepEqual(parseDraftField('0,3,7', axes), [0, 3, 7]);
});

const diagnostic = { code: 'linear-input-dimension', message: '输入最后一维为32，与全连接模块要求的16不同。请修改输入维度。', technical: 'final dimension32 does not equal in_features16.', nodeId: 'projection-b', parameter: 'in_features', portId: 'input' };
test('duplicate display labels never redirect a typed shape diagnostic to another module or infer a target from text', () => {
  const draft = branch(), before = JSON.stringify(draft), feedback = resolveDraftFeedback(new ApiError('English transport error', 400, [diagnostic]), draft, catalog);
  assert.equal(feedback.message, diagnostic.message); assert.equal(feedback.technical, diagnostic.technical);
  assert.equal(feedback.target?.nodeId, 'projection-b'); assert.equal(feedback.target?.parameter, 'in_features'); assert.equal(feedback.target?.portId, 'input');
  const noStructured = resolveDraftFeedback(new Error('重复显示名: final input dimension32 does not equal in_features16.'), draft, catalog);
  assert.equal(noStructured.target, undefined, 'even a recognisable message is not a stable target');
  assert.equal(JSON.stringify(draft), before); assert.equal(draft.nodes.filter(item => item.label === '重复显示名').length, 5);
});

test('unknown node identities and unregistered parameter/port names cannot produce an active field highlight', () => {
  const draft = branch();
  const foreign = resolveDraftFeedback(new ApiError('error', 400, [{ ...diagnostic, nodeId: 'missing', message: '重复显示名不匹配' }]), draft, catalog);
  assert.equal(foreign.target, undefined);
  for (const parameter of ['kernel_size', '__proto__', 'constructor', '', 9, null]) {
    const value = resolveDraftFeedback(new ApiError('error', 400, [{ ...diagnostic, parameter }]), draft, catalog);
    assert.notEqual(value.target?.parameter, parameter, `unregistered ${String(parameter)} must not become a field target`);
    if (value.target) assert.equal(value.target.nodeId, 'projection-b');
  }
  for (const portId of ['foreign', '__proto__', 9]) {
    const value = resolveDraftFeedback(new ApiError('error', 400, [{ ...diagnostic, portId }]), draft, catalog);
    assert.equal(value.target?.portId, undefined);
  }
  const unregisteredKind = structuredClone(draft); unregisteredKind.nodes[1].kind = 'ExternalUnknown';
  assert.equal(resolveDraftFeedback(new ApiError('error', 400, [diagnostic]), unregisteredKind, catalog).target?.parameter, undefined);
});

test('unstructuredHTTP conflicts and malformed diagnostics keep useful message without fabricated node or field targets', () => {
  const draft = branch();
  for (const payload of [undefined, null, false, {}, ['not a diagnostic'], [{ nodeId: 'projection-b', parameter: 'in_features' }], [{ ...diagnostic, message: 9 }], [{ ...diagnostic, nodeId: ['projection-b'] }]]) {
    const feedback = resolveDraftFeedback(new ApiError('storage conflict', 409, payload), draft, catalog);
    assert.equal(feedback.target, undefined); assert.ok(typeof feedback.message === 'string' && feedback.message.length > 0);
  }
  assert.equal(resolveDraftFeedback(new ApiError('storage conflict', 409), draft, catalog).target, undefined);
});

test('public JSON transport preserves structured diagnostics and HTTP status without changing legacy successful payloads', async () => {
  const realFetch = globalThis.fetch, payload = { error: 'dimension mismatch', diagnostics: [diagnostic] };
  globalThis.fetch = async () => Response.json(payload, { status: 400 });
  try {
    let caught: unknown;
    try { await request('/authoring/validate', { method: 'POST', body: '{}' }); } catch (reason) { caught = reason; }
    assert.ok(caught instanceof ApiError); assert.equal(caught.status, 400);
    assert.equal(resolveDraftFeedback(caught, branch(), catalog).target?.nodeId, 'projection-b');
    globalThis.fetch = async () => Response.json({ error: 'storage conflict', revision: 2 }, { status: 409 });
    await assert.rejects(request('/authoring/drafts/draft-independent-feedback'), (reason: unknown) => reason instanceof ApiError && reason.status === 409 && reason.message.includes('storage conflict'));
    globalThis.fetch = async () => Response.json({ sentinel: ['untouched', 42] });
    assert.deepEqual(await request('/authoring/catalog'), { sentinel: ['untouched', 42] });
    assert.equal(JSON.stringify(payload.diagnostics), JSON.stringify([diagnostic]));
  } finally { globalThis.fetch = realFetch; }
});

test('deferred old-draft response cannot resolve a missing identity in a replacement draft with the same labels', async () => {
  const realFetch = globalThis.fetch, snapshot = branch(), current = branch();
  current.id = 'draft-replacement'; current.nodes[1].id = 'fresh-projection'; current.edges = [];
  const original = JSON.stringify(current); let release!: () => void;
  const wait = new Promise<void>(resolve => { release = resolve; });
  globalThis.fetch = async input => {
    if (String(input) === '/api/session') return Response.json({ token: 'feedback-test-token' });
    await wait; return Response.json({ error: 'dimension mismatch', diagnostics: [diagnostic] }, { status: 400 });
  };
  try {
    const pending = api.validateDraft(snapshot); release(); let reason: unknown;
    try { await pending; } catch (error) { reason = error; }
    const feedback = resolveDraftFeedback(reason, current, catalog);
    assert.equal(feedback.target, undefined, 'stale missing ID cannot select the similarly named new projection');
    assert.equal(JSON.stringify(current), original); assert.equal(snapshot.id, 'draft-independent-feedback');
  } finally { globalThis.fetch = realFetch; }
});
