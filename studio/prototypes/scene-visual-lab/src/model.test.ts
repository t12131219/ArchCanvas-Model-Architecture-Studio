import { describe, expect, it } from "vitest";

import { expandScene } from "./expansion";
import { applyVisualPatch, clampBounds, cloneScene, editableNodeBounds } from "./model";
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

  it("keeps edits in stored coordinate space for every expandable scenario", () => {
    let sawShiftedNode = false;
    for (const source of SCENARIOS) {
      const expandedId = source.nodes.find((node) => node.detail_kind)?.scene_node_id;
      if (!expandedId) continue;
      const displayed = expandScene(source, new Set([expandedId]));

      for (const displayedNode of displayed.nodes) {
        const storedNode = source.nodes.find((node) => node.scene_node_id === displayedNode.scene_node_id)!;
        if (displayedNode.bounds.x !== storedNode.bounds.x) sawShiftedNode = true;
        expect(editableNodeBounds(source, displayedNode)).toEqual(storedNode.bounds);
      }
    }
    expect(sawShiftedNode).toBe(true);
  });

  it("keeps node positions unbounded while still constraining editable sizes", () => {
    const scene = cloneScene(SCENARIOS[0]);

    expect(clampBounds({ x: -480, y: -260, width: 20, height: 500 }, scene)).toEqual({
      x: -480,
      y: -260,
      width: 72,
      height: 180,
    });
    expect(clampBounds({
      x: scene.paper_width + 900,
      y: scene.paper_height + 700,
      width: 120,
      height: 80,
    }, scene)).toMatchObject({
      x: scene.paper_width + 900,
      y: scene.paper_height + 700,
    });
  });
});
