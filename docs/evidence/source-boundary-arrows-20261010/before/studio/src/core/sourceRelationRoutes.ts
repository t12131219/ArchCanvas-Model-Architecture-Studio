import type { Architecture, Bounds, PortLayout, SceneDiagnostic, SceneNode, SceneSourceRelation } from './types.ts';
import { createOrthogonalRouter, orthogonalPathPoints } from './orthogonalRouter.ts';
import { portLayoutPoint, portRoutePath } from './portRouting.ts';

export const SOURCE_RELATION_LABEL = 'Source data dependency · execution path unresolved';
export const SOURCE_RELATION_STROKE = '#776095';
export const SOURCE_RELATION_DASH = '2 4';

/** Project static evidence through the visible hierarchy, without tensor ports.
 * A collapsed container hides internal dependencies and restores them on expand.
 * A missing card under an expanded parent is not silently turned into a proxy. */
export function routeSourceRelations(architecture: Pick<Architecture, 'nodes' | 'sourceRelations'>, nodes: readonly SceneNode[], monochrome = false, unframedIds = new Set<string>()) {
  const diagnostics: SceneDiagnostic[] = [];
  if (!architecture.sourceRelations?.length) return { relations: [] as SceneSourceRelation[], diagnostics, points: [] as { x: number; y: number }[] };
  const canonical = new Map(architecture.nodes.map(node => [node.id, node]));
  const visible = new Map(nodes.map(node => [node.id, node]));
  const project = (id: string) => {
    let current: string | undefined = id;
    while (current) {
      const node = visible.get(current);
      if (node) return current === id || !node.expanded ? node : undefined;
      current = canonical.get(current)?.parentId;
    }
    return undefined;
  };
  const groups = new Map<string, { source: SceneNode; target: SceneNode; ids: string[] }>();
  for (const relation of architecture.sourceRelations) {
    const source = project(relation.sourceId), target = project(relation.targetId);
    if (!source || !target || source.id === target.id) continue;
    const key = JSON.stringify([source.id, target.id]);
    const group = groups.get(key);
    if (group) group.ids.push(relation.id); else groups.set(key, { source, target, ids: [relation.id] });
  }
  if (!groups.size) return { relations: [] as SceneSourceRelation[], diagnostics, points: [] as { x: number; y: number }[] };
  const route = createOrthogonalRouter(nodes, unframedIds);
  const relations: SceneSourceRelation[] = [];
  for (const { source, target, ids } of groups.values()) {
    // Anchors follow the current relative geometry, including manual movement.
    const dx = target.x + target.width / 2 - source.x - source.width / 2;
    const dy = target.y + target.height / 2 - source.y - source.height / 2;
    const horizontal = Math.abs(dx) > Math.abs(dy);
    const sourceSide = horizontal ? dx >= 0 ? 'right' : 'left' : dy >= 0 ? 'bottom' : 'top';
    const targetSide = horizontal ? dx >= 0 ? 'left' : 'right' : dy >= 0 ? 'top' : 'bottom';
    const sides: [PortLayout['side'], PortLayout['side']][] = [[sourceSide, targetSide], ['bottom', 'top'], ['right', 'left'], ['left', 'right'], ['top', 'bottom']];
    const probe = ([sourceSide, targetSide]: [PortLayout['side'], PortLayout['side']]) => {
      const start = portLayoutPoint(source, { side: sourceSide, offset: .5 });
      const end = portLayoutPoint(target, { side: targetSide, offset: .5 });
      const request = { sourceId: source.id, targetId: target.id, start, end, sourceSide, targetSide,
        minimumLeadLength: 12, preferredPath: portRoutePath(start, end, sourceSide, targetSide) };
      const result = route({ ...request, candidateProbe: true });
      const length = result.points.slice(1).reduce((sum, point, i) => sum + Math.abs(point.x - result.points[i].x) + Math.abs(point.y - result.points[i].y), 0);
      return { request, result, cost: result.blockedBy.length * 1e8 + length + result.points.length * 24 };
    };
    const initial = probe(sides[0]);
    // Most local dependencies already have a clear normal route. Candidate
    // search is reserved for blocked attachments, keeping drag work bounded.
    const best = initial.result.blockedBy.length ? [...new Map(sides.slice(1).map(pair => [pair.join(':'), pair])).values()]
      .map(probe).concat(initial).sort((a, b) => a.cost - b.cost)[0] : initial;
    const result = best.result.blockedBy.length ? route(best.request) : best.result;
    const id = ids[0];
    relations.push({ id, canonicalRelationIds: ids, sourceId: source.id, targetId: target.id,
      path: result.path, stroke: monochrome ? '#56616b' : SOURCE_RELATION_STROKE, width: 1.5, dashed: true,
      evidence: architecture.sourceRelations.filter(relation => ids.includes(relation.id)) });
    if (result.blockedBy.length) diagnostics.push({ level: 'warning', code: 'layout-route-blocked',
      objectIds: result.blockedBy, message: `Source dependency "${id}" has no clear route within the routing budget (${result.blockedBy.join(', ')}). Move the reported objects or increase spacing.` });
  }
  return { relations, diagnostics, points: relations.flatMap(relation => orthogonalPathPoints(relation.path)) };
}

export function sourceRelationLegend(x: number, y: number): Bounds {
  return { x, y, width: 360, height: 24 };
}
