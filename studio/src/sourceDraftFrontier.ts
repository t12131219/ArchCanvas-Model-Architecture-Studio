import { applyVisualBatch, buildScene } from './core/index.ts';
import { api } from './api.ts';
import type { AuthoredDraft } from './authoring.ts';
import type { CanvasDocument } from './core/types.ts';

/** Source expansion changes presentation frontier while preserving independent edits. */
export function sourceFrontierDocument(draft: AuthoredDraft, nodeId?: string, expanded?: boolean): CanvasDocument {
  const provenance = draft.sourceProvenance;
  if (!provenance) throw new Error('此草稿没有源码层级。');
  let document = structuredClone(provenance.canvas);
  const original = new Map(provenance.originalGraph.nodes.map(node => [node.id, node]));
  const moves = draft.nodes.flatMap(node => {
    const ref = provenance.nodeRefs[node.id], before = original.get(node.id);
    if (!ref || !before) return [];
    // Children already inherit moved source groups; moving every atom again
    // would double the group delta. Move explicit top-level frontier groups.
    const parent = node.presentation?.parentId;
    const parentNode = parent && draft.nodes.find(item => item.id === parent);
    const parentBefore = parent && original.get(parent);
    const inheritedX = parentNode && parentBefore ? parentNode.position.x - parentBefore.position.x : 0;
    const inheritedY = parentNode && parentBefore ? parentNode.position.y - parentBefore.position.y : 0;
    const dx = node.position.x - before.position.x - inheritedX, dy = node.position.y - before.position.y - inheritedY;
    return dx || dy ? [{ type: 'move' as const, ids: [ref.nodeId], dx, dy }] : [];
  });
  if (moves.length) document = applyVisualBatch(document, moves);
  if (nodeId) {
    const canonical = provenance.nodeRefs[nodeId]?.nodeId;
    if (!canonical) throw new Error('此模块没有可展开的源码层级。');
    document = applyVisualBatch(document, [{ type: 'expand', id: canonical, expanded: !!expanded }]);
  } else {
    document = applyVisualBatch(document, document.architecture.nodes.filter(node => node.children.length).map(node => ({ type: 'expand' as const, id: node.id, expanded: true })));
  }
  return document;
}
export async function reprojectSourceDraft(draft: AuthoredDraft, nodeId?: string, expanded?: boolean): Promise<AuthoredDraft> {
  const document = sourceFrontierDocument(draft, nodeId, expanded);
  return (await api.sourceDraftFrontier(draft, document, buildScene(document))).draft;
}
