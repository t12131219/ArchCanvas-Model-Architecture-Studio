export interface DefinitionRef {
  definition_id: string;
  version: string;
  digest: string;
}

export interface ParameterContract {
  parameter_id: string;
  required: boolean;
  default: unknown;
  value_type: "integer" | "number" | "boolean" | "string" | "shape" | "any";
  positional_index: number | null;
  affects: Array<"ports" | "shape" | "cost" | "code" | "visual">;
  editability: "editable" | "source-readonly" | "derived-readonly";
}

export interface PortContract {
  port_id: string;
  direction: "input" | "output";
  required: boolean;
  min_connections: number;
  max_connections: number | "many";
  ordering: "ordered" | "unordered";
  accepted_relations: string[];
  tensor_ranks: number[];
  tensor_layouts: Array<"NCHW" | "NHWC" | "sequence" | "scalar" | "any">;
}

export interface ModuleDefinition {
  definition_id: string;
  version: string;
  digest: string;
  semantic_kind: string;
  qualified_names: string[];
  parameter_schema_version: "1.0";
  parameters: ParameterContract[];
  ports: PortContract[];
  glyph_id: string;
  detail_template_id: string | null;
  shape_rule_id: string | null;
  cost_rule_id: string | null;
  codegen_rule_id: string | null;
}

export interface ModuleRegistryBundle {
  schema_version: "1.0";
  bundle_id: string;
  bundle_digest: string;
  definitions: ModuleDefinition[];
}

export interface DraftNodeContractInput {
  node_id: string;
  semantic_name: string;
  framework: string;
  node_type: string;
  definition_ref: DefinitionRef;
  parent_id: string | null;
  parameters: Record<string, unknown>;
  ports: Array<{
    port_id: string;
    name: string;
    direction: "input" | "output";
    role: string;
    definition_port_id: string;
    required: boolean;
    min_connections: number;
    max_connections: number | "many";
    ordering: "ordered" | "unordered";
    accepted_relations: string[];
    tensor_ranks: number[];
    tensor_layouts: Array<"NCHW" | "NHWC" | "sequence" | "scalar" | "any">;
  }>;
}
