export interface Point {
  x: number;
  y: number;
}

export interface Size {
  width: number;
  height: number;
}

export interface Bounds extends Point, Size {}

export type KernelRelation =
  | "sequence"
  | "parallel-branch"
  | "merge"
  | "residual"
  | "memory-reference"
  | "condition"
  | "state-update"
  | "shape-transform"
  | "routing"
  | "parameter-share"
  | "training-only";

export type KernelNodeShape =
  | "operation"
  | "container"
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

export type RouteStyle = "adaptive" | "direct" | "orthogonal" | "channel" | "curve";
export type NodeVisualStyle = "semantic" | "technical" | "compact";
export type EdgeLabelStyle = "plain" | "plate" | "endpoint";
export type KernelRenderRole = "atomic" | "collapsed-module" | "expanded-module";

export interface KernelPort {
  portId: string;
  ownerNodeId: string;
  direction: "input" | "output";
  role: string;
  evidenceIds: string[];
}

export interface KernelNode {
  nodeId: string;
  hierarchyNodeId: string;
  parentNodeId?: string;
  parentModuleId?: string;
  childNodeIds: string[];
  depth: number;
  expanded: boolean;
  renderRole: KernelRenderRole;
  canonicalNodeIds: string[];
  containedCanonicalNodeIds: string[];
  label: string;
  secondaryLabel?: string;
  semanticKind: string;
  shape: KernelNodeShape;
  inputPortIds: string[];
  outputPortIds: string[];
  evidenceIds: string[];
  templateBindingId?: string;
  synthetic: boolean;
}

export interface KernelEdge {
  edgeId: string;
  canonicalEdgeIds: string[];
  sourcePortId: string;
  targetPortId: string;
  relation: KernelRelation;
  semanticChannel: string;
  tensorIds: string[];
  label: string;
  evidenceIds: string[];
}

export interface KernelModule {
  moduleId: string;
  hierarchyNodeId: string;
  hostNodeId: string;
  parentModuleId?: string;
  childModuleIds: string[];
  nodeIds: string[];
  label: string;
  evidenceIds: string[];
}

export interface KernelDocument {
  documentId: string;
  architectureId: string;
  sourceDigest: string;
  nodes: KernelNode[];
  ports: KernelPort[];
  edges: KernelEdge[];
  modules: KernelModule[];
  templateBindings: KernelTemplateBinding[];
  diagnostics: KernelDiagnostic[];
}

export interface KernelTemplateBinding {
  bindingId: string;
  templateId: string;
  templateVersion?: string;
  fidelity: "exact" | "opaque" | "schematic";
  rootCanonicalNodeIds: string[];
  canonicalNodeIds: string[];
  nodeSlots: Record<string, string[]>;
  edgeSlots: Record<string, string[]>;
  portSlots: Record<string, string[]>;
  tensorSlots: Record<string, string[]>;
  evidenceIds: string[];
  predicateIds: string[];
  bindingDigest?: string;
}

export interface KernelDiagnostic {
  code: string;
  severity: "info" | "warning" | "blocking";
  message: string;
  targetIds: string[];
}

export interface KernelVisualState {
  expandedModuleIds: string[];
  nodePositions: Record<string, Point>;
  nodeSizes: Record<string, Size>;
  detailOffsets: Record<string, Point>;
  pinnedNodeIds: string[];
  routeHints: Record<string, Point[]>;
  routeStyle: RouteStyle;
  nodeStyle: NodeVisualStyle;
  labelStyle: EdgeLabelStyle;
  nodeShapeOverrides?: Record<string, KernelNodeShape>;
}

export interface RenderNode extends KernelNode {
  bounds: Bounds;
}

export interface RenderEdge extends KernelEdge {
  points: Point[];
  path: string;
  labelPoint: Point;
  labelAngle: number;
}

export interface RenderPortal {
  portalId: string;
  moduleNodeId: string;
  edgeId: string;
  direction: "entry" | "exit";
  point: Point;
}

export type DetailTone = "neutral" | "blue" | "green" | "pink" | "orange" | "violet";

export type RenderDetailPrimitive =
  | { primitiveId: string; kind: "box"; slotId: string; canonicalIds: string[]; x: number; y: number; width: number; height: number; label: string; note?: string; tone: DetailTone }
  | { primitiveId: string; kind: "matrix"; slotId: string; canonicalIds: string[]; x: number; y: number; width: number; height: number; label: string; columns: number; rows: number; depth: number; tone: DetailTone }
  | { primitiveId: string; kind: "operator"; slotId: string; canonicalIds: string[]; cx: number; cy: number; radius: number; label: string; tone: DetailTone }
  | { primitiveId: string; kind: "flow"; slotId: string; canonicalIds: string[]; points: Point[]; tone: DetailTone; marker: boolean }
  | { primitiveId: string; kind: "text"; slotId: string; canonicalIds: string[]; x: number; y: number; value: string; emphasis: boolean; tone: DetailTone };

export interface RenderTemplateDetail {
  nodeId: string;
  bindingId: string;
  templateId: string;
  evidenceIds: string[];
  bounds: Bounds;
  entryPoint: Point;
  exitPoint: Point;
  primitives: RenderDetailPrimitive[];
}

export interface KernelRenderScene {
  sceneId: string;
  sourceDigest: string;
  width: number;
  height: number;
  nodes: RenderNode[];
  edges: RenderEdge[];
  portals: RenderPortal[];
  details: RenderTemplateDetail[];
  diagnostics: KernelDiagnostic[];
}
