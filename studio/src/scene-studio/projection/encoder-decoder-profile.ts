import type {
  ExactEdge,
  ExactNode,
  StudioStatePayload,
  ViewPresetId,
} from "../domain/source-backed-scene";
import type { NodeDetailKind, NodeShape } from "../types";

export interface ProfileNode extends ExactNode {
  projected_canonical_node_ids: string[];
}

export interface ProfileEdge extends ExactEdge {
  projected_canonical_edge_ids: string[];
  projected_tensor_ids: string[];
}

export interface EncoderDecoderProfile {
  nodes: ProfileNode[];
  edges: ProfileEdge[];
}

type SlotId =
  | "source-input"
  | "source-embedding"
  | "source-position"
  | "source-add"
  | "source-mask"
  | "encoder-call"
  | "encoder"
  | "memory"
  | "target-input"
  | "target-embedding"
  | "target-position"
  | "target-add"
  | "target-mask"
  | "decoder-call"
  | "decoder"
  | "generator"
  | "softmax"
  | "output";

interface SlotDefinition {
  id: SlotId;
  label: string;
  secondary: string;
  kind: string;
  shape: NodeShape;
  paperTone: "encoder" | "decoder" | "input" | "output" | "neutral";
  paperBounds: { x: number; y: number; width: number; height: number };
  engineeringBounds: { x: number; y: number; width: number; height: number };
}

