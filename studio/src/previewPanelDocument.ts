import { validateDocument } from './core/validate.ts';
import { CATEGORY_STYLES } from './core/tokens.ts';
import { previewCanvasOperations, previewSelectionNodeIds, previewSourceLocation, previewUniqueNodeBindings } from './previewInterop.ts';
import { previewPresentationFields } from './previewPresentation.ts';
import type { PreviewEvidenceSource, PreviewVisualGraph } from './previewInterop.ts';
import type { Architecture, ArchitectureNode, CanvasDocument, HistoryState } from './core/types.ts';
import type { PreviewSnapshot } from './PreviewStudio';

const panelCategories: Record<string, string> = { group: 'container', container: 'container', module: 'module', input: 'input', output: 'output',
  attention: 'attention', linear: 'linear', activation: 'activation', normalization: 'norm', norm: 'norm', add: 'residual', residual: 'residual', tensor: 'tensor' };

export function isPreviewPanelDocument(document: CanvasDocument): boolean {
  return document.sourceBindingDigest.startsWith('preview-only:');
}

/** Catalog diagrams contain reviewed aggregates and display-only values which a
 * different AST parser cannot turn into unique executable source objects. */
export function previewMappingCoverage(snapshot: PreviewSnapshot, architecture: Architecture, source?: PreviewEvidenceSource) {
  const graph = snapshot.graph as unknown as PreviewVisualGraph & { recursive?: { authority?: { detail?: PreviewVisualGraph } } };
  const nodes = (graph.recursive?.authority?.detail ?? graph).nodes.filter(node => !node.junction);
  const canonical = new Set(architecture.nodes.map(node => node.id));
  const identities = new Map<string, string[]>(), unmapped: string[] = [], ambiguous: string[] = [];
  for (const node of nodes) {
    const ids = canonical.has(node.id) ? [node.id] : previewSelectionNodeIds(architecture, { nodeId: node.id, node }, source);
    if (!ids.length) unmapped.push(node.id);
    else if (ids.length !== 1) ambiguous.push(node.id);
    else identities.set(ids[0], [...(identities.get(ids[0]) ?? []), node.id]);
  }
  const shared = [...identities.values()].filter(ids => ids.length > 1).flat();
  return { total: nodes.length, mapped: nodes.length - unmapped.length - ambiguous.length - shared.length, unmapped, ambiguous, shared };
}
export function previewNeedsPanelDocument(snapshot: PreviewSnapshot, architecture: Architecture, source?: PreviewEvidenceSource): boolean {
  const coverage = previewMappingCoverage(snapshot, architecture, source);
  return coverage.unmapped.length + coverage.ambiguous.length + coverage.shared.length > 0;
}

/** Evidence coverage depends on source objects, never their changing geometry. */
export function previewMappingSignature(snapshot: PreviewSnapshot): string {
  const graph = snapshot.graph as unknown as PreviewVisualGraph & { recursive?: { authority?: { detail?: PreviewVisualGraph } } };
  return JSON.stringify((graph.recursive?.authority?.detail ?? graph).nodes.filter(node => !node.junction).map(node => {
    const raw = node.semantic ?? node;
    return [node.id, raw.id, raw.kind, raw.instance, raw.moduleType, raw.expression, raw.source_evidence,
      raw.sourceStructure, raw.sourceParameters?.callSites];
  }));
}

/** Mirror an already laid-out, validated preview. Replaying `expand` through the
 * formal layout engine would route and displace the same graph a second time.
 * History entries share immutable source architecture and untouched visual fields. */
export function projectPreviewHistory(history: HistoryState, graph: PreviewVisualGraph, source?: PreviewEvidenceSource, title = history.document.title,
  bindings = previewUniqueNodeBindings(history.document.architecture, graph, source)): HistoryState {
  const before = history.document;
  validateDocument(before);
  const operations = previewCanvasOperations(before, graph, source, bindings);
  let layout = before.layout, expandedIds = before.expandedIds;
  for (const operation of operations) {
    if (operation.type === 'nodeLayout') {
      if (layout === before.layout) layout = { ...layout };
      layout[operation.id] = { ...layout[operation.id], ...operation.position };
    } else if (operation.type === 'expand') {
      const expanded = new Set(expandedIds);
      if (operation.expanded) expanded.add(operation.id); else expanded.delete(operation.id);
      expandedIds = [...expanded];
    }
  }
  const presentation = previewPresentationFields(before, graph, source, bindings);
  let changed = layout !== before.layout || expandedIds !== before.expandedIds || title !== before.title;
  for (const key of Object.keys(presentation) as (keyof typeof presentation)[]) {
    if (JSON.stringify(presentation[key]) === JSON.stringify(before[key])) {
      // Keep React dependencies and source-authoring fingerprints stable for
      // selection/tool/busy messages which carry the same document again.
      Object.assign(presentation, { [key]: before[key] });
    } else changed = true;
  }
  if (!changed) return history;
  const document: CanvasDocument = { ...before, ...presentation, title, layout, expandedIds, revision: before.revision + 1 };
  validateDocument(document);
  return { document, past: [...history.past, before].slice(-100), future: [] };
}

