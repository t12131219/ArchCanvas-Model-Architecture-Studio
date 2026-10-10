import { createOrthogonalRouter } from './core/orthogonalRouter.ts';
import type { SceneNode } from './core/types.ts';
import type { Architecture, CanvasDocument } from './core/types.ts';
import type { PortLayout } from './core/types.ts';
import { portRoutePath, selectRoutingPorts } from './core/portRouting.ts';
import { visualPortSide } from './core/nodeVisualOutline.ts';
import { orderedLayers } from './core/layerOrdering.ts';
import { refineDraftRoutes } from './draftRouting.ts';
import { draftModuleSize, draftNodeBounds, draftNodeSize, draftPortPoint } from './draftNodeGeometry.ts';
import { customModuleCatalog, readCustomModuleDefinition } from './customModules.ts';
import type { CustomModuleDefinition } from './customModules.ts';
export { DRAFT_WIDTH, DRAFT_HEIGHT, DRAFT_PORT_PITCH, draftModuleSize, draftNodeBounds, draftNodeSize, draftPortSpacing } from './draftNodeGeometry.ts';

export type DraftValue = number | boolean | string | number[];
export type DraftPort = { id: string; name: string; direction: 'in' | 'out'; type: 'tensor' };
export type DraftParameter = { name: string; type: 'integer' | 'number' | 'boolean' | 'integer-array' | 'choice'; default: DraftValue; min?: number; max?: number; length?: number; minLength?: number; maxLength?: number; options?: string[] };
export type DraftModule = { kind: string; label: string; category: string; description: string; defaults: Record<string, DraftValue>; parameters: DraftParameter[]; ports: DraftPort[] };
export type DraftCatalog = { schemaVersion: 1; mode: 'authored-draft'; modules: DraftModule[]; unsupported: unknown[] };
export type DraftPresentation = { width: number; height: number; fill: string; stroke: string; group: boolean; parentId?: string; ports: Record<string, { x: number; y: number }> };
export type DraftVisual = { width: number; height: number; fill: string; stroke: string };
export type DraftNode = { id: string; kind: string; label: string; parameters: Record<string, DraftValue>; position: { x: number; y: number }; presentation?: DraftPresentation; visual?: DraftVisual; portLayouts?: Record<string, PortLayout | null> };
export type DraftEndpoint = { nodeId: string; portId: string };
export type DraftEdge = { id: string; source: DraftEndpoint; target: DraftEndpoint };
export type SourceDraftRef = { nodeId: string; sceneNodeId: string; kind: string; category: string; evidence: string; portBindings: Record<string, { nodeId: string; portId: string }[]>; originalParameters: Record<string, DraftValue>; group: boolean; instanceId?: string; repeat?: { count: number; sharing: 'independent' | 'shared' } };
export type DraftSourceProvenance = { schemaVersion: 1; digest: string; documentId: string; visualRevision: number; sourceDigest: string; irDigest: string; architecture: Architecture; canvas: CanvasDocument; viewCanvas?: CanvasDocument; viewGraph?: { nodes: DraftNode[]; edges: DraftEdge[] }; modules: DraftModule[]; nodeRefs: Record<string, SourceDraftRef>; edgeRefs: Record<string, string[]>; originalGraph: { nodes: DraftNode[]; edges: DraftEdge[] } };
export type SourceDraftCache = { nodes: DraftNode[]; edges: DraftEdge[]; removedNodeIds: string[]; removedCanonicalEdgeIds: string[] };
export type AuthoredDraft = { schemaVersion: 1; mode: 'authored-draft'; id: string; title: string; revision: number; nodes: DraftNode[]; edges: DraftEdge[]; customModules?: CustomModuleDefinition[]; sourceProvenance?: DraftSourceProvenance; sourceCache?: SourceDraftCache };
export type DraftHistory = { draft: AuthoredDraft; past: AuthoredDraft[]; future: AuthoredDraft[] };
export type DraftFlow = 'horizontal' | 'vertical';
const MAX_DRAFT_NODES = 128;
const MAX_DRAFT_EDGES = 384;