const SLOT_DEFINITIONS: Record<SlotId, SlotDefinition> = {
  "source-input": {
    id: "source-input", label: "Inputs", secondary: "source sequence", kind: "input_output", shape: "io", paperTone: "input",
    paperBounds: { x: 235, y: 980, width: 240, height: 66 },
    engineeringBounds: { x: 34, y: 164, width: 150, height: 78 },
  },
  "source-embedding": {
    id: "source-embedding", label: "Input Embedding", secondary: "tokens to model features", kind: "operator", shape: "tensor", paperTone: "input",
    paperBounds: { x: 235, y: 885, width: 240, height: 66 },
    engineeringBounds: { x: 218, y: 150, width: 202, height: 106 },
  },
  "source-position": {
    id: "source-position", label: "Positional Encoding", secondary: "sequence position", kind: "operator", shape: "operation", paperTone: "neutral",
    paperBounds: { x: 72, y: 893, width: 126, height: 50 },
    engineeringBounds: { x: 224, y: 44, width: 190, height: 72 },
  },
  "source-add": {
    id: "source-add", label: "+", secondary: "embedding + position", kind: "merge_event", shape: "add", paperTone: "neutral",
    paperBounds: { x: 326, y: 808, width: 58, height: 58 },
    engineeringBounds: { x: 456, y: 168, width: 58, height: 58 },
  },
  "source-mask": {
    id: "source-mask", label: "Source Mask", secondary: "padding / attention condition", kind: "condition", shape: "condition", paperTone: "neutral",
    paperBounds: { x: 55, y: 704, width: 148, height: 56 },
    engineeringBounds: { x: 510, y: 42, width: 210, height: 72 },
  },
  "encoder-call": {
    id: "encoder-call", label: "Encoder call", secondary: "states + source mask", kind: "merge_event", shape: "merge", paperTone: "neutral",
    paperBounds: { x: 326, y: 808, width: 58, height: 58 },
    engineeringBounds: { x: 470, y: 164, width: 144, height: 106 },
  },
  encoder: {
    id: "encoder", label: "Encoder · N ×", secondary: "self-attention · FFN", kind: "module_container", shape: "attention", paperTone: "encoder",
    paperBounds: { x: 205, y: 550, width: 300, height: 210 },
    engineeringBounds: { x: 670, y: 130, width: 224, height: 132 },
  },
  memory: {
    id: "memory", label: "Encoder Memory", secondary: "contextual source states", kind: "tensor", shape: "tensor", paperTone: "encoder",
    paperBounds: { x: 235, y: 454, width: 240, height: 66 },
    engineeringBounds: { x: 956, y: 154, width: 178, height: 84 },
  },
  "target-input": {
    id: "target-input", label: "Outputs", secondary: "shifted-right target sequence", kind: "input_output", shape: "io", paperTone: "output",
    paperBounds: { x: 785, y: 980, width: 240, height: 66 },
    engineeringBounds: { x: 34, y: 512, width: 150, height: 78 },
  },
  "target-embedding": {
    id: "target-embedding", label: "Output Embedding", secondary: "target features", kind: "operator", shape: "tensor", paperTone: "output",
    paperBounds: { x: 785, y: 885, width: 240, height: 66 },
    engineeringBounds: { x: 218, y: 498, width: 202, height: 106 },
  },
  "target-position": {
    id: "target-position", label: "Positional Encoding", secondary: "sequence position", kind: "operator", shape: "operation", paperTone: "neutral",
    paperBounds: { x: 1062, y: 893, width: 126, height: 50 },
    engineeringBounds: { x: 224, y: 638, width: 190, height: 72 },
  },
  "target-add": {
    id: "target-add", label: "+", secondary: "embedding + position", kind: "merge_event", shape: "add", paperTone: "neutral",
    paperBounds: { x: 876, y: 808, width: 58, height: 58 },
    engineeringBounds: { x: 456, y: 516, width: 58, height: 58 },
  },
  "target-mask": {
    id: "target-mask", label: "Target Mask", secondary: "padding + causal", kind: "condition", shape: "condition", paperTone: "neutral",
    paperBounds: { x: 1055, y: 704, width: 150, height: 56 },
    engineeringBounds: { x: 516, y: 648, width: 218, height: 72 },
  },
  "decoder-call": {
    id: "decoder-call", label: "Decoder call", secondary: "states + memory + masks", kind: "merge_event", shape: "merge", paperTone: "neutral",
    paperBounds: { x: 876, y: 808, width: 58, height: 58 },
    engineeringBounds: { x: 690, y: 480, width: 160, height: 106 },
  },
  decoder: {
    id: "decoder", label: "Decoder · N ×", secondary: "masked self · cross-attn · FFN", kind: "module_container", shape: "attention", paperTone: "decoder",
    paperBounds: { x: 745, y: 410, width: 320, height: 350 },
    engineeringBounds: { x: 972, y: 446, width: 238, height: 132 },
  },
  generator: {
    id: "generator", label: "Linear", secondary: "model features to vocabulary", kind: "operator", shape: "operation", paperTone: "neutral",
    paperBounds: { x: 785, y: 315, width: 240, height: 64 },
    engineeringBounds: { x: 1270, y: 466, width: 190, height: 92 },
  },
  softmax: {
    id: "softmax", label: "Softmax", secondary: "logits to probabilities", kind: "operator", shape: "operation", paperTone: "neutral",
    paperBounds: { x: 785, y: 225, width: 240, height: 64 },
    engineeringBounds: { x: 1498, y: 466, width: 174, height: 82 },
  },
  output: {
    id: "output", label: "Output", secondary: "model result", kind: "input_output", shape: "io", paperTone: "output",
    paperBounds: { x: 785, y: 130, width: 240, height: 66 },
    engineeringBounds: { x: 1500, y: 466, width: 142, height: 82 },
  },
};

function unique(values: string[]): string[] {
  return [...new Set(values)].sort();
}

function semanticText(node: ExactNode): string {
  const sourceSymbol = (node as ExactNode & { source_symbol?: string }).source_symbol ?? "";
  const attributes = Object.values(node.attributes)
    .filter((value): value is string => typeof value === "string")
    .join(" ");
  return `${node.node_id} ${node.semantic_name} ${sourceSymbol} ${attributes}`.toLowerCase();
}

function inputRole(node: ExactNode): "source" | "target" | "mask" | null {
  const text = semanticText(node);
  const io = String(node.attributes.io ?? "").toLowerCase();
  const assigned = String(node.attributes.assigned_symbol ?? "").toLowerCase();
  const portRoles = [...node.input_ports, ...node.output_ports].map((port) => port.role.toLowerCase()).join(" ");
  if (io === "output") return null;
  if (io !== "input" && node.kind.toLowerCase() !== "input_output") return null;
  if (/(mask|bias|causal)/.test(`${text} ${portRoles}`)) return "mask";
  if (assigned === "features") return null;
  if (assigned === "targets" || assigned === "target") return "target";
  if (assigned === "inputs" || assigned === "input") return "source";
  return /(target|tgt|decoder|shift)/.test(`${text} ${portRoles}`) ? "target" : "source";
}

