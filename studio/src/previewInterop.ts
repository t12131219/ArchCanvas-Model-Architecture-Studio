import type { Architecture, ArchitectureNode, CanvasDocument, VisualOperation } from './core/types.ts';
import type { AuthoredDraft } from './authoring.ts';

/** The preview adapter and the model editor analyse the same bytes with distinct IR contracts. */
export type PreviewSourceRequest = { files: Record<string, string>; entry: string; config: Record<string, unknown>; semanticMode?: 'summary' | 'legacy' };
export type PreviewSourceLocation = { path: string; line: number; endLine: number; expression?: string; column?: number; endColumn?: number };
export type PreviewEvidence = { file: string; line: number; endLine: number; expression: string; column?: number; endColumn?: number };
export type PreviewSourceNode = { id: string; parent?: string | null; kind?: string; operator?: string; semantic_type?: string; shape?: unknown; sourceKind?: string; label?: string; instance?: string; moduleType?: string; expression?: string; source_evidence?: string[]; sourceStructure?: boolean;
  presentation_only?: boolean; canonical_members?: string[]; sourceParameters?: { callSites?: (Partial<PreviewEvidence> & { path?: string })[]; condition?: string } };
export type PreviewSourceBundle = {
  schema: 'summary-source-adapter/1'; id: string; entry: string; sourceSha256: string; irSha256: string;
  files: { path: string; text: string; sha256: string }[]; config?: Record<string, unknown>;
  semanticMode?: 'summary' | 'legacy';
  ir?: { nodes: PreviewSourceNode[]; semanticSchema?: string; semantic_ir?: Record<string, unknown> };
  semantic?: { schema?: string; irDigest?: string; coverage?: { status?: string; scope?: string; complete?: boolean; reason?: string }; motifs?: unknown[]; semanticContracts?: unknown[]; modelExecuted?: boolean };
  evidence?: Record<string, PreviewEvidence>;
};
export type RawPreviewSource = {
  schema: 'archcanvas-preview-source/1'; caseId: string; title?: string; entry: string; files: Record<string, string>;
  evidence?: Record<string, PreviewEvidence>; profile?: Record<string, unknown>; config?: Record<string, unknown>;
};
export type PreviewEvidenceSource = PreviewSourceBundle | RawPreviewSource;
export type PreviewSelection = {
  caseId?: string; nodeId?: string; node?: PreviewSourceNode & { semantic?: PreviewSourceNode };
  sourcePath?: string; line?: number; span?: Partial<PreviewEvidence> & { path?: string };
  evidence?: PreviewEvidence | PreviewEvidence[] | Record<string, PreviewEvidence>;
};
export type PreviewSourceIdentity = { documentId: string; entry: string; sourceDigest: string; irDigest: string };
export type PreviewRequestTicket = { sequence: number; key: string };

function pythonPath(raw: string): string {
  if (typeof raw !== 'string') throw new Error('源码路径必须是相对 Python 文件路径。');
  const path = raw.replaceAll('\\', '/'), parts = path.split('/');
  if (path.startsWith('/') || /^[A-Za-z]:/.test(path) || parts.includes('..') || path.includes('\0')) {
    throw new Error(`源码路径不能离开模型工作副本：${raw}`);
  }
  const normalized = parts.filter(part => part && part !== '.').join('/');
  if (!normalized.endsWith('.py')) throw new Error(`只支持 Python 源文件：${raw}`);
  return normalized;
}

function sourceRequest(files: { path: string; text: string }[], entry: string, config: Record<string, unknown>): PreviewSourceRequest {
  if (!Array.isArray(files) || !files.length || files.length > 80) throw new Error('请选择 1–80 个 Python 源文件。');
  if (typeof entry !== 'string' || !entry.trim()) throw new Error('缺少模型入口。');
  if (!config || typeof config !== 'object' || Array.isArray(config)) throw new Error('构造参数必须是 JSON 对象。');
  const entries: [string, string][] = [], paths = new Set<string>();
  let size = 0;
  for (const file of files) {
    const path = pythonPath(file.path);
    if (paths.has(path)) throw new Error(`源码路径重复：${path}`);
    if (typeof file.text !== 'string') throw new Error(`源码内容必须是文本：${path}`);
    paths.add(path); size += new TextEncoder().encode(file.text).length;
    entries.push([path, file.text]);
  }
  if (size > 2_000_000) throw new Error('源码总量超过 2 MB。');
  // Summary_Merge semantic analysis is the sole source/graph authority for
  // migrated previews.  Keep an explicit escape hatch for old saved bundles,
  // but make every Studio initiated request select the Summary IR by default.
  return { files: Object.fromEntries(entries.sort(([a], [b]) => a.localeCompare(b))), entry: entry.trim(), config: structuredClone(config), semanticMode: 'summary' };
}

