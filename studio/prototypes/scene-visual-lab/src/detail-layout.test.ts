import { describe, expect, it } from "vitest";

import {
  buildInlineDetailLayout,
  clampDetailOffset,
  detailLevelContentBounds,
  detailLevelKey,
  expandedDetailSize,
  findInlineDetailLevel,
  fullyExpandedDetailTree,
  inlineAtomicEntry,
  inlineExpandedChildren,
  layoutDetailDiagram,
  listDetailNodes,
  visibleContainmentFrameBounds,
} from "./detail-layout";
import type { DetailExpansionBranch, InlineDetailLevel } from "./detail-layout";
import {
  buildAtomicHierarchyProjection,
  projectedAtomicEntryForModule,
  projectedAtomicExitForModule,
} from "./atomic-hierarchy";
import { buildModuleDetail, EXPANDED_DETAIL_SIZES } from "./module-details";
import type { ModuleDetailDiagram } from "./module-details";
import type { Bounds, NodeDetailKind, Point } from "./types";

function segmentCrossesBounds(a: Point, b: Point, bounds: Bounds): boolean {
  const right = bounds.x + bounds.width;
  const bottom = bounds.y + bounds.height;
  if (a.y === b.y) {
    return a.y > bounds.y && a.y < bottom && Math.max(Math.min(a.x, b.x), bounds.x) < Math.min(Math.max(a.x, b.x), right);
  }
  if (a.x === b.x) {
    return a.x > bounds.x && a.x < right && Math.max(Math.min(a.y, b.y), bounds.y) < Math.min(Math.max(a.y, b.y), bottom);
  }
  return false;
}

function pointsEqual(a: Point, b: Point): boolean {
  return Math.abs(a.x - b.x) < 0.01 && Math.abs(a.y - b.y) < 0.01;
}

function routeBacktrackLength(points: Point[]): number {
  let length = 0;
  for (let index = 2; index < points.length; index += 1) {
    const first = points[index - 2];
    const middle = points[index - 1];
    const last = points[index];
    if (first.y === middle.y && middle.y === last.y) {
      const incoming = middle.x - first.x;
      const outgoing = last.x - middle.x;
      if (incoming * outgoing < 0) length += Math.min(Math.abs(incoming), Math.abs(outgoing));
    } else if (first.x === middle.x && middle.x === last.x) {
      const incoming = middle.y - first.y;
      const outgoing = last.y - middle.y;
      if (incoming * outgoing < 0) length += Math.min(Math.abs(incoming), Math.abs(outgoing));
    }
  }
  return length;
}

function longestCollinearOverlap(first: Point[], second: Point[]): number {
  let longest = 0;
  for (let index = 1; index < first.length; index += 1) {
    const a = first[index - 1];
    const b = first[index];
    for (let otherIndex = 1; otherIndex < second.length; otherIndex += 1) {
      const c = second[otherIndex - 1];
      const d = second[otherIndex];
      if (a.y === b.y && c.y === d.y && a.y === c.y) {
        longest = Math.max(longest, Math.max(0, Math.min(Math.max(a.x, b.x), Math.max(c.x, d.x))
          - Math.max(Math.min(a.x, b.x), Math.min(c.x, d.x))));
      } else if (a.x === b.x && c.x === d.x && a.x === c.x) {
        longest = Math.max(longest, Math.max(0, Math.min(Math.max(a.y, b.y), Math.max(c.y, d.y))
          - Math.max(Math.min(a.y, b.y), Math.min(c.y, d.y))));
      }
    }
  }
  return longest;
}

function boundaryOverlapLength(points: Point[], bounds: Bounds): number {
  const right = bounds.x + bounds.width;
  const bottom = bounds.y + bounds.height;
  let overlap = 0;
  for (let index = 1; index < points.length; index += 1) {
    const first = points[index - 1];
    const second = points[index];
    if (Math.abs(first.x - second.x) < 0.01
      && (Math.abs(first.x - bounds.x) < 0.01 || Math.abs(first.x - right) < 0.01)) {
      overlap += Math.max(0, Math.min(Math.max(first.y, second.y), bottom)
        - Math.max(Math.min(first.y, second.y), bounds.y));
    }
    if (Math.abs(first.y - second.y) < 0.01
      && (Math.abs(first.y - bounds.y) < 0.01 || Math.abs(first.y - bottom) < 0.01)) {
      overlap += Math.max(0, Math.min(Math.max(first.x, second.x), right)
        - Math.max(Math.min(first.x, second.x), bounds.x));
    }
  }
  return overlap;
}

function distanceToNodeBoundary(point: Point, bounds: Bounds): number {
  const right = bounds.x + bounds.width;
  const bottom = bounds.y + bounds.height;
  const outsideX = Math.max(bounds.x - point.x, 0, point.x - right);
  const outsideY = Math.max(bounds.y - point.y, 0, point.y - bottom);
  if (outsideX || outsideY) return Math.hypot(outsideX, outsideY);
  return Math.min(
    Math.abs(point.x - bounds.x),
    Math.abs(point.x - right),
    Math.abs(point.y - bounds.y),
    Math.abs(point.y - bottom),
  );
}

function hierarchyNodeBounds(level: InlineDetailLevel): Bounds[] {
  return [
    ...level.nodes.map((node) => node.bounds),
    ...inlineExpandedChildren(level).flatMap((expanded) => hierarchyNodeBounds(expanded.level)),
  ];
}

function hierarchyLeafBounds(level: InlineDetailLevel): Bounds[] {
  const expanded = inlineExpandedChildren(level);
  const expandedIds = new Set(expanded.map((child) => child.node.id));
  return [
    ...level.nodes.filter((node) => !expandedIds.has(node.id)).map((node) => node.bounds),
    ...expanded.flatMap((child) => hierarchyLeafBounds(child.level)),
  ];
}

