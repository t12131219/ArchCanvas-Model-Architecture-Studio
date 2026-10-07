import type { AuthoredDraft, DraftCatalog, DraftParameter, DraftValue } from './authoring.ts';
import { DRAFT_HEIGHT, DRAFT_WIDTH } from './authoring.ts';
import { ApiError } from './api.ts';

export type DraftCamera = { x: number; y: number; zoom: number };
export type DraftFeedback = { message: string; technical?: string; target?: { nodeId: string; parameter?: string; portId?: string } };

export function parseDraftField(text: string, parameter: DraftParameter): DraftValue | null {
  const tokens = parameter.type === 'integer-array' ? text.split(',') : [text];
  if (tokens.some(token => !token.trim())) return null;
  const values = tokens.map(Number);
  if (values.some(value => !Number.isFinite(value) || ((parameter.type === 'integer' || parameter.type === 'integer-array') && !Number.isInteger(value)) || (parameter.min !== undefined && value < parameter.min) || (parameter.max !== undefined && value > parameter.max))) return null;
  if (parameter.type === 'integer-array' && ((parameter.length !== undefined && values.length !== parameter.length) || (parameter.minLength !== undefined && values.length < parameter.minLength) || (parameter.maxLength !== undefined && values.length > parameter.maxLength))) return null;
  return parameter.type === 'integer-array' ? values : values[0];
}

/** Fit is a view operation; even the widest supported graph must remain visible. */
export function fitDraftCamera(draft: AuthoredDraft, viewport: { width: number; height: number }, routePoints: readonly { x: number; y: number }[] = []): DraftCamera {
  if (!draft.nodes.length || !Number.isFinite(viewport.width) || !Number.isFinite(viewport.height) || viewport.width <= 0 || viewport.height <= 0) return { x: 30, y: 30, zoom: 1 };
  const xs = [...draft.nodes.flatMap(node => [node.position.x, node.position.x + DRAFT_WIDTH]), ...routePoints.map(point => point.x)];
  const ys = [...draft.nodes.flatMap(node => [node.position.y, node.position.y + DRAFT_HEIGHT]), ...routePoints.map(point => point.y)];
  const left = Math.min(...xs) - 32, top = Math.min(...ys) - 32;
  const width = Math.max(...xs) + 32 - left, height = Math.max(...ys) + 32 - top;
  const zoom = Math.min(1, Math.max(1, viewport.width - 30) / width, Math.max(1, viewport.height - 30) / height);
  return { x: (viewport.width - width * zoom) / 2 - left * zoom, y: (viewport.height - height * zoom) / 2 - top * zoom, zoom };
}

/** Localized backend text is display data; only exact registered identities locate objects. */
export function resolveDraftFeedback(reason: unknown, draft: AuthoredDraft, catalog: DraftCatalog | null): DraftFeedback {
  const fallback = reason instanceof Error ? reason.message : String(reason);
  if (!(reason instanceof ApiError) || !Array.isArray(reason.diagnostics)) return { message: fallback };
  const diagnostic = reason.diagnostics.find(item => item && typeof item === 'object' && typeof item.message === 'string' && item.message.trim());
  if (!diagnostic) return { message: fallback };
  const result: DraftFeedback = { message: diagnostic.message };
  if (typeof diagnostic.technical === 'string') result.technical = diagnostic.technical;
  const candidates = draft.nodes.filter(node => node.id === diagnostic.nodeId);
  if (candidates.length !== 1) return result;
  const node = candidates[0], module = catalog?.modules.find(item => item.kind === node.kind);
  if (!module) return result;
  result.target = { nodeId: node.id };
  if (module.parameters.some(item => item.name === diagnostic.parameter)) result.target.parameter = diagnostic.parameter;
  if (module.ports.some(item => item.id === diagnostic.portId)) result.target.portId = diagnostic.portId;
  return result;
}
