export interface Point {
  x: number;
  y: number;
}

export interface Bounds extends Point {
  width: number;
  height: number;
}

export type NodeShape =
  | "operation"
  | "tensor"
  | "convolution"
  | "attention"
  | "normalization"
  | "condition"
  | "merge"
  | "add"
  | "multiply"
  | "concat"
  | "io";

export type NodeDetailKind =
  | "attention"
  | "feedforward"
  | "add-norm"
  | "convolution"
  | "tensor-transform"
  | "embedding"
  | "recurrent"
  | "mixture-of-experts"
  | "pooling"
  | "linear-model"
  | "kernel-machine"
  | "decision-tree"
  | "ensemble"
  | "clustering"
  | "decomposition"
  | "mlp"
  | "normalization"
  | "residual-block"
  | "dense-connection"
  | "inception"
  | "depthwise-convolution"
  | "unet"
  | "vision-transformer"
  | "gru"
  | "bidirectional-recurrent"
  | "seq2seq"
  | "state-space"
  | "autoencoder"
  | "variational-autoencoder"
  | "gan"
  | "diffusion"
  | "normalizing-flow"
  | "graph-message-passing"
  | "time-series-forecast"
  | "dual-encoder"
  | "dqn"
  | "actor-critic"
  | "distillation"
  | "adapter-lora";

export interface LabNode {
  scene_node_id: string;
  bounds: Bounds;
  shape: NodeShape;
  label: string;
  secondary_label: string;
  detail_kind?: NodeDetailKind;
  detail_expanded?: boolean;
}

export type EdgeRelation =
  | "flow"
  | "branch"
  | "merge"
  | "residual"
  | "memory"
  | "condition"
  | "feedback";

export interface LabEdge {
  scene_edge_id: string;
  source_scene_node_id: string;
  target_scene_node_id: string;
  relation: EdgeRelation;
  label: string;
}

export interface LabScene {
  scene_id: string;
  title: string;
  description: string;
  paper_width: number;
  paper_height: number;
  nodes: LabNode[];
  edges: LabEdge[];
}

export type RouteStyle = "direct" | "orthogonal" | "channel" | "curve" | "adaptive";
export type HierarchyRoutingMode = "recursive" | "atomic-bottom-up";
export type NodeVisualStyle = "semantic" | "technical" | "compact";
export type EdgeLabelStyle = "plain" | "plate" | "endpoint";
export type PortSide = "left" | "right" | "top" | "bottom";

export interface SceneBoundaryPorts {
  entry: Point;
  exit: Point;
  entrySide?: PortSide;
  exitSide?: PortSide;
  entryIsInterior?: boolean;
  exitIsInterior?: boolean;
}

export type SceneBoundaryPortMap = Record<string, SceneBoundaryPorts>;

export interface VisualOptions {
  routeStyle: RouteStyle;
  nodeStyle: NodeVisualStyle;
  labelStyle: EdgeLabelStyle;
}

export interface RoutedEdge {
  edge: LabEdge;
  points: Point[];
  path: string;
  labelPoint: Point;
  labelAngle: number;
  sourceSide: PortSide;
  targetSide: PortSide;
  markerEnd?: boolean;
  foreground?: boolean;
}

export interface SceneMetrics {
  crossings: number;
  overlaps: number;
  nodeIntersections: number;
  labelIntersections: number;
  clearanceViolations: number;
  endpointCongestion: number;
  reverseExits: number;
  sharedLength: number;
  bends: number;
  routeLength: number;
}

export type LabPatch =
  | { operation: "add-node"; node: LabNode }
  | { operation: "update-node"; nodeId: string; changes: Partial<Omit<LabNode, "scene_node_id">> }
  | { operation: "remove-node"; nodeId: string }
  | { operation: "add-edge"; edge: LabEdge }
  | { operation: "update-edge"; edgeId: string; changes: Partial<Omit<LabEdge, "scene_edge_id">> }
  | { operation: "remove-edge"; edgeId: string };

export type Selection =
  | { kind: "node"; id: string }
  | { kind: "edge"; id: string }
  | null;
