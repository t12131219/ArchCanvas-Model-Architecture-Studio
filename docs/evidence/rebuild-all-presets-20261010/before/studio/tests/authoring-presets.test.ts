import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { blankDraft, changeDraft, draftHistory, draftRoutes, parseDraftCache, travelDraft } from '../src/authoring.ts';
import type { DraftCatalog } from '../src/authoring.ts';
import { draftPresets, draftPresetUnavailable, insertDraftPreset } from '../src/authoringPresets.ts';
import { fitDraftCamera } from '../src/authoringFeedback.ts';

const project = fileURLToPath(new URL('../../', import.meta.url));
const python = `${project}.venv/bin/python`, run = promisify(execFile);
const catalogRead = await run(python, ['-I', '-S', '-B', '-c',
  'import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_authoring import module_catalog;print(json.dumps(module_catalog()))', project]);
const catalog = JSON.parse(catalogRead.stdout) as DraftCatalog;
function ids() { let count = 0; return (prefix: 'n' | 'e') => `${prefix}_test${++count}`; }

test('a transparent network is one history step and redo restores its stable nodes, edges and edits', () => {
  for (const preset of draftPresets) {
    const initial = draftHistory(blankDraft('draft-preset-history')), before = JSON.stringify(initial);
    const added = changeDraft(initial, draft => insertDraftPreset(draft, catalog, preset.id, { x: 50, y: 70 }, ids()));
    assert.equal(JSON.stringify(initial), before);
    assert.equal(added.past.length, 1); assert.equal(added.draft.revision, 1);
    assert.equal(added.draft.nodes.length, preset.nodes.length);
    assert.equal(added.draft.edges.length, preset.edges.length);
    assert.equal(added.draft.nodes.filter(node => node.kind === 'Input').length, preset.nodes.filter(node => node.kind === 'Input').length);
    assert.equal(added.draft.nodes.filter(node => node.kind === 'Output').length, 1);
    const undone = travelDraft(added, 'undo');
    assert.deepEqual(undone.draft.nodes, []); assert.deepEqual(undone.draft.edges, []);
    const redone = travelDraft(undone, 'redo');
    assert.deepEqual(redone.draft.nodes, added.draft.nodes); assert.deepEqual(redone.draft.edges, added.draft.edges);
    const beforeLabel = added.draft.nodes[1].label;
    const edited = changeDraft(redone, value => { value.nodes[0].parameters.shape = [2, 16]; value.nodes[1].label = '我的隐藏层'; });
    assert.equal(edited.draft.nodes[1].label, '我的隐藏层'); assert.equal(added.draft.nodes[1].label, beforeLabel);
    assert.ok(parseDraftCache({ draft: redone.draft, storageRevision: 0, savedRevision: -1 }));
  }
});

test('repeat insertion avoids occupied cards, preserves prior identities and bindings, and never connects old networks', () => {
  const draft = blankDraft('draft-preset-repeat'), makeId = ids();
  const first = insertDraftPreset(draft, catalog, 'mlp', { x: 50, y: 70 }, makeId);
  draft.title = '已有模型'; draft.nodes[1].parameters.bias = false;
  const originalNodes = structuredClone(draft.nodes), originalEdges = structuredClone(draft.edges), originalTitle = draft.title;
  const presetBytes = JSON.stringify(draftPresets), catalogBytes = JSON.stringify(catalog);
  const second = insertDraftPreset(draft, catalog, 'cnn', { x: 50, y: 70 }, makeId);
  const third = insertDraftPreset(draft, catalog, 'residual-mlp', { x: 50, y: 70 }, makeId);
  assert.deepEqual(draft.nodes.slice(0, 5), originalNodes); assert.deepEqual(draft.edges.slice(0, 4), originalEdges); assert.equal(draft.title, originalTitle);
  assert.equal(new Set([...draft.nodes.map(node => node.id), ...draft.edges.map(edge => edge.id)]).size, draft.nodes.length + draft.edges.length);
  const owner = new Map([first, second, third].flatMap((inserted, index) => inserted.nodeIds.map(id => [id, index] as const)));
  for (const edge of draft.edges) assert.equal(owner.get(edge.source.nodeId), owner.get(edge.target.nodeId));
  assert.deepEqual(draftRoutes(draft, catalog).overlaps, []);
  for (let i = 0; i < draft.nodes.length; i++) for (const later of draft.nodes.slice(i + 1)) {
    const node = draft.nodes[i];
    assert.ok(Math.abs(node.position.x - later.position.x) >= 196 || Math.abs(node.position.y - later.position.y) >= 120);
  }
  assert.equal(JSON.stringify(draftPresets), presetBytes); assert.equal(JSON.stringify(catalog), catalogBytes);
  draft.nodes[5].parameters.shape = [2, 3, 16, 16];
  assert.deepEqual(catalog.modules.find(module => module.kind === 'Input')!.defaults.shape, [1, 16]);
});

