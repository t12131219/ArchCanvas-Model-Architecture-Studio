import type { Bounds, SceneCaptionGuide, SceneDiagnostic, SceneEdge, SceneNode } from './types.ts';
import { nodeVisualOutline } from './nodeVisualOutline.ts';
import { orthogonalPathPoints } from './orthogonalRouter.ts';

const FONT_SIZE = 9, PADDING = 2, SEARCH_RADIUS = 64;
/** Nominal scene distances, independent of camera scale or physical print size. */
export const CAPTION_ASSOCIATION = Object.freeze({ maxDirectDistance: 18, maxGuideLength: 48, guideWidth: .8 });
/** Deterministic work limits, never a wall-clock/presented-performance claim. */
export const CAPTION_WORK_BUDGET = Object.freeze({ maxLabeledEdges: 128, maxNodes: 1_024, maxRoutes: 512,
  maxAdditionalBodies: 1_024, maxPathCharacters: 262_144, maxRoutePoints: 4_096, maxCandidatesPerCaption: 320, maxGeometryChecks: 2_000_000 });
const EPSILON = 1e-6;
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

function segmentContacts(a: Point, b: Point, c: Point, d: Point): boolean {
  const av = a.x === b.x, cv = c.x === d.x;
  if (av !== cv) {
    const [v, w, h, k] = av ? [a, b, c, d] : [c, d, a, b];
    return v.x >= Math.min(h.x, k.x) - EPSILON && v.x <= Math.max(h.x, k.x) + EPSILON
      && h.y >= Math.min(v.y, w.y) - EPSILON && h.y <= Math.max(v.y, w.y) + EPSILON;
  }
  return Math.abs((av ? a.x : a.y) - (cv ? c.x : c.y)) < EPSILON
    && Math.max(Math.min(av ? a.y : a.x, av ? b.y : b.x), Math.min(av ? c.y : c.x, av ? d.y : d.x))
      <= Math.min(Math.max(av ? a.y : a.x, av ? b.y : b.x), Math.max(av ? c.y : c.x, av ? d.y : d.x)) + EPSILON;
}
function distanceToRoute(body: Bounds, points: Point[]): number {
  return Math.min(...points.slice(1).map((b, index) => {
    const a = points[index];
    const dx = Math.max(body.x - Math.max(a.x, b.x), Math.min(a.x, b.x) - body.x - body.width, 0);
    const dy = Math.max(body.y - Math.max(a.y, b.y), Math.min(a.y, b.y) - body.y - body.height, 0);
    return Math.hypot(dx, dy);
  }));
}
function guideProposals(body: Bounds, points: Point[]): { start: Point; end: Point; length: number }[] {
  const proposals: { start: Point; end: Point; length: number }[] = [];
  const add = (start: Point, end: Point) => {
    const length = Math.abs(end.x - start.x) + Math.abs(end.y - start.y);
    if (length > EPSILON && length <= CAPTION_ASSOCIATION.maxGuideLength) proposals.push({ start, end, length });
  };
  for (const [index, b] of points.entries()) {
    if (!index) continue;
    const a = points[index - 1];
    const vertical = a.x === b.x;
    const low = Math.min(vertical ? a.y : a.x, vertical ? b.y : b.x), high = Math.max(vertical ? a.y : a.x, vertical ? b.y : b.x);
    if (high - low <= EPSILON) continue;
    const margin = Math.min(3, (high - low) / 4);
    const boxLow = vertical ? body.y : body.x, boxHigh = boxLow + (vertical ? body.height : body.width);
    const overlapLow = Math.max(low + margin, boxLow), overlapHigh = Math.min(high - margin, boxHigh);
    if (overlapHigh < overlapLow) continue;
    const center = Math.max(overlapLow, Math.min(overlapHigh, (low + high) / 2));
    const captionCenter = Math.max(overlapLow, Math.min(overlapHigh, (boxLow + boxHigh) / 2));
    for (const coordinate of [...new Set([center, captionCenter, (overlapLow + overlapHigh) / 2])]) {
      if (vertical) {
        if (body.x > a.x) add({ x: a.x, y: coordinate }, { x: body.x, y: coordinate });
        else if (body.x + body.width < a.x) add({ x: a.x, y: coordinate }, { x: body.x + body.width, y: coordinate });
      } else {
        if (body.y > a.y) add({ x: coordinate, y: a.y }, { x: coordinate, y: body.y });
        else if (body.y + body.height < a.y) add({ x: coordinate, y: a.y }, { x: coordinate, y: body.y + body.height });
      }
    }
  }
  return proposals.sort((a, b) => a.length - b.length);
}

/** Caption placement is derived scene presentation. Nodes, routes, canonical
 * bindings and persisted manual layout are never moved or rewritten here. */
