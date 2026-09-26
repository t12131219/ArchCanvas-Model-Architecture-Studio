import { describe, expect, it } from "vitest";

import { measureScene, routeScene } from "./routing";
import { optionCombinations, SCENARIOS } from "./scenarios";
import { renderSceneSvg } from "./svg-export";

describe("scene lab case matrix", () => {
  it("covers every topology and visual combination", () => {
    expect(SCENARIOS).toHaveLength(26);
    expect(optionCombinations()).toHaveLength(45);
    expect(SCENARIOS.length * optionCombinations().length).toBe(1170);
  });

  it("renders all 1170 cases with finite routes and metrics", () => {
    for (const scene of SCENARIOS) {
      for (const options of optionCombinations()) {
        const routes = routeScene(scene, options.routeStyle);
        const metrics = measureScene(scene, routes);
        const { svg } = renderSceneSvg(scene, options);

        expect(routes, `${scene.scene_id} ${options.routeStyle}`).toHaveLength(scene.edges.length);
        expect(routes.every((route) => route.points.length >= 2)).toBe(true);
        expect(routes.flatMap((route) => route.points).every((point) => (
          Number.isFinite(point.x) && Number.isFinite(point.y)
        ))).toBe(true);
        expect(Object.values(metrics).every(Number.isFinite)).toBe(true);
        expect(svg).toContain("<svg");
        expect(svg).toContain("marker-end");
        expect(svg).not.toContain("NaN");
        expect(svg).not.toContain("undefined");
      }
    }
  });

  it("samples curved routes for collision and length metrics", () => {
    const scene = SCENARIOS.find((item) => item.scene_id === "fan-out")!;
    const routes = routeScene(scene, "curve");

    expect(routes.every((route) => route.points.length === 9)).toBe(true);
    expect(routes.every((route) => route.path.includes(" C "))).toBe(true);
    expect(measureScene(scene, routes).routeLength).toBeGreaterThan(0);
  });

  it("separates fan-in ports and avoids reverse departures in adaptive mode", () => {
    const fanIn = SCENARIOS.find((item) => item.scene_id === "terminal-fan-in")!;
    const nearestSide = SCENARIOS.find((item) => item.scene_id === "nearest-side-regression")!;
    const fanInRoutes = routeScene(fanIn, "adaptive");
    const nearestRoutes = routeScene(nearestSide, "adaptive");

    expect(new Set(fanInRoutes.map((route) => `${route.points.at(-1)!.x}:${route.points.at(-1)!.y}`)).size).toBe(fanIn.edges.length);
    expect(measureScene(fanIn, fanInRoutes).endpointCongestion).toBe(0);
    expect(nearestRoutes[0].sourceSide).toBe("left");
    expect(nearestRoutes[0].targetSide).toBe("right");
    expect(measureScene(nearestSide, nearestRoutes).reverseExits).toBe(0);
  });

  it("rotates labels placed on long vertical segments", () => {
    const scene = SCENARIOS.find((item) => item.scene_id === "vertical-edge-labels")!;
    const routes = routeScene(scene, "adaptive");

    expect(routes.some((route) => Math.abs(route.labelAngle) === 90)).toBe(true);
    expect(renderSceneSvg(scene, { routeStyle: "adaptive", nodeStyle: "semantic", labelStyle: "plate" }).svg)
      .toContain("rotate(-90");
  });
});
