import { describe, expect, it } from "vitest";

import { buildKernelRenderScene } from "../visual-kernel/layout";
import { resolveQualifiedName } from "../module-registry/registry";
import { adaptFormalState, type FormalStudioState } from "./formal-state-adapter";

function formalState(): FormalStudioState {
  return {
    architecture: {
      architecture_id: "architecture:test",
      nodes: [
        { node_id: "node:a", semantic_name: "Input", kind: "input", input_ports: [], output_ports: [{ port_id: "port:a", name: "out", direction: "output", role: "data" }], evidence_ids: ["evidence:a"], attributes: {} },
        { node_id: "node:b", semantic_name: "Block", kind: "operation", input_ports: [{ port_id: "port:b", name: "in", direction: "input", role: "data" }], output_ports: [], evidence_ids: ["evidence:b"], attributes: {} },
      ],
      edges: [
        { edge_id: "edge:a:b", tensor_id: "tensor:a", producer_id: "node:a", producer_port: "port:a", consumer_id: "node:b", consumer_port: "port:b", role: "residual", edge_type: "main", evidence_ids: ["evidence:edge"] },
      ],
    },
    hierarchy: {
      root_node_id: "hierarchy:root",
      nodes: [
        { hierarchy_node_id: "hierarchy:root", parent_hierarchy_node_id: null, semantic_name: "Model", kind: "module_container", depth: 0, canonical_node_ids: [] },
        { hierarchy_node_id: "hierarchy:a", parent_hierarchy_node_id: "hierarchy:root", semantic_name: "Input", kind: "input", depth: 1, canonical_node_ids: ["node:a"], evidence_ids: ["evidence:a"] },
        { hierarchy_node_id: "hierarchy:b", parent_hierarchy_node_id: "hierarchy:root", semantic_name: "Block", kind: "operation", depth: 1, canonical_node_ids: ["node:b"], evidence_ids: ["evidence:b"] },
      ],
    },
    document: { source_digest: "sha256:test" },
    view_state: {},
  };
}

const attentionSlots = [
  "q_projection", "k_projection", "v_projection", "q_split", "k_split", "v_split",
  "key_transpose", "score_matmul", "softmax", "value_matmul", "concat", "output_projection",
];

function exactAttentionBinding(fidelity: "exact" | "opaque" = "exact") {
  return {
    binding_id: "binding:attention:b",
    template_id: "attention.qkv-v1",
    template_version: "1.0.0",
    fidelity,
    root_canonical_node_ids: ["node:b"],
    node_slots: Object.fromEntries(attentionSlots.map((slot) => [slot, [`node:${slot}`]])),
    edge_slots: { score_to_softmax: ["edge:score:softmax"] },
    port_slots: { attention_input: ["port:b"] },
    tensor_slots: { attention_output: ["tensor:b"] },
    evidence_ids: ["evidence:attention"],
    predicate_ids: ["predicate:qkv-complete"],
    binding_digest: "sha256:binding:attention:b",
  };
}

