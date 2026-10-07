import type { AuthoredDraft, DraftCatalog } from './authoring.ts';

export type DraftEdgeRole = 'data' | 'residual';

/** Match the generated-source contract: a strict ancestor feeds Add's bypass.
 * Labels, positions and route lengths never establish a residual connection.
 * Incomplete, unknown or cyclic components keep ordinary data presentation.
 */
export function draftEdgeRoles(draft: AuthoredDraft, catalog: DraftCatalog): Map<string, DraftEdgeRole> {
  const roles = new Map(draft.edges.map(edge => [edge.id, 'data' as DraftEdgeRole]));
  const nodes = new Map(draft.nodes.map(node => [node.id, node]));
  if (nodes.size !== draft.nodes.length || roles.size !== draft.edges.length) return roles;
  const modules = new Map(draft.nodes.map(node => {
    const matches = catalog.modules.filter(module => module.kind === node.kind);
    return [node.id, matches.length === 1 ? matches[0] : null] as const;
  }));
  const adjacent = new Map(draft.nodes.map(node => [node.id, new Set<string>()]));
  const invalid = new Set<string>(), incoming = new Map<string, typeof draft.edges>();
  for (const node of draft.nodes) {
    const module = modules.get(node.id);
    if (!module || new Set(module.ports.map(port => port.id)).size !== module.ports.length
      || module.ports.some(port => port.type !== 'tensor' || !['in', 'out'].includes(port.direction))) invalid.add(node.id);
  }
  for (const edge of draft.edges) {
    const sourceExists = nodes.has(edge.source.nodeId), targetExists = nodes.has(edge.target.nodeId);
    if (sourceExists && targetExists) {
      adjacent.get(edge.source.nodeId)!.add(edge.target.nodeId);
      adjacent.get(edge.target.nodeId)!.add(edge.source.nodeId);
    }
    const sourcePort = modules.get(edge.source.nodeId)?.ports.find(port => port.id === edge.source.portId);
    const targetPort = modules.get(edge.target.nodeId)?.ports.find(port => port.id === edge.target.portId);
    if (!sourceExists || !targetExists || sourcePort?.direction !== 'out' || targetPort?.direction !== 'in') {
      if (sourceExists) invalid.add(edge.source.nodeId);
      if (targetExists) invalid.add(edge.target.nodeId);
    }
    incoming.set(edge.target.nodeId, [...(incoming.get(edge.target.nodeId) ?? []), edge]);
  }
  for (const node of draft.nodes) {
    const module = modules.get(node.id), edges = incoming.get(node.id) ?? [];
    if (module?.ports.filter(port => port.direction === 'in').some(port =>
      edges.filter(edge => edge.target.portId === port.id).length !== 1)) invalid.add(node.id);
  }
  const visited = new Set<string>();
  for (const node of draft.nodes) {
    if (visited.has(node.id)) continue;
    const component = new Set<string>(), waiting = [node.id];
    while (waiting.length) {
      const id = waiting.pop()!;
      if (visited.has(id)) continue;
      visited.add(id); component.add(id); waiting.push(...adjacent.get(id)!);
    }
    if ([...component].some(id => invalid.has(id))) continue;
    const edges = draft.edges.filter(edge => component.has(edge.source.nodeId) && component.has(edge.target.nodeId));
    const indegree = new Map([...component].map(id => [id, 0]));
    for (const edge of edges) indegree.set(edge.target.nodeId, indegree.get(edge.target.nodeId)! + 1);
    const ready = [...component].filter(id => indegree.get(id) === 0), order: string[] = [];
    while (ready.length) {
      const id = ready.pop()!; order.push(id);
      for (const edge of edges.filter(edge => edge.source.nodeId === id)) {
        const next = indegree.get(edge.target.nodeId)! - 1;
        indegree.set(edge.target.nodeId, next);
        if (next === 0) ready.push(edge.target.nodeId);
      }
    }
    if (order.length !== component.size) continue;
    const ancestors = new Map<string, Set<string>>();
    for (const id of order) {
      const reached = new Set<string>();
      for (const edge of incoming.get(id) ?? []) {
        reached.add(edge.source.nodeId);
        for (const ancestor of ancestors.get(edge.source.nodeId) ?? []) reached.add(ancestor);
      }
      ancestors.set(id, reached);
      if (nodes.get(id)!.kind !== 'Add') continue;
      const module = modules.get(id)!;
      if (module.ports.length !== 3 || !module.ports.some(port => port.id === 'output' && port.direction === 'out')
        || !['left', 'right'].every(portId => module.ports.some(port => port.id === portId && port.direction === 'in'))) continue;
      const left = incoming.get(id)!.find(edge => edge.target.portId === 'left')!;
      const right = incoming.get(id)!.find(edge => edge.target.portId === 'right')!;
      if (left.source.nodeId === right.source.nodeId) continue;
      if (ancestors.get(right.source.nodeId)!.has(left.source.nodeId)) roles.set(left.id, 'residual');
      else if (ancestors.get(left.source.nodeId)!.has(right.source.nodeId)) roles.set(right.id, 'residual');
    }
  }
  return roles;
}
