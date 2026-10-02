import { describe, expect, it } from "vitest";

import type { StudioStatePayload } from "../domain/source-backed-scene";
import { ALL_VIEW_PRESETS } from "../domain/view-preset";
import { projectToScene } from "./project-to-scene";

function sourceState(): StudioStatePayload {
  return {
    project: { project_id: "project:any", root: "/workspace", generation: 3, framework: "pytorch" },
    architecture: {
      architecture_id: "architecture:1",
      entrypoint: "model.py:Model",
      nodes: [
        { node_id: "node:input", semantic_name: "Input", kind: "input_output", evidence_ids: ["evidence:input"], attributes: { io: "input" }, input_ports: [], output_ports: [{ port_id: "port:input", name: "x", direction: "output", role: "series" }] },
        { node_id: "node:linear", semantic_name: "Projection", kind: "operator", evidence_ids: ["evidence:linear"], attributes: { op_type: "nn.Linear" }, input_ports: [{ port_id: "port:linear:in", name: "x", direction: "input", role: "series" }], output_ports: [{ port_id: "port:linear:out", name: "y", direction: "output", role: "features" }] },
        { node_id: "node:output", semantic_name: "Output", kind: "input_output", evidence_ids: ["evidence:output"], attributes: { io: "output" }, input_ports: [{ port_id: "port:output", name: "y", direction: "input", role: "features" }], output_ports: [] },
      ],
      edges: [
        { edge_id: "edge:input:linear", tensor_id: "tensor:x", producer_id: "node:input", producer_port: "port:input", consumer_id: "node:linear", consumer_port: "port:linear:in", role: "series", edge_type: "main", evidence_ids: ["evidence:edge:1"] },
        { edge_id: "edge:linear:output", tensor_id: "tensor:y", producer_id: "node:linear", producer_port: "port:linear:out", consumer_id: "node:output", consumer_port: "port:output", role: "features", edge_type: "main", evidence_ids: ["evidence:edge:2"] },
      ],
    },
    snapshot: { project_root: "/workspace", entrypoint: "model.py:Model", revision: "r1", source_files: [{ path: "model.py", sha256: "a".repeat(64) }] },
    hierarchy: { root_node_id: "hierarchy:root", nodes: [] },
    evidence: [],
    semantic_overlay: { exact_ir_digest: "b".repeat(64), annotations: [] },
    document: { source_digest: "a".repeat(64) },
    integrity: { source_digest: "a".repeat(64), exact_ir_digest: "b".repeat(64) },
    view_state: {},
  };
}

