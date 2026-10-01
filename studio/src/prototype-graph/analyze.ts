import {
  MODULE_REGISTRY,
  resolveDefinitionRef,
} from "../module-registry/registry";
import type { ModuleDefinition } from "../module-registry/types";
import type {
  AnalysisSnapshot,
  AnalyzedValue,
  CostEstimate,
  DimensionValue,
  GraphDiagnostic,
  PrototypeGraphDocument,
  PrototypeNode,
  ShapeValue,
} from "./types";

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, canonicalize(item)]),
    );
  }
  return value;
}

async function sha256(value: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(JSON.stringify(canonicalize(value)));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (item) => item.toString(16).padStart(2, "0")).join("");
}

function diagnostic(
  code: string,
  severity: GraphDiagnostic["severity"],
  message: string,
  targetIds: string[],
  relatedPortIds: string[] = [],
): GraphDiagnostic {
  return {
    diagnosticId: `diagnostic:${code.toLowerCase()}:${targetIds.join(":")}`,
    code,
    severity,
    message,
    targetIds,
    relatedPortIds,
  };
}

function dimension(value: unknown): DimensionValue {
  if (typeof value === "number" && Number.isSafeInteger(value) && value > 0) {
    return { kind: "known", value };
  }
  if (typeof value === "string" && value.trim()) {
    return { kind: "symbol", symbol: value.trim() };
  }
  return { kind: "unknown", reason: "dimension is absent or invalid" };
}

function shapeParameter(value: unknown): ShapeValue | null {
  if (!Array.isArray(value) || !value.length) return null;
  return { dimensions: value.map(dimension), layout: "any", constraints: [] };
}

function pair(value: unknown, fallback: number): [number, number] | null {
  if (typeof value === "number" && Number.isSafeInteger(value) && value > 0) {
    return [value, value];
  }
  if (
    Array.isArray(value)
    && value.length === 2
    && value.every((item) => typeof item === "number" && Number.isSafeInteger(item) && item > 0)
  ) {
    return [Number(value[0]), Number(value[1])];
  }
  if (value == null) return [fallback, fallback];
  return null;
}

function paddingPair(value: unknown): [number, number] | null {
  if (typeof value === "number" && Number.isSafeInteger(value) && value >= 0) return [value, value];
  if (
    Array.isArray(value)
    && value.length === 2
    && value.every((item) => typeof item === "number" && Number.isSafeInteger(item) && item >= 0)
  ) return [Number(value[0]), Number(value[1])];
  return null;
}

function convDimension(
  input: DimensionValue,
  kernel: number,
  stride: number,
  padding: number,
  dilation: number,
): DimensionValue {
  if (input.kind === "known") {
    return {
      kind: "known",
      value: Math.floor((input.value + 2 * padding - dilation * (kernel - 1) - 1) / stride + 1),
    };
  }
  const source = input.kind === "symbol" ? input.symbol : input.kind === "expression" ? input.expression : "?";
  return {
    kind: "expression",
    expression: `floor((${source}+${2 * padding}-${dilation}*(${kernel}-1)-1)/${stride}+1)`,
  };
}

function known(value: ShapeValue): AnalyzedValue {
  return { status: "known", shape: value };
}

function unknown(reason: string): AnalyzedValue {
  return { status: "unknown", reason, constraints: [] };
}

function blocked(diagnosticIds: string[]): AnalyzedValue {
  return { status: "blocked", causedByDiagnosticIds: diagnosticIds };
}

interface RuleResult {
  outputs: Record<string, AnalyzedValue>;
  diagnostics: GraphDiagnostic[];
  cost: CostEstimate;
}

const EMPTY_COST: CostEstimate = { parameterCount: null, flops: null, assumptions: [] };

function outputNames(definition: ModuleDefinition): string[] {
  return definition.ports.filter((port) => port.direction === "output").map((port) => port.port_id);
}

function unavailableRule(node: PrototypeNode, definition: ModuleDefinition): RuleResult {
  const item = diagnostic(
    "SHAPE_RULE_UNAVAILABLE",
    "warning",
    `Shape rule ${definition.shape_rule_id ?? "none"} is not implemented in the draft analyzer.`,
    [node.node_id],
  );
  return {
    outputs: Object.fromEntries(outputNames(definition).map((name) => [name, unknown(item.message)])),
    diagnostics: [item],
    cost: EMPTY_COST,
  };
}

function analyzeInput(node: PrototypeNode, definition: ModuleDefinition): RuleResult {
  const shape = shapeParameter(node.parameters.shape);
  if (!shape) {
    const item = diagnostic(
      "INPUT_SHAPE_REQUIRED",
      "blocking",
      "Tensor Input requires a non-empty shape parameter.",
      [node.node_id],
    );
    return {
      outputs: Object.fromEntries(outputNames(definition).map((name) => [name, blocked([item.diagnosticId])])),
      diagnostics: [item],
      cost: EMPTY_COST,
    };
  }
  return { outputs: { output: known(shape) }, diagnostics: [], cost: EMPTY_COST };
}

function analyzeIdentity(
  node: PrototypeNode,
  definition: ModuleDefinition,
  inputs: Record<string, AnalyzedValue[]>,
): RuleResult {
  const input = inputs.input?.[0];
  if (!input) return unavailableRule(node, definition);
  const output = input.status === "known" ? known(input.shape) : input;
  return {
    outputs: Object.fromEntries(outputNames(definition).map((name) => [name, output])),
    diagnostics: [],
    cost: EMPTY_COST,
  };
}

