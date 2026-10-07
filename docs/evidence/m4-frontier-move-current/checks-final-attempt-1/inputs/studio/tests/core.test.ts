import test from 'node:test';
import assert from 'node:assert/strict';
import { applyVisualBatch, buildScene, createDocument, createHistory, reduceHistory, renderSvg, reconcileDocument, RevisionConflict, validateDocument } from '../src/core/index.ts';
import type { Architecture, ArchitectureNode } from '../src/core/index.ts';
import { textWidth, wrapText } from '../src/core/typography.ts';

// An independently authored containment + boundary binding oracle, not a scene snapshot.
function gold(): Architecture {
  const node = (id: string, category: string, parentId?: string, children: string[] = []): ArchitectureNode => ({
    id, label: id, kind: category, category, parentId, children, parameters: {}, evidence: 'source',
    ports: [{ id: 'in', name: 'x', direction: 'in', role: 'data', ordinal: 0 }, { id: 'out', name: 'y', direction: 'out', role: 'data', ordinal: 0 }],
  });
  return {
    schemaVersion: 1, id: 'architecture:gold', label: 'Boundary binding oracle', entry: 'gold:Model', sourceDigest: 'gold-source', irDigest: 'gold-ir', sources: [], diagnostics: [],
    nodes: [node('model', 'container', undefined, ['input', 'block', 'output']), node('input', 'input', 'model'),
      { ...node('block', 'container', 'model', ['norm', 'linear']), repeat: { count: 3, sharing: 'shared' } },
      node('norm', 'norm', 'block'), node('linear', 'linear', 'block'), node('output', 'output', 'model')],
    edges: [
      { id: 'enter', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'norm', portId: 'in' }, tensorId: 'x', role: 'data' },
      { id: 'internal', source: { nodeId: 'norm', portId: 'out' }, target: { nodeId: 'linear', portId: 'in' }, tensorId: 'normalized', role: 'data' },
      { id: 'exit', source: { nodeId: 'linear', portId: 'out' }, target: { nodeId: 'output', portId: 'in' }, tensorId: 'y', role: 'data' },
    ],
  };
}

test('collapsed frontier retains canonical tensors, named port direction and hidden edges', () => {
  const d = createDocument(gold()), scene = buildScene(d);
  assert.deepEqual(scene.hiddenEdges, ['internal']);
  assert.equal(scene.edges.find(e => e.id === 'enter')!.targetId, 'block');
  assert.deepEqual(scene.edges.find(e => e.id === 'enter')!.target, { nodeId: 'norm', portId: 'in' });
  const proxy = scene.nodes.find(n => n.id === 'block')!.ports.find(p => p.direction === 'in')!;
  assert.equal(proxy.proxy, true); assert.equal(proxy.canonicalNodeId, 'norm');
  assert.equal(proxy.canonicalPortId, 'in'); assert.equal(scene.edges[0].tensorId, 'x');
  assert.match(d.id, /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/);
});

test('expansion preserves anchor, unrelated pins, repeat sharing and re-expanded local edits', () => {
  let d = createDocument(gold());
  d = applyVisualBatch(d, [{ type: 'pin', ids: ['output'], pinned: true }]);
  const before = buildScene(d), anchor = before.nodes.find(n => n.id === 'block')!, pin = before.nodes.find(n => n.id === 'output')!;
  const digest = JSON.stringify(d.architecture);
  d = applyVisualBatch(d, [{ type: 'expand', id: 'block', expanded: true }]);
  const expanded = buildScene(d), current = expanded.nodes.find(n => n.id === 'block')!, pinned = expanded.nodes.find(n => n.id === 'output')!;
  assert.equal(current.x, anchor.x); assert.equal(current.y, anchor.y);
  assert.equal(pinned.x, pin.x); assert.equal(pinned.y, pin.y);
  assert.equal(JSON.stringify(d.architecture), digest); assert.equal(current.repeat!.sharing, 'shared');
  assert.equal(expanded.edges.length, 3); assert.equal(expanded.edges.find(e => e.id === 'enter')!.targetId, 'norm');
  d = applyVisualBatch(d, [{ type: 'move', ids: ['norm'], dx: 19, dy: 7 }]);
  const manual = structuredClone(d.layout.norm);
  d = applyVisualBatch(d, [{ type: 'expand', id: 'block', expanded: false }]);
  d = applyVisualBatch(d, [{ type: 'expand', id: 'block', expanded: true }]);
  assert.deepEqual(d.layout.norm, manual);
});

