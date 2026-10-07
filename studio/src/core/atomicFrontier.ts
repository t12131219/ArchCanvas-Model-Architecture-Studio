import type { Architecture, ArchitectureEdge } from './types.ts';

/** Source relations at every depth are kept intact. This index establishes
 * which container bindings have a more detailed, source-backed counterpart;
 * it does not invent an operator, port, tensor or graph rewrite. */
export function indexAtomicRelations(architecture: Architecture) {
  const byId = new Map(architecture.nodes.map(node => [node.id, node]));
  const ancestors = new Map<string, Set<string>>();
  for (const node of architecture.nodes) {
    const chain = new Set<string>(); let parent = node.parentId;
    while (parent && !chain.has(parent)) { chain.add(parent); parent = byId.get(parent)?.parentId; }
    ancestors.set(node.id, chain);
  }
  const targetFamilies = new Map<string, ArchitectureEdge[]>(), sourceFamilies = new Map<string, ArchitectureEdge[]>();
  for (const edge of architecture.edges) {
    const targetKey = JSON.stringify([edge.source.nodeId, edge.source.portId, edge.tensorId, edge.role]);
    const sourceKey = JSON.stringify([edge.target.nodeId, edge.target.portId, edge.tensorId, edge.role]);
    const targets = targetFamilies.get(targetKey) ?? []; targets.push(edge); targetFamilies.set(targetKey, targets);
    const sources = sourceFamilies.get(sourceKey) ?? []; sources.push(edge); sourceFamilies.set(sourceKey, sources);
  }
  const refinements = new Map<string, { source: string[]; target: string[] }>();
  for (const edge of architecture.edges) {
    const targetKey = JSON.stringify([edge.source.nodeId, edge.source.portId, edge.tensorId, edge.role]);
    const sourceKey = JSON.stringify([edge.target.nodeId, edge.target.portId, edge.tensorId, edge.role]);
    const target = (targetFamilies.get(targetKey) ?? []).filter(candidate => ancestors.get(candidate.target.nodeId)?.has(edge.target.nodeId)).map(candidate => candidate.target.nodeId);
    const source = (sourceFamilies.get(sourceKey) ?? []).filter(candidate => ancestors.get(candidate.source.nodeId)?.has(edge.source.nodeId)).map(candidate => candidate.source.nodeId);
    if (source.length || target.length) refinements.set(edge.id, { source, target });
  }
  /** Collapse atomics onto their nearest visible ancestor. A coarse binding
   * disappears only after its source-backed refinement becomes a distinct
   * visible endpoint. Collapsed coverage and unresolved/opaque boundaries
   * retain the original edge; equal tensor names alone never prove an alias. */
  const project = (visible: ReadonlySet<string>, expanded: ReadonlySet<string>) => {
    const representative = (id: string) => {
      let node = byId.get(id)!;
      while (!visible.has(node.id) && node.parentId) node = byId.get(node.parentId)!;
      return node.id;
    };
    const hidden: string[] = [];
    const edges = architecture.edges.map(edge => ({ e: edge, s: representative(edge.source.nodeId), t: representative(edge.target.nodeId) })).filter(({ e, s, t }) => {
      const refinement = refinements.get(e.id);
      const duplicateTarget = expanded.has(t) && byId.get(t)?.evidence !== 'opaque' &&
        refinement?.target.some(id => representative(id) !== t);
      const duplicateSource = expanded.has(s) && byId.get(s)?.evidence !== 'opaque' &&
        refinement?.source.some(id => representative(id) !== s);
      const internal = s === t && (e.source.nodeId !== s || e.target.nodeId !== t);
      const adapter = e.target.nodeId === t && byId.get(t)!.children.length > 0 && ancestors.get(e.source.nodeId)?.has(t) ||
        e.source.nodeId === s && byId.get(s)!.children.length > 0 && ancestors.get(e.target.nodeId)?.has(s);
      if (internal || adapter || duplicateTarget || duplicateSource) { hidden.push(e.id); return false; }
      return true;
    });
    return { edges, hidden };
  };
  return { refinements, project };
}