function isOutputNode(node: ExactNode): boolean {
  const io = String(node.attributes.io ?? "").toLowerCase();
  return io === "output" || (node.kind.toLowerCase() === "input_output" && /(output|result|logits|probabil)/.test(semanticText(node)));
}

function roleFromText(node: ExactNode): SlotId | null {
  const text = semanticText(node);
  const assigned = String(node.attributes.assigned_symbol ?? "").toLowerCase();
  if (/transformer_prepare_encoder/.test(text)) return "source-embedding";
  if (/transformer_prepare_decoder/.test(text)) return "target-embedding";
  if (/transformer_encoder/.test(text)) return "encoder";
  if (/transformer_decoder/.test(text)) return "decoder";
  if (assigned === "encoder_input") return "source-embedding";
  if (assigned === "decoder_input") return "target-embedding";
  if (/target_space/.test(text)) return "source-position";
  const input = inputRole(node);
  if (input === "mask") return /(source|encoder|padding)/.test(text) && !/(target|tgt|decoder|causal)/.test(text)
    ? "source-mask"
    : "target-mask";
  if (input === "source") return "source-input";
  if (input === "target") return "target-input";
  if (isOutputNode(node)) return "output";
  if (/self\.decode/.test(text)) return "decoder";
  if (/self\.encode/.test(text)) return "encoder";
  if (/(softmax|probabil)/.test(text) && !/(enc_|dec_|cross_|attention)/.test(text)) return "softmax";
  if (/(generator|lm_head|vocab|vocabulary|output_projection|shared_softmax)/.test(text)) return "generator";
  if (/(embedding|embed)/.test(text)) return /(target|tgt|decoder|output)/.test(text) ? "target-embedding" : "source-embedding";
  if (/(position|positional|timing_signal|timing signal)/.test(text)) return /(target|tgt|decoder|output)/.test(text) ? "target-position" : "source-position";
  if (/(mask|bias|causal)/.test(text)) return /(source|encoder|padding)/.test(text) && !/(target|tgt|decoder|causal)/.test(text)
    ? "source-mask"
    : "target-mask";
  if (/(cross|encdec|encoder_decoder)/.test(text)) return "decoder";
  if (/(decoder|self\.decode|(^|[^a-z])dec[_\.])/.test(text)) return "decoder";
  if (/(encoder|self\.encode|(^|[^a-z])enc[_\.])/.test(text)) return "encoder";
  return null;
}

function propagationRole(
  nodeId: string,
  roles: ReadonlyMap<string, SlotId>,
  incoming: ReadonlyMap<string, string[]>,
  outgoing: ReadonlyMap<string, string[]>,
): SlotId | null {
  const neighboring = [
    ...(incoming.get(nodeId) ?? []).map((id) => roles.get(id)),
    ...(outgoing.get(nodeId) ?? []).map((id) => roles.get(id)),
  ].filter((role): role is SlotId => Boolean(role));
  if (neighboring.includes("decoder")) return "decoder";
  if (neighboring.includes("encoder")) return "encoder";
  return null;
}

function detailKind(slot: SlotId, paper: boolean, tensor2tensor: boolean): NodeDetailKind | undefined {
  if (slot === "encoder") {
    if (paper) return tensor2tensor ? "paper-tensor2tensor-encoder" : "paper-transformer-encoder";
    return tensor2tensor ? "tensor2tensor-encoder" : "transformer-encoder";
  }
  if (slot === "decoder") {
    if (paper) return tensor2tensor ? "paper-tensor2tensor-decoder" : "paper-transformer-decoder";
    return tensor2tensor ? "tensor2tensor-decoder" : "transformer-decoder";
  }
  if (slot === "source-embedding" || slot === "target-embedding") {
    if (tensor2tensor) return paper ? "paper-tensor-transform" : "tensor-transform";
    return paper ? "paper-sinusoidal-embedding" : "sinusoidal-embedding";
  }
  return undefined;
}

