import test from 'node:test';
import { normalizeDefaultMemoryLabels } from './historical-memory-caption-compat.ts';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import type { CanvasDocument, Scene } from '../src/core/types.ts';
import { analyzeSvg, assertHealthy, frontCards, ordinaryPorts, parseSvg, penetrates } from '../../docs/evidence/m4-repeat-outline-work/oracle/oracle.ts';
import { architecture, canonicalNode, cornerArchitecture, hierarchyArchitecture, manualScene, mixedSideArchitecture, repeat, sceneNode } from '../../docs/evidence/m4-repeat-outline-work/oracle/fixtures.ts';
import { verifyRefinement as verifyCorridorRefinement } from '../../docs/evidence/m4-ancestor-corridor-work/ancestor-corridor-oracle.ts';
import { assertRefinement as verifyCollapsedResidualRefinement, stats as residualRouteStats } from '../../docs/evidence/m4-collapsed-residual-work/acceptance/oracle.ts';

// The explicit sealed target is used only to demonstrate this suite failing on
// archived formal ChS. Normal tests always run the current formal product.
// Neither target imports a failed prototype or supplies a geometry oracle.
const core = process.env.ARCHCANVAS_REPEAT_ORACLE_BASELINE === 'sealed-ChS'
  ? new URL('../../docs/evidence/before-m4-repeat-outline/files/studio/src/core/', import.meta.url) : new URL('../src/core/', import.meta.url);
const { buildScene, buildExportScene, createDocument, applyVisualBatch, createHistory, reduceHistory, renderSvg } = await import(new URL('index.ts', core).href) as typeof import('../src/core/index.ts');
const { createOrthogonalRouter } = await import(new URL('orthogonalRouter.ts', core).href) as typeof import('../src/core/orthogonalRouter.ts');
const { prepareMovePreview, previewMoveScene } = await import(new URL('movePreview.ts', core).href) as typeof import('../src/core/movePreview.ts');
const evidence = new URL('../../docs/evidence/m4-repeat-outline-work/oracle/', import.meta.url);
const project = new URL('../../', import.meta.url);
const sha256 = (value: string) => createHash('sha256').update(value).digest('hex');
type BeforeRecord = {
  caseId: string; detailNodeId?: string; inputPath: string; inputSha256: string; svgPath: string; scenePath: string;
  frontCards: ReturnType<typeof frontCards>; ordinaryPorts: ReturnType<typeof ordinaryPorts>;
  sourceDigest: string; irDigest: string; sourceFactsSha256: string; hiddenEdges: string[];
  renderedBindings: unknown[]; exportScope?: Scene['exportScope']; report: ReturnType<typeof analyzeSvg>;
};
const before = JSON.parse(readFileSync(new URL('before.json', evidence), 'utf8')) as { stableSourceDuringCapture: boolean; records: BeforeRecord[] };
assert.equal(before.stableSourceDuringCapture, true);
const frontiers = before.records.filter(record => record.detailNodeId === undefined);
assert.equal(frontiers.length, 9, 'Nine independent source-bound frontiers must remain covered');

function semanticBindings(scene: Scene) {
  return scene.edges.map(edge => ({ id: edge.id, canonicalEdgeIds: edge.canonicalEdgeIds, source: edge.source, target: edge.target, tensorId: edge.tensorId, role: edge.role }));
}
function checkSourceBound(record: BeforeRecord, scene: Scene, svg: string) {
  assert.deepEqual(frontCards(scene, svg), record.frontCards, 'Nominal front/card anchors, expansion and pins changed');
  assert.deepEqual(ordinaryPorts(scene), record.ordinaryPorts, 'Nonrepeat or expanded display-port geometry changed');
  assert.equal(scene.sourceDigest, record.sourceDigest); assert.equal(scene.irDigest, record.irDigest);
  assert.equal(sha256(JSON.stringify(scene.sourceFacts)), record.sourceFactsSha256);
  assert.deepEqual(semanticBindings(scene), record.renderedBindings, 'Canonical tensor or port coverage changed');
  assert.deepEqual(scene.hiddenEdges, record.hiddenEdges);
  if (record.exportScope) assert.deepEqual(scene.exportScope, record.exportScope);
  const metadata = parseSvg(svg).metadata;
  assert.equal(metadata.sourceDigest, record.sourceDigest); assert.equal(metadata.irDigest, record.irDigest);
  assert.deepEqual(metadata.sourceFacts, scene.sourceFacts);
  assertHealthy(scene, svg);
}