/** Submit the registered workspace corpus, including local dependencies, rather than one display file. */
export function architecturePreviewRequest(architecture: Pick<Architecture, 'sources' | 'entry'>, config: Record<string, unknown> = {}): PreviewSourceRequest {
  return sourceRequest(architecture.sources.map(source => ({ path: source.path, text: source.content })), architecture.entry, config);
}

export function bundlePreviewRequest(bundle: PreviewSourceBundle): PreviewSourceRequest {
  if (bundle.schema !== 'summary-source-adapter/1') throw new Error('不支持的源码适配包。');
  return sourceRequest(bundle.files, bundle.entry, bundle.config ?? {});
}

export function rawPreviewSourceRequest(source: RawPreviewSource): PreviewSourceRequest {
  if (source.schema !== 'archcanvas-preview-source/1' || !source.files || typeof source.files !== 'object' || Array.isArray(source.files)) {
    throw new Error('不支持的预览源码包。');
  }
  return sourceRequest(Object.entries(source.files).map(([path, text]) => ({ path, text })), source.entry, source.config ?? {});
}

/** Manifest hashes differ because the two parsers use different manifest keys; compare entry and bytes. */
export function assertPreviewBundleMatchesArchitecture(bundle: PreviewSourceBundle, architecture: Pick<Architecture, 'sources' | 'entry'>): void {
  const preview = bundlePreviewRequest(bundle), editing = architecturePreviewRequest(architecture);
  if (preview.entry !== editing.entry || Object.keys(preview.files).length !== Object.keys(editing.files).length ||
    Object.entries(editing.files).some(([path, content]) => preview.files[path] !== content)) {
    throw new Error('预览源码与当前模型工作副本不同；保留当前编辑会话。');
  }
}

/** A catalog ID and an adapter ID may describe the same exact source corpus. */
export function previewSourceMatchesArchitecture(source: PreviewEvidenceSource, architecture: Pick<Architecture, 'sources' | 'entry'>): boolean {
  try {
    const preview = source.schema === 'summary-source-adapter/1' ? bundlePreviewRequest(source) : rawPreviewSourceRequest(source);
    const editing = architecturePreviewRequest(architecture);
    return preview.entry === editing.entry && Object.keys(preview.files).length === Object.keys(editing.files).length &&
      Object.entries(editing.files).every(([path, content]) => preview.files[path] === content);
  } catch { return false; }
}

export function previewSourceIdentity(architecture: Pick<Architecture, 'id' | 'entry' | 'sourceDigest' | 'irDigest'>, documentId = architecture.id): PreviewSourceIdentity {
  return { documentId, entry: architecture.entry, sourceDigest: architecture.sourceDigest, irDigest: architecture.irDigest };
}
export function previewSourceKey(identity: PreviewSourceIdentity): string {
  return JSON.stringify([identity.documentId, identity.entry, identity.sourceDigest, identity.irDigest]);
}

/** A parser response or iframe reply can publish only for its latest source generation. */
export class PreviewRequestGate {
  private sequence = 0;
  private key: string | null = null;
  begin(identity: PreviewSourceIdentity): PreviewRequestTicket {
    this.key = previewSourceKey(identity);
    return Object.freeze({ sequence: ++this.sequence, key: this.key });
  }
  invalidate(): void { this.sequence++; this.key = null; }
  isCurrent(ticket: PreviewRequestTicket, identity?: PreviewSourceIdentity): boolean {
    return ticket.sequence === this.sequence && ticket.key === this.key && (!identity || ticket.key === previewSourceKey(identity));
  }
}

