import { applyVisualBatch, buildScene } from './core/index.ts';
import { api } from './api.ts';
import type { AuthoredDraft } from './authoring.ts';
import type { CanvasDocument } from './core/types.ts';
import { customModuleCatalog } from './customModules.ts';
import type { DraftCatalog } from './authoring.ts';
import { draftNodeBounds } from './draftNodeGeometry.ts';

export type DeletedSourceRegion = { canonicalId: string; draftId?: string; label: string; kind: string; descendants: number };

/** Detect stale compact/expanded geometry before treating it as user moves. */
export function invalidSourceDraftGeometry(draft: AuthoredDraft, values = draft.nodes): boolean {
  const source = draft.sourceProvenance;
  if (!source) return false;
  const nodes = values.filter(node => source.nodeRefs[node.id]), byId = new Map(nodes.map(node => [node.id, node]));
  const bounds = new Map(nodes.map(node => [node.id, { ...node.position, ...(node.visual ?? node.presentation ?? { width: 176, height: 100 }) }]));
  const ancestor = (id: string, child: string) => {
    const visited = new Set<string>(); let parent = byId.get(child)?.presentation?.parentId;
    while (parent && !visited.has(parent)) { if (parent === id) return true; visited.add(parent); parent = byId.get(parent)?.presentation?.parentId; }
    return false;
  };
  for (const node of nodes) {
    const box = bounds.get(node.id)!, parent = node.presentation?.parentId && bounds.get(node.presentation.parentId);
    if (parent && (box.x < parent.x - .5 || box.y < parent.y - .5 || box.x + box.width > parent.x + parent.width + .5 || box.y + box.height > parent.y + parent.height + .5)) return true;
    for (const other of nodes) if (node.id < other.id && !ancestor(node.id, other.id) && !ancestor(other.id, node.id)) {
      const peer = bounds.get(other.id)!;
      if (box.x < peer.x + peer.width - .5 && peer.x < box.x + box.width - .5 && box.y < peer.y + peer.height - .5 && peer.y < box.y + box.height - .5) return true;
    }
  }
  return false;
}

/** Source frontier growth must not cover independent user additions. Move only
 * affected connected additions, preserving their internal coordinates, ports
 * and all graph bindings. Fresh source cards keep their independent layout. */
export function relocateSourceDraftAdditions(before: AuthoredDraft, after: AuthoredDraft, catalog?: DraftCatalog | null): AuthoredDraft {
  if (!after.sourceProvenance) return after;
  const result = structuredClone(after), source = result.sourceProvenance!;
  const specs: DraftCatalog = { schemaVersion: 1, mode: 'authored-draft', unsupported: [], modules: [
    ...(catalog?.modules ?? []), ...source.modules, ...(result.customModules ?? []).map(customModuleCatalog)] };
  const old = new Map(before.nodes.map(node => [node.id, node])), nodes = new Map(result.nodes.map(node => [node.id, node]));
  const additions = new Map(result.nodes.filter(node => !source.nodeRefs[node.id]).map(node => [node.id, node]));
  const visited = new Set<string>();
  for (const first of additions.values()) {
    if (visited.has(first.id)) continue;
    const waiting = [first.id], component: typeof result.nodes = [];
    while (waiting.length) {
      const id = waiting.pop()!, node = additions.get(id);
      if (!node || visited.has(id) || node.presentation?.parentId !== first.presentation?.parentId) continue;
      visited.add(id); component.push(node);
      for (const edge of result.edges) if (edge.source.nodeId === id) waiting.push(edge.target.nodeId); else if (edge.target.nodeId === id) waiting.push(edge.source.nodeId);
    }
    const ids = new Set(component.map(node => node.id)), owner = first.presentation?.parentId;
    // Parented additions follow their moved owner; a deliberate local editing
    // arrangement remains intact. Owner expansion is independently controlled.
    if (owner && nodes.has(owner) && old.has(owner)) {
      const parent = nodes.get(owner)!, previous = old.get(owner)!;
      for (const node of component) { node.position.x += parent.position.x - previous.position.x; node.position.y += parent.position.y - previous.position.y; }
      continue;
    }
    const boundaries = result.edges.flatMap(edge => ids.has(edge.source.nodeId) && source.nodeRefs[edge.target.nodeId] ? [edge.target.nodeId] : []);
    const anchor = boundaries.map(id => ({ before: old.get(id), after: nodes.get(id) })).find(pair => pair.before && pair.after);
    if (anchor?.before && anchor.after) {
      const dx = anchor.after.position.x - anchor.before.position.x;
      let dy = anchor.after.position.y - anchor.before.position.y;
      let root = anchor.after;
      while (root.presentation?.parentId && nodes.has(root.presentation.parentId)) root = nodes.get(root.presentation.parentId)!;
      const previousRoot = old.get(root.id), previousMembers = component.map(node => old.get(node.id) ?? node);
      const componentTop = Math.min(...previousMembers.map(node => node.position.y));
      if (previousRoot) {
        const previousBounds = draftNodeBounds(previousRoot, specs), bounds = draftNodeBounds(root, specs);
        // A component outside a source model follows the model's exterior.
        // A stale leaf/output inside a grown model must not turn its internal
        // correction into another displacement of these external additions.
        if (componentTop >= previousBounds.y + previousBounds.height - .5) dy = bounds.y + bounds.height - previousBounds.y - previousBounds.height;
      }
      for (const node of component) { node.position.x += dx; node.position.y += dy; }
    }
    const obstacles = result.nodes.filter(node => !ids.has(node.id));
    for (let step = 0; step <= obstacles.length; step++) {
      const bounds = component.map(node => draftNodeBounds(node, specs));
      const collisions = obstacles.map(node => draftNodeBounds(node, specs)).filter(box => bounds.some(part =>
        part.x < box.x + box.width + 24 && box.x < part.x + part.width + 24 && part.y < box.y + box.height + 24 && box.y < part.y + part.height + 24));
      if (!collisions.length) break;
      const dy = Math.max(...collisions.map(box => box.y + box.height + 24)) - Math.min(...bounds.map(box => box.y));
      if (dy <= 0) break;
      for (const node of component) node.position.y += dy;
    }
  }
  if (result.sourceCache) {
    const live = new Map(result.nodes.map(node => [node.id, node]));
    result.sourceCache.nodes = result.sourceCache.nodes.map(node => structuredClone(live.get(node.id) ?? node));
  }
  return result;
}

