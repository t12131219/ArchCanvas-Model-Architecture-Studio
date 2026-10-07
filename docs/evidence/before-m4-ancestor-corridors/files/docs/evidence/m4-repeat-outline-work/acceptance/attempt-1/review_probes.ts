/** Independent reviewer probes. Geometry expectations use literal public-card
 * rectangles, never the product outline/side/intersection helpers. */
import assert from 'node:assert/strict';
import { buildScene, buildExportScene, createDocument, applyVisualBatch, renderSvg } from '../../../../../studio/src/core/index.ts';
import { createOrthogonalRouter } from '../../../../../studio/src/core/orthogonalRouter.ts';
import type { Architecture, ArchitectureNode, SceneNode } from '../../../../../studio/src/core/types.ts';

const repeat = { count: 2, sharing: 'independent' as const };
const node = (id: string, options: Partial<ArchitectureNode> = {}): ArchitectureNode => ({ id, label: id, kind: 'Linear', category: 'linear', evidence: 'source',
  parameters: {}, children: [], ports: [{ id: `${id}:in`, name: 'input', direction: 'in', role: 'memory', ordinal: 0 },
    { id: `${id}:out`, name: 'output', direction: 'out', role: 'memory', ordinal: 0 }], ...options });
const graph = (nodes: ArchitectureNode[], edges: Architecture['edges']): Architecture => ({ schemaVersion: 1, id: 'review-graph', label: 'Review graph', entry: 'review:Model',
  sourceDigest: 'review-source', irDigest: 'review-ir', sources: [], diagnostics: [], nodes, edges });
