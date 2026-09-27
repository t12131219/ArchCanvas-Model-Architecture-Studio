export interface DragPoint {
  x: number;
  y: number;
}

export interface DragBounds extends DragPoint {
  width: number;
  height: number;
}

export interface DraggableNode {
  scene_node_id: string;
  parent_scene_node_id?: string;
  bounds: DragBounds;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value));
}

/** Keep every independently moved subtree inside its nearest stationary parent. */
export function constrainDragDelta<T extends DraggableNode>(
  nodes: T[],
  movingNodeIds: Iterable<string>,
  requested: DragPoint,
): DragPoint {
  const moving = new Set(movingNodeIds);
  const byId = new Map(nodes.map((node) => [node.scene_node_id, node]));
  let minimumX = Number.NEGATIVE_INFINITY;
  let maximumX = Number.POSITIVE_INFINITY;
  let minimumY = Number.NEGATIVE_INFINITY;
  let maximumY = Number.POSITIVE_INFINITY;

  for (const nodeId of moving) {
    const node = byId.get(nodeId);
    if (!node?.parent_scene_node_id || moving.has(node.parent_scene_node_id)) continue;
    const parent = byId.get(node.parent_scene_node_id);
    if (!parent) continue;

    minimumX = Math.max(minimumX, parent.bounds.x - node.bounds.x);
    maximumX = Math.min(
      maximumX,
      parent.bounds.x + parent.bounds.width - node.bounds.x - node.bounds.width,
    );
    minimumY = Math.max(minimumY, parent.bounds.y - node.bounds.y);
    maximumY = Math.min(
      maximumY,
      parent.bounds.y + parent.bounds.height - node.bounds.y - node.bounds.height,
    );
  }

  // Existing imported documents can contain an invalid child. Do not introduce a
  // discontinuous jump on pointer-down; allow movement back toward the parent.
  minimumX = Math.min(minimumX, 0);
  maximumX = Math.max(maximumX, 0);
  minimumY = Math.min(minimumY, 0);
  maximumY = Math.max(maximumY, 0);

  return {
    x: clamp(requested.x, minimumX, maximumX),
    y: clamp(requested.y, minimumY, maximumY),
  };
}
