import { createDocument } from './core/document.ts';
import { previewSourceLocation } from './previewInterop.ts';
import type { PreviewEvidenceSource, PreviewVisualGraph } from './previewInterop.ts';
import type { Architecture, ArchitectureNode, CanvasDocument } from './core/types.ts';
import type { PreviewSnapshot } from './PreviewStudio';

const panelCategories: Record<string, string> = { group: 'container', container: 'container', module: 'module', input: 'input', output: 'output',
  attention: 'attention', linear: 'linear', activation: 'activation', normalization: 'norm', norm: 'norm', add: 'residual', residual: 'residual', tensor: 'tensor' };

export function isPreviewPanelDocument(document: CanvasDocument): boolean {
  return document.sourceBindingDigest.startsWith('preview-only:');
}

/** A display projection for panel access. It is never a source-authoring contract. */
export function previewPanelDocument(snapshot: PreviewSnapshot, source?: PreviewEvidenceSource): CanvasDocument {
  const graph = snapshot.graph as unknown as PreviewVisualGraph & {
    caseId?: string; irSha256?: string; edges: { id: string; source: string; target: string; role?: string }[];
    recursive?: { authority?: { detail?: PreviewVisualGraph & { edges: { id: string; source: string; target: string; role?: string }[] } } };
  };
  const detail = graph.recursive?.authority?.detail ?? graph;
  const ids = new Set(detail.nodes.map(node => node.id));
  const nodes: ArchitectureNode[] = detail.nodes.map(node => {
    const location = previewSourceLocation({ nodeId: node.id, node }, source);
    const kind = node.semantic?.kind ?? node.kind ?? 'Opaque';
    const category = Object.hasOwn(panelCategories, kind.toLowerCase()) ? panelCategories[kind.toLowerCase()] : 'opaque';
    return { id: node.id, label: node.label ?? node.id, kind, category,
      ...(node.parent && ids.has(node.parent) ? { parentId: node.parent } : {}),
      children: detail.nodes.filter(child => child.parent === node.id).map(child => child.id), ports: [], parameters: {}, evidence: 'opaque',
      ...(location ? { source: { path: location.path, line: location.line, endLine: location.endLine, expression: location.expression ?? '' } } : {}) };
  });
  const byId = new Map(nodes.map(node => [node.id, node]));
  const edges: Architecture['edges'] = [];
  for (const edge of detail.edges ?? []) {
    const start = byId.get(edge.source), end = byId.get(edge.target);
    if (!start || !end || start === end) continue;
    if (!start.ports.some(port => port.id === 'out')) start.ports.push({ id: 'out', name: 'out', direction: 'out', ordinal: 0, role: 'display' });
    const input = `in:${end.ports.filter(port => port.direction === 'in').length}`;
    end.ports.push({ id: input, name: input, direction: 'in', ordinal: end.ports.filter(port => port.direction === 'in').length, role: 'display' });
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
  const document = createDocument(architecture);
  const positions = new Map(detail.nodes.map(node => [node.id, node]));
  document.expandedIds = graph.nodes.filter(node => node.expanded && byId.get(node.id)?.children.length).map(node => node.id);
  for (const node of detail.nodes) {
    const parent = node.parent ? positions.get(node.parent) : undefined;
    document.layout[node.id] = { x: node.x - (parent?.x ?? 0), y: node.y - (parent?.y ?? 0) };
  }
  return document;
}
