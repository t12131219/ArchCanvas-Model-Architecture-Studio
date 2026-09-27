import { describe, expect, it } from "vitest";

import { buildModuleDetail, EXPANDED_DETAIL_SIZES } from "./module-details";
import { optionCombinations, PRODUCTION_FIXTURES } from "./production-fixtures";
import { measureScene, routeScene, type RoutingInputScene } from "./routing-engine";
import { PRODUCTION_DETAIL_KINDS } from "./template-details";

describe("production visual-kernel matrix", () => {
  it("routes all 26 topologies across all 45 visual combinations", () => {
    const options = optionCombinations();
    expect(PRODUCTION_FIXTURES).toHaveLength(26);
    expect(options).toHaveLength(45);

    const digests: string[] = [];
    for (const fixture of PRODUCTION_FIXTURES) {
      const scene: RoutingInputScene = {
        sceneId: fixture.sceneId,
        width: fixture.width,
        height: fixture.height,
        nodes: fixture.nodes.map((node) => ({
          nodeId: node.nodeId,
          bounds: node.bounds,
          detailExpanded: Boolean(node.detailKind),
        })),
        edges: fixture.edges,
      };
      for (const option of options) {
        const routed = routeScene(scene, option.routeStyle);
        const metrics = measureScene(scene, routed);
        expect(routed).toHaveLength(fixture.edges.length);
        for (const route of routed) {
          expect(route.path).toMatch(/^M/);
          expect(route.points.length).toBeGreaterThanOrEqual(2);
          expect(route.points.every((point) => Number.isFinite(point.x) && Number.isFinite(point.y))).toBe(true);
          expect(Number.isFinite(route.labelPoint.x) && Number.isFinite(route.labelPoint.y)).toBe(true);
        }
        expect(Object.values(metrics).every(Number.isFinite)).toBe(true);
        digests.push(`${fixture.sceneId}:${option.routeStyle}:${option.nodeStyle}:${option.labelStyle}:${routed.map((route) => route.path).join("|")}`);
      }
    }
    expect(digests).toHaveLength(1170);
    expect(new Set(digests).size).toBe(1170);
  });

  it("builds every production catalog detail with bounded primitives and continuous boundaries", () => {
    expect(PRODUCTION_DETAIL_KINDS).toHaveLength(39);
    for (const kind of PRODUCTION_DETAIL_KINDS) {
      const size = EXPANDED_DETAIL_SIZES[kind];
      const bounds = { x: 40, y: 60, ...size };
      const detail = buildModuleDetail(kind, bounds);
      expect(detail.primitives.length, kind).toBeGreaterThan(0);
      expect(detail.entryPoint, kind).toEqual({ x: bounds.x, y: bounds.y + bounds.height / 2 });
      expect(detail.exitPoint, kind).toEqual({ x: bounds.x + bounds.width, y: bounds.y + bounds.height / 2 });
      for (const primitive of detail.primitives) {
        if (primitive.kind === "flow") {
          expect(primitive.points.length, kind).toBeGreaterThanOrEqual(2);
          expect(primitive.points.every((point) => Number.isFinite(point.x) && Number.isFinite(point.y)), kind).toBe(true);
        }
      }
    }
  });
});
