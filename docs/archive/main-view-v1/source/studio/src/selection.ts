export interface SelectionPoint {
  x: number;
  y: number;
}

export interface SelectionBounds extends SelectionPoint {
  width: number;
  height: number;
}

interface SelectableNode {
  scene_node_id: string;
  parent_scene_node_id?: string;
  bounds: SelectionBounds;
}

export function selectionBounds(
  start: SelectionPoint,
  current: SelectionPoint,
): SelectionBounds {
  return {
    x: Math.min(start.x, current.x),
    y: Math.min(start.y, current.y),
    width: Math.abs(current.x - start.x),
    height: Math.abs(current.y - start.y),
  };
}

export function nodesInSelection<T extends SelectableNode>(
  nodes: T[],
  bounds: SelectionBounds,
): string[] {
  const right = bounds.x + bounds.width;
  const bottom = bounds.y + bounds.height;
  return nodes
    .filter((node) => {
      if (!node.parent_scene_node_id) return false;
      const nodeRight = node.bounds.x + node.bounds.width;
      const nodeBottom = node.bounds.y + node.bounds.height;
      return (
        node.bounds.x >= bounds.x
        && node.bounds.y >= bounds.y
        && nodeRight <= right
        && nodeBottom <= bottom
      );
    })
    .map((node) => node.scene_node_id);
}