function evidenceCaseId(source: PreviewEvidenceSource): string { return source.schema === 'summary-source-adapter/1' ? source.id : source.caseId; }
function sourceNode(selection: PreviewSelection, source?: PreviewEvidenceSource): PreviewSourceNode | undefined {
  const supplied = selection.node?.semantic ?? selection.node, id = selection.nodeId ?? supplied?.id;
  const canonical = source?.schema === 'summary-source-adapter/1' ? source.ir?.nodes.find(node => node.id === id) : undefined;
  return supplied ? { ...canonical, ...supplied } : canonical;
}
function validLocation(raw: Partial<PreviewEvidence> & { path?: string }, sourcePath?: string): PreviewSourceLocation | null {
  const path = raw.path ?? raw.file ?? sourcePath;
  if (typeof path !== 'string' || !Number.isInteger(raw.line) || raw.line! < 1) return null;
  const endLine = raw.endLine ?? raw.line!;
  if (!Number.isInteger(endLine) || endLine < raw.line!) return null;
  try {
    return { path: pythonPath(path), line: raw.line!, endLine, ...(typeof raw.expression === 'string' ? { expression: raw.expression } : {}),
      ...(Number.isInteger(raw.column) && raw.column! >= 0 ? { column: raw.column } : {}),
      ...(Number.isInteger(raw.endColumn) && raw.endColumn! >= 0 ? { endColumn: raw.endColumn } : {}) };
  } catch { return null; }
}

/** AST columns remain UTF-8 byte offsets; source navigation should use the line number directly. */
function previewSourceLocations(selection: PreviewSelection, bundle?: PreviewEvidenceSource): PreviewSourceLocation[] {
  const locations: PreviewSourceLocation[] = [];
  const direct = selection.span ? validLocation(selection.span, selection.sourcePath) : null;
  if (direct) locations.push(direct);
  if (selection.sourcePath && selection.line) {
    const location = validLocation({ line: selection.line }, selection.sourcePath);
    if (location) locations.push(location);
  }
  const node = sourceNode(selection, bundle);
  for (const id of node?.source_evidence ?? []) {
    const evidence = bundle?.evidence?.[id], location = evidence && validLocation(evidence);
    if (location) locations.push(location);
  }
  // Inspection cards are anchored at constructors; the formal module may be
  // anchored at a call in another method/file. Match the independently rebuilt
  // call evidence too, while keeping construction as the first source location.
  for (const site of node?.sourceParameters?.callSites ?? []) {
    const location = validLocation(site);
    if (location) locations.push(location);
  }
  const raw = selection.evidence;
  const evidence = Array.isArray(raw) ? raw : raw && 'file' in raw ? [raw as PreviewEvidence] : Object.values(raw ?? {});
  for (const item of evidence) { const location = validLocation(item); if (location) locations.push(location); }
  return [...new Map(locations.map(location => [JSON.stringify(location), location])).values()];
}
export function previewSourceLocation(selection: PreviewSelection, bundle?: PreviewEvidenceSource): PreviewSourceLocation | null {
  return previewSourceLocations(selection, bundle)[0] ?? null;
}

const categoryAliases: Record<string, string[]> = { group: ['container'], container: ['container'], normalization: ['norm', 'normalization'], norm: ['norm', 'normalization'], convolution: ['convolution'],
  input: ['input'], output: ['output'], linear: ['linear'], activation: ['activation'], opaque: ['opaque'], literal: ['literal'], add: ['operator', 'residual'] };
const normalizedKind = (value: string | undefined) => (value ?? '').replace(/^torch\.nn\.|^nn\./, '').toLowerCase();
const normalizedInstance = (value: string | undefined) => (value ?? '').replace(/^instance:/, '').replace(':', '.');
function selectionScore(node: ArchitectureNode, raw: PreviewSourceNode | undefined, location: PreviewSourceLocation): number {
  const source = node.source;
  if (!source || source.path.replaceAll('\\', '/') !== location.path || source.endLine < location.line || source.line > location.endLine) return -1;
  let score = source.line === location.line && source.endLine === location.endLine ? 100 : 0;
  if (location.expression && source.expression.trim() === location.expression.trim()) score += 100;
  if (raw?.expression && source.expression.trim() === raw.expression.trim()) score += 80;
  if (raw?.kind) {
    const category = Object.hasOwn(categoryAliases, raw.kind) ? categoryAliases[raw.kind] : undefined;
    if (category) score += category.includes(node.category) ? 120 : -120;
    if (normalizedKind(node.kind) === normalizedKind(raw.moduleType ?? raw.kind)) score += 60;
  }
  // Formal input facts may span the whole method, while preview evidence names
  // one AST argument. Match the declared output port, never a display alias.
  if (raw?.kind === 'input' && node.category === 'input' && node.ports.some(port => port.direction === 'out') && location.expression &&
      /^[_\p{ID_Start}][_\p{ID_Continue}]*$/u.test(location.expression.trim())) {
    const name = location.expression.trim();
    if (!node.ports.some(port => port.direction === 'out' && port.name === name)) return -1;
    score += 200;
  }
  if (raw?.instance && node.instanceId) score += normalizedInstance(raw.instance) === normalizedInstance(node.instanceId) ? 160 : -80;
  if (raw?.sourceStructure && node.sourceStructure && raw.sourceKind === node.kind) score += 160;
  if (node.sourceStructure) score -= 30;
  return score;
}

