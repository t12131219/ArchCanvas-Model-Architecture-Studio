import { EXPANDED_DETAIL_SIZES } from "./module-details";
import type { Bounds, LabNode, LabScene } from "./types";

export type ExpandedSizeMap = Record<string, Pick<Bounds, "width" | "height">>;

export function expandableNodeIds(scene: LabScene): string[] {
  return scene.nodes.filter((node) => node.detail_kind).map((node) => node.scene_node_id);
}

export function expandScene(
  scene: LabScene,
  expandedNodeIds: ReadonlySet<string>,
  sizeOverrides: ExpandedSizeMap = {},
): LabScene {
  const expanded = scene.nodes
    .filter((node) => node.detail_kind && expandedNodeIds.has(node.scene_node_id))
    .map((node) => ({
      node,
      size: sizeOverrides[node.scene_node_id] ?? EXPANDED_DETAIL_SIZES[node.detail_kind!],
    }))
    .sort((a, b) => a.node.bounds.x - b.node.bounds.x || a.node.scene_node_id.localeCompare(b.node.scene_node_id));

  if (!expanded.length) {
    return {
      ...scene,
      nodes: scene.nodes.map((node) => ({ ...node, bounds: { ...node.bounds }, detail_expanded: undefined })),
      edges: scene.edges.map((edge) => ({ ...edge })),
    };
  }

  const deltaById = new Map(expanded.map(({ node, size }) => [
    node.scene_node_id,
    Math.max(0, size.width - node.bounds.width),
  ]));
  const expandedIds = new Set(expanded.map(({ node }) => node.scene_node_id));

  const nodes: LabNode[] = scene.nodes.map((node) => {
    const shiftX = expanded.reduce((sum, item) => (
      item.node.bounds.x < node.bounds.x ? sum + (deltaById.get(item.node.scene_node_id) ?? 0) : sum
    ), 0);
    if (!expandedIds.has(node.scene_node_id) || !node.detail_kind) {
      return {
        ...node,
        bounds: { ...node.bounds, x: node.bounds.x + shiftX },
        detail_expanded: undefined,
      };
    }

    const size = sizeOverrides[node.scene_node_id] ?? EXPANDED_DETAIL_SIZES[node.detail_kind];
    const centerY = node.bounds.y + node.bounds.height / 2;
    const naturalHeight = EXPANDED_DETAIL_SIZES[node.detail_kind].height;
    return {
      ...node,
      bounds: {
        x: node.bounds.x + shiftX,
        y: Math.max(32, centerY - naturalHeight / 2),
        width: size.width,
        height: size.height,
      },
      detail_expanded: true,
    };
  });

  const paperWidth = scene.paper_width + [...deltaById.values()].reduce((sum, delta) => sum + delta, 0);
  const paperHeight = Math.max(scene.paper_height, ...nodes.map((node) => node.bounds.y + node.bounds.height + 32));
  return {
    ...scene,
    paper_width: paperWidth,
    paper_height: paperHeight,
    nodes,
    edges: scene.edges.map((edge) => ({ ...edge })),
  };
}