function hierarchyAtomicPorts(level: InlineDetailLevel): Point[] {
  const projection = buildAtomicHierarchyProjection(level);
  const projected = projection.portalChains.flatMap((chain) => [
    projectedAtomicEntryForModule(projection, chain.childModuleId)?.point,
    projectedAtomicExitForModule(projection, chain.childModuleId)?.point,
  ]).filter((point): point is Point => Boolean(point));
  const inline = level.expandedChild
    ? [inlineAtomicEntry(level.expandedChild.level)?.point, ...hierarchyAtomicPorts(level.expandedChild.level)]
    : [];
  return [...projected, ...inline].filter((point): point is Point => Boolean(point));
}

function expectBoundsInside(inner: Bounds, outer: Bounds, label: string): void {
  const context = `${label} ${JSON.stringify({ inner, outer })}`;
  expect(inner.x, `${context} left`).toBeGreaterThanOrEqual(outer.x - 0.01);
  expect(inner.y, `${context} top`).toBeGreaterThanOrEqual(outer.y - 0.01);
  expect(inner.x + inner.width, `${context} right`).toBeLessThanOrEqual(outer.x + outer.width + 0.01);
  expect(inner.y + inner.height, `${context} bottom`).toBeLessThanOrEqual(outer.y + outer.height + 0.01);
}

function expectRecursiveContainment(level: InlineDetailLevel): void {
  const frame = visibleContainmentFrameBounds(level);
  for (const node of level.nodes) {
    expectBoundsInside(node.bounds, level.bounds, `${level.levelKey}/${node.label} in surface`);
    if (frame) expectBoundsInside(node.bounds, frame, `${level.levelKey}/${node.label} in frame`);
  }
  const expanded = inlineExpandedChildren(level);
  for (let index = 0; index < expanded.length; index += 1) {
    expectBoundsInside(expanded[index].level.bounds, level.bounds, `${expanded[index].level.levelKey} child surface`);
    if (frame) expectBoundsInside(expanded[index].level.bounds, frame, `${expanded[index].level.levelKey} child frame`);
    for (let other = index + 1; other < expanded.length; other += 1) {
      const first = expanded[index].level.bounds;
      const second = expanded[other].level.bounds;
      const overlaps = first.x < second.x + second.width
        && first.x + first.width > second.x
        && first.y < second.y + second.height
        && first.y + first.height > second.y;
      expect(overlaps, `${expanded[index].level.levelKey} overlaps ${expanded[other].level.levelKey}`).toBe(false);
    }
    expectRecursiveContainment(expanded[index].level);
  }
}