function edgeRelation(edge: ExactEdge): string {
  return `${edge.edge_type} ${edge.role}`.toLowerCase();
}

interface ProfileSkeletonEdge {
  source: SlotId;
  target: SlotId;
  relation: "flow" | "condition" | "memory" | "merge";
  role: string;
  factPairs: Array<[SlotId, SlotId]>;
}

function tensor2tensorSkeletonEdges(paper: boolean): ProfileSkeletonEdge[] {
  const head: ProfileSkeletonEdge[] = paper
    ? [
      { source: "source-input", target: "source-embedding", relation: "flow", role: "inputs", factPairs: [["source-input", "source-embedding"]] },
      { source: "source-position", target: "source-input", relation: "condition", role: "target space", factPairs: [["source-position", "source-embedding"]] },
      { source: "source-embedding", target: "encoder", relation: "flow", role: "encoder input", factPairs: [["source-embedding", "encoder"], ["source-input", "encoder"]] },
      { source: "source-mask", target: "encoder", relation: "condition", role: "bias", factPairs: [["source-mask", "encoder"], ["source-embedding", "encoder"]] },
      { source: "target-input", target: "target-embedding", relation: "flow", role: "targets", factPairs: [["target-input", "target-embedding"]] },
      { source: "target-embedding", target: "decoder", relation: "flow", role: "decoder input", factPairs: [["target-embedding", "decoder"], ["target-input", "decoder"]] },
      { source: "target-mask", target: "decoder", relation: "condition", role: "causal bias", factPairs: [["target-mask", "decoder"], ["target-embedding", "decoder"]] },
    ]
    : [
      { source: "source-input", target: "source-embedding", relation: "flow", role: "inputs", factPairs: [["source-input", "source-embedding"]] },
      { source: "source-position", target: "source-input", relation: "condition", role: "target space", factPairs: [["source-position", "source-embedding"]] },
      { source: "source-embedding", target: "encoder-call", relation: "flow", role: "encoder input", factPairs: [["source-embedding", "encoder"]] },
      { source: "source-mask", target: "encoder-call", relation: "condition", role: "encoder bias", factPairs: [["source-mask", "encoder"], ["source-embedding", "encoder"]] },
      { source: "encoder-call", target: "encoder", relation: "flow", role: "states + bias", factPairs: [["source-embedding", "encoder"]] },
      { source: "target-input", target: "target-embedding", relation: "flow", role: "targets", factPairs: [["target-input", "target-embedding"]] },
      { source: "target-embedding", target: "decoder-call", relation: "flow", role: "shifted decoder input", factPairs: [["target-embedding", "decoder"]] },
      { source: "target-mask", target: "decoder-call", relation: "condition", role: "decoder bias", factPairs: [["target-mask", "decoder"], ["target-embedding", "decoder"]] },
      { source: "source-mask", target: "decoder-call", relation: "condition", role: "enc-dec bias", factPairs: [["source-mask", "decoder"], ["source-embedding", "decoder"]] },
      { source: "decoder-call", target: "decoder", relation: "flow", role: "states + memory + biases", factPairs: [["target-embedding", "decoder"]] },
    ];
  return [
    ...head,
    { source: "encoder", target: "memory", relation: "flow", role: "encoder output", factPairs: [["encoder", "memory"]] },
    { source: "memory", target: paper ? "decoder" : "decoder-call", relation: "memory", role: "K,V memory", factPairs: [["memory", "decoder"], ["encoder", "decoder"]] },
    { source: "decoder", target: "generator", relation: "flow", role: "decoder output", factPairs: [["decoder", "generator"], ["decoder", "output"]] },
    { source: "generator", target: "output", relation: "flow", role: "shared logits", factPairs: [["generator", "output"], ["decoder", "output"]] },
  ];
}