function portFor(scene: ReturnType<typeof buildScene>, owner: string, edge: string, direction: 'in' | 'out') {
  const ports = scene.nodes.find(node => node.id === owner)!.ports.filter(port => port.direction === direction && port.canonicalEdgeIds.includes(edge));
  assert.equal(ports.length, 1); return ports[0];
}
function exposed(scene: ReturnType<typeof buildScene>, owner: string, p: { x: number; y: number }) {
  const n = scene.nodes.find(n => n.id === owner)!;
  const offsets = n.repeat && !n.expanded ? [0, 3.5, 7] : [0];
  const rectangles = offsets.map(offset => ({ x: n.x + offset, y: n.y + offset, w: n.width, h: n.height }));
  assert.ok(!rectangles.some(r => p.x > r.x + .001 && p.x < r.x + r.w - .001 && p.y > r.y + .001 && p.y < r.y + r.h - .001));
  assert.ok(rectangles.some(r => (Math.abs(p.x - r.x) < .001 || Math.abs(p.x - r.x - r.w) < .001) && p.y >= r.y && p.y <= r.y + r.h ||
    (Math.abs(p.y - r.y) < .001 || Math.abs(p.y - r.y - r.h) < .001) && p.x >= r.x && p.x <= r.x + r.w));
}
const results: object[] = [];
// Same canonical output and input are exercised on both sides and in both
// authored orders, including detail export reuse after translating the stack.
for (const reverse of [false, true]) {
  const nodes = [node('root', { category: 'container', children: ['stack', 'below', 'right', 'far'] }),
    node('stack', { parentId: 'root', repeat }), node('below', { parentId: 'root' }), node('right', { parentId: 'root' }), node('far', { parentId: 'root' })];
  const edges = ['below', 'right'].map(target => ({ id: `to-${target}`, source: { nodeId: 'stack', portId: 'stack:out' }, target: { nodeId: target, portId: `${target}:in` }, role: 'memory' as const, tensorId: 'shared' }));
  if (reverse) edges.reverse();
  let document = createDocument(graph(nodes, edges));
  document = applyVisualBatch(document, [{ type: 'expand', id: 'root', expanded: true }]);
  document.layout.stack = { x: 30, y: 90 }; document.layout.below = { x: 30, y: 320 }; document.layout.right = { x: 450, y: 90 }; document.layout.far = { x: 700, y: 600 };
  const before = JSON.stringify(document);
  for (const [label, scene] of [['full', buildScene(document)], ['detail', buildExportScene(document, { nodeId: 'root' })]] as const) {
    const a = portFor(scene, 'stack', 'to-below', 'out'), b = portFor(scene, 'stack', 'to-right', 'out');
    assert.notEqual(a.id, b.id); assert.deepEqual(a.canonicalBindings, [{ nodeId: 'stack', portId: 'stack:out' }]);
    assert.deepEqual(b.canonicalBindings, a.canonicalBindings); assert.deepEqual(a.canonicalEdgeIds, ['to-below']); assert.deepEqual(b.canonicalEdgeIds, ['to-right']);
    exposed(scene, 'stack', a); exposed(scene, 'stack', b);
    assert.equal(scene.edges.length, 2);
    const publicSvg = renderSvg(scene, { interactive: true });
    assert.ok(publicSvg.includes(`data-port-id="${a.id}"`)); assert.ok(publicSvg.includes(`data-port-id="${b.id}"`));
    results.push({ probe: 'side-specific-order-and-detail', reverse, label, ids: [a.id, b.id], points: [a, b].map(p => ({ x: p.x, y: p.y })), canonicalCoverageExact: true });
  }
  assert.equal(JSON.stringify(document), before);
}
// Bounding-envelope blank corner is empty; broad-phase owner envelopes must
// not become real rectangle obstacles or false overlap diagnostics.
const sn = (id: string, x: number, y: number, width: number, height: number, repeating = false): SceneNode => ({ id, x, y, width, height,
  localX: x, localY: y, label: id, subtitle: '', kind: 'Linear', category: 'linear', fill: '#fff', stroke: '#000', glyph: 'operator',
  evidence: 'source', headerHeight: height, expanded: false, expandable: false, pinned: false, ports: [], ...(repeating ? { repeat } : {}) });
{
  const nodes = [sn('stack', 0, 0, 20, 20, true), sn('blank', .5, 23, 2, 2), sn('source', -20, 10, 10, 10), sn('target', -20, 40, 10, 10)];
  const router = createOrthogonalRouter(nodes);
  assert.deepEqual(router.overlaps, []);
  const req = { sourceId: 'source', targetId: 'target', start: { x: -15, y: 20 }, end: { x: -15, y: 40 }, preferredPath: 'M -15 20 V 40' };
  const routed = router(req); assert.equal(routed.changed, false); assert.deepEqual(routed.blockedBy, []);
  results.push({ probe: 'empty-envelope-corner-does-not-count-as-overlap', overlaps: router.overlaps, routed });
}
// Newly generated detail incoming/outgoing proxy ports must retain exact
// canonical identities even if full-scene ancestor adapters hide both edges.
{
  const nodes = [node('root', { category: 'container', children: ['selected', 'other'] }), node('selected', { category: 'container', parentId: 'root', children: ['stack'] }),
    node('stack', { category: 'container', parentId: 'selected', children: ['leaf'], repeat }), node('leaf', { parentId: 'stack' }), node('other', { parentId: 'root' })];
  const edges = [
    { id: 'entry', source: { nodeId: 'root', portId: 'root:out' }, target: { nodeId: 'leaf', portId: 'leaf:in' }, role: 'memory' as const, tensorId: 'entry-tensor' },
    { id: 'exit', source: { nodeId: 'leaf', portId: 'leaf:out' }, target: { nodeId: 'root', portId: 'root:in' }, role: 'memory' as const, tensorId: 'exit-tensor' },
  ];
  const document = applyVisualBatch(createDocument(graph(nodes, edges)), [{ type: 'expand', id: 'selected', expanded: true }]);
  const before = JSON.stringify(document), detail = buildExportScene(document, { nodeId: 'selected' });
  const entry = portFor(detail, 'stack', 'entry', 'in'), exit = portFor(detail, 'stack', 'exit', 'out');
  exposed(detail, 'stack', entry); exposed(detail, 'stack', exit);
  assert.deepEqual(entry.canonicalBindings, [{ nodeId: 'leaf', portId: 'leaf:in' }]);
  assert.deepEqual(exit.canonicalBindings, [{ nodeId: 'leaf', portId: 'leaf:out' }]);
  assert.ok(entry.id.startsWith('detail:')); assert.ok(exit.id.startsWith('detail:'));
  assert.deepEqual(detail.exportScope!.boundaryEdges.map(edge => edge.edgeId), ['entry', 'exit']);
  assert.equal(JSON.stringify(document), before);
  results.push({ probe: 'detail-both-directions-fallback', ports: [entry, exit], scope: detail.exportScope, diagnostics: detail.diagnostics });
}
console.log(JSON.stringify({ status: 'passed', probeResults: results, modelExecution: false, browserActions: false, limits: 'Targeted deterministic code probes only; not pixels, full suite, runtime semantics or publication acceptance.' }, null, 2));
