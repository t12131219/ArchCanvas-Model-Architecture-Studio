export interface ScenePoint {
  x: number;
  y: number;
}

interface SceneBounds extends ScenePoint {
  width: number;
  height: number;
}

export interface IndexableSceneNode {
  scene_node_id: string;
  parent_scene_node_id?: string;
  shape: string;
  bounds: SceneBounds;
}

export interface RoutableSceneEdge {
  source_scene_node_id: string;
  target_scene_node_id: string;
  points: ScenePoint[];
}

export interface SceneRenderIndex<Node extends IndexableSceneNode> {
  byId: ReadonlyMap<string, Node>;
  depths: ReadonlyMap<string, number>;
  roots: readonly Node[];
  containers: readonly Node[];
  leaves: readonly Node[];
}

export function buildSceneRenderIndex<Node extends IndexableSceneNode>(
  nodes: readonly Node[],
): SceneRenderIndex<Node> {
  const byId = new Map(nodes.map((node) => [node.scene_node_id, node]));
  const depths = new Map<string, number>();
  const visiting = new Set<string>();

  const depthOf = (node: Node): number => {
    const cached = depths.get(node.scene_node_id);
    if (cached !== undefined) return cached;
    if (visiting.has(node.scene_node_id)) return 0;
    visiting.add(node.scene_node_id);
    const parent = node.parent_scene_node_id ? byId.get(node.parent_scene_node_id) : undefined;
    const depth = parent ? depthOf(parent) + 1 : 0;
    visiting.delete(node.scene_node_id);
    depths.set(node.scene_node_id, depth);
    return depth;
  };

  const roots: Node[] = [];
  const containers: Node[] = [];
  const leaves: Node[] = [];
  for (const node of nodes) {
    depthOf(node);
    if (!node.parent_scene_node_id) roots.push(node);
    else if (node.shape === "container") containers.push(node);
    else leaves.push(node);
  }
  return { byId, depths, roots, containers, leaves };
}

export function previewNodeTransform(
  node: IndexableSceneNode,
  position: ScenePoint,
): string {
  return `translate(${position.x - node.bounds.x} ${position.y - node.bounds.y})`;
}

export function edgeLabelPoint(edge: { points: readonly ScenePoint[] }): ScenePoint {
  const horizontal = edge.points.slice(0, -1).map((point, index) => ({
    start: point,
    end: edge.points[index + 1],
    length: Math.abs(edge.points[index + 1].x - point.x),
  })).filter((segment) => Math.abs(segment.start.y - segment.end.y) < 0.1).sort((a, b) => b.length - a.length)[0];
  if (horizontal) return { x: (horizontal.start.x + horizontal.end.x) / 2, y: horizontal.start.y - 7 };
  const start = edge.points[0];
  const end = edge.points.at(-1)!;
  return { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 - 7 };
}

export function previewEdgePoints(
  edge: RoutableSceneEdge,
  nodesById: ReadonlyMap<string, IndexableSceneNode>,
  preview: Readonly<Record<string, ScenePoint>>,
  index: number,
): ScenePoint[] {
  const source = nodesById.get(edge.source_scene_node_id);
  const target = nodesById.get(edge.target_scene_node_id);
  if (!source || !target) return edge.points;
  const sourcePreview = preview[source.scene_node_id];
  const targetPreview = preview[target.scene_node_id];
  const sourceDelta = sourcePreview
    ? { x: sourcePreview.x - source.bounds.x, y: sourcePreview.y - source.bounds.y }
    : { x: 0, y: 0 };
  const targetDelta = targetPreview
    ? { x: targetPreview.x - target.bounds.x, y: targetPreview.y - target.bounds.y }
    : { x: 0, y: 0 };
  if (!sourcePreview && !targetPreview) return edge.points;
  if (
    sourcePreview
    && targetPreview
    && Math.abs(sourceDelta.x - targetDelta.x) < 0.01
    && Math.abs(sourceDelta.y - targetDelta.y) < 0.01
  ) {
    return edge.points.map((point) => ({
      x: point.x + sourceDelta.x,
      y: point.y + sourceDelta.y,
    }));
  }
  const sourceBounds = { ...source.bounds, ...(sourcePreview ?? {}) };
  const targetBounds = { ...target.bounds, ...(targetPreview ?? {}) };
  const start = {
    x: sourceBounds.x + sourceBounds.width,
    y: sourceBounds.y + sourceBounds.height / 2,
  };
  const end = {
    x: targetBounds.x,
    y: targetBounds.y + targetBounds.height / 2,
  };
  if (edge.points.length >= 6 || end.x <= start.x + 30) {
    const corridorY = Math.min(...edge.points.map((point) => point.y));
    const targetStubX = Math.max(24, end.x - 24);
    return [
      start,
      { x: start.x + 24, y: start.y },
      { x: start.x + 24, y: corridorY },
      { x: targetStubX, y: corridorY },
      { x: targetStubX, y: end.y },
      end,
    ];
  }
  const corridorX = (start.x + end.x) / 2 + ((index % 5) - 2) * 5;
  return [
    start,
    { x: corridorX, y: start.y },
    { x: corridorX, y: end.y },
    end,
  ];
}
