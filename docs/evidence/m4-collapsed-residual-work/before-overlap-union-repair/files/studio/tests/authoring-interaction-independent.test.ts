import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { addDraftNode, arrangeDraft, blankDraft, changeDraft, connectDraft, draftHistory, draftRoutes, nextDraftPosition, parseDraftCache, portPoint, removeDraftNode, travelDraft } from '../src/authoring.ts';
import type { AuthoredDraft, DraftCatalog, DraftEndpoint, DraftModule } from '../src/authoring.ts';
import { api } from '../src/api.ts';
import { beginCameraPan, cameraAtPanInput } from '../src/cameraGesture.ts';

// The real formal catalog is data, obtained without importing/executing a model.
// Expected graph and geometry facts below are hand-authored, not product snapshots.
const project = fileURLToPath(new URL('../../', import.meta.url));
const catalogResult = await promisify(execFile)(`${project}.venv/bin/python`, ['-I', '-S', '-B', '-c',
  'import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_authoring import module_catalog;print(json.dumps(module_catalog()))', project], { encoding: 'utf8' });
const catalog = JSON.parse(catalogResult.stdout) as DraftCatalog;
function module(kind: string): DraftModule { const value = catalog.modules.find(item => item.kind === kind); assert.ok(value, kind); return value; }
function endpoint(nodeId: string, portId: string): DraftEndpoint { return { nodeId, portId }; }
function chain(): AuthoredDraft {
  const draft = blankDraft('draft-ab12');
  for (const [id, kind, x] of [['input', 'Input', 50], ['linear', 'Linear', 320], ['relu', 'ReLU', 590], ['output', 'Output', 860]] as const) addDraftNode(draft, module(kind), id, { x, y: 80 });
  connectDraft(draft, catalog, endpoint('input', 'output'), endpoint('linear', 'input'), 'in-linear');
  connectDraft(draft, catalog, endpoint('linear', 'output'), endpoint('relu', 'input'), 'linear-relu');
  connectDraft(draft, catalog, endpoint('relu', 'output'), endpoint('output', 'input'), 'relu-out');
  return draft;
}
type Point = [number, number];
function pathPoints(path: string): Point[] {
  const tokens = path.match(/[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?/g) ?? [];
  const points: Point[] = []; let x = 0, y = 0;
  for (let i = 0; i < tokens.length;) {
    const command = tokens[i++];
    if (command === 'M' || command === 'L') { x = +tokens[i++]; y = +tokens[i++]; }
    else if (command === 'H') x = +tokens[i++]; else if (command === 'V') y = +tokens[i++]; else throw new Error(command);
    assert.ok(Number.isFinite(x) && Number.isFinite(y)); points.push([x, y]);
  }
  return points;
}
function bodyHit(a: Point, b: Point, node: AuthoredDraft['nodes'][number]): boolean {
  const left = node.position.x + .02, right = node.position.x + 176 - .02, top = node.position.y + .02, bottom = node.position.y + 100 - .02;
  if (a[0] === b[0]) return a[0] > left && a[0] < right && Math.max(Math.min(a[1], b[1]), top) < Math.min(Math.max(a[1], b[1]), bottom);
  assert.equal(a[1], b[1], 'route must be orthogonal');
  return a[1] > top && a[1] < bottom && Math.max(Math.min(a[0], b[0]), left) < Math.min(Math.max(a[0], b[0]), right);
}
function assertRoutes(draft: AuthoredDraft, expectClear = true) {
  const original = JSON.stringify(draft), geometry = draftRoutes(draft, catalog);
  assert.equal(geometry.routes.length, draft.edges.length, 'one route for every authored binding');
  for (const edge of draft.edges) {
    const route = geometry.routes.find(item => item.id === edge.id)!;
    const points = pathPoints(route.path), source = draft.nodes.find(node => node.id === edge.source.nodeId)!, target = draft.nodes.find(node => node.id === edge.target.nodeId)!;
    const a = portPoint(source, module(source.kind), edge.source.portId), b = portPoint(target, module(target.kind), edge.target.portId);
    assert.ok(Math.hypot(points[0][0] - a.x, points[0][1] - a.y) <= .02);
    assert.ok(Math.hypot(points.at(-1)![0] - b.x, points.at(-1)![1] - b.y) <= .02);
    const hits = draft.nodes.filter(node => points.slice(1).some((point, index) => bodyHit(points[index], point, node))).map(node => node.id);
    if (expectClear) { assert.deepEqual(hits, [], edge.id); assert.deepEqual(route.blockedBy, [], edge.id); }
    else for (const id of hits) assert.ok(route.blockedBy.includes(id), `unreported ${edge.id} crossing ${id}`);
  }
  assert.equal(JSON.stringify(draft), original, 'routing must not edit model/history');
  return geometry;
}

test('independent four-direction authored moves preserve exact graph and one-command undo/redo', () => {
  const initial = chain(), original = JSON.stringify(initial);
  const expectedBindings = [
    ['input', 'output', 'linear', 'input'], ['linear', 'output', 'relu', 'input'], ['relu', 'output', 'output', 'input'],
  ];
  assert.deepEqual(initial.edges.map(edge => [edge.source.nodeId, edge.source.portId, edge.target.nodeId, edge.target.portId]), expectedBindings);
  for (const [dx, dy] of [[-32, 0], [32, 0], [0, -32], [0, 32], [-220, 0], [220, 0], [0, -180], [0, 180]]) {
    const history = draftHistory(initial), bytes = JSON.stringify(history);
    const moved = changeDraft(history, draft => { const node = draft.nodes.find(item => item.id === 'linear')!; node.position.x += dx; node.position.y += dy; });
    assert.equal(JSON.stringify(history), bytes); assert.equal(moved.past.length, 1); assert.equal(moved.draft.revision, 1);
    assert.deepEqual(moved.draft.edges, initial.edges); assert.deepEqual(moved.draft.nodes.map(({ position, ...node }) => node), initial.nodes.map(({ position, ...node }) => node));
    assert.deepEqual(moved.draft.nodes.find(node => node.id === 'linear')!.position, { x: 320 + dx, y: 80 + dy });
    for (const id of ['input', 'relu', 'output']) assert.deepEqual(moved.draft.nodes.find(node => node.id === id), initial.nodes.find(node => node.id === id));
    // Large horizontal moves intentionally cover an adjacent module. Their
    // anchors must survive and remaining conflicts must be explicit.
    const geometry = assertRoutes(moved.draft, Math.abs(dx) !== 220);
    if (Math.abs(dx) === 220) assert.ok(geometry.overlaps.length > 0);
    const undone = travelDraft(moved, 'undo'), redone = travelDraft(undone, 'redo');
    assert.equal(undone.draft.revision, 2); assert.equal(redone.draft.revision, 3);
    assert.deepEqual(undone.draft.nodes, initial.nodes); assert.deepEqual(redone.draft.nodes, moved.draft.nodes);
    assert.deepEqual(draftRoutes(redone.draft, catalog), draftRoutes(moved.draft, catalog));
  }
  assert.equal(JSON.stringify(initial), original);
});

test('merge ports stay distinct, fan-out is retained, malformed direction/foreign port and duplicate producers fail atomically', () => {
  let history = draftHistory(blankDraft('draft-ab13'));
  history = changeDraft(history, draft => {
    addDraftNode(draft, module('Input'), 'a', { x: 50, y: 50 }); addDraftNode(draft, module('Input'), 'b', { x: 50, y: 260 });
    addDraftNode(draft, module('Add'), 'merge', { x: 370, y: 140 }); addDraftNode(draft, module('Output'), 'out', { x: 690, y: 140 });
    connectDraft(draft, catalog, endpoint('a', 'output'), endpoint('merge', 'left'), 'left');
    connectDraft(draft, catalog, endpoint('b', 'output'), endpoint('merge', 'right'), 'right');
    connectDraft(draft, catalog, endpoint('merge', 'output'), endpoint('out', 'input'), 'exit');
  });
  const geometry = assertRoutes(history.draft), merge = history.draft.nodes.find(node => node.id === 'merge')!;
  assert.notDeepEqual(portPoint(merge, module('Add'), 'left'), portPoint(merge, module('Add'), 'right'));
  assert.equal(geometry.routes.length, 3);
  for (const [source, target] of [
    [endpoint('a', 'missing'), endpoint('merge', 'left')], [endpoint('merge', 'left'), endpoint('a', 'output')],
    [endpoint('a', 'output'), endpoint('merge', 'right')], [endpoint('missing', 'output'), endpoint('merge', 'left')],
  ]) {
    const before = JSON.stringify(history);
    assert.throws(() => changeDraft(history, draft => connectDraft(draft, catalog, source, target, 'invalid')));
    assert.equal(JSON.stringify(history), before);
  }
  const fork = changeDraft(history, draft => { addDraftNode(draft, module('Identity'), 'identity', { x: 370, y: 380 }); connectDraft(draft, catalog, endpoint('a', 'output'), endpoint('identity', 'input'), 'fan-out'); });
  assert.equal(fork.draft.edges.filter(edge => edge.source.nodeId === 'a').length, 2);
  assert.ok(fork.draft.edges.some(edge => edge.id === 'left')); assertRoutes(fork.draft);
});

test('a new binding that closes a directed cycle leaves history and every prior edge unchanged', () => {
  const draft = blankDraft('draft-ab14');
  for (const [i, kind] of ['Identity', 'ReLU', 'GELU'].entries()) addDraftNode(draft, module(kind), `n${i}`, { x: i * 270, y: 100 });
  connectDraft(draft, catalog, endpoint('n0', 'output'), endpoint('n1', 'input'), 'first');
  connectDraft(draft, catalog, endpoint('n1', 'output'), endpoint('n2', 'input'), 'second');
  const history = draftHistory(draft), bytes = JSON.stringify(history);
  assert.throws(() => changeDraft(history, value => connectDraft(value, catalog, endpoint('n2', 'output'), endpoint('n0', 'input'), 'cycle')), /循环/);
  assert.equal(JSON.stringify(history), bytes); assert.equal(history.past.length, 0); assert.equal(history.draft.edges.length, 2);
});

test('deleting a branch removes only its incident bindings and undo restores both merge ports', () => {
  const draft = chain();
  addDraftNode(draft, module('Identity'), 'branch', { x: 590, y: 280 });
  connectDraft(draft, catalog, endpoint('linear', 'output'), endpoint('branch', 'input'), 'branch-edge');
  const history = draftHistory(draft), removed = changeDraft(history, value => removeDraftNode(value, 'branch'));
  assert.deepEqual(removed.draft.edges.map(edge => edge.id), ['in-linear', 'linear-relu', 'relu-out']);
  assert.deepEqual(removed.draft.nodes.map(node => node.id), ['input', 'linear', 'relu', 'output']);
  assert.deepEqual(travelDraft(removed, 'undo').draft.nodes, draft.nodes); assert.deepEqual(travelDraft(removed, 'undo').draft.edges, draft.edges);
  assertRoutes(removed.draft);
});

test('explicit DAG arrange handles merge longest-path dependencies without overlaps or semantic changes', () => {
  const draft = blankDraft('draft-ab15');
  // Deliberately insert a downstream node first; authored array order is not a topological oracle.
  for (const [id, kind] of [['out', 'Output'], ['merge', 'Add'], ['slow', 'ReLU'], ['fast', 'Identity'], ['input', 'Input']] as const) addDraftNode(draft, module(kind), id, { x: -100, y: -100 });
  for (const [id, source, target, port] of [['to-slow', 'input', 'slow', 'input'], ['to-fast', 'input', 'fast', 'input'], ['left', 'slow', 'merge', 'left'], ['right', 'fast', 'merge', 'right'], ['exit', 'merge', 'out', 'input']] as const) connectDraft(draft, catalog, endpoint(source, 'output'), endpoint(target, port), id);
  const before = JSON.stringify(draft), arranged = changeDraft(draftHistory(draft), value => arrangeDraft(value));
  assert.equal(JSON.stringify(draft), before); assert.deepEqual(arranged.draft.edges, draft.edges);
  const byId = new Map(arranged.draft.nodes.map(node => [node.id, node]));
  for (const edge of draft.edges) assert.ok(byId.get(edge.target.nodeId)!.position.x > byId.get(edge.source.nodeId)!.position.x + 176);
  assert.deepEqual(draftRoutes(arranged.draft, catalog).overlaps, []); assertRoutes(arranged.draft);
  assert.deepEqual(travelDraft(arranged, 'undo').draft.nodes, draft.nodes);
});

test('manual covering overlaps keep anchors and report every retained routing obstruction', () => {
  const draft = chain();
  addDraftNode(draft, module('Identity'), 'cover', { x: 480, y: 80 });
  const original = JSON.stringify(draft), geometry = assertRoutes(draft, false);
  assert.ok(geometry.overlaps.some(pair => [pair.first, pair.second].includes('cover')));
  assert.ok(geometry.routes.some(route => route.blockedBy.includes('cover')));
  assert.equal(JSON.stringify(draft), original);
});

test('no-op changes and unavailable history travel preserve identity; a new edit after undo clears redo', () => {
  const initial = draftHistory(chain());
  assert.equal(changeDraft(initial, () => {}), initial); assert.equal(travelDraft(initial, 'undo'), initial); assert.equal(travelDraft(initial, 'redo'), initial);
  const first = changeDraft(initial, draft => { draft.title = 'Named'; }), second = changeDraft(first, draft => { draft.nodes[1].parameters.out_features = 64; });
  const undone = travelDraft(second, 'undo'), fork = changeDraft(undone, draft => { draft.nodes[1].label = 'Projection'; });
  assert.equal(fork.future.length, 0); assert.equal(travelDraft(fork, 'redo'), fork);
  assert.equal(fork.draft.nodes[1].parameters.out_features, 32); assert.equal(fork.draft.nodes[1].label, 'Projection');
  assert.equal(second.draft.nodes[1].parameters.out_features, 64);
});

test('public draft transport binds save CAS revision and reopens an independent exact draft while a conflict retains local edits', async () => {
  const realFetch = globalThis.fetch, calls: { url: string; options?: RequestInit }[] = [];
  const local = chain(), original = JSON.stringify(local); let envelope: { draft: AuthoredDraft; revision: number } | null = null;
  globalThis.fetch = async (input, options) => {
    const url = String(input); calls.push({ url, options });
    if (url === '/api/session') return Response.json({ token: 'independent-token' });
    if (options?.method === 'POST') {
      const body = JSON.parse(String(options.body));
      assert.equal(new Headers(options.headers).get('X-ArchCanvas-Session'), 'independent-token');
      if (body.expectedRevision !== (envelope?.revision ?? 0)) return Response.json({ error: 'storage conflict', revision: envelope?.revision }, { status: 409 });
      envelope = { draft: structuredClone(body.draft), revision: (envelope?.revision ?? 0) + 1 }; return Response.json(envelope);
    }
    return Response.json(envelope);
  };
  try {
    const saved = await api.saveDraft(local, 0); assert.equal(saved.revision, 1); assert.equal(JSON.stringify(local), original);
    const changed = changeDraft(draftHistory(local), draft => { draft.nodes[1].position.x += 32; });
    await assert.rejects(api.saveDraft(changed.draft, 0), /storage conflict/); assert.equal(changed.draft.nodes[1].position.x, 352);
    const reopened = await api.draft(local.id); assert.deepEqual(reopened.draft, local); assert.equal(reopened.revision, 1);
    reopened.draft.nodes[1].label = 'caller edit'; assert.equal(envelope!.draft.nodes[1].label, module('Linear').label); assert.equal(local.nodes[1].label, module('Linear').label);
    assert.ok(calls.some(call => call.url === `/api/authoring/drafts/${local.id}` && call.options?.method === 'POST'));
  } finally { globalThis.fetch = realFetch; }
});

test('click additions find free space past the original five-node overlap counterexample without moving prior modules', () => {
  const draft = blankDraft('draft-ab16'), preferred = { x: 300.25, y: 100.75 };
  for (let i = 0; i < 12; i++) {
    const previous = structuredClone(draft.nodes), position = nextDraftPosition(draft, preferred);
    for (const node of draft.nodes) assert.ok(Math.abs(position.x - node.position.x) >= 176 || Math.abs(position.y - node.position.y) >= 100, `new module ${i} covers ${node.id}`);
    addDraftNode(draft, module(i ? 'Linear' : 'Input'), `node-${i}`, position);
    assert.deepEqual(draft.nodes.slice(0, -1), previous);
    assert.deepEqual(draftRoutes(draft, catalog).overlaps, []);
  }
  assert.notDeepEqual(draft.nodes[4].position, draft.nodes[0].position);
  assert.equal(new Set(draft.nodes.map(node => JSON.stringify(node.position))).size, 12);
});

test('cache boundary rejects crash-causing node shapes, impossible revisions and unsafe coordinates while returning detached valid edits', () => {
  const valid = { draft: chain(), storageRevision: 3, savedRevision: 0 };
  const restored = parseDraftCache(valid); assert.ok(restored); assert.deepEqual(restored, valid);
  restored.draft.nodes[0].position.x += 1; assert.equal(valid.draft.nodes[0].position.x, 50);
  const corruptions: ((value: typeof valid) => void)[] = [
    value => { value.draft.nodes[0] = {} as never; },
    value => { value.draft.nodes[0].position = undefined as never; },
    value => { value.draft.nodes[0].position.x = Infinity; },
    value => { value.draft.nodes[0].position.y = 1_000_001; },
    value => { value.draft.nodes[0].position.x = '12' as never; },
    value => { value.draft.nodes[1].id = value.draft.nodes[0].id; },
    value => { value.draft.edges[0].target.nodeId = 'foreign'; },
    value => { value.draft.edges[1].id = value.draft.edges[0].id; },
    value => { value.draft.nodes[0].parameters.shape = [1, NaN]; },
    value => { value.draft.title = ''; },
    value => { value.draft.revision = -1; },
    value => { value.storageRevision = -1; },
    value => { value.storageRevision = 1.5; },
    value => { value.savedRevision = value.draft.revision + 1; },
    value => { value.savedRevision = -2; },
  ];
  for (const corrupt of corruptions) { const value = structuredClone(valid); corrupt(value); assert.equal(parseDraftCache(value), null); }
  for (const value of [null, undefined, false, [], {}, { draft: { mode: 'authored-draft', schemaVersion: 1, nodes: [{}], edges: [] } }]) assert.equal(parseDraftCache(value), null);
  // An unsaved draft is legitimate and must survive return-to-figure/remount.
  assert.deepEqual(parseDraftCache({ draft: chain(), storageRevision: 0, savedRevision: -1 })?.draft, valid.draft);
});

test('public authoring pan primitive uses final endpoint in all four directions, ignores foreign pointer and preserves model history', () => {
  const history = draftHistory(chain()), original = JSON.stringify(history);
  for (const zoom of [.15, 1, 3]) for (const [dx, dy] of [[-32, 0], [32, 0], [0, -32], [0, 32]]) {
    const camera = { x: -50, y: 80, zoom }, initial = { pointerId: 7, clientX: 500, clientY: 300, viewportX: 200, viewportY: 100 };
    const session = beginCameraPan(camera, initial);
    cameraAtPanInput(session, { ...initial, clientX: 500 + dx / 4, clientY: 300 + dy / 4 });
    assert.deepEqual(cameraAtPanInput(session, { ...initial, clientX: 500 + dx, clientY: 300 + dy }), { x: -50 + dx, y: 80 + dy, zoom });
    assert.equal(cameraAtPanInput(session, { ...initial, pointerId: 8, clientX: 900 }), null);
    assert.deepEqual(session.camera, camera, 'cancellation can restore the exact frozen camera');
    assert.deepEqual(cameraAtPanInput(session, initial), camera);
  }
  assert.equal(JSON.stringify(history), original);
});
