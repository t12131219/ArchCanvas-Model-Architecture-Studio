import type { EdgeRole, PortLayout, SceneNode } from './types.ts';
import { projectVisualPort, visualPortSide } from './nodeVisualOutline.ts';
import type { RoutePoint, RouteRequest, RouteResult } from './orthogonalRouter.ts';

export const PORT_ROUTING_BUDGET = Object.freeze({ maxNodes: 128, maxEdges: 384, maxPorts: 32, maxCandidates: 192, maxPairChecks: 100_000 });
const sides: PortLayout['side'][] = ['bottom', 'top', 'right', 'left'];
const vectors = { top: { x: 0, y: -1 }, right: { x: 1, y: 0 }, bottom: { x: 0, y: 1 }, left: { x: -1, y: 0 } };
const round = (n: number) => Math.round(n * 100) / 100;
export const portLayoutKey = (ownerId: string, nodeId: string, portId: string, role: EdgeRole) => JSON.stringify([ownerId, nodeId, portId, role]);
type PortNode = Pick<SceneNode, 'x' | 'y' | 'width' | 'height' | 'expanded' | 'headerHeight' | 'repeat'>;

/** A dimensionless offset survives node movement, resizing and frontier restoration. */
export function portLayoutPoint(node: PortNode, layout: PortLayout): RoutePoint {
  const vertical = layout.side === 'left' || layout.side === 'right';
  const low = vertical ? Math.min(node.height / 2, node.expanded ? node.headerHeight + 12 : 12) : Math.min(12, node.width / 2);
  const high = Math.max(low, (vertical ? node.height : node.width) - 12);
  const along = low + (high - low) * layout.offset;
  return projectVisualPort(node, vertical
    ? { x: node.x + (layout.side === 'right' ? node.width : 0), y: round(node.y + along) }
    : { x: round(node.x + along), y: node.y + (layout.side === 'bottom' ? node.height : 0) }, layout.side);
}
export function nearestPortLayout(node: PortNode, point: RoutePoint): PortLayout {
  const candidates = sides.map(side => {
    const vertical = side === 'left' || side === 'right';
    const low = vertical ? Math.min(node.height / 2, node.expanded ? node.headerHeight + 12 : 12) : Math.min(12, node.width / 2);
    const high = Math.max(low, (vertical ? node.height : node.width) - 12);
    const along = vertical ? point.y - node.y : point.x - node.x;
    const offset = high === low ? .5 : Math.max(0, Math.min(1, (along - low) / (high - low)));
    const layout = { side, offset: Math.round(offset * 1000) / 1000 };
    const anchor = portLayoutPoint(node, layout);
    return { layout, distance: Math.hypot(point.x - anchor.x, point.y - anchor.y) };
  });
  return candidates.sort((a, b) => a.distance - b.distance)[0].layout;
}

/** Normal leads precede corridor search; a target arrow always enters the selected side. */
export function portRoutePath(start: RoutePoint, end: RoutePoint, sourceSide: PortLayout['side'], targetSide: PortLayout['side'], lead = 12): string {
  const a = { x: round(start.x + vectors[sourceSide].x * lead), y: round(start.y + vectors[sourceSide].y * lead) };
  const b = { x: round(end.x + vectors[targetSide].x * lead), y: round(end.y + vectors[targetSide].y * lead) };
  const sourceVertical = sourceSide === 'top' || sourceSide === 'bottom', targetVertical = targetSide === 'top' || targetSide === 'bottom';
  const middle = sourceVertical && targetVertical
    ? [{ x: a.x, y: round((a.y + b.y) / 2) }, { x: b.x, y: round((a.y + b.y) / 2) }]
    : !sourceVertical && !targetVertical
      ? [{ x: round((a.x + b.x) / 2), y: a.y }, { x: round((a.x + b.x) / 2), y: b.y }]
      : [sourceVertical ? { x: a.x, y: b.y } : { x: b.x, y: a.y }];
  const points: RoutePoint[] = [];
  for (const p of [start, a, ...middle, b, end]) {
    if (points.length && p.x === points.at(-1)!.x && p.y === points.at(-1)!.y) continue;
    while (points.length > 1) {
      const u = points.at(-2)!, v = points.at(-1)!;
      const forward = u.x === v.x && v.x === p.x && (v.y - u.y) * (p.y - v.y) >= 0 || u.y === v.y && v.y === p.y && (v.x - u.x) * (p.x - v.x) >= 0;
      if (!forward) break; points.pop();
    }
    points.push(p);
  }
  return points.map((p, i) => !i ? `M ${round(p.x)} ${round(p.y)}` : p.x === points[i - 1].x ? `V ${round(p.y)}` : `H ${round(p.x)}`).join(' ');
}

