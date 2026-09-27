import { describe, expect, it } from "vitest";

import { nodesInSelection, selectionBounds } from "./selection";

describe("selectionBounds", () => {
  it("normalizes reverse-direction drags", () => {
    expect(selectionBounds({ x: 80, y: 70 }, { x: 20, y: 10 })).toEqual({
      x: 20,
      y: 10,
      width: 60,
      height: 60,
    });
  });
});

describe("nodesInSelection", () => {
  it("selects fully enclosed authored nodes and excludes the scene root", () => {
    const selected = nodesInSelection(
      [
        {
          scene_node_id: "root",
          bounds: { x: 0, y: 0, width: 200, height: 200 },
        },
        {
          scene_node_id: "inside",
          parent_scene_node_id: "root",
          bounds: { x: 20, y: 20, width: 30, height: 30 },
        },
        {
          scene_node_id: "partial",
          parent_scene_node_id: "root",
          bounds: { x: 80, y: 80, width: 40, height: 40 },
        },
      ],
      { x: 10, y: 10, width: 90, height: 90 },
    );

    expect(selected).toEqual(["inside"]);
  });
});
