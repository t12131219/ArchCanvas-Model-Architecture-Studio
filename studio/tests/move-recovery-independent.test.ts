import test from 'node:test';
import assert from 'node:assert/strict';
import { applyVisualBatch, buildScene, createDocument, createHistory, reduceHistory, renderSvg } from '../src/core/index.ts';
import { prepareMovePreview, previewMoveScene } from '../src/core/movePreview.ts';
import { planLayoutRecovery } from '../src/core/layoutRecovery.ts';
import { layoutWarnings } from '../src/layoutWarnings.ts';
import type { Architecture, ArchitectureNode, CanvasDocument, Scene } from '../src/core/types.ts';

// Authored from the public hierarchy/port contract. No historical captures,
// product router parser, candidate generator or placement helper supplies an oracle.
function architecture(): Architecture {
  const node = (id: string, category: string, parentId?: string, children: string[] = []): ArchitectureNode => ({
    id, label: id, kind: category, category, parentId, children, parameters: {}, evidence: 'source',
    ports: [{ id: 'in', name: 'input', direction: 'in', role: 'data', ordinal: 0 },
      { id: 'out', name: 'output', direction: 'out', role: 'data', ordinal: 0 }],
  });
  return {
    schemaVersion: 1, id: 'architecture:recovery-independent', label: 'Manual position recovery', entry: 'model:Model',
    sourceDigest: 'independent-source', irDigest: 'independent-ir',
    sources: [{ path: 'model.py', content: '# immutable model evidence\n', digest: 'source-file' }], diagnostics: [],
    nodes: [node('root', 'container', undefined, ['input', 'network', 'output', 'spare']), node('input', 'input', 'root'),
      node('network', 'container', 'root', ['first', 'second']), node('first', 'linear', 'network'),
      node('second', 'activation', 'network'), node('output', 'output', 'root'), node('spare', 'module', 'root')],
    edges: [
      { id: 'entry', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'first', portId: 'in' }, tensorId: 'input-tensor', role: 'data' },
      { id: 'fanout', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'second', portId: 'in' }, tensorId: 'input-tensor', role: 'data' },
      { id: 'middle', source: { nodeId: 'first', portId: 'out' }, target: { nodeId: 'second', portId: 'in' }, tensorId: 'first-tensor', role: 'data' },
      { id: 'exit', source: { nodeId: 'second', portId: 'out' }, target: { nodeId: 'output', portId: 'in' }, tensorId: 'second-tensor', role: 'data' },
    ],
  };
}
function document(): CanvasDocument {
  const doc = createDocument(architecture());
  doc.expandedIds = ['root', 'network'];
  doc.layout = {
    root: { x: 50, y: 92 }, input: { x: 30, y: 62 }, network: { x: 30, y: 162 },
    first: { x: 30, y: 62 }, second: { x: 30, y: 162 }, output: { x: 30, y: 454 }, spare: { x: 360, y: 62 },
  };
  doc.layoutByFrontier = { root: structuredClone(doc.layout), 'network|root': structuredClone(doc.layout) };
  doc.displayAliases = { first: '输入投影', second: '激活', network: '层序列' };
  doc.nodeStyleOverrides = { first: { fill: '#abcdef' } };
  doc.edgeStyleOverrides = { middle: { stroke: '#123456', width: 2 } };
  doc.annotations = [{ id: 'note', text: 'Preserve my explanation', x: -30, y: 700 }];
  doc.pinnedObjects = ['spare'];
  return doc;
}
type Point = { x: number; y: number };
function points(path: string): Point[] {
  const tokens = path.match(/[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?/g) ?? [];
  const result: Point[] = [];
  for (let i = 0; i < tokens.length;) {
    const command = tokens[i++], first = Number(tokens[i++]);
    assert.ok(Number.isFinite(first));
    if (command === 'M' || command === 'L') { const second = Number(tokens[i++]); assert.ok(Number.isFinite(second)); result.push({ x: first, y: second }); }
    else if (command === 'H') { assert.ok(result.length); result.push({ x: first, y: result.at(-1)!.y }); }
    else if (command === 'V') { assert.ok(result.length); result.push({ x: result.at(-1)!.x, y: first }); }
    else assert.fail(`Unknown route command ${command}`);
  }
  assert.ok(result.length >= 2);
  for (let i = 1; i < result.length; i++) assert.ok(result[i - 1].x === result[i].x || result[i - 1].y === result[i].y);
  return result;
}
function ancestors(scene: Scene, id: string): Set<string> {
  const ids = new Set<string>(), nodes = new Map(scene.nodes.map(node => [node.id, node]));
  let parent = nodes.get(id)?.parentId;
  while (parent) { assert.ok(!ids.has(parent)); ids.add(parent); parent = nodes.get(parent)?.parentId; }
  return ids;
}
function bodyConflicts(scene: Scene, id: string): string[] {
  const target = scene.nodes.find(node => node.id === id)!;
  const parents = ancestors(scene, id), result: string[] = [];
  for (const other of scene.nodes) {
    if (other.id === id || ancestors(scene, other.id).has(id)) continue;
    if (parents.has(other.id)) {
      if (target.x < other.x || target.y < other.y || target.x + target.width > other.x + other.width || target.y + target.height > other.y + other.height) result.push(`outside:${other.id}`);
      if (Math.min(target.x + target.width, other.x + other.width) > Math.max(target.x, other.x) &&
        Math.min(target.y + target.height, other.y + other.headerHeight) > Math.max(target.y, other.y)) result.push(`header:${other.id}`);
    } else if (Math.min(target.x + target.width, other.x + other.width) > Math.max(target.x, other.x) &&
      Math.min(target.y + target.height, other.y + other.height) > Math.max(target.y, other.y)) result.push(`body:${other.id}`);
  }
  return result;
}
function routeConflicts(scene: Scene, ids: Set<string>): string[] {
  const result: string[] = [];
  for (const edge of scene.edges) {
    if (!ids.has(edge.sourceId) && !ids.has(edge.targetId)) continue;
    const parsed = points(edge.path), frameIds = new Set([...ancestors(scene, edge.sourceId), ...ancestors(scene, edge.targetId)]);
    for (const node of scene.nodes) {
      const height = frameIds.has(node.id) ? node.headerHeight : node.height;
      for (let i = 1; i < parsed.length; i++) {
        const a = parsed[i - 1], b = parsed[i], left = node.x + .01, right = node.x + node.width - .01, top = node.y + .01, bottom = node.y + height - .01;
        const hit = a.x === b.x ? a.x > left && a.x < right && Math.max(Math.min(a.y, b.y), top) < Math.min(Math.max(a.y, b.y), bottom)
          : a.y > top && a.y < bottom && Math.max(Math.min(a.x, b.x), left) < Math.min(Math.max(a.x, b.x), right);
        if (hit) { result.push(`${edge.id}:${node.id}`); break; }
      }
    }
  }
  return result;
}
function endpointFacts(scene: Scene) {
  for (const edge of scene.edges) {
    const parsed = points(edge.path);
    for (const [owner, direction, endpoint] of [[edge.sourceId, 'out', parsed[0]], [edge.targetId, 'in', parsed.at(-1)!]] as const) {
      const node = scene.nodes.find(item => item.id === owner)!;
      const matching = node.ports.filter(port => port.direction === direction && port.canonicalEdgeIds.includes(edge.id));
      assert.ok(matching.some(port => Math.abs(endpoint.x - port.x) < .11 && Math.abs(endpoint.y - port.y) < .11), `${edge.id} detached ${direction}`);
    }
    for (const p of parsed) assert.ok(p.x >= scene.bounds.x && p.y >= scene.bounds.y && p.x <= scene.bounds.x + scene.bounds.width && p.y <= scene.bounds.y + scene.bounds.height);
  }
  const inputPorts = scene.nodes.find(node => node.id === 'input')!.ports.filter(port => port.direction === 'out');
  assert.equal(inputPorts.length, 1, 'same source binding/tensor fanout has one shared endpoint');
  assert.deepEqual(inputPorts[0].canonicalEdgeIds, ['entry', 'fanout']);
  // 50+30 + 194/2 = 177, 92+62+62 = 216. Neither input nor its ancestors moved.
  for (const edge of scene.edges.filter(edge => edge.id === 'entry' || edge.id === 'fanout')) assert.deepEqual(points(edge.path)[0], { x: 177, y: 216 });
}

test('independent oracle detects polluted body/header and route geometry', () => {
  const scene = buildScene(document());
  assert.deepEqual(bodyConflicts(scene, 'first'), []);
  const broken = structuredClone(scene);
  broken.nodes.find(node => node.id === 'first')!.y = 264;
  assert.ok(bodyConflicts(broken, 'first').includes('header:network'));
  const routeBroken = structuredClone(scene);
  routeBroken.edges.find(edge => edge.id === 'entry')!.path = 'M 177 216 V 350 H 207 V 316';
  assert.ok(routeConflicts(routeBroken, new Set(['first'])).includes('entry:first'));
});

test('four directions preserve exact manual coordinates, shared endpoints and expose left/header/sibling conflicts', () => {
  const original = document(), originalBytes = JSON.stringify(original);
  const first = buildScene(original).nodes.find(node => node.id === 'first')!;
  assert.deepEqual([first.x, first.y, first.width, first.height], [110, 316, 194, 62]);
  for (const [dx, dy, conflict] of [[-52, 0, 'outside:network'], [0, -52, 'header:network'], [0, 52, 'body:second'], [52, 0, '']] as const) {
    const moved = applyVisualBatch(original, [{ type: 'move', ids: ['first'], dx, dy }]);
    assert.deepEqual(moved.layout.first, { x: 30 + dx, y: 62 + dy });
    const scene = buildScene(moved), node = scene.nodes.find(item => item.id === 'first')!;
    assert.deepEqual([node.x, node.y], [110 + dx, 316 + dy], 'free drag is not clamped or silently repaired');
    assert.deepEqual(previewMoveScene(prepareMovePreview(original, ['first']), dx, dy), scene);
    endpointFacts(scene);
    assert.deepEqual(moved.architecture, original.architecture);
    assert.deepEqual(moved.pinnedObjects, ['spare']);
    if (conflict) assert.ok(bodyConflicts(scene, 'first').includes(conflict));
    if (dx === -52) {
      assert.equal(scene.nodes.find(item => item.id === 'network')!.x - node.x, 22);
      assert.ok(scene.diagnostics.some(diagnostic => diagnostic.code === 'layout-outside-parent' && diagnostic.objectIds?.[0] === 'first' && diagnostic.objectIds?.[1] === 'network'));
      assert.ok(layoutWarnings(scene).some(message => message.includes('输入投影') && message.includes('层序列')));
    }
    if (dy === 52) assert.equal(node.y + node.height - scene.nodes.find(item => item.id === 'second')!.y, 14);
  }
  assert.equal(JSON.stringify(original), originalBytes);
});

test('explicit recovery preview is obstacle-safe and commit is one reversible visual operation', () => {
  for (const [dx, dy] of [[-52, 0], [0, -52], [0, 52]]) {
    const moved = applyVisualBatch(document(), [{ type: 'move', ids: ['first'], dx, dy }]), bytes = JSON.stringify(moved);
    const plan = planLayoutRecovery(moved, 'first');
    assert.equal(plan.status, 'ready');
    assert.deepEqual(plan.operation.ids, ['first']); assert.equal(plan.operation.type, 'move');
    assert.ok(Number.isInteger(plan.candidateCount) && plan.candidateCount > 0 && plan.candidateCount <= 64);
    assert.ok(Number.isFinite(plan.operation.dx) && Number.isFinite(plan.operation.dy));
    assert.deepEqual(bodyConflicts(plan.scene, 'first'), []);
    assert.deepEqual(routeConflicts(plan.scene, new Set(['first'])), []);
    endpointFacts(plan.scene);
    assert.equal(JSON.stringify(moved), bytes, 'proposal is not a document/history mutation');
    let history = createHistory(moved);
    history = reduceHistory(history, { type: 'apply', baseRevision: moved.revision, operations: [plan.operation] });
    assert.equal(history.past.length, 1);
    assert.equal(history.document.revision, moved.revision + 1);
    const committed = buildScene(history.document);
    assert.deepEqual(committed, plan.scene); assert.equal(renderSvg(committed), renderSvg(plan.scene));
    assert.deepEqual(history.document.layout.first, { x: moved.layout.first.x + plan.operation.dx, y: moved.layout.first.y + plan.operation.dy });
    for (const [frontier, positions] of Object.entries(moved.layoutByFrontier)) {
      assert.deepEqual(history.document.layoutByFrontier[frontier].first, { x: positions.first.x + plan.operation.dx, y: positions.first.y + plan.operation.dy });
      for (const id of Object.keys(positions).filter(id => id !== 'first')) assert.deepEqual(history.document.layoutByFrontier[frontier][id], positions[id]);
    }
    for (const field of ['architecture', 'displayAliases', 'nodeStyleOverrides', 'edgeStyleOverrides', 'annotations', 'legendItems', 'pageSpec', 'pinnedObjects', 'expandedIds', 'title', 'id', 'sourceBindingDigest'] as const) assert.deepEqual(history.document[field], moved[field]);
    for (const id of Object.keys(moved.layout).filter(id => id !== 'first')) assert.deepEqual(history.document.layout[id], moved.layout[id]);
    assert.deepEqual(committed.nodes.find(node => node.id === 'spare'), buildScene(moved).nodes.find(node => node.id === 'spare'));
    const undo = reduceHistory(history, { type: 'undo' }), redo = reduceHistory(undo, { type: 'redo' });
    assert.deepEqual(undo.document.layout, moved.layout); assert.deepEqual(undo.document.layoutByFrontier, moved.layoutByFrontier);
    assert.deepEqual(redo.document.layout, history.document.layout); assert.deepEqual(redo.document.layoutByFrontier, history.document.layoutByFrontier);
    assert.deepEqual({ ...buildScene(redo.document), revision: 0 }, { ...committed, revision: 0 });
  }
});

test('recovery respects pins and keeps an unchanged route-only warning distinct from an unneeded body-clear object', () => {
  const left = applyVisualBatch(document(), [{ type: 'move', ids: ['first'], dx: -52, dy: 0 }]);
  const pinned = applyVisualBatch(left, [{ type: 'pin', ids: ['first'], pinned: true }]);
  for (const [doc, id] of [[pinned, 'first'], [pinned, 'network'], [pinned, 'root']] as const) {
    const bytes = JSON.stringify(doc), plan = planLayoutRecovery(doc, id);
    assert.equal(plan.status, 'unavailable'); assert.ok('reason' in plan && plan.reason.length > 0);
    assert.equal(JSON.stringify(doc), bytes);
  }
  // Keep this clear-right assertion independent of the route solver's choice
  // of a residual fan-out corridor. Route-only retention and improvement are
  // covered by the separate final-geometry safety fixture below.
  const clear = document(); clear.architecture.edges = clear.architecture.edges.filter(edge => edge.id !== 'fanout');
  const right = applyVisualBatch(clear, [{ type: 'move', ids: ['first'], dx: 52, dy: 0 }]);
  const scene = buildScene(right), bytes = JSON.stringify(right);
  assert.deepEqual(bodyConflicts(scene, 'first'), []);
  assert.equal(planLayoutRecovery(right, 'first').status, 'unneeded');
  assert.equal(planLayoutRecovery(right, 'output').status, 'unneeded');
  assert.equal(JSON.stringify(right), bytes);
});

test('a partial overlap reduction cannot be offered as selected-object position recovery', () => {
  const nodes: ArchitectureNode[] = ['chosen', 'blocker', 'lower'].map(id => ({
    id, label: id, kind: 'Linear', category: 'linear', children: [], ports: [], parameters: {}, evidence: 'source',
  }));
  const doc = createDocument({ schemaVersion: 1, id: 'two-overlap-obstacles', label: 'Two independent obstacles', entry: 'Model',
    sourceDigest: 'two-overlap-source', irDigest: 'two-overlap-ir', sources: [], diagnostics: [], nodes, edges: [] });
  doc.layout = { chosen: { x: 0, y: 100 }, blocker: { x: 180, y: 100 }, lower: { x: 100, y: 130 } };
  const bytes = JSON.stringify(doc), before = buildScene(doc);
  assert.deepEqual(bodyConflicts(before, 'chosen').sort(), ['body:blocker', 'body:lower']);
  // The nearer x=-56 candidate clears blocker, but its right=138 still
  // intersects lower over x=100..138, y=130..162. A smaller existing
  // collision remains a collision rather than a completed repair.
  const partial = buildScene(applyVisualBatch(doc, [{ type: 'move', ids: ['chosen'], dx: -56, dy: 0 }]));
  assert.deepEqual(bodyConflicts(partial, 'chosen'), ['body:lower']);
  const plan = planLayoutRecovery(doc, 'chosen');
  assert.equal(plan.status, 'ready');
  assert.deepEqual(bodyConflicts(plan.scene, 'chosen'), []);
  assert.notDeepEqual([plan.operation.dx, plan.operation.dy], [-56, 0]);
  assert.deepEqual(plan.scene.nodes.filter(node => node.id !== 'chosen'), before.nodes.filter(node => node.id !== 'chosen'));
  assert.equal(JSON.stringify(doc), bytes);
});

test('touching the true parent border is contained while even a one-unit left escape is diagnosed', () => {
  const onBorder = applyVisualBatch(document(), [{ type: 'move', ids: ['first'], dx: -30, dy: 0 }]);
  assert.equal(buildScene(onBorder).nodes.find(node => node.id === 'first')!.x, 80);
  assert.ok(!buildScene(onBorder).diagnostics.some(diagnostic => diagnostic.code === 'layout-outside-parent' && diagnostic.objectIds?.[0] === 'first'));
  const escaped = applyVisualBatch(onBorder, [{ type: 'move', ids: ['first'], dx: -1, dy: 0 }]);
  assert.equal(buildScene(escaped).nodes.find(node => node.id === 'first')!.x, 79);
  assert.ok(buildScene(escaped).diagnostics.some(diagnostic => diagnostic.code === 'layout-outside-parent' && diagnostic.objectIds?.[0] === 'first'));
});

test('selected expanded subtree moves as one root and recovery preserves child locals and outside pins', () => {
  const original = document(), moved = applyVisualBatch(original, [{ type: 'move', ids: ['network'], dx: 0, dy: -80 }]);
  assert.deepEqual(moved.layout.network, { x: 30, y: 82 });
  assert.deepEqual(moved.layout.first, { x: 30, y: 62 });
  assert.deepEqual(moved.layout.second, { x: 30, y: 162 });
  const before = buildScene(moved);
  assert.deepEqual([before.nodes.find(node => node.id === 'network')!.x, before.nodes.find(node => node.id === 'network')!.y], [80, 174]);
  assert.deepEqual([before.nodes.find(node => node.id === 'first')!.x, before.nodes.find(node => node.id === 'first')!.y], [110, 236]);
  assert.ok(bodyConflicts(before, 'network').includes('body:input'));
  const bytes = JSON.stringify(moved), plan = planLayoutRecovery(moved, 'network');
  assert.equal(plan.status, 'ready');
  assert.deepEqual(plan.operation.ids, ['network']);
  assert.ok(plan.candidateCount <= 64);
  for (const id of ['network', 'first', 'second']) assert.deepEqual(bodyConflicts(plan.scene, id), []);
  assert.deepEqual(routeConflicts(plan.scene, new Set(['network', 'first', 'second'])), []);
  const committed = applyVisualBatch(moved, [plan.operation]);
  assert.deepEqual(buildScene(committed), plan.scene);
  for (const id of ['first', 'second']) {
    assert.deepEqual(committed.layout[id], moved.layout[id]);
    const current: Scene['nodes'][number] = plan.scene.nodes.find(node => node.id === id)!;
    const prior = before.nodes.find(node => node.id === id)!;
    assert.deepEqual([current.x - prior.x, current.y - prior.y], [plan.operation.dx, plan.operation.dy]);
  }
  assert.deepEqual(plan.scene.nodes.find(node => node.id === 'spare'), before.nodes.find(node => node.id === 'spare'));
  endpointFacts(plan.scene); assert.equal(JSON.stringify(moved), bytes);
});

test('an invariant internal conflict is unavailable even with many nearby candidate obstacles', () => {
  const original = document();
  const root = original.architecture.nodes.find(node => node.id === 'root')!;
  for (let i = 0; i < 17; i++) {
    const id = `obstacle-${i}`;
    root.children.push(id);
    original.architecture.nodes.push({
      id, label: id, kind: 'Identity', category: 'module', parentId: 'root', children: [], ports: [], parameters: {}, evidence: 'source',
    });
    original.layout[id] = { x: 700 + i * 260, y: 200 + i * 200 };
  }
  const moved = applyVisualBatch(original, [{ type: 'move', ids: ['first'], dx: -52, dy: 0 }]);
  const bytes = JSON.stringify(moved);
  // Its child is always local x=-22: translating the entire network cannot
  // make that child fall inside it, regardless of which bounded candidate wins.
  assert.equal(moved.layout.first.x, -22);
  for (const [dx, dy] of [[0, 100], [100, 0], [-50, -50], [9000, 9000]]) {
    const translated = applyVisualBatch(moved, [{ type: 'move', ids: ['network'], dx, dy }]);
    const scene = buildScene(translated), child = scene.nodes.find(node => node.id === 'first')!, parent = scene.nodes.find(node => node.id === 'network')!;
    assert.equal(parent.x - child.x, 22);
  }
  const plan = planLayoutRecovery(moved, 'network');
  assert.equal(plan.status, 'unavailable'); assert.ok('reason' in plan && plan.reason.length > 0);
  assert.equal(JSON.stringify(moved), bytes);
});

test('ready recovery preserves an existing unrelated collision rather than presenting it as globally resolved', () => {
  const original = document();
  original.layout.spare = { x: 30, y: 454 }; // Exactly covers the unrelated Output.
  const moved = applyVisualBatch(original, [{ type: 'move', ids: ['first'], dx: -52, dy: 0 }]);
  const before = buildScene(moved), bytes = JSON.stringify(moved);
  assert.ok(bodyConflicts(before, 'output').includes('body:spare'));
  const plan = planLayoutRecovery(moved, 'first');
  assert.equal(plan.status, 'ready');
  assert.deepEqual(bodyConflicts(plan.scene, 'first'), []);
  assert.ok(bodyConflicts(plan.scene, 'output').includes('body:spare'));
  for (const id of ['output', 'spare']) assert.deepEqual(plan.scene.nodes.find(node => node.id === id), before.nodes.find(node => node.id === id));
  const signature = (diagnostic: Scene['diagnostics'][number]) => JSON.stringify([diagnostic.code, diagnostic.objectIds, diagnostic.edgeId]);
  const prior = new Set(before.diagnostics.filter(diagnostic => diagnostic.code).map(signature));
  for (const diagnostic of plan.scene.diagnostics.filter(diagnostic => diagnostic.code)) assert.ok(prior.has(signature(diagnostic)), 'proposal introduces a new unrelated conflict');
  assert.equal(JSON.stringify(moved), bytes);
});

test('unknown or hidden objects do not produce phantom recovery scenes', () => {
  const hidden = applyVisualBatch(document(), [{ type: 'expand', id: 'network', expanded: false }]);
  for (const [doc, id] of [[hidden, 'first'], [document(), 'absent-node']] as const) {
    const bytes = JSON.stringify(doc), plan = planLayoutRecovery(doc, id);
    assert.equal(plan.status, 'unavailable'); assert.ok('reason' in plan && plan.reason.length > 0);
    assert.equal(JSON.stringify(doc), bytes);
  }
});

test('same-pair ancestor collision growth rejects an otherwise clear nearby candidate', () => {
  const original = document();
  const network = original.architecture.nodes.find(node => node.id === 'network')!;
  network.children.push('blocker');
  original.architecture.nodes.push(
    { id: 'blocker', label: 'blocker', kind: 'Identity', category: 'module', parentId: 'network', children: [],
      ports: [{ id: 'out', name: 'output', direction: 'out', role: 'data', ordinal: 0 }], parameters: {}, evidence: 'source' },
    { id: 'outside', label: 'outside', kind: 'Identity', category: 'module', children: [], ports: [], parameters: {}, evidence: 'source' },
  );
  original.architecture.edges.push({ id: 'blocker-first', source: { nodeId: 'blocker', portId: 'out' }, target: { nodeId: 'first', portId: 'in' }, tensorId: 'blocker-tensor', role: 'data' });
  original.layout.blocker = { x: 30, y: 62 };
  original.layout.outside = { x: 320, y: 500 };
  original.pinnedObjects.push('outside');
  const moved = applyVisualBatch(original, [{ type: 'move', ids: ['first'], dx: 0, dy: 100 }]);
  const bytes = JSON.stringify(moved), before = buildScene(moved);
  const ancestor = before.nodes.find(node => node.id === 'network')!, fixed = before.nodes.find(node => node.id === 'outside')!;
  assert.deepEqual([ancestor.x, ancestor.y, ancestor.width, ancestor.height], [80, 254, 254, 254]);
  assert.deepEqual([fixed.x, fixed.y, fixed.width, fixed.height], [320, 500, 194, 62]);
  // The closest lateral clear slot starts at 304+42 = 346. Its parent expands
  // from right=334 to right=570. The *same* network/outside pair changes
  // from a 14×8 intersection to 194×8; rejecting only new pair IDs misses it.
  const lateral = applyVisualBatch(moved, [{ type: 'move', ids: ['first'], dx: 236, dy: 0 }]);
  const lateralScene = buildScene(lateral), grown = lateralScene.nodes.find(node => node.id === 'network')!;
  assert.equal(grown.width, 490);
  assert.deepEqual(bodyConflicts(lateralScene, 'first'), []);
  assert.deepEqual(routeConflicts(lateralScene, new Set(['first'])), []);
  const collision = (scene: Scene) => scene.diagnostics.find(diagnostic => diagnostic.code === 'layout-overlap' && diagnostic.objectIds?.includes('network') && diagnostic.objectIds?.includes('outside'))!;
  assert.ok(collision(before)); assert.deepEqual(collision(lateralScene).objectIds, collision(before).objectIds);
  const area = (a: Scene['nodes'][number], b: Scene['nodes'][number]) => Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x)) *
    Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
  assert.equal(area(ancestor, fixed), 112); assert.equal(area(grown, fixed), 1552);
  const plan = planLayoutRecovery(moved, 'first');
  // Every in-frame safe slot either widens this parent beyond x=334 or grows
  // its bottom beyond y=508, increasing this already-present fixed collision.
  assert.equal(plan.status, 'unavailable'); assert.ok('reason' in plan && plan.reason.length > 0);
  assert.equal(JSON.stringify(moved), bytes);
});