test('independent final-SVG oracle detects all six sealed ChS stack intrusions and three buried frontier outputs', () => {
  const bad = before.records.filter(record => record.report.stackHits.length);
  assert.equal(bad.length, 6);
  assert.equal(frontiers.filter(record => record.report.buriedPorts.length).length, 3);
  for (const record of bad) {
    const raw = readFileSync(new URL(record.inputPath, project), 'utf8'), document = JSON.parse(raw) as CanvasDocument;
    // Scene identity supplies canonical edge/port ownership; geometry comes
    // exclusively from the archived public SVG, not a product outline helper.
    const oldScene = JSON.parse(readFileSync(new URL(record.scenePath, evidence), 'utf8')) as Scene;
    assert.ok(record.report.stackHits.every(hit => hit.ownEndpointBody));
    const svg = readFileSync(new URL(record.svgPath, evidence), 'utf8');
    assert.ok(parseSvg(svg).cards.size > 0); assert.equal(sha256(raw), record.inputSha256);
    assert.equal(document.architecture.sourceDigest, record.sourceDigest);
    assert.deepEqual(analyzeSvg(oldScene, svg), record.report);
    assert.throws(() => assertHealthy(oldScene, svg), /ports are inside/);
  }
});
// Keeping this negative control data-only avoids silently rerunning archived
// product code during ordinary tests. The explicit baseline run below records
// the same repair assertions failing against the archived implementation.

