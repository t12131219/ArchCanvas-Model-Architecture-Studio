import type { Architecture, Bounds, CanvasDocument, EdgeStyle } from './core/types.ts';
import type { AnnotationBodyConflict } from './core/annotationPlacement.ts';
import { previewNodeLayoutOperation, previewSelectionNodeIds, previewSourceMatchesArchitecture } from './previewInterop.ts';
import type { PreviewEvidenceSource, PreviewVisualGraph } from './previewInterop.ts';

export type PreviewVisualEdge = {
  id: string; source: string; target: string; draft?: boolean; binding?: Record<string, unknown>;
  stroke?: string; width?: number; dashed?: boolean;
  projection?: { original?: string; originals?: string[]; source?: string; target?: string };
};
type Presentation = {
  title?: string;
  nodes?: Record<string, { alias?: string; fill?: string; stroke?: string; glyph?: string; pinned?: boolean }>;
  edges?: Record<string, EdgeStyle>; legend?: CanvasDocument['legendItems'];
  annotations?: Record<string, CanvasDocument['annotations'][number]>; page?: Partial<CanvasDocument['pageSpec']>;
};
type Graph = PreviewVisualGraph & { edges?: PreviewVisualEdge[]; canvas?: [number, number]; studioPresentation?: Presentation;
  recursive?: { state?: { studioPresentation?: Presentation }; authority?: { detail?: Graph } } };
const graphValue = (value: unknown): Graph | undefined => value && typeof value === 'object' ? value as Graph : undefined;

/** The recursive state is authoritative after an undo or frontier rebuild. */
export function previewPresentation(value: unknown): Presentation | undefined {
  const graph = graphValue(value);
  return graph?.recursive?.state?.studioPresentation ?? graph?.studioPresentation;
}

/** Native notes use a baseline and 20-unit wrapped lines, independently of the
 * formal renderer. Inspector geometry must follow those visible text metrics. */
export function previewAnnotationBody(annotation: CanvasDocument['annotations'][number]): Bounds {
  const width = Math.max(80, annotation.width || 380), length = Math.max(10, Math.floor(width / 9));
  const lines = String(annotation.text || '').split('\n').reduce((count, line) => count + Math.max(1, Math.ceil(line.length / length)), 0);
  return { x: annotation.x - 5, y: annotation.y - 17, width: width + 10, height: lines * 20 + 7 };
}

function previewAnnotationGeometry(value: unknown) {
  const graph = graphValue(value), presentation = previewPresentation(value);
  const nodes = (graph?.nodes ?? []).filter(node => !node.junction).map(node => ({ id: node.id, parent: node.parent,
    x: node.x, y: node.y, width: node.w ?? 180, height: node.h ?? 70 }));
  const annotations = Object.values(presentation?.annotations ?? {}).map(annotation => ({ id: annotation.id, ...previewAnnotationBody(annotation) }));
  const count = presentation?.legend?.length ?? 0, canvas = graph?.canvas;
  const legend = count && canvas ? { id: 'studio:legend', x: Math.max(10, canvas[0] - 270), y: Math.max(10, canvas[1] - count * 28 - 52), width: 250, height: count * 28 + 32 } : undefined;
  return { nodes, annotations, legend };
}

/** Inspect visible bodies only; expanded frames keep their free interior space. */
export function previewAnnotationConflicts(value: unknown, id: string): AnnotationBodyConflict[] {
  const { nodes, annotations, legend } = previewAnnotationGeometry(value), body = annotations.find(annotation => annotation.id === id);
  if (!body) return [];
  const intersects = (other: Bounds) => body.x < other.x + other.width && body.x + body.width > other.x && body.y < other.y + other.height && body.y + body.height > other.y;
  const parents = new Set(nodes.map(node => node.parent)), conflicts: AnnotationBodyConflict[] = [];
  for (const node of nodes) if (!parents.has(node.id) && intersects(node)) conflicts.push({ kind: 'node', id: node.id });
  if (legend && intersects(legend)) conflicts.push({ kind: 'legend', id: legend.id });
  for (const annotation of annotations) if (annotation.id !== id && intersects(annotation)) conflicts.push({ kind: 'annotation', id: annotation.id });
  return conflicts;
}

/** Move the note below current preview bodies without running layout or routing.
 * Excluding the note itself makes repeating the explicit command a no-op. */
export function previewAnnotationPosition(value: unknown, id: string): { x: number; y: number } {
  const { nodes, annotations, legend } = previewAnnotationGeometry(value);
  const bodies = [...nodes, ...annotations.filter(annotation => annotation.id !== id), ...(legend ? [legend] : [])];
  return { x: Math.min(50, ...nodes.map(node => node.x), ...(legend ? [legend.x] : [])),
    y: Math.max(92, ...bodies.map(body => body.y + body.height)) + 24 + 17 };
}

