import { describe, expect, it } from "vitest";

import type { StudioState } from "../app/studio-types";
import { resolveDefinitionId } from "../module-registry/registry";
import { compileStudioDraftPreview, studioDraftCodegenGraph } from "./studio-preview";

function draft(): StudioState["draft"] {
  const definition = resolveDefinitionId("pytorch.nn.gelu")!;
  return {
    draft_id: "draft:preview",
    revision: 1,
    base_registry_digest: "registry",
    nodes: [{
      node_id: "draft:gelu",
      semantic_name: "after_conv",
      framework: "pytorch",
      node_type: definition.definition_id,
      definition_ref: {
        definition_id: definition.definition_id,
        version: definition.version,
        digest: definition.digest,
      },
      parameters: { approximate: "none" },
      ports: definition.ports.map((port) => ({
        ...port,
        port_id: `draft:gelu.${port.port_id}`,
        name: port.port_id,
        role: port.port_id,
        definition_port_id: port.port_id,
      })),
    }],
    edges: [
      {
        edge_id: "draft:incoming",
        source_port_id: "port:canonical.output",
        target_port_id: "draft:gelu.input",
        policy: "fanout",
        relation: "main",
        parameters: {},
      },
      {
        edge_id: "draft:outgoing",
        source_port_id: "draft:gelu.output",
        target_port_id: "port:canonical.input",
        policy: "replace-input",
        relation: "main",
        parameters: {},
      },
    ],
    intents: [],
    lowering_status: "checking",
    proofs: [],
    writeback_summary: { eligibility: "blocked", blocking_intent_ids: [] },
  };
}

describe("Studio codegen preview", () => {
  it("turns canonical inputs into forward parameters and prints registered draft nodes", () => {
    const result = compileStudioDraftPreview(draft());

    expect(result.diagnostics).toEqual([]);
    expect(result.preview?.source).toContain("def forward(self, input_1):");
    expect(result.preview?.source).toContain("self.after_conv = nn.GELU()");
    expect(result.preview?.source).toContain("after_conv_output = self.after_conv(input_1)");
    expect(result.preview?.sourceMap["draft:gelu"]).toHaveLength(2);
  });

  it("omits canonical consumers while preserving the draft output as a terminal value", () => {
    const graph = studioDraftCodegenGraph(draft());
    expect(graph.edges.map((edge) => edge.edge_id)).toEqual(["draft:incoming"]);
    expect(graph.nodes.some((node) => node.node_id === "draft:gelu")).toBe(true);
  });

  it("blocks preview when a required draft input has no binding", () => {
    const value = draft();
    value.edges = [];
    const result = compileStudioDraftPreview(value);
    expect(result.preview).toBeNull();
    expect(result.diagnostics.map((item) => item.code)).toContain("CODEGEN_REQUIRED_PORT_MISSING");
  });
});