function sourceRegionState(draft: AuthoredDraft) {
  const source = draft.sourceProvenance;
  if (!source) throw new Error('此草稿没有源码层级。');
  const facts = new Map(source.architecture.nodes.map(node => [node.id, node]));
  const visible = new Set(draft.nodes.map(node => node.id));
  const removedIds = new Set([...draft.sourceCache?.removedNodeIds ?? [],
    ...source.originalGraph.nodes.filter(node => !visible.has(node.id)).map(node => node.id)]);
  const removedCanonical = new Set([...removedIds].flatMap(id => source.nodeRefs[id] ? [source.nodeRefs[id].nodeId] : []));
  const deleted = (id: string) => {
    let cursor: string | undefined = id;
    while (cursor) { if (removedCanonical.has(cursor)) return true; cursor = facts.get(cursor)?.parentId; }
    return false;
  };
  const subtree = (id: string) => {
    const ids = new Set<string>(), waiting = [id];
    while (waiting.length) { const next = waiting.pop()!; if (ids.has(next)) continue; ids.add(next); waiting.push(...facts.get(next)?.children ?? []); }
    return ids;
  };
  return { source, facts, removedIds, removedCanonical, deleted, subtree };
}

/** Source-backed recovery remains available after undo history has expired.
 * Entries name whole deleted scopes; descendants are restored with their owner. */
export function sourceDeletedRegions(draft: AuthoredDraft): DeletedSourceRegion[] {
  if (!draft.sourceProvenance) return [];
  const state = sourceRegionState(draft);
  return state.source.architecture.nodes.filter(node => state.removedCanonical.has(node.id) &&
    (!node.parentId || !state.deleted(node.parentId))).map(node => ({ canonicalId: node.id,
      draftId: Object.entries(state.source.nodeRefs).find(([, ref]) => ref.nodeId === node.id)?.[0],
      label: state.source.canvas.displayAliases[node.id] ?? node.label, kind: node.kind, descendants: state.subtree(node.id).size - 1 }));
}

/** Restore exact retained source objects, never substitute a palette default.
 * Rebase independently recreates never-materialized descendants afterwards.
 * A selected descendant of a deleted owner restores that intact owner scope. */
