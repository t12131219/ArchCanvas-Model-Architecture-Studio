import type { Architecture, CanvasDocument, ParameterOrigin } from './core';

export type Capabilities = { semanticWriteback: boolean; supportedIntents: string[]; publicationExport: { svg: boolean; pdf: boolean; png: boolean; unavailableReason?: string } };
export type ManagedProject = { id: string; entry: string; scope: 'managed-copy'; architecture: Architecture; sourceDigest: string; irDigest: string };
export type Binding = { nodeId: string; portId: string; tensorId: string; variable?: string };
export type SourceSpan = Omit<ParameterOrigin, 'kind'>;
export type SymbolicContract = { baseTensorId: string; shape: { kind: 'symbol'; identity: string }; dtype: { kind: 'symbol'; identity: string }; runtimeVerified: false; conditional: true; condition: string; basis: string };
export type RebindOptions = {
  schemaVersion: 1; status: 'supported' | 'unsupported'; supported: boolean; sourceDigest: string; irDigest: string;
  target: { nodeId: string; portId: string; slot: SourceSpan & { variable: string }; currentBinding: Binding } | null;
  candidates: { variable: string; binding: Binding; definition: SourceSpan; contract: SymbolicContract }[]; blockers: string[];
};
export type ParameterIntent = { kind?: 'SetParameter'; nodeId: string; parameter: string; before?: number; after: number; scope?: string; origin?: ParameterOrigin };
export type RebindIntent = { kind: 'RebindInput'; nodeId: string; portId: string; before?: Binding; after?: Binding; scope?: string; origin?: SourceSpan; contract?: SymbolicContract };
export type Transaction = {
  id: string; status: string; reviewDigest: string | null; approvalId?: string;
  sourceDigest: string; irDigest: string | null; diff: string; affectedNodeIds: string[];
  intent: ParameterIntent | RebindIntent;
  gates: { id: string; label: string; status: string; message: string }[]; blockers: string[];
  beforeArchitecture: Architecture | null; afterArchitecture: Architecture | null; committedArchitecture?: Architecture;
  checkpointImpact: { status: string; message: string };
};
export type ExportArtifact = { id: string; format: string; url: string; receiptUrl: string; receipt: Record<string, unknown> };
let session: Promise<string> | null = null;
async function mutation<T>(path: string, payload: unknown): Promise<T> {
  session ??= request<{ token: string }>('/session').then(result => result.token).catch(error => { session = null; throw error; });
  const token = await session;
  try { return await request<T>(path, { method: 'POST', headers: { 'X-ArchCanvas-Session': token }, body: JSON.stringify(payload) }); }
  catch (error) { session = null; throw error; }
}

export type Example = { id: string; name: string; description: string };
export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...options?.headers } });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || result.message || `请求失败 (${response.status})`);
  return result as T;
}
export const api = {
  capabilities: () => request<Capabilities>('/capabilities'),
  examples: () => request<Example[]>('/examples'),
  example: (id: string) => request<Architecture>(`/examples/${encodeURIComponent(id)}`),
  document: (id: string) => request<{ document: CanvasDocument; revision: number }>(`/documents/${encodeURIComponent(id)}`),
  save: (document: CanvasDocument, expectedRevision: number) => request<{ document: CanvasDocument; revision: number }>(`/documents/${encodeURIComponent(document.id)}`, { method: 'PUT', body: JSON.stringify({ document, expectedRevision }) }),
  analyze: (source: string, entry: string, filename: string) => request<Architecture>('/analyze', { method: 'POST', body: JSON.stringify({ source, entry, filename }) }),
  register: (architecture: Architecture) => mutation<ManagedProject>('/projects', { entry: architecture.entry, sources: architecture.sources, sourceDigest: architecture.sourceDigest, irDigest: architecture.irDigest }),
  project: (id: string) => request<ManagedProject>(`/projects/${encodeURIComponent(id)}`),
  prepare: (project: string, architecture: Architecture, nodeId: string, parameter: string, value: number) => mutation<Transaction>(`/projects/${encodeURIComponent(project)}/transactions`, { nodeId, parameter, value, baseSourceDigest: architecture.sourceDigest, baseIrDigest: architecture.irDigest }),
  rebindOptions: (project: string, architecture: Architecture, nodeId: string, portId: string) => mutation<RebindOptions>(`/projects/${encodeURIComponent(project)}/rebind-options`, { nodeId, portId, baseSourceDigest: architecture.sourceDigest, baseIrDigest: architecture.irDigest }),
  prepareRebind: (project: string, architecture: Architecture, nodeId: string, portId: string, producer: Binding) => mutation<Transaction>(`/projects/${encodeURIComponent(project)}/rebind`, { nodeId, portId, producerNodeId: producer.nodeId, producerPortId: producer.portId, baseSourceDigest: architecture.sourceDigest, baseIrDigest: architecture.irDigest }),
  transaction: (project: string, id: string) => request<Transaction>(`/projects/${encodeURIComponent(project)}/transactions/${encodeURIComponent(id)}`),
  approve: (project: string, transaction: Transaction) => mutation<Transaction>(`/projects/${encodeURIComponent(project)}/transactions/${transaction.id}/approve`, { reviewDigest: transaction.reviewDigest }),
  commit: (project: string, transaction: Transaction) => mutation<Transaction>(`/projects/${encodeURIComponent(project)}/transactions/${transaction.id}/commit`, { approvalId: transaction.approvalId }),
  discard: (project: string, id: string) => mutation<Transaction>(`/projects/${encodeURIComponent(project)}/transactions/${id}/discard`, {}),
  export: (document: CanvasDocument, format: string, dpi: number) => mutation<ExportArtifact>('/exports', { document, format, dpi }),
};
