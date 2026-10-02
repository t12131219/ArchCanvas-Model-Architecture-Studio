import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import type { ExactEdge, ExactNode, StudioStatePayload } from "../domain/source-backed-scene";
import { projectEncoderDecoderProfile } from "./encoder-decoder-profile";
import { projectToScene } from "./project-to-scene";

function transformerState(): StudioStatePayload {
  const raw = JSON.parse(readFileSync(resolve(process.cwd(), "src/scene-studio/fixtures/transformer.json"), "utf8")) as Partial<StudioStatePayload> & {
    architecture: StudioStatePayload["architecture"] & { framework?: string };
  };
  return {
    ...raw,
    project: {
      project_id: "test-project:transformer",
      root: "/fixture/transformer",
      generation: 1,
      framework: raw.architecture.framework ?? "pytorch",
    },
    snapshot: {
      project_root: "/fixture/transformer",
      entrypoint: raw.architecture.entrypoint,
      revision: "fixture",
      source_files: [],
    },
    evidence: raw.evidence ?? [],
    document: raw.document ?? { source_digest: "0".repeat(64) },
    architecture: raw.architecture,
    hierarchy: raw.hierarchy!,
  };
}

function fixtureState(name: string): StudioStatePayload {
  const raw = JSON.parse(readFileSync(resolve(process.cwd(), `src/scene-studio/fixtures/${name}.json`), "utf8")) as Partial<StudioStatePayload> & {
    architecture: StudioStatePayload["architecture"] & { framework?: string };
  };
  return {
    ...raw,
    project: {
      project_id: `test-project:${name}`,
      root: `/fixture/${name}`,
      generation: 1,
      framework: raw.architecture.framework ?? "pytorch",
    },
    snapshot: {
      project_root: `/fixture/${name}`,
      entrypoint: raw.architecture.entrypoint,
      revision: "fixture",
      source_files: [],
    },
    evidence: raw.evidence ?? [],
    document: raw.document ?? { source_digest: "0".repeat(64) },
    architecture: raw.architecture,
    hierarchy: raw.hierarchy!,
  };
}

function nodeBySlot(scene: ReturnType<typeof projectToScene>, slot: string) {
  return scene.nodes.find((node) => node.scene_node_id.endsWith(`profile:${slot}`));
}

function edgeBetween(scene: ReturnType<typeof projectToScene>, sourceSlot: string, targetSlot: string) {
  const source = nodeBySlot(scene, sourceSlot)?.scene_node_id;
  const target = nodeBySlot(scene, targetSlot)?.scene_node_id;
  return scene.edges.find((edge) => edge.source_scene_node_id === source && edge.target_scene_node_id === target);
}

function t2tNode(nodeId: string, semanticName: string, assignedSymbol: string, kind = "operator"): ExactNode {
  return {
    node_id: nodeId,
    semantic_name: semanticName,
    kind,
    parent_id: "node:transformer",
    evidence_ids: [`evidence:${nodeId}`],
    attributes: { assigned_symbol: assignedSymbol, source_expression: semanticName },
    input_ports: [],
    output_ports: [],
  };
}

function t2tEdge(index: number, producerId: string, consumerId: string, role: string): ExactEdge {
  return {
    edge_id: `edge:${index}`,
    tensor_id: `tensor:${role}`,
    producer_id: producerId,
    producer_port: `port:${producerId}:out`,
    consumer_id: consumerId,
    consumer_port: `port:${consumerId}:in`,
    role,
    edge_type: /bias/.test(role) ? "condition" : role === "encoder_output" ? "memory" : "main",
    evidence_ids: [`evidence:edge:${index}`],
  };
}

function tensor2tensorState(): StudioStatePayload {
  const state = transformerState();
  const nodes = [
    t2tNode("node:inputs", "features.get", "inputs"),
    t2tNode("node:targets", "Subscript", "targets"),
    t2tNode("node:target-space", "features.get", "target_space"),
    t2tNode("node:encoder-prepare", "transformer_prepare_encoder", "encoder_input"),
    t2tNode("node:decoder-prepare", "transformer_prepare_decoder", "decoder_input"),
    t2tNode("node:encoder", "transformer_encoder", "encoder_output", "module_container"),
    t2tNode("node:decoder", "transformer_decoder", "decoder_output", "module_container"),
    {
      ...t2tNode("node:output", "Model output", "model_output", "input_output"),
      attributes: { io: "output", assigned_symbol: "model_output" },
    },
  ];
  const edges = [
    t2tEdge(1, "node:inputs", "node:encoder-prepare", "inputs"),
    t2tEdge(2, "node:target-space", "node:encoder-prepare", "target_space"),
    t2tEdge(3, "node:encoder-prepare", "node:encoder", "encoder_input"),
    t2tEdge(4, "node:targets", "node:decoder-prepare", "targets"),
    t2tEdge(5, "node:decoder-prepare", "node:decoder", "decoder_input"),
    t2tEdge(6, "node:encoder", "node:decoder", "encoder_output"),
    t2tEdge(7, "node:decoder", "node:output", "decoder_output"),
  ];
  return {
    ...state,
    architecture: { ...state.architecture, nodes, edges },
    hierarchy: {
      ...state.hierarchy,
      nodes: nodes.map((node, index) => ({
        hierarchy_node_id: `hierarchy:${index}`,
        semantic_name: node.semantic_name,
        depth: 1,
        canonical_node_ids: [node.node_id],
      })),
    },
  };
}

