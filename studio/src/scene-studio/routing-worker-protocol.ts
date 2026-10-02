import type {
  LabScene,
  RouteStyle,
  RoutedEdge,
  SceneBoundaryPortMap,
  SceneMetrics,
} from "./types";

export interface RoutingWorkerRequest {
  type: "route";
  requestId: string;
  scene: LabScene;
  style: RouteStyle;
  boundaryPorts?: SceneBoundaryPortMap;
}

export interface RoutingWorkerSuccess {
  type: "route-complete";
  requestId: string;
  durationMs: number;
  routes: RoutedEdge[];
  metrics: SceneMetrics;
}

export interface RoutingWorkerFailure {
  type: "route-failed";
  requestId: string;
  message: string;
}

export type RoutingWorkerResponse = RoutingWorkerSuccess | RoutingWorkerFailure;

export function routingFingerprint(
  scene: LabScene,
  style: RouteStyle,
  boundaryPorts?: SceneBoundaryPortMap,
): string {
  return JSON.stringify({
    scene: {
      id: scene.scene_id,
      width: scene.paper_width,
      height: scene.paper_height,
      profile: scene.layout_profile,
      nodes: scene.nodes.map((node) => [
        node.scene_node_id,
        node.bounds.x,
        node.bounds.y,
        node.bounds.width,
        node.bounds.height,
        node.detail_expanded ?? false,
      ]),
      edges: scene.edges.map((edge) => [
        edge.scene_edge_id,
        edge.source_scene_node_id,
        edge.target_scene_node_id,
        edge.relation,
        edge.label,
        edge.target_port_role,
      ]),
    },
    style,
    boundaryPorts,
  });
}
