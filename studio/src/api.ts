import type { Architecture, CanvasDocument } from './core';

export type Example = { id: string; name: string; description: string };
export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...options?.headers } });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || result.message || `请求失败 (${response.status})`);
  return result as T;
}
export const api = {
  examples: () => request<Example[]>('/examples'),
  example: (id: string) => request<Architecture>(`/examples/${encodeURIComponent(id)}`),
  document: (id: string) => request<{ document: CanvasDocument; revision: number }>(`/documents/${encodeURIComponent(id)}`),
  save: (document: CanvasDocument, expectedRevision: number) => request<{ document: CanvasDocument; revision: number }>(`/documents/${encodeURIComponent(document.id)}`, { method: 'PUT', body: JSON.stringify({ document, expectedRevision }) }),
  analyze: (source: string, entry: string, filename: string) => request<Architecture>('/analyze', { method: 'POST', body: JSON.stringify({ source, entry, filename }) }),
};