function integerParameter(node: PrototypeNode, name: string): number | null {
  const value = node.parameters[name];
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0 ? value : null;
}

function analyzeConv2d(
  node: PrototypeNode,
  inputs: Record<string, AnalyzedValue[]>,
): RuleResult {
  const input = inputs.input?.[0];
  if (!input || input.status !== "known") {
    return { outputs: { output: input ?? unknown("Conv2d input is unavailable") }, diagnostics: [], cost: EMPTY_COST };
  }
  const shape = input.shape;
  const inChannels = integerParameter(node, "in_channels");
  const outChannels = integerParameter(node, "out_channels");
  const groups = integerParameter(node, "groups") ?? 1;
  const kernel = pair(node.parameters.kernel_size, 1);
  const stride = pair(node.parameters.stride, 1);
  const padding = paddingPair(node.parameters.padding);
  const dilation = pair(node.parameters.dilation, 1);
  const errors: GraphDiagnostic[] = [];
  if (shape.dimensions.length !== 4) {
    errors.push(diagnostic("CONV2D_RANK_MISMATCH", "blocking", "Conv2d input must have rank 4.", [node.node_id]));
  }
  const channel = shape.dimensions[1];
  if (inChannels && channel?.kind === "known" && channel.value !== inChannels) {
    errors.push(diagnostic(
      "CONV2D_CHANNEL_MISMATCH",
      "blocking",
      `Conv2d expects ${inChannels} channels but its input provides ${channel.value}.`,
      [node.node_id],
    ));
  }
  if (!inChannels || !outChannels || !kernel || !stride || !padding || !dilation || groups < 1) {
    errors.push(diagnostic("CONV2D_PARAMETER_INVALID", "blocking", "Conv2d parameters are incomplete or invalid.", [node.node_id]));
  }
  if (errors.length || !outChannels || !kernel || !stride || !padding || !dilation) {
    return { outputs: { output: blocked(errors.map((item) => item.diagnosticId)) }, diagnostics: errors, cost: EMPTY_COST };
  }
  const outputShape: ShapeValue = {
    dimensions: [
      shape.dimensions[0],
      { kind: "known", value: outChannels },
      convDimension(shape.dimensions[2], kernel[0], stride[0], padding[0], dilation[0]),
      convDimension(shape.dimensions[3], kernel[1], stride[1], padding[1], dilation[1]),
    ],
    dtype: shape.dtype,
    layout: "NCHW",
    constraints: [...shape.constraints],
  };
  const invalidSpatial = outputShape.dimensions.slice(2).some(
    (item) => item.kind === "known" && item.value <= 0,
  );
  if (invalidSpatial) {
    const item = diagnostic(
      "CONV2D_OUTPUT_INVALID",
      "blocking",
      "Conv2d parameters produce a non-positive spatial dimension.",
      [node.node_id],
    );
    return { outputs: { output: blocked([item.diagnosticId]) }, diagnostics: [item], cost: EMPTY_COST };
  }
  const bias = node.parameters.bias !== false ? outChannels : 0;
  const parameterCount = inChannels
    ? String(outChannels * Math.floor(inChannels / groups) * kernel[0] * kernel[1] + bias)
    : null;
  const outputDimensions = outputShape.dimensions.map((item) => item.kind === "known" ? String(item.value) : item.kind === "symbol" ? item.symbol : item.kind === "expression" ? item.expression : "?");
  return {
    outputs: { output: known(outputShape) },
    diagnostics: [],
    cost: {
      parameterCount,
      flops: `${outputDimensions.join("*")}*${Math.floor((inChannels ?? 1) / groups) * kernel[0] * kernel[1] * 2}`,
      assumptions: ["multiply-add counted as two FLOPs"],
    },
  };
}

function dimensionText(value: DimensionValue): string {
  if (value.kind === "known") return String(value.value);
  if (value.kind === "symbol") return value.symbol;
  if (value.kind === "expression") return value.expression;
  return "?";
}

function dimensionsEqual(left: DimensionValue, right: DimensionValue): boolean {
  return dimensionText(left) === dimensionText(right);
}

function productExpression(values: DimensionValue[]): string | null {
  if (values.some((value) => value.kind === "unknown")) return null;
  return values.map(dimensionText).join("*") || "1";
}

function knownInput(
  inputs: Record<string, AnalyzedValue[]>,
  portId: string,
): ShapeValue | AnalyzedValue {
  const input = inputs[portId]?.[0] ?? unknown(`${portId} input is unavailable`);
  return input.status === "known" ? input.shape : input;
}

function forwardUnavailable(outputIds: string[], value: AnalyzedValue): RuleResult {
  return {
    outputs: Object.fromEntries(outputIds.map((outputId) => [outputId, value])),
    diagnostics: [],
    cost: EMPTY_COST,
  };
}