test('IDs collide or fail safely before any draft mutation; retry uses fresh identities for every node and edge', () => {
  const draft = blankDraft('draft-preset-identities');
  insertDraftPreset(draft, catalog, 'mlp', { x: 50, y: 70 }, ids());
  const before = JSON.stringify(draft);
  assert.throws(() => insertDraftPreset(draft, catalog, 'cnn', { x: 50, y: 70 }, () => draft.nodes[0].id), /标识/);
  assert.equal(JSON.stringify(draft), before);
  assert.throws(() => insertDraftPreset(draft, catalog, 'cnn', { x: 50, y: 70 }, () => 'invalid id!'), /标识/);
  assert.equal(JSON.stringify(draft), before);
  let count = 0;
  const added = insertDraftPreset(draft, catalog, 'cnn', { x: 50, y: 70 }, prefix => ++count <= 2 ? draft.nodes[0].id : `${prefix}_fresh${count}`);
  assert.equal(added.nodeIds.length, 8); assert.equal(added.edgeIds.length, 7); assert.equal(count, 17);
  assert.ok(!added.nodeIds.includes(draft.nodes[0].id)); assert.equal(added.inputNodeId, added.nodeIds[0]);
});

test('catalog compatibility, node/edge budgets and extreme coordinates refuse atomically', () => {
  const initial = blankDraft('draft-preset-refusal');
  const cnn = draftPresets.find(preset => preset.id === 'cnn')!;
  assert.equal(draftPresetUnavailable(cnn, catalog), null);
  assert.match(draftPresetUnavailable(cnn, null)!, /加载/);
  const variants = [
    (copy: DraftCatalog) => { copy.modules = copy.modules.filter(module => module.kind !== 'Conv2d'); },
    (copy: DraftCatalog) => { copy.modules.find(module => module.kind === 'Linear')!.ports.push({ id: 'extra', name: 'extra', direction: 'in', type: 'tensor' }); },
    (copy: DraftCatalog) => { copy.modules.find(module => module.kind === 'Input')!.parameters.find(field => field.name === 'dtype')!.options = ['int64']; },
    (copy: DraftCatalog) => { copy.modules.find(module => module.kind === 'Conv2d')!.defaults.kernel_size = [-3, 3]; },
  ];
  for (const corrupt of variants) {
    const value = structuredClone(catalog); corrupt(value);
    assert.ok(draftPresetUnavailable(cnn, value));
    const before = JSON.stringify(initial);
    assert.throws(() => insertDraftPreset(initial, value, 'cnn', { x: 50, y: 70 }, ids()));
    assert.equal(JSON.stringify(initial), before);
  }
  const fullNodes = structuredClone(initial);
  for (let i = 0; i < 121; i++) fullNodes.nodes.push({ id: `old${i}`, kind: 'Input', label: '旧输入', parameters: {}, position: { x: 0, y: i * 128 } });
  const fullEdges = structuredClone(initial);
  for (let i = 0; i < 378; i++) fullEdges.edges.push({ id: `old-edge${i}`, source: { nodeId: 'x', portId: 'output' }, target: { nodeId: 'y', portId: 'input' } });
  for (const [draft, at] of [[fullNodes, { x: 0, y: 0 }], [fullEdges, { x: 0, y: 0 }], [initial, { x: 999_999, y: 0 }], [initial, { x: NaN, y: 0 }]] as const) {
    const before = JSON.stringify(draft);
    assert.throws(() => insertDraftPreset(draft, catalog, 'cnn', at, ids())); assert.equal(JSON.stringify(draft), before);
  }
});