/** Source frontier modules are retained in the draft, never advertised as presets. */
export function sourceDraftCatalog(draft: AuthoredDraft, catalog: DraftCatalog | null): DraftCatalog | null {
  return catalog ? { ...catalog, modules: [...catalog.modules, ...(draft.sourceProvenance?.modules ?? []), ...(draft.customModules ?? []).map(customModuleCatalog)] } : null;
}
export function draftSourceKind(draft: AuthoredDraft, node: DraftNode): string {
  return draft.sourceProvenance?.nodeRefs[node.id]?.kind ?? draft.customModules?.find(module => module.kind === node.kind)?.entry ?? node.kind;
}
export function implicitDraftRootIds(draft: AuthoredDraft): Set<string> {
  const architecture = draft.sourceProvenance?.architecture;
  if (!architecture) return new Set();
  return new Set(draft.nodes.filter(node => {
    const canonical = architecture.nodes.find(item => item.id === draft.sourceProvenance?.nodeRefs[node.id]?.nodeId);
    return node.presentation?.group && canonical && !canonical.parentId && canonical.children.length > 0;
  }).map(node => node.id));
}
/** Moving an expanded source group moves its descendants in the same undo step. */
export function draftMoveIds(draft: AuthoredDraft, selection: readonly string[]): string[] {
  const selected = new Set(selection), waiting = [...selection];
  while (waiting.length) {
    const parent = waiting.pop()!;
    for (const node of draft.nodes) if (node.presentation?.parentId === parent && !selected.has(node.id)) { selected.add(node.id); waiting.push(node.id); }
  }
  return draft.nodes.filter(node => selected.has(node.id)).map(node => node.id);
}
export function moveDraftNodes(draft: AuthoredDraft, selection: readonly string[], dx: number, dy: number) {
  const ids = new Set(draftMoveIds(draft, selection));
  for (const node of draft.nodes) if (ids.has(node.id)) { node.position.x += dx; node.position.y += dy; }
  if (draft.sourceCache) {
    const cached = { ...draft, nodes: draft.sourceCache.nodes };
    const hiddenIds = new Set(draftMoveIds(cached, selection));
    for (const node of draft.sourceCache.nodes) if (hiddenIds.has(node.id)) { node.position.x += dx; node.position.y += dy; }
  }
}
export function selectDraftNode(current: readonly string[], id: string, additive: boolean): string[] {
  return additive ? current.includes(id) ? current.filter(item => item !== id) : [...current, id] : current.includes(id) ? [...current] : [id];
}

/** Project ports along the connected graph's main axis without moving cards. */
export function draftFlow(draft: AuthoredDraft): DraftFlow {
  const nodes = new Map(draft.nodes.map(node => [node.id, node]));
  let horizontal = 0, vertical = 0;
  for (const edge of draft.edges) {
    const source = nodes.get(edge.source.nodeId), target = nodes.get(edge.target.nodeId);
    if (!source || !target) continue;
    horizontal += Math.abs(target.position.x - source.position.x);
    vertical += Math.abs(target.position.y - source.position.y);
  }
  return vertical > horizontal ? 'vertical' : 'horizontal';
}

/** Adding another independent network must not turn existing port projections. */
export function draftNodeFlows(draft: AuthoredDraft): Record<string, DraftFlow> {
  const nodes = new Map(draft.nodes.map(node => [node.id, node]));
  const adjacent = new Map(draft.nodes.map(node => [node.id, new Set<string>()]));
  for (const edge of draft.edges) {
    if (!nodes.has(edge.source.nodeId) || !nodes.has(edge.target.nodeId)) continue;
    adjacent.get(edge.source.nodeId)!.add(edge.target.nodeId);
    adjacent.get(edge.target.nodeId)!.add(edge.source.nodeId);
  }
  const flows: Record<string, DraftFlow> = {}, visited = new Set<string>();
  for (const node of draft.nodes) {
    if (visited.has(node.id)) continue;
    const component = new Set<string>(), waiting = [node.id];
    while (waiting.length) {
      const id = waiting.pop()!;
      if (visited.has(id)) continue;
      visited.add(id); component.add(id); waiting.push(...adjacent.get(id)!);
    }
    const flow = draftFlow({ ...draft, nodes: draft.nodes.filter(item => component.has(item.id)),
      edges: draft.edges.filter(edge => component.has(edge.source.nodeId) && component.has(edge.target.nodeId)) });
    for (const id of component) flows[id] = flow;
  }
  return flows;
}