for (const record of frontiers) {
  test(`source-bound final SVG stack/endpoint/Canvas invariants: ${record.caseId}`, () => {
    const path = new URL(record.inputPath, project), raw = readFileSync(path, 'utf8');
    assert.equal(sha256(raw), record.inputSha256);
    const document = JSON.parse(raw) as CanvasDocument, original = JSON.stringify(document);
    const scene = buildScene(document), svg = renderSvg(scene);
    checkSourceBound(record, scene, svg);
    if (!scene.nodes.some(node => node.repeat && !node.expanded)) {
      if (process.env.ARCHCANVAS_REPEAT_ORACLE_BASELINE !== 'sealed-ChS' && record.caseId === 'residual_cnn-level1-paper-180') {
        // This later revision deliberately shortens the proxy residual. Use
        // this suite's own original revision-9 Scene, not a normalized newer
        // capture. Every card/port/branch and pair-local safety remains frozen.
        const prior = JSON.parse(readFileSync(new URL(record.scenePath, evidence), 'utf8')) as Scene;
        assert.equal(prior.revision, document.revision);
        verifyCollapsedResidualRefinement(prior, JSON.parse(JSON.stringify(scene)), svg);
        const canonical = new Map(document.architecture.nodes.map(node => [node.id, node]));
        const changed = scene.edges.filter(edge => edge.path !== prior.edges.find(item => item.id === edge.id)!.path);
        assert.equal(changed.length, 1, 'Only the independently identified proxy residual may change');
        for (const edge of changed) {
          assert.equal(edge.role, 'residual');
          const owner = scene.nodes.find(node => node.id === edge.targetId)!;
          assert.ok(owner.expandable && !owner.expanded && edge.target.nodeId !== owner.id);
          let ancestor = canonical.get(edge.target.nodeId)?.parentId;
          while (ancestor && ancestor !== owner.id) ancestor = canonical.get(ancestor)?.parentId;
          assert.equal(ancestor, owner.id, 'The real target must be hidden inside this collapsed owner');
          const oldRoute = residualRouteStats(prior.edges.find(item => item.id === edge.id)!.path);
          assert.ok(Math.abs(oldRoute.length - 235.4) < 1e-9);
          assert.equal(oldRoute.bends, 4);
          assert.deepEqual(residualRouteStats(edge.path), { length: 38, bends: 0 });
        }
      } else if (process.env.ARCHCANVAS_REPEAT_ORACLE_BASELINE !== 'sealed-ChS' && record.caseId === 'residual_cnn-level2-paper-180') {
        // General geometry shortening now removes this independently measured
        // lane detour. Keep the original SVG immutable and compare every other
        // field after normalizing only this route and its derived caption.
        const prior = JSON.parse(readFileSync(new URL(record.scenePath, evidence), 'utf8')) as Scene;
        verifyCollapsedResidualRefinement(prior, JSON.parse(JSON.stringify(scene)), svg);
        const changed = scene.edges.filter(edge => edge.path !== prior.edges.find(item => item.id === edge.id)!.path);
        assert.deepEqual(changed.map(edge => edge.id), ['edge:18']);
        const shortened = residualRouteStats(changed[0].path);
        assert.ok(Math.abs(shortened.length - 831.4) < 1e-9);
        assert.equal(shortened.bends, 4);
        const protectedScene = JSON.parse(JSON.stringify(scene)) as Scene;
        const old = prior.edges.find(edge => edge.id === 'edge:18')!;
        const current = protectedScene.edges.find(edge => edge.id === 'edge:18')!;
        current.path = old.path; current.labelX = old.labelX; current.labelY = old.labelY;
        assert.deepEqual(protectedScene, prior);
        assert.equal(renderSvg(protectedScene), readFileSync(new URL(record.svgPath, evidence), 'utf8'));
      } else if (process.env.ARCHCANVAS_REPEAT_ORACLE_BASELINE !== 'sealed-ChS' && ['transformer-level1-paper-180', 'transformer-level2-paper-180', 'transformer-level3-paper-180'].includes(record.caseId)) {
        // These three current frontiers may improve routing. The archived BG
        // cards, ports, semantic branches and protected counts remain frozen.
        // The explicit sealed-ChS negative-control run retains its old scope.
        const baseline = new URL('../../docs/evidence/m4-ancestor-corridor-work/baseline/', import.meta.url);
        const prior = JSON.parse(readFileSync(new URL(`${record.caseId}.scene.json`, baseline), 'utf8')) as Scene;
        const historical = normalizeDefaultMemoryLabels(document, scene, prior);
        verifyCorridorRefinement(prior, historical, renderSvg(historical), readFileSync(new URL(`${record.caseId}.svg`, baseline), 'utf8'));
      } else assert.equal(svg, readFileSync(new URL(record.svgPath, evidence), 'utf8'), 'Frontier without any stack changed its published SVG');
    }
    assert.equal(renderSvg(buildExportScene(document)), svg, 'Full export and Canvas disagree');
    assert.deepEqual(analyzeSvg(scene, renderSvg(scene, { interactive: true })), analyzeSvg(scene, svg));
    for (const detail of before.records.filter(item => item.caseId === record.caseId && item.detailNodeId !== undefined)) {
      const exported = buildExportScene(document, { nodeId: detail.detailNodeId });
      checkSourceBound(detail, exported, renderSvg(exported));
      assert.equal(renderSvg(exported), renderSvg(buildExportScene(document, { nodeId: detail.detailNodeId })));
      const scope = exported.exportScope!;
      assert.deepEqual([...scope.internalEdgeIds, ...scope.boundaryEdges.map(edge => edge.edgeId), ...scope.omittedEdgeIds].sort(), document.architecture.edges.map(edge => edge.id).sort());
    }
    assert.equal(JSON.stringify(document), original, 'Whole CanvasDocument changed while rendering');
    assert.equal(readFileSync(path, 'utf8'), raw, 'Sealed Canvas bytes changed');
  });
}