describe("projectToScene", () => {
  it("projects two visual presets from one immutable semantic identity", () => {
    const state = sourceState();
    const engineering = projectToScene(state, "engineering-flow");
    const paper = projectToScene(state, "paper-publication");

    expect(engineering.sourceDigest).toBe(paper.sourceDigest);
    expect(engineering.exactIrDigest).toBe(paper.exactIrDigest);
    expect(engineering.nodes.flatMap((node) => node.canonical_node_ids ?? []).sort())
      .toEqual(paper.nodes.flatMap((node) => node.canonical_node_ids ?? []).sort());
    expect(engineering.edges.flatMap((edge) => edge.canonical_edge_ids ?? []).sort())
      .toEqual(paper.edges.flatMap((edge) => edge.canonical_edge_ids ?? []).sort());
    expect(engineering.layout_profile).toBe("freeform");
    expect(paper.layout_profile).toBe("paper");
    expect(engineering.nodes[0].bounds.x).not.toBe(paper.nodes[0].bounds.x);
  });

  it("keeps every declared preset source-backed and independently addressable", () => {
    const state = sourceState();
    const scenes = ALL_VIEW_PRESETS.map((preset) => projectToScene(state, preset));
    expect(new Set(scenes.map((scene) => scene.scene_id)).size).toBe(ALL_VIEW_PRESETS.length);
    expect(scenes.every((scene) => scene.nodes.length > 0 && scene.edges.length > 0)).toBe(true);
    expect(new Set(scenes.map((scene) => scene.sourceDigest))).toEqual(new Set([state.document.source_digest]));
    expect(scenes.find((scene) => scene.presetId === "paper-transformer")?.layout_profile).toBe("paper");
  });

  it("keeps named ports and evidence in stable scene bindings", () => {
    const scene = projectToScene(sourceState(), "engineering-flow");
    const projected = scene.nodes.find((node) => node.canonical_node_ids?.includes("node:linear"));
    expect(projected?.input_ports?.[0].port_id).toBe("port:linear:in");
    expect(projected?.output_ports?.[0].port_id).toBe("port:linear:out");
    expect(scene.bindings[projected!.scene_node_id]).toMatchObject({
      canonicalNodeIds: ["node:linear"],
      evidenceIds: ["evidence:linear"],
      fidelity: "exact",
      portBindings: { series: "port:linear:in", features: "port:linear:out" },
    });
  });

  it("replays geometry by the explicit hierarchy binding when canonical identity differs", () => {
    const state = sourceState();
    const linear = state.architecture.nodes.find((node) => node.node_id === "node:linear")!;
    linear.attributes.hierarchy_node_id = "hierarchy:group.projection";
    state.view_state = {
      node_positions: { "view:hierarchy:group.projection": { x: -120, y: 245 } },
      node_sizes: { "view:hierarchy:group.projection": { width: 230, height: 96 } },
    };

    const projected = projectToScene(state, "engineering-flow").nodes
      .find((node) => node.canonical_node_ids?.includes("node:linear"));
    expect(projected?.hierarchy_node_id).toBe("hierarchy:group.projection");
    expect(projected?.bounds).toEqual({ x: -120, y: 245, width: 230, height: 96 });
  });

  it("is deterministic when analyzer arrays arrive in a different order", () => {
    const first = sourceState();
    const second = sourceState();
    second.architecture.nodes.reverse();
    second.architecture.edges.reverse();
    expect(projectToScene(first, "engineering-flow")).toEqual(projectToScene(second, "engineering-flow"));
  });

  it("projects synthetic draft nodes and strict port bridges without forging canonical identity", () => {
    const state = sourceState();
    state.draft = {
      draft_id: "draft:test",
      revision: 2,
      base_registry_digest: "sha256:module-registry-v1",
      nodes: [{
        node_id: "draft:relu",
        semantic_name: "after_projection",
        framework: "pytorch",
        node_type: "pytorch.nn.relu",
        definition_ref: {
          definition_id: "pytorch.nn.relu",
          version: "1.0.0",
          digest: "sha256:pytorch-nn-relu-v1",
        },
        parameters: { inplace: false },
        ports: [
          { port_id: "draft:relu.input", name: "input", direction: "input", role: "input", accepted_relations: ["main"] },
          { port_id: "draft:relu.output", name: "output", direction: "output", role: "output", accepted_relations: ["main"] },
        ],
      }],
      edges: [
        { edge_id: "draft:incoming", source_port_id: "port:linear:out", target_port_id: "draft:relu.input", policy: "fanout", relation: "main", parameters: {} },
        { edge_id: "draft:outgoing", source_port_id: "draft:relu.output", target_port_id: "port:output", policy: "replace-input", relation: "main", parameters: {} },
      ],
      intents: [],
      lowering_status: "checking",
      proofs: [{
        intent_id: "intent:relu",
        status: "conditional",
        message: "awaiting adapter lowering",
        reason_codes: [],
        affected_subject_ids: ["draft:relu"],
      }],
      writeback_summary: { eligibility: "prepare", blocking_intent_ids: [] },
    };

    const scene = projectToScene(state, "engineering-flow");
    const draftNode = scene.nodes.find((node) => node.draft_node_id === "draft:relu");
    expect(draftNode).toMatchObject({
      draft_node_id: "draft:relu",
      draft_status: "conditional",
      input_ports: [{ port_id: "draft:relu.input" }],
      output_ports: [{ port_id: "draft:relu.output" }],
    });
    expect(draftNode?.canonical_node_ids).toBeUndefined();
    expect(scene.bindings[draftNode!.scene_node_id]).toMatchObject({
      canonicalNodeIds: [],
      draftNodeIds: ["draft:relu"],
      fidelity: "schematic",
    });
    expect(scene.edges.filter((edge) => edge.draft_edge_id).map((edge) => edge.draft_edge_id).sort())
      .toEqual(["draft:incoming", "draft:outgoing"]);
    expect(scene.edges.find((edge) => edge.draft_edge_id === "draft:incoming")).toMatchObject({
      source_scene_node_id: "engineering-flow:node:node:linear",
      target_scene_node_id: "engineering-flow:node:draft:relu",
    });
  });
});
