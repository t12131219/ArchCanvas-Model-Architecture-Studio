import type { AuthoredDraft, DraftCatalog } from './authoring.ts';
import { draftNodeSize } from './draftNodeGeometry.ts';
import { routeSourceRelations } from './core/sourceRelationRoutes.ts';
import type { SceneNode } from './core/types.ts';

/** Immutable source evidence follows the editable cards' live world geometry.
 * Source arrows never enter draft.edges or acquire editable tensor ports. */
export function draftSourceRelations(draft: AuthoredDraft, catalog: DraftCatalog) {
  const provenance = draft.sourceProvenance;
  if (!provenance) return { relations: [], diagnostics: [], points: [] };
  const facts = new Map(provenance.architecture.nodes.map(node => [node.id, node]));
  const nodes: SceneNode[] = draft.nodes.flatMap(node => {
    const fact = facts.get(provenance.nodeRefs[node.id]?.nodeId);
    if (!fact) return [];
    const size = draftNodeSize(node, catalog), expanded = !!node.presentation?.group;
    return [{ id: fact.id, parentId: fact.parentId, ...node.position, ...size,
      localX: node.position.x, localY: node.position.y, label: node.label, subtitle: '',
      headerHeight: expanded ? Math.min(36, Math.max(24, size.height - 2)) : 0,
      kind: fact.kind, category: fact.category, fill: '#ffffff', stroke: '#56616b', glyph: 'module',
      expanded, expandable: !!fact.children.length, pinned: false, evidence: fact.evidence, repeat: fact.repeat, ports: [] }];
  });
  const implicit = new Set(nodes.filter(node => !node.parentId && node.expanded).map(node => node.id));
  return routeSourceRelations(provenance.architecture, nodes, false, implicit);
}