function authoritativeClassicState(): StudioStatePayload {
  const state = transformerState();
  const nodes = [
    t2tNode("node:input.src", "src", "src", "input_output"),
    t2tNode("node:input.tgt", "tgt", "tgt", "input_output"),
    t2tNode("node:input.src_key_padding_mask", "src_key_padding_mask", "src_key_padding_mask", "input_output"),
    t2tNode("node:input.tgt_key_padding_mask", "tgt_key_padding_mask", "tgt_key_padding_mask", "input_output"),
    t2tNode("node:input.tgt_mask", "tgt_mask", "tgt_mask", "input_output"),
    { ...t2tNode("node:memory", "self.encode", "memory"), attributes: { assigned_symbol: "memory", op_type: "self.encode", source_expression: "self.encode(src, src_key_padding_mask)" } },
    { ...t2tNode("node:decoder_out", "self.decode", "decoder_out"), attributes: { assigned_symbol: "decoder_out", op_type: "self.decode", source_expression: "self.decode(tgt=tgt, memory=memory)" } },
    { ...t2tNode("node:generator", "generator", "model_result"), attributes: { assigned_symbol: "model_result", module_path: "self.generator", op_type: "nn.Linear" } },
    { ...t2tNode("node:output.model", "Model output", "model_output", "input_output"), attributes: { assigned_symbol: "model_output", io: "output" } },
  ];
  for (const node of nodes.filter((item) => item.node_id.startsWith("node:input."))) node.attributes.io = "input";
  const edges = [
    t2tEdge(1, "node:input.src", "node:memory", "src"),
    { ...t2tEdge(2, "node:input.src_key_padding_mask", "node:memory", "src_key_padding_mask"), edge_type: "condition" as const },
    t2tEdge(3, "node:input.tgt", "node:decoder_out", "tgt"),
    { ...t2tEdge(4, "node:memory", "node:decoder_out", "memory"), edge_type: "memory" as const },
    { ...t2tEdge(5, "node:input.tgt_mask", "node:decoder_out", "tgt_mask"), edge_type: "condition" as const },
    { ...t2tEdge(6, "node:input.tgt_key_padding_mask", "node:decoder_out", "tgt_key_padding_mask"), edge_type: "condition" as const },
    { ...t2tEdge(7, "node:input.src_key_padding_mask", "node:decoder_out", "src_key_padding_mask"), edge_type: "condition" as const },
    t2tEdge(8, "node:decoder_out", "node:generator", "decoder_out"),
    t2tEdge(9, "node:generator", "node:output.model", "model_result"),
  ];
  return {
    ...state,
    architecture: { ...state.architecture, entrypoint: "transformer:Transformer", nodes, edges },
    hierarchy: {
      ...state.hierarchy,
      nodes: nodes.map((node, index) => ({
        hierarchy_node_id: `hierarchy:classic:${index}`,
        semantic_name: node.semantic_name,
        depth: 1,
        canonical_node_ids: [node.node_id],
      })),
    },
  };
}