/** Send only changed formal presentation; layout retains the preview's own frames. */
export function previewDocumentSyncOperations(before: CanvasDocument | undefined, after: CanvasDocument, value: unknown,
  source?: PreviewEvidenceSource): Record<string, unknown>[] {
  if (!source || !previewSourceMatchesArchitecture(source, after.architecture)) throw new Error('预览与正式文档的源码字节不同，暂不同步视觉操作。');
  if (before && (before.id !== after.id || before.sourceBindingDigest !== after.sourceBindingDigest ||
    before.architecture.irDigest !== after.architecture.irDigest || before.architecture.entry !== after.architecture.entry)) {
    throw new Error('正式文档源码绑定已变化，请重新接入预览。');
  }
  const graph = graphValue(value);
  if (!graph?.nodes) throw new Error('预览图尚未就绪。');
  const all = graph.recursive?.authority?.detail?.nodes ?? graph.nodes;
  const equal = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
  const nodes: Record<string, unknown> = {}, edges: Record<string, EdgeStyle> = {};
  const operations: Record<string, unknown>[] = [];
  const identity = new Map<string, string>();
  for (const node of all) {
    const ids = previewSelectionNodeIds(after.architecture, { nodeId: node.id, node }, source);
    if (ids.length !== 1 || identity.has(ids[0])) continue;
    identity.set(ids[0], node.id);
  }
  for (const [id, previewId] of identity) {
    const desired = { ...(after.displayAliases[id] !== undefined ? { alias: after.displayAliases[id] } : {}),
      ...after.nodeStyleOverrides[id], pinned: after.pinnedObjects.includes(id) };
    const previous = before ? { ...(before.displayAliases[id] !== undefined ? { alias: before.displayAliases[id] } : {}),
      ...before.nodeStyleOverrides[id], pinned: before.pinnedObjects.includes(id) } : undefined;
    if (!equal(previous, desired)) nodes[previewId] = desired;
    if (before && !equal(before.layout[id], after.layout[id]) && after.layout[id]) {
      operations.push(previewNodeLayoutOperation(after, { type: 'nodeLayout', id, position: after.layout[id] }, graph, source));
    }
    const canonical = after.architecture.nodes.find(node => node.id === id);
    if (canonical?.children.length && before && before.expandedIds.includes(id) !== after.expandedIds.includes(id)) {
      operations.push({ type: 'expand', id: previewId, expanded: after.expandedIds.includes(id) });
    }
  }
  for (const edge of previewGraphEdges(graph)) {
    const ids = previewFormalEdgeIds(after.architecture, edge, graph, source);
    if (ids.length === 1 && (!before || !equal(before.edgeStyleOverrides[ids[0]], after.edgeStyleOverrides[ids[0]]))) {
      edges[edge.id] = after.edgeStyleOverrides[ids[0]] ?? {};
    }
  }
  if (Object.keys(nodes).length || Object.keys(edges).length || !before || before.title !== after.title ||
    !equal(before.legendItems, after.legendItems) || !equal(before.annotations, after.annotations) || !equal(before.pageSpec, after.pageSpec)) {
    operations.unshift({ type: 'syncPresentation', nodes, edges, title: after.title, legend: after.legendItems, annotations: after.annotations, page: after.pageSpec });
  }
  return operations;
}

/** Use the actual visible object for inspector coordinates and default paint. */
export function previewNodePresentation(value: unknown, node: PreviewVisualGraph['nodes'][number]) {
  const overlay = previewPresentation(value), item = overlay?.nodes?.[node.id];
  return { x: node.x, y: node.y, width: node.w, height: node.h, expanded: !!node.expanded,
    fill: overlay?.page?.preset === 'monochrome' ? '#ffffff' : item?.fill ?? node.fill ?? '#eef1fa',
    stroke: overlay?.page?.preset === 'monochrome' ? '#343a40' : item?.stroke ?? '#263348', glyph: item?.glyph };
}
export function previewGraphEdges(value: unknown): PreviewVisualEdge[] {
  const edges = graphValue(value)?.edges;
  return Array.isArray(edges) ? edges.filter(edge => edge && typeof edge.id === 'string' && typeof edge.source === 'string' && typeof edge.target === 'string') : [];
}
export function isPreviewDraftEdge(edge: PreviewVisualEdge): boolean {
  return edge.draft === true || /visual edit draft/i.test(String(edge.binding?.evidence ?? ''));
}

