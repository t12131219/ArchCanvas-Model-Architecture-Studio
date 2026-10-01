import type { DefinitionRef } from "../module-registry/types";

export type DimensionValue =
  | { kind: "known"; value: number }
  | { kind: "symbol"; symbol: string }
  | { kind: "expression"; expression: string }
  | { kind: "unknown"; reason: string };

export interface ShapeValue {
  dimensions: DimensionValue[];
  dtype?: string;
  layout?: "NCHW" | "NHWC" | "sequence" | "scalar" | "any";
  constraints: string[];
}

export type AnalyzedValue =
  | { status: "known"; shape: ShapeValue }
  | { status: "unknown"; reason: string; constraints: string[] }
  | { status: "blocked"; causedByDiagnosticIds: string[] };

export interface GraphDiagnostic {
  diagnosticId: string;
  code: string;
  severity: "info" | "warning" | "blocking";
  message: string;
  targetIds: string[];
  relatedPortIds: string[];
}

export interface CostEstimate {
  parameterCount: string | null;
  flops: string | null;
  assumptions: string[];
}

export interface PrototypePort {
  port_id: string;
  name: string;
  direction: "input" | "output";
  definition_port_id?: string | null;
  min_connections?: number;
  max_connections?: number | "many";
  ordering?: "ordered" | "unordered";
  accepted_relations?: string[];
  tensor_ranks?: number[];
  tensor_layouts?: Array<"NCHW" | "NHWC" | "sequence" | "scalar" | "any">;
}

export interface PrototypeNode {
  node_id: string;
  semantic_name?: string;
  definition_ref?: DefinitionRef | null;
  parameter_group_id?: string | null;
  parameters: Record<string, unknown>;
  ports: PrototypePort[];
}

export interface PrototypeEdge {
  edge_id: string;
  source_port_id: string;
  target_port_id: string;
  relation?: string;
  target_ordinal?: number | null;
}

export interface PrototypeGraphDocument {
  draft_id: string;
  base_registry_digest?: string | null;
  nodes: PrototypeNode[];
  edges: PrototypeEdge[];
}

export interface AnalysisSnapshot {
  documentDigest: string;
  registryDigest: string;
  nodeShapes: Record<string, Record<string, AnalyzedValue>>;
  diagnostics: GraphDiagnostic[];
  nodeCosts: Record<string, CostEstimate>;
  graphCost: CostEstimate;
}