test('CNN starting layout is legible at the observed viewport with one clear exterior row return', () => {
  const draft = blankDraft('draft-preset-cnn-layout');
  insertDraftPreset(draft, catalog, 'cnn', { x: 80, y: 90 }, ids());
  const geometry = draftRoutes(draft, catalog);
  assert.equal(draft.nodes.length, 8); assert.equal(geometry.routes.length, 7);
  assert.deepEqual(geometry.overlaps, []);
  // Independently inspect segments against the actual card bodies. Router
  // blockedBy flags alone cannot establish that a route is clear.
  const parts = geometry.routes.map(route => {
    const points = route.points.filter((point, index, all) => !index || point.x !== all[index - 1].x || point.y !== all[index - 1].y);
    const edge = draft.edges.find(edge => edge.id === route.id)!;
    const source = draft.nodes.find(node => node.id === edge.source.nodeId)!, target = draft.nodes.find(node => node.id === edge.target.nodeId)!;
    assert.deepEqual(points[0], { x: geometry.ports[source.id][edge.source.portId].x, y: geometry.ports[source.id][edge.source.portId].y });
    assert.deepEqual(points.at(-1), { x: geometry.ports[target.id][edge.target.portId].x, y: geometry.ports[target.id][edge.target.portId].y });
    return points.slice(1).map((b, index) => [points[index], b] as const);
  });
  let turns = 0, turnedRoutes = 0;
  for (const segments of parts) {
    let localTurns = 0;
    for (const [index, [a, b]] of segments.entries()) {
      assert.ok(a.x === b.x || a.y === b.y);
      for (const node of draft.nodes) {
        const left = node.position.x, right = left + 176, top = node.position.y, bottom = top + 100;
        const hit = a.x === b.x
          ? a.x > left && a.x < right && Math.max(Math.min(a.y, b.y), top) < Math.min(Math.max(a.y, b.y), bottom)
          : a.y > top && a.y < bottom && Math.max(Math.min(a.x, b.x), left) < Math.min(Math.max(a.x, b.x), right);
        assert.equal(hit, false, `line enters ${node.kind}`);
      }
      if (index) {
        const [previous, shared] = segments[index - 1];
        const dx = shared.x - previous.x, dy = shared.y - previous.y;
        if ((dx === 0) !== (a.x === b.x)) localTurns++;
        else assert.ok(dx * (b.x - a.x) + dy * (b.y - a.y) > 0, 'no reversing segment');
      }
    }
    turns += localTurns; if (localTurns) turnedRoutes++;
  }
  assert.equal(turnedRoutes, 1); assert.ok(turns <= 4, "candidate ports may shorten the exterior row return");
  for (let i = 0; i < parts.length; i++) for (const other of parts.slice(i + 1)) for (const [a, b] of parts[i]) for (const [c, d] of other) {
    const ah = a.y === b.y, ch = c.y === d.y;
    if (ah === ch) {
      if (ah ? a.y !== c.y : a.x !== c.x) continue;
      const axis = ah ? 'x' : 'y';
      assert.ok(Math.min(Math.max(a[axis], b[axis]), Math.max(c[axis], d[axis])) <= Math.max(Math.min(a[axis], b[axis]), Math.min(c[axis], d[axis])), 'routes do not share a positive-length segment');
    } else {
      const [h0, h1] = ah ? [a, b] : [c, d], [v0, v1] = ah ? [c, d] : [a, b];
      const cross = v0.x > Math.min(h0.x, h1.x) && v0.x < Math.max(h0.x, h1.x) && h0.y > Math.min(v0.y, v1.y) && h0.y < Math.max(v0.y, v1.y);
      assert.equal(cross, false, 'routes do not cross');
    }
  }
  const routePoints = geometry.routes.flatMap(route => route.points), viewport = { width: 815, height: 535.5 };
  const camera = fitDraftCamera(draft, viewport, catalog, routePoints);
  const all = [...draft.nodes.flatMap(node => [node.position, { x: node.position.x + 176, y: node.position.y + 100 }]), ...routePoints];
  const width = Math.max(...all.map(point => point.x)) - Math.min(...all.map(point => point.x)) + 64;
  const height = Math.max(...all.map(point => point.y)) - Math.min(...all.map(point => point.y)) + 64;
  assert.equal(camera.zoom, Math.min(1, (viewport.width - 30) / width, (viewport.height - 30) / height));
  assert.ok(camera.zoom >= .84 && camera.zoom <= 1, "shorter automatic routes may permit a larger fit");
  assert.ok(13 * camera.zoom > 11, '13-unit titles retain more than 11 CSS pixels at the observed viewport');
});

