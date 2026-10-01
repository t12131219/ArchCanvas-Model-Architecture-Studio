import { describe, expect, it } from "vitest";

import {
  materializeDraftNode,
  resolveDefinitionId,
} from "../module-registry/registry";
import { analyzeGraph } from "./analyze";
import type { PrototypeGraphDocument } from "./types";

function graph(inChannels = 3): PrototypeGraphDocument {
  const input = materializeDraftNode(
    resolveDefinitionId("archcanvas.input.tensor")!,
    "draft:input",
    "input",
    "pytorch",
    null,
  );
  input.parameters.shape = ["B", 3, 224, 224];
  const conv = materializeDraftNode(
    resolveDefinitionId("pytorch.nn.conv2d")!,
    "draft:conv",
    "conv",
    "pytorch",
    null,
  );
  Object.assign(conv.parameters, {
    in_channels: inChannels,
    out_channels: 16,
    kernel_size: [3, 3],
  });
  const relu = materializeDraftNode(
    resolveDefinitionId("pytorch.nn.relu")!,
    "draft:relu",
    "relu",
    "pytorch",
    null,
  );
  return {
    draft_id: "draft:test",
    base_registry_digest: "unused",
    nodes: [input, conv, relu],
    edges: [
      {
        edge_id: "draft:edge-input-conv",
        source_port_id: "draft:input.output",
        target_port_id: "draft:conv.input",
        relation: "main",
      },
      {
        edge_id: "draft:edge-conv-relu",
        source_port_id: "draft:conv.output",
        target_port_id: "draft:relu.input",
        relation: "main",
      },
    ],
  };
}

function registeredGraph(
  definitionId: string,
  inputShapes: Array<Array<string | number>>,
  parameters: Record<string, unknown>,
): PrototypeGraphDocument {
  const inputs = inputShapes.map((shape, index) => {
    const input = materializeDraftNode(
      resolveDefinitionId("archcanvas.input.tensor")!,
      `draft:source-${index}`,
      `source-${index}`,
      "pytorch",
      null,
    );
    input.parameters.shape = shape;
    return input;
  });
  const target = materializeDraftNode(
    resolveDefinitionId(definitionId)!,
    "draft:target",
    "target",
    "pytorch",
    null,
  );
  Object.assign(target.parameters, parameters);
  const targetPorts = target.ports.filter((port) => port.direction === "input");
  return {
    draft_id: `draft:${definitionId}`,
    nodes: [...inputs, target],
    edges: inputs.map((input, index) => ({
      edge_id: `draft:edge-${index}`,
      source_port_id: input.ports.find((port) => port.direction === "output")!.port_id,
      target_port_id: targetPorts.length === 1 ? targetPorts[0].port_id : targetPorts[index].port_id,
      relation: "main",
    })),
  };
}

function knownDimensions(snapshot: Awaited<ReturnType<typeof analyzeGraph>>, nodeId: string, portId: string) {
  const value = snapshot.nodeShapes[nodeId][portId];
  expect(value.status).toBe("known");
  return value.status === "known" ? value.shape.dimensions : [];
}