function skeletonEdges(paper: boolean, hasSoftmax: boolean, tensor2tensor: boolean): ProfileSkeletonEdge[] {
  if (tensor2tensor) return tensor2tensorSkeletonEdges(paper);
  const head: ProfileSkeletonEdge[] = paper
    ? [
      { source: "source-input", target: "source-embedding", relation: "flow", role: "", factPairs: [] },
      { source: "source-embedding", target: "source-add", relation: "flow", role: "", factPairs: [] },
      { source: "source-position", target: "source-add", relation: "merge", role: "position", factPairs: [] },
      { source: "source-add", target: "encoder", relation: "flow", role: "", factPairs: [["source-input", "encoder"]] },
      { source: "source-mask", target: "encoder", relation: "condition", role: "mask", factPairs: [["source-mask", "encoder"]] },
      { source: "target-input", target: "target-embedding", relation: "flow", role: "", factPairs: [] },
      { source: "target-embedding", target: "target-add", relation: "flow", role: "", factPairs: [] },
      { source: "target-position", target: "target-add", relation: "merge", role: "position", factPairs: [] },
      { source: "target-add", target: "decoder", relation: "flow", role: "", factPairs: [["target-input", "decoder"]] },
      { source: "target-mask", target: "decoder", relation: "condition", role: "causal mask", factPairs: [["target-mask", "decoder"]] },
    ]
    : [
      { source: "source-input", target: "source-embedding", relation: "flow", role: "token ids", factPairs: [] },
      { source: "source-embedding", target: "encoder-call", relation: "flow", role: "states", factPairs: [] },
      { source: "source-mask", target: "encoder-call", relation: "condition", role: "source mask", factPairs: [["source-mask", "encoder"]] },
      { source: "encoder-call", target: "encoder", relation: "flow", role: "encoder input", factPairs: [["source-input", "encoder"]] },
      { source: "target-input", target: "target-embedding", relation: "flow", role: "token ids", factPairs: [] },
      { source: "target-embedding", target: "decoder-call", relation: "flow", role: "shifted target", factPairs: [] },
      { source: "target-mask", target: "decoder-call", relation: "condition", role: "target mask", factPairs: [["target-mask", "decoder"]] },
      { source: "source-mask", target: "decoder-call", relation: "condition", role: "memory mask", factPairs: [["source-mask", "decoder"]] },
      { source: "memory", target: "decoder-call", relation: "memory", role: "memory", factPairs: [["memory", "decoder"], ["source-input", "decoder"], ["encoder", "decoder"]] },
      { source: "decoder-call", target: "decoder", relation: "flow", role: "decoder input", factPairs: [["target-input", "decoder"]] },
    ];
  const tail: ProfileSkeletonEdge[] = [
    { source: "encoder", target: "memory", relation: "flow", role: "", factPairs: [["encoder", "memory"]] },
    { source: "decoder", target: "generator", relation: "flow", role: "", factPairs: [["decoder", "generator"]] },
  ];
  if (paper) {
    tail.splice(1, 0, {
      source: "memory",
      target: "decoder",
      relation: "memory",
      role: "K,V memory",
      factPairs: [["memory", "decoder"], ["source-input", "decoder"], ["encoder", "decoder"]],
    });
  }
  if (hasSoftmax) {
    tail.push(
      { source: "generator", target: "softmax", relation: "flow", role: "", factPairs: [["generator", "softmax"]] },
      { source: "softmax", target: "output", relation: "flow", role: "", factPairs: [["softmax", "output"]] },
    );
  } else {
    tail.push({ source: "generator", target: "output", relation: "flow", role: "", factPairs: [["generator", "output"]] });
  }
  return [...head, ...tail];
}

