import { describe, expect, it } from "vitest";

import { materializeDraftNode, resolveDefinitionId } from "../module-registry/registry";
import type { PrototypeGraphDocument, PrototypeNode } from "../prototype-graph/types";
import { compilePyTorchDraft } from "./compile";
import { printPyTorchDraft } from "./printer";
import type { PyTorchDraft } from "./pytorch-ir";

function node(definitionId: string, id: string, parameters: Record<string, unknown> = {}): PrototypeNode {
  const value = materializeDraftNode(resolveDefinitionId(definitionId)!, id, id.replace("draft:", ""), "pytorch", null);
  Object.assign(value.parameters, parameters);
  return value;
}

function port(nodeValue: PrototypeNode, name: string): string {
  return nodeValue.ports.find((item) => item.name === name)!.port_id;
}

function compile(graph: PrototypeGraphDocument): string {
  const result = compilePyTorchDraft(graph);
  expect(result.diagnostics).toEqual([]);
  expect(result.draft).not.toBeNull();
  return printPyTorchDraft(result.draft!).source;
}

describe("structured PyTorch code generation", () => {
  it("prints Input -> Conv2d -> ReLU from exact named ports", () => {
    const input = node("archcanvas.input.tensor", "draft:input", { shape: ["B", 3, 224, 224] });
    input.semantic_name = "image";
    const conv = node("pytorch.nn.conv2d", "draft:conv", {
      in_channels: 3,
      out_channels: 16,
      kernel_size: [3, 3],
    });
    const relu = node("pytorch.nn.relu", "draft:relu");
    const graph: PrototypeGraphDocument = {
      draft_id: "draft:conv-relu",
      nodes: [input, conv, relu],
      edges: [
        { edge_id: "edge:input-conv", source_port_id: port(input, "output"), target_port_id: port(conv, "input") },
        { edge_id: "edge:conv-relu", source_port_id: port(conv, "output"), target_port_id: port(relu, "input") },
      ],
    };

    const source = compile(graph);
    expect(source).toContain("self.conv = nn.Conv2d(3, 16, [3, 3])");
    expect(source).toContain("self.relu = nn.ReLU()");
    expect(source).toContain("def forward(self, image):");
    expect(source).toContain("conv_output = self.conv(image)");
    expect(source).toContain("return relu_output");
  });

  it("prints named MHA inputs, safe string literals, and tuple outputs", () => {
    const query = node("archcanvas.input.tensor", "draft:query", { shape: ["B", "T", 16] });
    const memory = node("archcanvas.input.tensor", "draft:memory", { shape: ["B", "S", 16] });
    const mask = node("archcanvas.input.tensor", "draft:mask", { shape: ["T", "S"] });
    const attention = node("pytorch.nn.multiheadattention", "draft:attention", {
      embed_dim: 16,
      num_heads: 4,
      dropout: 0,
      batch_first: true,
      note: "ignored 'quoted'\nvalue",
    });
    const graph: PrototypeGraphDocument = {
      draft_id: "draft:mha",
      nodes: [query, memory, mask, attention],
      edges: [
        { edge_id: "e:q", source_port_id: port(query, "output"), target_port_id: port(attention, "query") },
        { edge_id: "e:k", source_port_id: port(memory, "output"), target_port_id: port(attention, "key") },
        { edge_id: "e:v", source_port_id: port(memory, "output"), target_port_id: port(attention, "value") },
        { edge_id: "e:m", source_port_id: port(mask, "output"), target_port_id: port(attention, "attention_mask") },
      ],
    };

    const result = compilePyTorchDraft(graph, "AttentionDraft");
    expect(result.draft).not.toBeNull();
    const printed = printPyTorchDraft(result.draft!);
    expect(printed.source).toContain("(attention_context, attention_weights) = self.attention(");
    expect(printed.source).toContain("attn_mask=mask");
    expect(printed.source).not.toContain("ignored");
    expect(printed.sourceMap["draft:attention"]).toHaveLength(2);
  });

  it("preserves LSTM's nested output pattern", () => {
    const input = node("archcanvas.input.tensor", "draft:sequence", { shape: ["B", "T", 8] });
    const lstm = node("pytorch.nn.lstm", "draft:lstm", { input_size: 8, hidden_size: 4 });
    const graph: PrototypeGraphDocument = {
      draft_id: "draft:lstm",
      nodes: [input, lstm],
      edges: [{ edge_id: "e:lstm", source_port_id: port(input, "output"), target_port_id: port(lstm, "input") }],
    };

    expect(compile(graph)).toContain(
      "(lstm_sequence, (lstm_hn, lstm_cn)) = self.lstm(sequence)",
    );
  });

  it("reuses one field for calls in the same parameter group", () => {
    const firstInput = node("archcanvas.input.tensor", "draft:first-input", { shape: ["B", 8] });
    const secondInput = node("archcanvas.input.tensor", "draft:second-input", { shape: ["B", 8] });
    const first = node("pytorch.nn.linear", "draft:first", { in_features: 8, out_features: 4 });
    const second = node("pytorch.nn.linear", "draft:second", { in_features: 8, out_features: 4 });
    first.parameter_group_id = "parameter-group:shared";
    second.parameter_group_id = "parameter-group:shared";
    const graph: PrototypeGraphDocument = {
      draft_id: "draft:shared",
      nodes: [firstInput, secondInput, first, second],
      edges: [
        { edge_id: "e:first", source_port_id: port(firstInput, "output"), target_port_id: port(first, "input") },
        { edge_id: "e:second", source_port_id: port(secondInput, "output"), target_port_id: port(second, "input") },
      ],
    };

    const source = compile(graph);
    expect(source.match(/self\.first = nn\.Linear/g)).toHaveLength(1);
    expect(source).toContain("second_output = self.first(second_input)");
  });

  it("returns blocking diagnostics instead of partial source", () => {
    const relu = node("pytorch.nn.relu", "draft:relu");
    const result = compilePyTorchDraft({ draft_id: "draft:invalid", nodes: [relu], edges: [] });

    expect(result.draft).toBeNull();
    expect(result.diagnostics.map((item) => item.code)).toContain("CODEGEN_REQUIRED_PORT_MISSING");
  });

  it("safely encodes nested literal values and special strings", () => {
    const draft: PyTorchDraft = {
      imports: [],
      className: "LiteralModel",
      forwardParameters: [],
      fields: [],
      forward: [],
      returns: {
        kind: "literal",
        value: {
          text: "quote \" slash \\ newline\nseparator\u2028paragraph\u2029",
          values: [null, true, false, -0, { z: 1, a: "first" }],
        },
      },
    };

    const source = printPyTorchDraft(draft).source;
    expect(source).toContain(
      '"text": "quote \\" slash \\\\ newline\\nseparator\\u2028paragraph\\u2029"',
    );
    expect(source).toContain(
      '"values": [None, True, False, -0.0, {"a": "first", "z": 1}]',
    );
  });
});
