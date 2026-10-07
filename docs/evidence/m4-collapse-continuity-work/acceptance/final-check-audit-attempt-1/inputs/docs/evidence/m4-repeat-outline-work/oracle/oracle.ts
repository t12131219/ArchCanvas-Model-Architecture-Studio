import assert from 'node:assert/strict';
import type { Scene } from '../../../../studio/src/core/types.ts';

// This oracle reads the published SVG. It imports no product geometry, path,
// outline, projection, intersection, routing or scoring implementation.
export type Point = { x: number; y: number };
export type Rectangle = Point & { width: number; height: number };
export type SvgGeometry = {
  cards: Map<string, Rectangle[]>;
  circles: Map<string, Point>;
  paths: Map<string, Point[]>;
  metadata: Record<string, unknown>;
  bounds: Rectangle;
};
const tolerance = .12; // Routes round to 0.1 units; SVG attributes round to 0.01.
const decode = (value: string) => value.replace(/&(?:quot|apos|lt|gt|amp);/g, entity =>
  ({ '&quot;': '"', '&apos;': "'", '&lt;': '<', '&gt;': '>', '&amp;': '&' })[entity]!);
const key = (nodeId: string, portId: string) => JSON.stringify([nodeId, portId]);

export function pathPoints(path: string): Point[] {
  const tokens = path.match(/[a-z]|[-+]?(?:\d*\.)?\d+(?:e[-+]?\d+)?/gi) ?? [];
  const result: Point[] = [];
  let x = 0, y = 0, command = '', cursor = 0;
  const value = () => {
    assert.ok(cursor < tokens.length && !/^[a-z]$/i.test(tokens[cursor]), `Incomplete SVG path ${path}`);
    const number = Number(tokens[cursor++]); assert.ok(Number.isFinite(number)); return number;
  };
  while (cursor < tokens.length) {
    if (/^[a-z]$/i.test(tokens[cursor])) command = tokens[cursor++];
    const relative = command === command.toLowerCase();
    switch (command.toUpperCase()) {
      case 'M': case 'L': { const a = value(), b = value(); x = relative ? x + a : a; y = relative ? y + b : b; break; }
      case 'H': { const a = value(); x = relative ? x + a : a; break; }
      case 'V': { const a = value(); y = relative ? y + a : a; break; }
      default: assert.fail(`Unsupported public route command ${command}`);
    }
    result.push({ x, y });
    if (command === 'M') command = 'L'; else if (command === 'm') command = 'l';
  }
  assert.ok(result.length >= 2, `Route has fewer than two points: ${path}`);
  return result;
}

export function parseSvg(svg: string): SvgGeometry {
  const cards = new Map<string, Rectangle[]>(), circles = new Map<string, Point>(), paths = new Map<string, Point[]>();
  const stack: { tag: string; attributes: Record<string, string> }[] = [];
  for (const token of svg.matchAll(/<\/?[a-z][^>]*>/gi)) {
    const text = token[0], tag = /^<\/?([a-z][\w:-]*)/i.exec(text)![1];
    if (text.startsWith('</')) { assert.equal(stack.pop()?.tag, tag, 'Unbalanced generated SVG'); continue; }
    const attributes = Object.fromEntries([...text.matchAll(/([\w:-]+)="([^"]*)"/g)].map(([, name, value]) => [name, decode(value)]));
    const parent = stack.at(-1)?.attributes;
    // Only rectangles directly owned by a node group are cards. Glyphs and
    // interactive controls use nested groups and are deliberately excluded.
    if (tag === 'rect' && parent?.['data-node-id'] && !parent['data-port-id']) {
      const rectangle = { x: Number(attributes.x), y: Number(attributes.y), width: Number(attributes.width), height: Number(attributes.height) };
      assert.ok(Object.values(rectangle).every(Number.isFinite));
      const list = cards.get(parent['data-node-id']) ?? []; list.push(rectangle); cards.set(parent['data-node-id'], list);
    }
    if (tag === 'circle' && Number(attributes.r) === 2.6) {
      const owner = attributes['data-port-id'] ? attributes : parent;
      if (owner?.['data-port-id'] && owner['data-node-id']) circles.set(key(owner['data-node-id'], owner['data-port-id']), { x: Number(attributes.cx), y: Number(attributes.cy) });
    }
    if (tag === 'path' && parent?.['data-edge-id']) {
      assert.ok(!paths.has(parent['data-edge-id']), 'More than one public route path for an edge');
      paths.set(parent['data-edge-id'], pathPoints(attributes.d));
    }
    if (!text.endsWith('/>')) stack.push({ tag, attributes });
  }
  assert.equal(stack.length, 0);
  const metadata = JSON.parse(decode(/<metadata>(.*?)<\/metadata>/s.exec(svg)![1])) as Record<string, unknown>;
  const [x, y, width, height] = /viewBox="([^"]+)"/.exec(svg)![1].split(/\s+/).map(Number);
  return { cards, circles, paths, metadata, bounds: { x, y, width, height } };
}