/** Match the original source relation, never a visually reconnected edge or a guessed parallel operand. */
export function previewFormalEdgeIds(architecture: Architecture, edge: PreviewVisualEdge, value: unknown,
  source?: PreviewEvidenceSource): string[] {
  if (isPreviewDraftEdge(edge)) return [];
  const graph = graphValue(value), detail = graph?.recursive?.authority?.detail;
  const originals = edge.projection?.originals ?? (edge.projection?.original ? [edge.projection.original] : []);
  if (detail && originals.length) {
    const raw = originals.map(id => previewGraphEdges(detail).find(candidate => candidate.id === id));
    if (raw.some(item => !item)) return [];
    const mapped = raw.map(item => previewFormalEdgeIds(architecture, { ...item!, projection: undefined }, detail, source));
    if (mapped.some(ids => ids.length !== 1)) return [];
    return [...new Set(mapped.flat())];
  }
  const nodes = detail?.nodes ?? graph?.nodes ?? [];
  const mapped = (id: string) => {
    const node = nodes.find(item => item.id === id);
    return node ? previewSelectionNodeIds(architecture, { nodeId: id, node }, source) : [];
  };
  const from = mapped(edge.source), to = mapped(edge.target);
  if (from.length !== 1 || to.length !== 1) return [];
  const candidates = architecture.edges.filter(item => item.source.nodeId === from[0] && item.target.nodeId === to[0]);
  const sourceIds = [edge.id, ...(Array.isArray(edge.binding?.semantic_edges) ? edge.binding.semantic_edges : [])];
  const exact = candidates.filter(item => sourceIds.includes(item.id));
  return exact.length === 1 ? [exact[0].id] : candidates.length === 1 ? [candidates[0].id] : [];
}

function edgeStyle(raw?: EdgeStyle): EdgeStyle {
  return { ...(typeof raw?.stroke === 'string' ? { stroke: raw.stroke } : {}),
    ...(Number.isFinite(raw?.width) ? { width: raw!.width } : {}),
    ...(typeof raw?.dashed === 'boolean' ? { dashed: raw.dashed } : {}) };
}
function overlayEdgeStyle(value: unknown, edge: PreviewVisualEdge): EdgeStyle | undefined {
  const styles = previewPresentation(value)?.edges;
  return styles?.[edge.id] ?? (edge.projection?.original ? styles?.[edge.projection.original] : undefined);
}
export function previewEdgeAppearance(value: unknown, edge: PreviewVisualEdge) {
  const style = { ...edgeStyle(edge), ...edgeStyle(overlayEdgeStyle(value, edge)) };
  return { stroke: previewPresentation(value)?.page?.preset === 'monochrome' ? '#4b5563' : style.stroke ?? '#263b4b',
    width: style.width ?? 2.2, dashed: style.dashed ?? false };
}

/** Rebuild every presentation field from the current snapshot so undo can remove overrides. */
export function previewPresentationFields(document: CanvasDocument, value: unknown, source?: PreviewEvidenceSource): Pick<CanvasDocument,
  'displayAliases' | 'nodeStyleOverrides' | 'edgeStyleOverrides' | 'pinnedObjects' | 'legendItems' | 'annotations' | 'pageSpec'> {
  const graph = graphValue(value), presentation = previewPresentation(value), detail = graph?.recursive?.authority?.detail;
  const nodes = [...(graph?.nodes ?? []), ...(detail?.nodes ?? [])];
  const displayAliases: CanvasDocument['displayAliases'] = {}, nodeStyleOverrides: CanvasDocument['nodeStyleOverrides'] = {};
  const edgeStyleOverrides: CanvasDocument['edgeStyleOverrides'] = {}, pinnedObjects: string[] = [];
  for (const [id, item] of Object.entries(presentation?.nodes ?? {})) {
    const raw = nodes.find(node => node.id === id);
    const ids = raw ? previewSelectionNodeIds(document.architecture, { nodeId: id, node: raw }, source) : [];
    for (const target of ids) {
      if (item.alias !== undefined) displayAliases[target] = item.alias;
      if (item.fill || item.stroke || item.glyph) nodeStyleOverrides[target] = { ...(item.fill ? { fill: item.fill } : {}),
        ...(item.stroke ? { stroke: item.stroke } : {}), ...(item.glyph ? { glyph: item.glyph as 'module' } : {}) };
      if (item.pinned) pinnedObjects.push(target);
    }
  }
  // Hidden original edges retain their own style. A bundled visible edge may
  // represent several formal operands; its style stays in the preview document.
  for (const edge of [...previewGraphEdges(detail), ...previewGraphEdges(graph)]) {
    const raw = overlayEdgeStyle(graph, edge);
    if (!raw) continue;
    const ids = previewFormalEdgeIds(document.architecture, edge, graph, source);
    if (ids.length === 1) edgeStyleOverrides[ids[0]] = edgeStyle(raw);
  }
  return { displayAliases, nodeStyleOverrides, edgeStyleOverrides, pinnedObjects: [...new Set(pinnedObjects)],
    legendItems: structuredClone(presentation?.legend ?? []), annotations: structuredClone(Object.values(presentation?.annotations ?? {})),
    pageSpec: { widthMm: 180, background: '#ffffff', preset: 'paper', ...presentation?.page } };
}