test('batch rejects semantic field injection and stale revision without mutating input', () => {
  const d = createDocument(gold()), original = JSON.stringify(d);
  assert.throws(() => applyVisualBatch(d, [{ type: 'alias', id: 'block', label: 'Safe' }, { type: 'nodeStyle', id: 'block', style: { parameters: { p: 0.8 } } } as never]), /unsupported field/);
  assert.equal(JSON.stringify(d), original);
  assert.throws(() => applyVisualBatch(d, [{ type: 'move', ids: ['block'], dx: Infinity, dy: 0 }]), /finite/);
  assert.throws(() => applyVisualBatch(d, [], 12), RevisionConflict);
  assert.throws(() => applyVisualBatch(d, [{ type: 'nodeStyle', id: 'block', style: { fill: 'url(javascript:x)' } }]), /hexadecimal/);
});

test('history restores a whole batch with monotonic revision and invalidates redo after new edit', () => {
  let h = createHistory(createDocument(gold()));
  h = reduceHistory(h, { type: 'apply', operations: [{ type: 'alias', id: 'block', label: 'New title' }, { type: 'nodeStyle', id: 'block', style: { fill: '#abcdef' } }] });
  assert.equal(h.past.length, 1); assert.equal(h.document.revision, 1);
  h = reduceHistory(h, { type: 'undo' }); assert.equal(h.document.revision, 2); assert.equal(h.document.displayAliases.block, undefined);
  h = reduceHistory(h, { type: 'redo' }); assert.equal(h.document.revision, 3); assert.equal(h.document.nodeStyleOverrides.block.fill, '#abcdef');
  h = reduceHistory(h, { type: 'undo' });
  h = reduceHistory(h, { type: 'apply', operations: [{ type: 'alias', id: 'block', label: 'Replacement' }] });
  assert.equal(h.future.length, 0); assert.equal(h.document.revision, 5);
});

test('publication serializes the edited scene, escapes every user string and excludes editor controls', () => {
  const d = applyVisualBatch(createDocument(gold()), [
    { type: 'alias', id: 'block', label: '<script>alert("x")</script>&' },
    { type: 'nodeStyle', id: 'block', style: { fill: '#abcdef', glyph: 'attention' } },
    { type: 'legend', items: [{ id: 'legend', label: 'Edited & legend', color: '#abcdef', glyph: 'attention' }] },
    { type: 'annotation', annotation: { id: 'note', text: 'Safe <note>', x: 40, y: 600 } },
  ]);
  const scene = buildScene(d), svg = renderSvg(scene);
  assert.equal(svg, renderSvg(buildScene(JSON.parse(JSON.stringify(d)))));
  assert.match(svg, /fill="#abcdef"/); assert.match(svg, /&lt;script&gt;/); assert.doesNotMatch(svg, /<script>/);
  assert.match(svg, /Edited &amp; legend/); assert.match(svg, /Safe &lt;note&gt;/); assert.match(svg, /data-revision="1"/);
  assert.doesNotMatch(svg, /data-expand-id/); assert.match(renderSvg(scene, { interactive: true }), /data-expand-id="block"/);
  assert.equal(scene.nodes.find(n => n.id === 'block')!.label, d.displayAliases.block);
});

test('document loader rejects port mismatch, parent cycle and non-finite imported geometry', () => {
  const d = createDocument(gold());
  assert.equal(JSON.stringify(validateDocument(JSON.parse(JSON.stringify(d)))), JSON.stringify(d));
  const broken = structuredClone(d); broken.architecture.edges[0].target.portId = 'out';
  assert.throws(() => validateDocument(broken), /port binding/);
  const cycle = structuredClone(d); cycle.architecture.nodes[0].parentId = 'block'; cycle.architecture.nodes[2].children.push('model');
  assert.throws(() => validateDocument(cycle), /containment cycle/);
  const position = structuredClone(d); position.layout.input.x = NaN;
  assert.throws(() => validateDocument(position), /finite/);
});

