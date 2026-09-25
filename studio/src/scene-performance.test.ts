import { describe, expect, it } from "vitest";

import {
  buildSceneRenderIndex,
  edgeLabelPoint,
  previewEdgePoints,
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

describe("previewEdgePoints", () => {
  const edge = {
    source_scene_node_id: "source",
    target_scene_node_id: "target",
    points: [
      { x: 150, y: 110 },
      { x: 240, y: 110 },
      { x: 240, y: 170 },
      { x: 330, y: 170 },
    ],
  };
  const index = buildSceneRenderIndex(nodes);

  it("translates an existing route when both endpoints move together", () => {
    expect(previewEdgePoints(edge, index.byId, {
      source: { x: 90, y: 100 },
      target: { x: 350, y: 160 },
    }, 0)).toEqual(edge.points.map((point) => ({ x: point.x + 20, y: point.y + 10 })));
  });

  it("reroutes from the moved boundary when only one endpoint moves", () => {
    const points = previewEdgePoints(edge, index.byId, { source: { x: 100, y: 100 } }, 0);

    expect(points[0]).toEqual({ x: 180, y: 120 });
    expect(points.at(-1)).toEqual({ x: 330, y: 170 });
    expect(edgeLabelPoint({ points })).not.toEqual(edgeLabelPoint(edge));
  });
});

describe("previewNodeTransform", () => {
  it("uses SVG user-space translation so the complete node group tracks the route preview", () => {
    expect(previewNodeTransform(nodes[2], { x: 105, y: 72 })).toBe("translate(35 -18)");
  });
});
