import rawBundle from "./module-registry-v1.json";

import type {
  DefinitionRef,
  DraftNodeContractInput,
  ModuleDefinition,
  ModuleRegistryBundle,
} from "./types";

function validateBundle(value: unknown): ModuleRegistryBundle {
  if (!value || typeof value !== "object") throw new Error("Module registry bundle is missing.");
  const candidate = value as ModuleRegistryBundle;
  if (candidate.schema_version !== "1.0" || !candidate.bundle_digest) {
    throw new Error("Module registry bundle has an unsupported protocol version.");
  }
  const identities = new Set<string>();
  const qualifiedNames = new Set<string>();
  for (const definition of candidate.definitions) {
    const identity = `${definition.definition_id}@${definition.version}`;
    if (identities.has(identity)) throw new Error(`Duplicate module definition: ${identity}`);
    identities.add(identity);
    const ports = new Set<string>();
    const parameters = new Set<string>();
    if (definition.parameter_schema_version !== "1.0") {
      throw new Error(`Unsupported parameter schema on ${identity}`);
    }
    for (const parameter of definition.parameters) {
      if (parameters.has(parameter.parameter_id)) {
        throw new Error(`Duplicate parameter ${parameter.parameter_id} on ${identity}`);
      }
      parameters.add(parameter.parameter_id);
      if (new Set(parameter.affects).size !== parameter.affects.length) {
        throw new Error(`Duplicate parameter impact ${parameter.parameter_id} on ${identity}`);
      }
    }
    for (const port of definition.ports) {
      if (ports.has(port.port_id)) throw new Error(`Duplicate port ${port.port_id} on ${identity}`);
      ports.add(port.port_id);
    }
    for (const qualifiedName of definition.qualified_names) {
      if (qualifiedNames.has(qualifiedName)) {
        throw new Error(`Ambiguous registry qualified name: ${qualifiedName}`);
      }
      qualifiedNames.add(qualifiedName);
    }
  }
  return candidate;
}

function deepFreeze<T>(value: T): T {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    for (const child of Object.values(value as Record<string, unknown>)) deepFreeze(child);
    Object.freeze(value);
  }
  return value;
}

export const MODULE_REGISTRY = deepFreeze(validateBundle(rawBundle));

const byQualifiedName = new Map(
  MODULE_REGISTRY.definitions.flatMap((definition) =>
    definition.qualified_names.map((qualifiedName) => [qualifiedName, definition] as const)),
);
const byReference = new Map(
  MODULE_REGISTRY.definitions.map((definition) => [
    `${definition.definition_id}@${definition.version}:${definition.digest}`,
    definition,
  ] as const),
);
const byDefinitionId = new Map(
  MODULE_REGISTRY.definitions.map((definition) => [definition.definition_id, definition] as const),
);

export function resolveQualifiedName(qualifiedName: string): ModuleDefinition | undefined {
  return byQualifiedName.get(qualifiedName);
}

export function resolveDefinitionRef(reference: DefinitionRef): ModuleDefinition | undefined {
  return byReference.get(`${reference.definition_id}@${reference.version}:${reference.digest}`);
}

export function resolveDefinitionId(definitionId: string): ModuleDefinition | undefined {
  return byDefinitionId.get(definitionId);
}

export type DerivedArtifact = "ports" | "shape" | "cost" | "code" | "visual";

const INVALIDATION_CLOSURE: Record<DerivedArtifact, DerivedArtifact[]> = {
  ports: ["ports", "shape", "cost", "code", "visual"],
  shape: ["shape", "cost", "visual"],
  cost: ["cost"],
  code: ["code"],
  visual: ["visual"],
};

export function migrateParameterValues(
  definition: ModuleDefinition,
  sourceSchemaVersion: string,
  values: Record<string, unknown>,
): Record<string, unknown> {
  if (sourceSchemaVersion !== definition.parameter_schema_version) {
    throw new Error(
      `No registered parameter migration from ${sourceSchemaVersion} to ${definition.parameter_schema_version}.`,
    );
  }
  const contracts = new Map(definition.parameters.map((item) => [item.parameter_id, item]));
  const unknown = Object.keys(values).filter((key) => !contracts.has(key)).sort();
  if (unknown.length) throw new Error(`Unknown module parameters: ${unknown.join(", ")}`);
  const migrated = Object.fromEntries(
    definition.parameters.map((parameter) => [parameter.parameter_id, structuredClone(parameter.default)]),
  );
  Object.assign(migrated, structuredClone(values));
  return migrated;
}

