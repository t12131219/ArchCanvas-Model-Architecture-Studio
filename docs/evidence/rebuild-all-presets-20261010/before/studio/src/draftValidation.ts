import type { AuthoredDraft, DraftValue, DraftPresentation, DraftSourceProvenance, SourceDraftCache } from './authoring.ts';
import { readCustomModuleDefinition } from './customModules.ts';

export type DraftTensor = { shape: number[]; dtype: 'float32' | 'float64' | 'int64' };
export type DraftDiagnosticValue = null | boolean | number | string | DraftDiagnosticValue[] | { [key: string]: DraftDiagnosticValue };
export type DraftValidationDiagnostic = {
  code: string; message: string; technical?: string;
  nodeId?: string; nodeIds?: string[]; parameter?: string; portId?: string; portIds?: string[];
  edgeId?: string; endpoint?: 'source' | 'target'; expected?: DraftDiagnosticValue; actual?: DraftDiagnosticValue;
};
export type DraftValidation = {
  draft: AuthoredDraft; draftDigest: string; complete: boolean; issues: DraftValidationDiagnostic[];
  tensors: Record<string, DraftTensor>; order: string[];
  portTensors?: Record<string, Record<string, DraftTensor>>;
  verification: 'static-declared-tensors; no model execution' | 'source-preserved-graph; no model execution' | 'static-topology; custom output shapes unknown; no model execution';
  unknownTensorNodeIds?: string[];
};

