import { describe, expect, it } from "vitest";

import type { LabScene } from "./types";
import { layoutPatchesFromResult, startElkLayout } from "./layout-worker-client";
import { layoutRequestForScene, sceneGeometryFingerprint } from "./layout-worker-protocol";

const scene: LabScene = {
  scene_id: "layout-test",
  title: "Layout test",
  description: "",
  paper_width: 900,
  paper_height: 600,
  nodes: [
    { scene_node_id: "b", bounds: { x: 180, y: 80, width: 120, height: 64 }, shape: "operation", label: "B", secondary_label: "" },
    { scene_node_id: "a", hierarchy_node_id: "hierarchy:a", bounds: { x: -40, y: 20, width: 100, height: 50 }, shape: "io", label: "A", secondary_label: "" },
    { scene_node_id: "c", bounds: { x: 420, y: 160, width: 140, height: 70 }, shape: "operation", label: "C", secondary_label: "" },
  ],
  edges: [
    { scene_edge_id: "a-b", source_scene_node_id: "a", target_scene_node_id: "b", relation: "flow", label: "" },
    { scene_edge_id: "missing", source_scene_node_id: "a", target_scene_node_id: "missing", relation: "flow", label: "" },
  ],
};

describe("ELK layout worker protocol", () => {
  it("serializes only valid graph edges and selects direction from the view profile", () => {
    expect(layoutRequestForScene(scene, "request:1")).toMatchObject({
      requestId: "request:1",
      direction: "RIGHT",
      edges: [{ id: "a-b", sourceId: "a", targetId: "b" }],
    });
    expect(layoutRequestForScene({ ...scene, layout_profile: "paper" }, "request:2").direction).toBe("UP");
  });

  it("keeps pinned geometry exact and emits one position patch per movable node", () => {
    const patches = layoutPatchesFromResult(scene, [
      { id: "a", x: 24, y: 24 },
      { id: "b", x: 220, y: 100 },
      { id: "c", x: 440, y: 200 },
    ], new Set(["a"]));

    expect(patches).toHaveLength(2);
    expect(patches.map((patch) => patch.operation === "update-node" && patch.nodeId)).toEqual(["b", "c"]);
    expect(patches[0]).toMatchObject({
      changes: { bounds: { x: 156, y: 96, width: 120, height: 64 } },
    });
    expect(patches.some((patch) => patch.operation === "update-node" && patch.nodeId === "a")).toBe(false);
  });

  it("preserves the current top-left origin when no node is pinned", () => {
    const patches = layoutPatchesFromResult(scene, [
      { id: "a", x: 24, y: 24 },
      { id: "b", x: 220, y: 24 },
      { id: "c", x: 440, y: 24 },
    ], new Set());
    expect(patches.some((patch) => patch.operation === "update-node" && patch.nodeId === "a")).toBe(false);
    expect(Math.min(...scene.nodes.map((node) => node.bounds.x))).toBe(-40);
    expect(Math.min(...scene.nodes.map((node) => node.bounds.y))).toBe(20);
  });

  it("invalidates results after any scene geometry or topology change", () => {
    expect(sceneGeometryFingerprint(scene)).not.toBe(sceneGeometryFingerprint({
      ...scene,
      nodes: scene.nodes.map((node) => node.scene_node_id === "b"
        ? { ...node, bounds: { ...node.bounds, x: node.bounds.x + 1 } }
        : node),
    }));
  });

  it("terminates a pending worker and rejects cancellation without producing a result", async () => {
    let terminated = 0;
    let posted = false;
    const worker = {
      onmessage: null,
      onerror: null,
      postMessage() { posted = true; },
      terminate() { terminated += 1; },
    };
    const task = startElkLayout(scene, () => worker);
    task.cancel();
    await expect(task.promise).rejects.toMatchObject({ name: "AbortError" });
    expect(posted).toBe(true);
    expect(terminated).toBe(1);
  });
});