function inOpenRectangle(point: Point, rectangle: Rectangle): boolean {
  return point.x > rectangle.x + tolerance && point.x < rectangle.x + rectangle.width - tolerance &&
    point.y > rectangle.y + tolerance && point.y < rectangle.y + rectangle.height - tolerance;
}
function onClosedRectangle(point: Point, rectangle: Rectangle): boolean {
  return point.x >= rectangle.x - tolerance && point.x <= rectangle.x + rectangle.width + tolerance &&
    point.y >= rectangle.y - tolerance && point.y <= rectangle.y + rectangle.height + tolerance;
}
export function penetrates(a: Point, b: Point, rectangle: Rectangle): boolean {
  assert.ok(a.x === b.x || a.y === b.y, 'Published tensor route must be orthogonal');
  if (a.x === b.x) return a.x > rectangle.x + tolerance && a.x < rectangle.x + rectangle.width - tolerance &&
    Math.max(Math.min(a.y, b.y), rectangle.y + tolerance) < Math.min(Math.max(a.y, b.y), rectangle.y + rectangle.height - tolerance);
  return a.y > rectangle.y + tolerance && a.y < rectangle.y + rectangle.height - tolerance &&
    Math.max(Math.min(a.x, b.x), rectangle.x + tolerance) < Math.min(Math.max(a.x, b.x), rectangle.x + rectangle.width - tolerance);
}
const close = (a: Point, b: Point) => Math.abs(a.x - b.x) <= tolerance && Math.abs(a.y - b.y) <= tolerance;