export function placeEdgeLabels(nodes: readonly SceneNode[], edges: readonly SceneEdge[], additionalBodies: readonly Body[] = []) {
  const placements = new Map<string, Point>(), diagnostics: SceneDiagnostic[] = [], guides: SceneCaptionGuide[] = [];
  if (!edges.some(edge => edge.label)) return { placements, diagnostics, guides };
  const preserveAtLimit = (reason?: string) => {
    for (const edge of edges.filter(item => item.label)) {
      placements.set(edge.id, { x: edge.labelX, y: edge.labelY });
      diagnostics.push({ level: 'warning', code: 'layout-edge-label-association', edgeId: edge.id,
        message: reason
          ? `Caption association cannot certify ${reason}. Edge "${edge.id}" retains its text and derived position; use finite nonnegative route stroke widths before assessing caption association.`
          : `Caption association exceeded its deterministic work limits. Edge "${edge.id}" retains its text and derived position; reduce visible detail or increase spacing before assessing caption association.` });
    }
    return { placements, diagnostics, guides };
  };
  if (edges.some(edge => !Number.isFinite(edge.width) || edge.width < 0)) return preserveAtLimit('route stroke widths');
  if (nodes.length > CAPTION_WORK_BUDGET.maxNodes || edges.length > CAPTION_WORK_BUDGET.maxRoutes
      || additionalBodies.length > CAPTION_WORK_BUDGET.maxAdditionalBodies
      || edges.reduce((total, edge) => total + edge.path.length, 0) > CAPTION_WORK_BUDGET.maxPathCharacters
      || edges.filter(edge => edge.label).length > CAPTION_WORK_BUDGET.maxLabeledEdges) return preserveAtLimit();
  const bodies: Body[] = nodes.flatMap(node => node.expanded
    ? [{ id: node.id, x: node.x, y: node.y, width: node.width, height: node.headerHeight }]
    : nodeVisualOutline(node).rectangles.map(rectangle => ({ id: node.id, ...rectangle })));
  bodies.push(...additionalBodies);
  const routes = edges.map(edge => orthogonalPathPoints(edge.path));
  if (routes.reduce((total, route) => total + route.length, 0) > CAPTION_WORK_BUDGET.maxRoutePoints) return preserveAtLimit();
  let checks = 0, exhausted = false;
  const take = () => { if (checks >= CAPTION_WORK_BUDGET.maxGeometryChecks) { exhausted = true; return false; } checks++; return true; };
  const checkedEnters = (points: Point[], body: Bounds) => points.slice(1).some((point, index) => !take() || routeEnters([points[index], point], body));
  const checkedContact = (a: Point, b: Point, points: Point[]) => points.slice(1).some((point, index) => !take() || segmentContacts(a, b, points[index], point));
  // A centerline can miss another line while their visible strokes touch.
  // The combined half widths form a conservative rectangle around each
  // orthogonal peer segment, including its joints and endpoint vicinity.
  const checkedStrokeContact = (a: Point, b: Point, points: Point[], clearance: number) => points.slice(1).some((point, index) => {
    if (!take()) return true;
    const previous = points[index], left = Math.min(previous.x, point.x) - clearance,
      right = Math.max(previous.x, point.x) + clearance, top = Math.min(previous.y, point.y) - clearance,
      bottom = Math.max(previous.y, point.y) + clearance;
    return a.x === b.x ? a.x >= left - EPSILON && a.x <= right + EPSILON
      && Math.max(a.y, b.y) >= top - EPSILON && Math.min(a.y, b.y) <= bottom + EPSILON
      : a.y >= top - EPSILON && a.y <= bottom + EPSILON
      && Math.max(a.x, b.x) >= left - EPSILON && Math.min(a.x, b.x) <= right + EPSILON;
  });
  const captions = new Map(edges.filter(edge => edge.label).map(edge => [edge.id, { id: edge.id, ...edgeLabelBounds(edge.label, edge.labelX, edge.labelY) }]));
  const reservedGuides: Point[][] = [];
  const occupiedIds = new Set([...nodes, ...edges, ...additionalBodies].map(item => item.id));
  for (const [index, edge] of edges.entries()) {
    if (!edge.label) continue;
    const origin = { x: edge.labelX, y: edge.labelY };
    const conflicts = (point: Point) => {
      const bounds = edgeLabelBounds(edge.label, point.x, point.y);
      const blockedBodies = [...bodies, ...[...captions.values()].filter(body => body.id !== edge.id)].filter(body => !take() || intersects(bounds, body)).map(body => body.id);
      const blockedRoutes = edges.flatMap((other, routeIndex) => routeIndex !== index && checkedEnters(routes[routeIndex], bounds) ? [other.id] : []);
      const guidePadding = CAPTION_ASSOCIATION.guideWidth / 2;
      const guideExclusion = { x: bounds.x - guidePadding, y: bounds.y - guidePadding,
        width: bounds.width + guidePadding * 2, height: bounds.height + guidePadding * 2 };
      if (reservedGuides.some(guide => checkedEnters(guide, guideExclusion))) blockedRoutes.push('caption-guide');
      return { bounds, blockedBodies, blockedRoutes };
    };
    const association = (bounds: Bounds) => {
      if (exhausted || checkedEnters(routes[index], bounds)) return undefined;
      const gap = distanceToRoute(bounds, routes[index]);
      if (gap <= CAPTION_ASSOCIATION.maxDirectDistance) return { gap };
      for (const proposal of guideProposals(bounds, routes[index])) {
        const { start, end } = proposal;
        const guide = [start, end], padding = CAPTION_ASSOCIATION.guideWidth / 2;
        const guideBodies = [...bodies, ...[...captions.values()].filter(body => body.id !== edge.id)]
          .map(body => ({ ...body, x: body.x - padding, y: body.y - padding, width: body.width + padding * 2, height: body.height + padding * 2 }));
        if (guideBodies.some(body => checkedEnters(guide, body))) continue;
        if (edges.some((other, routeIndex) => routeIndex !== index
          && checkedStrokeContact(start, end, routes[routeIndex], padding + other.width / 2))) continue;
        if (reservedGuides.some(route => {
          const [a, b] = route, strokeClearance = CAPTION_ASSOCIATION.guideWidth;
          const envelope = { x: Math.min(a.x, b.x) - strokeClearance, y: Math.min(a.y, b.y) - strokeClearance,
            width: Math.abs(b.x - a.x) + strokeClearance * 2, height: Math.abs(b.y - a.y) + strokeClearance * 2 };
          return checkedContact(start, end, route) || checkedEnters(guide, envelope);
        })) continue;
        // A guide touches its owner at one strict-interior attachment only.
        // Its remaining span cannot cross a second segment of that same path.
        const departure = { x: start.x + Math.sign(end.x - start.x) * EPSILON * 10, y: start.y + Math.sign(end.y - start.y) * EPSILON * 10 };
        if (checkedContact(departure, end, routes[index])) continue;
        return { gap: proposal.length, guide };
      }
      return undefined;
    };
    const initial = conflicts(origin);
    let position = origin;
    let selectedAssociation = !initial.blockedBodies.length && !initial.blockedRoutes.length ? association(initial.bounds) : undefined;
    if (!selectedAssociation || selectedAssociation.guide) {
      const candidates = new Map<string, Point>();
      const add = (x: number, y: number) => {
        if (Math.abs(x - origin.x) > SEARCH_RADIUS || Math.abs(y - origin.y) > SEARCH_RADIUS) return;
        const point = { x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100 };
        if (candidates.size >= CAPTION_WORK_BUDGET.maxCandidatesPerCaption) return;
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
      const available = [...candidates.values()].flatMap(candidate => {
        const result = conflicts(candidate);
        if (result.blockedBodies.length || result.blockedRoutes.length) return [];
        const connected = association(result.bounds);
        return connected ? [{ candidate, connected }] : [];
      }).sort((a, b) => Number(!!a.connected.guide) - Number(!!b.connected.guide) || a.connected.gap - b.connected.gap
        || distance(a.candidate) - distance(b.candidate) || a.candidate.y - b.candidate.y || a.candidate.x - b.candidate.x)[0];
      if (available) { position = available.candidate; selectedAssociation = available.connected; }
      else diagnostics.push({ level: 'warning', code: initial.blockedBodies.length || initial.blockedRoutes.length ? 'layout-edge-label-blocked' : 'layout-edge-label-association', edgeId: edge.id,
        objectIds: [...new Set(initial.blockedBodies)],
        message: exhausted ? `Edge "${edge.id}" retains its caption after association geometry checks reached their deterministic budget. Its text and object anchors are preserved; reduce visible detail before assessing caption association.`
          : `Edge "${edge.id}" has no clear, associated caption within ${SEARCH_RADIUS} scene units of its derived anchor: direct captions must be within ${CAPTION_ASSOCIATION.maxDirectDistance} units of their owned route; decorative guides must be clear and no longer than ${CAPTION_ASSOCIATION.maxGuideLength} units. Its text and object anchors are preserved; increase spacing to resolve this caption conflict.` });
    }
    placements.set(edge.id, position);
    captions.set(edge.id, { id: edge.id, ...edgeLabelBounds(edge.label, position.x, position.y) });
    if (selectedAssociation?.guide) {
      const [start, end] = selectedAssociation.guide;
      let id = `caption-guide:${edge.id}`;
      while (occupiedIds.has(id)) id += ':guide';
      occupiedIds.add(id);
      guides.push({ id, kind: 'caption-guide', sceneEdgeId: edge.id, path: `M ${start.x} ${start.y} L ${end.x} ${end.y}`,
        stroke: edge.stroke, width: CAPTION_ASSOCIATION.guideWidth });
      reservedGuides.push(selectedAssociation.guide);
    }
  }
  return { placements, diagnostics, guides };
}