function analyzeLinear(
  node: PrototypeNode,
  definition: ModuleDefinition,
  inputs: Record<string, AnalyzedValue[]>,
): RuleResult {
  const input = knownInput(inputs, "input");
  if (!("dimensions" in input)) return forwardUnavailable(outputNames(definition), input);
  const inFeatures = integerParameter(node, "in_features");
  const outFeatures = integerParameter(node, "out_features");
  const last = input.dimensions.at(-1);
  const errors: GraphDiagnostic[] = [];
  if (!last) {
    errors.push(diagnostic("LINEAR_RANK_INVALID", "blocking", "Linear input must have at least one dimension.", [node.node_id]));
  } else if (inFeatures && last.kind === "known" && last.value !== inFeatures) {
    errors.push(diagnostic("LINEAR_FEATURE_MISMATCH", "blocking", `Linear expects ${inFeatures} input features but receives ${last.value}.`, [node.node_id]));
  }
  if (!inFeatures || !outFeatures) {
    errors.push(diagnostic("LINEAR_PARAMETER_INVALID", "blocking", "Linear features must be positive integers.", [node.node_id]));
  }
  if (errors.length || !outFeatures) {
    return { outputs: { output: blocked(errors.map((item) => item.diagnosticId)) }, diagnostics: errors, cost: EMPTY_COST };
  }
  const output: ShapeValue = {
    ...input,
    dimensions: [...input.dimensions.slice(0, -1), { kind: "known", value: outFeatures }],
  };
  const elements = productExpression(output.dimensions);
  return {
    outputs: { output: known(output) },
    diagnostics: [],
    cost: {
      parameterCount: inFeatures ? String(inFeatures * outFeatures + (node.parameters.bias === false ? 0 : outFeatures)) : null,
      flops: elements && inFeatures ? `${elements}*${2 * inFeatures}` : null,
      assumptions: ["multiply-add counted as two FLOPs"],
    },
  };
}

function broadcastDimension(left: DimensionValue, right: DimensionValue): DimensionValue | null {
  if (dimensionsEqual(left, right)) return left;
  if (left.kind === "known" && left.value === 1) return right;
  if (right.kind === "known" && right.value === 1) return left;
  if (left.kind === "unknown" || right.kind === "unknown") {
    return { kind: "unknown", reason: "broadcast dimension is unresolved" };
  }
  if (left.kind !== "known" || right.kind !== "known") {
    return { kind: "expression", expression: `broadcast(${dimensionText(left)},${dimensionText(right)})` };
  }
  return null;
}

function analyzeBroadcast(
  node: PrototypeNode,
  definition: ModuleDefinition,
  inputs: Record<string, AnalyzedValue[]>,
): RuleResult {
  const values = inputs.operands ?? [];
  const unavailable = values.find((value) => value.status !== "known");
  if (unavailable) return forwardUnavailable(outputNames(definition), unavailable);
  const shapes = values.map((value) => (value as Extract<AnalyzedValue, { status: "known" }>).shape);
  if (!shapes.length) return unavailableRule(node, definition);
  let result = [...shapes[0].dimensions];
  const errors: GraphDiagnostic[] = [];
  for (const shape of shapes.slice(1)) {
    const rank = Math.max(result.length, shape.dimensions.length);
    const left = Array(rank - result.length).fill({ kind: "known", value: 1 } as DimensionValue).concat(result);
    const right = Array(rank - shape.dimensions.length).fill({ kind: "known", value: 1 } as DimensionValue).concat(shape.dimensions);
    const merged = left.map((item, index) => broadcastDimension(item, right[index]));
    if (merged.some((item) => item === null)) {
      errors.push(diagnostic("BROADCAST_SHAPE_MISMATCH", "blocking", "Add operands are not broadcast compatible.", [node.node_id]));
      break;
    }
    result = merged as DimensionValue[];
  }
  if (errors.length) {
    return { outputs: { output: blocked(errors.map((item) => item.diagnosticId)) }, diagnostics: errors, cost: EMPTY_COST };
  }
  const output: ShapeValue = { ...shapes[0], dimensions: result };
  const elements = productExpression(result);
  return {
    outputs: { output: known(output) },
    diagnostics: [],
    cost: {
      parameterCount: null,
      flops: elements ? `${elements}*${Math.max(1, shapes.length - 1)}` : null,
      assumptions: [],
    },
  };
}

