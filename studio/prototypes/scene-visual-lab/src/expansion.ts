import { EXPANDED_DETAIL_SIZES } from "./module-details";
import type { Bounds, LabNode, LabScene } from "./types";

export type ExpandedSizeMap = Record<string, Pick<Bounds, "width" | "height">>;

const PAPER_LANE_GAP = 72;
const PAPER_MARGIN = 36;
const PAPER_SIDE_GAP = 24;

function paperLaneCenter(nodes: LabNode[]): number {
  const centers = nodes.map((node) => node.bounds.x + node.bounds.width / 2).sort((a, b) => a - b);
  return centers[Math.floor(centers.length / 2)] ?? 0;
}

function expandPaperScene(
  scene: LabScene,
  expandedNodeIds: ReadonlySet<string>,
  sizeOverrides: ExpandedSizeMap,
): LabScene {
  const expandedSizes = new Map(scene.nodes.flatMap((node) => (
    node.detail_kind && expandedNodeIds.has(node.scene_node_id)
      ? [[node.scene_node_id, sizeOverrides[node.scene_node_id] ?? EXPANDED_DETAIL_SIZES[node.detail_kind]]]
      : []
  )));
  const growthById = new Map(scene.nodes.map((node) => {
    const size = expandedSizes.get(node.scene_node_id);
    return [node.scene_node_id, size ? Math.max(0, size.height - node.bounds.height) : 0];
  }));
  const lanes = new Map<string, LabNode[]>();
  for (const node of scene.nodes) {
    const lane = node.layout_lane ?? node.scene_node_id;
    lanes.set(lane, [...(lanes.get(lane) ?? []), node]);
  }

  const transformedById = new Map<string, LabNode>();
  for (const laneNodes of lanes.values()) {
    for (const node of laneNodes) {
      const size = expandedSizes.get(node.scene_node_id);
      const rank = node.layout_rank ?? 0;
      const upwardGrowth = laneNodes.reduce((sum, candidate) => (
        (candidate.layout_rank ?? 0) <= rank
          ? sum + (growthById.get(candidate.scene_node_id) ?? 0)
          : sum
      ), 0);
      const width = size?.width ?? node.bounds.width;
      const height = size?.height ?? node.bounds.height;
      transformedById.set(node.scene_node_id, {
        ...node,
        bounds: {
          x: node.bounds.x + (node.bounds.width - width) / 2,
          y: node.bounds.y - upwardGrowth,
          width,
          height,
        },
        detail_expanded: size ? true : undefined,
      });
    }
    for (const expandedSource of laneNodes.filter((node) => expandedSizes.has(node.scene_node_id))) {
      const expanded = transformedById.get(expandedSource.scene_node_id)!;
      for (const peer of laneNodes) {
        if (peer.scene_node_id === expandedSource.scene_node_id) continue;
        if ((peer.layout_rank ?? 0) !== (expandedSource.layout_rank ?? 0)) continue;
        const current = transformedById.get(peer.scene_node_id)!;
        const verticallyOverlaps = current.bounds.y < expanded.bounds.y + expanded.bounds.height
          && current.bounds.y + current.bounds.height > expanded.bounds.y;
        if (!verticallyOverlaps) continue;
        const peerCenter = peer.bounds.x + peer.bounds.width / 2;
        const expandedCenter = expandedSource.bounds.x + expandedSource.bounds.width / 2;
        if (peerCenter < expandedCenter) {
          const shiftX = expanded.bounds.x - PAPER_SIDE_GAP - (current.bounds.x + current.bounds.width);
          if (shiftX < 0) {
            transformedById.set(peer.scene_node_id, {
              ...current,
              bounds: { ...current.bounds, x: current.bounds.x + shiftX },
            });
          }
        } else if (peerCenter > expandedCenter) {
          const shiftX = expanded.bounds.x + expanded.bounds.width + PAPER_SIDE_GAP - current.bounds.x;
          if (shiftX > 0) {
            transformedById.set(peer.scene_node_id, {
              ...current,
              bounds: { ...current.bounds, x: current.bounds.x + shiftX },
            });
          }
        }
      }
    }
  }

  const orderedLanes = [...lanes.entries()].sort(([, first], [, second]) => (
    paperLaneCenter(first) - paperLaneCenter(second)
  ));
  let previousRight = -Infinity;
  for (const [, laneNodes] of orderedLanes) {
    const transformed = laneNodes.map((node) => transformedById.get(node.scene_node_id)!);
    const laneLeft = Math.min(...transformed.map((node) => node.bounds.x));
    const laneRight = Math.max(...transformed.map((node) => node.bounds.x + node.bounds.width));
    const shiftX = Number.isFinite(previousRight)
      ? Math.max(0, previousRight + PAPER_LANE_GAP - laneLeft)
      : 0;
    if (shiftX) {
      for (const node of transformed) {
        transformedById.set(node.scene_node_id, {
          ...node,
          bounds: { ...node.bounds, x: node.bounds.x + shiftX },
        });
      }
    }
    previousRight = laneRight + shiftX;
  }

  const rawNodes = scene.nodes.map((node) => transformedById.get(node.scene_node_id)!);
  const minX = Math.min(...rawNodes.map((node) => node.bounds.x));
  const minY = Math.min(...rawNodes.map((node) => node.bounds.y));
  const translateX = minX < PAPER_MARGIN ? PAPER_MARGIN - minX : 0;
  const translateY = minY < PAPER_MARGIN ? PAPER_MARGIN - minY : 0;
  const nodes = rawNodes.map((node) => ({
    ...node,
    bounds: {
      ...node.bounds,
      x: node.bounds.x + translateX,
      y: node.bounds.y + translateY,
    },
  }));
  const right = Math.max(...nodes.map((node) => node.bounds.x + node.bounds.width));
  const bottom = Math.max(...nodes.map((node) => node.bounds.y + node.bounds.height));
  return {
    ...scene,
    paper_width: Math.max(scene.paper_width, right + PAPER_MARGIN),
    paper_height: Math.max(scene.paper_height, bottom + PAPER_MARGIN),
    nodes,
    edges: scene.edges.map((edge) => ({ ...edge })),
  };
}

