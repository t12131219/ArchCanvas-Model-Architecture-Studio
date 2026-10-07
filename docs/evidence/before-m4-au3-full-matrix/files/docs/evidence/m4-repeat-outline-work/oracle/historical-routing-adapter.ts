import assert from 'node:assert/strict';
import { compact, intrusions, metrics, parsePath, verifyRefinement } from '../../m4-routing-refinement/independent/oracle.ts';
import { analyzeSvg, parseSvg } from './oracle.ts';
import type { Point, Rectangle } from './oracle.ts';
import type { Scene, SceneNode, ScenePort } from '../../../../studio/src/core/types.ts';

// Compatibility is deliberately limited to the documented visible-card
// projection and side IDs. Historical evidence and its oracle stay untouched.
type Side = 'bottom' | 'top' | 'right' | 'left';
const epsilon = 1e-6, same = (a: number, b: number) => Math.abs(a - b) < epsilon;
function priorSide(scene: Scene, node: SceneNode, port: ScenePort): Side {
  const normal = port.direction === 'out' ? 'bottom' : 'top';
  if (same(port.y, normal === 'bottom' ? node.y + node.height : node.y) && port.x > node.x && port.x < node.x + node.width) return normal;
  const side = port.direction === 'out' ? 'right' : 'left';
  assert.ok(same(port.x, side === 'right' ? node.x + node.width : node.x) && same(port.y, node.y + node.height * .55), 'Historical port is outside supported front sides');
  const edges = scene.edges.filter(edge => port.canonicalEdgeIds.some(id => edge.canonicalEdgeIds.includes(id)) &&
    (port.direction === 'out' ? edge.sourceId : edge.targetId) === node.id);
  assert.ok(edges.length > 0 && edges.every(edge => {
    const source = scene.nodes.find(item => item.id === edge.sourceId)!, target = scene.nodes.find(item => item.id === edge.targetId)!;
    return edge.role === 'memory' && Math.abs(source.y - target.y) < 15 && source.x + source.width < target.x;
  }), 'Side ID exception requires a preexisting horizontal memory binding');
  return side;
}
function exposedAnchor(rectangles: Rectangle[], point: Point, side: Side): Point {
  // The expected coordinate is derived from SVG cross sections, independently
  // of any product outline/projector. A corner ray must actually meet a card.
  const alongVertical = side === 'top' || side === 'bottom';
  const hits = rectangles.filter(rectangle => alongVertical ? point.x >= rectangle.x && point.x <= rectangle.x + rectangle.width
    : point.y >= rectangle.y && point.y <= rectangle.y + rectangle.height);
  assert.ok(hits.length, 'Port projection ray misses displayed cards');
  const values = hits.map(rectangle => side === 'bottom' ? rectangle.y + rectangle.height : side === 'top' ? rectangle.y
    : side === 'right' ? rectangle.x + rectangle.width : rectangle.x);
  const coordinate = side === 'bottom' || side === 'right' ? Math.max(...values) : Math.min(...values);
  return alongVertical ? { x: point.x, y: coordinate } : { x: coordinate, y: point.y };
}
export function verifyOutlineCompatibleRefinement(before: Scene, after: Scene, afterSvg: string) {
  const original = JSON.stringify(before), geometry = parseSvg(afterSvg), normalized = structuredClone(before);
  assert.equal(after.nodes.length, before.nodes.length, 'Visible owner coverage changed');
  for (const [index, oldNode] of before.nodes.entries()) {
    const cards = geometry.cards.get(oldNode.id)!;
    assert.equal(cards?.length, oldNode.repeat && !oldNode.expanded ? 3 : 1, 'Displayed card count changed');
    const rounded = (value: number) => Math.round(value * 100) / 100;
    const expected = (offset: number) => ({ x: rounded(oldNode.x + offset), y: rounded(oldNode.y + offset), width: rounded(oldNode.width), height: rounded(oldNode.height) });
    assert.deepEqual(cards, oldNode.repeat && !oldNode.expanded ? [expected(7), expected(3.5), expected(0)] : [expected(0)], 'Front/stack geometry changed');
    normalized.nodes[index].ports = oldNode.ports.map(port => {
      const side = priorSide(before, oldNode, port), point = exposedAnchor(cards, port, side);
      // SVG rounds to 0.01. Preserve higher precision coordinates unless the
      // independently observed union boundary actually differs from front.
      const delta = side === 'bottom' || side === 'top' ? point.y - rounded(port.y) : point.x - rounded(port.x);
      assert.ok([0, 3.5, 7].some(offset => Math.abs(delta - offset) < .011), 'Projection changed by an unsupported offset');
      assert.ok((oldNode.repeat && !oldNode.expanded) || Math.abs(delta) < .011, 'Projection moved an ordinary/expanded port');
      const coordinates = side === 'bottom' || side === 'top' ? { x: port.x, y: port.y + delta } : { x: port.x + delta, y: port.y };
      return { ...port, id: side === 'right' || side === 'left' ? `${port.id}:${side}` : port.id, ...coordinates };
    });
  }
  assert.deepEqual(JSON.parse(JSON.stringify(after.nodes)), JSON.parse(JSON.stringify(normalized.nodes)), 'Only exact card-ray port projection and horizontal-memory side ID are permitted');
  const publicReport = analyzeSvg(after, afterSvg);
  for (const field of ['endpointMisses', 'buriedPorts', 'floatingPorts', 'clippedCards', 'clippedPaths'] as const)
    assert.deepEqual(publicReport[field], [], `Final SVG ${field} invalid`);
  // A frozen manual move can already overlap source/target fronts. Preserve
  // that explicitly diagnosed conflict; a new backplate-only hit is rejected.
  const priorBodyHits = intrusions(before);
  for (const hit of publicReport.stackHits) {
    assert.ok(priorBodyHits.some(prior => prior.edgeId === hit.edgeId && prior.nodeId === hit.nodeId && prior.obstacle === 'body'), 'New backplate-only intrusion is not permitted');
    assert.ok(after.diagnostics.some(diagnostic => diagnostic.code === 'layout-route-blocked' && diagnostic.edgeId === hit.edgeId && diagnostic.objectIds?.includes(hit.nodeId)), 'Existing overlapped endpoint must remain explicitly blocked');
  }
  // Check actual raw metrics against the frozen raw baseline before adapting
  // endpoint anchors for the old endpoint-preserving verifier.
  const rawBefore = metrics(before), rawAfter = metrics(after);
  for (const group of ['distinctTensor', 'disjointOwners'] as const) for (const metric of ['crossingPairs', 'crossingPairPoints', 'overlapPairs'] as const)
    assert.ok(rawAfter[group][metric] <= rawBefore[group][metric], `Raw ${group} ${metric} regressed`);
  const rawPriorIntrusions = new Set(priorBodyHits.map(hit => JSON.stringify(hit)));
  for (const hit of intrusions(after)) assert.ok(rawPriorIntrusions.has(JSON.stringify(hit)), `New raw body/header intrusion: ${JSON.stringify(hit)}`);
  assert.equal(rawAfter.routes.length, rawBefore.routes.length, 'Canonical route count changed');
  for (let index = 0; index < rawAfter.routes.length; index++) {
    assert.deepEqual(rawAfter.routes[index].vectors[0], rawBefore.routes[index].vectors[0], 'Raw departure direction changed');
    assert.deepEqual(rawAfter.routes[index].vectors.at(-1), rawBefore.routes[index].vectors.at(-1), 'Raw arrival direction changed');
    assert.ok(rawAfter.routes[index].reversals <= rawBefore.routes[index].reversals, 'Raw U-turn regression');
  }
  for (const [index, edge] of before.edges.entries()) {
    const points = compact(parsePath(edge.path));
    for (const [nodeId, direction, pointIndex] of [[edge.sourceId, 'out', 0], [edge.targetId, 'in', points.length - 1]] as const) {
      const oldNode = before.nodes.find(node => node.id === nodeId)!, node = normalized.nodes.find(node => node.id === nodeId)!;
      const portIndex = oldNode.ports.findIndex(port => port.direction === direction && port.canonicalEdgeIds.some(id => edge.canonicalEdgeIds.includes(id)) &&
        Math.abs(port.x - points[pointIndex].x) <= .15 && Math.abs(port.y - points[pointIndex].y) <= .15);
      assert.ok(portIndex >= 0, 'Historical edge lacks a matching canonical display port');
      const oldPort = oldNode.ports[portIndex], port = node.ports[portIndex];
      points[pointIndex] = { x: points[pointIndex].x + port.x - oldPort.x, y: points[pointIndex].y + port.y - oldPort.y };
    }
    normalized.edges[index].path = points.map((point, i) => `${i ? 'L' : 'M'} ${Math.round(point.x * 1e6) / 1e6} ${Math.round(point.y * 1e6) / 1e6}`).join(' ');
  }
  const verification = verifyRefinement(normalized, after);
  assert.equal(JSON.stringify(before), original, 'Compatibility adapter mutated historical input');
  return { ...verification, before: rawBefore, after: rawAfter };
}