function analyzeReshape(
  node: PrototypeNode,
  definition: ModuleDefinition,
  inputs: Record<string, AnalyzedValue[]>,
): RuleResult {
  const input = knownInput(inputs, "input");
  if (!("dimensions" in input)) return forwardUnavailable(outputNames(definition), input);
  const raw = Array.isArray(node.parameters.shape) ? node.parameters.shape : [node.parameters.shape];
  const inferIndices = raw.flatMap((value, index) => value === -1 ? [index] : []);
  const invalid = raw.length === 0 || inferIndices.length > 1 || raw.some((value) => (
    typeof value === "number" ? !Number.isSafeInteger(value) || value === 0 || value < -1 : typeof value !== "string" || !value.trim()
  ));
  if (invalid) {
    const item = diagnostic("RESHAPE_TARGET_INVALID", "blocking", "Reshape requires non-zero dimensions and at most one inferred -1 dimension.", [node.node_id]);
    return { outputs: { output: blocked([item.diagnosticId]) }, diagnostics: [item], cost: EMPTY_COST };
  }
  const dimensions = raw.map((value) => value === -1
    ? { kind: "unknown", reason: "pending reshape inference" } as DimensionValue
    : dimension(value));
  const inputProduct = productExpression(input.dimensions);
  const knownTarget = productExpression(dimensions.filter((_, index) => index !== inferIndices[0]));
  if (inferIndices.length && inputProduct && knownTarget) {
    dimensions[inferIndices[0]] = { kind: "expression", expression: `(${inputProduct})/(${knownTarget})` };
  } else if (!inferIndices.length) {
    const inputKnown = input.dimensions.every((value) => value.kind === "known")
      ? input.dimensions.reduce((total, value) => total * (value as { kind: "known"; value: number }).value, 1)
      : null;
    const targetKnown = dimensions.every((value) => value.kind === "known")
      ? dimensions.reduce((total, value) => total * (value as { kind: "known"; value: number }).value, 1)
      : null;
    if (inputKnown !== null && targetKnown !== null && inputKnown !== targetKnown) {
      const item = diagnostic("RESHAPE_ELEMENT_MISMATCH", "blocking", "Reshape changes the number of tensor elements.", [node.node_id]);
      return { outputs: { output: blocked([item.diagnosticId]) }, diagnostics: [item], cost: EMPTY_COST };
    }
  }
  return {
    outputs: { output: known({ ...input, dimensions, layout: "any" }) },
    diagnostics: [],
    cost: EMPTY_COST,
  };
}

function analyzePool2d(
  node: PrototypeNode,
  definition: ModuleDefinition,
  inputs: Record<string, AnalyzedValue[]>,
): RuleResult {
  const input = knownInput(inputs, "input");
  if (!("dimensions" in input)) return forwardUnavailable(outputNames(definition), input);
  const kernel = node.parameters.kernel_size == null ? null : pair(node.parameters.kernel_size, 1);
  const stride = node.parameters.stride == null ? kernel : pair(node.parameters.stride, 0);
  const padding = paddingPair(node.parameters.padding ?? 0);
  const errors: GraphDiagnostic[] = [];
  if (input.dimensions.length !== 4) errors.push(diagnostic("POOL2D_RANK_MISMATCH", "blocking", "MaxPool2d input must have rank 4.", [node.node_id]));
  if (!kernel || !stride || !padding) errors.push(diagnostic("POOL2D_PARAMETER_INVALID", "blocking", "MaxPool2d parameters are incomplete or invalid.", [node.node_id]));
  if (errors.length || !kernel || !stride || !padding) {
    return { outputs: { output: blocked(errors.map((item) => item.diagnosticId)) }, diagnostics: errors, cost: EMPTY_COST };
  }
  const output: ShapeValue = {
    ...input,
    dimensions: [
      input.dimensions[0],
      input.dimensions[1],
      convDimension(input.dimensions[2], kernel[0], stride[0], padding[0], 1),
      convDimension(input.dimensions[3], kernel[1], stride[1], padding[1], 1),
    ],
    layout: "NCHW",
  };
  const elements = productExpression(output.dimensions);
  return {
    outputs: { output: known(output) },
    diagnostics: [],
    cost: { parameterCount: null, flops: elements ? `${elements}*${kernel[0] * kernel[1]}` : null, assumptions: ["one comparison per pooling element"] },
  };
}

function analyzeEmbedding(
  node: PrototypeNode,
  definition: ModuleDefinition,
  inputs: Record<string, AnalyzedValue[]>,
): RuleResult {
  const input = knownInput(inputs, "input");
  if (!("dimensions" in input)) return forwardUnavailable(outputNames(definition), input);
  const count = integerParameter(node, "num_embeddings");
  const width = integerParameter(node, "embedding_dim");
  if (!count || !width) {
    const item = diagnostic("EMBEDDING_PARAMETER_INVALID", "blocking", "Embedding dimensions must be positive integers.", [node.node_id]);
    return { outputs: { output: blocked([item.diagnosticId]) }, diagnostics: [item], cost: EMPTY_COST };
  }
  return {
    outputs: { output: known({ ...input, dimensions: [...input.dimensions, { kind: "known", value: width }] }) },
    diagnostics: [],
    cost: { parameterCount: String(count * width), flops: null, assumptions: ["embedding lookup has no arithmetic FLOP estimate"] },
  };
}

function analyzeLayerNorm(
  node: PrototypeNode,
  definition: ModuleDefinition,
  inputs: Record<string, AnalyzedValue[]>,
): RuleResult {
  const input = knownInput(inputs, "input");
  if (!("dimensions" in input)) return forwardUnavailable(outputNames(definition), input);
  const normalized = shapeParameter(
    Array.isArray(node.parameters.normalized_shape)
      ? node.parameters.normalized_shape
      : [node.parameters.normalized_shape],
  );
  const errors: GraphDiagnostic[] = [];
  if (node.parameters.normalized_shape == null || !normalized || normalized.dimensions.length > input.dimensions.length) {
    errors.push(diagnostic("LAYERNORM_SHAPE_INVALID", "blocking", "LayerNorm normalized_shape must match an input suffix.", [node.node_id]));
  } else {
    const suffix = input.dimensions.slice(-normalized.dimensions.length);
    if (suffix.some((value, index) => value.kind === "known" && normalized.dimensions[index].kind === "known" && !dimensionsEqual(value, normalized.dimensions[index]))) {
      errors.push(diagnostic("LAYERNORM_SHAPE_MISMATCH", "blocking", "LayerNorm normalized_shape does not match the input suffix.", [node.node_id]));
    }
  }
  if (errors.length || !normalized) {
    return { outputs: { output: blocked(errors.map((item) => item.diagnosticId)) }, diagnostics: errors, cost: EMPTY_COST };
  }
  const normalizedElements = productExpression(normalized.dimensions);
  const outputElements = productExpression(input.dimensions);
  return {
    outputs: { output: known(input) },
    diagnostics: [],
    cost: {
      parameterCount: node.parameters.elementwise_affine === false || !normalizedElements ? null : `${normalizedElements}*2`,
      flops: outputElements ? `${outputElements}*5` : null,
      assumptions: ["LayerNorm estimated as five elementwise operations"],
    },
  };
}

