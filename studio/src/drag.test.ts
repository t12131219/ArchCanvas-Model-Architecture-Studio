import { describe, expect, it } from "vitest";

import { constrainDragDelta, type DraggableNode } from "./drag";

const nodes: DraggableNode[] = [
  {
    scene_node_id: "root",
    bounds: { x: 0, y: 0, width: 500, height: 400 },
  },
  {
    scene_node_id: "parent-a",
    parent_scene_node_id: "root",
    bounds: { x: 20, y: 30, width: 200, height: 160 },
  },
  {
    scene_node_id: "child-a",
    parent_scene_node_id: "parent-a",
    bounds: { x: 60, y: 70, width: 80, height: 40 },
  },
  {
    scene_node_id: "grandchild-a",
    parent_scene_node_id: "child-a",
    bounds: { x: 70, y: 80, width: 30, height: 20 },
  },
  {
    scene_node_id: "parent-b",
    parent_scene_node_id: "root",
    bounds: { x: 270, y: 40, width: 180, height: 140 },
  },
  {
    scene_node_id: "child-b",
    parent_scene_node_id: "parent-b",
    bounds: { x: 300, y: 80, width: 60, height: 50 },
  },
];

describe("constrainDragDelta", () => {
  it("clamps a child against every side of its parent", () => {
    expect(constrainDragDelta(nodes, ["child-a"], { x: -100, y: -100 })).toEqual({
      x: -40,
      y: -40,
    });
    expect(constrainDragDelta(nodes, ["child-a"], { x: 200, y: 200 })).toEqual({
      x: 80,
      y: 80,
    });
  });

  it("moves a container and its descendants as one subtree", () => {
    expect(
      constrainDragDelta(nodes, ["parent-a", "child-a", "grandchild-a"], { x: 400, y: 400 }),
    ).toEqual({ x: 280, y: 210 });
  });

  it("intersects containment limits for a multi-parent selection", () => {
    expect(constrainDragDelta(nodes, ["child-a", "child-b"], { x: 100, y: -100 })).toEqual({
      x: 80,
      y: -40,
    });
  });

  it("does not constrain a child separately when its parent also moves", () => {
    expect(constrainDragDelta(nodes, ["child-a", "grandchild-a"], { x: 200, y: 200 })).toEqual({
      x: 80,
      y: 80,
    });
  });
});
