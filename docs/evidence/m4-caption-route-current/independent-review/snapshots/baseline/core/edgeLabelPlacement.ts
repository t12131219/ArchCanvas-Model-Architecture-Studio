import type { Bounds, SceneDiagnostic, SceneEdge, SceneNode } from './types.ts';
import { nodeVisualOutline } from './nodeVisualOutline.ts';
import { orthogonalPathPoints } from './orthogonalRouter.ts';

const FONT_SIZE = 9, PADDING = 2, SEARCH_RADIUS = 64;
const OFFSETS = [0, -8, 8, -16, 16, -24, 24, -32, 32, -40, 40, -48, 48, -56, 56, -64, 64];
type Point = { x: number; y: number };
type Body = Bounds & { id: string };

/** A deterministic nominal envelope for the shared 9-unit SVG edge font.
 * One em per code point plus padding deliberately exceeds ordinary Latin
 * advances. This is not a resolved-font measurement or physical print proof. */
export function edgeLabelBounds(label: string, x: number, y: number): Bounds {
  return { x: x - PADDING, y: y - FONT_SIZE - PADDING,
    width: [...label].length * FONT_SIZE + PADDING * 2, height: FONT_SIZE + PADDING * 2 + 3 };
}

function intersects(a: Bounds, b: Bounds): boolean {
  return Math.min(a.x + a.width, b.x + b.width) > Math.max(a.x, b.x)
    && Math.min(a.y + a.height, b.y + b.height) > Math.max(a.y, b.y);
}

function routeEnters(points: Point[], body: Bounds): boolean {
  return points.slice(1).some((b, index) => {
    const a = points[index];
    if (a.x === b.x) return a.x > body.x && a.x < body.x + body.width
      && Math.max(Math.min(a.y, b.y), body.y) < Math.min(Math.max(a.y, b.y), body.y + body.height);
    return a.y > body.y && a.y < body.y + body.height
      && Math.max(Math.min(a.x, b.x), body.x) < Math.min(Math.max(a.x, b.x), body.x + body.width);
  });
}

/** Caption placement is derived scene presentation. Nodes, routes, canonical
 * bindings and persisted manual layout are never moved or rewritten here. */
export function placeEdgeLabels(nodes: readonly SceneNode[], edges: readonly SceneEdge[], additionalBodies: readonly Body[] = []) {
  const placements = new Map<string, Point>(), diagnostics: SceneDiagnostic[] = [];
  if (!edges.some(edge => edge.label)) return { placements, diagnostics };
  const bodies: Body[] = nodes.flatMap(node => node.expanded
    ? [{ id: node.id, x: node.x, y: node.y, width: node.width, height: node.headerHeight }]
    : nodeVisualOutline(node).rectangles.map(rectangle => ({ id: node.id, ...rectangle })));
  bodies.push(...additionalBodies);
  const routes = edges.map(edge => orthogonalPathPoints(edge.path));
  const reserved: Body[] = [];
  for (const [index, edge] of edges.entries()) {
    if (!edge.label) continue;
    const origin = { x: edge.labelX, y: edge.labelY };
    const conflicts = (point: Point) => {
      const bounds = edgeLabelBounds(edge.label, point.x, point.y);
      const blockedBodies = [...bodies, ...reserved].filter(body => intersects(bounds, body)).map(body => body.id);
      const blockedRoutes = edges.flatMap((other, routeIndex) => routeIndex !== index && routeEnters(routes[routeIndex], bounds) ? [other.id] : []);
      return { bounds, blockedBodies, blockedRoutes };
    };
    const initial = conflicts(origin);
    let position = origin;
    if (initial.blockedBodies.length || initial.blockedRoutes.length) {
      const candidates = new Map<string, Point>();
      const add = (x: number, y: number) => {
        if (Math.abs(x - origin.x) > SEARCH_RADIUS || Math.abs(y - origin.y) > SEARCH_RADIUS) return;
        const point = { x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100 };
        candidates.set(`${point.x}:${point.y}`, point);
      };
      for (const dx of OFFSETS) for (const dy of OFFSETS) add(origin.x + dx, origin.y + dy);
      // Candidate positions beside the owned route retain a clear association
      // even when the caption is wider than a short endpoint gap.
      const width = edgeLabelBounds(edge.label, 0, 0).width - PADDING * 2;
      for (const [routeIndex, b] of routes[index].entries()) {
        if (!routeIndex) continue;
        const a = routes[index][routeIndex - 1], cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2;
        if (a.y === b.y) { add(cx - width / 2, cy - 7); add(cx - width / 2, cy + FONT_SIZE + 8); }
        else { add(cx + 7, cy + FONT_SIZE / 2); add(cx - width - 7, cy + FONT_SIZE / 2); }
      }
      const distance = (point: Point) => (point.x - origin.x) ** 2 + (point.y - origin.y) ** 2;
      const sorted = [...candidates.values()].sort((a, b) => distance(a) - distance(b) || a.y - b.y || a.x - b.x);
      const available = sorted.find(candidate => {
        const result = conflicts(candidate);
        return !result.blockedBodies.length && !result.blockedRoutes.length;
      });
      if (available) position = available;
      else diagnostics.push({ level: 'warning', code: 'layout-edge-label-blocked', edgeId: edge.id,
        objectIds: [...new Set(initial.blockedBodies)],
        message: `Edge "${edge.id}" has no clear caption position within ${SEARCH_RADIUS} scene units of its derived anchor. The nominal text envelope intersects cards, headers, notes, other captions or routes. Its text and object anchors are preserved; increase spacing to resolve this caption conflict.` });
    }
    placements.set(edge.id, position);
    reserved.push({ id: edge.id, ...edgeLabelBounds(edge.label, position.x, position.y) });
  }
  return { placements, diagnostics };
}
