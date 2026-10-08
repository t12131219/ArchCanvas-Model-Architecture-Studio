import type { Architecture, CanvasDocument, ParameterOrigin, Scene } from './core';
import type { AuthoredDraft, DraftCatalog } from './authoring';
import type { CustomModulePreview } from './customModules';

export type GeneratedDraft = { draft: AuthoredDraft; presentationDraft?: AuthoredDraft; draftDigest: string; source: string; entry: string; architecture: Architecture; nodeBindings: Record<string, string>; containerBindings?: Record<string, string>; edgeBindings?: Record<string, string[]>; verification: Record<string, unknown> };
export type ImportedSourceDraft = { draft: AuthoredDraft; sourceNodeBindings: Record<string, string>; sceneNodeBindings: Record<string, string>; provenanceDigest: string; verification: string };

export type Capabilities = { semanticWriteback: boolean; supportedIntents: string[]; publicationExport: { svg: boolean; pdf: boolean; png: boolean; unavailableReason?: string } };
export type ManagedProject = { id: string; entry: string; scope: 'managed-copy'; architecture: Architecture; sourceDigest: string; irDigest: string };
export type Binding = { nodeId: string; portId: string; tensorId: string; variable?: string };
export type InputSpec = { schemaVersion: 1; inputs: Record<string, { shape: number[]; dtype: string }>; seed: number; modes: ('eval' | 'train')[]; constructor?: Record<string, unknown> };
export type SourceSpan = Omit<ParameterOrigin, 'kind'>;
export type SymbolicContract = { baseTensorId: string; shape: { kind: 'symbol'; identity: string }; dtype: { kind: 'symbol'; identity: string }; runtimeVerified: false; conditional: true; condition: string; basis: string };
export type ConcreteContract = { shape: number[]; dtype: string; inputSpecDigest?: string; runtimeVerified: false; runtimeRequired: true; condition?: string; basis?: string };
export type RebindOptions = {
  schemaVersion: 1; status: 'supported' | 'unsupported'; supported: boolean; sourceDigest: string; irDigest: string;
  target: { nodeId: string; portId: string; slot: SourceSpan & { variable: string }; currentBinding: Binding } | null;
  candidates: { variable: string; binding: Binding; definition: SourceSpan; contract: SymbolicContract | ConcreteContract }[]; blockers: string[];
};
export type ParameterIntent = { kind?: 'SetParameter'; nodeId: string; parameter: string; before?: number; after: number; scope?: string; origin?: ParameterOrigin };
export type ConfigurationIntent = Omit<ParameterIntent, 'kind'> & { kind: 'UpdateConfiguration'; configurationName: string };
export type ActivationIntent = { kind: 'ReplaceActivation'; nodeId: string; before: string; after: string; scope: string; origin: SourceSpan };
export type ConfigurationOptions = { supported: boolean; target: { name: string; before: number; origin: SourceSpan } | null; affectedNodeIds: string[]; blockers: string[] };
export type RebindIntent = { kind: 'RebindInput'; nodeId: string; portId: string; before?: Binding; after?: Binding; scope?: string; origin?: SourceSpan; contract?: SymbolicContract | ConcreteContract };
export type Transaction = {
  id: string; status: string; reviewDigest: string | null; approvalId?: string;
  sourceDigest: string; irDigest: string | null; diff: string; affectedNodeIds: string[];
  intent: ParameterIntent | RebindIntent | ConfigurationIntent | ActivationIntent;
  gates: { id: string; label: string; status: string; message: string }[]; blockers: string[];
  beforeArchitecture: Architecture | null; afterArchitecture: Architecture | null; committedArchitecture?: Architecture;
  checkpointImpact: { status: string; message: string };
  runtimeVerification?: { status: string; runtimeVerified: boolean; reason?: string; profile: string; manifest?: { inputSpec: InputSpec; environment: Record<string, unknown>; isolation?: { available: boolean; checks?: Record<string, boolean>; mechanism?: string }; limits: Record<string, unknown> }; observation?: { modes: { mode: string; finite: boolean; calls: unknown[]; outputs: unknown; replay: Record<string, unknown>; gradients: { status: string; finite: boolean }; state: unknown }[] }; stateCompatibility?: Record<string, unknown>; limitations?: string[] };
};
export type ExportArtifact = { id: string; format: string; url: string; receiptUrl: string; receipt: Record<string, unknown> };
export type RuntimeJob = { id: string; projectId: string; status: 'running' | 'complete' | 'failed'; transaction?: Transaction; error?: string };
let session: Promise<string> | null = null;
async function mutation<T>(path: string, payload: unknown): Promise<T> {
  session ??= request<{ token: string }>('/session').then(result => result.token).catch(error => { session = null; throw error; });
  const token = await session;
  try { return await request<T>(path, { method: 'POST', headers: { 'X-ArchCanvas-Session': token }, body: JSON.stringify(payload) }); }
  catch (error) { session = null; throw error; }
}
async function runtimePreview(project: string, action: string, payload: unknown, onStart: (cancel: () => Promise<void>) => void): Promise<Transaction> {
  const job = await mutation<RuntimeJob>(`/projects/${encodeURIComponent(project)}/${action}-jobs`, payload);
  onStart(async () => { await mutation(`/projects/${encodeURIComponent(project)}/runtime-jobs/${job.id}/cancel`, {}); });
  let state = job;
  while (state.status === 'running') {
    await new Promise(resolve => setTimeout(resolve, 400));
    const token = await session!;
    state = await request<RuntimeJob>(`/projects/${encodeURIComponent(project)}/runtime-jobs/${job.id}`, { headers: { 'X-ArchCanvas-Session': token } });
  }
  if (!state.transaction) throw new Error(state.error ?? '运行预览没有生成事务');
  return state.transaction;
}

