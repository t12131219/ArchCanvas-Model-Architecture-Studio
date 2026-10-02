import { describe, expect, it } from "vitest";

import { alignNodeBounds, distributeNodeBounds } from "./layout-commands";
import type { LabNode } from "./types";

function node(id: string, x: number, y: number, width = 100, height = 60): LabNode {
  return {
    scene_node_id: id,
    bounds: { x, y, width, height },
    shape: "operation",
    label: id,
    secondary_label: "",
  };
}

describe("layout commands", () => {
  it("aligns heterogeneous nodes by edge or center without moving pinned nodes", () => {
    const nodes = [node("a", -40, 10, 80), node("b", 120, 90, 140), node("c", 340, -20, 60)];
    const left = alignNodeBounds(nodes, "left", new Set(["b"]));
    expect(left.get("a")?.x).toBe(-40);
    expect(left.has("b")).toBe(false);
    expect(left.get("c")?.x).toBe(-40);

    const centered = alignNodeBounds(nodes, "horizontal-center");
    const centers = nodes.map((item) => {
      const bounds = centered.get(item.scene_node_id)!;
      return bounds.x + bounds.width / 2;
    });
    expect(new Set(centers).size).toBe(1);
  });

  it("distributes node centers deterministically while preserving endpoints and pins", () => {
    const nodes = [node("a", 0, 0), node("b", 70, 100), node("c", 310, 300), node("d", 500, 600)];
    const horizontal = distributeNodeBounds(nodes, "horizontal");
    expect(horizontal.has("a")).toBe(false);
    expect(horizontal.has("d")).toBe(false);
    expect(horizontal.get("b")!.x + 50).toBeCloseTo(50 + (550 - 50) / 3);
    expect(horizontal.get("c")!.x + 50).toBeCloseTo(50 + 2 * (550 - 50) / 3);

    const vertical = distributeNodeBounds(nodes, "vertical", new Set(["b"]));
    expect(vertical.has("b")).toBe(false);
    expect(vertical.get("c")!.y + 30).toBeCloseTo(30 + 2 * (630 - 30) / 3);
  });
});
