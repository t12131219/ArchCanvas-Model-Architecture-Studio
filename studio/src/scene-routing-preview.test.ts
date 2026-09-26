import { describe, expect, it } from "vitest";

import routingFixture from "../../fixtures/routing/preview-contract-v1.json";
import { buildSceneRenderIndex, edgeLabelPoint } from "./scene-performance";
import { routingContractSignature } from "./scene-routing-contract";
import { createGestureRouteLock, previewEdgePoints } from "./scene-routing-preview";

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

describe("gesture route preview", () => {
  const index = buildSceneRenderIndex(nodes);

  it("translates the authoritative route when both endpoints move together", () => {
    expect(previewEdgePoints(edge, index.byId, {
      source: { x: 90, y: 100 },
      target: { x: 350, y: 160 },
    }, 0)).toEqual(edge.points.map((point) => ({ x: point.x + 20, y: point.y + 10 })));
  });

  it("keeps the pointer-down port sides and corridor while one endpoint moves", () => {
    const lock = createGestureRouteLock(edge, index.byId, 0);
    const first = previewEdgePoints(
      edge,
      index.byId,
      { source: { x: 100, y: 100 } },
      0,
      lock,
    );
    const crossed = previewEdgePoints(
      edge,
      index.byId,
      { source: { x: 380, y: 100 } },
      0,
      lock,
    );

    expect(lock?.source.side).toBe("right");
    expect(lock?.target.side).toBe("left");
    expect(first[0]).toEqual({ x: 180, y: 120 });
    expect(first.at(-1)).toEqual({ x: 330, y: 170 });
    expect(first[1].x).toBeGreaterThan(first[0].x);
    expect(crossed[0]).toEqual({ x: 460, y: 120 });
    expect(crossed[1].x).toBeGreaterThan(crossed[0].x);
    expect(first.some((point) => point.x === lock?.corridorValue)).toBe(true);
    expect(crossed.some((point) => point.x === lock?.corridorValue)).toBe(true);
    expect(edgeLabelPoint({ points: first })).not.toEqual(edgeLabelPoint(edge));
  });

  it("keeps every generated segment orthogonal", () => {
    const lock = createGestureRouteLock(edge, index.byId, 0);
    const points = previewEdgePoints(
      edge,
      index.byId,
      { source: { x: 115, y: 125 } },
      0,
      lock,
    );
    expect(points.slice(1).every((point, pointIndex) => (
      point.x === points[pointIndex].x || point.y === points[pointIndex].y
    ))).toBe(true);
  });

  it("uses the adjacent segment to disambiguate a corner attachment", () => {
    const cornerEdge = {
      ...edge,
      points: [
        ...edge.points.slice(0, -2),
        { x: 330, y: 130 },
        { x: 330, y: 150 },
      ],
    };
    const lock = createGestureRouteLock(cornerEdge, index.byId, 0);
    expect(lock?.target.side).toBe("top");
  });
});

describe("Python routing contract fixture", () => {
  const index = buildSceneRenderIndex(routingFixture.nodes);

  it("preserves authoritative port sides and the portal signature", () => {
    const lock = createGestureRouteLock(routingFixture.edge, index.byId, 0);
    expect(lock?.source.side).toBe(routingFixture.expected.source_side);
    expect(lock?.target.side).toBe(routingFixture.expected.target_side);
    expect(routingContractSignature(routingFixture.edge)).toBe(
      routingFixture.expected.contract_signature,
    );
  });

  it("keeps the moved endpoint attached while retaining the Python route contract", () => {
    const lock = createGestureRouteLock(routingFixture.edge, index.byId, 0);
    const points = previewEdgePoints(
      routingFixture.edge,
      index.byId,
      routingFixture.preview,
      0,
      lock,
    );
    const source = index.byId.get(routingFixture.edge.source_scene_node_id)!;
    const moved = routingFixture.preview.source;
    expect(points[0].x).toBe(moved.x + source.bounds.width);
    expect(points[0].y).toBeGreaterThanOrEqual(moved.y);
    expect(points[0].y).toBeLessThanOrEqual(moved.y + source.bounds.height);
    expect(routingContractSignature(routingFixture.edge)).toBe(
      routingFixture.expected.contract_signature,
    );
  });
});