function analyzeMultiheadAttention(
  node: PrototypeNode,
  definition: ModuleDefinition,
  inputs: Record<string, AnalyzedValue[]>,
): RuleResult {
  const query = knownInput(inputs, "query");
  const key = knownInput(inputs, "key");
  const value = knownInput(inputs, "value");
  const unavailable = [query, key, value].find((item) => !("dimensions" in item));
  if (unavailable && !("dimensions" in unavailable)) return forwardUnavailable(outputNames(definition), unavailable);
  const shapes = [query, key, value] as ShapeValue[];
  const embed = integerParameter(node, "embed_dim");
  const heads = integerParameter(node, "num_heads");
  const errors: GraphDiagnostic[] = [];
  if (shapes.some((shape) => shape.dimensions.length !== 3)) {
    errors.push(diagnostic("MHA_RANK_MISMATCH", "blocking", "MultiheadAttention query, key, and value must have rank 3.", [node.node_id]));
  }
  if (!embed || !heads || embed % heads !== 0) {
    errors.push(diagnostic("MHA_PARAMETER_INVALID", "blocking", "MultiheadAttention embed_dim must be divisible by num_heads.", [node.node_id]));
  }
  for (const shape of shapes) {
    const feature = shape.dimensions.at(-1);
    if (embed && feature?.kind === "known" && feature.value !== embed) {
      errors.push(diagnostic("MHA_EMBED_MISMATCH", "blocking", `MultiheadAttention expects embedding width ${embed}.`, [node.node_id]));
      break;
    }
  }
  const batchIndex = node.parameters.batch_first === true ? 0 : 1;
  const sequenceIndex = node.parameters.batch_first === true ? 1 : 0;
  if (shapes.every((shape) => shape.dimensions.length === 3)) {
    if (!dimensionsEqual(shapes[0].dimensions[batchIndex], shapes[1].dimensions[batchIndex])
      || !dimensionsEqual(shapes[1].dimensions[batchIndex], shapes[2].dimensions[batchIndex])) {
      errors.push(diagnostic("MHA_BATCH_MISMATCH", "blocking", "MultiheadAttention batch dimensions must match.", [node.node_id]));
    }
    if (!dimensionsEqual(shapes[1].dimensions[sequenceIndex], shapes[2].dimensions[sequenceIndex])) {
      errors.push(diagnostic("MHA_KEY_VALUE_LENGTH_MISMATCH", "blocking", "MultiheadAttention key and value sequence lengths must match.", [node.node_id]));
    }
  }
  if (errors.length || !embed) {
    const output = blocked(errors.map((item) => item.diagnosticId));
    return { outputs: Object.fromEntries(outputNames(definition).map((name) => [name, output])), diagnostics: errors, cost: EMPTY_COST };
  }
  const batch = shapes[0].dimensions[batchIndex];
  const queryLength = shapes[0].dimensions[sequenceIndex];
  const keyLength = shapes[1].dimensions[sequenceIndex];
  const weights: ShapeValue = {
    dimensions: [batch, queryLength, keyLength],
    dtype: shapes[0].dtype,
    layout: "any",
    constraints: [],
  };
  return {
    outputs: { context: known(shapes[0]), weights: known(weights) },
    diagnostics: [],
    cost: {
      parameterCount: String(4 * embed * embed + 4 * embed),
      flops: `${dimensionText(batch)}*(${dimensionText(queryLength)}+${dimensionText(keyLength)})*${4 * embed * embed}+${dimensionText(batch)}*${dimensionText(queryLength)}*${dimensionText(keyLength)}*${4 * embed}`,
      assumptions: ["dense QKV/output projections and attention matmuls included"],
    },
  };
}

