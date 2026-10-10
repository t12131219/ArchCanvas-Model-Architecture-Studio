import { projectSourceEditing } from './sourceEditingProjection.ts';
import type { CanvasDocument } from './core/types.ts';

type ProjectionInput = { document: CanvasDocument; previousEditing?: CanvasDocument; previousView?: CanvasDocument };
const scope = self as unknown as { onmessage: ((event: MessageEvent<ProjectionInput>) => void) | null; postMessage: (value: unknown) => void };
scope.onmessage = event => {
  try { scope.postMessage({ result: projectSourceEditing(event.data.document, event.data.previousEditing, event.data.previousView) }); }
  catch (reason) { scope.postMessage({ error: reason instanceof Error ? reason.message : String(reason) }); }
};
