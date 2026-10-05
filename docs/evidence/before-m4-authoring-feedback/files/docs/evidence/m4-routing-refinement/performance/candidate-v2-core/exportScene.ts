import { buildScene } from './scene.ts';
import { renderSvg } from './svg.ts';
import { validateDocument, ValidationError } from './validate.ts';
import { CATEGORY_STYLES, EDGE_COLORS } from './tokens.ts';
import { textWidth, wrapText } from './typography.ts';
import { createOrthogonalRouter, orthogonalPathPoints } from './orthogonalRouter.ts';
import type { ArchitectureEdge, CanvasDocument, DetailExportScope, ExportSceneOptions, Scene, SceneNode, ScenePort } from './types.ts';

function pathPoints(path: string): { x: number; y: number }[] {
  let x = 0, y = 0;
  return [...path.matchAll(/([MVH])\s*(-?[\d.]+)(?:\s+(-?[\d.]+))?/g)].map(([, op, a, b]) => {
    if (op === 'M') { x = +a; y = +b; } else if (op === 'H') x = +a; else y = +a;
    return { x, y };
  });
}
function translatePath(path: string, dx: number, dy: number): string {
  return path.replace(/([MVH])\s*(-?[\d.]+)(?:\s+(-?[\d.]+))?/g, (_, op, a, b) => {
    const round = (value: number) => Math.round(value * 100) / 100;
    return op === 'M' ? `M ${round(+a + dx)} ${round(+b + dy)}` : `${op} ${round(+a + (op === 'H' ? dx : dy))}`;
  });
}