function analyzeLstm(
  node: PrototypeNode,
  definition: ModuleDefinition,
  inputs: Record<string, AnalyzedValue[]>,
): RuleResult {
  const input = knownInput(inputs, "input");
  if (!("dimensions" in input)) return forwardUnavailable(outputNames(definition), input);
  const inputSize = integerParameter(node, "input_size");
  const hiddenSize = integerParameter(node, "hidden_size");
  const layers = integerParameter(node, "num_layers") ?? 1;
  const directions = node.parameters.bidirectional === true ? 2 : 1;
  const errors: GraphDiagnostic[] = [];
  if (input.dimensions.length !== 3) errors.push(diagnostic("LSTM_RANK_MISMATCH", "blocking", "LSTM input must have rank 3.", [node.node_id]));
  const feature = input.dimensions.at(-1);
  if (inputSize && feature?.kind === "known" && feature.value !== inputSize) {
    errors.push(diagnostic("LSTM_INPUT_SIZE_MISMATCH", "blocking", `LSTM expects input_size ${inputSize}.`, [node.node_id]));
  }
  if (!inputSize || !hiddenSize) errors.push(diagnostic("LSTM_PARAMETER_INVALID", "blocking", "LSTM sizes must be positive integers.", [node.node_id]));
  if (errors.length || !inputSize || !hiddenSize) {
    const output = blocked(errors.map((item) => item.diagnosticId));
    return { outputs: Object.fromEntries(outputNames(definition).map((name) => [name, output])), diagnostics: errors, cost: EMPTY_COST };
  }
  const batchIndex = node.parameters.batch_first === true ? 0 : 1;
  const batch = input.dimensions[batchIndex];
  const sequence: ShapeValue = {
    ...input,
    dimensions: [...input.dimensions.slice(0, -1), { kind: "known", value: hiddenSize * directions }],
    layout: "sequence",
  };
  const state: ShapeValue = {
    dimensions: [
      { kind: "known", value: layers * directions },
      batch,
      { kind: "known", value: hiddenSize },
    ],
    dtype: input.dtype,
    layout: "sequence",
    constraints: [],
  };
  let parameters = 0;
  for (let layer = 0; layer < layers; layer += 1) {
    const layerInput = layer === 0 ? inputSize : hiddenSize * directions;
    parameters += directions * 4 * hiddenSize * (layerInput + hiddenSize + 2);
  }
  const sequenceLength = input.dimensions[node.parameters.batch_first === true ? 1 : 0];
  return {
    outputs: { sequence: known(sequence), hn: known(state), cn: known(state) },
    diagnostics: [],
    cost: {
      parameterCount: String(parameters),
      flops: `${dimensionText(batch)}*${dimensionText(sequenceLength)}*${parameters * 2}`,
      assumptions: ["LSTM gate multiply-adds estimated from recurrent parameter matrices"],
    },
  };
}

function runRule(
  node: PrototypeNode,
  definition: ModuleDefinition,
  inputs: Record<string, AnalyzedValue[]>,
): RuleResult {
  if (definition.shape_rule_id === "shape.input.v1") return analyzeInput(node, definition);
  if (definition.shape_rule_id === "shape.conv2d.v1") return analyzeConv2d(node, inputs);
  if (definition.shape_rule_id === "shape.linear.v1") return analyzeLinear(node, definition, inputs);
  if (definition.shape_rule_id === "shape.broadcast.v1") return analyzeBroadcast(node, definition, inputs);
  if (definition.shape_rule_id === "shape.reshape.v1") return analyzeReshape(node, definition, inputs);
  if (definition.shape_rule_id === "shape.pool2d.v1") return analyzePool2d(node, definition, inputs);
  if (definition.shape_rule_id === "shape.embedding.v1") return analyzeEmbedding(node, definition, inputs);
  if (definition.shape_rule_id === "shape.multihead-attention.v1") return analyzeMultiheadAttention(node, definition, inputs);
  if (definition.shape_rule_id === "shape.lstm.v1") return analyzeLstm(node, definition, inputs);
  if (definition.shape_rule_id === "shape.identity.v1") {
    if (definition.definition_id === "pytorch.nn.layernorm") return analyzeLayerNorm(node, definition, inputs);
    return analyzeIdentity(node, definition, inputs);
  }
  return unavailableRule(node, definition);
}

export interface AnalyzeGraphOptions {
  allowExternalBoundaries?: boolean;
}

