import type { Bounds, LabPatch, LabScene } from "./types";

export function cloneScene(scene: LabScene): LabScene {
  return {
    ...scene,
    nodes: scene.nodes.map((node) => ({ ...node, bounds: { ...node.bounds } })),
    edges: scene.edges.map((edge) => ({ ...edge })),
  };
}

export function applyVisualPatch(scene: LabScene, patch: LabPatch): LabScene {
  if (patch.operation === "add-node") {
    return { ...scene, nodes: [...scene.nodes, patch.node] };
  }
  if (patch.operation === "update-node") {
    return {
      ...scene,
      nodes: scene.nodes.map((node) => node.scene_node_id === patch.nodeId
        ? {
          ...node,
          ...patch.changes,
          bounds: patch.changes.bounds ? { ...patch.changes.bounds } : node.bounds,
        }
        : node),
    };
  }
  if (patch.operation === "remove-node") {
    return {
      ...scene,
      nodes: scene.nodes.filter((node) => node.scene_node_id !== patch.nodeId),
      edges: scene.edges.filter((edge) => (
        edge.source_scene_node_id !== patch.nodeId && edge.target_scene_node_id !== patch.nodeId
      )),
    };
  }
  if (patch.operation === "add-edge") {
    const sourceExists = scene.nodes.some((node) => node.scene_node_id === patch.edge.source_scene_node_id);
    const targetExists = scene.nodes.some((node) => node.scene_node_id === patch.edge.target_scene_node_id);
    if (!sourceExists || !targetExists || patch.edge.source_scene_node_id === patch.edge.target_scene_node_id) return scene;
    return { ...scene, edges: [...scene.edges, patch.edge] };
  }
  if (patch.operation === "update-edge") {
    return {
      ...scene,
      edges: scene.edges.map((edge) => edge.scene_edge_id === patch.edgeId
        ? { ...edge, ...patch.changes }
        : edge),
    };
  }
  return { ...scene, edges: scene.edges.filter((edge) => edge.scene_edge_id !== patch.edgeId) };
}

export function clampBounds(bounds: Bounds, scene: LabScene): Bounds {
  const width = Math.max(72, Math.min(320, bounds.width));
  const height = Math.max(42, Math.min(180, bounds.height));
  return {
    x: Math.max(12, Math.min(scene.paper_width - width - 12, bounds.x)),
    y: Math.max(12, Math.min(scene.paper_height - height - 12, bounds.y)),
    width,
    height,
  };
}