export interface RoutingPort extends RoutePoint { id: string; nodeId: string; fixed: boolean }
export interface PortRouteRequest extends RouteRequest { sourcePortKey: string; targetPortKey: string }
const length = (points: RoutePoint[]) => points.slice(1).reduce((sum, p, i) => sum + Math.abs(p.x - points[i].x) + Math.abs(p.y - points[i].y), 0);
function properNormal(points: RoutePoint[], source: SceneNode, target: SceneNode) {
  if (points.length < 2) return false;
  const start = points[0], next = points[1], end = points.at(-1)!, previous = points.at(-2)!;
  const s = vectors[visualPortSide(source, start)], t = vectors[visualPortSide(target, end)];
  return (next.x - start.x) * s.x + (next.y - start.y) * s.y >= 6 - .01 &&
    (previous.x - end.x) * t.x + (previous.y - end.y) * t.y >= 6 - .01;
}

/** Independent bounded candidate assignment inspired by free-side port candidates.
 * Each binding has one anchor (including fan-out). No node or semantic binding moves.
 * Candidates must not increase blocked routes or peer crossings/overlaps. */
export function selectRoutingPorts(nodes: readonly SceneNode[], ports: readonly RoutingPort[], input: readonly PortRouteRequest[], route: (request: RouteRequest) => RouteResult) {
  const byId = new Map(nodes.map(node => [node.id, node]));
  const anchors = new Map(ports.map(port => [port.id, { ...port }]));
  const requests = input.map(request => ({ ...request }));
  if (nodes.length > PORT_ROUTING_BUDGET.maxNodes || input.length > PORT_ROUTING_BUDGET.maxEdges) return { anchors, requests };
  if (ports.every(port => port.fixed)) return { anchors, requests };
  const probe = (request: RouteRequest) => route({ ...request, candidateProbe: true });
  const results = requests.map(probe);
  const adjacent = new Map(ports.map(port => [port.id, [] as number[]]));
  requests.forEach((r, i) => { adjacent.get(r.sourcePortKey)?.push(i); adjacent.get(r.targetPortKey)?.push(i); });
  let attempts = 0, pairChecks = 0;
  const peerCost = (a: RoutePoint[], b: RoutePoint[], shared: boolean): number | undefined => {
    let conflicts = 0;
    for (let i = 1; i < a.length; i++) for (let j = 1; j < b.length; j++) {
      if (++pairChecks > PORT_ROUTING_BUDGET.maxPairChecks) return undefined;
      const p = a[i - 1], q = a[i], r = b[j - 1], s = b[j], av = p.x === q.x, bv = r.x === s.x;
      if (av !== bv) {
        const [v, w, h, k] = av ? [p, q, r, s] : [r, s, p, q];
        // Includes bend contacts, while exact shared whole-edge endpoints are allowed.
        const endpoint = [a[0], a.at(-1)!, b[0], b.at(-1)!].some(x => x.x === v.x && x.y === h.y);
        if (!endpoint && v.x >= Math.min(h.x, k.x) && v.x <= Math.max(h.x, k.x) && h.y >= Math.min(v.y, w.y) && h.y <= Math.max(v.y, w.y)) conflicts++;
      } else if (!shared && (av ? p.x === r.x : p.y === r.y)) {
        const overlap = Math.min(av ? Math.max(p.y, q.y) : Math.max(p.x, q.x), av ? Math.max(r.y, s.y) : Math.max(r.x, s.x)) -
          Math.max(av ? Math.min(p.y, q.y) : Math.min(p.x, q.x), av ? Math.min(r.y, s.y) : Math.min(r.x, s.x));
        if (overlap > .01) conflicts++;
      }
    }
    return conflicts;
  };
  const metric = (affected: Set<number>, proposed: Map<number, RouteResult>) => {
    let blocked = 0, conflicts = 0, distance = 0;
    for (const i of affected) {
      const r = proposed.get(i) ?? results[i], request = requests[i];
      blocked += r.blockedBy.length + Number(!properNormal(r.points, byId.get(request.sourceId)!, byId.get(request.targetId)!));
      const segments = r.points.slice(1).map((p, j) => ({ x: Math.sign(p.x - r.points[j].x), y: Math.sign(p.y - r.points[j].y) })).filter(v => v.x || v.y);
      const bends = segments.slice(1).filter((v, j) => v.x !== segments[j].x || v.y !== segments[j].y).length;
      distance += length(r.points) + bends * 24;
      for (let j = 0; j < requests.length; j++) {
        if (i === j || affected.has(j) && j < i) continue;
        const cost = peerCost(r.points, (proposed.get(j) ?? results[j]).points, request.tensorId !== undefined && request.tensorId === requests[j].tensorId);
        if (cost === undefined) return undefined;
        conflicts += cost;
      }
    }
    return { blocked, conflicts, distance };
  };
  // Move both ends of a connection together before the per-binding pass.
  // A reversed edge otherwise gets stuck at a locally short side detour:
  // changing either end alone is worse even though the facing pair is direct.
  const pairOrder = requests.map((request, index) => ({ index, excess: length(results[index].points) - Math.abs(request.start.x - request.end.x) - Math.abs(request.start.y - request.end.y) }))
    .sort((a, b) => b.excess - a.excess || requests[a.index].sourcePortKey.localeCompare(requests[b.index].sourcePortKey));
  for (const { index } of pairOrder) {
    const request = requests[index], source = anchors.get(request.sourcePortKey)!, target = anchors.get(request.targetPortKey)!;
    if (source.fixed && target.fixed || attempts >= PORT_ROUTING_BUDGET.maxCandidates) continue;
    const affected = new Set([...(adjacent.get(source.id) ?? []), ...(adjacent.get(target.id) ?? [])]);
    const original = metric(affected, new Map()); if (!original) break;
    const direct = [...affected].reduce((sum, i) => sum + Math.abs(requests[i].start.x - requests[i].end.x) + Math.abs(requests[i].start.y - requests[i].end.y), 0);
    if (!original.blocked && !original.conflicts && original.distance <= direct + affected.size * 48 + .01) continue;
    const options = (port: RoutingPort) => port.fixed ? [port] : sides.map(side => ({ ...port, ...portLayoutPoint(byId.get(port.nodeId)!, { side, offset: .5 }) }));
    const pairs = options(source).flatMap(a => options(target).map(b => ({ a, b, distance: Math.abs(a.x - b.x) + Math.abs(a.y - b.y) })))
      .sort((a, b) => a.distance - b.distance);
    let bestMetric = original, bestRequests: Map<number, PortRouteRequest> | undefined, bestResults: Map<number, RouteResult> | undefined;
    let bestPair: typeof pairs[number] | undefined;
    for (const pair of pairs) {
      if (++attempts > PORT_ROUTING_BUDGET.maxCandidates) break;
      if ([pair.a, pair.b].some(port => [...anchors.values()].some(other => other.id !== source.id && other.id !== target.id && other.nodeId === port.nodeId && Math.hypot(port.x - other.x, port.y - other.y) < 10))) continue;
      const changes = new Map([[source.id, pair.a], [target.id, pair.b]]), proposedRequests = new Map<number, PortRouteRequest>(), proposedResults = new Map<number, RouteResult>();
      for (const i of affected) {
        const r = requests[i], a = changes.get(r.sourcePortKey) ?? r.start, b = changes.get(r.targetPortKey) ?? r.end;
        const start = { x: a.x, y: a.y }, end = { x: b.x, y: b.y }, sourceSide = visualPortSide(byId.get(r.sourceId)!, start), targetSide = visualPortSide(byId.get(r.targetId)!, end);
        const candidate = { ...r, start, end, sourceSide, targetSide, minimumLeadLength: 12, preferredPath: portRoutePath(start, end, sourceSide, targetSide) };
        proposedRequests.set(i, candidate); proposedResults.set(i, probe(candidate));
      }
      const candidate = metric(affected, proposedResults); if (!candidate) break;
      const better = candidate.blocked < bestMetric.blocked || candidate.blocked === bestMetric.blocked && (candidate.conflicts < bestMetric.conflicts || candidate.conflicts === bestMetric.conflicts && candidate.distance < bestMetric.distance - 12);
      if (candidate.blocked <= original.blocked && candidate.conflicts <= original.conflicts && better) {
        bestMetric = candidate; bestRequests = proposedRequests; bestResults = proposedResults; bestPair = pair;
      }
    }
    if (bestPair && bestRequests && bestResults) {
      anchors.set(source.id, bestPair.a); anchors.set(target.id, bestPair.b);
      for (const [i, r] of bestRequests) { requests[i] = r; results[i] = bestResults.get(i)!; }
    }
    if (pairChecks > PORT_ROUTING_BUDGET.maxPairChecks) break;
  }
  let visited = 0;
  for (const port of [...ports].sort((a, b) => a.id.localeCompare(b.id))) {
    const affected = new Set(adjacent.get(port.id));
    if (port.fixed || !affected.size) continue;
    if (++visited > PORT_ROUTING_BUDGET.maxPorts || attempts >= PORT_ROUTING_BUDGET.maxCandidates) break;
    const node = byId.get(port.nodeId)!;
    const originalMetric = metric(affected, new Map()); if (!originalMetric) break;
    const directLength = [...affected].reduce((sum, i) => sum + Math.abs(requests[i].start.x - requests[i].end.x) + Math.abs(requests[i].start.y - requests[i].end.y), 0);
    if (!originalMetric.blocked && !originalMetric.conflicts && originalMetric.distance <= directLength + affected.size * 48 + .01) continue;
    let bestMetric = originalMetric, best = anchors.get(port.id)!, bestRequests: Map<number, PortRouteRequest> | undefined, bestResults: Map<number, RouteResult> | undefined;
    const neighbors = [...affected].map(i => requests[i].sourcePortKey === port.id ? requests[i].end : requests[i].start);
    const average = { x: neighbors.reduce((sum, p) => sum + p.x, 0) / neighbors.length, y: neighbors.reduce((sum, p) => sum + p.y, 0) / neighbors.length };
    const layouts = sides.flatMap(side => {
      const vertical = side === 'left' || side === 'right';
      const low = vertical ? 12 : 12, high = (vertical ? node.height : node.width) - 12;
      const aligned = Math.max(0, Math.min(1, ((vertical ? average.y - node.y : average.x - node.x) - low) / Math.max(1, high - low)));
      return [...new Set([.5, aligned])].map(offset => ({ side, offset }));
    });
    for (const layout of layouts) {
      if (++attempts > PORT_ROUTING_BUDGET.maxCandidates) break;
      const point = portLayoutPoint(node, layout);
      if ([...anchors.values()].some(other => other.id !== port.id && other.nodeId === port.nodeId && Math.hypot(other.x - point.x, other.y - point.y) < 10)) continue;
      const proposedRequests = new Map<number, PortRouteRequest>(), proposedResults = new Map<number, RouteResult>();
      for (const i of affected) {
        const r = requests[i], start = r.sourcePortKey === port.id ? point : r.start, end = r.targetPortKey === port.id ? point : r.end;
        const sourceSide = visualPortSide(byId.get(r.sourceId)!, start), targetSide = visualPortSide(byId.get(r.targetId)!, end);
        const request = { ...r, start, end, sourceSide, targetSide, minimumLeadLength: 12, preferredPath: portRoutePath(start, end, sourceSide, targetSide) };
        proposedRequests.set(i, request); proposedResults.set(i, probe(request));
      }
      const candidate = metric(affected, proposedResults); if (!candidate) break;
      const better = candidate.blocked < bestMetric.blocked || candidate.blocked === bestMetric.blocked &&
        (candidate.conflicts < bestMetric.conflicts || candidate.conflicts === bestMetric.conflicts && candidate.distance < bestMetric.distance - 12);
      if (candidate.blocked <= originalMetric.blocked && candidate.conflicts <= originalMetric.conflicts && better) {
        bestMetric = candidate; best = { ...port, ...point }; bestRequests = proposedRequests; bestResults = proposedResults;
      }
    }
    if (bestRequests && bestResults) {
      anchors.set(port.id, best);
      for (const [i, r] of bestRequests) { requests[i] = r; results[i] = bestResults.get(i)!; }
    }
    if (pairChecks > PORT_ROUTING_BUDGET.maxPairChecks) break;
  }
  return { anchors, requests };
}