describe("formal state adapter", () => {
  it("projects canonical facts without accepting scene geometry", () => {
    const { document, visualState } = adaptFormalState(formalState());

    expect(document.nodes.map((node) => node.nodeId)).toEqual([
      "view:hierarchy:root",
      "view:hierarchy:a",
      "view:hierarchy:b",
    ].sort());
    expect(document.nodes.find((node) => node.hierarchyNodeId === "hierarchy:root")).toMatchObject({
      renderRole: "expanded-module",
      childNodeIds: ["view:hierarchy:a", "view:hierarchy:b"],
    });
    expect(document.edges).toHaveLength(1);
    expect(document.edges[0]).toMatchObject({
      canonicalEdgeIds: ["edge:a:b"],
      relation: "residual",
      sourcePortId: "view:hierarchy:a:output",
      targetPortId: "view:hierarchy:b:input",
    });
    expect(visualState.routeStyle).toBe("adaptive");
  });

  it("materializes registry-backed named ports without changing legacy projections", () => {
    const state = formalState();
    const definition = resolveQualifiedName("torch.nn.Conv2d")!;
    const node = state.architecture.nodes.find((item) => item.node_id === "node:b")!;
    node.attributes = {
      definition_id: definition.definition_id,
      definition_version: definition.version,
      definition_digest: definition.digest,
      glyph_id: definition.glyph_id,
      semantic_kind: definition.semantic_kind,
    };
    node.output_ports = [{ port_id: "port:b:output", name: "output", direction: "output", role: "output" }];
    node.input_ports[0] = { port_id: "port:b:input", name: "input", direction: "input", role: "input" };
    state.architecture.edges[0].consumer_port = "port:b:input";

    const { document } = adaptFormalState(state);
    const projected = document.nodes.find((item) => item.hierarchyNodeId === "hierarchy:b")!;
    const input = document.ports.find((item) => item.ownerNodeId === projected.nodeId && item.direction === "input")!;

    expect(projected).toMatchObject({ glyphId: "conv2d", shape: "convolution" });
    expect(input).toMatchObject({
      role: "input",
      canonicalPortIds: ["port:b:input"],
      contract: {
        required: true,
        minConnections: 1,
        maxConnections: 1,
        definitionId: "pytorch.nn.conv2d",
      },
    });
    expect(document.edges[0].targetPortId).toBe(input.portId);
  });

  it("keeps the same registry glyph across engineering and paper-style presets", () => {
    const definition = resolveQualifiedName("torch.nn.Conv2d")!;
    const engineering = formalState();
    const paper = formalState();
    for (const state of [engineering, paper]) {
      const node = state.architecture.nodes.find((item) => item.node_id === "node:b")!;
      node.attributes = {
        definition_id: definition.definition_id,
        definition_version: definition.version,
        definition_digest: definition.digest,
        glyph_id: definition.glyph_id,
        semantic_kind: definition.semantic_kind,
      };
    }
    engineering.view_state.node_style = "technical";
    engineering.view_state.label_style = "endpoint";
    paper.view_state.node_style = "compact";
    paper.view_state.label_style = "plain";

    const engineeringNode = adaptFormalState(engineering).document.nodes
      .find((item) => item.hierarchyNodeId === "hierarchy:b")!;
    const paperNode = adaptFormalState(paper).document.nodes
      .find((item) => item.hierarchyNodeId === "hierarchy:b")!;

    expect(engineeringNode.glyphId).toBe("conv2d");
    expect(paperNode.glyphId).toBe(engineeringNode.glyphId);
    expect(paperNode.definitionRef).toEqual(engineeringNode.definitionRef);
  });

  it("projects registered draft nodes and named ports as synthetic kernel facts", () => {
    const state = formalState();
    const input = resolveQualifiedName("archcanvas.input.Tensor")!;
    const relu = resolveQualifiedName("torch.nn.ReLU")!;
    state.draft = {
      draft_id: "draft:test",
      nodes: [
        {
          node_id: "draft:input",
          semantic_name: "Draft input",
          node_type: input.definition_id,
          definition_ref: {
            definition_id: input.definition_id,
            version: input.version,
            digest: input.digest,
          },
          ports: [{
            port_id: "draft:input.output",
            name: "output",
            direction: "output",
            role: "output",
            definition_port_id: "output",
            required: true,
            min_connections: 0,
            max_connections: "many",
            accepted_relations: ["main"],
          }],
        },
        {
          node_id: "draft:relu",
          semantic_name: "Draft ReLU",
          node_type: relu.definition_id,
          definition_ref: {
            definition_id: relu.definition_id,
            version: relu.version,
            digest: relu.digest,
          },
          ports: relu.ports.map((port) => ({
            port_id: `draft:relu.${port.port_id}`,
            name: port.port_id,
            direction: port.direction,
            role: port.port_id,
            definition_port_id: port.port_id,
            required: port.required,
            min_connections: port.min_connections,
            max_connections: port.max_connections,
            accepted_relations: port.accepted_relations,
          })),
        },
      ],
      edges: [{
        edge_id: "draft:input-relu",
        source_port_id: "draft:input.output",
        target_port_id: "draft:relu.input",
        relation: "main",
      }],
    };

    const { document, visualState } = adaptFormalState(state);
    const draftNode = document.nodes.find((node) => node.nodeId === "draft:relu")!;
    const scene = buildKernelRenderScene(document, visualState);

    expect(draftNode).toMatchObject({
      synthetic: true,
      glyphId: "relu",
      definitionRef: { definitionId: "pytorch.nn.relu", version: "1.0.0" },
      inputPortIds: ["draft:relu.input"],
      outputPortIds: ["draft:relu.output"],
    });
    expect(document.ports.find((port) => port.portId === "draft:relu.input")).toMatchObject({
      ownerNodeId: "draft:relu",
      contract: { required: true, minConnections: 1, maxConnections: 1 },
    });
    expect(document.edges.find((edge) => edge.edgeId === "draft:input-relu")).toMatchObject({
      canonicalEdgeIds: [],
      relation: "sequence",
    });
    expect(scene.nodes.some((node) => node.nodeId === "draft:relu")).toBe(true);
  });

  it("produces deterministic geometry when formal arrays are reordered", () => {
    const first = formalState();
    const second = formalState();
    second.architecture.nodes.reverse();
    second.hierarchy.nodes.reverse();
    const left = adaptFormalState(first);
    const right = adaptFormalState(second);

    expect(buildKernelRenderScene(left.document, left.visualState))
      .toEqual(buildKernelRenderScene(right.document, right.visualState));
  });

  it("downgrades stale exact template bindings to opaque", () => {
    const state = formalState();
    state.semantic_overlay = {
      template_bindings: [{
        binding_id: "binding:attention",
        template_id: "attention.qkv-v1",
        fidelity: "exact",
        canonical_node_ids: ["node:b"],
        evidence_ids: ["evidence:b"],
        source_digest: "sha256:stale",
      }],
    };

    expect(adaptFormalState(state).document.templateBindings[0].fidelity).toBe("opaque");
  });

  it("retains an expanded parent and lays its immediate children inside its frame", () => {
    const state = formalState();
    const block = state.hierarchy.nodes.find((node) => node.hierarchy_node_id === "hierarchy:b")!;
    block.kind = "module_container";
    block.canonical_node_ids = [];
    state.hierarchy.nodes.push({
      hierarchy_node_id: "hierarchy:b:operation",
      parent_hierarchy_node_id: "hierarchy:b",
      semantic_name: "Block operation",
      kind: "operation",
      depth: 2,
      canonical_node_ids: ["node:b"],
      evidence_ids: ["evidence:b"],
    });
    state.architecture.nodes.push({ node_id: "node:c", semantic_name: "Output", kind: "output", input_ports: [{ port_id: "port:c", name: "in", direction: "input", role: "data" }], output_ports: [], evidence_ids: ["evidence:c"], attributes: {} });
    state.architecture.edges.push({ edge_id: "edge:b:c", tensor_id: "tensor:b", producer_id: "node:b", producer_port: "port:b:out", consumer_id: "node:c", consumer_port: "port:c", role: "data", edge_type: "main", evidence_ids: ["evidence:edge:b:c"] });
    state.hierarchy.nodes.push({ hierarchy_node_id: "hierarchy:c", parent_hierarchy_node_id: "hierarchy:root", semantic_name: "Output", kind: "output", depth: 1, canonical_node_ids: ["node:c"], evidence_ids: ["evidence:c"] });

    const collapsed = adaptFormalState(state);
    const collapsedScene = buildKernelRenderScene(collapsed.document, collapsed.visualState);
    const collapsedOutputX = collapsedScene.nodes.find((node) => node.hierarchyNodeId === "hierarchy:c")!.bounds.x;
    state.view_state.module_expansion = ["hierarchy:b"];

    const adapted = adaptFormalState(state);
    const parent = adapted.document.nodes.find((node) => node.hierarchyNodeId === "hierarchy:b")!;
    const child = adapted.document.nodes.find((node) => node.hierarchyNodeId === "hierarchy:b:operation")!;
    const scene = buildKernelRenderScene(adapted.document, adapted.visualState);
    const parentBounds = scene.nodes.find((node) => node.nodeId === parent.nodeId)!.bounds;
    const childBounds = scene.nodes.find((node) => node.nodeId === child.nodeId)!.bounds;
    const expandedOutputX = scene.nodes.find((node) => node.hierarchyNodeId === "hierarchy:c")!.bounds.x;

    expect(parent).toMatchObject({ renderRole: "expanded-module", childNodeIds: [child.nodeId] });
    expect(child.parentNodeId).toBe(parent.nodeId);
    expect(childBounds.x).toBeGreaterThan(parentBounds.x);
    expect(childBounds.y).toBeGreaterThan(parentBounds.y + 49);
    expect(childBounds.x + childBounds.width).toBeLessThan(parentBounds.x + parentBounds.width);
    expect(adapted.document.edges[0].targetPortId).toBe(`${child.nodeId}:input`);
    expect(expandedOutputX).toBeGreaterThan(collapsedOutputX);
    expect(scene.portals).toEqual(expect.arrayContaining([
      expect.objectContaining({ moduleNodeId: parent.nodeId, direction: "entry" }),
      expect.objectContaining({ moduleNodeId: parent.nodeId, direction: "exit" }),
    ]));

    const enlargedVisualState = {
      ...adapted.visualState,
      nodeSizes: { [parent.nodeId]: { width: 500, height: 320 } },
    };
    const enlarged = buildKernelRenderScene(adapted.document, enlargedVisualState);
    const moved = buildKernelRenderScene(adapted.document, {
      ...enlargedVisualState,
      detailOffsets: { [child.nodeId]: { x: 36, y: 22 } },
    });
    const enlargedChild = enlarged.nodes.find((node) => node.nodeId === child.nodeId)!.bounds;
    const movedChild = moved.nodes.find((node) => node.nodeId === child.nodeId)!.bounds;
    expect(movedChild.x - enlargedChild.x).toBe(36);
    expect(movedChild.y - enlargedChild.y).toBe(22);
  });

  it("expands an exact attention binding into stable slot-backed detail primitives", () => {
    const state = formalState();
    state.semantic_overlay = { template_bindings: [exactAttentionBinding()] };

    const collapsed = adaptFormalState(state);
    const collapsedAttention = collapsed.document.nodes.find((node) => node.hierarchyNodeId === "hierarchy:b")!;
    expect(collapsedAttention).toMatchObject({ renderRole: "collapsed-module", templateBindingId: "binding:attention:b", shape: "attention" });

    state.view_state.module_expansion = ["hierarchy:b"];
    const expanded = adaptFormalState(state);
    const expandedAttention = expanded.document.nodes.find((node) => node.hierarchyNodeId === "hierarchy:b")!;
    const scene = buildKernelRenderScene(expanded.document, expanded.visualState);
    const detail = scene.details[0];

    expect(expandedAttention.renderRole).toBe("expanded-module");
    expect(scene.details).toHaveLength(1);
    expect(detail.bounds).toMatchObject({ width: 900, height: 380 });
    expect(detail.evidenceIds).toEqual(["evidence:attention"]);
    expect(detail.entryPoint).toEqual({ x: detail.bounds.x, y: detail.bounds.y + 190 });
    expect(detail.exitPoint).toEqual({ x: detail.bounds.x + 900, y: detail.bounds.y + 190 });
    expect(expanded.document.templateBindings[0]).toMatchObject({
      predicateIds: ["predicate:qkv-complete"],
      bindingDigest: "sha256:binding:attention:b",
    });
    expect(detail.primitives.filter((primitive) => attentionSlots.includes(primitive.slotId)).map((primitive) => primitive.primitiveId).sort())
      .toEqual(attentionSlots.map((slot) => `binding:attention:b:${slot}`).sort());
    expect(new Set(detail.primitives.filter((primitive) => attentionSlots.includes(primitive.slotId)).flatMap((primitive) => primitive.canonicalIds)))
      .toEqual(new Set(attentionSlots.map((slot) => `node:${slot}`)));
  });

  it("does not infer attention internals without an exact formal binding", () => {
    const unbound = formalState();
    unbound.hierarchy.nodes.find((node) => node.hierarchy_node_id === "hierarchy:b")!.semantic_name = "Multi-head attention QKV";
    unbound.view_state.module_expansion = ["hierarchy:b"];
    const unboundAdapted = adaptFormalState(unbound);
    expect(buildKernelRenderScene(unboundAdapted.document, unboundAdapted.visualState).details).toEqual([]);

    const opaque = formalState();
    opaque.semantic_overlay = { template_bindings: [exactAttentionBinding("opaque")] };
    opaque.view_state.module_expansion = ["hierarchy:b"];
    const opaqueAdapted = adaptFormalState(opaque);
    expect(buildKernelRenderScene(opaqueAdapted.document, opaqueAdapted.visualState).details).toEqual([]);
  });

  it("selects semantic glyphs only from formal kinds, attributes, and annotations", () => {
    const cases = [
      { attributes: { op_type: "nn.Conv2d" }, expected: "convolution" },
      { attributes: { op_type: "nn.LayerNorm" }, expected: "normalization" },
      { attributes: { semantic_role: "add" }, expected: "add" },
      { attributes: { semantic_role: "multiply" }, expected: "multiply" },
      { attributes: { semantic_role: "concat" }, expected: "concat" },
    ] as const;
    for (const item of cases) {
      const state = formalState();
      state.architecture.nodes.find((node) => node.node_id === "node:b")!.attributes = item.attributes;
      expect(adaptFormalState(state).document.nodes.find((node) => node.hierarchyNodeId === "hierarchy:b")?.shape).toBe(item.expected);
    }

    const annotated = formalState();
    annotated.semantic_overlay = {
      annotations: [{
        annotation_id: "annotation:attention:b",
        pack_id: "pack:attention",
        canonical_node_ids: ["node:b"],
        semantic_role: "attention core",
        glyph: "attention",
        predicate_ids: ["predicate:attention"],
      }],
    };
    expect(adaptFormalState(annotated).document.nodes.find((node) => node.hierarchyNodeId === "hierarchy:b")?.shape).toBe("attention");
  });

  it("does not infer a semantic glyph from a node label", () => {
    const state = formalState();
    const node = state.architecture.nodes.find((item) => item.node_id === "node:b")!;
    node.semantic_name = "Attention Conv LayerNorm Add Multiply Concat";
    node.kind = "operation";
    node.attributes = {};

    expect(adaptFormalState(state).document.nodes.find((item) => item.hierarchyNodeId === "hierarchy:b")?.shape).toBe("operation");
  });

  it("reports malformed formal inputs without accepting or inventing geometry", () => {
    const state = formalState();
    state.architecture.edges[0].producer_port = "port:missing";
    state.architecture.edges.push({
      ...state.architecture.edges[0],
      edge_id: "edge:dangling",
      consumer_id: "node:missing",
    });
    state.hierarchy.nodes.find((node) => node.hierarchy_node_id === "hierarchy:a")!.parent_hierarchy_node_id = "hierarchy:a";
    state.semantic_overlay = {
      template_bindings: [{
        ...exactAttentionBinding(),
        source_digest: "sha256:stale",
        canonical_node_ids: ["node:missing"],
      }],
    };

    const codes = adaptFormalState(state).document.diagnostics.map((item) => item.code);
    expect(codes).toEqual(expect.arrayContaining([
      "cyclic-hierarchy",
      "dangling-canonical-edge",
      "dangling-template-slot",
      "missing-producer-port",
      "stale-template-binding",
    ]));
  });
});
