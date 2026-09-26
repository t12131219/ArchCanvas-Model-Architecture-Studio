import { describe, expect, it } from "vitest";

import { applyVisualPatch, cloneScene } from "./model";
import { SCENARIOS } from "./scenarios";

describe("scene lab visual patches", () => {
  it("removes a node and every attached edge without mutating the source scene", () => {
    const source = cloneScene(SCENARIOS[0]);
    const removedId = source.nodes[1].scene_node_id;
    const next = applyVisualPatch(source, { operation: "remove-node", nodeId: removedId });

    expect(next.nodes.some((node) => node.scene_node_id === removedId)).toBe(false);
    expect(next.edges.some((edge) => (
      edge.source_scene_node_id === removedId || edge.target_scene_node_id === removedId
    ))).toBe(false);
    expect(source.nodes.some((node) => node.scene_node_id === removedId)).toBe(true);
  });

  it("rejects self edges and edges with missing endpoints", () => {
    const source = cloneScene(SCENARIOS[0]);
    const nodeId = source.nodes[0].scene_node_id;
    const edge = {
      scene_edge_id: "invalid-edge",
      source_scene_node_id: nodeId,
      target_scene_node_id: nodeId,
      relation: "flow" as const,
      label: "invalid",
    };

    expect(applyVisualPatch(source, { operation: "add-edge", edge })).toBe(source);
    expect(applyVisualPatch(source, {
      operation: "add-edge",
      edge: { ...edge, target_scene_node_id: "missing" },
    })).toBe(source);
  });
});
