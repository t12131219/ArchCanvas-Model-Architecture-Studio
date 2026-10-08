import type { SceneNode } from './types.ts';
import type { RoutePoint, RouteRequest, RouteResult } from './orthogonalRouter.ts';
import { nodeVisualOutline, visualPortSide } from './nodeVisualOutline.ts';
import { routeLaneConflicts, sharedBindingPrefix } from './routeLaneConflicts.ts';

/** Independent allowance for visible lane separation after obstacle routing.
 * It applies to ordinary and auxiliary bindings alike. Work exhaustion retains
 * the last checked route, rather than moving a node or inventing a connection. */
export const READABLE_ROUTE_BUDGET = Object.freeze({ maxNodes: 1_024, maxRoutes: 512, maxRoutePoints: 4_096,
  maxCandidatesPerRoute: 64, maxCandidates: 2_048, maxAccepted: 64, maxPairChecks: 100_000,
  maxSegmentChecks: 400_000, maxObstacleChecks: 250_000 });
export const READABLE_COMPONENT_BUDGET = Object.freeze({ maxMembers: 8, maxChoicesPerRoute: 32, maxAssignments: 8_192, maxAccepted: 16 });
type Rect = { id: string; x: number; y: number; width: number; height: number };
type Metric = { crossings: number; overlap: number; contacts: number;
  crossingPoints: RoutePoint[]; contactPoints: RoutePoint[]; spans: Map<string, [number, number][]> };
const EPS = 1e-7, GAP = 8;
const round = (n: number) => Math.round(n * 100) / 100;
const equal = (a: RoutePoint, b: RoutePoint) => Math.abs(a.x - b.x) <= EPS && Math.abs(a.y - b.y) <= EPS;
const length = (points: readonly RoutePoint[]) => points.slice(1).reduce((total, p, i) => total + Math.abs(p.x - points[i].x) + Math.abs(p.y - points[i].y), 0);
function simplify(points: readonly RoutePoint[]) {
  const result: RoutePoint[] = [];
  for (const p of points) {
    if (result.length && equal(p, result.at(-1)!)) continue;
    while (result.length > 1) {
      const a = result.at(-2)!, b = result.at(-1)!;
      if (!(a.x === b.x && b.x === p.x && (b.y - a.y) * (p.y - b.y) >= 0) &&
          !(a.y === b.y && b.y === p.y && (b.x - a.x) * (p.x - b.x) >= 0)) break;
      result.pop();
    }
    result.push({ ...p });
  }
  return result;
}
const path = (points: readonly RoutePoint[]) => points.map((p, i) => i === 0 ? `M ${p.x} ${p.y}` : p.x === points[i - 1].x ? `V ${p.y}` : `H ${p.x}`).join(' ');
const enters = (a: RoutePoint, b: RoutePoint, r: Rect, gap = 0) => a.x === b.x
  ? a.x > r.x - gap + EPS && a.x < r.x + r.width + gap - EPS && Math.max(Math.min(a.y, b.y), r.y - gap) < Math.min(Math.max(a.y, b.y), r.y + r.height + gap) - EPS
  : a.y > r.y - gap + EPS && a.y < r.y + r.height + gap - EPS && Math.max(Math.min(a.x, b.x), r.x - gap) < Math.min(Math.max(a.x, b.x), r.x + r.width + gap) - EPS;
const normal = (node: SceneNode, p: RoutePoint) => {
  const side = visualPortSide(node, p);
  return { x: side === 'left' ? -1 : side === 'right' ? 1 : 0, y: side === 'top' ? -1 : side === 'bottom' ? 1 : 0 };
};

/** Refine geometry, never canonical binding/style/port identities. Every peer
 * pair is checked individually: improvements elsewhere cannot conceal a newly
 * introduced crossing or a longer overlap. Equal tensor IDs do not bypass it. */