export function expandableNodeIds(scene: LabScene): string[] {
  return scene.nodes.filter((node) => node.detail_kind).map((node) => node.scene_node_id);
}

export function expandScene(
  scene: LabScene,
  expandedNodeIds: ReadonlySet<string>,
  sizeOverrides: ExpandedSizeMap = {},
): LabScene {
  if (scene.layout_profile === "paper" && expandedNodeIds.size) {
    return expandPaperScene(scene, expandedNodeIds, sizeOverrides);
  }
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
  const verticalGrowthById = new Map(expanded.map(({ node, size }) => [
    node.scene_node_id,
    Math.max(0, size.height - EXPANDED_DETAIL_SIZES[node.detail_kind!].height),
  ]));
  const expandedIds = new Set(expanded.map(({ node }) => node.scene_node_id));

  const nodes: LabNode[] = scene.nodes.map((node) => {
    const shiftX = expanded.reduce((sum, item) => (
      item.node.bounds.x < node.bounds.x ? sum + (deltaById.get(item.node.scene_node_id) ?? 0) : sum
    ), 0);
    const centerY = node.bounds.y + node.bounds.height / 2;
    const shiftY = expanded.reduce((sum, item) => (
      item.node.bounds.y + item.node.bounds.height / 2 < centerY
        ? sum + (verticalGrowthById.get(item.node.scene_node_id) ?? 0)
        : sum
    ), 0);
    if (!expandedIds.has(node.scene_node_id) || !node.detail_kind) {
      return {
        ...node,
        bounds: { ...node.bounds, x: node.bounds.x + shiftX, y: node.bounds.y + shiftY },
        detail_expanded: undefined,
      };
    }

    const size = sizeOverrides[node.scene_node_id] ?? EXPANDED_DETAIL_SIZES[node.detail_kind];
    const naturalHeight = EXPANDED_DETAIL_SIZES[node.detail_kind].height;
    return {
      ...node,
      bounds: {
        x: node.bounds.x + shiftX,
        y: centerY - naturalHeight / 2 + shiftY,
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
