import type { LabScene } from "../types";
import type { StudioJob } from "../../jobs";

export type ViewPresetId =
  | "engineering-flow"
  | "paper-publication"
  | "paper-transformer"
  | "module-hierarchy"
  | "source-call"
  | "tensor-dataflow"
  | "compact-overview";

export interface ViewPreset {
  id: ViewPresetId;
  label: string;
  projection: "architecture" | "module" | "source" | "tensor";
  orientation: "left-to-right" | "top-to-bottom" | "bottom-to-top";
  layout: "incremental-flow" | "publication-structural" | "paper-dual-lane" | "hierarchical" | "compact";
  hierarchyDepth: number | "expanded-frontier";
  templateProfile: "engineering" | "paper" | "technical";
  edgePolicy: "semantic" | "all" | "main-flow";
}

export interface SceneBinding {
  sceneId: string;
  canonicalNodeIds: string[];
  canonicalEdgeIds: string[];
  sourceAnchorIds: string[];
  evidenceIds: string[];
  portBindings: Record<string, string>;
  fidelity: "exact" | "schematic" | "opaque";
  draftNodeIds?: string[];
  draftEdgeIds?: string[];
}

export interface SourceBackedScene extends LabScene {
  sourceProjectId: string;
  architectureId: string;
  sourceDigest: string;
  exactIrDigest: string;
  presetId: ViewPresetId;
  bindings: Record<string, SceneBinding>;
}

export interface ExactPort {
  port_id: string;
  name: string;
  direction: "input" | "output";
  role: string;
}

export interface ExactNode {
  node_id: string;
  semantic_name: string;
  kind: string;
  parent_id?: string | null;
  evidence_ids: string[];
  attributes: Record<string, unknown>;
  input_ports: ExactPort[];
  output_ports: ExactPort[];
  parameters?: Array<{
    name: string;
    source_expression: string;
    value: unknown;
    origin: string;
    evidence_ids: string[];
  }>;
}

export interface ExactEdge {
  edge_id: string;
  tensor_id: string;
  producer_id: string;
  producer_port: string;
  consumer_id: string;
  consumer_port: string;
  role: string;
  edge_type: string;
  evidence_ids: string[];
}

export type EditTargetScope =
  | "definition"
  | "module-instance"
  | "call-site"
  | "repeat-template"
  | "config-value"
  | "parameter-sharing-group"
  | "all-shared-uses";

export interface ParameterEditContext {
  context_id: string;
  target_node_id: string;
  parameter_name: string;
  current_value: unknown;
  value_origin: {
    origin_id: string;
    kind: string;
    source_anchor_ids: string[];
    config_path?: string | null;
    config_key_path: string[];
    confidence: "exact" | "conditional" | "unknown";
    editability: "direct" | "adapter-required" | "readonly";
    evidence_ids: string[];
  };
  allowed_scopes: EditTargetScope[];
  default_scope?: EditTargetScope | null;
  affected_canonical_ids: string[];
  blocking_reason?: string | null;
}

export interface HierarchyFact {
  hierarchy_node_id: string;
  parent_hierarchy_node_id?: string | null;
  semantic_name: string;
  kind?: string;
  depth: number;
  canonical_node_ids: string[];
  evidence_ids?: string[];
  attributes?: Record<string, unknown>;
}

export interface SemanticAnnotation {
  annotation_id: string;
  canonical_node_ids: string[];
  semantic_role: string;
  glyph?: string | null;
  layout_family?: string | null;
  evidence_ids?: string[];
}

export interface DraftPort {
  port_id: string;
  name: string;
  direction: "input" | "output";
  role: string;
  definition_port_id?: string | null;
  required?: boolean;
  min_connections?: number;
  max_connections?: number | "many";
  ordering?: "ordered" | "unordered";
  accepted_relations?: string[];
  tensor_ranks?: number[];
  tensor_layouts?: Array<"NCHW" | "NHWC" | "sequence" | "scalar" | "any">;
}

