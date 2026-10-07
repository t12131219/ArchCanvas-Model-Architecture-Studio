import type { CanvasDocument, MoveScope, Scene } from './types.ts';
import { effectiveVisibleFrontier, resolveMoveScope } from './document.ts';
import { buildScene } from './scene.ts';
import { finite, textValue, validateDocument, ValidationError } from './validate.ts';

/** A temporary gesture snapshot. It cannot be committed or added to history. */
export interface MovePreviewSession {
  readonly documentId: string;
  readonly baseRevision: number;
  readonly selectedIds: readonly string[];
  readonly scope: MoveScope;
}
type PreparedMove = { document: CanvasDocument; movingIds: string[] };
const prepared = new WeakMap<MovePreviewSession, PreparedMove>();
function freezeSnapshot(value: unknown): void {
  if (typeof value !== 'object' || value === null || Object.isFrozen(value)) return;
  Object.freeze(value);
  for (const child of Object.values(value)) freezeSnapshot(child);
}

/** Validate and snapshot once, rather than cloning source text every pointer frame. */
export function prepareMovePreview(document: CanvasDocument, ids: readonly string[], scope?: MoveScope): MovePreviewSession {
  validateDocument(document);
  const moveScope = resolveMoveScope(scope);
  if (!Array.isArray(ids)) throw new ValidationError('move.ids: expected array');
  const byId = new Map(document.architecture.nodes.map(node => [node.id, node]));
  const selectedIds = ids.map(id => {
    const key = textValue(id, 'operation.id');
    if (!byId.has(key)) throw new ValidationError(`operation: unknown object ${key}`);
    return key;
  });
  if (moveScope === 'current-frontier') {
    const visibleIds = effectiveVisibleFrontier(document).visibleIds;
    for (const id of selectedIds) if (!visibleIds.has(id)) throw new ValidationError(`move: ${id} is hidden in the current frontier`);
  }
  const moving = new Set(selectedIds), pinnedSubtrees = new Set<string>();
  for (const pin of document.pinnedObjects) {
    let node = byId.get(pin);
    while (node) { pinnedSubtrees.add(node.id); node = node.parentId ? byId.get(node.parentId) : undefined; }
  }
  const snapshot = structuredClone(document);
  // Match move materialization, including restored documents with sparse layout.
  for (const node of buildScene(snapshot).nodes) if (!snapshot.layout[node.id]) snapshot.layout[node.id] = { x: node.localX, y: node.localY };
  const movingIds: string[] = [];
  for (const id of moving) {
    if (pinnedSubtrees.has(id)) continue;
    let parent = byId.get(id)?.parentId, covered = false;
    while (parent) { if (moving.has(parent)) covered = true; parent = byId.get(parent)?.parentId; }
    if (covered) continue;
    if (!snapshot.layout[id]) throw new ValidationError(`move: ${id} is hidden and has no established layout`);
    movingIds.push(id);
  }
  const session = Object.freeze({ documentId: document.id, baseRevision: document.revision, selectedIds: Object.freeze(selectedIds), scope: moveScope });
  freezeSnapshot(snapshot);
  prepared.set(session, { document: snapshot, movingIds });
  return session;
}

/** Render the exact committed move geometry without mutating a document or history. */
export function previewMoveScene(session: MovePreviewSession, dx: number, dy: number): Scene {
  const context = prepared.get(session);
  if (!context) throw new ValidationError('move preview: unknown gesture snapshot');
  finite(dx, 'move.dx'); finite(dy, 'move.dy');
  const base = context.document, layout = { ...base.layout };
  for (const id of context.movingIds) {
    const position = base.layout[id];
    layout[id] = { ...position, x: finite(position.x + dx, 'move.x'), y: finite(position.y + dy, 'move.y') };
  }
  // Stored frontier positions matter on a later expand/collapse, not this scene.
  // The real commit applies the session's scope through the guarded move operation.
  return buildScene({ ...base, layout, revision: base.revision + 1 });
}
