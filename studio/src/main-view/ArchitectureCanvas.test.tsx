import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ArchitectureCanvas } from "./ArchitectureCanvas";
import type { FormalStudioState } from "./formal-state-adapter";
import { normalizedSelectionBox, selectionIntersectsBounds } from "./interaction";

const slots = [
  "q_projection", "k_projection", "v_projection", "q_split", "k_split", "v_split",
  "key_transpose", "score_matmul", "softmax", "value_matmul", "concat", "output_projection",
];

function exactAttentionState(): FormalStudioState {
  return {
    architecture: {
      architecture_id: "architecture:attention-render",
      nodes: [{
        node_id: "node:attention",
        semantic_name: "Attention",
        kind: "operation",
        input_ports: [{ port_id: "port:attention:input", name: "input", direction: "input", role: "data" }],
        output_ports: [{ port_id: "port:attention:output", name: "output", direction: "output", role: "data" }],
        evidence_ids: ["evidence:attention-node"],
        attributes: {},
      }],
      edges: [],
    },
    hierarchy: {
      root_node_id: "hierarchy:root",
      nodes: [
        { hierarchy_node_id: "hierarchy:root", parent_hierarchy_node_id: null, semantic_name: "Model", kind: "module_container", depth: 0, canonical_node_ids: [] },
        { hierarchy_node_id: "hierarchy:attention", parent_hierarchy_node_id: "hierarchy:root", semantic_name: "Attention", kind: "operation", depth: 1, canonical_node_ids: ["node:attention"] },
      ],
    },
    document: { source_digest: "sha256:attention-render" },
    view_state: { module_expansion: ["hierarchy:attention"] },
    semantic_overlay: {
      template_bindings: [{
        binding_id: "binding:attention:render",
        template_id: "attention.qkv-v1",
        template_version: "1.0.0",
        fidelity: "exact",
        root_canonical_node_ids: ["node:attention"],
        node_slots: Object.fromEntries(slots.map((slot) => [slot, [`node:${slot}`]])),
        edge_slots: {},
        port_slots: {},
        tensor_slots: {},
        evidence_ids: ["evidence:attention-binding"],
        predicate_ids: ["predicate:qkv-complete"],
        binding_digest: "sha256:attention-render-binding",
      }],
    },
  };
}

function connectedState(): FormalStudioState {
  return {
    architecture: {
      architecture_id: "architecture:connected",
      nodes: [
        {
          node_id: "node:a",
          semantic_name: "Input",
          kind: "input",
          input_ports: [],
          output_ports: [{ port_id: "port:a:out", name: "out", direction: "output", role: "data" }],
          evidence_ids: ["evidence:a"],
          attributes: {},
        },
        {
          node_id: "node:b",
          semantic_name: "Output",
          kind: "output",
          input_ports: [{ port_id: "port:b:in", name: "in", direction: "input", role: "data" }],
          output_ports: [],
          evidence_ids: ["evidence:b"],
          attributes: {},
        },
      ],
      edges: [{
        edge_id: "edge:a:b",
        tensor_id: "tensor:a:b",
        producer_id: "node:a",
        producer_port: "port:a:out",
        consumer_id: "node:b",
        consumer_port: "port:b:in",
        role: "data",
        edge_type: "main",
        evidence_ids: ["evidence:edge:a:b"],
      }],
    },
    hierarchy: {
      root_node_id: "hierarchy:root",
      nodes: [
        { hierarchy_node_id: "hierarchy:root", parent_hierarchy_node_id: null, semantic_name: "Model", kind: "module_container", depth: 0, canonical_node_ids: [] },
        { hierarchy_node_id: "hierarchy:a", parent_hierarchy_node_id: "hierarchy:root", semantic_name: "Input", kind: "input", depth: 1, canonical_node_ids: ["node:a"] },
        { hierarchy_node_id: "hierarchy:b", parent_hierarchy_node_id: "hierarchy:root", semantic_name: "Output", kind: "output", depth: 1, canonical_node_ids: ["node:b"] },
      ],
    },
    document: { source_digest: "sha256:connected" },
    view_state: {},
  };
}

