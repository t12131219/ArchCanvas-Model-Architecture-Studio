import type { LabScene } from "./types";

export interface LayoutWorkerNode {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface LayoutWorkerEdge {
  id: string;
  sourceId: string;
  targetId: string;
}

export interface LayoutWorkerRequest {
  type: "layout";
  requestId: string;
  direction: "RIGHT" | "UP";
  nodes: LayoutWorkerNode[];
  edges: LayoutWorkerEdge[];
}

export interface LayoutWorkerSuccess {
  type: "layout-complete";
  requestId: string;
  durationMs: number;
  positions: Array<{ id: string; x: number; y: number }>;
}

export interface LayoutWorkerFailure {
  type: "layout-failed";
  requestId: string;
  message: string;
}

export type LayoutWorkerResponse = LayoutWorkerSuccess | LayoutWorkerFailure;

export function layoutRequestForScene(scene: LabScene, requestId: string): LayoutWorkerRequest {
  const nodeIds = new Set(scene.nodes.map((node) => node.scene_node_id));
  return {
    type: "layout",
    requestId,
    direction: scene.layout_profile === "paper" ? "UP" : "RIGHT",
    nodes: scene.nodes.map((node) => ({
      id: node.scene_node_id,
      ...node.bounds,
    })),
    edges: scene.edges.flatMap((edge) => (
      nodeIds.has(edge.source_scene_node_id)
      && nodeIds.has(edge.target_scene_node_id)
      && edge.source_scene_node_id !== edge.target_scene_node_id
        ? [{
          id: edge.scene_edge_id,
          sourceId: edge.source_scene_node_id,
          targetId: edge.target_scene_node_id,
        }]
        : []
    )),
  };
}

export function sceneGeometryFingerprint(scene: LabScene): string {
  return JSON.stringify({
    id: scene.scene_id,
    nodes: scene.nodes.map((node) => [
      node.scene_node_id,
      node.bounds.x,
      node.bounds.y,
      node.bounds.width,
      node.bounds.height,
    ]),
    edges: scene.edges.map((edge) => [
      edge.scene_edge_id,
      edge.source_scene_node_id,
      edge.target_scene_node_id,
    ]),
  });
}