test('actual inserted graphs pass the formal nonexecuting backend source pipeline; a disconnected old node still fails generation', async () => {
  const drafts = draftPresets.map(preset => {
    const draft = blankDraft(`draft-preset-${preset.id}`); insertDraftPreset(draft, catalog, preset.id, { x: 50, y: 70 }, ids()); return draft;
  });
  const invalid = structuredClone(drafts[0]);
  invalid.nodes.push({ id: 'unconnected', kind: 'ReLU', label: '待连接', parameters: {}, position: { x: 50, y: 300 } });
  const response = await run(python, ['-I', '-S', '-B', '-c', [
    'import sys,json;sys.path.insert(0,sys.argv[1]+"/src")',
    'from archcanvas_authoring import generate_model,DraftError',
    'from unittest.mock import patch',
    'drafts=json.loads(sys.argv[2]); result=[]',
    'with patch("builtins.exec",side_effect=AssertionError("model execution forbidden")), patch("builtins.eval",side_effect=AssertionError("evaluation forbidden")):',
    ' for draft in drafts[:-1]:',
    '  generated=generate_model(draft); outputs={n["id"]:generated["tensors"][n["id"]] for n in draft["nodes"] if n["kind"]=="Output"}',
    '  result.append({"outputs":outputs,"verification":generated["verification"],"source":generated["source"]})',
    ' try: generate_model(drafts[-1])',
    ' except DraftError as error: result.append({"issues":[d["code"] for d in error.diagnostics]})',
    ' else: raise AssertionError("old disconnected module silently ignored")',
    'print(json.dumps(result))',
  ].join('\n'), project, JSON.stringify([...drafts, invalid])], { maxBuffer: 2_000_000 });
  const results = JSON.parse(response.stdout);
  for (const [index, expected] of [[0, [1, 4]], [1, [1, 4]], [2, [1, 16]]] as const) {
    assert.deepEqual(Object.values(results[index].outputs), [{ shape: expected, dtype: 'float32' }]);
    assert.equal(results[index].verification.status, 'passed'); assert.equal(results[index].verification.modelExecution, 'not_run');
    assert.match(results[index].source, /class AuthoredModel\(nn.Module\)/);
  }
  assert.ok(results.at(-1).issues.includes('unbound-input')); assert.ok(results.at(-1).issues.includes('unused-node'));
  for (const [index, preset] of draftPresets.entries()) {
    const expected = JSON.parse(preset.output);
    assert.deepEqual(Object.values(results[index].outputs), [{ shape: expected, dtype: 'float32' }], preset.id);
    assert.equal(results[index].verification.status, 'passed', preset.id);
  }
});
