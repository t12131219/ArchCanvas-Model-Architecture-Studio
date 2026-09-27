import type { StudioJob } from "../jobs";

export type Projection = "module" | "source";
export type LayoutMode = "auto" | "dual-swimlane" | "single-lane" | "hierarchical" | "branch-tree" | "force-directed" | "radial" | "orthogonal";
export type DraftEdgePolicy = "replace-input" | "add-residual" | "concat" | "fanout" | "disconnect";

export interface NavigationNode {
  id: string;
  parent_id: string | null;
  kind: string;
  label: string;
  depth: number;
  relation: string;
  canonical_ids: string[];
  evidence_ids: string[];
  path?: string | null;
  span?: { start_line: number; end_line: number; start_column: number; end_column: number } | null;
  reference: boolean;
  secondary_label?: string | null;
  binding_status: "exact" | "ambiguous" | "unbound";
  child_count: number;
  sibling_index: number;
  sibling_count: number;
}

export interface PublicationNode {
  view_node_id: string;
  semantic_name: string;
  canonical_node_ids: string[];
  collapsed: boolean;
  attributes: Record<string, unknown>;
}

export interface PublicationView {
  projection_id: string;
  frontier_digest: string;
  visible_depth: number;
  max_depth: number;
  fully_expanded: boolean;
  name: string;
  nodes: PublicationNode[];
}

export interface Evidence {
  evidence_id: string;
  kind: string;
  path?: string;
  symbol?: string;
  claim: string;
  confidence: string;
  span?: { start_line: number; end_line: number };
  runtime_trace_id?: string;
  runtime_observation_ids?: string[];
}

export interface Diagnostic {
  code: string;
  severity: string;
  message: string;
  target_ids: string[];
}

export interface ArchitectureParameter {
  name: string;
  source_expression: string;
  value: unknown;
  origin: string;
  evidence_ids: string[];
}

export interface ArchitecturePort {
  port_id: string;
  name: string;
  direction: "input" | "output";
  role: string;
}

export interface ArchitectureNodeView {
  node_id: string;
  semantic_name: string;
  kind: string;
  source_symbol?: string;
  parent_id?: string;
  confidence: string;
  evidence_ids: string[];
  attributes: Record<string, unknown>;
  parameters: ArchitectureParameter[];
  input_ports: ArchitecturePort[];
  output_ports: ArchitecturePort[];
}

export interface ArchitectureTensor {
  tensor_id: string;
  role: string;
  producer_id: string;
  consumer_ids: string[];
  symbolic_shape: string;
  semantic_axes: string[];
  dtype: string;
  confidence: string;
}

export interface HierarchyNode {
  hierarchy_node_id: string;
  parent_hierarchy_node_id?: string;
  semantic_name: string;
  depth: number;
  canonical_node_ids: string[];
}

export interface SourceExcerpt {
  path: string;
  sha256: string;
  revision: string;
  start_line: number;
  end_line: number;
  highlight_start_line: number;
  highlight_end_line: number;
  lines: Array<{ number: number; text: string }>;
}

export interface GraphDelta {
  added_nodes: string[];
  removed_nodes: string[];
  changed_nodes: string[];
  added_edges: string[];
  removed_edges: string[];
  changed_edges: string[];
  added_ports: string[];
  removed_ports: string[];
  changed_ports: string[];
  added_tensors: string[];
  removed_tensors: string[];
  changed_tensors: string[];
  added_fanouts: string[];
  removed_fanouts: string[];
  changed_fanouts: string[];
  added_config_predicates: string[];
  removed_config_predicates: string[];
  changed_config_predicates: string[];
  changed_parameters: Array<{
    node_id: string;
    parameter_name: string;
    before: unknown;
    after: unknown;
    source_expression: string;
  }>;
  changed_shapes: Array<{ subject_id: string; before: string; after: string }>;
}

export interface SourceTransaction {
  transaction_id: string;
  state: string;
  request: {
    target_node_id?: string;
    operation: "set_parameter" | "replace_activation" | "insert_layer_norm" | "edit_source_buffers";
    parameter_name?: string;
    new_value?: unknown;
    parameters?: Record<string, unknown>;
    buffers?: Array<{ path: string; base_sha256: string; content: string }>;
  };
  source_diff: string;
  expected_delta: GraphDelta;
  observed_delta?: GraphDelta;
  gates: Array<{ gate: string; status: string; message: string }>;
  diagnostics: Diagnostic[];
}

export interface AgentProposal {
  proposal_id: string;
  status: "handoff-required";
  reason_code: string;
  summary: string;
  source_context: Record<string, unknown>;
  permissions: { shell: false; network: false; source_write: false };
}

export interface SourceWorkspaceFile {
  path: string;
  base_sha256: string;
  staged_sha256: string | null;
  working_sha256: string | null;
  state: "clean" | "modified" | "stale" | "readonly";
  opened: boolean;
  size: number;
  readonly_reason: string | null;
}