export function parameterChangeInvalidation(
  definition: ModuleDefinition,
  before: Record<string, unknown>,
  after: Record<string, unknown>,
): DerivedArtifact[] {
  const affected = new Set<DerivedArtifact>();
  for (const parameter of definition.parameters) {
    if (JSON.stringify(before[parameter.parameter_id]) === JSON.stringify(after[parameter.parameter_id])) continue;
    for (const scope of parameter.affects) {
      for (const invalidated of INVALIDATION_CLOSURE[scope]) affected.add(invalidated);
    }
  }
  return (["ports", "shape", "cost", "code", "visual"] as DerivedArtifact[])
    .filter((scope) => affected.has(scope));
}

export type ModuleCategory =
  | "Inputs"
  | "Torch Ops"
  | "Tensor Shape"
  | "Activations"
  | "Normalization"
  | "Regularization"
  | "Linear / Dense"
  | "Vision - Convolution"
  | "Vision - Pooling"
  | "Sequence / Attention";

export const MODULE_CATEGORY_ORDER: ModuleCategory[] = [
  "Inputs",
  "Torch Ops",
  "Tensor Shape",
  "Activations",
  "Normalization",
  "Regularization",
  "Linear / Dense",
  "Vision - Convolution",
  "Vision - Pooling",
  "Sequence / Attention",
];

const labels: Record<string, string> = {
  "archcanvas.input.tensor": "Tensor Input",
  "pytorch.nn.linear": "Linear",
  "pytorch.nn.conv2d": "Conv2d",
  "pytorch.nn.maxpool2d": "MaxPool2d",
  "pytorch.nn.relu": "ReLU",
  "pytorch.nn.gelu": "GELU",
  "pytorch.op.add": "Add",
  "pytorch.nn.layernorm": "LayerNorm",
  "pytorch.nn.dropout": "Dropout",
  "pytorch.op.reshape": "Reshape",
  "pytorch.op.transpose": "Transpose",
  "pytorch.nn.embedding": "Embedding",
  "pytorch.nn.multiheadattention": "Multihead Attention",
  "pytorch.nn.lstm": "LSTM",
};

export function moduleDefinitionLabel(definition: ModuleDefinition): string {
  return labels[definition.definition_id] ?? definition.definition_id;
}

export function moduleDefinitionCategory(definition: ModuleDefinition): ModuleCategory {
  if (definition.semantic_kind === "input") return "Inputs";
  if (definition.semantic_kind === "add") return "Torch Ops";
  if (definition.semantic_kind === "shape-transform") return "Tensor Shape";
  if (definition.semantic_kind === "activation") return "Activations";
  if (definition.semantic_kind === "normalization") return "Normalization";
  if (definition.semantic_kind === "regularization") return "Regularization";
  if (definition.semantic_kind === "linear") return "Linear / Dense";
  if (definition.semantic_kind === "convolution") return "Vision - Convolution";
  if (definition.semantic_kind === "pooling") return "Vision - Pooling";
  return "Sequence / Attention";
}

export function materializeDraftNode(
  definition: ModuleDefinition,
  nodeId: string,
  semanticName: string,
  framework: string,
  parentId: string | null,
): DraftNodeContractInput {
  return {
    node_id: nodeId,
    semantic_name: semanticName,
    framework,
    node_type: definition.definition_id,
    definition_ref: {
      definition_id: definition.definition_id,
      version: definition.version,
      digest: definition.digest,
    },
    parent_id: parentId,
    parameters: Object.fromEntries(
      definition.parameters.map((parameter) => [parameter.parameter_id, structuredClone(parameter.default)]),
    ),
    ports: definition.ports.map((port) => ({
      port_id: `${nodeId}.${port.port_id}`,
      name: port.port_id,
      direction: port.direction,
      role: port.port_id,
      definition_port_id: port.port_id,
      required: port.required,
      min_connections: port.min_connections,
      max_connections: port.max_connections,
      ordering: port.ordering,
      accepted_relations: [...port.accepted_relations],
      tensor_ranks: [...port.tensor_ranks],
      tensor_layouts: [...port.tensor_layouts],
    })),
  };
}
