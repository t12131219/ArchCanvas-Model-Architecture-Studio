import { describe, expect, it } from "vitest";

import {
  buildSceneRenderIndex,
  previewNodeTransform,
} from "./scene-performance";

const nodes = [
  {
    scene_node_id: "root",
    shape: "container",
    bounds: { x: 0, y: 0, width: 600, height: 300 },
  },
  {
    scene_node_id: "group",
    parent_scene_node_id: "root",
    shape: "container",
    bounds: { x: 30, y: 30, width: 520, height: 220 },
  },
  {
    scene_node_id: "source",
    parent_scene_node_id: "group",
    shape: "rect",
    bounds: { x: 70, y: 90, width: 80, height: 40 },
  },
  {
    scene_node_id: "target",
    parent_scene_node_id: "group",
    shape: "rect",
    bounds: { x: 330, y: 150, width: 90, height: 40 },
  },
] as const;

describe("buildSceneRenderIndex", () => {
  it("indexes nodes and partitions the three SVG render layers in one pass", () => {
    const index = buildSceneRenderIndex(nodes);

    expect(index.roots.map((node) => node.scene_node_id)).toEqual(["root"]);
    expect(index.containers.map((node) => node.scene_node_id)).toEqual(["group"]);
    expect(index.leaves.map((node) => node.scene_node_id)).toEqual(["source", "target"]);
    expect(index.depths.get("target")).toBe(2);
    expect(index.byId.get("source")?.bounds.x).toBe(70);
  });
});

describe("previewNodeTransform", () => {
  it("uses SVG user-space translation so the complete node group tracks the route preview", () => {
    expect(previewNodeTransform(nodes[2], { x: 105, y: 72 })).toBe("translate(35 -18)");
  });
});
