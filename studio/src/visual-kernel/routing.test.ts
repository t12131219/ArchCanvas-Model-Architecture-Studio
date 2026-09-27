import { describe, expect, it } from "vitest";

import { curvePath, labelGeometry, roundedPath, routePoints } from "./routing";
import type { RouteStyle } from "./types";

describe("production visual-kernel routing primitives", () => {
  it.each<RouteStyle>(["adaptive", "direct", "orthogonal", "channel", "curve"])(
    "builds finite %s routes",
    (style) => {
      const points = routePoints(
        { x: 20, y: 30, width: 140, height: 80 },
        { x: 420, y: 210, width: 160, height: 90 },
        style,
      );
      expect(points.length).toBeGreaterThanOrEqual(2);
      expect(points.every((point) => Number.isFinite(point.x) && Number.isFinite(point.y))).toBe(true);
      expect(style === "curve" ? curvePath(points) : roundedPath(points)).not.toContain("NaN");
      expect(labelGeometry(points).point).toEqual(expect.objectContaining({ x: expect.any(Number), y: expect.any(Number) }));
    },
  );

  it("keeps orthogonal segments axis aligned", () => {
    const points = routePoints(
      { x: 20, y: 30, width: 140, height: 80 },
      { x: 420, y: 210, width: 160, height: 90 },
      "adaptive",
    );
    for (let index = 1; index < points.length; index += 1) {
      expect(points[index].x === points[index - 1].x || points[index].y === points[index - 1].y).toBe(true);
    }
  });
});