function profilePresentation(
  definition: SlotDefinition,
  paper: boolean,
  tensor2tensor: boolean,
): Pick<SlotDefinition, "label" | "secondary"> & { bounds: SlotDefinition["paperBounds"] } {
  const base = {
    label: definition.label,
    secondary: definition.secondary,
    bounds: paper ? definition.paperBounds : definition.engineeringBounds,
  };
  if (!tensor2tensor) return base;
  const overrides: Partial<Record<SlotId, {
    label: string;
    secondary: string;
    paper?: SlotDefinition["paperBounds"];
    engineering?: SlotDefinition["engineeringBounds"];
  }>> = {
    "source-input": { label: "Inputs", secondary: "flatten4d3d · [B,S,H]", engineering: { x: 34, y: 176, width: 138, height: 82 } },
    "source-embedding": { label: "Encoder Prepare", secondary: "space embedding + timing", engineering: { x: 218, y: 164, width: 202, height: 106 } },
    "source-position": { label: "Target Space", secondary: "learned id embedding", paper: { x: 55, y: 893, width: 142, height: 50 }, engineering: { x: 34, y: 44, width: 174, height: 72 } },
    "source-mask": { label: "Encoder Bias", secondary: "ignore padding", paper: { x: 45, y: 704, width: 158, height: 56 }, engineering: { x: 34, y: 390, width: 206, height: 72 } },
    "encoder-call": { label: "Encoder call", secondary: "states + attention bias", engineering: { x: 470, y: 164, width: 144, height: 106 } },
    encoder: { label: paper ? "Encoder · N ×" : "Encoder Stack × N", secondary: "self-attention · conv FFN", engineering: { x: 670, y: 150, width: 210, height: 132 } },
    memory: { label: paper ? "Encoder Output" : "Encoder output", secondary: "memory + attention bias", engineering: { x: 956, y: 174, width: 170, height: 84 } },
    "target-input": { label: "Targets", secondary: "teacher forcing", engineering: { x: 34, y: 518, width: 138, height: 82 } },
    "target-embedding": { label: "Decoder Prepare", secondary: "shift-left + timing", engineering: { x: 218, y: 506, width: 202, height: 106 } },
    "target-mask": { label: "Decoder Bias", secondary: "lower triangle", paper: { x: 1050, y: 704, width: 158, height: 56 }, engineering: { x: 516, y: 650, width: 218, height: 72 } },
    "decoder-call": { label: "Decoder call", secondary: "states + memory + biases", engineering: { x: 724, y: 480, width: 174, height: 106 } },
    decoder: { label: paper ? "Decoder · N ×" : "Decoder Stack × N", secondary: "bias-masked attention · conv FFN", engineering: { x: 972, y: 450, width: 226, height: 132 } },
    generator: { label: "Shared Softmax", secondary: "tied embedding weights", engineering: { x: 1270, y: 468, width: 190, height: 92 } },
    output: { label: "Target Logits", secondary: "label-smoothed output", paper: { x: 785, y: 220, width: 240, height: 66 }, engineering: { x: 1500, y: 475, width: 142, height: 82 } },
  };
  const override = overrides[definition.id];
  return override
    ? {
      label: override.label,
      secondary: override.secondary,
      bounds: (paper ? override.paper : override.engineering) ?? base.bounds,
    }
    : base;
}