export async function analyzeGraph(
  graph: PrototypeGraphDocument,
  options: AnalyzeGraphOptions = {},
): Promise<AnalysisSnapshot> {
  const diagnostics: GraphDiagnostic[] = [];
  const nodeShapes: AnalysisSnapshot["nodeShapes"] = {};
  const nodeCosts: AnalysisSnapshot["nodeCosts"] = {};
  const nodes = new Map(graph.nodes.map((node) => [node.node_id, node]));
  const portOwners = new Map<string, { node: PrototypeNode; port: PrototypeNode["ports"][number] }>();
  for (const node of graph.nodes) {
    for (const port of node.ports) {
      if (portOwners.has(port.port_id)) {
        diagnostics.push(diagnostic("DUPLICATE_PORT_ID", "blocking", `Duplicate port ${port.port_id}.`, [node.node_id], [port.port_id]));
      } else {
        portOwners.set(port.port_id, { node, port });
      }
    }
  }

  const incoming = new Map<string, typeof graph.edges>();
  const outgoingNodes = new Map<string, Set<string>>();
  const indegree = new Map(graph.nodes.map((node) => [node.node_id, 0]));
  for (const edge of [...graph.edges].sort((left, right) => left.edge_id.localeCompare(right.edge_id))) {
    const source = portOwners.get(edge.source_port_id);
    const target = portOwners.get(edge.target_port_id);
    if (!source || !target) {
      if (options.allowExternalBoundaries && source && !target) {
        if (source.port.direction !== "output") {
          diagnostics.push(diagnostic("EDGE_DIRECTION_INVALID", "blocking", "Draft edge direction is invalid.", [edge.edge_id], [edge.source_port_id, edge.target_port_id]));
        }
        continue;
      }
      if (options.allowExternalBoundaries && !source && target) {
        if (target.port.direction !== "input") {
          diagnostics.push(diagnostic("EDGE_DIRECTION_INVALID", "blocking", "Draft edge direction is invalid.", [edge.edge_id], [edge.source_port_id, edge.target_port_id]));
          continue;
        }
        const relation = edge.relation ?? "main";
        if (target.port.accepted_relations && !target.port.accepted_relations.includes(relation)) {
          diagnostics.push(diagnostic("EDGE_RELATION_INVALID", "blocking", `Target port rejects ${relation}.`, [edge.edge_id, target.node.node_id], [edge.target_port_id]));
        }
        incoming.set(target.port.port_id, [...(incoming.get(target.port.port_id) ?? []), edge]);
        continue;
      }
      diagnostics.push(diagnostic("UNKNOWN_EDGE_PORT", "blocking", "Draft edge references an unknown port.", [edge.edge_id], [edge.source_port_id, edge.target_port_id]));
      continue;
    }
    if (source.port.direction !== "output" || target.port.direction !== "input") {
      diagnostics.push(diagnostic("EDGE_DIRECTION_INVALID", "blocking", "Draft edge direction is invalid.", [edge.edge_id], [edge.source_port_id, edge.target_port_id]));
      continue;
    }
    const relation = edge.relation ?? "main";
    if (target.port.accepted_relations && !target.port.accepted_relations.includes(relation)) {
      diagnostics.push(diagnostic("EDGE_RELATION_INVALID", "blocking", `Target port rejects ${relation}.`, [edge.edge_id, target.node.node_id], [edge.target_port_id]));
    }
    incoming.set(target.port.port_id, [...(incoming.get(target.port.port_id) ?? []), edge]);
    if (source.node.node_id !== target.node.node_id) {
      const dependents = outgoingNodes.get(source.node.node_id) ?? new Set<string>();
      if (!dependents.has(target.node.node_id)) {
        dependents.add(target.node.node_id);
        outgoingNodes.set(source.node.node_id, dependents);
        indegree.set(target.node.node_id, (indegree.get(target.node.node_id) ?? 0) + 1);
      }
    }
  }

  for (const [portId, edges] of incoming) {
    const target = portOwners.get(portId);
    if (!target || target.port.direction !== "input") continue;
    const ordering = target.port.ordering ?? "ordered";
    if (ordering === "unordered") {
      if (edges.some((edge) => edge.target_ordinal != null)) {
        diagnostics.push(diagnostic(
          "UNORDERED_PORT_HAS_ORDINAL",
          "blocking",
          "Unordered input ports reject target ordinals.",
          [target.node.node_id],
          [portId],
        ));
      }
      continue;
    }
    const maximum = target.port.max_connections ?? "many";
    if (maximum === 1) continue;
    const ordinals = edges.map((edge) => edge.target_ordinal);
    if (ordinals.some((ordinal) => ordinal == null)) {
      diagnostics.push(diagnostic(
        "ORDERED_PORT_ORDINAL_REQUIRED",
        "blocking",
        "Ordered variadic input connections require stable target ordinals.",
        [target.node.node_id],
        [portId],
      ));
    } else {
      const values = ordinals as number[];
      const expected = values.map((_, index) => index);
      if ([...values].sort((left, right) => left - right).some((value, index) => value !== expected[index])) {
        diagnostics.push(diagnostic(
          "ORDERED_PORT_ORDINAL_INVALID",
          "blocking",
          "Ordered variadic input ordinals must be unique and contiguous.",
          [target.node.node_id],
          [portId],
        ));
      }
    }
  }

  for (const node of graph.nodes) {
    for (const port of node.ports) {
      const count = incoming.get(port.port_id)?.length ?? 0;
      const minimum = port.min_connections ?? 0;
      const maximum = port.max_connections ?? "many";
      if (port.direction === "input" && count < minimum) {
        diagnostics.push(diagnostic("PORT_CARDINALITY_INCOMPLETE", "blocking", `${port.name} requires ${minimum} connection(s).`, [node.node_id], [port.port_id]));
      }
      if (port.direction === "input" && typeof maximum === "number" && count > maximum) {
        diagnostics.push(diagnostic("PORT_CARDINALITY_EXCEEDED", "blocking", `${port.name} accepts at most ${maximum} connection(s).`, [node.node_id], [port.port_id]));
      }
    }
  }

  const ready = [...indegree.entries()].filter(([, count]) => count === 0).map(([nodeId]) => nodeId).sort();
  const visited = new Set<string>();
  while (ready.length) {
    const nodeId = ready.shift()!;
    const node = nodes.get(nodeId)!;
    visited.add(nodeId);
    nodeShapes[nodeId] = {};
    if (!node.definition_ref) {
      const item = diagnostic("DEFINITION_REF_MISSING", "blocking", "Draft node has no exact module definition.", [nodeId]);
      diagnostics.push(item);
      for (const port of node.ports.filter((item) => item.direction === "output")) {
        nodeShapes[nodeId][port.name] = blocked([item.diagnosticId]);
      }
      nodeCosts[nodeId] = EMPTY_COST;
    } else {
      const definition = resolveDefinitionRef(node.definition_ref);
      if (!definition) {
        const item = diagnostic("DEFINITION_REF_STALE", "blocking", "Draft node module definition is unavailable or stale.", [nodeId]);
        diagnostics.push(item);
        for (const port of node.ports.filter((item) => item.direction === "output")) {
          nodeShapes[nodeId][port.name] = blocked([item.diagnosticId]);
        }
        nodeCosts[nodeId] = EMPTY_COST;
      } else {
        const inputs: Record<string, AnalyzedValue[]> = {};
        for (const port of node.ports.filter((item) => item.direction === "input")) {
          const contractId = port.definition_port_id ?? port.name;
          inputs[contractId] = (incoming.get(port.port_id) ?? [])
            .sort((left, right) => {
              if ((port.ordering ?? "ordered") === "ordered") {
                const ordinal = (left.target_ordinal ?? Number.MAX_SAFE_INTEGER)
                  - (right.target_ordinal ?? Number.MAX_SAFE_INTEGER);
                if (ordinal) return ordinal;
              }
              return left.edge_id.localeCompare(right.edge_id);
            })
            .map((edge) => {
              const source = portOwners.get(edge.source_port_id);
              if (!source) return unknown("canonical upstream shape is unavailable in the draft analyzer");
              const sourceContractId = source.port.definition_port_id ?? source.port.name;
              return nodeShapes[source.node.node_id]?.[sourceContractId]
                ?? unknown("upstream output has not been analyzed");
            });
          for (const value of inputs[contractId]) {
            if (value.status !== "known") continue;
            if (port.tensor_ranks?.length && !port.tensor_ranks.includes(value.shape.dimensions.length)) {
              diagnostics.push(diagnostic(
                "PORT_TENSOR_RANK_INVALID",
                "blocking",
                `${port.name} rejects rank ${value.shape.dimensions.length}.`,
                [nodeId],
                [port.port_id],
              ));
            }
            if (
              port.tensor_layouts?.length
              && value.shape.layout
              && value.shape.layout !== "any"
              && !port.tensor_layouts.includes("any")
              && !port.tensor_layouts.includes(value.shape.layout)
            ) {
              diagnostics.push(diagnostic(
                "PORT_TENSOR_LAYOUT_INVALID",
                "blocking",
                `${port.name} rejects ${value.shape.layout} layout.`,
                [nodeId],
                [port.port_id],
              ));
            }
          }
        }
        const requiredDiagnosticIds = diagnostics
          .filter((item) => item.severity === "blocking" && item.targetIds.includes(nodeId))
          .map((item) => item.diagnosticId);
        const result = requiredDiagnosticIds.length
          ? {
              outputs: Object.fromEntries(outputNames(definition).map((name) => [name, blocked(requiredDiagnosticIds)])),
              diagnostics: [],
              cost: EMPTY_COST,
            }
          : runRule(node, definition, inputs);
        nodeShapes[nodeId] = result.outputs;
        nodeCosts[nodeId] = result.cost;
        diagnostics.push(...result.diagnostics);
      }
    }
    for (const targetId of [...(outgoingNodes.get(nodeId) ?? [])].sort()) {
      const next = (indegree.get(targetId) ?? 1) - 1;
      indegree.set(targetId, next);
      if (next === 0) ready.push(targetId);
    }
    ready.sort();
  }

  for (const node of graph.nodes.filter((item) => !visited.has(item.node_id))) {
    const item = diagnostic("GRAPH_CYCLE_UNSUPPORTED", "blocking", "Draft graph contains an unsupported cycle.", [node.node_id]);
    diagnostics.push(item);
    nodeShapes[node.node_id] = Object.fromEntries(
      node.ports.filter((port) => port.direction === "output").map((port) => [port.name, blocked([item.diagnosticId])]),
    );
    nodeCosts[node.node_id] = EMPTY_COST;
  }

  const parameterTermsByGroup = new Map<string, string>();
  for (const node of [...graph.nodes].sort((left, right) => left.node_id.localeCompare(right.node_id))) {
    const parameterCount = nodeCosts[node.node_id]?.parameterCount;
    if (!parameterCount) continue;
    const groupId = node.parameter_group_id ?? `node:${node.node_id}`;
    const existing = parameterTermsByGroup.get(groupId);
    if (existing && existing !== parameterCount) {
      diagnostics.push(diagnostic(
        "SHARED_PARAMETER_COST_MISMATCH",
        "blocking",
        `Shared parameter group ${groupId} has inconsistent parameter estimates.`,
        [node.node_id, groupId],
      ));
      continue;
    }
    parameterTermsByGroup.set(groupId, parameterCount);
  }
  const parameterTerms = [...parameterTermsByGroup.values()];
  const flopTerms = Object.values(nodeCosts).flatMap((cost) => cost.flops ? [cost.flops] : []);
  return {
    documentDigest: await sha256({ nodes: graph.nodes, edges: graph.edges }),
    registryDigest: MODULE_REGISTRY.bundle_digest,
    nodeShapes,
    diagnostics: diagnostics.sort((left, right) => left.diagnosticId.localeCompare(right.diagnosticId)),
    nodeCosts,
    graphCost: {
      parameterCount: parameterTerms.length ? parameterTerms.join("+") : null,
      flops: flopTerms.length ? flopTerms.join("+") : null,
      assumptions: [...new Set(Object.values(nodeCosts).flatMap((cost) => cost.assumptions))],
    },
  };
}
