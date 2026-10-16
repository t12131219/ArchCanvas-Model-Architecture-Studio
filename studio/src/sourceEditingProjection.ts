import { buildScene } from './core/scene.ts';
import type { CanvasDocument } from './core/types.ts';

/** A separate editing frontier exposes recovered compound implementations.
 * One projection replaces repeated expand operations; the source view and its
 * frontier caches are never changed by entering the model editor. */
export function sourceEditingDocument(view: CanvasDocument, initializeInspection = true): CanvasDocument {
  const document = structuredClone(view);
  // Large unresolved source trees are inspection data, not a tensor graph that
  // needs complete materialization before editing. Keep their authored regions
  // available as expandable cards; proven compositions still expose primitives.
  // Existing user expansion choices survive both entry and subsequent rebases.
  const boundedInspection = document.architecture.nodes.length > 96 && document.architecture.nodes.some(node => node.sourceStructure);
  // Branch/control wrappers describe editable scope, not an implementation
  // detail. Leaving them collapsed hides all useful contents behind empty
  // if/else cards. Open these wrappers even for a large source corpus while
  // keeping large module implementations individually expandable.
  const controlScopes = new Set(['SourceBranch', 'SourceConditional', 'SourceLoop', 'SourceAlternatives']);
  const compound = document.architecture.nodes.filter(node => node.children.length &&
    (!node.sourceStructure || initializeInspection && (!boundedInspection || controlScopes.has(node.kind))));
  const missing = compound.some(node => !document.expandedIds.includes(node.id));
  if (!missing) return document;
  document.expandedIds = [...new Set([...document.expandedIds, ...compound.map(node => node.id)])];
  // Compact card coordinates cannot enclose full implementations. Arrange the
  // independent editor frontier once, retaining each root's world anchor.
  document.layout = Object.fromEntries(document.architecture.nodes.filter(node => !node.parentId && view.layout[node.id])
    .map(node => [node.id, { x: view.layout[node.id].x, y: view.layout[node.id].y }]));
  document.layoutByFrontier = {};
  return document;
}

export function projectSourceEditing(view: CanvasDocument, previousEditing?: CanvasDocument, previousView?: CanvasDocument) {
  let document = sourceEditingDocument(view);
  if (previousEditing && previousView && [previousEditing, previousView].every(before =>
    before.id === view.id && before.sourceBindingDigest === view.sourceBindingDigest && before.architecture.irDigest === view.architecture.irDigest)) {
    // Preserve the independent editor arrangement. A compact group movement
    // changes its local anchor, carrying every expanded descendant with it.
    document = structuredClone(previousEditing);
    document.revision = view.revision;
    // A newly expanded view region must also be accessible in the editor.
    // Compare with its old view frontier so unchanged view flags do not undo
    // an intentional collapse made independently in the editing workspace.
    const beforeExpanded = new Set(previousView.expandedIds);
    const newlyExpanded = view.expandedIds.filter(id => !beforeExpanded.has(id));
    document.expandedIds = [...new Set([...document.expandedIds, ...newlyExpanded])];
    for (const key of ['displayAliases', 'nodeStyleOverrides', 'edgeStyleOverrides', 'portLayoutOverrides', 'pageSpec', 'legendItems', 'annotations', 'pinnedObjects'] as const) {
      Object.assign(document, { [key]: structuredClone(view[key]) });
    }
    const before = new Map(buildScene(previousView).nodes.map(node => [node.id, node]));
    for (const node of buildScene(view).nodes) {
      const old = before.get(node.id), layout = document.layout[node.id];
      if (!old || !layout || old.parentId !== node.parentId) continue;
      layout.x += node.localX - old.localX;
      layout.y += node.localY - old.localY;
      if (!node.expandable) { layout.width = node.width; layout.height = node.height; }
    }
    document = sourceEditingDocument(document, false);
  }
  const scene = buildScene(document, { presentation: 'editor' });
  for (const node of scene.nodes) document.layout[node.id] = { x: node.localX, y: node.localY };
  return { document, scene };
}
