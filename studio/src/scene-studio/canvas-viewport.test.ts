import { describe, expect, it } from "vitest";

import {
  boundsIntersect,
  canvasWorldViewport,
  LARGE_SCENE_EDGE_THRESHOLD,
  LARGE_SCENE_NODE_THRESHOLD,
  pointInBounds,
  shouldVirtualizeSceneDetails,
} from "./canvas-viewport";

describe("large-scene viewport detail policy", () => {
  it("maps the screen viewport into world coordinates with CSS-pixel overscan", () => {
    expect(canvasWorldViewport(
      { x: -200, y: 100, zoom: 2 },
      { width: 1000, height: 600 },
      120,
    )).toEqual({
      x: 40,
      y: -110,
      width: 620,
      height: 420,
    });
  });

  it("treats touching bounds as visible and rejects separated bounds", () => {
    const viewport = { x: 100, y: 80, width: 400, height: 300 };
    expect(boundsIntersect(viewport, { x: 500, y: 120, width: 20, height: 20 })).toBe(true);
    expect(boundsIntersect(viewport, { x: 501, y: 120, width: 20, height: 20 })).toBe(false);
    expect(pointInBounds({ x: 100, y: 380 }, viewport)).toBe(true);
    expect(pointInBounds({ x: 99, y: 380 }, viewport)).toBe(false);
  });

  it("only enables detail virtualization for genuinely large scenes", () => {
    expect(shouldVirtualizeSceneDetails(LARGE_SCENE_NODE_THRESHOLD - 1, LARGE_SCENE_EDGE_THRESHOLD - 1)).toBe(false);
    expect(shouldVirtualizeSceneDetails(LARGE_SCENE_NODE_THRESHOLD, 0)).toBe(true);
    expect(shouldVirtualizeSceneDetails(0, LARGE_SCENE_EDGE_THRESHOLD)).toBe(true);
  });
});
