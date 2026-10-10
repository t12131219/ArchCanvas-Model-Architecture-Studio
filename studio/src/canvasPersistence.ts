import type { CanvasDocument, HistoryState } from './core/types.ts';
/** The current document binds one immutable architecture for every snapshot.
 * Only equal architectures are replaced; a changed fact remains rejectable. */
export function canvasSavePayload(document: CanvasDocument, expectedRevision: number, history?: HistoryState) {
  const architecture = JSON.stringify(document.architecture);
  const snapshot = (value: CanvasDocument) => JSON.stringify(value.architecture) === architecture ?
    { ...value, architecture: { archcanvasSharedArchitecture: 1 } } : value;
  return { document, expectedRevision, ...(history ? { history: {
    document: snapshot(history.document), past: history.past.map(snapshot), future: history.future.map(snapshot) } } : {}) };
}