export function prepareSourceRegionRestore(draft: AuthoredDraft, canonicalId: string, catalog?: DraftCatalog | null): AuthoredDraft {
  const state = sourceRegionState(draft);
  if (!state.facts.has(canonicalId)) throw new Error('未知源码区域；当前草稿保持原样。');
  let root = canonicalId, cursor = state.facts.get(canonicalId)?.parentId;
  while (cursor) { if (state.removedCanonical.has(cursor)) root = cursor; cursor = state.facts.get(cursor)?.parentId; }
  const canonicalIds = state.subtree(root), next = structuredClone(draft), source = next.sourceProvenance!;
  const restoredIds = new Set(Object.entries(source.nodeRefs).filter(([, ref]) => canonicalIds.has(ref.nodeId)).map(([id]) => id));
  // Original facts provide a baseline; retained edited snapshots take priority.
  const originals = new Map([...source.viewGraph?.nodes ?? [], ...source.originalGraph.nodes,
    ...next.sourceCache?.nodes ?? []].map(node => [node.id, node]));
  // User-created children share their source owner's scope even though they
  // have no canonical identity of their own.
  let inherited = true;
  while (inherited) {
    inherited = false;
    for (const node of originals.values()) if (node.presentation?.parentId && restoredIds.has(node.presentation.parentId) && !restoredIds.has(node.id)) {
      restoredIds.add(node.id); inherited = true;
    }
  }
  const live = new Set(next.nodes.map(node => node.id));
  for (const id of restoredIds) { const node = originals.get(id); if (node && !live.has(id)) { next.nodes.push(structuredClone(node)); live.add(id); } }
  const candidateEdges = new Map([...source.viewGraph?.edges ?? [], ...source.originalGraph.edges,
    ...next.sourceCache?.edges ?? []].map(edge => [edge.id, edge]));
  const incident = [...candidateEdges.values()].filter(edge => restoredIds.has(edge.source.nodeId) || restoredIds.has(edge.target.nodeId));
  const removedEdges = new Set(next.sourceCache?.removedCanonicalEdgeIds ?? []);
  const specs = new Map([...(catalog?.modules ?? []), ...source.modules,
    ...(next.customModules ?? []).map(customModuleCatalog)].map(module => [module.kind, module]));
  const nodes = new Map(next.nodes.map(node => [node.id, node]));
  const validPort = (end: import('./authoring.ts').DraftEndpoint, direction: 'in' | 'out') => {
    const node = nodes.get(end.nodeId);
    return !!node && !!specs.get(node.kind)?.ports.some(port => port.id === end.portId && port.direction === direction);
  };
  for (const edge of incident) if (!(source.edgeRefs[edge.id] ?? []).some(id => removedEdges.has(id)) && validPort(edge.source, 'out') && validPort(edge.target, 'in') &&
      !next.edges.some(item => item.id === edge.id || item.target.nodeId === edge.target.nodeId && item.target.portId === edge.target.portId)) next.edges.push(structuredClone(edge));
  if (next.sourceCache) {
    next.sourceCache.removedNodeIds = next.sourceCache.removedNodeIds.filter(id => !restoredIds.has(id));
    // Node deletion suppresses its incident source edges by node tombstone.
    // Independent edge tombstones, including legacy ambiguous records, remain
    // deleted; recovery must not undo an unrelated deliberate disconnection.
  }
  return next;
}

