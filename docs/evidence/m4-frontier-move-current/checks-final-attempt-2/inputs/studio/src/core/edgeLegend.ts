import type { Bounds, EdgeLegendLayout, EdgeRole, PageSpec, Scene, SceneEdge, SceneEdgeLegend } from './types.ts';
import { edgeAppearanceKey, edgeDashPattern } from './edgePresentation.ts';
import { textWidth } from './typography.ts';

const ROLES: EdgeRole[] = ['data', 'residual', 'memory', 'mask'];
const LABELS: Record<EdgeRole, string> = {
  data: 'Data / 数据流', residual: 'Residual / 残差连接', memory: 'Memory / Memory 连接', mask: 'Mask / Mask 连接',
};
const intersects = (a: Bounds, b: Bounds) => a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;

/** A derived legend samples each visible role/style variant exactly as drawn. */
export function buildEdgeLegend(edges: SceneEdge[], preset: PageSpec['preset'], layout: EdgeLegendLayout, annotations: Bounds[] = [], reservedIds: readonly string[] = []): SceneEdgeLegend[] {
  if (preset !== 'monochrome' || !edges.length) return [];
  const usedIds = new Set(reservedIds);
  const variants = ROLES.flatMap(role => {
    const groups = new Map<string, SceneEdge[]>();
    for (const edge of edges) if (edge.role === role) {
      const key = edgeAppearanceKey(edge), members = groups.get(key) ?? [];
      members.push(edge); groups.set(key, members);
    }
    return [...groups.values()].map((members, index) => {
      const edge = members[0], label = `${LABELS[role]}${groups.size > 1 ? ` · 样式 ${index + 1}` : ''}`;
      const sampleLength = Math.max(40, edge.width * 5.5), height = Math.max(20, edge.width * 5.5);
      // Marker uses strokeWidth units; include its actual overhang and height.
      const sampleInset = Math.max(0, edge.width * .55), labelOffset = sampleLength + Math.max(16, edge.width * .55 + 8);
      let id = `edge-role-legend:${role}:${index + 1}`;
      while (usedIds.has(id)) id += ':derived';
      usedIds.add(id);
      return { id, role, label, stroke: edge.stroke, lineWidth: edge.width,
        dashed: edge.dashed, dashPattern: edgeDashPattern(edge), sampleLength,
        sceneEdgeIds: members.map(member => member.id), canonicalEdgeIds: [...new Set(members.flatMap(member => member.canonicalEdgeIds))],
        x: 0, y: 0, width: sampleInset + labelOffset + textWidth(label, 10), height };
    });
  });
  const place = (top: number) => {
    let x = layout.x, y = top, rowHeight = 0;
    return variants.map(item => {
      if (x !== layout.x && x + item.width > layout.x + layout.availableWidth) { x = layout.x; y += rowHeight + 12; rowHeight = 0; }
      const placed = { ...item, x, y }; x += item.width + 24; rowHeight = Math.max(rowHeight, item.height); return placed;
    });
  };
  let top = layout.y, result = place(top);
  // Manual annotation anchors stay fixed. Every collision raises the entire
  // band beyond at least one finite annotation, so this cannot oscillate.
  for (let pass = 0; pass <= annotations.length; pass++) {
    const conflicts = annotations.filter(annotation => result.some(item => intersects(item, annotation)));
    if (!conflicts.length) return result;
    top = Math.max(top, ...conflicts.map(annotation => annotation.y + annotation.height + 16)); result = place(top);
  }
  return result;
}

/** Reflow while ignoring a selected note; it must not push itself repeatedly. */
export function visibleEdgeLegend(scene: Scene, ignoreAnnotationId?: string): SceneEdgeLegend[] {
  if (!scene.edgeLegendLayout) return scene.edgeLegend ?? [];
  return buildEdgeLegend(scene.edges, scene.pageSpec.preset, scene.edgeLegendLayout,
    scene.annotations.filter(annotation => annotation.id !== ignoreAnnotationId),
    [...scene.nodes, ...scene.edges, ...scene.legend, ...scene.annotations].map(item => item.id));
}