describe("interactive module detail layout", () => {
  it("moves a stable child node and keeps its incident arrows attached", () => {
    const diagram = buildModuleDetail("gru", { x: 20, y: 30, width: 900, height: 380 });
    const updateGate = listDetailNodes(diagram).find((node) => node.label === "z_t")!;
    const moved = layoutDetailDiagram(diagram, { [updateGate.id]: { x: 44, y: 18 } });
    const movedGate = listDetailNodes(moved).find((node) => node.id === updateGate.id)!;

    expect(movedGate.bounds.x).toBe(updateGate.bounds.x + 44);
    expect(movedGate.bounds.y).toBe(updateGate.bounds.y + 18);
    const attachedPoints = moved.primitives
      .filter((primitive) => primitive.kind === "flow")
      .flatMap((primitive) => primitive.kind === "flow" ? [primitive.points[0], primitive.points.at(-1)!] : []);
    expect(attachedPoints.some((point) => point.x === movedGate.bounds.x || point.x === movedGate.bounds.x + movedGate.bounds.width)).toBe(true);
  });

  it("routes the GRU candidate input around the update gate", () => {
    const diagram = layoutDetailDiagram(buildModuleDetail("gru", { x: 0, y: 0, width: 900, height: 380 }));
    const updateGate = listDetailNodes(diagram).find((node) => node.label === "z_t")!;
    const candidate = listDetailNodes(diagram).find((node) => node.label === "h̃_t")!;
    const candidateInput = diagram.primitives.find((primitive) => primitive.kind === "flow"
      && primitive.points.at(-1)?.x === candidate.bounds.x
      && primitive.points.at(-1)?.y === candidate.bounds.y + candidate.bounds.height / 2);

    expect(candidateInput?.kind).toBe("flow");
    if (candidateInput?.kind !== "flow") return;
    const crossesUpdateGate = candidateInput.points.slice(1).some((point, index) => (
      segmentCrossesBounds(candidateInput.points[index], point, updateGate.bounds)
    ));
    expect(crossesUpdateGate).toBe(false);
  });

  it("uses distinct semantic channels and axis ports for attention inputs", () => {
    const diagram = buildModuleDetail("attention", { x: 0, y: 0, ...EXPANDED_DETAIL_SIZES.attention });
    const multipliers = listDetailNodes(diagram)
      .filter((node) => node.primitive.kind === "circle" && node.label === "×")
      .sort((a, b) => a.bounds.x - b.bounds.x);
    const flows = diagram.primitives.filter((primitive) => primitive.kind === "flow");
    const incoming = (node: (typeof multipliers)[number]) => flows.filter((flow) => {
      const point = flow.points.at(-1)!;
      return point.x >= node.bounds.x && point.x <= node.bounds.x + node.bounds.width
        && point.y >= node.bounds.y && point.y <= node.bounds.y + node.bounds.height;
    });
    const firstInputs = incoming(multipliers[0]);
    const secondInputs = incoming(multipliers[1]);

    expect(firstInputs.map((flow) => [flow.channel, flow.tone])).toEqual(expect.arrayContaining([
      ["Q", "blue"],
      ["K", "green"],
    ]));
    expect(secondInputs.map((flow) => [flow.channel, flow.tone])).toEqual(expect.arrayContaining([
      ["attention-weights", "green"],
      ["V", "pink"],
    ]));
    for (const [node, inputs] of [[multipliers[0], firstInputs], [multipliers[1], secondInputs]] as const) {
      const center = { x: node.bounds.x + node.bounds.width / 2, y: node.bounds.y + node.bounds.height / 2 };
      expect(inputs.some((flow) => pointsEqual(flow.points.at(-1)!, { x: center.x, y: node.bounds.y }))).toBe(true);
      expect(inputs.some((flow) => pointsEqual(flow.points.at(-1)!, { x: node.bounds.x, y: center.y }))).toBe(true);
    }
  });

  it("assigns separate routing corridors when dragged arrows would otherwise overlap", () => {
    const diagram: ModuleDetailDiagram = {
      kind: "attention",
      entryPoint: { x: 0, y: 100 },
      exitPoint: { x: 340, y: 100 },
      primitives: [
        { kind: "rect", x: 20, y: 50, width: 40, height: 30, rx: 4, label: "A", tone: "blue" },
        { kind: "rect", x: 20, y: 120, width: 40, height: 30, rx: 4, label: "B", tone: "green" },
        { kind: "rect", x: 280, y: 50, width: 40, height: 30, rx: 4, label: "C", tone: "blue" },
        { kind: "rect", x: 280, y: 120, width: 40, height: 30, rx: 4, label: "D", tone: "green" },
        { kind: "flow", points: [{ x: 60, y: 65 }, { x: 280, y: 65 }], channel: "upper" },
        { kind: "flow", points: [{ x: 60, y: 135 }, { x: 280, y: 135 }], channel: "lower" },
      ],
    };
    const nodes = listDetailNodes(diagram);
    const targetC = nodes.find((node) => node.label === "C")!;
    const targetD = nodes.find((node) => node.label === "D")!;
    const moved = layoutDetailDiagram(diagram, {
      [targetC.id]: { x: 0, y: 70 },
      [targetD.id]: { x: 0, y: -70 },
    });
    const routed = moved.primitives.filter((primitive) => primitive.kind === "flow");

    expect(routed).toHaveLength(2);
    expect(longestCollinearOverlap(routed[0].points, routed[1].points)).toBeLessThanOrEqual(14);
  });

  it("does not leave collinear hairpins after connected nodes move", () => {
    const diagram: ModuleDetailDiagram = {
      kind: "attention",
      entryPoint: { x: 0, y: 120 },
      exitPoint: { x: 420, y: 120 },
      primitives: [
        { kind: "rect", x: 30, y: 150, width: 90, height: 54, rx: 4, label: "Source", tone: "blue" },
        { kind: "rect", x: 270, y: 40, width: 100, height: 54, rx: 4, label: "Target", tone: "violet" },
        { kind: "rect", x: 170, y: 120, width: 48, height: 48, rx: 4, label: "Obstacle", tone: "neutral" },
        { kind: "flow", points: [{ x: 120, y: 177 }, { x: 270, y: 67 }], channel: "moved-route" },
      ],
    };
    const source = listDetailNodes(diagram).find((node) => node.label === "Source")!;
    const target = listDetailNodes(diagram).find((node) => node.label === "Target")!;
    const moved = layoutDetailDiagram(diagram, {
      [source.id]: { x: 36, y: -58 },
      [target.id]: { x: -18, y: 92 },
    });
    const flow = moved.primitives.find((primitive) => primitive.kind === "flow")!;

    expect(routeBacktrackLength(flow.points)).toBe(0);
  });

  it("rebinds VAE parameter branches to the expanded encoder exit", () => {
    const kind: NodeDetailKind = "variational-autoencoder";
    const base = buildModuleDetail(kind, { x: 0, y: 0, ...EXPANDED_DETAIL_SIZES[kind] });
    const encoder = listDetailNodes(base).find((node) => node.label === "Encoder")!;
    const branch: DetailExpansionBranch = { childId: encoder.id };
    const size = expandedDetailSize(kind, branch);
    const level = buildInlineDetailLayout(kind, { x: 0, y: 0, ...size }, branch, {}, "vae-root");
    const expanded = level.expandedChild!;
    const projection = buildAtomicHierarchyProjection(level);
    const exit = projectedAtomicExitForModule(projection, expanded.level.levelKey)!.point;
    const flows = level.diagram.primitives.filter((primitive) => primitive.kind === "flow");
    const outgoing = flows.filter((flow) => pointsEqual(flow.points[0], exit)
      && !pointsEqual(flow.points.at(-1)!, exit));
    const epsilon = level.nodes.find((node) => node.label === "ε")!;
    const sampler = level.nodes.find((node) => node.label === "μ+σε")!;

    expect(outgoing).toHaveLength(2);
    expect(outgoing.map((flow) => flow.points.at(-1)!.y).sort((a, b) => a - b)).toEqual([
      level.nodes.find((node) => node.label === "μ")!.bounds.y + 25,
      level.nodes.find((node) => node.label === "log σ²")!.bounds.y + 25,
    ]);
    expect(flows.some((flow) => pointsEqual(flow.points[0], {
      x: epsilon.bounds.x + epsilon.bounds.width / 2,
      y: epsilon.bounds.y + epsilon.bounds.height,
    }) && pointsEqual(flow.points.at(-1)!, {
      x: sampler.bounds.x + sampler.bounds.width / 2,
      y: sampler.bounds.y,
    }))).toBe(true);
  });

  it("switches ordinary VAE flow ports when a child moves around its target", () => {
    const kind: NodeDetailKind = "variational-autoencoder";
    const base = buildModuleDetail(kind, { x: 0, y: 0, ...EXPANDED_DETAIL_SIZES[kind] });
    const epsilon = listDetailNodes(base).find((node) => node.label === "ε")!;
    const sampler = listDetailNodes(base).find((node) => node.label === "μ+σε")!;

    const belowOffset = {
      x: 0,
      y: sampler.bounds.y + sampler.bounds.height + 34 - epsilon.bounds.y,
    };
    const below = layoutDetailDiagram(base, { [epsilon.id]: belowOffset });
    const movedBelow = listDetailNodes(below).find((node) => node.id === epsilon.id)!;
    const belowFlow = below.primitives.find((primitive) => primitive.kind === "flow"
      && pointsEqual(primitive.points[0], {
        x: movedBelow.bounds.x + movedBelow.bounds.width / 2,
        y: movedBelow.bounds.y,
      })
      && pointsEqual(primitive.points.at(-1)!, {
        x: sampler.bounds.x + sampler.bounds.width / 2,
        y: sampler.bounds.y + sampler.bounds.height,
      }));

    expect(belowFlow?.kind).toBe("flow");
    if (belowFlow?.kind !== "flow") return;
    expect(belowFlow.marker).not.toBe(false);

    const leftOffset = {
      x: sampler.bounds.x - epsilon.bounds.width - 48 - epsilon.bounds.x,
      y: sampler.bounds.y + sampler.bounds.height / 2 - epsilon.bounds.height / 2 - epsilon.bounds.y,
    };
    const left = layoutDetailDiagram(base, { [epsilon.id]: leftOffset });
    const movedLeft = listDetailNodes(left).find((node) => node.id === epsilon.id)!;
    const leftFlow = left.primitives.find((primitive) => primitive.kind === "flow"
      && pointsEqual(primitive.points[0], {
        x: movedLeft.bounds.x + movedLeft.bounds.width,
        y: movedLeft.bounds.y + movedLeft.bounds.height / 2,
      })
      && pointsEqual(primitive.points.at(-1)!, {
        x: sampler.bounds.x,
        y: sampler.bounds.y + sampler.bounds.height / 2,
      }));

    expect(leftFlow?.kind).toBe("flow");
    if (leftFlow?.kind !== "flow") return;
    expect(leftFlow.marker).not.toBe(false);
  });

  it("switches semantic channel ports when moved nodes change relative position", () => {
    const diagram: ModuleDetailDiagram = {
      kind: "attention",
      entryPoint: { x: 0, y: 0 },
      exitPoint: { x: 300, y: 0 },
      primitives: [
        { kind: "rect", x: 20, y: 40, width: 60, height: 40, rx: 4, label: "Q", tone: "blue" },
        { kind: "circle", cx: 220, cy: 60, radius: 20, label: "×", tone: "orange" },
        { kind: "flow", channel: "Q", points: [{ x: 80, y: 60 }, { x: 200, y: 60 }] },
      ],
    };
    const source = listDetailNodes(diagram).find((node) => node.label === "Q")!;
    const target = listDetailNodes(diagram).find((node) => node.label === "×")!;
    const moved = layoutDetailDiagram(diagram, {
      [source.id]: { x: 140, y: 100 },
    });
    const flow = moved.primitives.find((primitive) => primitive.kind === "flow")!;
    const movedSource = listDetailNodes(moved).find((node) => node.id === source.id)!;
    const movedTarget = listDetailNodes(moved).find((node) => node.id === target.id)!;

    expect(flow.points[0]).toEqual({
      x: movedSource.bounds.x + movedSource.bounds.width / 2,
      y: movedSource.bounds.y,
    });
    expect(flow.points.at(-1)).toEqual({
      x: movedTarget.bounds.x + movedTarget.bounds.width / 2,
      y: movedTarget.bounds.y + movedTarget.bounds.height,
    });
  });

  it("uses the shortest-facing ports after the Transformer source mask moves below attention", () => {
    const kind: NodeDetailKind = "transformer-encoder";
    const base = buildModuleDetail(kind, { x: 0, y: 0, ...EXPANDED_DETAIL_SIZES[kind] });
    const mask = listDetailNodes(base).find((node) => node.label === "Source padding mask")!;
    const attention = listDetailNodes(base).find((node) => node.label === "Self-attention")!;
    const moved = layoutDetailDiagram(base, {
      [mask.id]: {
        x: attention.bounds.x + attention.bounds.width / 2 - mask.bounds.width / 2 - mask.bounds.x,
        y: attention.bounds.y + attention.bounds.height + 44 - mask.bounds.y,
      },
    });
    const movedMask = listDetailNodes(moved).find((node) => node.id === mask.id)!;
    const flow = moved.primitives.find((primitive) => (
      primitive.kind === "flow" && primitive.channel === "src-padding-mask"
    ));

    expect(flow?.kind).toBe("flow");
    if (flow?.kind !== "flow") return;
    expect(flow.points[0]).toEqual({
      x: movedMask.bounds.x + movedMask.bounds.width / 2,
      y: movedMask.bounds.y,
    });
    expect(flow.points.at(-1)).toEqual({
      x: attention.bounds.x + attention.bounds.width / 2,
      y: attention.bounds.y + attention.bounds.height,
    });
    expect(flow.points).toHaveLength(2);
  });

  it("does not create isolated flow endpoints when any catalog child expands", () => {
    for (const [kind, naturalSize] of Object.entries(EXPANDED_DETAIL_SIZES) as Array<[NodeDetailKind, Pick<Bounds, "width" | "height">]>) {
      const base = buildModuleDetail(kind, { x: 0, y: 0, ...naturalSize });
      for (const candidate of listDetailNodes(base).filter((node) => node.nestedKind)) {
        const branch = { childId: candidate.id };
        const size = expandedDetailSize(kind, branch);
        const level = buildInlineDetailLayout(kind, { x: 0, y: 0, ...size }, branch, {}, "root");
        const flows = level.diagram.primitives.filter((primitive) => primitive.kind === "flow");
        const endpoints = flows.flatMap((flow) => [flow.points[0], flow.points.at(-1)!]);
        const nodeBounds = hierarchyNodeBounds(level);
        const atomicPorts = hierarchyAtomicPorts(level);
        for (const point of endpoints) {
          const attached = pointsEqual(point, level.diagram.entryPoint)
            || pointsEqual(point, level.diagram.exitPoint)
            || atomicPorts.some((port) => pointsEqual(port, point))
            || nodeBounds.some((bounds) => distanceToNodeBoundary(point, bounds) <= 12);
          const shared = endpoints.filter((candidatePoint) => pointsEqual(candidatePoint, point)).length > 1;
          expect(
            attached || shared,
            `${kind}/${candidate.label} has isolated endpoint at ${JSON.stringify(point)}`,
          ).toBe(true);
        }
      }
    }
  });

  it("keeps every fully expanded catalog tree inside its immediate surface and visible frame", () => {
    for (const kind of Object.keys(EXPANDED_DETAIL_SIZES) as NodeDetailKind[]) {
      const branch = fullyExpandedDetailTree(kind);
      const size = expandedDetailSize(kind, branch);
      for (const routingMode of ["atomic-bottom-up", "recursive"] as const) {
        const level = buildInlineDetailLayout(
          kind,
          { x: 0, y: 0, ...size },
          branch,
          {},
          `catalog-${kind}`,
          [],
          routingMode,
        );
        expectRecursiveContainment(level);
      }
    }
  }, 30_000);

  it("keeps the attention semantic group scoped to scaled dot-product operations", () => {
    const kind = "attention" as const;
    const branch = fullyExpandedDetailTree(kind);
    const size = expandedDetailSize(kind, branch);
    const natural = buildModuleDetail(kind, { x: 0, y: 0, ...EXPANDED_DETAIL_SIZES[kind] });
    const query = listDetailNodes(natural).find((node) => node.label === "Q")!;
    const queryProjection = listDetailNodes(natural).find((node) => node.label === "Linear")!;
    const naturalFrame = natural.primitives.find((primitive) => (
      primitive.kind === "rect" && primitive.variant === "frame"
    ));
    expect(naturalFrame).toMatchObject({
      frameRole: "semantic-group",
      x: 250,
      y: 72,
      width: 330,
      height: 230,
    });
    if (!naturalFrame || naturalFrame.kind !== "rect") return;
    const levelKey = "attention-semantic-group";

    for (const routingMode of ["atomic-bottom-up", "recursive"] as const) {
      const baseline = buildInlineDetailLayout(
        kind,
        { x: 0, y: 0, ...size },
        branch,
        {},
        `${levelKey}-baseline`,
        [],
        routingMode,
      );
      const level = buildInlineDetailLayout(kind, { x: 0, y: 0, ...size }, branch, {
        [levelKey]: {
          [query.id]: { x: -26, y: 0 },
          [queryProjection.id]: { x: -18, y: 8 },
        },
      }, levelKey, [], routingMode);
      const baselineFrame = baseline.diagram.primitives.find((primitive) => (
        primitive.kind === "rect" && primitive.variant === "frame"
      ));
      const frame = level.diagram.primitives.find((primitive) => (
        primitive.kind === "rect" && primitive.variant === "frame"
      ));
      expect(visibleContainmentFrameBounds(level)).toBeUndefined();
      expect(frame).toMatchObject({
        frameRole: "semantic-group",
        width: naturalFrame.width,
        height: naturalFrame.height,
      });
      expect(frame).toMatchObject(baselineFrame ?? {});
      if (!frame || frame.kind !== "rect") continue;

      const content = detailLevelContentBounds(level);
      expect(content).toEqual({
        x: level.bounds.x + 12,
        y: level.bounds.y + 62,
        width: level.bounds.width - 24,
        height: level.bounds.height - 98,
      });
      for (const child of inlineExpandedChildren(level)) {
        expectBoundsInside(child.level.bounds, content, `${routingMode}/${child.node.label} expansion in detail surface`);
      }

      const frameBounds = {
        x: frame.x,
        y: frame.y,
        width: frame.width,
        height: frame.height,
      };
      const title = level.diagram.primitives.find((primitive) => (
        primitive.kind === "text" && primitive.value === "Scaled dot-product attention / head"
      ));
      expect(title).toMatchObject({ x: frame.x + frame.width / 2, y: frame.y + 19 });
      for (const label of ["Scale", "Softmax", "weights"]) {
        const node = level.nodes.find((candidate) => candidate.label === label)!;
        expectBoundsInside(node.bounds, frameBounds, `${routingMode}/${label} in semantic group`);
      }
      const multipliers = level.nodes.filter((node) => node.label === "×");
      expect(multipliers).toHaveLength(2);
      for (const multiplier of multipliers) {
        expectBoundsInside(multiplier.bounds, frameBounds, `${routingMode}/multiply in semantic group`);
      }

      for (const label of ["Q", "K", "V"]) {
        const node = level.nodes.find((candidate) => candidate.label === label)!;
        expect(node.bounds.x + node.bounds.width, `${routingMode}/${label} remains left of semantic group`)
          .toBeLessThanOrEqual(frameBounds.x);
      }
      for (const label of ["context", "Concat h", "Output Wᴼ", "Output"]) {
        const node = level.nodes.find((candidate) => candidate.label === label)!;
        expect(node.bounds.x, `${routingMode}/${label} remains right of semantic group`)
          .toBeGreaterThanOrEqual(frameBounds.x + frameBounds.width);
      }
    }
  });

  it("exposes a second-level detail kind for recurrent branch children", () => {
    const diagram = buildModuleDetail("bidirectional-recurrent", { x: 0, y: 0, width: 800, height: 340 });
    const branches = listDetailNodes(diagram).filter((node) => node.label.includes("RNN"));
    expect(branches).toHaveLength(2);
    expect(branches.every((node) => node.nestedKind === "gru")).toBe(true);
  });

  it("does not misclassify GRU gate values as expandable networks", () => {
    const diagram = buildModuleDetail("gru", { x: 0, y: 0, width: 900, height: 380 });
    const updateGate = listDetailNodes(diagram).find((node) => node.label === "z_t")!;
    expect(updateGate.nestedKind).toBeUndefined();
  });

  it("keeps dragged children inside the editable parent content area", () => {
    const parent = { x: 100, y: 100, width: 500, height: 300 };
    const child = { x: 180, y: 190, width: 100, height: 50 };
    expect(clampDetailOffset(parent, child, { x: -500, y: -500 })).toEqual({ x: -68, y: -28 });
    expect(clampDetailOffset(parent, child, { x: 500, y: 500 })).toEqual({ x: 308, y: 124 });
  });

  it("keeps rerouted flows inside their detail level after dragging around an expanded child", () => {
    const kind: NodeDetailKind = "tensor2tensor-encoder";
    const base = buildModuleDetail(kind, { x: 0, y: 0, ...EXPANDED_DETAIL_SIZES[kind] });
    const addNorm = listDetailNodes(base).find((node) => node.label === "Add & Norm")!;
    const feedForward = listDetailNodes(base).find((node) => node.label === "Feed-forward")!;
    const branch: DetailExpansionBranch = { childId: addNorm.id };
    const size = expandedDetailSize(kind, branch);
    const bounds = { x: 40, y: 60, ...size };
    const naturalFeedForward = listDetailNodes(buildModuleDetail(kind, bounds))
      .find((node) => node.id === feedForward.id)!;
    const offset = clampDetailOffset(bounds, naturalFeedForward.bounds, { x: -220, y: -160 });
    for (const routingMode of ["atomic-bottom-up", "recursive"] as const) {
      const level = buildInlineDetailLayout(kind, bounds, branch, {
        [detailLevelKey("root")]: { [feedForward.id]: offset },
      }, "root", [], routingMode);

      for (const primitive of level.diagram.primitives) {
        if (primitive.kind !== "flow") continue;
        for (const point of primitive.points) {
          expect(point.x, `${routingMode}: ${JSON.stringify(primitive.points)}`).toBeGreaterThanOrEqual(level.bounds.x);
          expect(point.x, `${routingMode}: ${JSON.stringify(primitive.points)}`).toBeLessThanOrEqual(level.bounds.x + level.bounds.width);
          expect(point.y, `${routingMode}: ${JSON.stringify(primitive.points)}`).toBeGreaterThanOrEqual(level.bounds.y);
          expect(point.y, `${routingMode}: ${JSON.stringify(primitive.points)}`).toBeLessThanOrEqual(level.bounds.y + level.bounds.height);
        }
        const start = primitive.points[0];
        const end = primitive.points.at(-1)!;
        for (const nodeBounds of hierarchyLeafBounds(level)) {
          const ownsEndpoint = [start, end].some((point) => (
            point.x >= nodeBounds.x && point.x <= nodeBounds.x + nodeBounds.width
            && point.y >= nodeBounds.y && point.y <= nodeBounds.y + nodeBounds.height
          ));
          if (ownsEndpoint) continue;
          const crosses = primitive.points.slice(1).some((point, index) => (
            segmentCrossesBounds(primitive.points[index], point, nodeBounds)
          ));
          expect(
            crosses,
            `${routingMode}: moved route ${JSON.stringify(primitive.points)} crosses leaf ${JSON.stringify(nodeBounds)}`,
          ).toBe(false);
        }
      }
    }
  });

  it("keeps every internal route out of unrelated child nodes across all detail kinds", () => {
    for (const [kind, size] of Object.entries(EXPANDED_DETAIL_SIZES) as Array<[NodeDetailKind, Pick<Bounds, "width" | "height">]>) {
      const diagram = layoutDetailDiagram(buildModuleDetail(kind, { x: 0, y: 0, ...size }));
      const nodes = listDetailNodes(diagram);
      for (const primitive of diagram.primitives) {
        if (primitive.kind !== "flow") continue;
        const start = primitive.points[0];
        const end = primitive.points.at(-1)!;
        for (const node of nodes) {
          const endpointNode = [start, end].some((point) => (
            point.x >= node.bounds.x && point.x <= node.bounds.x + node.bounds.width
            && point.y >= node.bounds.y && point.y <= node.bounds.y + node.bounds.height
          ));
          if (endpointNode) continue;
          const crosses = primitive.points.slice(1).some((point, index) => (
            segmentCrossesBounds(primitive.points[index], point, node.bounds)
          ));
          expect(crosses, `${kind} flow crosses ${node.label}`).toBe(false);
        }
      }
    }
  });

  it("keeps bidirectional siblings and merge visible around an inline expanded branch", () => {
    const kind: NodeDetailKind = "bidirectional-recurrent";
    const base = buildModuleDetail(kind, { x: 0, y: 0, ...EXPANDED_DETAIL_SIZES[kind] });
    const forward = listDetailNodes(base).find((node) => node.label.startsWith("→"))!;
    const branch: DetailExpansionBranch = { childId: forward.id };
    const size = expandedDetailSize(kind, branch);
    const level = buildInlineDetailLayout(kind, { x: 40, y: 60, ...size }, branch, {}, "root");
    const reverse = level.nodes.find((node) => node.label.startsWith("←"));
    const merge = level.nodes.find((node) => node.label === "Concat / Σ");
    const expanded = level.expandedChild!;

    expect(reverse).toBeDefined();
    expect(merge).toBeDefined();
    expect(reverse!.bounds.y).toBeGreaterThan(expanded.node.bounds.y + expanded.node.bounds.height);
    expect(merge!.bounds.x).toBeGreaterThan(expanded.node.bounds.x + expanded.node.bounds.width);

    const flows = level.diagram.primitives.filter((primitive) => primitive.kind === "flow");
    const left = expanded.node.bounds.x;
    const atomicExit = projectedAtomicExitForModule(
      buildAtomicHierarchyProjection(level),
      expanded.level.levelKey,
    )!.point;
    expect(flows.some((flow) => flow.points.at(-1)!.x === left)).toBe(true);
    expect(flows.some((flow) => pointsEqual(flow.points[0], atomicExit))).toBe(true);
    expect(expanded.level.diagram.primitives.some((primitive) => primitive.kind === "flow"
      && primitive.points[0].x === expanded.level.diagram.entryPoint.x
      && primitive.points[0].y === expanded.level.diagram.entryPoint.y)).toBe(true);
    expect(expanded.level.diagram.primitives.some((primitive) => primitive.kind === "flow"
      && primitive.points.at(-1)!.x === expanded.level.diagram.exitPoint.x
      && primitive.points.at(-1)!.y === expanded.level.diagram.exitPoint.y)).toBe(true);
    expect(level.diagram.primitives.some((primitive) => primitive.kind === "flow"
      && primitive.points[0].x === level.diagram.entryPoint.x
      && primitive.points[0].y === level.diagram.entryPoint.y)).toBe(true);
  });

  it("bridges the intentional arrow gap when a catalog pipeline child expands", () => {
    const kind: NodeDetailKind = "vision-transformer";
    const base = buildModuleDetail(kind, { x: 0, y: 0, ...EXPANDED_DETAIL_SIZES[kind] });
    const transformer = listDetailNodes(base).find((node) => node.label === "Transformer ×L")!;
    const branch: DetailExpansionBranch = { childId: transformer.id };
    const size = expandedDetailSize(kind, branch);
    const level = buildInlineDetailLayout(kind, { x: 30, y: 40, ...size }, branch, {}, "root");
    const expanded = level.expandedChild!;
    const projection = buildAtomicHierarchyProjection(level);
    const entry = inlineAtomicEntry(expanded.level)?.point
      ?? projectedAtomicEntryForModule(projection, expanded.level.levelKey)?.point
      ?? expanded.level.diagram.entryPoint;
    const exit = projectedAtomicExitForModule(
      buildAtomicHierarchyProjection(level),
      expanded.level.levelKey,
    )!.point;
    const flows = level.diagram.primitives.filter((primitive) => primitive.kind === "flow");

    expect(flows.some((flow) => pointsEqual(flow.points.at(-1)!, entry))).toBe(true);
    expect(flows.some((flow) => pointsEqual(flow.points[0], exit))).toBe(true);
    expect(expanded.level.diagram.primitives.some((primitive) => primitive.kind === "flow"
      && pointsEqual(primitive.points[0], entry))).toBe(true);
    expect(expanded.level.diagram.primitives.some((primitive) => primitive.kind === "flow"
      && pointsEqual(primitive.points[0], exit)
      && pointsEqual(primitive.points.at(-1)!, expanded.level.diagram.exitPoint))).toBe(true);
  });

  it("preserves siblings at every level of a recursive expansion path", () => {
    const rootKind: NodeDetailKind = "dual-encoder";
    const rootBase = buildModuleDetail(rootKind, { x: 0, y: 0, ...EXPANDED_DETAIL_SIZES[rootKind] });
    const imageEncoder = listDetailNodes(rootBase).find((node) => node.nestedKind === "vision-transformer")!;
    const childKind = imageEncoder.nestedKind!;
    const childBase = buildModuleDetail(childKind, { x: 0, y: 0, ...EXPANDED_DETAIL_SIZES[childKind] });
    const transformer = listDetailNodes(childBase).find((node) => node.nestedKind)!;
    const branch: DetailExpansionBranch = {
      childId: imageEncoder.id,
      child: { childId: transformer.id },
    };
    const size = expandedDetailSize(rootKind, branch);
    const root = buildInlineDetailLayout(rootKind, { x: 0, y: 0, ...size }, branch, {}, "root");
    const nested = findInlineDetailLevel(root, [imageEncoder.id]);

    expect(root.nodes.length).toBe(listDetailNodes(rootBase).length);
    expect(nested?.nodes.length).toBe(listDetailNodes(childBase).length);
    expect(root.expandedChild?.node.id).toBe(imageEncoder.id);
    expect(nested?.expandedChild?.node.id).toBe(transformer.id);
  });

  it("lays out every expandable catalog child inside its recursively grown parent", () => {
    for (const [kind, naturalSize] of Object.entries(EXPANDED_DETAIL_SIZES) as Array<[NodeDetailKind, Pick<Bounds, "width" | "height">]>) {
      const base = buildModuleDetail(kind, { x: 0, y: 0, ...naturalSize });
      for (const candidate of listDetailNodes(base).filter((node) => node.nestedKind)) {
        const branch = { childId: candidate.id };
        const size = expandedDetailSize(kind, branch);
        const level = buildInlineDetailLayout(kind, { x: 10, y: 20, ...size }, branch, {}, "root");
        const expanded = level.expandedChild!;
        expect(level.nodes.length, `${kind}/${candidate.label} sibling count`).toBe(listDetailNodes(base).length);
        for (const node of level.nodes) {
          expect(node.bounds.x, `${kind}/${candidate.label}/${node.label} left`).toBeGreaterThanOrEqual(level.bounds.x);
          expect(node.bounds.y, `${kind}/${candidate.label}/${node.label} top`).toBeGreaterThanOrEqual(level.bounds.y);
          expect(node.bounds.x + node.bounds.width, `${kind}/${candidate.label}/${node.label} right`).toBeLessThanOrEqual(level.bounds.x + level.bounds.width);
          expect(node.bounds.y + node.bounds.height, `${kind}/${candidate.label}/${node.label} bottom`).toBeLessThanOrEqual(level.bounds.y + level.bounds.height);
        }
        level.nodes.forEach((node, index) => {
          for (const other of level.nodes.slice(index + 1)) {
            const overlaps = node.bounds.x < other.bounds.x + other.bounds.width
              && node.bounds.x + node.bounds.width > other.bounds.x
              && node.bounds.y < other.bounds.y + other.bounds.height
              && node.bounds.y + node.bounds.height > other.bounds.y;
            expect(overlaps, `${kind}/${candidate.label}: ${node.label} ${JSON.stringify(node.bounds)} overlaps ${other.label} ${JSON.stringify(other.bounds)}`).toBe(false);
          }
        });
        for (const primitive of level.diagram.primitives) {
          if (primitive.kind !== "flow") continue;
          for (const point of primitive.points) {
            expect(Number.isFinite(point.x), `${kind}/${candidate.label} finite x`).toBe(true);
            expect(Number.isFinite(point.y), `${kind}/${candidate.label} finite y`).toBe(true);
          }
          const start = primitive.points[0];
          const end = primitive.points.at(-1)!;
          for (const node of level.nodes) {
            const endpointNode = [start, end].some((point) => (
              point.x >= node.bounds.x && point.x <= node.bounds.x + node.bounds.width
              && point.y >= node.bounds.y && point.y <= node.bounds.y + node.bounds.height
            ));
            if (endpointNode) continue;
            const crosses = primitive.points.slice(1).some((point, index) => (
              segmentCrossesBounds(primitive.points[index], point, node.bounds)
            ));
            expect(
              crosses,
              `${kind}/${candidate.label} flow ${JSON.stringify(primitive.points)} crosses ${node.label} ${JSON.stringify(node.bounds)}`,
            ).toBe(false);
          }
        }
        const parentFlows = level.diagram.primitives.filter((primitive) => primitive.kind === "flow");
        const atomicExit = projectedAtomicExitForModule(
          buildAtomicHierarchyProjection(level),
          expanded.level.levelKey,
        )!.point;
        expect(
          parentFlows.some((flow) => pointsEqual(
            flow.points.at(-1)!,
            inlineAtomicEntry(expanded.level)?.point
              ?? projectedAtomicEntryForModule(
                buildAtomicHierarchyProjection(level),
                expanded.level.levelKey,
              )?.point
              ?? expanded.level.diagram.entryPoint,
          )),
          `${kind}/${candidate.label} has no incoming atomic portal attachment`,
        ).toBe(true);
        expect(
          parentFlows.some((flow) => pointsEqual(flow.points[0], atomicExit)),
          `${kind}/${candidate.label} has no outgoing descendant atomic attachment`,
        ).toBe(true);
      }
    }
  });

  it("keeps parent-level routes off expanded child borders", () => {
    for (const [kind, naturalSize] of Object.entries(EXPANDED_DETAIL_SIZES) as Array<[NodeDetailKind, Pick<Bounds, "width" | "height">]>) {
      const base = buildModuleDetail(kind, { x: 0, y: 0, ...naturalSize });
      for (const candidate of listDetailNodes(base).filter((node) => node.nestedKind)) {
        const branch = { childId: candidate.id };
        const size = expandedDetailSize(kind, branch);
        const level = buildInlineDetailLayout(kind, { x: 10, y: 20, ...size }, branch, {}, "root");
        const expandedBounds = level.expandedChild!.node.bounds;
        for (const primitive of level.diagram.primitives) {
          if (primitive.kind !== "flow") continue;
          expect(
            boundaryOverlapLength(primitive.points, expandedBounds),
            `${kind}/${candidate.label} route overlaps expanded border: ${JSON.stringify(primitive.points)}`,
          ).toBe(0);
        }
      }
    }
  });

  it("snaps every internal circle connection to a horizontal or vertical axis", () => {
    for (const [kind, size] of Object.entries(EXPANDED_DETAIL_SIZES) as Array<[NodeDetailKind, Pick<Bounds, "width" | "height">]>) {
      const diagram = layoutDetailDiagram(buildModuleDetail(kind, { x: 0, y: 0, ...size }));
      const circles = listDetailNodes(diagram).filter((node) => node.primitive.kind === "circle");
      const endpoints = diagram.primitives.flatMap((primitive) => primitive.kind === "flow"
        ? [primitive.points[0], primitive.points.at(-1)!]
        : []);
      for (const circle of circles) {
        const center = {
          x: circle.bounds.x + circle.bounds.width / 2,
          y: circle.bounds.y + circle.bounds.height / 2,
        };
        const attached = endpoints.filter((point) => {
          const onVerticalBoundary = (Math.abs(point.x - circle.bounds.x) < 0.01
            || Math.abs(point.x - circle.bounds.x - circle.bounds.width) < 0.01)
            && point.y >= circle.bounds.y && point.y <= circle.bounds.y + circle.bounds.height;
          const onHorizontalBoundary = (Math.abs(point.y - circle.bounds.y) < 0.01
            || Math.abs(point.y - circle.bounds.y - circle.bounds.height) < 0.01)
            && point.x >= circle.bounds.x && point.x <= circle.bounds.x + circle.bounds.width;
          return onVerticalBoundary || onHorizontalBoundary;
        });
        expect(attached.length, `${kind}/${circle.label} has no attached flow`).toBeGreaterThan(0);
        for (const point of attached) {
          expect(
            Math.abs(point.x - center.x) < 0.01 || Math.abs(point.y - center.y) < 0.01,
            `${kind}/${circle.label} endpoint is off-axis`,
          ).toBe(true);
        }
      }
    }
  });
});