test('selected parent plus child moves once, pinned descendants protect their subtree', () => {
  let d = applyVisualBatch(createDocument(gold()), [{ type: 'expand', id: 'block', expanded: true }]);
  const before = buildScene(d).nodes.find(n => n.id === 'norm')!;
  d = applyVisualBatch(d, [{ type: 'move', ids: ['block', 'norm'], dx: 21, dy: 18 }]);
  const after = buildScene(d).nodes.find(n => n.id === 'norm')!;
  assert.equal(after.x - before.x, 21); assert.equal(after.y - before.y, 18);
  d = applyVisualBatch(d, [{ type: 'pin', ids: ['norm'], pinned: true }]);
  const pinned = buildScene(d).nodes.find(n => n.id === 'norm')!;
  d = applyVisualBatch(d, [{ type: 'move', ids: ['block'], dx: 50, dy: 50 }]);
  assert.deepEqual(buildScene(d).nodes.find(n => n.id === 'norm'), pinned);
});

test('repeated toggles restore neighbor geometry without drifting or losing a collapsed user move', () => {
  let d = createDocument(gold());
  d = applyVisualBatch(d, [{ type: 'expand', id: 'block', expanded: true }]);
  const expandedY = buildScene(d).nodes.find(n => n.id === 'output')!.y;
  for (let i = 0; i < 3; i++) {
    d = applyVisualBatch(d, [{ type: 'expand', id: 'block', expanded: false }]);
    d = applyVisualBatch(d, [{ type: 'expand', id: 'block', expanded: true }]);
    assert.equal(buildScene(d).nodes.find(n => n.id === 'output')!.y, expandedY);
  }
  d = applyVisualBatch(d, [{ type: 'expand', id: 'block', expanded: false }, { type: 'move', ids: ['output'], dx: 14, dy: 25 }]);
  d = applyVisualBatch(d, [{ type: 'expand', id: 'block', expanded: true }]);
  assert.equal(buildScene(d).nodes.find(n => n.id === 'output')!.y, expandedY + 25);
});

test('long Chinese aliases and annotations retain text while their geometry grows', () => {
  const label = '这是包含完整说明与独立层级关系的注意力模块'.repeat(4);
  const note = '保留用户全部说明内容并依据字宽自动换行。'.repeat(5);
  const d = applyVisualBatch(createDocument(gold()), [{ type: 'alias', id: 'block', label }, { type: 'annotation', annotation: { id: 'long-note', text: note, x: 30, y: 20, width: 160 } }]);
  const scene = buildScene(d), node = scene.nodes.find(n => n.id === 'block')!, annotation = scene.annotations[0];
  const rows = wrapText(label, node.width - 62);
  assert.ok(rows.length > 2); assert.ok(rows.every(row => textWidth(row) <= node.width - 62));
  assert.equal(rows.join(''), label); assert.ok(node.height >= rows.length * 16 + 26);
  assert.ok(annotation.height > 34); assert.equal(wrapText(note, 140, 11).join(''), note);
  assert.ok(renderSvg(scene).includes('这是包含完整说明'));
});


