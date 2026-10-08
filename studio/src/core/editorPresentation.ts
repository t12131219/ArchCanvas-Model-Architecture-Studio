import type { Bounds, EdgeRole, LegendItem, Scene, SceneEdgeLegend } from './types.ts';
import { edgeAppearanceKey, edgeDashPattern } from './edgePresentation.ts';
import { nodeVisualOutline } from './nodeVisualOutline.ts';
import { edgeLabelBounds } from './edgeLabelPlacement.ts';
import { orthogonalPathPoints } from './orthogonalRouter.ts';

/** A root remains in the scene for hierarchy, layout, ports and routing facts.
 * Only its expanded editor decoration is implicit. Collapsed roots are cards. */
export function implicitRootIds(scene: { nodes: readonly { id: string; parentId?: string; boundary?: boolean; expanded: boolean; expandable: boolean }[] }): Set<string> {
  return new Set(scene.nodes.filter(node => !node.parentId && !node.boundary && node.expanded && node.expandable).map(node => node.id));
}

/** Fit the editable world content, independently of publication furniture.
 * Title, both legends and the implicit root do not reserve infinite-canvas
 * space. Every actual route, caption, annotation and exposed card still does. */
export function editorSceneBounds(scene: Scene): Bounds {
  const implicit = implicitRootIds(scene);
  const rectangles: Bounds[] = scene.nodes.filter(node => !implicit.has(node.id)).map(node => nodeVisualOutline(node).bounds);
  rectangles.push(...scene.annotations.map(({ x, y, width, height }) => ({ x, y, width, height })));
  rectangles.push(...scene.edges.filter(edge => edge.label).map(edge => edgeLabelBounds(edge.label, edge.labelX, edge.labelY)));
  const points = [...scene.edges.flatMap(edge => orthogonalPathPoints(edge.path)),
    ...(scene.captionGuides ?? []).flatMap(guide => orthogonalPathPoints(guide.path))];
  if (!rectangles.length && !points.length) return { x: 0, y: 0, width: 320, height: 200 };
  const padding = Math.max(24, ...scene.edges.map(edge => edge.width * 5.5 + 8));
  const left = Math.min(...rectangles.map(rectangle => rectangle.x), ...points.map(point => point.x));
  const top = Math.min(...rectangles.map(rectangle => rectangle.y), ...points.map(point => point.y));
  const right = Math.max(...rectangles.map(rectangle => rectangle.x + rectangle.width), ...points.map(point => point.x));
  const bottom = Math.max(...rectangles.map(rectangle => rectangle.y + rectangle.height), ...points.map(point => point.y));
  return { x: left - padding, y: top - padding, width: Math.max(1, right - left + 2 * padding), height: Math.max(1, bottom - top + 2 * padding) };
}

/** Keep the complete constraint scene while selecting editor-only view bounds.
 * Render with presentation: 'editor'; SVG viewBox and world wrapper then share
 * these exact bounds without changing node/route coordinates or the document. */
export function presentEditorScene(scene: Scene): Scene {
  return { ...scene, bounds: editorSceneBounds(scene) };
}

export type EditorEdgeLegend = Pick<SceneEdgeLegend, 'id' | 'role' | 'label' | 'stroke' | 'lineWidth' | 'dashed' | 'dashPattern' | 'sceneEdgeIds' | 'canonicalEdgeIds'>;
export interface EditorLegendItems { nodes: LegendItem[]; edges: EditorEdgeLegend[] }
const roles: EdgeRole[] = ['data', 'residual', 'memory', 'mask'];
const labels: Record<EdgeRole, string> = { data: '数据流', residual: '残差连接', memory: 'Memory 连接', mask: 'Mask 连接' };

/** Floating legend content follows the stored node legend and each actual
 * visible edge style. It is usable in color and monochrome and has no world
 * coordinates, hit regions, history entry or canonical tensor bindings. */
export function editorLegendItems(scene: Scene): EditorLegendItems {
  const nodes = scene.legend.map(({ id, label, color, glyph }) => ({ id, label, color, glyph }));
  const edges = roles.flatMap(role => {
    const groups = new Map<string, Scene['edges']>();
    for (const edge of scene.edges) if (edge.role === role) {
      const key = edgeAppearanceKey(edge), group = groups.get(key) ?? [];
      group.push(edge); groups.set(key, group);
    }
    return [...groups.values()].map((members, index): EditorEdgeLegend => ({
      id: `editor-edge-legend:${role}:${index + 1}`, role,
      label: `${labels[role]}${groups.size > 1 ? ` · 样式 ${index + 1}` : ''}`,
      stroke: members[0].stroke, lineWidth: members[0].width, dashed: members[0].dashed,
      dashPattern: edgeDashPattern(members[0]), sceneEdgeIds: members.map(edge => edge.id),
      canonicalEdgeIds: [...new Set(members.flatMap(edge => edge.canonicalEdgeIds))],
    }));
  });
  return { nodes, edges };
}
