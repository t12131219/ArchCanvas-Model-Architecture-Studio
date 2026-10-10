import { buildScene } from './core/scene.ts';
import type { CanvasDocument } from './core/types.ts';

/** A separate editing frontier exposes recovered compound implementations.
 * One projection replaces repeated expand operations; the source view and its
 * frontier caches are never changed by entering the model editor. */
export function sourceEditingDocument(view: CanvasDocument): CanvasDocument {
  const document = structuredClone(view);
  const compound = document.architecture.nodes.filter(node => node.children.length);
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
    document = sourceEditingDocument(document);
  }
  const scene = buildScene(document, { presentation: 'editor' });
  for (const node of scene.nodes) document.layout[node.id] = { x: node.localX, y: node.localY };
  return { document, scene };
}