/** A display projection for panel access. It is never a source-authoring contract. */
export function previewPanelDocument(snapshot: PreviewSnapshot, source?: PreviewEvidenceSource): CanvasDocument {
  const graph = snapshot.graph as unknown as PreviewVisualGraph & {
    caseId?: string; irSha256?: string; edges: { id: string; source: string; target: string; role?: string }[];
    recursive?: { authority?: { mandatory?: string[]; detail?: PreviewVisualGraph & { edges: { id: string; source: string; target: string; role?: string }[] } }; state?: { open?: string[]; folded?: string[] } };
  };
  const detail = graph.recursive?.authority?.detail ?? graph;
  const ids = new Set(detail.nodes.map(node => node.id));
  const children = new Map<string, string[]>();
  for (const node of detail.nodes) if (node.parent && ids.has(node.parent)) {
    const siblings = children.get(node.parent) ?? [];
    siblings.push(node.id); children.set(node.parent, siblings);
  }
  const nodes: ArchitectureNode[] = detail.nodes.map(node => {
    const location = previewSourceLocation({ nodeId: node.id, node }, source);
    const kind = node.semantic?.kind ?? node.kind ?? 'Opaque';
    const category = Object.hasOwn(panelCategories, kind.toLowerCase()) ? panelCategories[kind.toLowerCase()] : 'opaque';
    return { id: node.id, label: node.label ?? node.id, kind, category,
      ...(node.parent && ids.has(node.parent) ? { parentId: node.parent } : {}),
      children: children.get(node.id) ?? [], ports: [], parameters: {}, evidence: 'opaque',
      ...(location ? { source: { path: location.path, line: location.line, endLine: location.endLine, expression: location.expression ?? '' } } : {}) };
  });
  const byId = new Map(nodes.map(node => [node.id, node]));
  const edges: Architecture['edges'] = [];
  const inputs = new Map<string, number>(), outputs = new Set<string>();
  for (const edge of detail.edges ?? []) {
    const start = byId.get(edge.source), end = byId.get(edge.target);
    if (!start || !end || start === end) continue;
    if (!outputs.has(start.id)) { start.ports.push({ id: 'out', name: 'out', direction: 'out', ordinal: 0, role: 'display' }); outputs.add(start.id); }
    const ordinal = inputs.get(end.id) ?? 0, input = `in:${ordinal}`;
    inputs.set(end.id, ordinal + 1);
    end.ports.push({ id: input, name: input, direction: 'in', ordinal, role: 'display' });
    edges.push({ id: edge.id, source: { nodeId: start.id, portId: 'out' }, target: { nodeId: end.id, portId: input },
      tensorId: `preview:${edge.id}`, role: 'data' });
  }
  const caseId = String(graph.caseId ?? snapshot.caseId ?? snapshot.case ?? 'graph');
  const sources = source?.schema === 'summary-source-adapter/1' ? source.files.map(file => ({ path: file.path, content: file.text, digest: file.sha256 })) :
    source ? Object.entries(source.files).map(([path, content]) => ({ path, content, digest: 'preview-only' })) : [];
  const info = snapshot.caseInfo as { title?: string } | undefined;
  const title = String(snapshot.title ?? info?.title ?? nodes.find(node => !node.parentId)?.label ?? caseId);
  const architecture: Architecture = { schemaVersion: 1, id: `preview:${caseId}`, label: title, entry: source?.entry ?? '',
    sourceDigest: `preview-only:${caseId}`, irDigest: graph.irSha256 ?? `preview-only:${caseId}`, nodes, edges, sources,
    diagnostics: [{ level: 'info', message: '当前文档是预览图的面板投影。源码编辑会从原始 Python 重新建立正式编辑绑定；视觉连接不会自动写入源码。' }] };
  // The preview has already measured and laid out every object. Initial panel
  // setup must not materialize a second scene through the formal renderer.
  const categories = [...new Set(nodes.map(node => node.category))].filter(category => CATEGORY_STYLES[category]);
  const document: CanvasDocument = {
    schemaVersion: 1, id: `canvas-${architecture.id.replace(/[^A-Za-z0-9_.-]/g, '-').slice(0, 72)}-${architecture.sourceDigest.slice(0, 12)}-${architecture.irDigest.slice(0, 8)}`,
    title, revision: 0, sourceBindingDigest: architecture.sourceDigest, architecture,
    displayAliases: {}, nodeStyleOverrides: {}, edgeStyleOverrides: {}, annotations: [],
    legendItems: categories.slice(0, 6).map(category => ({ id: `legend:${category}`, label: category[0].toUpperCase() + category.slice(1), color: CATEGORY_STYLES[category].fill, glyph: CATEGORY_STYLES[category].glyph })),
    pageSpec: { widthMm: 180, background: '#ffffff', preset: 'paper' }, expandedIds: [], layout: {}, layoutByFrontier: {}, pinnedObjects: [],
  };
  const positions = new Map(detail.nodes.map(node => [node.id, node]));
  const mandatory = new Set(graph.recursive?.authority?.mandatory ?? []), folded = new Set(graph.recursive?.state?.folded ?? []);
  const expanded = new Set([...(graph.recursive?.state?.open ?? []), ...mandatory].filter(id => byId.get(id)?.children.length && (mandatory.has(id) || !folded.has(id))));
  for (const node of graph.nodes) if (byId.get(node.id)?.children.length && typeof node.expanded === 'boolean') {
    if (node.expanded) expanded.add(node.id); else expanded.delete(node.id);
  }
  document.expandedIds = [...expanded];
  for (const node of detail.nodes) {
    const parent = node.parent ? positions.get(node.parent) : undefined;
    document.layout[node.id] = { x: node.x - (parent?.x ?? 0), y: node.y - (parent?.y ?? 0) };
  }
  return validateDocument(document);
}