export function parseDraftCache(value: unknown): { draft: AuthoredDraft; storageRevision: number; savedRevision: number } | null {
  if (!value || typeof value !== 'object') return null;
  const cache = value as Record<string, unknown>, draft = cache.draft as AuthoredDraft | undefined;
  const identity = (id: unknown) => typeof id === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(id);
  const text = (label: unknown) => typeof label === 'string' && label.length > 0 && label.length <= 120 && !/[\x00-\x1f]/.test(label);
  const safeNumber = (n: unknown) => typeof n === 'number' && Number.isFinite(n) && Math.abs(n) <= 1_000_000;
  const parameter = (p: unknown) => typeof p === 'boolean' || typeof p === 'string' || (typeof p === 'number' && Number.isFinite(p)) || (Array.isArray(p) && p.every(n => typeof n === 'number' && Number.isFinite(n)));
  if (!draft || draft.mode !== 'authored-draft' || draft.schemaVersion !== 1 || !identity(draft.id) || !draft.id.startsWith('draft-') || !text(draft.title) || !Number.isSafeInteger(draft.revision) || draft.revision < 0 || !Array.isArray(draft.nodes) || draft.nodes.length > (draft.sourceProvenance ? 1200 : MAX_DRAFT_NODES) || !Array.isArray(draft.edges) || draft.edges.length > (draft.sourceProvenance ? 3600 : MAX_DRAFT_EDGES)) return null;
  const ids = new Set<string>(), edgeIds = new Set<string>();
  if (draft.customModules) {
    if (!Array.isArray(draft.customModules) || draft.customModules.length > 32) return null;
    try { for (const definition of draft.customModules) readCustomModuleDefinition(definition); } catch { return null; }
    if (new Set(draft.customModules.map(module => module.kind)).size !== draft.customModules.length) return null;
  }
  for (const node of draft.nodes) {
    if (!node || !identity(node.id) || ids.has(node.id) || !text(node.kind) || !text(node.label) || !node.position || !safeNumber(node.position.x) || !safeNumber(node.position.y) || !node.parameters || Array.isArray(node.parameters) || typeof node.parameters !== 'object' || !Object.values(node.parameters).every(parameter)) return null;
    if (node.visual && (!['width', 'height'].every(key => typeof node.visual![key as 'width' | 'height'] === 'number' && Number.isFinite(node.visual![key as 'width' | 'height']) && node.visual![key as 'width' | 'height'] >= 10 && node.visual![key as 'width' | 'height'] <= 1000000) || ![node.visual.fill, node.visual.stroke].every(color => typeof color === 'string' && /^#(?:[0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})$/i.test(color)))) return null;
    if (node.portLayouts && (typeof node.portLayouts !== 'object' || Array.isArray(node.portLayouts) || Object.entries(node.portLayouts).some(([id, layout]) => !identity(id) || layout !== null && (!layout || !['top', 'right', 'bottom', 'left'].includes(layout.side) || typeof layout.offset !== 'number' || !Number.isFinite(layout.offset) || layout.offset < 0 || layout.offset > 1)))) return null;
    ids.add(node.id);
  }
  for (const edge of draft.edges) {
    if (!edge || !identity(edge.id) || edgeIds.has(edge.id) || ![edge.source, edge.target].every(end => end && ids.has(end.nodeId) && identity(end.portId))) return null;
    edgeIds.add(edge.id);
  }
  if (!Number.isSafeInteger(cache.storageRevision) || (cache.storageRevision as number) < 0 || !Number.isSafeInteger(cache.savedRevision) || (cache.savedRevision as number) < -1 || (cache.savedRevision as number) > draft.revision) return null;
  return { draft: structuredClone(draft), storageRevision: cache.storageRevision as number, savedRevision: cache.savedRevision as number };
}

export function nextDraftPosition(draft: AuthoredDraft, preferred: { x: number; y: number }, module: DraftModule, catalog: DraftCatalog) {
  const size = draftModuleSize(module);
  let position = { x: Math.round(preferred.x), y: Math.round(preferred.y) };
  for (let step = 0; step <= draft.nodes.length; step++) {
    const overlaps = draft.nodes.map(node => draftNodeBounds(node, catalog)).filter(box =>
      box.x < position.x + size.width + 20 && box.x + box.width + 20 > position.x &&
      box.y < position.y + size.height + 20 && box.y + box.height + 20 > position.y);
    if (!overlaps.length) return position;
    position = { x: position.x, y: Math.max(...overlaps.map(box => box.y + box.height + 28)) };
  }
  return position;
}

export function blankDraft(id: string): AuthoredDraft {
  return { schemaVersion: 1, mode: 'authored-draft', id, title: '我的模型', revision: 0, nodes: [], edges: [] };
}
export function draftHistory(draft: AuthoredDraft): DraftHistory { return { draft, past: [], future: [] }; }
export function changeDraft(history: DraftHistory, update: (draft: AuthoredDraft) => void): DraftHistory {
  const next = structuredClone(history.draft); update(next);
  if (JSON.stringify(next) === JSON.stringify(history.draft)) return history;
  next.revision = history.draft.revision + 1;
  return { draft: next, past: [...history.past.slice(-79), history.draft], future: [] };
}
export function travelDraft(history: DraftHistory, action: 'undo' | 'redo'): DraftHistory {
  const stack = action === 'undo' ? history.past : history.future, target = stack.at(-1);
  if (!target) return history;
  const draft = { ...structuredClone(target), revision: history.draft.revision + 1 };
  return action === 'undo' ? { draft, past: stack.slice(0, -1), future: [...history.future, history.draft] }
    : { draft, past: [...history.past, history.draft], future: stack.slice(0, -1) };
}
export function addDraftNode(draft: AuthoredDraft, module: DraftModule, id: string, position: { x: number; y: number }) {
  if (draft.nodes.length >= (draft.sourceProvenance ? 1200 : MAX_DRAFT_NODES)) throw new Error(`草稿达到模块数量上限（最多 ${draft.sourceProvenance ? 1200 : MAX_DRAFT_NODES} 个）；请删除一个模块后重试。`);
  draft.nodes.push({ id, kind: module.kind, label: module.label, parameters: structuredClone(module.defaults), position });
}
export function removeDraftNode(draft: AuthoredDraft, id: string) {
  const ids = new Set(draftMoveIds(draft, [id]));
  draft.nodes = draft.nodes.filter(node => !ids.has(node.id));
  draft.edges = draft.edges.filter(edge => !ids.has(edge.source.nodeId) && !ids.has(edge.target.nodeId));
}
/** A draft binding has one producer and preserves fan-out; cycles are rejected before mutation. */
export function connectDraft(draft: AuthoredDraft, catalog: DraftCatalog, source: DraftEndpoint, target: DraftEndpoint, id: string) {
  if (draft.edges.length >= (draft.sourceProvenance ? 3600 : MAX_DRAFT_EDGES)) throw new Error(`草稿达到连接数量上限（最多 ${draft.sourceProvenance ? 3600 : MAX_DRAFT_EDGES} 条）；请删除一条连接后重试。`);
  const port = (end: DraftEndpoint) => catalog.modules.find(module => module.kind === draft.nodes.find(node => node.id === end.nodeId)?.kind)?.ports.find(item => item.id === end.portId);
  if (port(source)?.direction !== 'out' || port(target)?.direction !== 'in') throw new Error('请从输出端口连接到输入端口。');
  if (source.nodeId === target.nodeId) throw new Error('模块不能连接到自身。');
  if (draft.edges.some(edge => edge.target.nodeId === target.nodeId && edge.target.portId === target.portId)) throw new Error('该输入已有连接；先选择连线并删除，再重新连接。');
  const reached = new Set<string>(), visit = [target.nodeId];
  while (visit.length) {
    const node = visit.pop()!;
    if (node === source.nodeId) throw new Error('此连接形成循环；当前支持无环模型。');
    if (reached.has(node)) continue; reached.add(node);
    visit.push(...draft.edges.filter(edge => edge.source.nodeId === node).map(edge => edge.target.nodeId));
  }
  draft.edges.push({ id, source: { ...source }, target: { ...target } });
}
export function portPoint(node: DraftNode, module: DraftModule, portId: string, flow: DraftFlow = 'horizontal') {
  return draftPortPoint(node, module, portId, flow);
}
export function setDraftPortLayout(draft: AuthoredDraft, endpoint: DraftEndpoint, layout: PortLayout | null) {
  const node = draft.nodes.find(node => node.id === endpoint.nodeId);
  if (!node) throw new Error('未知模块');
  node.portLayouts ??= {}; node.portLayouts[endpoint.portId] = layout;
}
export function draftRoutes(draft: AuthoredDraft, catalog: DraftCatalog) {
  const flow = draftFlow(draft), nodeFlows = draftNodeFlows(draft);
  // An expanded opaque boundary still owns the conservative tensor ports.
  // Keep it in the router even when its inspected children have no ports.
  const nodes: SceneNode[] = draft.nodes.map(node => ({ id: node.id, ...draftNodeBounds(node, catalog), parentId: node.presentation?.parentId,
    localX: node.position.x, localY: node.position.y, label: node.label, subtitle: '', headerHeight: node.presentation?.group ? 36 : 0, kind: node.kind, category: 'operator',
    fill: '#ffffff', stroke: '#355247', glyph: 'operator', expanded: !!node.presentation?.group, expandable: !!node.presentation?.group, pinned: false, evidence: 'contract', ports: [] }));
  const router = createOrthogonalRouter(nodes, implicitDraftRootIds(draft)), byId = new Map(draft.nodes.map(node => [node.id, node]));
  const sceneNodes = new Map(nodes.map(node => [node.id, node]));
  const routingPorts = draft.nodes.flatMap(node => {
    const module = catalog.modules.find(module => module.kind === node.kind);
    return !module ? [] : module.ports.map(port => ({ id: JSON.stringify([node.id, port.id]), nodeId: node.id,
      ...portPoint(node, module, port.id, nodeFlows[node.id]), fixed: !!node.presentation?.group || !!node.portLayouts?.[port.id] || !!node.presentation?.ports[port.id] && node.portLayouts?.[port.id] !== null }));
  });
  const requests = draft.edges.flatMap(edge => {
    const source = byId.get(edge.source.nodeId), target = byId.get(edge.target.nodeId);
    const sourceModule = catalog.modules.find(module => module.kind === source?.kind), targetModule = catalog.modules.find(module => module.kind === target?.kind);
    if (!source || !target || !sourceModule || !targetModule || !sourceModule.ports.some(port => port.id === edge.source.portId) || !targetModule.ports.some(port => port.id === edge.target.portId)) return [];
    const componentFlow = nodeFlows[source.id];
    const start = portPoint(source, sourceModule, edge.source.portId, componentFlow), end = portPoint(target, targetModule, edge.target.portId, componentFlow);
    const middle = componentFlow === 'horizontal' ? (start.x + end.x) / 2 : (start.y + end.y) / 2;
    let preferredPath = componentFlow === 'horizontal'
      ? start.y === end.y ? `M ${start.x} ${start.y} H ${end.x}` : `M ${start.x} ${start.y} H ${middle} V ${end.y} H ${end.x}`
      : start.x === end.x ? `M ${start.x} ${start.y} V ${end.y}` : `M ${start.x} ${start.y} V ${middle} H ${end.x} V ${end.y}`;
    if (source.portLayouts?.[edge.source.portId] || target.portLayouts?.[edge.target.portId]) preferredPath = portRoutePath(start, end, visualPortSide(sceneNodes.get(source.id)!, start), visualPortSide(sceneNodes.get(target.id)!, end));
    return [{ id: edge.id, sourceId: source.id, targetId: target.id, tensorId: JSON.stringify([source.id, edge.source.portId]),
      sourcePortKey: JSON.stringify([source.id, edge.source.portId]), targetPortKey: JSON.stringify([target.id, edge.target.portId]),
      ...(source.portLayouts?.[edge.source.portId] || target.portLayouts?.[edge.target.portId] ? { sourceSide: visualPortSide(sceneNodes.get(source.id)!, start), targetSide: visualPortSide(sceneNodes.get(target.id)!, end), minimumLeadLength: 12 } : {}), start, end, preferredPath }];
  });
  const selected = selectRoutingPorts(nodes, routingPorts, requests, router);
  const baseline = router.batch(selected.requests);
  const routed = nodes.some(node => node.expanded) ? baseline : refineDraftRoutes(nodes, selected.requests, baseline);
  const routes = requests.map((request, index) => ({ ...routed[index], id: request.id }));
  const ports: Record<string, Record<string, { x: number; y: number; side: PortLayout['side'] }>> = {};
  for (const [key, anchor] of selected.anchors) {
    const [nodeId, portId] = JSON.parse(key) as string[];
    (ports[nodeId] ??= {})[portId] = { x: anchor.x, y: anchor.y, side: visualPortSide(sceneNodes.get(nodeId)!, anchor) };
  }
  return { routes, overlaps: router.overlaps, flow, nodeFlows, ports };
}
/** Only explicit user layout requests move objects; rank order is deterministic. */
export function arrangeDraft(draft: AuthoredDraft, catalog: DraftCatalog, viewport?: { width: number; height: number }) {
  const rank = new Map<string, number>(), waiting = new Set(draft.nodes.map(node => node.id));
  while (waiting.size) {
    let changed = false;
    for (const node of draft.nodes) {
      if (!waiting.has(node.id)) continue;
      const parents = draft.edges.filter(edge => edge.target.nodeId === node.id).map(edge => edge.source.nodeId);
      if (parents.some(id => !rank.has(id))) continue;
      rank.set(node.id, parents.length ? Math.max(...parents.map(id => rank.get(id)!)) + 1 : 0); waiting.delete(node.id); changed = true;
    }
    if (!changed) throw new Error('循环图不能自动排版。');
  }
  // Fold a complete unary chain to the current viewport instead of making a
  // long, unreadable strip. Branch/merge graphs keep their topological lanes.
  const unaryChain = draft.nodes.length >= 7 && draft.edges.length === draft.nodes.length - 1 &&
    new Set(rank.values()).size === draft.nodes.length && draft.nodes.every(node => {
      const module = catalog.modules.find(item => item.kind === node.kind);
      return module && module.ports.filter(port => port.direction === 'in').length <= 1 && module.ports.filter(port => port.direction === 'out').length <= 1 &&
        draft.edges.filter(edge => edge.target.nodeId === node.id).length <= 1 && draft.edges.filter(edge => edge.source.nodeId === node.id).length <= 1;
    });
  if (unaryChain && viewport && Number.isFinite(viewport.width) && Number.isFinite(viewport.height) && viewport.width > 0 && viewport.height > 0) {
    const rowPitch = Math.max(...draft.nodes.map(node => draftNodeSize(node, catalog).height)) + 80;
    let columns = draft.nodes.length, bestZoom = 0;
    for (let candidate = 2; candidate <= draft.nodes.length; candidate++) {
      const width = (candidate - 1) * 248 + 176 + 144, height = (Math.ceil(draft.nodes.length / candidate) - 1) * rowPitch + rowPitch - 80 + 64;
      const zoom = Math.min(1, Math.max(1, viewport.width - 30) / width, Math.max(1, viewport.height - 30) / height);
      if (zoom > bestZoom) { bestZoom = zoom; columns = candidate; }
    }
    for (const node of draft.nodes) {
      const index = rank.get(node.id)!;
      node.position = { x: 50 + index % columns * 248, y: 70 + Math.floor(index / columns) * rowPitch };
    }
    return;
  }
  const nextY = new Map<number, number>();
  const rows = orderedLayers(draft.nodes.map(node => node.id), rank, draft.edges.map(edge => [edge.source.nodeId, edge.target.nodeId] as const));
  const arranged = new Map(draft.nodes.map(node => [node.id, node]));
  for (const id of [...rows.values()].flat()) {
    const node = arranged.get(id)!;
    const column = rank.get(node.id)!, y = nextY.get(column) ?? 70;
    node.position = { x: 50 + column * 248, y };
    nextY.set(column, y + draftNodeSize(node, catalog).height + 54);
  }
}