export type Example = { id: string; name: string; description: string };
export class ApiError extends Error {
  readonly status: number;
  readonly diagnostics?: unknown;
  constructor(message: string, status: number, diagnostics?: unknown) { super(message); this.name = 'ApiError'; this.status = status; this.diagnostics = diagnostics; }
}
export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...options?.headers } });
  const result = await response.json();
  if (!response.ok) throw new ApiError(result.error || result.message || `请求失败 (${response.status})`, response.status, result.diagnostics);
  return result as T;
}
export const api = {
  previewCustomModule: (value: { source: string; entry: string; label: string; constructorValues: Record<string, unknown> }) => mutation<CustomModulePreview>('/authoring/custom-modules/preview', value),
  importSourceDraft: (document: CanvasDocument, scene: Scene) => mutation<ImportedSourceDraft>('/authoring/import-source', { document, scene }),
  sourceDraftFrontier: (draft: AuthoredDraft, document: CanvasDocument, scene: Scene) => mutation<ImportedSourceDraft>('/authoring/source-frontier', { draft, document, scene }),
  authoringCatalog: () => request<DraftCatalog>('/authoring/catalog'),
  draft: (id: string) => request<{ draft: AuthoredDraft; revision: number }>(`/authoring/drafts/${encodeURIComponent(id)}`),
  saveDraft: (draft: AuthoredDraft, expectedRevision: number) => mutation<{ draft: AuthoredDraft; revision: number }>(`/authoring/drafts/${encodeURIComponent(draft.id)}`, { draft, expectedRevision }),
  validateDraft: (draft: AuthoredDraft) => mutation<Record<string, unknown>>('/authoring/validate', { draft }),
  generateDraft: (draft: AuthoredDraft) => mutation<GeneratedDraft>('/authoring/generate', { draft }),
  capabilities: () => request<Capabilities>('/capabilities'),
  examples: () => request<Example[]>('/examples'),
  example: (id: string) => request<Architecture>(`/examples/${encodeURIComponent(id)}`),
  document: (id: string) => request<{ document: CanvasDocument; revision: number }>(`/documents/${encodeURIComponent(id)}`),
  save: (document: CanvasDocument, expectedRevision: number) => request<{ document: CanvasDocument; revision: number }>(`/documents/${encodeURIComponent(document.id)}`, { method: 'PUT', body: JSON.stringify({ document, expectedRevision }) }),
  analyze: (source: string, entry: string, filename: string) => request<Architecture>('/analyze', { method: 'POST', body: JSON.stringify({ source, entry, filename }) }),
  register: (architecture: Architecture) => mutation<ManagedProject>('/projects', { entry: architecture.entry, sources: architecture.sources, sourceDigest: architecture.sourceDigest, irDigest: architecture.irDigest }),
  project: (id: string) => request<ManagedProject>(`/projects/${encodeURIComponent(id)}`),
  prepare: (project: string, architecture: Architecture, nodeId: string, parameter: string, value: number) => mutation<Transaction>(`/projects/${encodeURIComponent(project)}/transactions`, { nodeId, parameter, value, baseSourceDigest: architecture.sourceDigest, baseIrDigest: architecture.irDigest }),
  configurationOptions: (project: string, architecture: Architecture, nodeId: string, parameter: string) => mutation<ConfigurationOptions>(`/projects/${encodeURIComponent(project)}/configuration-options`, { nodeId, parameter, baseSourceDigest: architecture.sourceDigest, baseIrDigest: architecture.irDigest }),
  prepareConfiguration: (project: string, architecture: Architecture, nodeId: string, parameter: string, value: number) => mutation<Transaction>(`/projects/${encodeURIComponent(project)}/configuration`, { nodeId, parameter, value, baseSourceDigest: architecture.sourceDigest, baseIrDigest: architecture.irDigest }),
  rebindOptions: (project: string, architecture: Architecture, nodeId: string, portId: string) => mutation<RebindOptions>(`/projects/${encodeURIComponent(project)}/rebind-options`, { nodeId, portId, baseSourceDigest: architecture.sourceDigest, baseIrDigest: architecture.irDigest }),
  prepareRebind: (project: string, architecture: Architecture, nodeId: string, portId: string, producer: Binding) => mutation<Transaction>(`/projects/${encodeURIComponent(project)}/rebind`, { nodeId, portId, producerNodeId: producer.nodeId, producerPortId: producer.portId, baseSourceDigest: architecture.sourceDigest, baseIrDigest: architecture.irDigest }),
  structuralRebindOptions: (project: string, architecture: Architecture, nodeId: string, portId: string, inputSpec: InputSpec) => mutation<RebindOptions>(`/projects/${encodeURIComponent(project)}/structural-rebind-options`, { nodeId, portId, inputSpec, baseSourceDigest: architecture.sourceDigest, baseIrDigest: architecture.irDigest }),
  prepareStructuralRebind: (project: string, architecture: Architecture, nodeId: string, portId: string, producer: Binding, inputSpec: InputSpec, onStart: (cancel: () => Promise<void>) => void) => runtimePreview(project, 'structural-rebind', { nodeId, portId, producerNodeId: producer.nodeId, producerPortId: producer.portId, inputSpec, baseSourceDigest: architecture.sourceDigest, baseIrDigest: architecture.irDigest }, onStart),
  prepareActivation: (project: string, architecture: Architecture, nodeId: string, activation: string, inputSpec: InputSpec, onStart: (cancel: () => Promise<void>) => void) => runtimePreview(project, 'activation', { nodeId, activation, inputSpec, baseSourceDigest: architecture.sourceDigest, baseIrDigest: architecture.irDigest }, onStart),
  transaction: (project: string, id: string) => request<Transaction>(`/projects/${encodeURIComponent(project)}/transactions/${encodeURIComponent(id)}`),
  approve: (project: string, transaction: Transaction) => mutation<Transaction>(`/projects/${encodeURIComponent(project)}/transactions/${transaction.id}/approve`, { reviewDigest: transaction.reviewDigest }),
  commit: (project: string, transaction: Transaction) => mutation<Transaction>(`/projects/${encodeURIComponent(project)}/transactions/${transaction.id}/commit`, { approvalId: transaction.approvalId }),
  discard: (project: string, id: string) => mutation<Transaction>(`/projects/${encodeURIComponent(project)}/transactions/${id}/discard`, {}),
  export: (document: CanvasDocument, format: string, dpi: number, options?: { nodeId?: string; widthMm?: number }) => mutation<ExportArtifact>('/exports', { document, format, dpi, ...(options ? { options } : {}) }),
};