describe("encoder-decoder structural profile", () => {
  it("keeps source, shifted target, and model output as separate evidence-backed slots", () => {
    const scene = projectToScene(transformerState(), "paper-publication");
    const source = nodeBySlot(scene, "source-input");
    const target = nodeBySlot(scene, "target-input");
    const output = nodeBySlot(scene, "output");

    expect(source?.canonical_node_ids).toContain("node:input.src");
    expect(target?.canonical_node_ids).toContain("node:input.tgt");
    expect(output?.canonical_node_ids).toContain("node:output.model");
    expect(target?.canonical_node_ids).not.toContain("node:output.model");
    expect(output?.canonical_node_ids).not.toContain("node:input.tgt");
  });

  it("preserves the paper dual-lane, bottom-to-top composition", () => {
    const scene = projectToScene(transformerState(), "paper-publication");
    const source = nodeBySlot(scene, "source-input")!;
    const encoder = nodeBySlot(scene, "encoder")!;
    const target = nodeBySlot(scene, "target-input")!;
    const decoder = nodeBySlot(scene, "decoder")!;
    const generator = nodeBySlot(scene, "generator")!;
    const output = nodeBySlot(scene, "output")!;

    expect(encoder.bounds.x).toBeLessThan(decoder.bounds.x);
    expect(source.bounds.x).toBeLessThan(target.bounds.x);
    expect(source.bounds.y).toBeGreaterThan(encoder.bounds.y);
    expect(target.bounds.y).toBeGreaterThan(decoder.bounds.y);
    expect(output.bounds.y).toBeLessThan(generator.bounds.y);
    expect(source.layout_lane).toBe("encoder");
    expect(encoder.layout_rank).toBe(3);
    expect(target.layout_lane).toBe("decoder");
    expect(decoder.layout_rank).toBe(3);
    expect(output.layout_rank).toBe(6);
  });

  it("retains the memory, target-mask, and output-chain relations", () => {
    const scene = projectToScene(transformerState(), "paper-publication");
    expect(edgeBetween(scene, "memory", "decoder")).toMatchObject({ relation: "memory", target_port_role: "memory" });
    expect(edgeBetween(scene, "target-mask", "decoder")).toMatchObject({ relation: "condition", target_port_role: "mask" });
    expect(edgeBetween(scene, "source-mask", "encoder")).toMatchObject({ relation: "condition", target_port_role: "mask" });
    expect(edgeBetween(scene, "decoder", "generator")).toBeDefined();
    expect(edgeBetween(scene, "generator", "softmax")).toBeDefined();
    expect(edgeBetween(scene, "softmax", "output")).toBeDefined();
  });

  it("uses the Tensor2Tensor prepare, bias, shared-softmax, and dual-lane grammar", () => {
    const state = tensor2tensorState();
    const engineering = projectEncoderDecoderProfile(state, "engineering-flow")!;
    const paper = projectEncoderDecoderProfile(state, "paper-publication")!;
    const engineeringScene = projectToScene(state, "engineering-flow");
    const bySlot = (slot: string) => paper.nodes.find((node) => node.attributes.profile_slot === slot);

    expect(engineering.nodes).toHaveLength(14);
    expect(paper.nodes).toHaveLength(12);
    expect(bySlot("source-position")).toMatchObject({
      semantic_name: "Target Space",
      attributes: { profile_shape: "condition" },
    });
    expect(bySlot("source-embedding")?.semantic_name).toBe("Encoder Prepare");
    expect(bySlot("target-embedding")?.semantic_name).toBe("Decoder Prepare");
    expect(bySlot("encoder")?.projected_canonical_node_ids).toEqual(["node:encoder"]);
    expect(bySlot("memory")?.projected_canonical_node_ids).toEqual([]);
    expect(bySlot("generator")).toMatchObject({
      semantic_name: "Shared Softmax",
      projected_canonical_node_ids: [],
    });
    expect(paper.edges).toHaveLength(11);
    expect(nodeBySlot(engineeringScene, "encoder")?.bounds).toEqual({ x: 670, y: 150, width: 210, height: 132 });
    expect(nodeBySlot(engineeringScene, "decoder")?.bounds).toEqual({ x: 972, y: 450, width: 226, height: 132 });
    expect(nodeBySlot(engineeringScene, "source-embedding")?.bounds).toEqual({ x: 218, y: 164, width: 202, height: 106 });
    expect(nodeBySlot(engineeringScene, "target-embedding")?.bounds).toEqual({ x: 218, y: 506, width: 202, height: 106 });
  });

  it("projects the sparse authoritative classic forward graph without requiring explicit softmax calls", () => {
    const state = authoritativeClassicState();
    const engineering = projectEncoderDecoderProfile(state, "engineering-flow")!;
    const paper = projectEncoderDecoderProfile(state, "paper-publication")!;
    const engineeringScene = projectToScene(state, "engineering-flow");
    const bySlot = (slot: string) => paper.nodes.find((node) => node.attributes.profile_slot === slot);

    expect(engineering.nodes).toHaveLength(13);
    expect(engineering.edges).toHaveLength(13);
    expect(paper.nodes).toHaveLength(16);
    expect(bySlot("encoder")?.projected_canonical_node_ids).toEqual([]);
    expect(bySlot("memory")?.projected_canonical_node_ids).toEqual(["node:memory"]);
    expect(bySlot("decoder")?.projected_canonical_node_ids).toEqual(["node:decoder_out"]);
    expect(bySlot("softmax")?.projected_canonical_node_ids).toEqual([]);
    expect(paper.edges).toHaveLength(15);
    expect(nodeBySlot(engineeringScene, "encoder")).toMatchObject({
      detail_kind: "transformer-encoder",
      hierarchy_expandable: false,
    });
    expect(nodeBySlot(engineeringScene, "decoder")).toMatchObject({
      detail_kind: "transformer-decoder",
      hierarchy_expandable: false,
    });
  });

  it("does not coerce decomposition encoder-decoder graphs into the Transformer profile", () => {
    const state = fixtureState("autoformer");

    expect(projectEncoderDecoderProfile(state, "engineering-flow")).toBeNull();
    expect(projectEncoderDecoderProfile(state, "paper-publication")).toBeNull();
  });
});