export interface SourceWorkspaceBuffer {
  path: string;
  revision: number;
  base_sha256: string;
  staged_sha256: string;
  working_sha256: string;
  state: "clean" | "modified" | "stale";
  base_content: string;
  staged_content: string;
  working_content: string;
  diff: string;
}

export interface CanonicalDeleteImpact {
  node_id: string;
  semantic_name: string;
  input_fingerprint: string;
  incoming_edge_ids: string[];
  outgoing_edge_ids: string[];
  produced_tensor_ids: string[];
  downstream_node_ids: string[];
  fanout_ids: string[];
  shared_parameter_node_ids: string[];
  child_node_ids: string[];
  repeat_id: string | null;
  execution_predicate: string;
  source_evidence_ids: string[];
  runtime_evidence_ids: string[];
  expected_delta: GraphDelta;
  required_action: string;
  blocking_reasons: string[];
}

export interface StudioState {
  session_nonce?: string;
  project: {
    project_id: string;
    root: string;
    generation: number;
    framework: string;
    environment_path?: string | null;
    python_executable?: string | null;
  };
  architecture: {
    architecture_id: string;
    entrypoint: string;
    nodes: ArchitectureNodeView[];
    tensors: ArchitectureTensor[];
  };
  snapshot: {
    project_root: string;
    entrypoint: string;
    revision: string;
    source_files: Array<{ path: string; sha256: string }>;
  };
  hierarchy: { root_node_id: string; max_depth: number; nodes: HierarchyNode[] };
  evidence: Evidence[];
  runtime: {
    trace: {
      trace_id: string;
      environment: { selected_device: string; torch_version: string };
      observations: unknown[];
    };
    node_evidence: Record<string, string[]>;
  } | null;
  active_projection_id: string;
  views: Record<string, PublicationView>;
  document: {
    source_digest: string;
    visual_patches: unknown[];
    redo_patches: unknown[];
  };
  integrity?: { source_digest: string; exact_ir_digest: string };
  view_state: {
    navigation_view?: Projection;
    layout_mode?: LayoutMode;
    pinned_node_ids?: string[];
    collapsed_node_ids?: string[];
    theme?: string;
    cameras?: Record<string, { x: number; y: number; zoom: number }>;
    module_expansion?: string[];
    source_expansion?: string[];
    font_scale?: number;
    line_weight?: number;
    palette_overrides?: Record<string, string>;
    caption?: string;
    legend_placement?: "top-left" | "top-right" | "bottom-left" | "bottom-right" | "hidden";
  };
  navigation: {
    active_projection: Projection;
    projections: Record<Projection, {
      projection_id: Projection;
      label: string;
      description: string;
      nodes: NavigationNode[];
    }>;
  };
  draft: {
    draft_id: string;
    revision: number;
    nodes: Array<{
      node_id: string;
      semantic_name: string;
      framework: string;
      node_type: string;
      parent_id?: string | null;
      source_anchor?: string | null;
      parameters: Record<string, unknown>;
      ports: Array<{
        port_id: string;
        name: string;
        direction: "input" | "output";
        role: string;
      }>;
    }>;
    edges: Array<{
      edge_id: string;
      source_port_id: string;
      target_port_id: string;
      policy: DraftEdgePolicy;
      parameters: Record<string, unknown>;
    }>;
    intents: Array<{
      intent_id: string;
      kind: "create-node" | "delete-node" | "connect-ports" | "disconnect-edge" | "replace-node" | "set-parameter" | "edit-source-buffer" | "edit-onnx-initializer" | "edit-onnx-attribute";
      target_ids: string[];
      expected_delta: GraphDelta | null;
      user_input: Record<string, unknown>;
      capability_requirement: string;
    }>;
    lowering_status: "not-planned" | "checking" | "planned" | "blocked";
    proofs: Array<{
      intent_id: string;
      status: "checking" | "conditional" | "unproven" | "invalid" | "stale" | "proven" | "review-ready";
      message: string;
      reason_codes: string[];
      affected_subject_ids: string[];
    }>;
    writeback_summary: { eligibility: "blocked" | "prepare" | "commit"; blocking_intent_ids: string[] };
  };
  source_workspace: {
    workspace_id: string;
    revision: number;
    base_revision: string;
    state: "clean" | "modified" | "stale";
    files: SourceWorkspaceFile[];
  };
  validation_runs: Array<{
    validation_id: string;
    profile: string;
    state: string;
    input_fingerprint: string;
    gate_results: Array<{ gate: string; status: string; message: string }>;
    diagnostics: Diagnostic[];
  }>;
  jobs?: StudioJob<Diagnostic>[];
  diagnostics: Diagnostic[];
  transaction: SourceTransaction | null;
  proposal: AgentProposal | null;
  capabilities: {
    visual_editing: boolean;
    source_editing: boolean;
    runtime_evidence: boolean;
    semantic_transforms: string[];
    proposed_connection: boolean;
  };
}