export function analyzeSvg(scene: Scene, svg: string) {
  const geometry = parseSvg(svg);
  const endpointMisses: { edgeId: string; direction: string; point: Point }[] = [];
  const buriedPorts: { nodeId: string; portId: string; point: Point }[] = [];
  const floatingPorts: { nodeId: string; portId: string; point: Point }[] = [];
  const stackHits: { edgeId: string; nodeId: string; ownEndpointBody: boolean }[] = [];
  const ownBodyHits: { edgeId: string; nodeId: string }[] = [];
  const clippedCards: string[] = [], clippedPaths: string[] = [];
  for (const node of scene.nodes) {
    const rectangles = geometry.cards.get(node.id)!;
    assert.equal(rectangles?.length, node.repeat && !node.expanded ? 3 : 1, `${node.id} public card count`);
    const front = rectangles.at(-1)!;
    if (rectangles.some(rectangle => !onClosedRectangle(rectangle, geometry.bounds) ||
      !onClosedRectangle({ x: rectangle.x + rectangle.width, y: rectangle.y + rectangle.height }, geometry.bounds))) clippedCards.push(node.id);
    assert.deepEqual(front, { x: round(node.x), y: round(node.y), width: round(node.width), height: round(node.height) }, `${node.id} nominal front moved`);
    if (node.repeat && !node.expanded) {
      assert.deepEqual(rectangles.slice(0, 2), [7, 3.5].map(offset => ({ x: round(node.x + offset), y: round(node.y + offset), width: round(node.width), height: round(node.height) })), `${node.id} visible stack differs from expected cards`);
    }
    for (const port of node.ports) {
      const circle = geometry.circles.get(key(node.id, port.id)); assert.ok(circle, `${node.id}/${port.id} has no visible SVG circle`);
      if (!node.repeat || node.expanded) continue;
      if (rectangles.some(rectangle => inOpenRectangle(circle, rectangle))) buriedPorts.push({ nodeId: node.id, portId: port.id, point: circle });
      if (!rectangles.some(rectangle => onClosedRectangle(circle, rectangle))) floatingPorts.push({ nodeId: node.id, portId: port.id, point: circle });
    }
  }
  assert.equal(geometry.paths.size, scene.edges.length, 'Every Scene edge has a public SVG path');
  for (const edge of scene.edges) {
    const points = geometry.paths.get(edge.id)!;
    if (points.some(point => !onClosedRectangle(point, geometry.bounds))) clippedPaths.push(edge.id);
    for (const [nodeId, direction, endpoint] of [[edge.sourceId, 'out', points[0]], [edge.targetId, 'in', points.at(-1)!]] as const) {
      const node = scene.nodes.find(node => node.id === nodeId)!;
      const ports = node.ports.filter(port => port.direction === direction && port.canonicalEdgeIds.some(id => edge.canonicalEdgeIds.includes(id)));
      if (!ports.some(port => close(geometry.circles.get(key(nodeId, port.id))!, endpoint))) endpointMisses.push({ edgeId: edge.id, direction, point: endpoint });
    }
    for (const node of scene.nodes.filter(node => !node.expanded)) {
      const rectangles = geometry.cards.get(node.id)!;
      const intersects = (candidates: Rectangle[]) => candidates.some(rectangle => points.slice(1).some((point, index) => penetrates(points[index], point, rectangle)));
      const own = node.id === edge.sourceId || node.id === edge.targetId;
      if (node.repeat && intersects(rectangles.slice(0, 2))) stackHits.push({ edgeId: edge.id, nodeId: node.id, ownEndpointBody: own });
      if (own && intersects(rectangles)) ownBodyHits.push({ edgeId: edge.id, nodeId: node.id });
    }
  }
  return { endpointMisses, buriedPorts, floatingPorts, stackHits, ownBodyHits, clippedCards, clippedPaths };
}
export function assertHealthy(scene: Scene, svg: string): ReturnType<typeof analyzeSvg> {
  const report = analyzeSvg(scene, svg);
  assert.deepEqual(report.endpointMisses, [], 'Final SVG path endpoints do not match their canonical-covered port circles');
  assert.deepEqual(report.buriedPorts, [], 'Collapsed Repeat ports are inside the displayed cards');
  assert.deepEqual(report.floatingPorts, [], 'Ports lie in empty envelope corners without any displayed card');
  assert.deepEqual(report.stackHits, [], 'Tensor paths penetrate displayed Repeat backplates');
  assert.deepEqual(report.ownBodyHits, [], 'Tensor path re-enters its own endpoint body');
  assert.deepEqual(report.clippedCards, [], 'SVG viewBox clips displayed cards');
  assert.deepEqual(report.clippedPaths, [], 'SVG viewBox clips tensor paths');
  return report;
}
const round = (value: number) => Math.round(value * 100) / 100;
export function frontCards(scene: Scene, svg: string) {
  const geometry = parseSvg(svg);
  return scene.nodes.filter(node => !node.boundary).map(node => ({ id: node.id, rectangle: geometry.cards.get(node.id)!.at(-1)!, localX: node.localX, localY: node.localY, expanded: node.expanded, pinned: node.pinned }));
}
export function ordinaryPorts(scene: Scene) {
  return scene.nodes.filter(node => !node.boundary && (!node.repeat || node.expanded)).flatMap(node => node.ports.map(port => ({ nodeId: node.id,
    canonicalNodeId: port.canonicalNodeId, canonicalPortId: port.canonicalPortId, direction: port.direction, canonicalEdgeIds: port.canonicalEdgeIds, x: round(port.x), y: round(port.y) })));
}