const STATIC_VERIFICATION = 'static-declared-tensors; no model execution';
const IDENTITY = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;
function invalid(): never { throw new Error('模型检查响应格式不正确，无法显示已检查的声明形状。'); }
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return invalid();
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) return invalid();
  return value as Record<string, unknown>;
}
function keys(value: Record<string, unknown>, required: string[], optional: string[] = []) {
  if (required.some(key => !Object.hasOwn(value, key)) || Object.keys(value).some(key => !required.includes(key) && !optional.includes(key))) invalid();
}
function identity(value: unknown): string {
  if (typeof value !== 'string' || !IDENTITY.test(value)) return invalid();
  return value;
}
function text(value: unknown, limit = 120): string {
  if (typeof value !== 'string' || !value.length || Array.from(value).length > limit || /[\x00-\x1f]/.test(value)) return invalid();
  return value;
}
function parameter(value: unknown): DraftValue {
  if (typeof value === 'boolean' || typeof value === 'string' || (typeof value === 'number' && Number.isFinite(value))) return value;
  if (Array.isArray(value) && value.every(item => typeof item === 'number' && Number.isFinite(item))) return [...value];
  return invalid();
}
function readDraft(value: unknown): AuthoredDraft {
  const draft = record(value);
  keys(draft, ['schemaVersion', 'mode', 'id', 'title', 'revision', 'nodes', 'edges'], ['sourceProvenance', 'sourceCache', 'customModules']);
  if (draft.schemaVersion !== 1 || draft.mode !== 'authored-draft' || !Number.isSafeInteger(draft.revision) || (draft.revision as number) < 0 || !Array.isArray(draft.nodes) || draft.nodes.length > (draft.sourceProvenance ? 1200 : 128) || !Array.isArray(draft.edges) || draft.edges.length > (draft.sourceProvenance ? 3600 : 384)) invalid();
  const nodeIds = new Set<string>(), edgeIds = new Set<string>();
  const nodes = (draft.nodes as unknown[]).map(value => {
    const node = record(value); keys(node, ['id', 'kind', 'label', 'parameters', 'position'], draft.sourceProvenance ? ['presentation', 'visual', 'portLayouts'] : ['visual', 'portLayouts']);
    const id = identity(node.id); if (nodeIds.has(id)) invalid(); nodeIds.add(id);
    const position = record(node.position); keys(position, ['x', 'y']);
    if (![position.x, position.y].every(item => typeof item === 'number' && Number.isFinite(item) && Math.abs(item) <= 1_000_000)) invalid();
    const parameters = Object.fromEntries(Object.entries(record(node.parameters)).map(([name, value]) => [identity(name), parameter(value)]));
    let presentation: DraftPresentation | undefined;
    if (node.presentation) {
      const p = record(node.presentation); keys(p, ['width', 'height', 'fill', 'stroke', 'group', 'ports'], ['parentId']);
      if (![p.width, p.height].every(item => typeof item === 'number' && Number.isFinite(item) && item >= 10 && item <= 1_000_000) || typeof p.group !== 'boolean') invalid();
      const ports = Object.fromEntries(Object.entries(record(p.ports)).map(([id, item]) => { const point = record(item); keys(point, ['x', 'y']); if (![point.x, point.y].every(n => typeof n === 'number' && Number.isFinite(n))) invalid(); return [identity(id), { x: point.x as number, y: point.y as number }]; }));
      presentation = { width: p.width as number, height: p.height as number, fill: text(p.fill), stroke: text(p.stroke), group: p.group as boolean, ports, ...(p.parentId ? { parentId: identity(p.parentId) } : {}) };
    }
    let visual;
    if (node.visual !== undefined) {
      const p = record(node.visual); keys(p, ['width', 'height', 'fill', 'stroke']);
      if (![p.width, p.height].every(item => typeof item === 'number' && Number.isFinite(item) && item >= 10 && item <= 1000000) || ![p.fill, p.stroke].every(color => typeof color === 'string' && /^#(?:[0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})$/i.test(color))) invalid();
      visual = { width: p.width as number, height: p.height as number, fill: p.fill as string, stroke: p.stroke as string };
    }
    let portLayouts: import('./authoring.ts').DraftNode['portLayouts'];
    if (node.portLayouts !== undefined) portLayouts = Object.fromEntries(Object.entries(record(node.portLayouts)).map(([id, raw]) => {
      identity(id); if (raw === null) return [id, null];
      const layout = record(raw); keys(layout, ['side', 'offset']);
      if (!['top', 'right', 'bottom', 'left'].includes(layout.side as string) || typeof layout.offset !== 'number' || !Number.isFinite(layout.offset) || layout.offset < 0 || layout.offset > 1) invalid();
      return [id, { side: layout.side as import('./core/types.ts').PortLayout['side'], offset: layout.offset }];
    }));
    return { id, kind: text(node.kind), label: text(node.label), parameters, position: { x: position.x as number, y: position.y as number }, ...(presentation ? { presentation } : {}), ...(visual ? { visual } : {}), ...(portLayouts ? { portLayouts } : {}) };
  });
  const edges = (draft.edges as unknown[]).map(value => {
    const edge = record(value); keys(edge, ['id', 'source', 'target']);
    const id = identity(edge.id); if (edgeIds.has(id)) invalid(); edgeIds.add(id);
    const endpoint = (value: unknown) => {
      const end = record(value); keys(end, ['nodeId', 'portId']);
      const nodeId = identity(end.nodeId); if (!nodeIds.has(nodeId)) invalid();
      return { nodeId, portId: identity(end.portId) };
    };
    return { id, source: endpoint(edge.source), target: endpoint(edge.target) };
  });
  let sourceProvenance: DraftSourceProvenance | undefined;
  if (draft.sourceProvenance) {
    const provenance = record(draft.sourceProvenance);
    if (provenance.schemaVersion !== 1 || typeof provenance.digest !== 'string' || !/^[a-f0-9]{64}$/.test(provenance.digest) || !Array.isArray(provenance.modules) || !provenance.architecture || !provenance.canvas || !provenance.originalGraph) invalid();
    record(provenance.nodeRefs); record(provenance.edgeRefs);
    sourceProvenance = structuredClone(provenance) as DraftSourceProvenance;
  }
  const sourceCache = draft.sourceCache ? structuredClone(record(draft.sourceCache)) as SourceDraftCache : undefined;
  const customModules = draft.customModules ? (Array.isArray(draft.customModules) && draft.customModules.length <= 32 ? draft.customModules.map(readCustomModuleDefinition) : invalid()) : undefined;
  return { schemaVersion: 1, mode: 'authored-draft', id: identity(draft.id), title: text(draft.title), revision: draft.revision as number, nodes, edges, ...(sourceProvenance ? { sourceProvenance } : {}), ...(sourceCache ? { sourceCache } : {}), ...(customModules ? { customModules } : {}) };
}
function jsonValue(value: unknown, depth = 0): DraftDiagnosticValue {
  if (depth > 8) return invalid();
  if (value === null || typeof value === 'boolean' || typeof value === 'string' || (typeof value === 'number' && Number.isFinite(value))) return value;
  if (Array.isArray(value)) return value.map(item => jsonValue(item, depth + 1));
  return Object.fromEntries(Object.entries(record(value)).map(([key, item]) => [key, jsonValue(item, depth + 1)]));
}
function readDiagnostic(value: unknown): DraftValidationDiagnostic {
  const diagnostic = record(value);
  keys(diagnostic, ['code', 'message'], ['technical', 'nodeId', 'nodeIds', 'parameter', 'portId', 'portIds', 'edgeId', 'endpoint', 'expected', 'actual']);
  const result: DraftValidationDiagnostic = { code: identity(diagnostic.code), message: text(diagnostic.message, 4_096) };
  if (Object.hasOwn(diagnostic, 'technical')) result.technical = text(diagnostic.technical, 4_096);
  for (const key of ['nodeId', 'parameter', 'portId', 'edgeId'] as const) if (Object.hasOwn(diagnostic, key)) result[key] = identity(diagnostic[key]);
  for (const key of ['nodeIds', 'portIds'] as const) {
    if (!Object.hasOwn(diagnostic, key)) continue;
    if (!Array.isArray(diagnostic[key]) || !diagnostic[key].length || diagnostic[key].length > 128) invalid();
    const ids = (diagnostic[key] as unknown[]).map(identity); if (new Set(ids).size !== ids.length) invalid(); result[key] = ids;
  }
  if (Object.hasOwn(diagnostic, 'endpoint')) {
    if (diagnostic.endpoint !== 'source' && diagnostic.endpoint !== 'target') invalid(); result.endpoint = diagnostic.endpoint;
  }
  for (const key of ['expected', 'actual'] as const) if (Object.hasOwn(diagnostic, key)) result[key] = jsonValue(diagnostic[key]);
  return result;
}
function readTensor(value: unknown): DraftTensor {
  const tensor = record(value); keys(tensor, ['shape', 'dtype']);
  if (!Array.isArray(tensor.shape) || tensor.shape.length < 1 || tensor.shape.length > 8 || !tensor.shape.every(item => typeof item === 'number' && Number.isSafeInteger(item) && item > 0) || tensor.shape.reduce((size, item) => size * item, 1) > 1_000_000_000 || !['float32', 'float64', 'int64'].includes(tensor.dtype as string)) invalid();
  return { shape: [...tensor.shape as number[]], dtype: tensor.dtype as DraftTensor['dtype'] };
}

/** Read only the backend's static-declaration response, never execution/generated-source receipts. */
export function readDraftValidation(value: unknown): DraftValidation {
  const result = record(value);
  keys(result, ['draft', 'draftDigest', 'complete', 'issues', 'tensors', 'order', 'verification'], ['portTensors', 'unknownTensorNodeIds']);
  if (![STATIC_VERIFICATION, 'source-preserved-graph; no model execution', 'static-topology; custom output shapes unknown; no model execution'].includes(result.verification as string) || typeof result.draftDigest !== 'string' || !/^[a-f0-9]{64}$/.test(result.draftDigest) || typeof result.complete !== 'boolean' || !Array.isArray(result.issues) || result.issues.length > 3600 || !Array.isArray(result.order)) invalid();
  const draft = readDraft(result.draft), nodeIds = new Set(draft.nodes.map(node => node.id)), edgeIds = new Set(draft.edges.map(edge => edge.id));
  const issues = (result.issues as unknown[]).map(readDiagnostic), order = (result.order as unknown[]).map(identity);
  if (result.complete !== (issues.length === 0) || order.length !== nodeIds.size || new Set(order).size !== order.length || order.some(id => !nodeIds.has(id))) invalid();
  const rank = new Map(order.map((id, index) => [id, index]));
  if (draft.edges.some(edge => rank.get(edge.source.nodeId)! >= rank.get(edge.target.nodeId)!)) invalid();
  for (const issue of issues) {
    if ((issue.nodeId && !nodeIds.has(issue.nodeId)) || issue.nodeIds?.some(id => !nodeIds.has(id)) || (issue.edgeId && !edgeIds.has(issue.edgeId))) invalid();
  }
  const tensors = Object.fromEntries(Object.entries(record(result.tensors)).map(([id, tensor]) => {
    if (!nodeIds.has(id)) invalid(); return [id, readTensor(tensor)];
  }));
  const portTensors = result.portTensors ? Object.fromEntries(Object.entries(record(result.portTensors)).map(([id, ports]) => {
    if (!nodeIds.has(id)) invalid(); return [id, Object.fromEntries(Object.entries(record(ports)).map(([portId, tensor]) => [identity(portId), readTensor(tensor)]))];
  })) : undefined;
  if (!draft.sourceProvenance && !draft.customModules?.length && result.complete && (Object.keys(tensors).length !== nodeIds.size || !draft.nodes.some(node => node.kind === 'Input') || !draft.nodes.some(node => node.kind === 'Output'))) invalid();
  if (draft.customModules?.length ? result.verification !== 'static-topology; custom output shapes unknown; no model execution' : !!draft.sourceProvenance !== (result.verification === 'source-preserved-graph; no model execution')) invalid();
  const unknownTensorNodeIds = result.unknownTensorNodeIds ? (Array.isArray(result.unknownTensorNodeIds) ? result.unknownTensorNodeIds.map(identity) : invalid()) : undefined;
  if (unknownTensorNodeIds?.some(id => !nodeIds.has(id) || tensors[id])) invalid();
  return { draft, draftDigest: result.draftDigest as string, complete: result.complete as boolean, issues, tensors, order, verification: result.verification as DraftValidation['verification'], ...(portTensors ? { portTensors } : {}), ...(unknownTensorNodeIds ? { unknownTensorNodeIds } : {}) };
}

/** Arrays preserve the server's stable graph/forward ordering; parameter object order has no meaning. */
export function draftValidationKey(draft: AuthoredDraft): string {
  return JSON.stringify({ ...(draft.customModules ? { customModules: draft.customModules } : {}), schemaVersion: draft.schemaVersion, mode: draft.mode, id: draft.id, ...(draft.sourceProvenance ? { provenance: draft.sourceProvenance.digest } : {}),
    nodes: draft.nodes.map(node => ({ id: node.id, kind: node.kind,
      parameters: Object.fromEntries(Object.entries(node.parameters).sort(([a], [b]) => a === b ? 0 : a < b ? -1 : 1).map(([name, value]) => [name, parameter(value)])) })),
    edges: draft.edges.map(edge => ({ id: edge.id, source: { nodeId: edge.source.nodeId, portId: edge.source.portId }, target: { nodeId: edge.target.nodeId, portId: edge.target.portId } })) });
}

/** Call with tensors from readDraftValidation; declarations are not runtime observations. */
export function draftTensorLabel(tensor: DraftTensor): string {
  const validated = readTensor(tensor);
  return `声明 ${validated.dtype} · ${validated.shape.join('×')}`;
}