/** Different parsers have different node IDs. Exact source evidence and instance identity bridge them. */
export function previewSelectionNodeIds(architecture: Architecture, selection: PreviewSelection, bundle?: PreviewEvidenceSource): string[] {
  if (bundle && selection.caseId && selection.caseId !== evidenceCaseId(bundle)) return [];
  const raw = sourceNode(selection, bundle), id = selection.nodeId ?? raw?.id;
  // Certified summaries can aggregate several exact source objects. Their
  // source spans aid inspection and cannot license one formal edit target.
  if (raw?.presentation_only || (raw?.canonical_members?.length ?? 0) > 1) return [];
  if (id && architecture.nodes.some(node => node.id === id)) return [id];
  const locations = previewSourceLocations(selection, bundle);
  if (!locations.length) return [];
  const scores = architecture.nodes.map(node => ({ id: node.id, score: Math.max(...locations.map(location => selectionScore(node, raw, location))) }));
  const best = Math.max(0, ...scores.map(item => item.score));
  const candidates = best ? scores.filter(item => item.score === best).map(item => item.id) : [];
  if (candidates.length && raw?.sourceStructure && bundle?.schema === 'summary-source-adapter/1') {
    // The same constructor can be inspected under mutually exclusive paths.
    // A branch's authored condition and exact source span distinguish these
    // occurrences without selecting a runtime path or comparing display names.
    const previewNodes = new Map(bundle.ir?.nodes.map(node => [node.id, node]) ?? []);
    const facts = new Map(architecture.nodes.map(node => [node.id, node]));
    const signature = (condition: unknown, location: PreviewSourceLocation | null | undefined) =>
      typeof condition === 'string' && location ? JSON.stringify([condition, location.path, location.line, location.endLine, location.expression?.trim()]) : undefined;
    const rawContext: string[] = [], seen = new Set<string>();
    let cursor = id ? previewNodes.get(id) : undefined;
    while (cursor && !seen.has(cursor.id)) {
      seen.add(cursor.id);
      if (cursor.sourceKind === 'SourceBranch') {
        const key = signature(cursor.sourceParameters?.condition, previewSourceLocation({ nodeId: cursor.id, node: cursor }, bundle));
        if (key) rawContext.unshift(key);
      }
      cursor = cursor.parent ? previewNodes.get(cursor.parent) : undefined;
    }
    if (rawContext.length) {
      const contextual = candidates.filter(candidate => {
        const context: string[] = [], visited = new Set<string>();
        let fact = facts.get(candidate);
        // A real formal call can be represented by a syntax inspection card.
        // It carries its own operation identity rather than a branch wrapper.
        if (!fact?.sourceStructure) return true;
        while (fact && !visited.has(fact.id)) {
          visited.add(fact.id);
          if (fact.sourceStructure && fact.kind === 'SourceBranch') {
            const key = signature(fact.parameters.condition, fact.source);
            if (key) context.unshift(key);
          }
          fact = fact.parentId ? facts.get(fact.parentId) : undefined;
        }
        return JSON.stringify(context) === JSON.stringify(rawContext);
      });
      return contextual;
    }
  }
  return candidates;
}

/** Only live draft objects are selected; removed source objects stay in the editor's recovery cache. */
export function previewSelectionDraftIds(draft: AuthoredDraft, selection: PreviewSelection, architecture?: Architecture,
  bundle?: PreviewEvidenceSource, generatedBindings?: Record<string, string>): string[] {
  const actual = architecture ?? draft.sourceProvenance?.architecture;
  if (!actual) return [];
  const canonical = new Set(previewSelectionNodeIds(actual, selection, bundle)), refs = draft.sourceProvenance?.nodeRefs ?? {};
  return draft.nodes.filter(node => canonical.has(refs[node.id]?.nodeId) || canonical.has(refs[node.id]?.sceneNodeId) ||
    (!!generatedBindings?.[node.id] && canonical.has(generatedBindings[node.id]))).map(node => node.id);
}