export interface DraftNode {
  node_id: string;
  semantic_name: string;
  framework: string;
  node_type: string;
  definition_ref?: { definition_id: string; version: string; digest: string } | null;
  parent_id?: string | null;
  source_anchor?: string | null;
  parameters: Record<string, unknown>;
  ports: DraftPort[];
}

export interface DraftEdge {
  edge_id: string;
  source_port_id: string;
  target_port_id: string;
  policy: "fanout" | "replace-input" | "add-residual" | "concat";
  relation?: string;
  target_ordinal?: number | null;
  parameters: Record<string, unknown>;
}

export interface DraftGraphState {
  draft_id: string;
  revision: number;
  base_registry_digest?: string | null;
  nodes: DraftNode[];
  edges: DraftEdge[];
  intents: Array<{
    intent_id: string;
    kind: string;
    target_ids: string[];
    expected_delta: Record<string, unknown> | null;
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
  writeback_summary: {
    eligibility: "blocked" | "prepare" | "commit";
    blocking_intent_ids: string[];
  };
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

export interface GeneratedProjectFile {
  path: string;
  sha256: string;
  size: number;
}

export interface RoundTripConformanceReport {
  schema_version: "1.0";
  report_id: string;
  path: "source-view" | "intent-source" | "draft-source";
  base_source_digest?: string | null;
  result_source_digest?: string | null;
  base_exact_ir_digest?: string | null;
  result_exact_ir_digest: string;
  draft_digest?: string | null;
  normalization_rule_digest: string;
  expected_delta_digest?: string | null;
  observed_delta_digest?: string | null;
  semantic_isomorphism: "exact" | "equivalent" | "failed";
  source_writes: string[];
  diagnostics: Array<{ code: string; severity: string; message: string; target_ids: string[] }>;
}

export interface StateMigrationPlan {
  schema_version: "1.0";
  plan_id: string;
  framework: "pytorch" | "keras" | "jax" | "onnx";
  base_source_digest: string;
  result_source_digest: string;
  source_state_digest: string;
  target_state_schema_digest: string;
  entries: Array<{
    old_state_key?: string | null;
    new_state_key?: string | null;
    action: "preserve" | "rename" | "reshape" | "initialize" | "drop" | "block";
    diagnostics: Array<{ code: string; severity: string; message: string; target_ids: string[] }>;
  }>;
  shared_identity_checks: string[];
  status: "verified" | "partial" | "blocked" | "not-requested";
}

export interface RecoveryReceipt {
  schema_version: "1.0";
  receipt_id: string;
  transaction_id: string;
  journal_id: string;
  outcome: "discarded" | "committed" | "rolled-back" | "recovery-failed";
  journal_state: string;
  before_state_proven: boolean;
  after_state_proven: boolean;
  source_writes: boolean;
  recovered_files: string[];
  diagnostics: Array<{ code: string; severity: string; message: string; target_ids: string[] }>;
  created_at: string;
}

export interface GeneratedProjectRecord {
  project_id: string;
  state: "generated-source-draft" | "statically-validated" | "review-ready" | "materialized" | "opened-and-reanalyzed" | "failed" | "discarded" | "stale";
  graph_digest: string;
  registry_digest: string;
  generator_version: string;
  target_framework: "pytorch";
  class_name: "GeneratedModel";
  entrypoint: "model:GeneratedModel";
  input_spec: Record<string, unknown>;
  files: GeneratedProjectFile[];
  source_map: Array<{
    origin_kind: "node" | "port" | "edge" | "parameter";
    origin_id: string;
    path: string;
    start_line: number;
    end_line: number;
  }>;
  receipt: {
    receipt_id: string;
    inventory_digest: string;
    status: "generated-source-draft" | "review-ready";
  };
  conformance_report?: RoundTripConformanceReport | null;
  materialization_receipt?: {
    receipt_id: string;
    target_directory: string;
    status: "opened-and-reanalyzed";
    source_project_id: string;
  } | null;
  diagnostics: Array<{ code: string; severity: string; message: string; target_ids: string[] }>;
}

export type StudioEditSession =
  | { mode: "visual"; document_id: string; current_document_digest: string }
  | {
    mode: "topology-draft";
    current_document_digest: string;
    capability: {
      capability_id: string;
      subject: string;
      draft_id: string;
      base_document_digest: string;
      allowed_commands: string[];
      issued_at: string;
      expires_at: string;
    };
  }
  | { mode: "contract-maintenance"; candidate_digest: string; capability: Record<string, unknown> };

export interface ContractMigration {
  migration_id: string;
  from_version: string;
  to_version: string;
  parameter_map: Record<string, string | null>;
  port_map: Record<string, string | null>;
  fixture_results: Array<{ fixture_id: string; status: "passed" | "failed"; message: string }>;
}

export interface ContractMaintenanceState {
  session: {
    mode: "contract-maintenance";
    candidate_digest: string;
    capability: {
      capability_id: string;
      base: { definition_id: string; version: string; digest: string };
    };
  } | null;
  draft: {
    draft_id: string;
    base: { definition_id: string; version: string; digest: string };
    candidate: Record<string, unknown>;
    candidate_digest: string;
    revision: number;
    state: "draft" | "validating" | "review-ready" | "approved" | "rejected";
    migration: ContractMigration | null;
  } | null;
  validation: {
    status: "passed" | "failed";
    validation_digest: string;
    diff: {
      compatibility: string;
      required_version_bump: string;
      changes: Array<{ subject: string; compatibility: string; message: string }>;
    };
    diagnostics: Array<{ code: string; message: string }>;
  } | null;
  review_receipt: {
    decision: "approved" | "rejected";
    reviewer: string;
    validation_digest: string;
  } | null;
  published: Array<Record<string, unknown>>;
}

export interface StudioStatePayload {
  session_nonce?: string;
  edit_session?: StudioEditSession;
  topology_review_receipt?: {
    receipt_id: string;
    draft_id: string;
    document_digest: string;
    registry_digest: string;
    status: "review-ready";
    submitted_at: string;
    diagnostics: Array<Record<string, unknown>>;
  } | null;
  generated_projects?: {
    generator_version: string;
    active: GeneratedProjectRecord | null;
    records: GeneratedProjectRecord[];
  } | null;
  round_trip_reports?: RoundTripConformanceReport[];
  recovery_receipts?: RecoveryReceipt[];
  contract_maintenance?: ContractMaintenanceState | null;
  analysis_environment?: {
    schema_version: "1.0";
    environment_manifest_digest: string;
    reproducibility_level: "locked" | "partially-locked" | "unlocked";
    framework_versions: Record<string, string | null>;
    lockfile_digests: Record<string, string>;
  } | null;
  analysis_input?: {
    schema_version: "2.0";
    analysis_input_digest: string;
    environment_manifest_digest: string;
    entry_invocation: {
      constructor_args: unknown[];
      constructor_kwargs: Record<string, unknown>;
      forward_args: unknown[];
      forward_kwargs: Record<string, unknown>;
      static_args: Record<string, unknown>;
      mode: "eval" | "train";
      input_structure: unknown;
    };
  } | null;
  project: {
    project_id: string;
    root: string;
    generation: number;
    framework: string;
  };
  architecture: {
    architecture_id: string;
    entrypoint: string;
    nodes: ExactNode[];
    edges: ExactEdge[];
  };
  parameter_edit_contexts?: ParameterEditContext[];
  snapshot: {
    project_root: string;
    entrypoint: string;
    revision: string;
    source_files: Array<{ path: string; sha256: string }>;
  };
  hierarchy: {
    root_node_id: string;
    max_depth?: number;
    nodes: HierarchyFact[];
  };
  evidence: Array<{
    evidence_id: string;
    kind: string;
    path?: string;
    claim: string;
    confidence: string;
    span?: { start_line: number; end_line: number };
  }>;
  semantic_overlay?: {
    annotations?: SemanticAnnotation[];
    exact_ir_digest?: string;
  } | null;
  document: {
    source_digest: string;
    visual_patches?: unknown[];
    redo_patches?: unknown[];
  };
  integrity?: {
    source_digest: string;
    exact_ir_digest: string;
  };
  semantic_intent_binding?: {
    base_source_digest: string;
    base_exact_ir_digest: string;
  };
  view_state?: {
    node_positions?: Record<string, { x: number; y: number }>;
    node_sizes?: Record<string, { width: number; height: number }>;
    cameras?: Record<string, { x: number; y: number; zoom: number }>;
    module_expansion?: string[];
    pinned_node_ids?: string[];
    theme?: "paper-light" | "studio-dark";
  };
  draft?: DraftGraphState;
  source_workspace?: {
    workspace_id: string;
    revision: number;
    base_revision: string;
    state: "clean" | "modified" | "stale";
    files: SourceWorkspaceFile[];
  };
  diagnostics?: Array<{ code: string; severity: string; message: string; target_ids: string[] }>;
  validation_runs?: Array<{
    validation_id: string;
    profile: string;
    state: string;
    gate_results: Array<{ gate: string; status: string; message: string }>;
    diagnostics: Array<{ code: string; severity: string; message: string; target_ids: string[] }>;
  }>;
  jobs?: StudioJob[];
  transaction?: {
    transaction_id: string;
    state: string;
    request: {
      target_node_id?: string;
      operation: string;
      parameter_name?: string;
      new_value?: unknown;
      value_origin_id?: string | null;
      edit_target_scope?: EditTargetScope | null;
      confirmed_affected_ids?: string[];
      confirmed_source_anchor_ids?: string[];
      parameters?: Record<string, unknown>;
    };
    parameter_edit_context?: ParameterEditContext | null;
    state_migration_plan?: StateMigrationPlan | null;
    source_diff: string;
    expected_delta: Record<string, unknown>;
    observed_delta?: Record<string, unknown>;
    gates: Array<{ gate: string; status: string; message: string }>;
    diagnostics: Array<{ code: string; severity: string; message: string; target_ids: string[] }>;
  } | null;
  capabilities?: {
    source_editing?: boolean;
    semantic_transforms?: string[];
    draft_node_authoring?: { status: "available" | "unavailable"; writeback?: string };
    arbitrary_draft_node_lowering?: { status: "available" | "unavailable"; reason?: string };
    generated_project?: {
      status: "available" | "unavailable";
      framework: string;
      generator_version: string;
      supported_slice: string[];
    };
    framework_forms?: Array<{
      schema_version: "2.0";
      adapter_id: string;
      framework: string;
      adapter_version: string;
      status: "verified" | "experimental" | "partial" | "unavailable";
      forms: Array<{
        form_id: string;
        form_name: string;
        framework: string;
        static_analysis: "verified" | "experimental" | "partial" | "unavailable";
        runtime_evidence: "verified" | "experimental" | "partial" | "unavailable";
        parameter_transaction: "verified" | "experimental" | "partial" | "unavailable";
        structural_transaction: "verified" | "experimental" | "partial" | "unavailable";
        code_generation: "verified" | "experimental" | "partial" | "unavailable";
        artifact_commit: "verified" | "experimental" | "partial" | "unavailable";
        supported_targets: string[];
        verified_fixtures: string[];
        limitations: string[];
      }>;
    }>;
  };
}

export function isStudioStatePayload(value: unknown): value is StudioStatePayload {
  if (!value || typeof value !== "object") return false;
  const state = value as Partial<StudioStatePayload>;
  return Boolean(
    state.project?.project_id
    && state.architecture?.architecture_id
    && Array.isArray(state.architecture.nodes)
    && Array.isArray(state.architecture.edges)
    && state.document?.source_digest,
  );
}