/** Source expansion changes presentation frontier while preserving independent edits. */
export function sourceFrontierDocument(draft: AuthoredDraft, nodeId: string, expanded: boolean): CanvasDocument {
  const provenance = draft.sourceProvenance;
  if (!provenance) throw new Error('此草稿没有源码层级。');
  let document = structuredClone(provenance.canvas);
  const invalidGeometry = invalidSourceDraftGeometry(draft) || invalidSourceDraftGeometry(draft, provenance.originalGraph.nodes);
  if (invalidGeometry) {
    // Older frontiers retained compact world coordinates for newly expanded
    // owners. Their inconsistent positions are not intentional editing deltas.
    const roots = provenance.architecture.nodes.filter(node => !node.parentId);
    document.layout = Object.fromEntries(roots.map(root => {
      const visible = draft.nodes.find(node => provenance.nodeRefs[node.id]?.nodeId === root.id);
      const position = visible?.position ?? provenance.canvas.layout[root.id] ?? { x: 60, y: 60 };
      return [root.id, { x: position.x, y: position.y }];
    }));
    document.layoutByFrontier = {};
  }
  // The canvas is an independent layout baseline. Rebase carries draft moves
  // relative to it exactly once; projecting them into this canvas as well
  // double-applies the same movement when a region grows or shrinks.
  const portOperations: import('./core/types.ts').VisualOperation[] = [];
  for (const node of draft.nodes) {
    const ref = provenance.nodeRefs[node.id]; if (!ref) continue;
    for (const [portId, layout] of Object.entries(node.portLayouts ?? {})) for (const binding of ref.portBindings[portId] ?? []) {
      const roles = new Set(document.architecture.edges.filter(edge =>
        [edge.source, edge.target].some(end => end.nodeId === binding.nodeId && end.portId === binding.portId)).map(edge => edge.role));
      for (const role of roles) portOperations.push({ type: 'portLayout', ownerId: ref.sceneNodeId, nodeId: binding.nodeId, portId: binding.portId, role, layout });
    }
  }
  if (portOperations.length) document = applyVisualBatch(document, portOperations);
  const canonical = provenance.nodeRefs[nodeId]?.nodeId;
  if (!canonical) throw new Error('此模块没有可展开的源码层级。');
  document = applyVisualBatch(document, [{ type: 'expand', id: canonical, expanded }]);
  return document;
}
export async function reprojectSourceDraft(draft: AuthoredDraft, nodeId: string, expanded: boolean, catalog?: DraftCatalog | null): Promise<AuthoredDraft> {
  const { sourceFrontierProjection } = await import('./sourceEditingClient.ts');
  const { document, scene } = await sourceFrontierProjection(draft, nodeId, expanded);
  return relocateSourceDraftAdditions(draft, (await api.sourceDraftFrontier(draft, document, scene)).draft, catalog);
}

/** Reveal one scope and its immediate contents without expanding all models. */
export function sourceRegionDocument(draft: AuthoredDraft, canonicalId: string): CanvasDocument {
  const source = draft.sourceProvenance;
  if (!source) throw new Error('此草稿没有源码层级。');
  const facts = new Map(source.architecture.nodes.map(node => [node.id, node]));
  if (!facts.has(canonicalId)) throw new Error('未知源码区域；当前草稿保持原样。');
  const path: string[] = [];
  let cursor: string | undefined = canonicalId;
  while (cursor) { if (facts.get(cursor)?.children.length) path.unshift(cursor); cursor = facts.get(cursor)?.parentId; }
  // Synchronize live placement and ports using the existing frontier contract.
  const first = Object.entries(source.nodeRefs).find(([, ref]) => ref.nodeId === path[0]);
  const document = first ? sourceFrontierDocument(draft, first[0], true) : structuredClone(source.canvas);
  return applyVisualBatch(document, path.filter(id => !document.expandedIds.includes(id)).map(id => ({ type: 'expand' as const, id, expanded: true })));
}

export async function revealSourceRegion(draft: AuthoredDraft, canonicalId: string, catalog?: DraftCatalog | null): Promise<AuthoredDraft> {
  const { sourceRegionProjection } = await import('./sourceEditingClient.ts');
  const { document, scene } = await sourceRegionProjection(draft, canonicalId);
  return relocateSourceDraftAdditions(draft, (await api.sourceDraftFrontier(draft, document, scene)).draft, catalog);
}

export async function restoreSourceRegion(draft: AuthoredDraft, canonicalId: string, catalog?: DraftCatalog | null): Promise<AuthoredDraft> {
  return revealSourceRegion(prepareSourceRegionRestore(draft, canonicalId, catalog), canonicalId, catalog);
}

/** Upgrade pre-scope editor snapshots once; callers decide when an untouched
 * legacy workspace qualifies, so a later deliberate collapse stays collapsed. */
export async function expandSourceDraftScopes(draft: AuthoredDraft, catalog?: DraftCatalog | null): Promise<AuthoredDraft> {
  if (!draft.sourceProvenance) return draft;
  const { sourceEditingProjection, sourceRegionProjection } = await import('./sourceEditingClient.ts');
  const invalid = invalidSourceDraftGeometry(draft) || invalidSourceDraftGeometry(draft, draft.sourceProvenance.originalGraph.nodes);
  const root = draft.sourceProvenance.architecture.nodes.find(node => !node.parentId && node.children.length);
  const { document, scene } = invalid && root ? await sourceRegionProjection(draft, root.id) : await sourceEditingProjection(draft.sourceProvenance.canvas);
  return relocateSourceDraftAdditions(draft, (await api.sourceDraftFrontier(draft, document, scene)).draft, catalog);
}