describe("ArchitectureCanvas formal detail rendering", () => {
  it("uses the QKV semantic glyph for a collapsed exact attention module", () => {
    const state = exactAttentionState();
    state.view_state.module_expansion = [];
    const markup = renderToStaticMarkup(<ArchitectureCanvas
      state={state}
      selectedCanonicalIds={[]}
      onSelectNode={() => undefined}
      tx={(english) => english}
    />);

    expect(markup).toContain("shape-attention");
    expect(markup).toContain("attention-glyph");
    expect(markup).toContain(">Q<");
    expect(markup).toContain(">K<");
    expect(markup).toContain(">V<");
  });

  it("renders the exact attention inventory, marker, portals, and provenance into the main SVG", () => {
    const markup = renderToStaticMarkup(<ArchitectureCanvas
      state={exactAttentionState()}
      selectedCanonicalIds={["node:q_projection"]}
      onSelectNode={() => undefined}
      onSelectCanonicalIds={() => undefined}
      tx={(english) => english}
    />);

    expect(markup).toContain('id="kernel-detail-arrow"');
    expect(markup).toContain('data-detail-slot-id="q_projection"');
    expect(markup).toContain('data-detail-slot-id="visual:attention-weights"');
    expect(markup).toContain('data-detail-binding-id="binding:attention:render"');
    expect(markup).toContain("Evidence: evidence:attention-binding");
    expect(markup.match(/class="kernel-detail-boundary-portal/g)).toHaveLength(2);
    expect(markup.match(/class="kernel-detail-flow /g)).toHaveLength(23);
    expect(markup.match(/class="kernel-detail-interactive/g)).toHaveLength(12);
    expect(markup).toContain('class="kernel-detail-interactive selected" data-detail-primitive-id="binding:attention:render:q_projection"');
    expect(markup).not.toContain('data-detail-primitive-id="binding:attention:render:visual:q-input"');
    expect(markup).toContain('aria-label="Focus selection"');
    expect(markup).not.toContain('aria-label="Focus selection" title="Focus selection" disabled=""');
  });

  it("distinguishes exact, opaque, and schematic template fidelity without inventing internals", () => {
    for (const fidelity of ["exact", "opaque", "schematic"] as const) {
      const state = exactAttentionState();
      state.semantic_overlay!.template_bindings![0].fidelity = fidelity;
      const markup = renderToStaticMarkup(<ArchitectureCanvas
        state={state}
        selectedCanonicalIds={[]}
        onSelectNode={() => undefined}
        tx={(english) => english}
      />);

      expect(markup).toContain(`data-template-fidelity="${fidelity}"`);
      expect(markup).toContain(`fidelity-${fidelity}`);
      if (fidelity === "exact") expect(markup).toContain('data-detail-binding-id="binding:attention:render"');
      else expect(markup).not.toContain('data-detail-binding-id="binding:attention:render"');
    }
  });

  it("renders migrated catalog details for supported exact bindings", () => {
    const state = exactAttentionState();
    const binding = state.semantic_overlay!.template_bindings![0];
    binding.binding_id = "binding:feedforward:render";
    binding.template_id = "catalog.feedforward-v1";
    binding.node_slots = {};
    const markup = renderToStaticMarkup(<ArchitectureCanvas
      state={state}
      selectedCanonicalIds={[]}
      onSelectNode={() => undefined}
      tx={(english) => english}
    />);

    expect(markup).toContain('data-detail-binding-id="binding:feedforward:render"');
    expect(markup).toContain('data-detail-slot-id="visual:');
    expect(markup).toContain("position-wise channel expansion and contraction");
  });

  it("renders edge hit areas, edge selection, and node resize handles", () => {
    const markup = renderToStaticMarkup(<ArchitectureCanvas
      state={connectedState()}
      selectedCanonicalIds={["node:a"]}
      selectedCanonicalEdgeIds={["edge:a:b"]}
      onSelectNode={() => undefined}
      onSelectEdge={() => undefined}
      tx={(english) => english}
    />);

    expect(markup).toContain('class="kernel-edge selected"');
    expect(markup).toContain('class="kernel-edge-hit"');
    expect(markup).toContain('data-canonical-edge-ids="edge:a:b"');
    expect(markup).toContain('data-resize-node-id="view:hierarchy:a"');
  });

  it("normalizes reverse drag boxes and detects geometric intersections", () => {
    const box = normalizedSelectionBox({ x: 90, y: 80 }, { x: 10, y: 20 });
    expect(box).toEqual({ x: 10, y: 20, width: 80, height: 60 });
    expect(selectionIntersectsBounds(box, { x: 70, y: 70, width: 40, height: 30 })).toBe(true);
    expect(selectionIntersectsBounds(box, { x: 120, y: 120, width: 20, height: 20 })).toBe(false);
  });
});
