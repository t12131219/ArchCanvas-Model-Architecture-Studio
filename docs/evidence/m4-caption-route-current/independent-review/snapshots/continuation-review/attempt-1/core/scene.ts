import type { ArchitectureNode, CanvasDocument, EdgeRole, Scene, SceneNode, ScenePort } from './types.ts';
import { CATEGORY_STYLES, TOKENS } from './tokens.ts';
import { effectiveEdgeAppearance, edgeAppearanceKey } from './edgePresentation.ts';
import { buildEdgeLegend } from './edgeLegend.ts';
import { textWidth, wrapText } from './typography.ts';
import { compactOutputPath, sourceNodeFacts } from './nodeFacts.ts';
import { createOrthogonalRouter, orthogonalPathPoints } from './orthogonalRouter.ts';
import type { RoutePoint, RouteRequest } from './orthogonalRouter.ts';
import { nodeVisualOutline, projectVisualPort } from './nodeVisualOutline.ts';
import type { VisualSide } from './nodeVisualOutline.ts';
import { edgeLabelBounds, placeEdgeLabels } from './edgeLabelPlacement.ts';

type Box = { x: number; y: number; width: number; height: number };
const num = (n: number) => Math.round(n * 10) / 10;
function subtitle(n: ArchitectureNode, callCount: number, hasDisplayAlias: boolean): string {
  if (n.evidence === 'opaque') return 'unresolved · opaque boundary';
  if (n.repeat) return `${n.repeat.count} × ${n.repeat.sharing === 'shared' ? 'shared instances' : 'independent instances'}`;
  // An explicit visual alias supplies the output caption. The real return path
  // remains in source facts and SVG titles/metadata; never infer key provenance.
  if (n.outputPath) return hasDisplayAlias ? 'model output' : compactOutputPath(n.outputPath);
  if (callCount > 1) return `shared instance · ${callCount} calls`;
  const p = n.parameters;
  if (p.in_features !== undefined && p.out_features !== undefined) return `${p.in_features} → ${p.out_features}`;
  if (p.embed_dim !== undefined) return `d = ${p.embed_dim}${p.num_heads !== undefined ? ` · ${p.num_heads} heads` : ''}`;
  if (p.p !== undefined) return `p = ${p.p}`;
  if (p.normalized_shape !== undefined) return `shape ${JSON.stringify(p.normalized_shape)}`;
  return n.kind;
}

