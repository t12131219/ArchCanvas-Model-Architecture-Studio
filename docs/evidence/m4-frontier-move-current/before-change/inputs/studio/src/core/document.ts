import type { Architecture, CanvasDocument, HistoryAction, HistoryState, Position, VisualOperation } from './types.ts';
import { CATEGORY_STYLES, TOKENS } from './tokens.ts';
import { buildScene } from './scene.ts';
import { fields, finite, object, textValue, validateArchitecture, validateDocument, ValidationError } from './validate.ts';

const clone = <T>(v: T): T => structuredClone(v);
const FRONTIER_PREFIX = 'visible-frontier/1:';
type Frontier = { key: string; expandedIds: string[]; visibleIds: Set<string> };

/** Hidden expansion flags remember detail, but do not describe the displayed frontier. */
function frontier(document: CanvasDocument, expandedIds = document.expandedIds): Frontier {
  const byId = new Map(document.architecture.nodes.map(node => [node.id, node]));
  const expanded = new Set(expandedIds), visibleIds = new Set<string>(), effective: string[] = [];
  const visit = (id: string) => {
    const node = byId.get(id)!;
    visibleIds.add(id);
    if (expanded.has(id) && node.children.length) {
      effective.push(id);
      node.children.forEach(visit);
    }
  };
  document.architecture.nodes.filter(node => !node.parentId).forEach(node => visit(node.id));
  effective.sort();
  // A JSON array distinguishes identities containing the old '|' separator.
  return { key: `${FRONTIER_PREFIX}${JSON.stringify(effective)}`, expandedIds: effective, visibleIds };
}

function cachedExpansionIds(document: CanvasDocument, key: string): string[] | undefined {
  const byId = new Map(document.architecture.nodes.map(node => [node.id, node]));
  const valid = (ids: unknown): ids is string[] => Array.isArray(ids) && ids.every(id => typeof id === 'string' && !!byId.get(id)?.children.length) && new Set(ids).size === ids.length;
  if (key.startsWith(FRONTIER_PREFIX)) {
    try { const ids: unknown = JSON.parse(key.slice(FRONTIER_PREFIX.length)); if (valid(ids)) return ids; }
    catch { /* Legacy arbitrary IDs can start with this prefix; inspect them below. */ }
  }
  if (!key) return byId.get('')?.children.length ? undefined : [];
  // Old keys joined sorted identities with '|', which can also occur inside an
  // identity. Find at most two complete, sorted interpretations, including
  // composite identities such as ['a|b', 'root']. A split-only lookup is unsafe.
  const candidates = new Map<number, { id: string; next: number }[]>();
  const interpretations = new Map<string, string[][]>();
  let budget = 20_000, exhausted = false;
  function parse(start: number, previous?: string): string[][] {
    const memoKey = JSON.stringify([start, previous ?? null]);
    const memo = interpretations.get(memoKey);
    if (memo) return memo;
    if (--budget < 0) { exhausted = true; return []; }
    let matches = candidates.get(start);
    if (!matches) {
      matches = [];
      for (let end = start; end <= key.length; end++) {
        if (--budget < 0) { exhausted = true; return []; }
        if (end !== key.length && key[end] !== '|') continue;
        const id = key.slice(start, end);
        if (byId.get(id)?.children.length) matches.push({ id, next: end === key.length ? -1 : end + 1 });
      }
      candidates.set(start, matches);
    }
    const solutions: string[][] = [];
    for (const match of matches) {
      // Strict order also excludes duplicate identities, matching the old key writer.
      if (previous !== undefined && match.id <= previous) continue;
      const tails = match.next === -1 ? [[]] : parse(match.next, match.id);
      for (const tail of tails) {
        solutions.push([match.id, ...tail]);
        if (solutions.length === 2) break;
      }
      if (solutions.length === 2 || exhausted) break;
    }
    interpretations.set(memoKey, solutions);
    return solutions;
  }
  const solutions = parse(0);
  // Preserve old bytes but never choose geometry on ambiguous or bounded-out parsing.
  return !exhausted && solutions.length === 1 ? solutions[0] : undefined;
}