describe("prototype graph analysis", () => {
  it("propagates Input -> Conv2d -> ReLU by exact named ports", async () => {
    const snapshot = await analyzeGraph(graph());
    const conv = snapshot.nodeShapes["draft:conv"].output;
    const relu = snapshot.nodeShapes["draft:relu"].output;

    expect(snapshot.diagnostics.filter((item) => item.severity === "blocking")).toEqual([]);
    expect(conv.status).toBe("known");
    expect(relu).toEqual(conv);
    if (conv.status === "known") {
      expect(conv.shape.dimensions).toEqual([
        { kind: "symbol", symbol: "B" },
        { kind: "known", value: 16 },
        { kind: "known", value: 222 },
        { kind: "known", value: 222 },
      ]);
    }
    expect(snapshot.nodeCosts["draft:conv"].parameterCount).toBe("448");
    expect(snapshot.documentDigest).toMatch(/^[a-f0-9]{64}$/);
  });

  it("blocks a Conv2d channel mismatch without erasing independent results", async () => {
    const snapshot = await analyzeGraph(graph(4));

    expect(snapshot.diagnostics.map((item) => item.code)).toContain("CONV2D_CHANNEL_MISMATCH");
    expect(snapshot.nodeShapes["draft:input"].output.status).toBe("known");
    expect(snapshot.nodeShapes["draft:conv"].output.status).toBe("blocked");
    expect(snapshot.nodeShapes["draft:relu"].output.status).toBe("blocked");
  });

  it("reports missing required named ports and keeps the draft serializable", async () => {
    const incomplete = graph();
    incomplete.edges = incomplete.edges.filter((edge) => edge.target_port_id !== "draft:relu.input");
    const snapshot = await analyzeGraph(incomplete);

    expect(snapshot.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({ code: "PORT_CARDINALITY_INCOMPLETE", relatedPortIds: ["draft:relu.input"] }),
    ]));
    expect(snapshot.nodeShapes["draft:relu"].output.status).toBe("blocked");
  });

  it("treats canonical Studio endpoints as explicit external boundaries only when enabled", async () => {
    const relu = materializeDraftNode(
      resolveDefinitionId("pytorch.nn.relu")!,
      "draft:relu-boundary",
      "relu_boundary",
      "pytorch",
      null,
    );
    const boundaryGraph: PrototypeGraphDocument = {
      draft_id: "draft:canonical-boundaries",
      nodes: [relu],
      edges: [
        {
          edge_id: "draft:canonical-in",
          source_port_id: "port:canonical-conv.output",
          target_port_id: "draft:relu-boundary.input",
          relation: "main",
        },
        {
          edge_id: "draft:canonical-out",
          source_port_id: "draft:relu-boundary.output",
          target_port_id: "port:canonical-consumer.input",
          relation: "main",
        },
      ],
    };

    expect((await analyzeGraph(boundaryGraph)).diagnostics.map((item) => item.code))
      .toContain("UNKNOWN_EDGE_PORT");
    const studioSnapshot = await analyzeGraph(boundaryGraph, { allowExternalBoundaries: true });
    expect(studioSnapshot.diagnostics.filter((item) => item.severity === "blocking")).toEqual([]);
    expect(studioSnapshot.nodeShapes[relu.node_id].output).toEqual({
      status: "unknown",
      reason: "canonical upstream shape is unavailable in the draft analyzer",
      constraints: [],
    });
  });

  it("infers Linear, pooling, embedding, LayerNorm, and Reshape rules", async () => {
    const linear = await analyzeGraph(registeredGraph(
      "pytorch.nn.linear", [["B", 8]], { in_features: 8, out_features: 4 },
    ));
    expect(knownDimensions(linear, "draft:target", "output")).toEqual([
      { kind: "symbol", symbol: "B" },
      { kind: "known", value: 4 },
    ]);
    expect(linear.nodeCosts["draft:target"].parameterCount).toBe("36");

    const pool = await analyzeGraph(registeredGraph(
      "pytorch.nn.maxpool2d", [["B", 3, 8, 8]], { kernel_size: 2 },
    ));
    expect(knownDimensions(pool, "draft:target", "output")).toEqual([
      { kind: "symbol", symbol: "B" },
      { kind: "known", value: 3 },
      { kind: "known", value: 4 },
      { kind: "known", value: 4 },
    ]);

    const embedding = await analyzeGraph(registeredGraph(
      "pytorch.nn.embedding", [["B", "T"]], { num_embeddings: 100, embedding_dim: 16 },
    ));
    expect(knownDimensions(embedding, "draft:target", "output").at(-1)).toEqual({ kind: "known", value: 16 });
    expect(embedding.nodeCosts["draft:target"].parameterCount).toBe("1600");

    const layerNorm = await analyzeGraph(registeredGraph(
      "pytorch.nn.layernorm", [["B", "T", 16]], { normalized_shape: [16] },
    ));
    expect(knownDimensions(layerNorm, "draft:target", "output")).toEqual([
      { kind: "symbol", symbol: "B" },
      { kind: "symbol", symbol: "T" },
      { kind: "known", value: 16 },
    ]);

    const reshape = await analyzeGraph(registeredGraph(
      "pytorch.op.reshape", [[2, 3, 4]], { shape: [2, -1] },
    ));
    expect(knownDimensions(reshape, "draft:target", "output")).toEqual([
      { kind: "known", value: 2 },
      { kind: "expression", expression: "(2*3*4)/(2)" },
    ]);
  });

  it("broadcasts Add operands by the named variadic port", async () => {
    const snapshot = await analyzeGraph(registeredGraph(
      "pytorch.op.add", [["B", 1, 8], [1, "T", 8]], {},
    ));

    expect(snapshot.diagnostics.filter((item) => item.severity === "blocking")).toEqual([]);
    expect(knownDimensions(snapshot, "draft:target", "output")).toEqual([
      { kind: "symbol", symbol: "B" },
      { kind: "symbol", symbol: "T" },
      { kind: "known", value: 8 },
    ]);
  });

  it("preserves named multi-output shapes for MHA and LSTM", async () => {
    const attention = await analyzeGraph(registeredGraph(
      "pytorch.nn.multiheadattention",
      [["B", "T", 16], ["B", "S", 16], ["B", "S", 16]],
      { embed_dim: 16, num_heads: 4, batch_first: true },
    ));
    expect(knownDimensions(attention, "draft:target", "context")).toEqual([
      { kind: "symbol", symbol: "B" },
      { kind: "symbol", symbol: "T" },
      { kind: "known", value: 16 },
    ]);
    expect(knownDimensions(attention, "draft:target", "weights")).toEqual([
      { kind: "symbol", symbol: "B" },
      { kind: "symbol", symbol: "T" },
      { kind: "symbol", symbol: "S" },
    ]);

    const lstm = await analyzeGraph(registeredGraph(
      "pytorch.nn.lstm", [["B", "T", 8]], {
        input_size: 8,
        hidden_size: 4,
        num_layers: 2,
        batch_first: true,
        bidirectional: true,
      },
    ));
    expect(knownDimensions(lstm, "draft:target", "sequence")).toEqual([
      { kind: "symbol", symbol: "B" },
      { kind: "symbol", symbol: "T" },
      { kind: "known", value: 8 },
    ]);
    expect(knownDimensions(lstm, "draft:target", "hn")).toEqual([
      { kind: "known", value: 4 },
      { kind: "symbol", symbol: "B" },
      { kind: "known", value: 4 },
    ]);
    expect(knownDimensions(lstm, "draft:target", "cn"))
      .toEqual(knownDimensions(lstm, "draft:target", "hn"));
  });

  it("rejects wrong directions, illegal relations, and excess input connections", async () => {
    const invalidDirection = graph();
    invalidDirection.edges = [{
      edge_id: "draft:wrong-direction",
      source_port_id: "draft:conv.input",
      target_port_id: "draft:relu.input",
      relation: "main",
    }];
    expect((await analyzeGraph(invalidDirection)).diagnostics.map((item) => item.code))
      .toContain("EDGE_DIRECTION_INVALID");

    const invalidRelation = graph();
    invalidRelation.edges[0].relation = "feedback";
    const relationSnapshot = await analyzeGraph(invalidRelation);
    expect(relationSnapshot.diagnostics.map((item) => item.code)).toContain("EDGE_RELATION_INVALID");
    expect(relationSnapshot.nodeShapes["draft:conv"].output.status).toBe("blocked");

    const excess = graph();
    const second = structuredClone(excess.nodes[0]);
    second.node_id = "draft:input-2";
    second.ports[0].port_id = "draft:input-2.output";
    excess.nodes.push(second);
    excess.edges.push({
      edge_id: "draft:edge-input-2-conv",
      source_port_id: "draft:input-2.output",
      target_port_id: "draft:conv.input",
      relation: "main",
    });
    expect((await analyzeGraph(excess)).diagnostics.map((item) => item.code))
      .toContain("PORT_CARDINALITY_EXCEEDED");
  });

  it("enforces registry tensor-rank constraints before running shape rules", async () => {
    const snapshot = await analyzeGraph(registeredGraph(
      "pytorch.nn.conv2d", [["B", 3, 32]], {
        in_channels: 3,
        out_channels: 8,
        kernel_size: 3,
      },
    ));

    expect(snapshot.diagnostics.map((item) => item.code)).toContain("PORT_TENSOR_RANK_INVALID");
    expect(snapshot.nodeShapes["draft:target"].output.status).toBe("blocked");
  });

  it("keeps symbolic and unknown dimensions without inventing concrete values", async () => {
    const cases = [
      ["pytorch.nn.conv2d", [["B", 3, null, "W"]], { in_channels: 3, out_channels: 8, kernel_size: 3 }, "output"],
      ["pytorch.nn.linear", [[null, 8]], { in_features: 8, out_features: 4 }, "output"],
      ["pytorch.op.add", [["B", null, 8], [1, "T", 8]], {}, "output"],
      ["pytorch.op.reshape", [["B", null]], { shape: ["B", -1] }, "output"],
      ["pytorch.nn.multiheadattention", [["B", null, 16], ["B", "S", 16], ["B", "S", 16]], { embed_dim: 16, num_heads: 4, batch_first: true }, "context"],
    ] as const;
    for (const [definitionId, shapes, parameters, output] of cases) {
      const snapshot = await analyzeGraph(registeredGraph(
        definitionId,
        shapes as unknown as Array<Array<string | number>>,
        parameters,
      ));
      const value = snapshot.nodeShapes["draft:target"][output];
      expect(value.status).toBe("known");
      expect(JSON.stringify(value)).toMatch(/unknown|\?|expression/);
    }
  });

  it("blocks invalid Conv2d, Linear, Add, Reshape, and MHA shapes independently", async () => {
    const cases = [
      ["pytorch.nn.conv2d", [["B", 3, 2, 2]], { in_channels: 3, out_channels: 8, kernel_size: 5 }, "CONV2D_OUTPUT_INVALID"],
      ["pytorch.nn.linear", [["B", 7]], { in_features: 8, out_features: 4 }, "LINEAR_FEATURE_MISMATCH"],
      ["pytorch.op.add", [[2, 3], [4, 3]], {}, "BROADCAST_SHAPE_MISMATCH"],
      ["pytorch.op.reshape", [[2, 3]], { shape: [5] }, "RESHAPE_ELEMENT_MISMATCH"],
      ["pytorch.nn.multiheadattention", [["B", "T", 16], ["B", "S", 8], ["B", "S", 8]], { embed_dim: 16, num_heads: 4, batch_first: true }, "MHA_EMBED_MISMATCH"],
    ] as const;
    for (const [definitionId, shapes, parameters, code] of cases) {
      const snapshot = await analyzeGraph(registeredGraph(
        definitionId,
        shapes as unknown as Array<Array<string | number>>,
        parameters,
      ));
      expect(snapshot.diagnostics.map((item) => item.code), definitionId).toContain(code);
    }
  });

  it("is byte-stable for the same document and registry", async () => {
    const first = await analyzeGraph(graph());
    const second = await analyzeGraph(structuredClone(graph()));
    expect(JSON.stringify(second)).toBe(JSON.stringify(first));
  });

  it("counts shared parameters once while charging FLOPs for every call", async () => {
    const shared = registeredGraph(
      "pytorch.nn.linear",
      [["B", 8]],
      { in_features: 8, out_features: 8 },
    );
    const first = shared.nodes.at(-1)!;
    first.node_id = "draft:linear-1";
    first.semantic_name = "linear-1";
    first.parameter_group_id = "parameter-group:shared-linear";
    for (const port of first.ports) {
      port.port_id = port.port_id.replace("draft:target", first.node_id);
    }
    shared.edges[0].target_port_id = "draft:linear-1.input";
    const second = structuredClone(first);
    second.node_id = "draft:linear-2";
    second.semantic_name = "linear-2";
    for (const port of second.ports) {
      port.port_id = port.port_id.replace("draft:linear-1", second.node_id);
    }
    shared.nodes.push(second);
    shared.edges.push({
      edge_id: "draft:edge-linear-1-linear-2",
      source_port_id: "draft:linear-1.output",
      target_port_id: "draft:linear-2.input",
      relation: "main",
    });

    const snapshot = await analyzeGraph(shared);

    expect(snapshot.diagnostics.filter((item) => item.severity === "blocking")).toEqual([]);
    expect(snapshot.nodeCosts["draft:linear-1"].parameterCount).toBe("72");
    expect(snapshot.nodeCosts["draft:linear-2"].parameterCount).toBe("72");
    expect(snapshot.graphCost.parameterCount).toBe("72");
    expect(snapshot.graphCost.flops).toBe("B*8*16+B*8*16");
  });
});