/** One deterministic projection used by both interactive display and publication export. */
export function buildScene(document: CanvasDocument): Scene {
  const architecture = document.architecture, byId = new Map(architecture.nodes.map(n => [n.id, n]));
  const sourceFacts = sourceNodeFacts(architecture), factsById = new Map(sourceFacts.map(fact => [fact.id, fact]));
  const expanded = new Set(document.expandedIds), visible = new Set<string>(), boxes = new Map<string, Box>();
  const roots = architecture.nodes.filter(n => !n.parentId).map(n => n.id);
  const authoredOrder = new Map(architecture.nodes.map((node, index) => [node.id, index]));
  const auxiliaryInputs = new Set(architecture.edges.filter(edge => edge.role === 'mask' || edge.role === 'memory').map(edge => edge.source.nodeId));
  function directChild(id: string, siblings: Set<string>): string | undefined {
    let n = byId.get(id);
    while (n) { if (siblings.has(n.id)) return n.id; n = n.parentId ? byId.get(n.parentId) : undefined; }
    return undefined;
  }
  function arrange(ids: string[], padding: number, top: number): Box {
    const set = new Set(ids), ranks = new Map(ids.map(id => [id, 0]));
    const links = architecture.edges.filter(e => e.role === 'data').map(e => [directChild(e.source.nodeId, set), directChild(e.target.nodeId, set)]).filter(([s, t]) => s && t && s !== t) as [string, string][];
    // Auxiliary mask inputs are a dedicated side channel. They remain compact and never widen the main token lane.
    const isAuxiliary = (id: string) => {
      const n = byId.get(id)!;
      return n.category === 'input' && auxiliaryInputs.has(id);
    };
    const primaryIds = ids.filter(id => !isAuxiliary(id)), auxiliaryIds = ids.filter(isAuxiliary);
    // Bounded longest-path relaxation also terminates on cycles; cyclic regions retain authored order.
    let cyclic = false;
    for (let pass = 0; pass < ids.length; pass++) {
      let changed = false;
      for (const [s, t] of links) if (ranks.get(t)! <= ranks.get(s)!) { ranks.set(t, ranks.get(s)! + 1); changed = true; }
      if (!changed) break;
      if (pass === ids.length - 1) cyclic = true;
    }
    if (cyclic || (ids.length > 1 && !links.length)) ids.forEach((id, index) => ranks.set(id, index));
    const levels = [...new Set([...ranks.values()])].sort((a, b) => a - b);
    const rows = new Map<number, string[]>();
    for (const id of primaryIds) { const level = ranks.get(id)!; const row = rows.get(level) ?? []; row.push(id); rows.set(level, row); }
    const predecessorsByTarget = new Map<string, Set<string>>();
    for (const [source, target] of links) { const predecessors = predecessorsByTarget.get(target) ?? new Set<string>(); predecessors.add(source); predecessorsByTarget.set(target, predecessors); }
    const widths = levels.map(level => (rows.get(level) ?? []).reduce((w, id, i) => w + boxes.get(id)!.width + (i ? TOKENS.gapX : 0), 0));
    const contentWidth = Math.max(TOKENS.nodeWidth, ...widths);
    let y = top + (auxiliaryIds.length ? 56 : 0), maxX = contentWidth + padding, maxY = top;
    levels.forEach((level, li) => {
      const upstreamCenter = (id: string): number | undefined => {
        const predecessors = [...predecessorsByTarget.get(id) ?? []].filter(source => ranks.get(source)! < level);
        return predecessors.length ? predecessors.reduce((x, source) => x + boxes.get(source)!.x + boxes.get(source)!.width / 2, 0) / predecessors.length : undefined;
      };
      const row = (rows.get(level) ?? []).sort((a, b) => (upstreamCenter(a) ?? authoredOrder.get(a)!) - (upstreamCenter(b) ?? authoredOrder.get(b)!));
      const rowHeight = row.length ? Math.max(...row.map(id => boxes.get(id)!.height)) : 0;
      let x = padding + (contentWidth - widths[li]) / 2;
      for (const id of row) {
        const b = boxes.get(id)!, saved = document.layout[id];
        const center = upstreamCenter(id);
        b.x = saved?.x ?? (center === undefined ? x : Math.max(padding, x, center - b.width / 2)); b.y = saved?.y ?? y;
        maxX = Math.max(maxX, b.x + b.width); maxY = Math.max(maxY, b.y + b.height);
        x = b.x + b.width + TOKENS.gapX;
      }
      y += rowHeight + TOKENS.gapY;
    });
    if (auxiliaryIds.length) {
      let ax = padding;
      for (const id of auxiliaryIds) { const b = boxes.get(id)!, saved = document.layout[id]; b.x = saved?.x ?? ax; b.y = saved?.y ?? top; ax += b.width + 12; maxX = Math.max(maxX, b.x + b.width); maxY = Math.max(maxY, b.y + b.height); }
    }
    return { x: 0, y: 0, width: maxX + padding, height: maxY + padding };
  }
  function size(id: string) {
    const n = byId.get(id)!;
    visible.add(id);
    const label = document.displayAliases[id] ?? n.label;
    const auxiliary = n.category === 'input' && auxiliaryInputs.has(id);
    const width = auxiliary ? Math.max(150, Math.min(180, textWidth(label) + 62)) : Math.max(TOKENS.nodeWidth, Math.min(420, textWidth(label) + 68));
    let box: Box = { x: 0, y: 0, width, height: Math.max(auxiliary ? 40 : TOKENS.nodeHeight, wrapText(label, width - 62).length * 16 + 26) };
    if (expanded.has(id) && n.children.length) {
      n.children.forEach(size);
      const headerHeight = Math.max(TOKENS.header, wrapText(label, width - 90).length * 16 + 23);
      box = arrange(n.children, TOKENS.padding, headerHeight + 16);
      box.width = Math.max(box.width, width + 20);
    }
    if (document.layout[id]?.width !== undefined) box.width = Math.max(box.width, document.layout[id].width!);
    if (document.layout[id]?.height !== undefined) box.height = Math.max(box.height, document.layout[id].height!);
    boxes.set(id, box);
  }
  roots.forEach(size);
  arrange(roots, 50, 92);
  const nodes: SceneNode[] = [];
  function place(id: string, px: number, py: number) {
    const n = byId.get(id)!, b = boxes.get(id)!;
    const base = n.evidence === 'opaque' ? CATEGORY_STYLES.opaque : CATEGORY_STYLES[n.category] ?? CATEGORY_STYLES.module;
    const style = { ...base, ...document.nodeStyleOverrides[id] };
    const mono = document.pageSpec.preset === 'monochrome';
    const node: SceneNode = {
      ...b, x: px + b.x, y: py + b.y, localX: b.x, localY: b.y,
      id, parentId: n.parentId, label: document.displayAliases[id] ?? n.label, subtitle: subtitle(n, factsById.get(id)?.callCount ?? 0, Object.hasOwn(document.displayAliases, id)),
      headerHeight: Math.max(TOKENS.header, wrapText(document.displayAliases[id] ?? n.label, b.width - 90).length * 16 + 23),
      kind: n.kind, category: n.category, fill: mono ? '#ffffff' : style.fill, stroke: mono ? '#56616b' : style.stroke,
      glyph: style.glyph, expanded: expanded.has(id), expandable: n.children.length > 0,
      pinned: document.pinnedObjects.includes(id), evidence: n.evidence, repeat: n.repeat, sourceFact: factsById.get(id), ports: [],
    };
    nodes.push(node);
    if (node.expanded) n.children.forEach(child => place(child, node.x, node.y));
  }
  roots.forEach(id => place(id, 0, 0));
  const sceneById = new Map(nodes.map(n => [n.id, n]));
  const visualBounds = new Map(nodes.map(node => [node.id, nodeVisualOutline(node).bounds]));
  const containmentDiagnostics: Scene['diagnostics'] = [];
  for (const node of nodes) {
    const parent = node.parentId ? sceneById.get(node.parentId) : undefined;
    const outline = visualBounds.get(node.id)!;
    if (parent?.expanded && (outline.x < parent.x - 1e-6 || outline.y < parent.y - 1e-6 ||
        outline.x + outline.width > parent.x + parent.width + 1e-6 || outline.y + outline.height > parent.y + parent.height + 1e-6)) {
      containmentDiagnostics.push({ level: 'warning', code: 'layout-outside-parent', objectIds: [node.id, parent.id],
        message: `Object "${node.id}" extends outside its expanded parent "${parent.id}". Its manual anchor is preserved; move it inside the parent or preview a position repair.` });
    }
  }
  function representative(id: string): string {
    let n = byId.get(id)!;
    while (!visible.has(n.id) && n.parentId) n = byId.get(n.parentId)!;
    return n.id;
  }
  const hiddenEdges: string[] = [];
  const isAncestor = (ancestor: string, descendant: string) => {
    let current = byId.get(descendant)?.parentId;
    while (current) { if (current === ancestor) return true; current = byId.get(current)?.parentId; }
    return false;
  };
  const rawProjected = architecture.edges.map(e => ({ e, s: representative(e.source.nodeId), t: representative(e.target.nodeId) })).filter(({ e, s, t }) => {
    if (s === t && (e.source.nodeId !== s || e.target.nodeId !== t)) { hiddenEdges.push(e.id); return false; }
    // Structural adapter edges at a collapsed boundary are provenance only. Showing them
    // creates a line from a child input/output back to its container, obscuring the main lane.
    if ((e.target.nodeId === t && byId.get(t)!.children.length && isAncestor(t, e.source.nodeId)) ||
        (e.source.nodeId === s && byId.get(s)!.children.length && isAncestor(s, e.target.nodeId))) {
      hiddenEdges.push(e.id); return false;
    }
    return true;
  });
  // Only bundle bindings with the same effective style. Every authored override
  // must remain represented when collapsed hierarchy projects edges together.
  const projected = [...rawProjected.reduce((groups, item) => {
    const style = document.edgeStyleOverrides[item.e.id] ?? {};
    const appearance = effectiveEdgeAppearance(document.pageSpec.preset, item.e.role, style);
    // Keep existing authored-style boundaries even when monochrome projects
    // distinct stored colors to one gray. Add the actual pattern distinction.
    const authoredAppearance = effectiveEdgeAppearance('paper', item.e.role, style);
    const key = `${item.s}|${item.t}|${item.e.tensorId}|${item.e.role}|${item.e.label ?? ''}|${edgeAppearanceKey(authoredAppearance)}|${edgeAppearanceKey(appearance)}`;
    const current = groups.get(key);
    if (current) current.e = { ...current.e, id: current.e.id, label: current.e.label, _canonicalEdgeIds: [...(current.e as typeof current.e & { _canonicalEdgeIds?: string[] })._canonicalEdgeIds ?? [], item.e.id] } as typeof current.e;
    else groups.set(key, { ...item, e: { ...item.e, _canonicalEdgeIds: [item.e.id] } as typeof item.e });
    return groups;
  }, new Map<string, { e: typeof architecture.edges[number] & { _canonicalEdgeIds?: string[] }; s: string; t: string }>()).values()];
  const displaySides = projected.map(({ e, s, t }): { source: VisualSide; target: VisualSide } => {
    const source = sceneById.get(s)!, target = sceneById.get(t)!;
    return e.role === 'memory' && Math.abs(source.y - target.y) < 15 && source.x + source.width < target.x
      ? { source: 'right', target: 'left' } : { source: 'bottom', target: 'top' };
  });
  type PortGroups = { indices: Map<string, number>; canonicalIds: Map<string, Set<string>> };
  const incoming = new Map<string, PortGroups>(), outgoing = new Map<string, PortGroups>();
  // Build each projected port's order and canonical coverage once. The maps
  // retain the same authored projection order used by the previous scans.
  for (const [projectedIndex, item] of projected.entries()) for (const direction of ['in', 'out'] as const) {
    const id = direction === 'out' ? item.s : item.t;
    const binding = direction === 'out' ? item.e.source : item.e.target;
    const registry = direction === 'out' ? outgoing : incoming;
    const group = registry.get(id) ?? { indices: new Map<string, number>(), canonicalIds: new Map<string, Set<string>>() };
    const key = `${binding.nodeId}:${binding.portId}:${item.e.role}`;
    if (!group.indices.has(key)) group.indices.set(key, group.indices.size);
    const side = direction === 'out' ? displaySides[projectedIndex].source : displaySides[projectedIndex].target;
    const bindingKey = JSON.stringify([binding.nodeId, binding.portId, item.e.role, side]);
    const canonicalIds = group.canonicalIds.get(bindingKey) ?? new Set<string>();
    for (const edgeId of item.e._canonicalEdgeIds ?? [item.e.id]) canonicalIds.add(edgeId);
    group.canonicalIds.set(bindingKey, canonicalIds); registry.set(id, group);
  }
  const canonicalEdges = new Map(architecture.edges.map((edge, index) => [edge.id, { edge, index }]));
  const existingPorts = new Map<string, Map<string, ScenePort>>();
  function port(id: string, nodeId: string, portId: string, direction: 'in' | 'out', role: EdgeRole, side: VisualSide): ScenePort {
    const node = sceneById.get(id)!;
    const key = `${nodeId}:${portId}:${role}`, displayKey = JSON.stringify([nodeId, portId, role, side]);
    const existing = existingPorts.get(id)?.get(displayKey);
    if (existing) return existing;
    const canonical = byId.get(nodeId)!.ports.find(p => p.id === portId)!;
    const group = (direction === 'out' ? outgoing : incoming).get(id)!;
    const index = group.indices.get(key)!;
    const canonicalEdgeIds = [...group.canonicalIds.get(displayKey)!];
    // Canonical bindings follow architecture order, even if a collapsed
    // projection bundles non-adjacent canonical edges together.
    const canonicalBindings = canonicalEdgeIds.map(edgeId => canonicalEdges.get(edgeId)!).sort((a, b) => a.index - b.index).map(({ edge }) => direction === 'out' ? edge.source : edge.target);
    const anchor = side === 'right' || side === 'left'
      ? { x: side === 'right' ? node.x + node.width : node.x, y: node.y + node.height * .55 }
      : { x: node.x + node.width * (index + 1) / (group.indices.size + 1), y: side === 'bottom' ? node.y + node.height : node.y };
    const p: ScenePort = { id: side === (direction === 'out' ? 'bottom' : 'top') ? key : `${key}:${side}`,
      canonicalNodeId: nodeId, canonicalPortId: portId, canonicalBindings, canonicalEdgeIds, direction, role: canonical.role, name: canonical.name,
      ...projectVisualPort(node, anchor, side),
      proxy: nodeId !== id };
    node.ports.push(p);
    const byKey = existingPorts.get(id) ?? new Map<string, ScenePort>(); byKey.set(displayKey, p); existingPorts.set(id, byKey);
    return p;
  }
  const parallelCounts = new Map<string, number>();
  const route = createOrthogonalRouter(nodes), routeDiagnostics: Scene['diagnostics'] = [];
  const routePoints: RoutePoint[] = [];
  const routeRequests: RouteRequest[] = [];
  for (const overlap of route.overlaps) routeDiagnostics.push({ level: 'warning', code: 'layout-overlap', objectIds: [overlap.first, overlap.second], message: `Objects "${overlap.first}" and "${overlap.second}" overlap. Their manual anchors are preserved; move the objects or increase spacing to resolve this layout conflict.` });
  for (const overlap of route.headerOverlaps) routeDiagnostics.push({ level: 'warning', code: 'layout-header-overlap', objectIds: [overlap.node, overlap.ancestor], message: `Object "${overlap.node}" overlaps the header of its expanded ancestor "${overlap.ancestor}". Its manual anchor is preserved; move the object below the header to resolve this layout conflict.` });
  const edges = projected.map(({ e, s, t }, index) => {
    const parallelKey = JSON.stringify([s, t, e.tensorId, e.role]);
    const parallelIndex = parallelCounts.get(parallelKey) ?? 0;
    parallelCounts.set(parallelKey, parallelIndex + 1);
    const sourceBox = sceneById.get(s)!, targetBox = sceneById.get(t)!;
    const sides = displaySides[index];
    const a = port(s, e.source.nodeId, e.source.portId, 'out', e.role, sides.source), b = port(t, e.target.nodeId, e.target.portId, 'in', e.role, sides.target);
    const special = e.role !== 'data' || b.y < a.y;
    let path: string, labelX: number, labelY: number;
    if (sides.source === 'right') {
      path = `M ${num(a.x)} ${num(a.y)} H ${num(b.x)}${num(a.y) === num(b.y) ? '' : ` V ${num(b.y)}`}`;
      labelX = (a.x + b.x) / 2 - 18; labelY = a.y - 8;
    } else if (special) {
      const sourceOutline = visualBounds.get(s)!, targetOutline = visualBounds.get(t)!;
      const corridor = Math.max(sourceOutline.x + sourceOutline.width, targetOutline.x + targetOutline.width) + 23 + index % 3 * 11;
      path = `M ${num(a.x)} ${num(a.y)} V ${num(a.y + 13)} H ${num(corridor)} V ${num(b.y - 13)} H ${num(b.x)} V ${num(b.y)}`;
      labelX = corridor + 7; labelY = (a.y + b.y) / 2;
    } else {
      const mid = (a.y + b.y) / 2 + parallelIndex * 8;
      path = `M ${num(a.x)} ${num(a.y)} V ${num(mid)} H ${num(b.x)} V ${num(b.y)}`;
      labelX = (a.x + b.x) / 2 + 8; labelY = mid - 7;
    }
    const canonicalIds = e._canonicalEdgeIds ?? [e.id];
    const canonicalEdgesForRoute = canonicalIds.map(id => canonicalEdges.get(id)?.edge).filter(Boolean) as typeof architecture.edges;
    const appearance = effectiveEdgeAppearance(document.pageSpec.preset, e.role, document.edgeStyleOverrides[e.id]);
    const exactSource = canonicalEdgesForRoute[0]?.source;
    const resolved = !!exactSource && canonicalIds.length > 0 && canonicalEdgesForRoute.length === canonicalIds.length && canonicalEdgesForRoute.every(item => {
      return item.source.nodeId === exactSource.nodeId && item.source.portId === exactSource.portId && item.tensorId === e.tensorId && item.role === e.role &&
        edgeAppearanceKey(effectiveEdgeAppearance(document.pageSpec.preset, item.role, document.edgeStyleOverrides[item.id])) === edgeAppearanceKey(appearance);
    }) && canonicalIds.every(id => a.canonicalEdgeIds.includes(id)) && a.canonicalBindings.length > 0 &&
      a.canonicalBindings.every(binding => binding.nodeId === exactSource.nodeId && binding.portId === exactSource.portId);
    const exactTarget = canonicalEdgesForRoute[0]?.target;
    const collapsedTarget = resolved && !!exactTarget && b.proxy && !targetBox.expanded && targetBox.expandable &&
      isAncestor(t, exactTarget.nodeId) && canonicalEdgesForRoute.every(item =>
        item.target.nodeId === exactTarget.nodeId && item.target.portId === exactTarget.portId) &&
      canonicalIds.every(id => b.canonicalEdgeIds.includes(id)) && b.canonicalBindings.length > 0 &&
      b.canonicalBindings.every(binding => binding.nodeId === exactTarget.nodeId && binding.portId === exactTarget.portId);
    routeRequests.push({ sourceId: s, targetId: t, tensorId: e.tensorId, role: e.role,
      appearance, canonicalEdgeIds: canonicalIds, canonicalSource: resolved ? { ...exactSource } : undefined,
      canonicalTarget: collapsedTarget ? { ...exactTarget } : undefined,
      displaySide: sides.source, start: { x: a.x, y: a.y }, end: { x: b.x, y: b.y }, preferredPath: path });
    return { id: e.id, sourceId: s, targetId: t, source: e.source, target: e.target, canonicalEdgeIds: e._canonicalEdgeIds ?? [e.id], tensorId: e.tensorId, role: e.role,
      path, ...appearance, label: e.label ?? (e.role === 'memory' && Math.abs(sourceBox.y - targetBox.y) < 15 ? 'memory' : ''), labelX, labelY };
  });
  // Display sides own distinct immutable port projections; every request and
  // its final public circle use the same endpoint throughout batch routing.
  const routedEdges = route.batch(routeRequests);
  edges.forEach((edge, index) => {
    const routed = routedEdges[index]; routePoints.push(...routed.points); edge.path = routed.path;
    if (routed.changed) {
      const segments = routed.points.slice(1).map((point, i) => ({ a: routed.points[i], b: point,
        length: Math.abs(point.x - routed.points[i].x) + Math.abs(point.y - routed.points[i].y) })).sort((first, second) => second.length - first.length);
      const longest = segments[0]; edge.labelX = (longest.a.x + longest.b.x) / 2 + 7; edge.labelY = (longest.a.y + longest.b.y) / 2 - 7;
    }
    if (routed.blockedBy.length) routeDiagnostics.push({ level: 'warning', code: 'layout-route-blocked', objectIds: routed.blockedBy, edgeId: edge.id, message: `Edge "${edge.id}" crosses object bodies or headers (${routed.blockedBy.join(', ')}). No clear route was found within the routing budget. Object anchors are preserved; move the reported objects or increase spacing to resolve this routing conflict.` });
  });
  const maxBottom = Math.max(160, ...[...visualBounds.values()].map(b => b.y + b.height));
  const legend = document.legendItems.map((item, i) => ({ ...item, color: document.pageSpec.preset === 'monochrome' ? '#ffffff' : item.color,
    x: 50 + i % 3 * 185, y: maxBottom + 52 + Math.floor(i / 3) * 27 }));
  const annotations = document.annotations.map(a => {
    const width = a.width ?? Math.max(150, Math.min(400, textWidth(a.text, 11) + 20));
    return { ...a, width, height: Math.max(a.height ?? 34, wrapText(a.text, width - 20, 11).length * 15 + 20) };
  });
  const labelPlacement = placeEdgeLabels(nodes, edges, annotations);
  for (const edge of edges) {
    const position = labelPlacement.placements.get(edge.id);
    if (position) { edge.labelX = position.x; edge.labelY = position.y; }
  }
  const labelBounds = edges.filter(edge => edge.label).map(edge => edgeLabelBounds(edge.label, edge.labelX, edge.labelY));
  const guidePoints = labelPlacement.guides.flatMap(guide => orthogonalPathPoints(guide.path));
  const guideXs = guidePoints.map(point => point.x), guideYs = guidePoints.map(point => point.y);
  const modelRight = Math.max(560, ...[...visualBounds.values()].map(b => b.x + b.width + 55), ...routePoints.map(point => point.x + 20), ...guideXs.map(x => x + 20), ...edges.map(e => e.labelX + 90), ...labelBounds.map(b => b.x + b.width + 20), ...legend.map(l => l.x + 175));
  const contentRight = Math.max(modelRight, ...annotations.map(a => a.x + a.width + 20));
  // A note may enlarge the page, but cannot change this derived band's row
  // capacity: moving that note below the figure must not reflow it repeatedly.
  const edgeLegendLayout = { x: 50, y: Math.max(maxBottom + 35, ...routePoints.map(point => point.y + 20), ...guideYs.map(y => y + 20), ...labelBounds.map(b => b.y + b.height + 20), ...legend.map(l => l.y + 8)) + 24, availableWidth: modelRight - 70 };
  const edgeLegend = buildEdgeLegend(edges, document.pageSpec.preset, edgeLegendLayout, annotations,
    [...nodes, ...edges, ...legend, ...annotations].map(item => item.id));
  const right = Math.max(contentRight, ...edgeLegend.map(item => item.x + item.width + 20));
  const bottom = Math.max(maxBottom + 35, ...routePoints.map(point => point.y + 20), ...guideYs.map(y => y + 20), ...labelBounds.map(b => b.y + b.height + 20), ...legend.map(l => l.y + 25), ...annotations.map(a => a.y + a.height + 20), ...edgeLegend.map(item => item.y + item.height + 20));
  const minX = Math.min(0, ...nodes.map(n => n.x - 30), ...routePoints.map(point => point.x - 20), ...guideXs.map(x => x - 20), ...labelBounds.map(b => b.x - 20), ...annotations.map(a => a.x - 20));
  const minY = Math.min(0, ...nodes.map(n => n.y - 30), ...routePoints.map(point => point.y - 20), ...guideYs.map(y => y - 20), ...labelBounds.map(b => b.y - 20), ...annotations.map(a => a.y - 20));
  const layoutDiagnostics: Scene['diagnostics'] = nodes.filter(n => n.pinned).flatMap(pinned => nodes.filter(n => {
    const bounds = visualBounds.get(pinned.id)!;
    return n.expanded && n.id !== pinned.id && !isAncestor(n.id, pinned.id) && !isAncestor(pinned.id, n.id) &&
      bounds.x < n.x + n.width && bounds.x + bounds.width > n.x && bounds.y < n.y + n.height && bounds.y + bounds.height > n.y;
  }).map(container => ({ level: 'warning', code: 'layout-overlap' as const, objectIds: [pinned.id, container.id], message: `Pinned object "${pinned.label}" overlaps expanded "${container.label}". Both anchors were preserved; move or unpin the object to resolve this layout conflict.` })));
  return { version: '1.0', documentId: document.id, revision: document.revision, title: document.title,
    bounds: { x: minX, y: minY, width: right - minX, height: bottom - minY }, nodes, edges, hiddenEdges, legend, annotations,
    ...(labelPlacement.guides.length ? { captionGuides: labelPlacement.guides } : {}),
    ...(edgeLegend.length ? { edgeLegend, edgeLegendLayout } : {}),
    pageSpec: document.pageSpec, sourceDigest: architecture.sourceDigest, irDigest: architecture.irDigest, sourceFacts,
    diagnostics: [...architecture.diagnostics, ...containmentDiagnostics, ...layoutDiagnostics, ...routeDiagnostics, ...labelPlacement.diagnostics] };
}
