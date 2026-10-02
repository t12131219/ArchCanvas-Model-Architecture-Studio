import type { Bounds, LabNode } from "./types";

export type AlignmentCommand = "left" | "horizontal-center" | "top" | "vertical-center";
export type DistributionCommand = "horizontal" | "vertical";

function centerX(bounds: Bounds): number {
  return bounds.x + bounds.width / 2;
}

function centerY(bounds: Bounds): number {
  return bounds.y + bounds.height / 2;
}

export function alignNodeBounds(
  nodes: readonly LabNode[],
  command: AlignmentCommand,
  pinnedIds: ReadonlySet<string> = new Set(),
): Map<string, Bounds> {
  if (nodes.length < 2) return new Map();
  const target = command === "left"
    ? Math.min(...nodes.map((node) => node.bounds.x))
    : command === "horizontal-center"
      ? nodes.reduce((sum, node) => sum + centerX(node.bounds), 0) / nodes.length
      : command === "top"
        ? Math.min(...nodes.map((node) => node.bounds.y))
        : nodes.reduce((sum, node) => sum + centerY(node.bounds), 0) / nodes.length;
  return new Map(nodes.flatMap((node) => {
    if (pinnedIds.has(node.scene_node_id)) return [];
    const bounds = { ...node.bounds };
    if (command === "left") bounds.x = target;
    if (command === "horizontal-center") bounds.x = target - bounds.width / 2;
    if (command === "top") bounds.y = target;
    if (command === "vertical-center") bounds.y = target - bounds.height / 2;
    return [[node.scene_node_id, bounds] as const];
  }));
}

export function distributeNodeBounds(
  nodes: readonly LabNode[],
  command: DistributionCommand,
  pinnedIds: ReadonlySet<string> = new Set(),
): Map<string, Bounds> {
  if (nodes.length < 3) return new Map();
  const coordinate = command === "horizontal" ? centerX : centerY;
  const ordered = [...nodes].sort((left, right) => (
    coordinate(left.bounds) - coordinate(right.bounds)
    || left.scene_node_id.localeCompare(right.scene_node_id)
  ));
  const first = coordinate(ordered[0].bounds);
  const step = (coordinate(ordered.at(-1)!.bounds) - first) / (ordered.length - 1);
  return new Map(ordered.flatMap((node, index) => {
    if (index === 0 || index === ordered.length - 1 || pinnedIds.has(node.scene_node_id)) return [];
    const bounds = { ...node.bounds };
    const next = first + step * index;
    if (command === "horizontal") bounds.x = next - bounds.width / 2;
    else bounds.y = next - bounds.height / 2;
    return [[node.scene_node_id, bounds] as const];
  }));
}