export function refineReadableRoutes(nodes: readonly SceneNode[], requests: readonly RouteRequest[], baseline: readonly RouteResult[]) {
  const limits = READABLE_ROUTE_BUDGET, results = baseline.map(result => ({ ...result }));
  if (nodes.length > limits.maxNodes || requests.length > limits.maxRoutes || requests.length !== baseline.length ||
      baseline.reduce((sum, r) => sum + r.points.length, 0) > limits.maxRoutePoints) return results;
  const byId = new Map(nodes.map(n => [n.id, n])), geometry = baseline.map(r => simplify(r.points));
  const outlines = new Map(nodes.map(n => [n.id, nodeVisualOutline(n).rectangles.map(r => ({ id: n.id, ...r }))]));
  const ancestors = (id: string) => { const result = new Set<string>(); let parent = byId.get(id)?.parentId;
    while (parent && byId.has(parent) && !result.has(parent)) { result.add(parent); parent = byId.get(parent)?.parentId; } return result; };
  const work = { candidates: 0, accepted: 0, pairs: 0, segments: 0, obstacles: 0 };
  const exhausted = () => work.candidates >= limits.maxCandidates || work.accepted >= limits.maxAccepted ||
    work.pairs >= limits.maxPairChecks || work.segments >= limits.maxSegmentChecks || work.obstacles >= limits.maxObstacleChecks;
  const bounds = (points: readonly RoutePoint[]) => ({ left: Math.min(...points.map(p => p.x)), right: Math.max(...points.map(p => p.x)),
    top: Math.min(...points.map(p => p.y)), bottom: Math.max(...points.map(p => p.y)) });
  const boxes = geometry.map(bounds);
  const meets = (a: ReturnType<typeof bounds>, b: ReturnType<typeof bounds>) => a.right >= b.left - EPS && b.right >= a.left - EPS && a.bottom >= b.top - EPS && b.bottom >= a.top - EPS;
  const empty = (): Metric => ({ crossings: 0, contacts: 0, overlap: 0, crossingPoints: [], contactPoints: [], spans: new Map() });
  const pair = (first: readonly RoutePoint[], second: readonly RoutePoint[], self = false): Metric | undefined => {
    if (++work.pairs > limits.maxPairChecks) return undefined;
    const intersections: RoutePoint[] = [], contacts: RoutePoint[] = [], spans = new Map<string, [number, number][]>(); let overlap = 0;
    const add = (list: RoutePoint[], p: RoutePoint) => { if (!list.some(q => equal(q, p))) list.push(p); };
    for (let i = 1; i < first.length; i++) for (let j = self ? i + 2 : 1; j < second.length; j++) {
      if (++work.segments > limits.maxSegmentChecks) return undefined;
      const a = first[i - 1], b = first[i], c = second[j - 1], d = second[j], vertical = a.x === b.x, otherVertical = c.x === d.x;
      if (vertical !== otherVertical) {
        const [v, w, h, k] = vertical ? [a, b, c, d] : [c, d, a, b];
        if (v.x >= Math.min(h.x, k.x) - EPS && v.x <= Math.max(h.x, k.x) + EPS && h.y >= Math.min(v.y, w.y) - EPS && h.y <= Math.max(v.y, w.y) + EPS) {
          const p = { x: v.x, y: h.y };
          if (v.x > Math.min(h.x, k.x) + EPS && v.x < Math.max(h.x, k.x) - EPS && h.y > Math.min(v.y, w.y) + EPS && h.y < Math.max(v.y, w.y) - EPS) add(intersections, p);
          else add(contacts, p);
        }
      } else if (Math.abs((vertical ? a.x : a.y) - (vertical ? c.x : c.y)) <= EPS) {
        const low = Math.max(vertical ? Math.min(a.y, b.y) : Math.min(a.x, b.x), vertical ? Math.min(c.y, d.y) : Math.min(c.x, d.x));
        const high = Math.min(vertical ? Math.max(a.y, b.y) : Math.max(a.x, b.x), vertical ? Math.max(c.y, d.y) : Math.max(c.x, d.x));
        if (high > low + EPS) {
          overlap += high - low;
          const key = `${vertical ? 'v' : 'h'}:${vertical ? a.x : a.y}`, list = spans.get(key) ?? [];
          list.push([low, high]); spans.set(key, list);
        }
        else if (high >= low - EPS) { const p = vertical ? { x: a.x, y: low } : { x: low, y: a.y }; add(contacts, p); }
      }
    }
    return { crossings: intersections.length, contacts: contacts.length, overlap, crossingPoints: intersections, contactPoints: contacts, spans };
  };
  const bindingEdge = (i: number, points: readonly RoutePoint[]) => ({ id: String(i), sourceId: requests[i].sourceId,
    source: requests[i].canonicalSource ?? { nodeId: requests[i].sourceId, portId: `unresolved-${i}` }, tensorId: requests[i].tensorId ?? `unresolved-${i}`,
    role: requests[i].role ?? 'data' as const, path: path(points), stroke: requests[i].appearance?.stroke ?? '#000000',
    width: requests[i].appearance?.width ?? 1, dashed: requests[i].appearance?.dashed ?? false, dashPattern: requests[i].appearance?.dashPattern });
  const bindingPair = (i: number, first: readonly RoutePoint[], j: number, second: readonly RoutePoint[]) => {
    const metric = pair(first, second); if (!metric) return undefined;
    const trunk = sharedBindingPrefix(bindingEdge(i, first), bindingEdge(j, second), first, second);
    if (trunk.length < 2) return metric;
    const onTrunk = (point: RoutePoint) => trunk.slice(1).some((b, n) => {
      const a = trunk[n]; return a.x === b.x ? Math.abs(point.x - a.x) <= EPS && point.y >= Math.min(a.y, b.y) - EPS && point.y <= Math.max(a.y, b.y) + EPS
        : Math.abs(point.y - a.y) <= EPS && point.x >= Math.min(a.x, b.x) - EPS && point.x <= Math.max(a.x, b.x) + EPS;
    });
    const spans = new Map<string, [number, number][]>();
    for (const [key, original] of metric.spans) {
      let parts = original;
      for (let n = 1; n < trunk.length; n++) {
        const a = trunk[n - 1], b = trunk[n], vertical = a.x === b.x;
        if (key !== `${vertical ? 'v' : 'h'}:${vertical ? a.x : a.y}`) continue;
        const low = Math.min(vertical ? a.y : a.x, vertical ? b.y : b.x), high = Math.max(vertical ? a.y : a.x, vertical ? b.y : b.x);
        parts = parts.flatMap(([start, end]) => high <= start + EPS || low >= end - EPS ? [[start, end] as [number, number]] : [
          ...(low > start + EPS ? [[start, Math.min(end, low)] as [number, number]] : []),
          ...(high < end - EPS ? [[Math.max(start, high), end] as [number, number]] : []),
        ]);
      }
      if (parts.length) spans.set(key, parts);
    }
    const crossingPoints = metric.crossingPoints.filter(point => !onTrunk(point)), contactPoints = metric.contactPoints.filter(point => !onTrunk(point));
    return { crossings: crossingPoints.length, contacts: contactPoints.length, crossingPoints, contactPoints, spans,
      overlap: [...spans.values()].reduce((sum, parts) => sum + parts.reduce((total, [low, high]) => total + high - low, 0), 0) };
  };
  const obstacleSafe = (index: number, points: readonly RoutePoint[]) => {
    if (points.length < 2 || points.some((point, n) => !Number.isFinite(point.x) || !Number.isFinite(point.y) ||
        n > 0 && point.x !== points[n - 1].x && point.y !== points[n - 1].y)) return false;
    const request = requests[index], source = byId.get(request.sourceId), target = byId.get(request.targetId);
    if (!source || !target) return false;
    const owners = new Set([...ancestors(source.id), ...ancestors(target.id)]);
    // Component choices have already passed the full obstacle scan. This
    // final guard only protects the non-negotiable local contract: ancestor
    // headers and the two endpoint bodies may not be traversed. Unrelated
    // body corridors remain governed by the complete peer/budget checks.
    const rectangles: Rect[] = [
      ...nodes.flatMap(node => owners.has(node.id) && node.expanded
        ? [{ id: node.id, x: node.x, y: node.y, width: node.width, height: node.headerHeight }] : []),
      ...outlines.get(source.id)!, ...outlines.get(target.id)!,
    ];
    for (let segment = 1; segment < points.length; segment++) if (rectangles.some(rectangle => enters(points[segment - 1], points[segment], rectangle, 0))) return false;
    return true;
  };
  const occupied = (p: RoutePoint, m: Metric) => m.contactPoints.some(q => equal(p, q)) || [...m.spans].some(([key, spans]) => {
    const [axis, coordinate] = key.split(':'); return Math.abs((axis === 'v' ? p.x : p.y) - +coordinate) <= EPS &&
      spans.some(([low, high]) => (axis === 'v' ? p.y : p.x) >= low - EPS && (axis === 'v' ? p.y : p.x) <= high + EPS);
  });
  const inOverlap = (p: RoutePoint, m: Metric) => [...m.spans].some(([key, spans]) => {
    const [axis, coordinate] = key.split(':'); return Math.abs((axis === 'v' ? p.x : p.y) - +coordinate) <= EPS &&
      spans.some(([low, high]) => (axis === 'v' ? p.y : p.x) >= low - EPS && (axis === 'v' ? p.y : p.x) <= high + EPS);
  });
  const crossesOnlyFormerOverlap = (a: Metric, b: Metric) => a.overlap < b.overlap - EPS &&
    a.crossingPoints.every(p => b.crossingPoints.some(q => equal(p, q)) || inOverlap(p, b));
  const noWorse = (a: Metric, b: Metric) => a.crossingPoints.every(p => b.crossingPoints.some(q => equal(p, q)) ||
    crossesOnlyFormerOverlap(a, b) && inOverlap(p, b)) &&
    a.contactPoints.every(p => occupied(p, b)) && a.overlap <= b.overlap + EPS &&
    [...a.spans].every(([key, spans]) => spans.every(([low, high]) =>
      b.spans.get(key)?.some(([start, end]) => start <= low + EPS && end >= high - EPS)));
  const penalty = (m: Metric) => m.crossings * 1_000 + m.contacts * 100 + m.overlap;
  const plans = new Map<number, { candidates: RoutePoint[][]; valid: RoutePoint[][] }>();
  for (let i = 0; i < requests.length && !exhausted(); i++) {
    const request = requests[i], original = geometry[i], source = byId.get(request.sourceId), target = byId.get(request.targetId);
    if (!source || !target || baseline[i].blockedBy.length || original.length < 2 || original.length > 64) continue;
    if (original.some((p, n) => !Number.isFinite(p.x) || !Number.isFinite(p.y) || n > 0 && p.x !== original[n - 1].x && p.y !== original[n - 1].y ||
        n > 1 && (p.x - original[n - 1].x) * (original[n - 1].x - original[n - 2].x) + (p.y - original[n - 1].y) * (original[n - 1].y - original[n - 2].y) < 0)) continue;
    const start = original[0], end = original.at(-1)!, first = normal(source, start), last = normal(target, end);
    const owners = new Set([...ancestors(source.id), ...ancestors(target.id)]);
    const rectangles: Rect[] = nodes.flatMap(n => owners.has(n.id) ? n.expanded
      ? [{ id: n.id, x: n.x, y: n.y, width: n.width, height: n.headerHeight }] : [] : outlines.get(n.id)!);
    const segmentClearance = (a: RoutePoint, b: RoutePoint, r: Rect) => {
      const lowX = Math.min(a.x, b.x), highX = Math.max(a.x, b.x), lowY = Math.min(a.y, b.y), highY = Math.max(a.y, b.y);
      const dx = Math.max(r.x - highX, lowX - r.x - r.width, 0), dy = Math.max(r.y - highY, lowY - r.y - r.height, 0);
      return Math.max(dx, dy);
    };
    const previousClearance = new Map(rectangles.map(r => [r, Math.min(...original.slice(1).flatMap((b, n) =>
      r.id === source.id && n === 0 || r.id === target.id && n === original.length - 2 ? [] : [segmentClearance(original[n], b, r)]))]));
    const clear = (candidate: readonly RoutePoint[], gap: number, retainExistingClearance = false) => {
      for (let segment = 1; segment < candidate.length; segment++) {
        const a = candidate[segment - 1], b = candidate[segment];
        for (const r of rectangles) {
          if (++work.obstacles > limits.maxObstacleChecks) return false;
          const terminal = r.id === source.id && segment === 1 || r.id === target.id && segment === candidate.length - 1;
          if (enters(a, b, r, terminal ? 0 : gap)) {
            // Some fixed saved layouts cannot fit eight units between two
            // boundaries. Retain that obstacle's measured baseline clearance,
            // never its body intrusion and never a worse margin elsewhere.
            if (terminal || !retainExistingClearance || enters(a, b, r, 0) ||
                segmentClearance(a, b, r) < Math.min(gap, previousClearance.get(r)!) - EPS) return false;
          }
        }
        // Crossing an ancestor boundary is necessary. Running alongside it
        // needs breathing room; a border is never a free routing lane.
        for (const id of owners) {
          const n = byId.get(id)!; if (!n.expanded) continue;
          if (++work.obstacles > limits.maxObstacleChecks) return false;
          const vertical = a.x === b.x;
          if (vertical && Math.min(Math.max(a.y, b.y), n.y + n.height) - Math.max(Math.min(a.y, b.y), n.y) > GAP &&
              Math.min(Math.abs(a.x - n.x), Math.abs(a.x - n.x - n.width)) < gap - EPS) return false;
          if (!vertical && Math.min(Math.max(a.x, b.x), n.x + n.width) - Math.max(Math.min(a.x, b.x), n.x) > GAP &&
              Math.min(Math.abs(a.y - n.y), Math.abs(a.y - n.y - n.height)) < gap - EPS) return false;
        }
      }
      return true;
    };
    const originalClear = clear(original, GAP);
    // The obstacle router's established six-unit clearance is a floor, not a
    // new relaxation: preserve it when a saved header-to-node gap cannot fit
    // the preferred eight units at both ends. Never shrink an eight-unit
    // route to six. Body/header penetration remains forbidden in all cases.
    const clearance = request.role === 'mask' || originalClear ? GAP : 6;
    // An alternate side of a wide expanded container can legitimately be
    // hundreds of units longer than the shared lane. A fixed +64 cap made
    // that escape impossible even when it is the only separated corridor.
    // Bound the detour by the local hierarchy's geometric span, not a model
    // name, and still require every peer pair and obstacle to remain safe.
    const detourAllowance = Math.max(64, ...[...owners].map(id => {
      const n = byId.get(id)!; return n.expanded ? 2 * (n.width + n.headerHeight + GAP) : 0;
    }));
    const previous = geometry.map((points, j) => j === i || !meets(boxes[i], boxes[j]) ? empty() : bindingPair(i, original, j, points));
    if (previous.some(metric => !metric) || exhausted()) break;
    const beforePenalty = previous.reduce((sum, metric) => sum + penalty(metric!), 0), originalCost = length(original) + (original.length - 2) * 18;
    // The sparse 300-layer chain has no conflict or detour to improve. Reject
    // it before building candidate axes; do not spend a quadratic candidate
    // search on each adjacent straight binding during every pointer move.
    if (originalClear && !beforePenalty && original.length <= 4 &&
        length(original) <= Math.abs(start.x - end.x) + Math.abs(start.y - end.y) + EPS) continue;
    const originalSelf = pair(original, original, true);
    if (!originalSelf || originalSelf.crossings || originalSelf.overlap || originalSelf.contacts) continue;
    const coordinates = (axis: 'x' | 'y') => {
      const values = new Set<number>(original.map(p => p[axis]));
      for (const n of nodes) {
        const bounds = nodeVisualOutline(n).bounds;
        for (const gap of [GAP, 18, 28]) {
          values.add(round((axis === 'x' ? bounds.x : bounds.y) - gap));
          values.add(round((axis === 'x' ? bounds.x + bounds.width : bounds.y + bounds.height) + gap));
          if (n.expanded) { values.add(round((axis === 'x' ? bounds.x : bounds.y) + gap)); values.add(round((axis === 'x' ? bounds.x + bounds.width : bounds.y + bounds.height) - gap)); }
        }
      }
      // Nearby occupied lanes get distinct ±8 coordinates. They are candidates
      // only; complete-batch acceptance still checks every binding.
      for (const points of geometry) for (const p of points) if (p.y >= Math.min(start.y, end.y) - 30 && p.y <= Math.max(start.y, end.y) + 30)
        for (const gap of [-GAP, GAP]) values.add(round(p[axis] + gap));
      const low = Math.min(start[axis], end[axis]), high = Math.max(start[axis], end[axis]);
      return [...values].sort((a, b) => Math.max(low - a, a - high, 0) - Math.max(low - b, b - high, 0) ||
        Math.min(Math.abs(a - start[axis]), Math.abs(a - end[axis])) - Math.min(Math.abs(b - start[axis]), Math.abs(b - end[axis])) || a - b).slice(0, 30);
    };
    // A nearby-axis cap can omit every corridor outside a wide ancestor
    // header. Reserve candidates for those boundaries before inexpensive
    // paths through the header consume the per-route allowance. Wider frames
    // come first; no fixture identity or tensor name participates.
    const escapeAxes = (axis: 'x' | 'y') => {
      const perpendicular = axis === 'x' ? 'y' : 'x';
      const low = Math.min(start[perpendicular], end[perpendicular]);
      const high = Math.max(start[perpendicular], end[perpendicular]);
      const frames = [...owners].map(id => byId.get(id)!).filter(n => n.expanded &&
        (axis === 'x' ? n.y < high && n.y + n.headerHeight > low : n.x < high && n.x + n.width > low))
        .sort((a, b) => (axis === 'x' ? b.width - a.width : b.headerHeight - a.headerHeight) || a.id.localeCompare(b.id));
      return [...new Set(frames.flatMap(n => axis === 'x'
        ? [round(n.x - GAP), round(n.x - GAP * 2), round(n.x + n.width + GAP), round(n.x + n.width + GAP * 2)]
        : [round(n.y - GAP), round(n.y - GAP * 2), round(n.y + n.headerHeight + GAP), round(n.y + n.headerHeight + GAP * 2)]))].slice(0, 8);
    };
    const xs = coordinates('x'), ys = coordinates('y'), escapeXs = first.y || last.y ? escapeAxes('x') : [],
      escapeYs = first.x || last.x ? escapeAxes('y') : [], generated = new Map<string, RoutePoint[]>(), escapes = new Set<string>(), doglegs = new Set<string>(), peerDetours = new Set<string>(), maskLocal = new Set<string>();
    const add = (points: RoutePoint[], escape = false, dogleg = false) => {
      const candidate = simplify(points);
      // Every later check (obstacle entry, pair intersections and path
      // serialization) assumes a true orthogonal polyline.  In particular,
      // peer detours may choose different source/target rails; the bridge
      // between those rails must still be split into two axis-aligned legs.
      // Reject malformed candidates at publication time instead of letting
      // `path()` silently encode a diagonal as an `H` command.
      if (candidate.length < 2 || candidate.length > original.length + 2 ||
          candidate.some((point, index) => index > 0 && point.x !== candidate[index - 1].x && point.y !== candidate[index - 1].y) ||
          path(candidate) === path(original)) return;
      const p = candidate[1], q = candidate.at(-2)!;
      if ((p.x - start.x) * first.x + (p.y - start.y) * first.y < clearance - EPS ||
          (q.x - end.x) * last.x + (q.y - end.y) * last.y < Math.min(clearance, length(original.slice(-2))) - EPS ||
          first.x && p.y !== start.y || first.y && p.x !== start.x || last.x && q.y !== end.y || last.y && q.x !== end.x) return;
      if (length(candidate) > length(original) + detourAllowance) return;
      const key = path(candidate); generated.set(key, candidate); if (escape) escapes.add(key); if (dogleg) doglegs.add(key);
    };
    // Source and target lead lengths are independent. A target immediately
    // below an ancestor header may only admit an eight-unit final lead, while
    // a fan-out needs a longer source lead to separate the two top corridors.
    const sourceLeads = request.role === 'mask' ? [GAP, 18, 28] : [...new Set([GAP, 18, 28, Math.max(6, Math.min(GAP, length(original.slice(0, 2))))])];
    const targetLeads = request.role === 'mask' ? [GAP, 18, 28] : [...new Set([Math.max(6, Math.min(GAP, length(original.slice(-2)))), GAP, 18, 28])];
    for (const targetLead of targetLeads) for (const sourceLead of sourceLeads) {
      const a = { x: start.x + first.x * sourceLead, y: start.y + first.y * sourceLead }, b = { x: end.x + last.x * targetLead, y: end.y + last.y * targetLead };
      for (const x of escapeXs) add([start, a, { x, y: a.y }, { x, y: b.y }, b, end], true);
      for (const y of escapeYs) add([start, a, { x: a.x, y }, { x: b.x, y }, b, end], true);
      add([start, a, { x: b.x, y: a.y }, b, end]); add([start, a, { x: a.x, y: b.y }, b, end]);
      for (const x of xs) add([start, a, { x, y: a.y }, { x, y: b.y }, b, end]);
      for (const y of ys) add([start, a, { x: a.x, y }, { x: b.x, y }, b, end]);
      // A frame can have a free header rail and a free internal side lane,
      // while an auxiliary binding occupies its outside lane. One dogleg
      // enters below the header, then travels beside the target's body.
      // Reserve these geometry-derived routes independently of the one-lane
      // candidates; no operator, fixture or tensor name participates.
      if (first.y && last.y) {
        const targetBounds = nodeVisualOutline(target).bounds;
        const targetLanes = [...new Set([round(targetBounds.x - GAP), round(targetBounds.x + targetBounds.width + GAP), ...escapeXs])];
        for (const id of owners) {
          const frame = byId.get(id)!; if (!frame.expanded) continue;
          for (const gap of [6, GAP, 18]) {
            const rail = round(frame.y + frame.headerHeight + gap);
            if (rail <= Math.min(a.y, b.y) || rail >= Math.max(a.y, b.y)) continue;
            for (const x of escapeXs) for (const lane of targetLanes)
              add([start, a, { x, y: a.y }, { x, y: rail }, { x: lane, y: rail }, { x: lane, y: b.y }, b, end], false, true);
          }
        }
      }
    }
    // Preserve the established mask-rail correction even when the source
    // route is otherwise considered clear. Its first horizontal rail is a
    // presentation clearance, not a semantic port move; retain all later
    // bends and let the complete peer check decide whether it is admissible.
    if (request.role === 'mask' && first.y && original.length >= 3) {
      const y = start.y + first.y * Math.max(GAP, Math.abs(original[1].y - start.y));
      const lifted = original.map((point, n) => n === 1 || n === 2 ? { ...point, y } : { ...point });
      for (const dx of [-2, 0, 2]) { const candidate = lifted.map((point, n) => n >= 2 && n < lifted.length - 1 && point.x === original[2].x ? {...point, x: point.x + dx} : point); add(candidate, true); maskLocal.add(path(simplify(candidate))); }
    }
    // Keep the existing route shape as a local candidate. Moving each
    // interior lane by two units can give a six-unit obstacle escape the
    // eight-unit breathing room without replacing it with a distant axis.
    // Endpoint coordinates stay literal; the usual normals, body clearance,
    // self-intersection and every peer-pair check still govern acceptance.
    for (const dx of [-2, 0, 2]) for (const dy of [-2, 0, 2]) {
      if (!dx && !dy) continue;
      const candidate = original.map((p, index) => index === 0 || index === original.length - 1 ? { ...p } : {
        x: p.x + (index === 1 && first.y || index === original.length - 2 && last.y ? 0 : dx),
        y: p.y + (index === 1 && first.x || index === original.length - 2 && last.x ? 0 : dy),
      });
      if (candidate.some((p, index) => index > 0 && p.x !== candidate[index - 1].x && p.y !== candidate[index - 1].y ||
          index > 1 && (p.x - candidate[index - 1].x) * (candidate[index - 1].x - candidate[index - 2].x) +
            (p.y - candidate[index - 1].y) * (candidate[index - 1].y - candidate[index - 2].y) < 0)) continue;
      add(candidate, true);
    }
    // If a peer occupies the only local lane, route around the peer's
    // derived corridor before considering the bounded component assignment.
    // The corridor comes from geometry, so this applies equally to data,
    // residual, memory and mask bindings without naming a model or fixture.
    for (let j = 0; j < geometry.length; j++) {
      if (j === i || !meets(boxes[i], boxes[j])) continue;
      const peerMetric = bindingPair(i, geometry[i], j, geometry[j]);
      if (!peerMetric || (peerMetric.overlap <= EPS && !peerMetric.crossings && !peerMetric.contacts)) continue;
      const peer = boxes[j], peerXs = [GAP, 18, 28].flatMap(gap => [round(peer.left - gap), round(peer.right + gap)]), peerYs = [GAP, 18, 28].flatMap(gap => [round(peer.top - gap), round(peer.bottom + gap)]);
      const peerA = { x: start.x + first.x * sourceLeads[0], y: start.y + first.y * sourceLeads[0] };
      const peerB = { x: end.x + last.x * targetLeads[0], y: end.y + last.y * targetLeads[0] };
      for (const rail of peerYs) {
        for (const targetRail of [rail, ...peerYs]) {
          const candidate = [start, peerA, { x: peerA.x, y: rail }, { x: peerB.x, y: rail },
            { x: peerB.x, y: targetRail }, peerB, end];
          add(candidate, true, true); const key = path(simplify(candidate)); if (generated.has(key)) peerDetours.add(key);
        }
      }
      for (const rail of peerXs) {
        for (const targetRail of [rail, ...peerXs]) {
          const candidate = [start, peerA, { x: rail, y: peerA.y }, { x: rail, y: peerB.y },
            { x: targetRail, y: peerB.y }, peerB, end];
          add(candidate, true, true); const key = path(simplify(candidate)); if (generated.has(key)) peerDetours.add(key);
        }
      }
    }
    const reservedKeys = [...new Set([...maskLocal].filter(key => generated.has(key)).concat([...peerDetours].slice(0, limits.maxCandidatesPerRoute / 4))
      .concat([...escapes].slice(0, limits.maxCandidatesPerRoute / 4)).concat([...doglegs].slice(0, limits.maxCandidatesPerRoute / 4)))];
    const reserved = reservedKeys.map(key => generated.get(key)!);
    const candidates = [...reserved, ...[...generated.values()].filter(candidate => !reserved.some(p => path(p) === path(candidate)))
      .sort((a, b) => length(a) + (a.length - 2) * 18 - length(b) - (b.length - 2) * 18 || path(a).localeCompare(path(b)))
      .slice(0, limits.maxCandidatesPerRoute - reserved.length)];
    const valid: RoutePoint[][] = []; plans.set(i, { candidates, valid });
    let best: RoutePoint[] | undefined, bestPenalty = beforePenalty, bestCost = originalCost;
    for (const candidate of candidates) {
      if (exhausted()) break; work.candidates++;
      if (!clear(candidate, clearance)) continue;
      const self = pair(candidate, candidate, true); if (!self || self.crossings || self.overlap || self.contacts) continue;
      valid.push(candidate);
      let sum = 0, safe = true;
      const candidateBounds = bounds(candidate);
      for (let j = 0; j < geometry.length; j++) {
        if (j === i || !meets(candidateBounds, boxes[j]) && !meets(boxes[i], boxes[j])) continue;
        const after = bindingPair(i, candidate, j, geometry[j]); if (!after || !noWorse(after, previous[j]!)) { safe = false; break; } sum += penalty(after);
      }
      const cost = length(candidate) + (candidate.length - 2) * 18;
      const forceBreathingRoom = request.role === 'mask' && !originalClear;
      if (safe && (forceBreathingRoom && best === undefined || sum < bestPenalty - EPS || Math.abs(sum - bestPenalty) <= EPS &&
          (cost < bestCost - EPS || forceBreathingRoom && best === undefined && cost <= originalCost + detourAllowance))) {
        best = candidate; bestPenalty = sum; bestCost = cost;
      }
    }
    if (best) { geometry[i] = best; boxes[i] = bounds(best); results[i] = { path: path(best), points: best, changed: true, blockedBy: [] }; work.accepted++; }
  }
  // Two individually safe routes may both need to leave their current lane:
  // moving only one first creates a temporary crossing, which the pairwise
  // guard correctly rejects. Evaluate small complete conflict components in
  // one transaction, with the identical guard applied to their final geometry
  // and every external peer. No intermediate path is ever published.
  // Component refinement has an independent deterministic allowance. The
  // per-route pass may have consumed its own candidate budget while preparing
  // the component choices; reset only the phase counters before this second
  // bounded search so a small conflicted component still gets evaluated.
  work.candidates = 0; work.accepted = 0; work.pairs = 0; work.segments = 0; work.obstacles = 0;
  if (!exhausted()) {
    const publicEdges = requests.map((request, i) => ({ id: String(i), sourceId: request.sourceId,
      source: request.canonicalSource ?? { nodeId: request.sourceId, portId: `unresolved-${i}` }, tensorId: request.tensorId ?? `unresolved-${i}`,
      role: request.role ?? 'data' as const, path: results[i].path, stroke: request.appearance?.stroke ?? '#000000',
      width: request.appearance?.width ?? 1, dashed: request.appearance?.dashed ?? false, dashPattern: request.appearance?.dashPattern }));
    const adjacency = new Map<number, Set<number>>();
    for (const conflict of routeLaneConflicts(publicEdges)) {
      const a = +conflict.firstId, b = +conflict.secondId;
      if (!plans.has(a) || !plans.has(b)) continue;
      const first = adjacency.get(a) ?? new Set<number>(), second = adjacency.get(b) ?? new Set<number>();
      first.add(b); second.add(a); adjacency.set(a, first); adjacency.set(b, second);
    }
    // A candidate that leaves an existing ambiguous pair can encounter a
    // third lane which was clear in the baseline. Pull that lane into the
    // same bounded component so the assignment can move all affected routes
    // atomically. This keeps the strict external-peer guard for routes that
    // remain outside the actual candidate corridor.
    for (const root of [...adjacency.keys()]) {
      const pending = [root], visited = new Set<number>();
      while (pending.length) {
        const i = pending.pop()!; if (visited.has(i)) continue; visited.add(i);
        const plan = plans.get(i); if (!plan) continue;
        for (const j of plans.keys()) {
          if (i === j || adjacency.get(i)?.has(j)) continue;
          const before = meets(boxes[i], boxes[j]) ? bindingPair(i, geometry[i], j, geometry[j]) : empty();
          if (!before) continue;
          let touched = false;
          for (const candidate of plan.valid) {
            const after = meets(bounds(candidate), boxes[j]) ? bindingPair(i, candidate, j, geometry[j]) : empty();
            if (!after) break;
            if (after.crossings > before.crossings || after.overlap > before.overlap + EPS || after.contacts > before.contacts) { touched = true; break; }
          }
          if (!touched) continue;
          const first = adjacency.get(i) ?? new Set<number>(), second = adjacency.get(j) ?? new Set<number>();
          first.add(j); second.add(i); adjacency.set(i, first); adjacency.set(j, second); pending.push(j);
        }
      }
    }
    const seen = new Set<number>(), componentLimits = READABLE_COMPONENT_BUDGET; let assignments = 0, accepted = 0;
    for (const root of adjacency.keys()) {
      if (seen.has(root) || exhausted() || accepted >= componentLimits.maxAccepted) continue;
      const members: number[] = [], pending = [root];
      while (pending.length) { const i = pending.pop()!; if (seen.has(i)) continue; seen.add(i); members.push(i); pending.push(...adjacency.get(i) ?? []); }
      members.sort((a, b) => a - b);
      if (members.length > componentLimits.maxMembers) continue;
      const choices = members.map(i => {
        const valid = plans.get(i)!.valid.filter(candidate => obstacleSafe(i, candidate));
        const simple = valid.filter(candidate => candidate.length <= 6), dogleg = valid.filter(candidate => candidate.length > 6);
        const reservedDoglegs = dogleg.slice(0, Math.floor(componentLimits.maxChoicesPerRoute / 2));
        return [geometry[i], ...simple.slice(0, componentLimits.maxChoicesPerRoute - 1 - reservedDoglegs.length), ...reservedDoglegs];
      });
      const memberSet = new Set(members), pairs: { i: number; j: number; before: Metric }[] = [];
      for (let i = 0; i < geometry.length; i++) for (let j = i + 1; j < geometry.length; j++) if (memberSet.has(i) || memberSet.has(j)) {
        const before = meets(boxes[i], boxes[j]) ? bindingPair(i, geometry[i], j, geometry[j]) : empty();
        if (!before) break;
        pairs.push({ i, j, before });
      }
      if (exhausted()) break;
      const beforePenalty = pairs.reduce((sum, value) => sum + penalty(value.before), 0);
      const beforeCost = members.reduce((sum, i) => sum + length(geometry[i]) + (geometry[i].length - 2) * 18, 0);
      const beforeOverlap = pairs.reduce((sum, value) => sum + value.before.overlap, 0);
      let best: RoutePoint[][] | undefined, bestPenalty = beforePenalty, bestCost = beforeCost, bestOverlap = beforeOverlap;
      // Check external lanes once per choice, and reject incompatible internal
      // choices as soon as both are assigned. A bounded search must not spend
      // its whole allowance on permutations sharing the first route unchanged.
      const external = choices.map((options, n) => options.map(candidate => {
        let sum = 0, overlap = 0;
        for (const { i, j, before } of pairs) {
          if (memberSet.has(i) && memberSet.has(j) || i !== members[n] && j !== members[n]) continue;
          const other = geometry[i === members[n] ? j : i];
          const after = meets(bounds(candidate), bounds(other)) ? bindingPair(members[n], candidate, i === members[n] ? j : i, other) : empty();
          if (!after || !noWorse(after, before)) return undefined;
          sum += penalty(after); overlap += after.overlap;
        }
        return { sum, overlap };
      }));
      const internal = new Map<string, Metric | undefined>();
      const baselinePairs = new Map(pairs.map(value => [`${value.i}:${value.j}`, value.before]));
      const option = (a: number, ai: number, b: number, bi: number) => {
        const key = `${a}:${ai}:${b}:${bi}`;
        if (internal.has(key)) return internal.get(key);
        const after = meets(bounds(choices[a][ai]), bounds(choices[b][bi])) ? bindingPair(members[a], choices[a][ai], members[b], choices[b][bi]) : empty();
        const before = baselinePairs.get(`${Math.min(members[a], members[b])}:${Math.max(members[a], members[b])}`)!;
        const result = after && noWorse(after, before) ? after : undefined;
        internal.set(key, result); return result;
      };
      const selection: number[] = [];
      const visit = (index: number, sum: number, totalOverlap: number, cost: number) => {
        if (exhausted() || assignments >= componentLimits.maxAssignments) return;
        if (index === members.length) {
          assignments++;
          if (totalOverlap < bestOverlap - EPS || Math.abs(totalOverlap - bestOverlap) <= EPS &&
              (sum < bestPenalty - EPS || Math.abs(sum - bestPenalty) <= EPS && cost < bestCost - EPS)) {
            best = selection.map((choice, n) => choices[n][choice]); bestPenalty = sum; bestCost = cost; bestOverlap = totalOverlap;
          }
          return;
        }
        for (let choice = 0; choice < choices[index].length; choice++) {
          const outside = external[index][choice]; if (!outside) continue;
          let nextSum = sum + outside.sum, nextOverlap = totalOverlap + outside.overlap, safe = true;
          for (let previous = 0; previous < index; previous++) {
            const after = option(previous, selection[previous], index, choice);
            if (!after) { safe = false; break; }
            nextSum += penalty(after); nextOverlap += after.overlap;
          }
          if (!safe) continue;
          selection[index] = choice;
          const points = choices[index][choice];
          visit(index + 1, nextSum, nextOverlap, cost + length(points) + (points.length - 2) * 18);
          if (exhausted() || assignments >= componentLimits.maxAssignments) break;
        }
      };
      visit(0, 0, 0, 0);
      if (best) {
        for (const [n, i] of members.entries()) { geometry[i] = best[n]; boxes[i] = bounds(best[n]); results[i] = { path: path(best[n]), points: best[n], changed: true, blockedBy: [] }; }
        accepted++;
        // Pair-level refinement examines every candidate pair after the
        // bounded component search. It is atomic and applies the same strict
        // peer guard, so no temporary crossing is published.
        work.pairs = 0; work.segments = 0; work.obstacles = 0; work.candidates = 0;
        for (const { i, j } of pairs) {
          // The component assignment has already changed several members.
          // Recompute this pair's baseline from the geometry that is about to
          // be published; the pre-component metric is stale and can make a
          // later pair pass reintroduce an overlap that the assignment removed.
          const before = bindingPair(i, geometry[i], j, geometry[j]);
          if (!before || before.overlap <= EPS && !before.crossings && !before.contacts) continue;
          const optionsI = choices[members.indexOf(i)] ?? [], optionsJ = choices[members.indexOf(j)] ?? [];
          let pairBest: [RoutePoint[], RoutePoint[]] | undefined, pairScore = Number.POSITIVE_INFINITY;
          for (const candidateI of optionsI) for (const candidateJ of optionsJ) {
            const pairMetric = bindingPair(i, candidateI, j, candidateJ); if (!pairMetric || !noWorse(pairMetric, before)) continue;
            let score = penalty(pairMetric), safe = true;
            for (const k of geometry.keys()) {
              if (k === i || k === j || !meets(bounds(candidateI), boxes[k]) && !meets(boxes[i], boxes[k])) continue;
              const oldMetric = bindingPair(i, geometry[i], k, geometry[k]), nextMetric = bindingPair(i, candidateI, k, geometry[k]);
              if (!oldMetric || !nextMetric || !noWorse(nextMetric, oldMetric)) { safe = false; break; } score += penalty(nextMetric);
            }
            if (!safe) continue;
            for (const k of geometry.keys()) {
              if (k === i || k === j || !meets(bounds(candidateJ), boxes[k]) && !meets(boxes[j], boxes[k])) continue;
              const oldMetric = bindingPair(j, geometry[j], k, geometry[k]), nextMetric = bindingPair(j, candidateJ, k, geometry[k]);
              if (!oldMetric || !nextMetric || !noWorse(nextMetric, oldMetric)) { safe = false; break; } score += penalty(nextMetric);
            }
            if (safe && score < pairScore - EPS &&
                (pairMetric.crossings < before.crossings || pairMetric.contacts < before.contacts || pairMetric.overlap < before.overlap - EPS)) {
              pairBest = [candidateI, candidateJ]; pairScore = score;
            }
          }
          if (pairBest) {
            geometry[i] = pairBest[0]; boxes[i] = bounds(pairBest[0]); results[i] = { path: path(pairBest[0]), points: pairBest[0], changed: true, blockedBy: [] };
            geometry[j] = pairBest[1]; boxes[j] = bounds(pairBest[1]); results[j] = { path: path(pairBest[1]), points: pairBest[1], changed: true, blockedBy: [] };
          }
        }
      }
    }
    // A component's separation can release another route's outside corridor.
    // Reuse the already bounded candidates, rechecking every current peer.
    if (accepted) for (const [i, plan] of plans) {
      if (exhausted()) break;
      const original = geometry[i], previous = geometry.map((points, j) => j === i || !meets(boxes[i], boxes[j]) ? empty() : bindingPair(i, original, j, points));
      if (previous.some(metric => !metric)) break;
      let best: RoutePoint[] | undefined, bestPenalty = previous.reduce((sum, metric) => sum + penalty(metric!), 0), bestCost = length(original) + (original.length - 2) * 18;
      for (const candidate of plan.valid) {
        if (exhausted()) break;
        work.candidates++;
        const box = bounds(candidate); let sum = 0, safe = true;
        for (let j = 0; j < geometry.length; j++) {
          if (i === j || !meets(box, boxes[j]) && !meets(boxes[i], boxes[j])) continue;
          const after = bindingPair(i, candidate, j, geometry[j]);
          const maskClearance = requests[i].role === 'mask' && Math.abs(candidate[1].y - original[0].y) >= GAP - EPS;
          if (!after || (!noWorse(after, previous[j]!) && !(maskClearance && after.crossings <= previous[j]!.crossings && after.overlap <= previous[j]!.overlap + EPS && after.contacts <= previous[j]!.contacts))) { safe = false; break; } sum += penalty(after);
        }
        const cost = length(candidate) + (candidate.length - 2) * 18;
        if (safe && (sum < bestPenalty - EPS || Math.abs(sum - bestPenalty) <= EPS && cost < bestCost - EPS)) { best = candidate; bestPenalty = sum; bestCost = cost; }
      }
      if (best) { geometry[i] = best; boxes[i] = bounds(best); results[i] = { path: path(best), points: best, changed: true, blockedBy: [] }; work.accepted++; }
    }
  }
  // Keep the role-specific breathing contract even when the translated or
  // mirrored baseline has no peer conflict that would otherwise cause the
  // bounded candidate pass to select an alternate. This post-pass only edits
  // the first lead and its immediate rail, preserving both endpoints.
  for (let i = 0; i < requests.length; i++) {
    if (requests[i].role !== 'mask') continue;
    const current = results[i].points, start = current[0], lead = current[1];
    if (!lead || Math.abs(start.y - lead.y) >= GAP - EPS || (lead.x !== start.x && Math.abs(start.x - lead.x) >= GAP - EPS)) continue;
    const horizontal = lead.y === start.y, sign = horizontal ? Math.sign(lead.x - start.x) || 1 : Math.sign(lead.y - start.y) || 1;
    const candidate = current.map((point, n) => n === 1 ? horizontal ? { ...point, x: start.x + sign * GAP } : { ...point, y: start.y + sign * GAP } : { ...point });
    if (candidate.length > 3) candidate[2] = horizontal ? { ...candidate[2], x: candidate[1].x } : { ...candidate[2], y: candidate[1].y };
    const self = pair(candidate, candidate, true); if (!self || self.crossings || self.overlap || self.contacts) continue;
    let safe = true;
    for (let j = 0; j < results.length; j++) if (i !== j) {
      const before = bindingPair(i, current, j, results[j].points), after = bindingPair(i, candidate, j, results[j].points);
      if (!before || !after || !noWorse(after, before)) { safe = false; break; }
    }
    if (safe) {
      geometry[i] = candidate; boxes[i] = bounds(candidate);
      results[i] = { ...results[i], path: path(candidate), points: candidate, changed: true };
    }
  }
  // Repair only local endpoint/header violations introduced by the complete
  // component assignment. Most route choices remain untouched; an invalid
  // choice is replaced by the best already-validated candidate for that
  // request, preserving the broader lane optimization.
  for (let i = 0; i < results.length; i++) if (requests[i].role !== 'mask' && !obstacleSafe(i, results[i].points)) {
    let replacement: RoutePoint[] | undefined, replacementOverlap = Number.POSITIVE_INFINITY, replacementCrossings = Number.POSITIVE_INFINITY,
      replacementContacts = Number.POSITIVE_INFINITY, replacementScore = Number.POSITIVE_INFINITY, replacementCost = Number.POSITIVE_INFINITY;
    for (const candidate of plans.get(i)?.valid ?? []) {
      if (!obstacleSafe(i, candidate)) continue;
      let score = 0, overlap = 0, crossings = 0, contacts = 0, valid = true;
      for (let j = 0; j < geometry.length; j++) {
        if (i === j || !meets(bounds(candidate), boxes[j]) && !meets(boxes[i], boxes[j])) continue;
        const metric = bindingPair(i, candidate, j, geometry[j]);
        if (!metric) { valid = false; break; }
        score += penalty(metric); overlap += metric.overlap; crossings += metric.crossings; contacts += metric.contacts;
      }
      const cost = length(candidate) + (candidate.length - 2) * 18;
      if (valid && (overlap < replacementOverlap - EPS || Math.abs(overlap - replacementOverlap) <= EPS &&
          (crossings < replacementCrossings || crossings === replacementCrossings &&
            (contacts < replacementContacts || contacts === replacementContacts &&
              (score < replacementScore - EPS || Math.abs(score - replacementScore) <= EPS && cost < replacementCost - EPS))))) {
        replacement = candidate; replacementOverlap = overlap; replacementCrossings = crossings; replacementContacts = contacts;
        replacementScore = score; replacementCost = cost;
      }
    }
    if (replacement) {
      geometry[i] = replacement; boxes[i] = bounds(replacement);
      results[i] = { ...results[i], path: path(replacement), points: replacement, changed: true, blockedBy: [] };
    } else {
      geometry[i] = baseline[i].points.slice(); boxes[i] = bounds(geometry[i]);
      results[i] = { ...baseline[i], points: geometry[i] };
    }
  }
  return results;
}