export function projectEncoderDecoderProfile(
  state: StudioStatePayload,
  presetId: ViewPresetId,
): EncoderDecoderProfile | null {
  if (presetId !== "engineering-flow" && presetId !== "paper-publication" && presetId !== "paper-transformer") return null;
  const nodes = [...state.architecture.nodes].sort((left, right) => left.node_id.localeCompare(right.node_id));
  const edges = [...state.architecture.edges].sort((left, right) => left.edge_id.localeCompare(right.edge_id));
  const roles = new Map<string, SlotId>();
  const incoming = new Map<string, string[]>();
  const outgoing = new Map<string, string[]>();
  for (const edge of edges) {
    incoming.set(edge.consumer_id, [...(incoming.get(edge.consumer_id) ?? []), edge.producer_id]);
    outgoing.set(edge.producer_id, [...(outgoing.get(edge.producer_id) ?? []), edge.consumer_id]);
  }
  for (const node of nodes) {
    const role = roleFromText(node);
    if (role) roles.set(node.node_id, role);
  }
  const tensor2tensor = nodes.some((node) => /(target_space|attention_bias|conv_hidden_relu|timing_signal|model_fn_body|transformer_prepare_)/.test(semanticText(node)));
  const hasDecompositionTopology = nodes.some((node) => (
    /(decomp|decomposition|seasonal|trend|autocorrelation|auto-correlation)/.test(semanticText(node))
  ));
  const initialRoles = new Set(roles.values());
  const hasEncoderDecoderPath = (initialRoles.has("encoder") || nodes.some((node) => /self\.encode/.test(semanticText(node))))
    && (initialRoles.has("decoder") || nodes.some((node) => /self\.decode/.test(semanticText(node))));
  const hasOutputHead = initialRoles.has("output");
  const hasMemoryEvidence = edges.some((edge) => edge.edge_type === "memory" || /memory/.test(edgeRelation(edge)))
    || nodes.some((node) => String(node.attributes.assigned_symbol ?? "").toLowerCase() === "memory");
  if (hasDecompositionTopology || !hasEncoderDecoderPath || !hasOutputHead || !hasMemoryEvidence) return null;

  for (let pass = 0; pass < nodes.length; pass += 1) {
    let changed = false;
    for (const node of nodes) {
      if (roles.has(node.node_id)) continue;
      const text = semanticText(node);
      if (!/(feed.?forward|ffn|activation|residual|norm|dropout|add)/.test(text)) continue;
      const role = propagationRole(node.node_id, roles, incoming, outgoing);
      if (role) {
        roles.set(node.node_id, role);
        changed = true;
      }
    }
    if (!changed) break;
  }

  const encoderIds = new Set([...roles].filter(([, role]) => role === "encoder").map(([id]) => id));
  const decoderIds = new Set([...roles].filter(([, role]) => role === "decoder").map(([id]) => id));
  const memoryCandidate = nodes
    .filter((node) => encoderIds.has(node.node_id))
    .filter((node) => (outgoing.get(node.node_id) ?? []).some((id) => decoderIds.has(id)))
    .sort((left, right) => {
      const leftNorm = /norm|memory|output/.test(semanticText(left)) ? 0 : 1;
      const rightNorm = /norm|memory|output/.test(semanticText(right)) ? 0 : 1;
      return leftNorm - rightNorm || left.node_id.localeCompare(right.node_id);
    })[0];
  if (memoryCandidate && !tensor2tensor) roles.set(memoryCandidate.node_id, "memory");

  for (const node of nodes) {
    if (roles.has(node.node_id)) continue;
    const role = propagationRole(node.node_id, roles, incoming, outgoing);
    if (role) roles.set(node.node_id, role);
  }

  const paper = presetId !== "engineering-flow";
  const hierarchyByCanonical = new Map<string, { id: string; parent?: string | null; childCount: number }>();
  const childCounts = new Map<string, number>();
  for (const item of state.hierarchy.nodes) {
    if (item.parent_hierarchy_node_id) childCounts.set(item.parent_hierarchy_node_id, (childCounts.get(item.parent_hierarchy_node_id) ?? 0) + 1);
  }
  for (const item of state.hierarchy.nodes) {
    for (const canonicalId of item.canonical_node_ids) {
      hierarchyByCanonical.set(canonicalId, {
        id: item.hierarchy_node_id,
        parent: item.parent_hierarchy_node_id,
        childCount: childCounts.get(item.hierarchy_node_id) ?? 0,
      });
    }
  }

  const grouped = new Map<SlotId, ExactNode[]>();
  for (const node of nodes) {
    const role = roles.get(node.node_id);
    if (!role) continue;
    grouped.set(role, [...(grouped.get(role) ?? []), node]);
  }
  const requiredSchematicSlots = new Set<SlotId>(tensor2tensor
    ? [
      "source-input", "source-embedding", "source-position", "source-mask",
      ...(paper ? [] : ["encoder-call"] as SlotId[]),
      "encoder", "memory", "target-input", "target-embedding", "target-mask",
      ...(paper ? [] : ["decoder-call"] as SlotId[]),
      "decoder", "generator", "output",
    ]
    : paper
      ? ["source-embedding", "source-position", "source-add", "source-mask", "encoder", "memory", "target-embedding", "target-position", "target-add", "target-mask", "decoder", "generator", "softmax", "output"]
      : ["source-embedding", "source-mask", "encoder-call", "encoder", "memory", "target-embedding", "target-mask", "decoder-call", "decoder", "generator", "output"]);
  const profileNodes: ProfileNode[] = [];
  for (const definition of Object.values(SLOT_DEFINITIONS)) {
    const facts = grouped.get(definition.id) ?? [];
    if (!facts.length && !requiredSchematicSlots.has(definition.id)) continue;
    if (paper && (definition.id === "encoder-call" || definition.id === "decoder-call")) continue;
    if (!paper && !tensor2tensor && (definition.id === "source-position" || definition.id === "source-add" || definition.id === "target-position" || definition.id === "target-add" || definition.id === "softmax")) continue;
    if (!paper && tensor2tensor && (definition.id === "source-add" || definition.id === "target-position" || definition.id === "target-add" || definition.id === "softmax")) continue;
    const canonicalIds = facts.map((node) => node.node_id).sort();
    const hierarchy = facts.map((node) => hierarchyByCanonical.get(node.node_id)).find(Boolean);
    const presentation = profilePresentation(definition, paper, tensor2tensor);
    const bounds = presentation.bounds;
    const actualLabel = !tensor2tensor && definition.id === "output" && !grouped.has("softmax") ? "Output Logits" : presentation.label;
    const secondary = facts.length ? presentation.secondary : `${presentation.secondary} · schematic`;
    profileNodes.push({
      node_id: `profile:${definition.id}`,
      semantic_name: actualLabel,
      kind: definition.kind,
      parent_id: null,
      evidence_ids: unique(facts.flatMap((node) => node.evidence_ids)),
      attributes: {
        profile_slot: definition.id,
        profile_x: bounds.x,
        profile_y: bounds.y,
        profile_width: bounds.width,
        profile_height: bounds.height,
        profile_shape: tensor2tensor && definition.id === "source-position" ? "condition" : definition.shape,
        profile_secondary: secondary,
        profile_paper_tone: definition.paperTone,
        profile_detail_kind: detailKind(definition.id, paper, tensor2tensor),
        hierarchy_node_id: hierarchy?.id,
        child_count: hierarchy?.childCount ?? 0,
      },
      input_ports: facts.flatMap((node) => node.input_ports),
      output_ports: facts.flatMap((node) => node.output_ports),
      projected_canonical_node_ids: canonicalIds,
    });
  }

  const slotByCanonical = new Map<string, SlotId>();
  for (const [canonicalId, slot] of roles) slotByCanonical.set(canonicalId, slot);
  const factsByPair = new Map<string, ExactEdge[]>();
  for (const edge of edges) {
    const source = slotByCanonical.get(edge.producer_id);
    const target = slotByCanonical.get(edge.consumer_id);
    if (!source || !target || source === target) continue;
    const key = `${source}\u0000${target}`;
    factsByPair.set(key, [...(factsByPair.get(key) ?? []), edge]);
  }
  const visibleSlots = new Set(profileNodes.map((node) => String(node.attributes.profile_slot) as SlotId));
  const profileEdges: ProfileEdge[] = skeletonEdges(paper, grouped.has("softmax") || (!tensor2tensor && paper), tensor2tensor).flatMap((spec) => {
    if (!visibleSlots.has(spec.source) || !visibleSlots.has(spec.target)) return [];
    const facts = unique(spec.factPairs.flatMap(([source, target]) => (
      factsByPair.get(`${source}\u0000${target}`)?.map((edge) => edge.edge_id) ?? []
    ))).map((edgeId) => edges.find((edge) => edge.edge_id === edgeId)!).filter(Boolean);
    return {
      edge_id: `profile:${spec.source}:${spec.target}`,
      tensor_id: facts[0]?.tensor_id ?? `schematic:${spec.source}:${spec.target}`,
      producer_id: `profile:${spec.source}`,
      producer_port: facts[0]?.producer_port ?? `schematic:${spec.source}:out`,
      consumer_id: `profile:${spec.target}`,
      consumer_port: facts[0]?.consumer_port ?? `schematic:${spec.target}:in`,
      role: spec.role || spec.relation,
      edge_type: spec.relation,
      evidence_ids: unique(facts.flatMap((edge) => edge.evidence_ids)),
      projected_canonical_edge_ids: facts.map((edge) => edge.edge_id).sort(),
      projected_tensor_ids: unique(facts.map((edge) => edge.tensor_id)),
    };
  });
  return { nodes: profileNodes, edges: profileEdges };
}
