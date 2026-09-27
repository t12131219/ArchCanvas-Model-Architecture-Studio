import type { KernelNodeShape, KernelRelation } from "./types";

export interface RelationToken {
  label: string;
  color: string;
  dash?: string;
}

export const RELATION_TOKENS: Record<KernelRelation, RelationToken> = {
  sequence: { label: "Flow", color: "#39444d" },
  "parallel-branch": { label: "Branch", color: "#266d66" },
  merge: { label: "Merge", color: "#725b19" },
  residual: { label: "Residual", color: "#b33d5a", dash: "7 5" },
  "memory-reference": { label: "Memory", color: "#7756a2", dash: "4 3" },
  condition: { label: "Condition", color: "#a35416" },
  "state-update": { label: "State", color: "#2467a5", dash: "7 4" },
  "shape-transform": { label: "Transform", color: "#6b4aa5" },
  routing: { label: "Routing", color: "#b05c12" },
  "parameter-share": { label: "Shared", color: "#a23f73", dash: "3 3" },
  "training-only": { label: "Training", color: "#7a7d80", dash: "5 5" },
};

export const NODE_TOKENS: Record<KernelNodeShape, { fill: string; stroke: string }> = {
  operation: { fill: "#f7f9fa", stroke: "#64727d" },
  container: { fill: "#edf7f5", stroke: "#397b73" },
  tensor: { fill: "#eef5fb", stroke: "#4f7896" },
  convolution: { fill: "#edf7f5", stroke: "#397b73" },
  attention: { fill: "#fff3e8", stroke: "#a5652e" },
  normalization: { fill: "#eaf6f1", stroke: "#397662" },
  condition: { fill: "#fbf0f8", stroke: "#966487" },
  merge: { fill: "#f8f2df", stroke: "#8d742d" },
  add: { fill: "#fff4cf", stroke: "#8d742d" },
  multiply: { fill: "#fcebdc", stroke: "#a35416" },
  concat: { fill: "#eeeaf8", stroke: "#72549b" },
  io: { fill: "#f8edf1", stroke: "#9b5268" },
};