function snapshotFor(document: CanvasDocument, target: Frontier): Record<string, Position> | undefined {
  const direct = document.layoutByFrontier[target.key];
  if (direct) return direct;
  const legacyKey = target.expandedIds.join('|'), legacyIds = cachedExpansionIds(document, legacyKey);
  const exactLegacy = legacyIds && frontier(document, legacyIds).key === target.key ? document.layoutByFrontier[legacyKey] : undefined;
  if (exactLegacy) return exactLegacy;
  const compatible = Object.entries(document.layoutByFrontier).filter(([key]) => {
    const ids = cachedExpansionIds(document, key);
    return ids && frontier(document, ids).key === target.key;
  }).map(([, positions]) => positions);
  if (!compatible.length) return undefined;
  const signature = (positions: Record<string, Position>) => JSON.stringify([...target.visibleIds].sort().map(id => {
    const position = positions[id];
    return position ? [id, position.x, position.y, position.width ?? null, position.height ?? null] : [id, null];
  }));
  const expected = signature(compatible[0]);
  // Several old hidden-state keys can project to one display. Conflicting
  // placements carry no ordering evidence, so retain the current arrangement.
  return compatible.every(positions => signature(positions) === expected) ? compatible[0] : undefined;
}

function visibleSnapshot(document: CanvasDocument, visibleIds: Set<string>, positions = document.layout): Record<string, Position> {
  return clone(Object.fromEntries(Object.entries(positions).filter(([id]) => visibleIds.has(id))));
}

export class RevisionConflict extends Error {
  expected: number;
  actual: number;
  constructor(expected: number, actual: number) { super(`Revision conflict: expected ${expected}, current ${actual}`); this.name = 'RevisionConflict'; this.expected = expected; this.actual = actual; }
}

export function createDocument(architecture: Architecture, title = architecture.label, displayAliases: Record<string, string> = {}): CanvasDocument {
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
    displayAliases: clone(displayAliases), nodeStyleOverrides: {}, edgeStyleOverrides: {},
    legendItems: categories.slice(0, 6).map(c => ({ id: `legend:${c}`, label: c[0].toUpperCase() + c.slice(1), color: CATEGORY_STYLES[c].fill, glyph: CATEGORY_STYLES[c].glyph })),
    annotations: [], pageSpec: { widthMm: 180, background: '#ffffff', preset: 'paper' },
    expandedIds: roots.length === 1 && roots[0].children.length ? [roots[0].id] : [],
    layout: {}, layoutByFrontier: {}, pinnedObjects: [],
  };
  // Initial aliases must participate in text measurement before positions are
  // materialized. Later visual edits still preserve the user's arrangement.
  validateDocument(document);
  materialize(document);
  return document;
}