export function architecturePreviewFocus(architecture: Architecture, nodeId: string): { nodeId: string; sourcePath?: string; line?: number; endLine?: number; expression?: string } | null {
  const node = architecture.nodes.find(item => item.id === nodeId);
  if (!node) return null;
  return { nodeId, ...(node.source ? { sourcePath: node.source.path, line: node.source.line, endLine: node.source.endLine, expression: node.source.expression } : {}) };
}

/** Identity follows the source binding, independent of either editor's visual revisions. */
export function documentPreviewIdentity(document: CanvasDocument): PreviewSourceIdentity {
  if (document.sourceBindingDigest !== document.architecture.sourceDigest) throw new Error('画布源码绑定摘要已改变。');
  return previewSourceIdentity(document.architecture, document.id);
}

export type PreviewVisualNode = PreviewSourceNode & { parent?: string | null; x: number; y: number; w?: number; h?: number; fill?: string; expanded?: boolean; junction?: boolean; semantic?: PreviewSourceNode; semanticRef?: true };
export type PreviewVisualGraph = { nodes: PreviewVisualNode[]; semanticHierarchy?: { nodes: PreviewVisualNode[] }; generic?: { ir?: { nodes: PreviewSourceNode[] } } };

/** Summary publishes its semantic navigation index; this is never a second layout authority. */
export function previewDetailGraph<T extends PreviewVisualGraph>(graph: T): T {
  const recursive = (graph as T & { recursive?: { authority?: { detail?: T } } }).recursive?.authority?.detail;
  if (recursive) return recursive;
  if (!graph.semanticHierarchy) return graph;
  // A native hierarchy row references the same complete IR already carried by
  // this snapshot. Exact ID joins retain source-matching facts without copying
  // large expressions/receipts into a second navigation tree.
  const canonical = new Map((graph.generic?.ir?.nodes ?? []).map(node => [node.id, node]));
  const nodes = graph.semanticHierarchy.nodes.map(node => node.semanticRef === true && canonical.has(node.id) ? { ...node, semantic: canonical.get(node.id) } : node);
  return { ...graph, nodes };
}

/** A reviewed aggregate may share evidence with another display object. Only
 * globally one-to-one identities can carry formal presentation or selection. */
export function previewUniqueNodeBindings(architecture: Architecture, graph: PreviewVisualGraph, source?: PreviewEvidenceSource): Map<string, string> {
  const detail = previewDetailGraph(graph);
  const byCanonical = new Map<string, string[]>();
  const singleton = new Set<string>();
  for (const node of new Map((detail?.nodes ?? graph.nodes).map(node => [node.id, node])).values()) {
    if (node.junction) continue;
    const ids = previewSelectionNodeIds(architecture, { nodeId: node.id, node }, source);
    if (ids.length === 1) singleton.add(node.id);
    for (const id of ids) byCanonical.set(id, [...(byCanonical.get(id) ?? []), node.id]);
  }
  return new Map([...byCanonical].filter(([, ids]) => ids.length === 1 && singleton.has(ids[0])).map(([canonical, ids]) => [ids[0], canonical]));
}