/** A view projection of an already expanded container, never a model rewrite. */
export function buildExportScene(document: CanvasDocument, options: ExportSceneOptions = {}): Scene {
  validateDocument(document);
  if (Object.keys(options).some(key => !['nodeId', 'widthMm'].includes(key))) throw new ValidationError('Unknown export scene option');
  const widthMm = options.widthMm ?? document.pageSpec.widthMm;
  if (typeof widthMm !== 'number' || !Number.isFinite(widthMm) || widthMm < 25 || widthMm > 1000) throw new ValidationError('Export width must be within 25–1000 mm');
  const scene = buildScene(document);
  scene.pageSpec = { ...scene.pageSpec, widthMm };
  if (options.nodeId === undefined) return scene;
  const selected = scene.nodes.find(node => node.id === options.nodeId);
  if (!selected || !selected.expanded || !selected.expandable) throw new ValidationError('Detail export requires a currently visible expanded container; expand it before previewing');
  const architecture = document.architecture, canonical = new Map(architecture.nodes.map(node => [node.id, node]));
  const inside = new Set<string>();
  function collect(id: string) { inside.add(id); canonical.get(id)!.children.forEach(collect); }
  collect(selected.id);
  const internal = architecture.edges.filter(edge => inside.has(edge.source.nodeId) && inside.has(edge.target.nodeId));
  const crossing = architecture.edges.filter(edge => inside.has(edge.source.nodeId) !== inside.has(edge.target.nodeId));
  const omitted = architecture.edges.filter(edge => !inside.has(edge.source.nodeId) && !inside.has(edge.target.nodeId));
  const boundaryGroups = new Map<string, { direction: 'in' | 'out'; external: ArchitectureEdge['source']; edges: ArchitectureEdge[] }>();
  for (const edge of crossing) {
    const direction = inside.has(edge.target.nodeId) ? 'in' : 'out', external = direction === 'in' ? edge.source : edge.target;
    const key = JSON.stringify([direction, external.nodeId, external.portId, edge.role]);
    const group = boundaryGroups.get(key);
    if (group) group.edges.push(edge); else boundaryGroups.set(key, { direction, external, edges: [edge] });
  }
  const inputs = [...boundaryGroups.values()].filter(group => group.direction === 'in');
  const outputs = [...boundaryGroups.values()].filter(group => group.direction === 'out');
  const boundaryLayout = new Map([...boundaryGroups.values()].map(group => {
    const external = canonical.get(group.external.nodeId)!;
    const label = `${group.direction === 'in' ? 'FROM' : 'TO'} ${document.displayAliases[external.id] ?? external.label}`;
    const width = Math.max(194, Math.min(300, textWidth(label) + 66));
    return [group, { label, width, height: Math.max(62, wrapText(label, width - 62).length * 16 + 26) }];
  }));
  const bandHeight = (groups: typeof inputs) => groups.reduce((sum, group) => sum + boundaryLayout.get(group)!.height + 20, 0);
  const dx = 35 - selected.x, dy = 104 + bandHeight(inputs) - selected.y;
  const nodes: SceneNode[] = scene.nodes.filter(node => inside.has(node.id)).map(node => ({ ...structuredClone(node), x: node.x + dx, y: node.y + dy,
    ports: node.ports.map(port => ({ ...structuredClone(port), x: port.x + dx, y: port.y + dy })) }));
  const visible = new Map(nodes.map(node => [node.id, node]));
  const internalIds = new Set(internal.map(edge => edge.id));
  const edges = scene.edges.filter(edge => edge.canonicalEdgeIds.every(id => internalIds.has(id))).map(edge => ({ ...structuredClone(edge), path: translatePath(edge.path, dx, dy), labelX: edge.labelX + dx, labelY: edge.labelY + dy }));
  const represented = new Set(edges.flatMap(edge => edge.canonicalEdgeIds));
  function representative(id: string) {
    let node = canonical.get(id)!;
    while (!visible.has(node.id) && node.parentId && inside.has(node.parentId)) node = canonical.get(node.parentId)!;
    return visible.get(node.id)!;
  }
  function insidePort(edge: ArchitectureEdge, direction: 'in' | 'out'): { node: SceneNode; port: ScenePort } {
    const endpoint = direction === 'in' ? edge.target : edge.source, node = representative(endpoint.nodeId);
    let port = node.ports.find(port => port.direction === direction && port.canonicalBindings.some(binding => binding.nodeId === endpoint.nodeId && binding.portId === endpoint.portId) && port.canonicalEdgeIds.includes(edge.id));
    if (!port) {
      const authored = canonical.get(endpoint.nodeId)!.ports.find(port => port.id === endpoint.portId)!;
      const count = node.ports.filter(port => port.direction === direction).length;
      port = { id: `detail:${edge.id}:${direction}`, canonicalNodeId: endpoint.nodeId, canonicalPortId: endpoint.portId,
        canonicalBindings: [structuredClone(endpoint)], canonicalEdgeIds: [edge.id], direction, role: authored.role, name: authored.name,
        x: node.x + node.width * (count + 1) / (count + 2), y: direction === 'in' ? node.y : node.y + node.height, proxy: node.id !== endpoint.nodeId };
      node.ports.push(port);
    }
    return { node, port };
  }
  const mono = scene.pageSpec.preset === 'monochrome';
  const contentBottom = Math.max(...nodes.map(node => node.y + node.height));
  for (const [index, group] of [...boundaryGroups.values()].entries()) {
    const external = canonical.get(group.external.nodeId)!, direction = group.direction;
    const siblings = direction === 'in' ? inputs : outputs, row = siblings.indexOf(group);
    const y = (direction === 'in' ? 94 : contentBottom + 42) + bandHeight(siblings.slice(0, row));
    const { label, width, height } = boundaryLayout.get(group)!;
    let boundaryId = `detail-boundary:${index}`;
    while (canonical.has(boundaryId)) boundaryId += ':boundary';
    const base = CATEGORY_STYLES[direction === 'in' ? 'input' : 'output'];
    const boundary: SceneNode = { id: boundaryId, canonicalNodeId: external.id, boundary: true,
      x: 35, y, localX: 35, localY: y, width, height, parentId: undefined, label,
      subtitle: `external ${direction === 'in' ? 'source' : 'consumer'} · ${group.edges[0].role}`, kind: 'Boundary', category: direction === 'in' ? 'input' : 'output',
      fill: mono ? '#ffffff' : base.fill, stroke: mono ? '#56616b' : base.stroke, glyph: 'tensor',
      headerHeight: height, expanded: false, expandable: false, pinned: false, evidence: external.evidence,
      sourceFact: scene.sourceFacts.find(fact => fact.id === external.id), ports: [] };
    const endpointDirection = direction === 'in' ? 'out' : 'in';
    const name = external.ports.find(port => port.id === group.external.portId)!.name;
    const boundaryPort: ScenePort = { id: `${boundary.id}:${group.external.portId}`, canonicalNodeId: external.id, canonicalPortId: group.external.portId,
      canonicalBindings: [structuredClone(group.external)], canonicalEdgeIds: group.edges.map(edge => edge.id), direction: endpointDirection,
      role: group.edges[0].role, name, x: boundary.x + boundary.width / 2,
      y: direction === 'in' ? boundary.y + boundary.height : boundary.y, proxy: true };
    boundary.ports.push(boundaryPort); nodes.push(boundary);
    for (const [edgeIndex, edge] of group.edges.entries()) {
      const endpoint = insidePort(edge, direction), a = direction === 'in' ? boundaryPort : endpoint.port, b = direction === 'in' ? endpoint.port : boundaryPort;
      const corridor = selected.x + dx + selected.width + 18 + index * 5 + edgeIndex * 3;
      const path = `M ${a.x} ${a.y} V ${a.y + 10} H ${corridor} V ${b.y - 10} H ${b.x} V ${b.y}`;
      const override = document.edgeStyleOverrides[edge.id] ?? {};
      edges.push({ id: edge.id, sourceId: direction === 'in' ? boundary.id : endpoint.node.id, targetId: direction === 'in' ? endpoint.node.id : boundary.id,
        source: structuredClone(edge.source), target: structuredClone(edge.target), canonicalEdgeIds: [edge.id], tensorId: edge.tensorId, role: edge.role,
        path, stroke: mono ? '#56616b' : override.stroke ?? EDGE_COLORS[edge.role], width: override.width ?? 1.5,
        dashed: override.dashed ?? edge.role === 'mask', label: edge.label ?? '', labelX: corridor + 7, labelY: (a.y + b.y) / 2 });
    }
  }
  // Reuse canvas obstacle routing after every boundary body exists. A later
  // boundary row must be an obstacle for earlier incoming/outgoing stubs too.
  const route = createOrthogonalRouter(nodes), routeDiagnostics: Scene['diagnostics'] = [];
  for (const overlap of route.overlaps) routeDiagnostics.push({ level: 'warning', code: 'layout-overlap', objectIds: [overlap.first, overlap.second], message: `Detail objects "${overlap.first}" and "${overlap.second}" overlap. Their manual anchors are preserved; move the objects or increase spacing to resolve this layout conflict.` });
  for (const overlap of route.headerOverlaps) routeDiagnostics.push({ level: 'warning', code: 'layout-header-overlap', objectIds: [overlap.node, overlap.ancestor], message: `Detail object "${overlap.node}" overlaps the header of its expanded ancestor "${overlap.ancestor}". Its manual anchor is preserved; move the object below the header to resolve this layout conflict.` });
  const routedEdges = route.batch(edges.map(edge => {
    const original = orthogonalPathPoints(edge.path);
    return { sourceId: edge.sourceId, targetId: edge.targetId, tensorId: edge.tensorId,
      start: original[0], end: original.at(-1)!, preferredPath: edge.path };
  }));
  edges.forEach((edge, index) => {
    const routed = routedEdges[index];
    edge.path = routed.path;
    if (routed.changed) {
      const segments = routed.points.slice(1).map((point, index) => ({ a: routed.points[index], b: point,
        length: Math.abs(point.x - routed.points[index].x) + Math.abs(point.y - routed.points[index].y) })).sort((a, b) => b.length - a.length);
      const longest = segments[0]; edge.labelX = (longest.a.x + longest.b.x) / 2 + 7; edge.labelY = (longest.a.y + longest.b.y) / 2 - 7;
    }
    if (routed.blockedBy.length) routeDiagnostics.push({ level: 'warning', code: 'layout-route-blocked', objectIds: routed.blockedBy, edgeId: edge.id, message: `Detail edge "${edge.id}" crosses object bodies or headers (${routed.blockedBy.join(', ')}). No clear route was found within the routing budget. Object anchors are preserved; move the reported objects or increase spacing to resolve this routing conflict.` });
  });
  const contained = (annotation: Scene['annotations'][number]) => annotation.x >= selected.x && annotation.y >= selected.y && annotation.x + annotation.width <= selected.x + selected.width && annotation.y + annotation.height <= selected.y + selected.height;
  const annotations = scene.annotations.filter(contained).map(annotation => ({ ...annotation, x: annotation.x + dx, y: annotation.y + dy }));
  const maxBottom = Math.max(...nodes.map(node => node.y + node.height), ...annotations.map(annotation => annotation.y + annotation.height));
  const legend = scene.legend.map((item, i) => ({ ...item, x: 35, y: maxBottom + 38 + i * 27 }));
  const scope: DetailExportScope = { kind: 'detail', selectedNodeId: selected.id, selectedLabel: selected.label, sourceDocumentTitle: document.title,
    canonicalNodeIds: [...inside], internalEdgeIds: internal.map(edge => edge.id), hiddenInternalEdgeIds: internal.filter(edge => !represented.has(edge.id)).map(edge => edge.id),
    boundaryEdges: crossing.map(edge => ({ edgeId: edge.id, direction: inside.has(edge.target.nodeId) ? 'in' : 'out', source: structuredClone(edge.source), target: structuredClone(edge.target), tensorId: edge.tensorId, role: edge.role })),
    omittedEdgeIds: omitted.map(edge => edge.id), includedAnnotationIds: annotations.map(annotation => annotation.id), omittedAnnotationIds: scene.annotations.filter(annotation => !contained(annotation)).map(annotation => annotation.id) };
  const citationY = Math.max(maxBottom + 38, ...legend.map(item => item.y + 20));
  const citationText = `${document.title} · ${selected.label} · rev ${document.revision}\n${crossing.length} boundary bindings shown; ${internal.length - represented.size} internal adapter/hidden bindings retained in metadata.`;
  const citationWidth = Math.max(240, selected.width);
  let citationId = 'detail-provenance';
  while (annotations.some(annotation => annotation.id === citationId)) citationId += ':export';
  annotations.push({ id: citationId, text: citationText, x: 35, y: citationY + 12, width: citationWidth,
    height: Math.max(68, wrapText(citationText, citationWidth - 20, 11).length * 15 + 20) });
  const points = edges.flatMap(edge => pathPoints(edge.path));
  const subtitle = 'MODEL ARCHITECTURE · SOURCE-BOUND VIEW';
  const right = Math.max(50 + textWidth(selected.label, 19), 50 + textWidth(subtitle, 10) + subtitle.length * 1.4, ...nodes.map(node => node.x + node.width + (node.repeat && !node.expanded ? 7 : 0)), ...points.map(point => point.x), ...edges.filter(edge => edge.label).map(edge => edge.labelX + textWidth(edge.label, 9)), ...legend.map(item => item.x + textWidth(item.label, 10) + 35), ...annotations.map(annotation => annotation.x + annotation.width));
  const bottom = Math.max(...nodes.map(node => node.y + node.height), ...points.map(point => point.y), ...annotations.map(annotation => annotation.y + annotation.height));
  const minX = Math.min(0, ...nodes.map(node => node.x - 15), ...points.map(point => point.x - 15), ...annotations.map(annotation => annotation.x - 15));
  const minY = Math.min(0, ...nodes.map(node => node.y - 15), ...points.map(point => point.y - 15), ...annotations.map(annotation => annotation.y - 15));
  return { ...scene, title: selected.label, bounds: { x: minX, y: minY, width: right + 35 - minX, height: bottom + 35 - minY }, nodes, edges,
    hiddenEdges: scope.hiddenInternalEdgeIds, legend, annotations, exportScope: scope,
    diagnostics: [...scene.diagnostics, ...routeDiagnostics, { level: 'info', message: `Detail page of ${selected.id}; every boundary binding is explicitly shown. Unrelated edges and outside annotations are listed in exportScope metadata.` }] };
}