test('reported CNN bottom and Transformer memory examples attach to exposed card union', () => {
  for (const [caseId, edgeId, expected] of [
    ['residual_cnn-level0-paper-180', 'edge:20', { x: 177, y: 423 }],
    ['transformer-level0-paper-180', 'edge:44', { x: 281, y: 444.1 }],
  ] as const) {
    const record = frontiers.find(record => record.caseId === caseId)!;
    const document = JSON.parse(readFileSync(new URL(record.inputPath, project), 'utf8')) as CanvasDocument;
    const scene = buildScene(document), geometry = parseSvg(renderSvg(scene));
    assert.deepEqual(geometry.paths.get(edgeId)![0], expected);
    assertHealthy(scene, renderSvg(scene));
  }
});

test('near-left bottom outputs follow actual +0/+3.5/+7 cards instead of empty envelope corners', () => {
  const document = createDocument(cornerArchitecture());
  document.layout.stack = { x: 100, y: 100 }; document.layout.consumer = { x: 100, y: 320 };
  const original = JSON.stringify(document), scene = buildScene(document), svg = renderSvg(scene), geometry = parseSvg(svg);
  const node = scene.nodes.find(node => node.id === 'stack')!, front = geometry.cards.get('stack')!.at(-1)!;
  const offsets = [0, 3.5, 7];
  for (let index = 0; index < offsets.length; index++) {
    const port = node.ports.find(port => port.canonicalPortId === `out-${index}`)!;
    const circle = geometry.circles.get(JSON.stringify(['stack', port.id]))!;
    assert.ok(circle.x - front.x > index * 3.5 && circle.x - front.x < (index + 1) * 3.5);
    assert.equal(circle.y, front.y + front.height + offsets[index]);
  }
  assertHealthy(scene, svg); assert.equal(JSON.stringify(document), original);
  // Coherently move a corner path endpoint and its circle into the envelope's
  // blank lower-left corner. Endpoint agreement alone must not accept this.
  const polluted = structuredClone(scene), first = polluted.nodes.find(node => node.id === 'stack')!.ports.find(port => port.canonicalPortId === 'out-0')!;
  first.y = front.y + front.height + 7;
  polluted.edges.find(edge => edge.id === 'corner-0')!.path = polluted.edges.find(edge => edge.id === 'corner-0')!.path.replace(/^M\s+[-\d.]+\s+[-\d.]+/, `M ${first.x} ${first.y}`);
  assert.ok(analyzeSvg(polluted, renderSvg(polluted)).floatingPorts.some(port => port.portId === first.id), 'Independent oracle accepted an invented card corner');
});

test('same canonical memory output has coherent bottom and right display ports for multiple consumers', () => {
  const document = createDocument(mixedSideArchitecture());
  document.layout.stack = { x: 100, y: 100 }; document.layout.below = { x: 100, y: 340 }; document.layout.right = { x: 500, y: 100 };
  const original = JSON.stringify(document), scene = buildScene(document), svg = renderSvg(scene), geometry = parseSvg(svg);
  const source = scene.nodes.find(node => node.id === 'stack')!, front = geometry.cards.get('stack')!.at(-1)!;
  const bottom = geometry.paths.get('to-below')![0], right = geometry.paths.get('to-right')![0];
  assert.equal(bottom.y, front.y + front.height + 7); assert.equal(right.x, front.x + front.width + 7);
  assert.notDeepEqual(bottom, right); assertHealthy(scene, svg);
  assert.deepEqual(scene.edges.map(edge => edge.source), [{ nodeId: 'stack', portId: 'out' }, { nodeId: 'stack', portId: 'out' }]);
  assert.equal(JSON.stringify(document), original);
  const corrupted = structuredClone(scene), ports = corrupted.nodes.find(node => node.id === 'stack')!.ports.filter(port => port.canonicalPortId === 'out');
  for (const port of ports) { port.x = right.x; port.y = right.y; }
  assert.ok(analyzeSvg(corrupted, renderSvg(corrupted)).endpointMisses.some(miss => miss.edgeId === 'to-below'), 'Oracle accepted later mutation of a previously bound circle');
});

