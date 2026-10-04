import type { Architecture, CanvasDocument, HistoryAction, HistoryState, Position, VisualOperation } from './types.ts';
import { CATEGORY_STYLES } from './tokens.ts';
import { buildScene } from './scene.ts';
import { fields, finite, object, textValue, validateArchitecture, validateDocument, ValidationError } from './validate.ts';

const clone = <T>(v: T): T => structuredClone(v);
const frontierKey = (d: CanvasDocument) => [...d.expandedIds].sort().join('|');

export class RevisionConflict extends Error {
  expected: number;
  actual: number;
  constructor(expected: number, actual: number) { super(`Revision conflict: expected ${expected}, current ${actual}`); this.name = 'RevisionConflict'; this.expected = expected; this.actual = actual; }
}

export function createDocument(architecture: Architecture, title = architecture.label): CanvasDocument {
  validateArchitecture(architecture);
  const roots = architecture.nodes.filter(n => !n.parentId);
  const categories = [...new Set(architecture.nodes.map(n => n.category))].filter(c => CATEGORY_STYLES[c]);
  const document: CanvasDocument = {
    // Include the frozen source digest so two revisions of a same-named entry
    // cannot collide in the CAS document store. The digest is already part of
    // the document binding, but making it part of the identity also lets a
    // newly imported source save as a fresh document instead of conflicting
    // with a stale canvas from an older source snapshot.
    schemaVersion: 1, id: `canvas-${architecture.id.replace(/[^A-Za-z0-9_.-]/g, '-').slice(0, 72)}-${architecture.sourceDigest.slice(0, 12)}-${architecture.irDigest.slice(0, 8)}`, title, revision: 0, sourceBindingDigest: architecture.sourceDigest, architecture: clone(architecture),
    displayAliases: {}, nodeStyleOverrides: {}, edgeStyleOverrides: {},
    legendItems: categories.slice(0, 6).map(c => ({ id: `legend:${c}`, label: c[0].toUpperCase() + c.slice(1), color: CATEGORY_STYLES[c].fill, glyph: CATEGORY_STYLES[c].glyph })),
    annotations: [], pageSpec: { widthMm: 180, background: '#ffffff', preset: 'paper' },
    expandedIds: roots.length === 1 && roots[0].children.length ? [roots[0].id] : [],
    layout: {}, layoutByFrontier: {}, pinnedObjects: [],
  };
  materialize(document);
  return document;
}

function materialize(document: CanvasDocument) {
  for (const node of buildScene(document).nodes) if (!document.layout[node.id]) document.layout[node.id] = { x: node.localX, y: node.localY };
}
function subtreePinned(document: CanvasDocument, id: string): boolean {
  const byId = new Map(document.architecture.nodes.map(n => [n.id, n]));
  return document.pinnedObjects.some(pin => { let n = byId.get(pin); while (n) { if (n.id === id) return true; n = n.parentId ? byId.get(n.parentId) : undefined; } return false; });
}
function expand(document: CanvasDocument, id: string, expanded: boolean) {
  const canonical = document.architecture.nodes.find(n => n.id === id)!;
  if (!canonical.children.length) throw new ValidationError(`${id}: no recovered children to expand`);
  const before = buildScene(document), operated = before.nodes.find(n => n.id === id);
  document.layoutByFrontier[frontierKey(document)] = clone(document.layout);
  const ids = new Set(document.expandedIds);
  if (expanded) ids.add(id); else ids.delete(id);
  document.expandedIds = [...ids];
  // Restore frontier geometry, including neighbor displacement. A direct user move updates
  // every stored frontier below, so a subsequent toggle cannot undo deliberate placement.
  const saved = document.layoutByFrontier[frontierKey(document)];
  if (saved) for (const [key, position] of Object.entries(saved)) if (key !== id && !subtreePinned(document, key)) document.layout[key] = clone(position);
  materialize(document);
  if (!operated || !expanded || saved) return;
  const after = buildScene(document), afterById = new Map(after.nodes.map(n => [n.id, n]));
  // A descendant expansion also grows its containing ancestors. Repair siblings at
  // each affected containment level without moving the operated node or its ancestry.
  for (const previous of [...before.nodes].reverse()) {
    const grown = afterById.get(previous.id)!;
    const dx = grown.width - previous.width, dy = grown.height - previous.height;
    if (dx <= 0 && dy <= 0) continue;
    for (const n of before.nodes) {
      if (n.id === previous.id || n.parentId !== previous.parentId || subtreePinned(document, n.id)) continue;
      const p = document.layout[n.id];
      if (dx > 0 && n.x >= previous.x + previous.width && n.y < grown.y + grown.height && n.y + n.height > grown.y) p.x += dx;
      else if (dy > 0 && n.y >= previous.y + previous.height && n.x < grown.x + grown.width && n.x + n.width > grown.x) p.y += dy;
    }
  }
}

