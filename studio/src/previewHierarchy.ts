import { moduleSymbol, type ModuleSymbol } from './moduleSymbols.ts';
import type { ArchitectureNode } from './core/types.ts';
import type { PreviewSnapshot } from './PreviewStudio';
import type { PreviewVisualGraph } from './previewInterop.ts';
import { previewDetailGraph } from './previewInterop.ts';
import { previewPresentation } from './previewPresentation.ts';

export type HierarchyNode = Pick<ArchitectureNode, 'id' | 'label' | 'category' | 'parentId' | 'children' | 'repeat'> & { fill?: string; symbol?: ModuleSymbol; symbolDescription?: string };
export type PreviewHierarchy = {
  nodes: HierarchyNode[];
  expandedIds: string[];
  displayAliases: Record<string, string>;
  pinnedObjects: string[];
  mandatoryIds: string[];
};

/** A small, read-only summary for the Studio semantic view panel.  The child
 * preview remains the authority for expansion and routing; this function only
 * counts the committed snapshot that the iframe published. */
export type PreviewFrontier = {
  preset: 'overview' | 'detail' | 'custom';
  label: string;
  depth: number;
  visibleNodeCount: number;
  visibleEdgeCount: number;
  expandableCount: number;
  expandedIds: string[];
};

export function previewFrontier(snapshot: PreviewSnapshot | null, hierarchy: PreviewHierarchy | null): PreviewFrontier | null {
  if (!snapshot?.graph || !hierarchy) return null;
  const graph = snapshot.graph as unknown as { nodes?: Array<{ id: string; junction?: boolean; expanded?: boolean }>; edges?: unknown[]; frontierPreset?: string };
  const byId = new Map(hierarchy.nodes.map(node => [node.id, node]));
  const depth = (id: string) => {
    let value = 0, current = byId.get(id), seen = new Set<string>();
    while (current?.parentId && !seen.has(current.id)) { seen.add(current.id); value++; current = byId.get(current.parentId); }
    return value;
  };
  const visible = (graph.nodes ?? []).filter(node => !node.junction);
  const expanded = hierarchy.expandedIds.filter(id => byId.get(id)?.children.length);
  const expandableCount = visible.filter(node => {
    const item = byId.get(node.id); return !!item?.children.length && !hierarchy.mandatoryIds.includes(node.id) && !expanded.includes(node.id);
  }).length;
  const maxDepth = visible.reduce((value, node) => Math.max(value, depth(node.id)), 0);
  const snapshotPreset = (snapshot as { frontierPreset?: unknown }).frontierPreset;
  const presetValue = typeof snapshotPreset === 'string' ? snapshotPreset : graph.frontierPreset;
  const preset = presetValue === 'overview' || presetValue === 'detail' ? presetValue : 'custom';
  const label = preset === 'overview' ? '架构概览（F0）' : preset === 'detail' ? '架构详图（F1）' : (expanded.length ? '当前递归前沿' : '架构概览（F0）');
  return { preset, label, depth: maxDepth, visibleNodeCount: visible.length,
    visibleEdgeCount: Array.isArray(graph.edges) ? graph.edges.length : 0, expandableCount, expandedIds: expanded };
}

/** Navigation follows the renderer's actual identities, including inspection
 * wrappers with no unique formal counterpart. It never creates source facts. */
export function previewHierarchy(snapshot: PreviewSnapshot | null): PreviewHierarchy | null {
  if (!snapshot?.graph) return null;
  const graph = snapshot.graph as unknown as PreviewVisualGraph & {
    recursive?: { authority?: { detail?: PreviewVisualGraph; mandatory?: string[] }; state?: { open?: string[]; folded?: string[] } };
  };
  if (!Array.isArray(graph.nodes)) return null;
  const detail = previewDetailGraph(graph);
  const visible = new Map(graph.nodes.map(node => [node.id, node]));
  const presentation = previewPresentation(snapshot.graph);
  const all = new Map(detail.nodes.map(node => [node.id, node]));
  const nodes: HierarchyNode[] = detail.nodes.filter(node => !node.junction).map(node => {
    let parent = node.parent;
    // Junctions are routing implementation objects, not tree rows. Retain a
    // visible descendant's nearest real container if a catalog uses one.
    const visited = new Set([node.id]);
    while (parent && all.get(parent)?.junction && !visited.has(parent)) { visited.add(parent); parent = all.get(parent)?.parent; }
    const kind = node.semantic?.kind ?? node.kind ?? 'opaque';
    const marker = moduleSymbol(node.semantic ?? node);
    return { id: node.id, label: node.label ?? node.id, fill: presentation?.nodes?.[node.id]?.fill ?? visible.get(node.id)?.fill ?? node.fill, symbol: marker.symbol, symbolDescription: marker.description, category: kind === 'group' || kind === 'composite' ? 'container' : kind === 'normalization' ? 'norm' : kind,
      ...(parent && all.has(parent) && !all.get(parent)?.junction && !visited.has(parent) ? { parentId: parent } : {}), children: [] };
  });
  const byId = new Map(nodes.map(node => [node.id, node]));
  for (const node of nodes) if (node.parentId) byId.get(node.parentId)?.children.push(node.id);
  const mandatory = new Set(graph.recursive?.authority?.mandatory ?? []), folded = new Set(graph.recursive?.state?.folded ?? []);
  const expanded = new Set([...(graph.recursive?.state?.open ?? []), ...mandatory].filter(id => mandatory.has(id) || !folded.has(id)));
  // Visible flags describe the committed frontier. Latent descendant choices
  // stay in recursive state when their parent is collapsed.
  for (const node of graph.nodes) if (typeof node.expanded === 'boolean') {
    if (node.expanded) expanded.add(node.id); else if (!mandatory.has(node.id)) expanded.delete(node.id);
  }
  const displayAliases: Record<string, string> = {}, pinnedObjects: string[] = [];
  for (const [id, presentation] of Object.entries(previewPresentation(snapshot.graph)?.nodes ?? {})) {
    if (!byId.has(id)) continue;
    if (presentation.alias !== undefined) displayAliases[id] = presentation.alias;
    if (presentation.pinned) pinnedObjects.push(id);
  }
  return { nodes, expandedIds: [...expanded].filter(id => byId.get(id)?.children.length), displayAliases, pinnedObjects, mandatoryIds: [...mandatory] };
}

/** A search can expose rows beneath a folded parent. Reveal that path in the
 * same preview transaction instead of changing an invisible expansion flag. */
export function previewHierarchyExpansion(hierarchy: PreviewHierarchy, id: string, expanded: boolean) {
  const byId = new Map(hierarchy.nodes.map(node => [node.id, node])), target = byId.get(id);
  if (!target?.children.length || hierarchy.mandatoryIds.includes(id)) return [];
  const ids = [id];
  if (expanded) {
    let parent = target.parentId;
    const seen = new Set(ids);
    while (parent && !seen.has(parent)) { seen.add(parent); ids.unshift(parent); parent = byId.get(parent)?.parentId; }
  }
  const open = new Set(hierarchy.expandedIds);
  return ids.filter(id => !hierarchy.mandatoryIds.includes(id) && open.has(id) !== expanded)
    .map(id => ({ type: 'expand' as const, id, expanded }));
}
