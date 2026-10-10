import type { AuthoredDraft, DraftNode } from './authoring.ts';
import { buildScene } from './core/scene.ts';
import type { CanvasDocument, VisualOperation } from './core/types.ts';

const canonical = (value: unknown): unknown => Array.isArray(value) ? value.map(canonical) :
  value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).filter(([, item]) => item !== undefined)
    .sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonical(item)])) : value;
const equal = (a: unknown, b: unknown) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
const allNodes = (draft: AuthoredDraft) => [...new Map([...(draft.sourceCache?.nodes ?? []), ...draft.nodes].map(node => [node.id, node])).values()];

/** A changed frontier may expose different proxy edges, but an unedited graph
 * still equals its independently imported original graph at that frontier. */
function unchangedSourceGraph(draft: AuthoredDraft) {
  const source = draft.sourceProvenance!;
  if (draft.sourceCache?.removedNodeIds.length || draft.sourceCache?.removedCanonicalEdgeIds.length || draft.sourceCache?.edges.length) return false;
  if (source.originalGraph.nodes.length !== draft.nodes.length || !equal(source.originalGraph.edges, draft.edges)) return false;
  const ids = new Set(draft.nodes.map(node => node.id));
  if (source.originalGraph.nodes.some(node => !ids.has(node.id))) return false;
  return allNodes(draft).every(node => {
    const ref = source.nodeRefs[node.id];
    return ref && node.kind === `Source_${node.id.slice(2)}` && equal(node.parameters, ref.originalParameters);
  });
}

/** Presentation edits never require Python regeneration, including opaque code.
 * Changes to constructors, removed nodes or tensor bindings stay structural. */
export function sameSourceSemantics(a: AuthoredDraft, b: AuthoredDraft): boolean {
  const x = a.sourceProvenance, y = b.sourceProvenance;
  return !!x && !!y && a.id === b.id && x.documentId === y.documentId && x.sourceDigest === y.sourceDigest && x.irDigest === y.irDigest &&
    equal(x.architecture, y.architecture) && equal(a.customModules, b.customModules) && unchangedSourceGraph(a) && unchangedSourceGraph(b);
}

/** Project an editor delta through original source IDs into the same document.
 * Compact view dimensions and expanded editor dimensions remain independent. */
export function sourcePresentationOperations(document: CanvasDocument, before: AuthoredDraft, after: AuthoredDraft): VisualOperation[] {
  if (!sameSourceSemantics(before, after)) throw new Error('模型语义已变化，需要独立生成与验证。');
  const source = after.sourceProvenance!;
  if (source.documentId !== document.id || source.sourceDigest !== document.sourceBindingDigest || source.irDigest !== document.architecture.irDigest)
    throw new Error('源码绑定已变化，无法将展示修改应用到原画布。');
  const operations: VisualOperation[] = [], original = new Map(allNodes(before).map(node => [node.id, node]));
  const edited = new Map(allNodes(after).map(node => [node.id, node]));
  const visible = new Map(buildScene(document).nodes.map(node => [node.id, node]));
  if (after.title !== before.title) operations.push({ type: 'title', title: after.title });
  for (const node of allNodes(after)) {
    const prior = original.get(node.id), ref = source.nodeRefs[node.id];
    if (!ref) throw new Error('展示模块缺少源码绑定。');
    if (!prior) continue; // Newly exposed facts retain the source view layout.
    if (node.label !== prior.label) operations.push({ type: 'alias', id: ref.nodeId, label: node.label });
    const style = node.visual ?? node.presentation, oldStyle = prior.visual ?? prior.presentation;
    if (style && (style.fill !== oldStyle?.fill || style.stroke !== oldStyle?.stroke))
      operations.push({ type: 'nodeStyle', id: ref.nodeId, style: { fill: style.fill, stroke: style.stroke } });
    const parentId = node.presentation?.parentId, parent = parentId ? edited.get(parentId) : undefined, oldParent = parentId ? original.get(parentId) : undefined;
    const dx = node.position.x - prior.position.x - (parent && oldParent ? parent.position.x - oldParent.position.x : 0);
    const dy = node.position.y - prior.position.y - (parent && oldParent ? parent.position.y - oldParent.position.y : 0);
    const scene = visible.get(ref.nodeId), layout = document.layout[ref.nodeId];
    const resized = style && oldStyle && (style.width !== oldStyle.width || style.height !== oldStyle.height);
    if (dx || dy || resized) {
      // Hidden atoms establish their local editor coordinates, so expanding the
      // source group later reveals the edit instead of discarding it.
      const base = layout ?? (scene ? { x: scene.localX, y: scene.localY } :
        { x: prior.position.x - (oldParent?.position.x ?? 0), y: prior.position.y - (oldParent?.position.y ?? 0) });
      const size = resized && style && (!scene || scene.expanded === !!node.presentation?.group) ? { width: style.width, height: style.height } : {};
      operations.push({ type: 'nodeLayout', id: ref.nodeId, position: { ...base, x: base.x + dx, y: base.y + dy, ...size } });
    }
    for (const [portId, layout] of Object.entries(node.portLayouts ?? {})) {
      if (equal(layout, prior.portLayouts?.[portId])) continue;
      for (const binding of ref.portBindings[portId] ?? []) {
        const roles = new Set(document.architecture.edges.filter(edge => [edge.source, edge.target].some(end => end.nodeId === binding.nodeId && end.portId === binding.portId)).map(edge => edge.role));
        for (const role of roles) operations.push({ type: 'portLayout', ownerId: ref.sceneNodeId, ...binding, role, layout });
      }
    }
  }
  return operations;
}