/** A batch validates entirely before returning; no intermediate mutation reaches the caller. */
export function applyVisualBatch(document: CanvasDocument, operations: VisualOperation[], baseRevision = document.revision): CanvasDocument {
  if (baseRevision !== document.revision) throw new RevisionConflict(baseRevision, document.revision);
  validateDocument(document);
  if (!Array.isArray(operations)) throw new ValidationError('operations: expected array');
  if (!operations.length) return document;
  const next = clone(document), ids = new Set(next.architecture.nodes.map(n => n.id)), edgeIds = new Set(next.architecture.edges.map(e => e.id));
  const target = (id: unknown, allowed = ids) => { const key = textValue(id, 'operation.id'); if (!allowed.has(key)) throw new ValidationError(`operation: unknown object ${key}`); return key; };
  for (const raw of operations) {
    const op = object(raw, 'operation');
    switch (op.type) {
      case 'alias': fields(op, ['type', 'id', 'label'], 'operation'); next.displayAliases[target(op.id)] = textValue(op.label, 'alias.label'); break;
      case 'nodeStyle': { fields(op, ['type', 'id', 'style'], 'operation'); const id = target(op.id); next.nodeStyleOverrides[id] = { ...next.nodeStyleOverrides[id], ...object(op.style, 'nodeStyle') }; break; }
      case 'edgeStyle': { fields(op, ['type', 'id', 'style'], 'operation'); const id = target(op.id, edgeIds); next.edgeStyleOverrides[id] = { ...next.edgeStyleOverrides[id], ...object(op.style, 'edgeStyle') }; break; }
      case 'move': {
        fields(op, ['type', 'ids', 'dx', 'dy'], 'operation'); if (!Array.isArray(op.ids)) throw new ValidationError('move.ids: expected array');
        const dx = finite(op.dx, 'move.dx'), dy = finite(op.dy, 'move.dy'), moving = new Set(op.ids.map(id => target(id)));
        materialize(next);
        for (const id of moving) {
          if (subtreePinned(next, id)) continue;
          // Moving a selected parent already moves its descendants through local coordinates.
          let parent = next.architecture.nodes.find(n => n.id === id)?.parentId, covered = false;
          while (parent) { if (moving.has(parent)) covered = true; parent = next.architecture.nodes.find(n => n.id === parent)?.parentId; }
          if (!covered) {
            const p = next.layout[id]; if (!p) throw new ValidationError(`move: ${id} is hidden and has no established layout`); p.x += dx; p.y += dy;
            for (const snapshot of Object.values(next.layoutByFrontier)) if (snapshot[id]) { snapshot[id].x += dx; snapshot[id].y += dy; }
          }
        }
        break;
      }
      case 'expand': fields(op, ['type', 'id', 'expanded'], 'operation'); if (typeof op.expanded !== 'boolean') throw new ValidationError('expand.expanded: expected boolean'); expand(next, target(op.id), op.expanded); break;
      case 'legend': fields(op, ['type', 'items'], 'operation'); next.legendItems = clone(op.items) as CanvasDocument['legendItems']; break;
      case 'annotation': { fields(op, ['type', 'annotation'], 'operation'); const annotation = clone(object(op.annotation, 'annotation')) as unknown as CanvasDocument['annotations'][number]; next.annotations = next.annotations.filter(a => a.id !== annotation.id); next.annotations.push(annotation); break; }
      case 'removeAnnotation': fields(op, ['type', 'id'], 'operation'); next.annotations = next.annotations.filter(a => a.id !== textValue(op.id, 'annotation.id')); break;
      case 'page': fields(op, ['type', 'page'], 'operation'); next.pageSpec = { ...next.pageSpec, ...object(op.page, 'page') }; break;
      case 'pin': {
        fields(op, ['type', 'ids', 'pinned'], 'operation'); if (!Array.isArray(op.ids) || typeof op.pinned !== 'boolean') throw new ValidationError('pin: ids and pinned required');
        const pinned = new Set(next.pinnedObjects); for (const id of op.ids) { const key = target(id); if (op.pinned) pinned.add(key); else pinned.delete(key); } next.pinnedObjects = [...pinned]; break;
      }
      default: throw new ValidationError(`operation: unsupported type ${String(op.type)}`);
    }
  }
  next.revision = document.revision + 1;
  validateDocument(next);
  return next;
}

export function createHistory(document: CanvasDocument): HistoryState { validateDocument(document); return { document: clone(document), past: [], future: [] }; }
export function reduceHistory(history: HistoryState, action: HistoryAction): HistoryState {
  if (action.type === 'apply') {
    const next = applyVisualBatch(history.document, action.operations, action.baseRevision ?? history.document.revision);
    if (next === history.document) return history;
    return { document: next, past: [...history.past, clone(history.document)].slice(-100), future: [] };
  }
  const source = action.type === 'undo' ? history.past : history.future;
  if (!source.length) return history;
  const next = clone(source[source.length - 1]); next.revision = history.document.revision + 1;
  return action.type === 'undo'
    ? { document: next, past: history.past.slice(0, -1), future: [...history.future, clone(history.document)] }
    : { document: next, past: [...history.past, clone(history.document)], future: history.future.slice(0, -1) };
}