test('unrelated backplate-only obstacle and source own-stack reentry are independently rejected and rerouted', () => {
  for (const [nodes, preferredPath, start, end, expectedOwner] of [
    [[sceneNode('a', 0, 0), sceneNode('b', 100, 150), sceneNode('stack', 40, 80, 40, 20, true)], 'M 10 20 V 104 H 110 V 150', { x: 10, y: 20 }, { x: 110, y: 150 }, 'stack'],
    [[sceneNode('a', 0, 0, 20, 20, true), sceneNode('b', 100, 100)], 'M 10 27 V 40 H 24 V 10 H 110 V 100', { x: 10, y: 27 }, { x: 110, y: 100 }, 'a'],
  ] as const) {
    const beforeScene = manualScene([...nodes], preferredPath), beforeGeometry = parseSvg(renderSvg(beforeScene));
    const oldPoints = beforeGeometry.paths.get('route')!, cards = beforeGeometry.cards.get(expectedOwner)!;
    assert.ok(cards.slice(0, 2).some(rectangle => oldPoints.slice(1).some((point, index) => penetrates(oldPoints[index], point, rectangle))));
    assert.ok(!oldPoints.slice(1).some((point, index) => penetrates(oldPoints[index], point, cards.at(-1)!)), 'Counterexample should miss the front card');
    const router = createOrthogonalRouter(nodes), request = { sourceId: 'a', targetId: 'b', start, end, preferredPath, tensorId: 'tensor' };
    for (const routed of [router(request), router.batch([request])[0]]) {
      assert.equal(routed.changed, true); assert.deepEqual(routed.blockedBy, []);
      const published = manualScene([...nodes], routed.path), geometry = parseSvg(renderSvg(published)), points = geometry.paths.get('route')!;
      for (const rectangle of geometry.cards.get(expectedOwner)!) assert.ok(!points.slice(1).some((point, index) => penetrates(points[index], point, rectangle)), `Accepted ${expectedOwner} penetration`);
      assert.deepEqual(points[0], start); assert.deepEqual(points.at(-1), end);
    }
  }
});

test('overlapping Repeat ownership is reported once and an endpoint covered by another body remains honestly blocked', () => {
  const overlap = createOrthogonalRouter([sceneNode('first', 0, 0, 20, 20, true), sceneNode('second', 23, 23, 20, 20, true)]);
  assert.deepEqual(overlap.overlaps, [{ first: 'first', second: 'second' }]);
  const nodes = [sceneNode('a', 0, 0, 20, 20, true), sceneNode('b', 100, 100), sceneNode('cover', 8, 26, 4, 4)];
  const result = createOrthogonalRouter(nodes)({ sourceId: 'a', targetId: 'b', start: { x: 10, y: 27 }, end: { x: 110, y: 100 }, preferredPath: 'M 10 27 V 60 H 110 V 100' });
  assert.ok(result.blockedBy.includes('cover')); assert.equal(new Set(result.blockedBy).size, result.blockedBy.length);
});

test('detail fallback ports and translated stacks retain canonical boundary coverage and exposed endpoints', () => {
  const graph = architecture([
    canonicalNode('model', { category: 'container', children: ['selected', 'other'] }),
    canonicalNode('selected', { category: 'container', parentId: 'model', children: ['stack'] }),
    canonicalNode('stack', { category: 'container', parentId: 'selected', children: ['leaf'], repeat }),
    canonicalNode('leaf', { parentId: 'stack' }), canonicalNode('other', { parentId: 'model' }),
  ], [{ id: 'implicit-exit', source: { nodeId: 'leaf', portId: 'out' }, target: { nodeId: 'model', portId: 'in' }, tensorId: 'fallback-tensor', role: 'data' }]);
  const document = applyVisualBatch(createDocument(graph), [{ type: 'expand', id: 'selected', expanded: true }]);
  const original = JSON.stringify(document), full = buildScene(document), detail = buildExportScene(document, { nodeId: 'selected' });
  assert.equal(full.edges.length, 0); assert.ok(full.hiddenEdges.includes('implicit-exit'));
  assertHealthy(detail, renderSvg(detail));
  const node = detail.nodes.find(node => node.id === 'stack')!, originalNode = full.nodes.find(node => node.id === 'stack')!;
  assert.ok(node.x !== originalNode.x || node.y !== originalNode.y, 'Fixture did not exercise translation');
  const port = node.ports.find(port => port.canonicalEdgeIds.includes('implicit-exit'))!;
  assert.ok(port.id.startsWith('detail:')); assert.equal(port.y, node.y + node.height + 7);
  assert.deepEqual(port.canonicalBindings, [{ nodeId: 'leaf', portId: 'out' }]);
  assert.deepEqual(detail.exportScope!.boundaryEdges.map(edge => edge.edgeId), ['implicit-exit']);
  assert.equal(JSON.stringify(document), original);
});