/** Carry visible arrangement and expansion into the model editor without borrowing preview HTML or topology. */
export function previewCanvasOperations(document: CanvasDocument, graph: PreviewVisualGraph, source?: PreviewEvidenceSource,
  bindings = previewUniqueNodeBindings(document.architecture, graph, source)): VisualOperation[] {
  const architecture = document.architecture, canonical = new Map(architecture.nodes.map(node => [node.id, node]));
  const mapped = new Map<string, string>(), positioned = new Map<string, PreviewVisualNode>();
  for (const node of graph.nodes) {
    if (!Number.isFinite(node.x) || !Number.isFinite(node.y) || Math.abs(node.x) > 1_000_000 || Math.abs(node.y) > 1_000_000) continue;
    const id = bindings.get(node.id);
    if (!id || positioned.has(id)) continue;
    mapped.set(node.id, id); positioned.set(id, node);
  }
  const operations: VisualOperation[] = [];
  for (const [id, node] of positioned) {
    const target = canonical.get(id)!;
    if (target.children.length && typeof node.expanded === 'boolean' && document.expandedIds.includes(id) !== node.expanded) {
      operations.push({ type: 'expand', id, expanded: node.expanded });
    }
    const parent = target.parentId ? positioned.get(target.parentId) : undefined;
    // An unmapped parent has an independent formal frame. Keep that frame's
    // layout rather than interpreting a world position as its local offset.
    if (target.parentId && (!parent || !node.parent || mapped.get(node.parent) !== target.parentId)) continue;
    const position = { x: node.x - (parent?.x ?? 0), y: node.y - (parent?.y ?? 0) };
    const before = document.layout[id];
    if (!before || before.x !== position.x || before.y !== position.y) operations.push({ type: 'nodeLayout', id, position });
  }
  return operations;
}

/** A concrete model-editor position is local; the recursive preview gesture uses world coordinates. */
export function previewNodeLayoutOperation(document: CanvasDocument, operation: Extract<VisualOperation, { type: 'nodeLayout' }>,
  graph: PreviewVisualGraph, source?: PreviewEvidenceSource): Extract<VisualOperation, { type: 'nodeLayout' }> {
  const target = document.architecture.nodes.find(node => node.id === operation.id);
  const candidates = graph.nodes.filter(node => previewSelectionNodeIds(document.architecture, { nodeId: node.id, node }, source).includes(operation.id));
  if (!target || candidates.length !== 1) throw new Error('当前位置没有唯一的预览图元绑定。');
  const preview = candidates[0];
  let parent: PreviewVisualNode | undefined;
  if (target.parentId) {
    parent = graph.nodes.find(node => node.id === preview.parent);
    if (!parent || !previewSelectionNodeIds(document.architecture, { nodeId: parent.id, node: parent }, source).includes(target.parentId)) {
      throw new Error('编辑与预览的直接父容器不同；保留当前位置，请在预览中调整。');
    }
  } else if (preview.parent) throw new Error('预览图元具有独立父容器，无法将编辑根坐标应用到该图元。');
  return { ...operation, id: preview.id, position: { ...operation.position, x: operation.position.x + (parent?.x ?? 0), y: operation.position.y + (parent?.y ?? 0) } };
}

/** Replay only known containers; saved coordinates need a separate preview-layout provenance. */
export function previewExpansionOperations(document: CanvasDocument, graph: PreviewVisualGraph, source?: PreviewEvidenceSource): Extract<VisualOperation, { type: 'expand' }>[] {
  const expanded = new Set(document.expandedIds), facts = new Map(document.architecture.nodes.map(node => [node.id, node]));
  const detail = previewDetailGraph(graph);
  const nodes = new Map(detail.nodes.map(node => [node.id, node])), states = new Map<string, boolean>(), requiredAncestors = new Set<string>();
  const visible = (id: string) => {
    let parent = facts.get(id)?.parentId;
    const seen = new Set<string>();
    while (parent && !seen.has(parent)) {
      seen.add(parent);
      if (!expanded.has(parent)) return false;
      parent = facts.get(parent)?.parentId;
    }
    return !parent;
  };
  for (const node of nodes.values()) {
    if (node.junction) continue;
    const ids = previewSelectionNodeIds(document.architecture, { nodeId: node.id, node }, source);
    if (!ids.length) continue;
    // Several syntax wrappers can display one formal region. They may share a
    // collapse choice; they still do not gain a unique geometry/source binding.
    if (ids.every(id => !!facts.get(id)?.children.length) && ids.every(id => expanded.has(id) === expanded.has(ids[0]))) {
      states.set(node.id, expanded.has(ids[0]));
    }
    if (ids.every(visible)) {
      let parent = node.parent;
      const seen = new Set<string>();
      while (parent && nodes.has(parent) && !seen.has(parent)) {
        seen.add(parent); requiredAncestors.add(parent); parent = nodes.get(parent)!.parent;
      }
    }
  }
  // Preview wrappers and formal containers need not share the same hierarchy.
  // Reveal required ancestors after collecting explicit states so node order
  // cannot hide a formally visible descendant again.
  for (const id of requiredAncestors) states.set(id, true);
  return [...states].map(([id, expanded]) => ({ type: 'expand', id, expanded }));
}