test('source refresh preserves unique identity presentation and resets source undo boundary', () => {
  let prior = createDocument(gold());
  prior = applyVisualBatch(prior, [
    { type: 'expand', id: 'block', expanded: true },
    { type: 'alias', id: 'linear', label: 'My Projection' },
    { type: 'nodeStyle', id: 'linear', style: { fill: '#123456' } },
    { type: 'edgeStyle', id: 'internal', style: { width: 3 } },
    { type: 'move', ids: ['linear'], dx: 28, dy: 12 },
    { type: 'pin', ids: ['linear'], pinned: true },
  ]);
  const architecture = structuredClone(prior.architecture);
  architecture.sourceDigest = 'new-source'; architecture.irDigest = 'new-ir';
  architecture.nodes.find(n => n.id === 'linear')!.parameters.p = 0.2;
  const refreshed = reconcileDocument(prior, architecture);
  assert.notEqual(refreshed.document.id, prior.id);
  assert.equal(refreshed.document.sourceBindingDigest, 'new-source');
  assert.equal(refreshed.document.displayAliases.linear, 'My Projection');
  assert.deepEqual(refreshed.document.nodeStyleOverrides, prior.nodeStyleOverrides);
  assert.deepEqual(refreshed.document.edgeStyleOverrides, prior.edgeStyleOverrides);
  assert.deepEqual(refreshed.document.layout.linear, prior.layout.linear);
  assert.deepEqual(refreshed.document.layoutByFrontier, prior.layoutByFrontier);
  assert.deepEqual(refreshed.document.pinnedObjects, ['linear']);
  const history = createHistory(refreshed.document);
  assert.equal(history.past.length, 0);
  assert.equal(reduceHistory(history, { type: 'undo' }).document.architecture.nodes.find(n => n.id === 'linear')!.parameters.p, 0.2);
  architecture.nodes.find(n => n.id === 'linear')!.instanceId = 'different-source-instance';
  const changed = reconcileDocument(prior, architecture);
  assert.deepEqual(changed.removedNodeIds, ['linear']);
  assert.equal(changed.document.displayAliases.linear, undefined);
  assert.equal(changed.document.edgeStyleOverrides.internal, undefined);
  assert.deepEqual(changed.document.pinnedObjects, []);
});

test('a rebound edge cannot inherit a style from its previous tensor binding', () => {
  const prior = applyVisualBatch(createDocument(gold()), [
    { type: 'expand', id: 'block', expanded: true },
    { type: 'alias', id: 'linear', label: 'Kept consumer' },
    { type: 'nodeStyle', id: 'linear', style: { fill: '#ece3f4' } },
    { type: 'move', ids: ['linear'], dx: 24, dy: 16 },
    { type: 'pin', ids: ['linear'], pinned: true },
    { type: 'edgeStyle', id: 'internal', style: { stroke: '#bb3322', width: 4 } },
    { type: 'edgeStyle', id: 'exit', style: { dashed: true } },
  ]);
  const frozen = JSON.stringify(prior);
  const architecture = structuredClone(prior.architecture);
  architecture.sourceDigest = 'rebound-source'; architecture.irDigest = 'rebound-ir';
  architecture.edges[1].source = { nodeId: 'input', portId: 'out' };
  architecture.edges[1].tensorId = 'x';
  const result = reconcileDocument(prior, architecture);
  assert.equal(result.document.edgeStyleOverrides.internal, undefined);
  assert.deepEqual(result.document.edgeStyleOverrides.exit, { dashed: true });
  assert.deepEqual(result.document.layout.linear, prior.layout.linear);
  assert.equal(result.document.displayAliases.linear, 'Kept consumer');
  assert.deepEqual(result.document.nodeStyleOverrides.linear, { fill: '#ece3f4' });
  assert.deepEqual(result.document.pinnedObjects, ['linear']);
  const scene = buildScene(result.document);
  assert.equal(scene.edges.find(e => e.id === 'internal')!.source.nodeId, 'input');
  assert.notEqual(scene.edges.find(e => e.id === 'internal')!.stroke, '#bb3322');
  assert.equal(JSON.stringify(prior), frozen);
});

test('projected parallel edges retain differing canonical styles instead of discarding them', () => {
  const architecture = gold();
  architecture.edges.push({ ...structuredClone(architecture.edges[0]), id: 'second-enter', target: { nodeId: 'linear', portId: 'in' } });
  let document = createDocument(architecture);
  assert.equal(buildScene(document).edges.filter(e => e.tensorId === 'x').length, 1);
  document = applyVisualBatch(document, [{ type: 'edgeStyle', id: 'second-enter', style: { stroke: '#bb3322', width: 3, dashed: true } }]);
  const projected = buildScene(document).edges.filter(e => e.tensorId === 'x');
  assert.equal(projected.length, 2);
  const edited = projected.find(e => e.canonicalEdgeIds.includes('second-enter'))!;
  assert.equal(edited.stroke, '#bb3322'); assert.equal(edited.width, 3); assert.equal(edited.dashed, true);
  assert.deepEqual(projected.flatMap(e => e.canonicalEdgeIds).sort(), ['enter', 'second-enter']);
});