/** A canonical refresh starts a fresh source-bound document, outside visual undo. */
export function reconcileDocument(previous: CanvasDocument, architecture: Architecture) {
  validateDocument(previous); validateArchitecture(architecture);
  const document = createDocument(architecture, previous.title);
  const oldNodes = new Map(previous.architecture.nodes.map(n => [n.id, n]));
  const preservedNodeIds = architecture.nodes.filter(n => {
    const before = oldNodes.get(n.id);
    return before && before.kind === n.kind && before.parentId === n.parentId && before.instanceId === n.instanceId && before.callId === n.callId
      && JSON.stringify(before.outputPath) === JSON.stringify(n.outputPath);
  }).map(n => n.id);
  const nodes = new Set(preservedNodeIds);
  const oldEdges = new Map(previous.architecture.edges.map(e => [e.id, e]));
  const preservedEdgeIds = architecture.edges.filter(e => {
    const old = oldEdges.get(e.id);
    return old && nodes.has(e.source.nodeId) && nodes.has(e.target.nodeId) && old.source.nodeId === e.source.nodeId && old.source.portId === e.source.portId && old.target.nodeId === e.target.nodeId && old.target.portId === e.target.portId && old.tensorId === e.tensorId && old.role === e.role;
  }).map(e => e.id);
  const edges = new Set(preservedEdgeIds);
  const filter = <T>(record: Record<string, T>, ids: Set<string>) => Object.fromEntries(Object.entries(record).filter(([id]) => ids.has(id))) as Record<string, T>;
  document.displayAliases = clone(filter(previous.displayAliases, nodes));
  document.nodeStyleOverrides = clone(filter(previous.nodeStyleOverrides, nodes));
  document.edgeStyleOverrides = clone(filter(previous.edgeStyleOverrides, edges));
  document.layout = { ...document.layout, ...clone(filter(previous.layout, nodes)) };
  document.expandedIds = previous.expandedIds.filter(id => nodes.has(id) && architecture.nodes.find(n => n.id === id)!.children.length > 0);
  document.pinnedObjects = previous.pinnedObjects.filter(id => nodes.has(id));
  document.layoutByFrontier = {};
  for (const [key, positions] of Object.entries(previous.layoutByFrontier)) {
    const expanded = cachedExpansionIds(previous, key);
    if (expanded && expanded.every(id => nodes.has(id))) document.layoutByFrontier[key] = clone(filter(positions, nodes));
  }
  document.legendItems = clone(previous.legendItems); document.annotations = clone(previous.annotations); document.pageSpec = clone(previous.pageSpec);
  document.revision = previous.revision + 1;
  materialize(document); validateDocument(document);
  return { document, preservedNodeIds, preservedEdgeIds, removedNodeIds: previous.architecture.nodes.filter(n => !nodes.has(n.id)).map(n => n.id) };
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
  const previousFrontier = frontier(document), previousSaved = snapshotFor(document, previousFrontier);
  const hasHiddenExpansionMemory = previousFrontier.expandedIds.length !== document.expandedIds.length;
  // An older document may already be collapsed with stretched neighbors. Its
  // correct overview cache must survive the first toggle after reopening.
  // Ordinary moves update every saved frontier, including this prior geometry.
  document.layoutByFrontier[previousFrontier.key] = visibleSnapshot(document, previousFrontier.visibleIds,
    hasHiddenExpansionMemory && previousSaved ? previousSaved : document.layout);
  const ids = new Set(document.expandedIds);
  if (expanded) ids.add(id); else ids.delete(id);
  document.expandedIds = [...ids];
  const nextFrontier = frontier(document);
  // Toggling a hidden descendant changes memory only, not visible placement.
  if (nextFrontier.key === previousFrontier.key) return;
  // Restore frontier geometry, including neighbor displacement. A direct user move updates
  // every stored frontier below, so a subsequent toggle cannot undo deliberate placement.
  const saved = snapshotFor(document, nextFrontier);
  const anchored = new Set([id]);
  let parent = canonical.parentId;
  while (parent) { anchored.add(parent); parent = document.architecture.nodes.find(node => node.id === parent)?.parentId; }
  if (saved) for (const [key, position] of Object.entries(saved)) {
    if (nextFrontier.visibleIds.has(key) && !anchored.has(key) && !subtreePinned(document, key)) document.layout[key] = clone(position);
  }
  materialize(document);
  if (!operated || !expanded || saved) return;
  const grownIds = new Set([id]);
  let ancestor = canonical.parentId;
  while (ancestor) { grownIds.add(ancestor); ancestor = document.architecture.nodes.find(n => n.id === ancestor)?.parentId; }
  // A descendant expansion also grows its containing ancestors. Repair siblings at
  // each affected containment level without moving the operated node or its ancestry.
  for (const previous of [...before.nodes].reverse().filter(node => grownIds.has(node.id))) {
    // Moving children can further enlarge their parent. Measure that parent
    // after the child-level repair so downstream siblings receive the full growth.
    const grown = buildScene(document).nodes.find(node => node.id === previous.id)!;
    const dx = grown.width - previous.width, dy = grown.height - previous.height;
    if (dx <= 0 && dy <= 0) continue;
    const siblings = before.nodes.filter(n => n.id !== previous.id && n.parentId === previous.parentId && !subtreePinned(document, n.id));
    const horizontal = dx > 0 ? siblings.filter(n => n.x >= previous.x + previous.width && n.y < grown.y + grown.height && n.y + n.height > grown.y) : [];
    const horizontalIds = new Set(horizontal.map(n => n.id));
    if (horizontal.length) {
      const first = Math.min(...horizontal.map(n => n.x));
      const clearance = Math.min(TOKENS.gapX, first - previous.x - previous.width);
      const displacement = Math.max(0, grown.x + grown.width + clearance - first);
      // Translate the whole affected frontier together, retaining its relative/manual gaps.
      for (const n of horizontal) document.layout[n.id].x += displacement;
    }
    const vertical = dy > 0 ? siblings.filter(n => !horizontalIds.has(n.id) && n.y >= previous.y + previous.height && n.x < grown.x + grown.width && n.x + n.width > grown.x) : [];
    if (vertical.length) {
      const first = Math.min(...vertical.map(n => n.y));
      const clearance = Math.min(TOKENS.gapY, first - previous.y - previous.height);
      const displacement = Math.max(0, grown.y + grown.height + clearance - first);
      // Existing free space absorbs growth; parallel branches must not add their heights.
      for (const n of vertical) document.layout[n.id].y += displacement;
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