export function publicationPreflight(scene: Scene) {
  const svg = renderSvg(scene), unitPt = scene.pageSpec.widthMm / scene.bounds.width * 72 / 25.4;
  const minFont = Math.min(...Array.from(svg.matchAll(/font-size="([\d.]+)"/g), match => Number(match[1])));
  const suggestedWidthFor7Pt = Math.ceil(7 / minFont * scene.bounds.width * 25.4 / 72);
  return { widthMm: scene.pageSpec.widthMm, heightMm: scene.pageSpec.widthMm * scene.bounds.height / scene.bounds.width,
    minTextPt: minFont * unitPt, nodeLabelPt: 13 * unitPt,
    minMainLinePt: (scene.edges.length ? Math.min(...scene.edges.map(edge => edge.width)) : 1.5) * unitPt,
    suggestedWidthFor7Pt, suggestedHeightFor7Pt: suggestedWidthFor7Pt * scene.bounds.height / scene.bounds.width, exampleTargetPt: 7,
    claim: 'Physical-size measurement only; 7 pt is an adjustable starting recommendation, not a universal journal rule.' };
}

/** Explicit scope choices; this never expands, collapses or edits the canvas. */
export function detailExportChoices(document: CanvasDocument, widthMm = document.pageSpec.widthMm) {
  const full = buildExportScene(document, { widthMm });
  const visible = new Map(full.nodes.map(node => [node.id, node]));
  return full.nodes.filter(node => node.expanded && node.expandable).map(node => {
    const scene = buildExportScene(document, { nodeId: node.id, widthMm });
    const path = [node.label];
    let parent = node.parentId ? visible.get(node.parentId) : undefined;
    while (parent) { path.unshift(parent.label); parent = parent.parentId ? visible.get(parent.parentId) : undefined; }
    return { nodeId: node.id, label: node.label, pathLabel: path.join(' › '),
      visibleNodeCount: scene.nodes.filter(item => !item.boundary).length,
      boundaryBindingCount: scene.exportScope!.boundaryEdges.length, ...publicationPreflight(scene) };
  });
}