test('expanded/nonrepeat ports, in-place expansion, pins and move preview/history preserve presentation contracts', () => {
  let document = createDocument(hierarchyArchitecture());
  // Keep the pinned consumer beyond the expanded subtree. Pinning a body on
  // top of an expanding child intentionally leaves an unsatisfiable layout.
  document.layout.output = { x: 30, y: 800 };
  document = applyVisualBatch(document, [{ type: 'pin', ids: ['output'], pinned: true }]);
  const original = JSON.stringify(document), collapsed = buildScene(document), anchor = collapsed.nodes.find(node => node.id === 'stack')!, pinned = collapsed.nodes.find(node => node.id === 'output')!;
  assertHealthy(collapsed, renderSvg(collapsed));
  const top = anchor.ports.find(port => port.direction === 'in')!; assert.equal(top.y, anchor.y);
  const expandedDocument = applyVisualBatch(document, [{ type: 'expand', id: 'stack', expanded: true }]);
  const expanded = buildScene(expandedDocument), current = expanded.nodes.find(node => node.id === 'stack')!;
  assert.equal(current.x, anchor.x); assert.equal(current.y, anchor.y); assert.deepEqual(expanded.nodes.find(node => node.id === 'output'), pinned);
  assertHealthy(expanded, renderSvg(expanded)); assert.equal(parseSvg(renderSvg(expanded)).cards.get('stack')!.length, 1);
  const plain = structuredClone(expandedDocument); delete plain.architecture.nodes.find(node => node.id === 'stack')!.repeat;
  assert.deepEqual(ordinaryPorts(buildScene(plain)), ordinaryPorts(expanded));
  assert.deepEqual(buildScene(plain).edges.map(edge => edge.path), expanded.edges.map(edge => edge.path));
  const edited = applyVisualBatch(expandedDocument, [{ type: 'move', ids: ['leaf'], dx: 19, dy: 7 }]);
  const restored = applyVisualBatch(applyVisualBatch(edited, [{ type: 'expand', id: 'stack', expanded: false }]), [{ type: 'expand', id: 'stack', expanded: true }]);
  assert.deepEqual(restored.layout.leaf, edited.layout.leaf); assert.deepEqual(restored.architecture, document.architecture);
  const preview = previewMoveScene(prepareMovePreview(document, ['stack']), 21, 13);
  const history = reduceHistory(createHistory(document), { type: 'apply', baseRevision: document.revision, operations: [{ type: 'move', ids: ['stack'], dx: 21, dy: 13 }] });
  assert.equal(renderSvg(preview), renderSvg(buildScene(history.document))); assertHealthy(preview, renderSvg(preview));
  const undo = reduceHistory(history, { type: 'undo' }), redo = reduceHistory(undo, { type: 'redo' });
  assert.deepEqual(undo.document.layout, document.layout); assert.deepEqual(redo.document.layout, history.document.layout);
  assert.deepEqual(history.document.architecture, document.architecture); assert.deepEqual(history.document.pinnedObjects, document.pinnedObjects);
  assert.equal(JSON.stringify(document), original);
});
