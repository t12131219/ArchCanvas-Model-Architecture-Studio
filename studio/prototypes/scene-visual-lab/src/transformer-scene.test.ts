import { describe, expect, it } from "vitest";

import {
  buildInlineDetailLayout,
  detailLevelContentBounds,
  detailExpansionChildren,
  expandedDetailSize,
  fullyExpandedDetailTree,
  inlineAtomicEntry,
  inlineExpandedChildren,
  listDetailNodes,
  toggleDetailExpansionAtPath,
  visibleContainmentFrameBounds,
} from "./detail-layout";
import type { DetailExpansionBranch } from "./detail-layout";
import { buildAtomicHierarchyRoutingPlan } from "./atomic-hierarchy";
import { expandScene, expandableNodeIds } from "./expansion";
import { buildModuleDetail } from "./module-details";
import { measureScene, routeScene } from "./routing";
import { DEFAULT_OPTIONS, SCENARIOS } from "./scenarios";
import { renderSceneSvg } from "./svg-export";

const transformer = SCENARIOS.find((scene) => scene.scene_id === "classic-transformer")!;

function boundsOverlap(
  first: { x: number; y: number; width: number; height: number },
  second: { x: number; y: number; width: number; height: number },
): boolean {
  return first.x < second.x + second.width
    && first.x + first.width > second.x
    && first.y < second.y + second.height
    && first.y + first.height > second.y;
}

function assertFullyExpanded(level: ReturnType<typeof buildInlineDetailLayout>): number {
  const expanded = inlineExpandedChildren(level);
  const expandableIds = level.nodes.filter((node) => node.nestedKind).map((node) => node.id);
  expect(expanded.map((child) => child.node.id).sort()).toEqual(expandableIds.sort());
  const frame = visibleContainmentFrameBounds(level);
  if (frame) {
    for (const node of level.nodes) {
      expect(node.bounds.x, `${level.levelKey}/${node.label} left of visible frame`).toBeGreaterThanOrEqual(frame.x);
      expect(node.bounds.y, `${level.levelKey}/${node.label} above visible frame`).toBeGreaterThanOrEqual(frame.y);
      expect(
        node.bounds.x + node.bounds.width,
        `${level.levelKey}/${node.label} right of visible frame`,
      ).toBeLessThanOrEqual(frame.x + frame.width);
      expect(
        node.bounds.y + node.bounds.height,
        `${level.levelKey}/${node.label} below visible frame`,
      ).toBeLessThanOrEqual(frame.y + frame.height);
    }
  }
  for (const child of expanded) {
    expect(child.node.bounds.x).toBeGreaterThanOrEqual(level.bounds.x);
    expect(child.node.bounds.y).toBeGreaterThanOrEqual(level.bounds.y);
    expect(child.node.bounds.x + child.node.bounds.width).toBeLessThanOrEqual(level.bounds.x + level.bounds.width);
    expect(child.node.bounds.y + child.node.bounds.height).toBeLessThanOrEqual(level.bounds.y + level.bounds.height);
  }
  for (let index = 0; index < expanded.length; index += 1) {
    for (let other = index + 1; other < expanded.length; other += 1) {
      expect(boundsOverlap(expanded[index].node.bounds, expanded[other].node.bounds)).toBe(false);
    }
  }
  return expanded.reduce((count, child) => count + 1 + assertFullyExpanded(child.level), 0);
}

describe("classic Transformer source-grounded scene", () => {
  it("models the encoder-decoder paths, masks, memory and tied target weights", () => {
    expect(transformer).toBeTruthy();
    expect(transformer.nodes.map((node) => node.scene_node_id)).toEqual(expect.arrayContaining([
      "transformer-src-embed",
      "transformer-encoder",
      "transformer-memory",
      "transformer-tgt-embed",
      "transformer-decoder",
      "transformer-projection",
      "transformer-logits",
    ]));
    expect(transformer.edges.map((edge) => edge.label)).toEqual(expect.arrayContaining([
      "src_mask",
      "cross-attn K,V",
      "memory mask",
      "causal mask",
      "logits",
    ]));
    expect(transformer.nodes.find((node) => node.scene_node_id === "transformer-tgt-embed")?.secondary_label)
      .toContain("shared W");
    expect(transformer.nodes.find((node) => node.scene_node_id === "transformer-projection")?.secondary_label)
      .toContain("shared Wᵀ");
  });

  it("uses expandable source/target embeddings and encoder/decoder stacks", () => {
    expect(expandableNodeIds(transformer)).toEqual([
      "transformer-src-embed",
      "transformer-encoder",
      "transformer-tgt-embed",
      "transformer-decoder",
    ]);

    const expanded = expandScene(transformer, new Set(expandableNodeIds(transformer)));
    const metrics = measureScene(expanded, routeScene(expanded, "adaptive"));
    expect(metrics.nodeIntersections).toBe(0);
    expect(metrics.clearanceViolations).toBe(0);
    expect(metrics.endpointCongestion).toBe(0);
    expect(metrics.reverseExits).toBe(0);
  });

  it("allows recursive drill-down from both stacks into attention, Add & Norm and FFN", () => {
    for (const kind of ["transformer-encoder", "transformer-decoder"] as const) {
      const natural = buildModuleDetail(kind, { x: 0, y: 0, ...expandedDetailSize(kind) });
      const children = listDetailNodes(natural).filter((node) => node.nestedKind);
      expect(new Set(children.map((node) => node.nestedKind))).toEqual(new Set([
        "attention",
        "add-norm",
        "feedforward",
      ]));

      const attention = children.find((node) => node.nestedKind === "attention")!;
      const branch: DetailExpansionBranch = { childId: attention.id };
      const size = expandedDetailSize(kind, branch);
      const layout = buildInlineDetailLayout(kind, { x: 0, y: 0, ...size }, branch, {}, kind);
      expect(layout.expandedChild?.level.kind).toBe("attention");
      expect(layout.expandedChild?.level.diagram.primitives.some((primitive) => (
        primitive.kind === "rect" && primitive.label === "Softmax"
      ))).toBe(true);
    }
  });

  it("keeps sibling expansions open and fully expands both Transformer scenes to atomic leaves", () => {
    for (const sceneId of ["classic-transformer", "tensor2tensor-transformer"]) {
      const scene = SCENARIOS.find((candidate) => candidate.scene_id === sceneId)!;
      for (const root of scene.nodes.filter((node) => node.detail_kind)) {
        const tree = fullyExpandedDetailTree(root.detail_kind!);
        const rootChildren = detailExpansionChildren(tree);
        const expectedRootChildren = listDetailNodes(buildModuleDetail(root.detail_kind!, {
          x: 0,
          y: 0,
          ...expandedDetailSize(root.detail_kind!),
        })).filter((node) => node.nestedKind);
        expect(rootChildren.map(([id]) => id).sort()).toEqual(expectedRootChildren.map((node) => node.id).sort());

        const size = expandedDetailSize(root.detail_kind!, tree);
        for (const routingMode of ["atomic-bottom-up", "recursive"] as const) {
          const layout = buildInlineDetailLayout(
            root.detail_kind!,
            { x: 0, y: 0, ...size },
            tree,
            {},
            root.scene_node_id,
            [],
            routingMode,
          );
          const expansionCount = assertFullyExpanded(layout);
          if (routingMode === "atomic-bottom-up") {
            const projection = buildAtomicHierarchyRoutingPlan(
              { [root.scene_node_id]: layout },
              new Set(),
              new Set(),
            ).projections[root.scene_node_id];
            expect(projection.portalChains).toHaveLength(expansionCount);
          }
        }
      }
    }
  }, 20_000);

  it("expands the parent content area around a child offset retained across full expansion", () => {
    const kind = "tensor2tensor-encoder" as const;
    const tree = fullyExpandedDetailTree(kind);
    const size = expandedDetailSize(kind, tree);
    const natural = buildModuleDetail(kind, { x: 0, y: 0, ...expandedDetailSize(kind) });
    const input = listDetailNodes(natural).find((node) => node.label === "x")!;
    const levelKey = "retained-offset";

    for (const routingMode of ["atomic-bottom-up", "recursive"] as const) {
      const level = buildInlineDetailLayout(kind, { x: 0, y: 0, ...size }, tree, {
        [levelKey]: { [input.id]: { x: -26, y: -122 } },
      }, levelKey, [], routingMode);
      const moved = level.nodes.find((node) => node.id === input.id)!;
      const content = detailLevelContentBounds(level);
      expect(visibleContainmentFrameBounds(level)).toBeUndefined();
      expect(moved.bounds.x).toBeGreaterThanOrEqual(content.x);
      expect(moved.bounds.y).toBeGreaterThanOrEqual(content.y);
      expect(moved.bounds.x + moved.bounds.width).toBeLessThanOrEqual(content.x + content.width);
      expect(moved.bounds.y + moved.bounds.height).toBeLessThanOrEqual(content.y + content.height);
    }
  });

  it("toggles one sibling without collapsing the other expanded modules", () => {
    const nodes = listDetailNodes(buildModuleDetail("transformer-encoder", {
      x: 0,
      y: 0,
      ...expandedDetailSize("transformer-encoder"),
    })).filter((node) => node.nestedKind);
    const [attention, addNorm, feedforward] = [
      nodes.find((node) => node.nestedKind === "attention")!,
      nodes.find((node) => node.nestedKind === "add-norm")!,
      nodes.find((node) => node.nestedKind === "feedforward")!,
    ];
    let tree: DetailExpansionBranch | undefined;
    tree = toggleDetailExpansionAtPath(tree, [], attention.id);
    tree = toggleDetailExpansionAtPath(tree, [], addNorm.id);
    tree = toggleDetailExpansionAtPath(tree, [], feedforward.id);
    expect(detailExpansionChildren(tree).map(([id]) => id)).toEqual([
      attention.id,
      addNorm.id,
      feedforward.id,
    ]);

    tree = toggleDetailExpansionAtPath(tree, [], addNorm.id);
    expect(detailExpansionChildren(tree).map(([id]) => id)).toEqual([attention.id, feedforward.id]);
  });

  it("renders recursively expanded attention without a redundant parent layer frame", () => {
    const encoder = transformer.nodes.find((node) => node.scene_node_id === "transformer-encoder")!;
    const base = buildModuleDetail("transformer-encoder", {
      x: 0,
      y: 0,
      ...expandedDetailSize("transformer-encoder"),
    });
    const attention = listDetailNodes(base).find((node) => node.nestedKind === "attention")!;
    const branch: DetailExpansionBranch = { childId: attention.id };
    const expanded = expandScene(transformer, new Set([encoder.scene_node_id]), {
      [encoder.scene_node_id]: expandedDetailSize("transformer-encoder", branch),
    });
    const { svg } = renderSceneSvg(expanded, DEFAULT_OPTIONS, {}, {
      [encoder.scene_node_id]: branch,
    });

    const nestedSurface = svg.indexOf("nested-inline-surface");
    const nestedContent = svg.indexOf("Scaled dot-product attention / head");
    expect(svg.match(/<g class="[^"]*detail-frame/g)).toHaveLength(1);
    expect(nestedSurface).toBeGreaterThan(-1);
    expect(nestedContent).toBeGreaterThan(nestedSurface);
  });

  it("removes redundant Transformer layer frames while retaining their configuration labels", () => {
    const expectations = [
      ["transformer-encoder", "EncoderLayer"],
      ["transformer-decoder", "DecoderLayer"],
      ["tensor2tensor-encoder", "EncoderLayer"],
      ["tensor2tensor-decoder", "DecoderLayer"],
    ] as const;
    for (const [kind, label] of expectations) {
      const diagram = buildModuleDetail(kind, { x: 0, y: 0, ...expandedDetailSize(kind) });
      expect(diagram.primitives.some((primitive) => (
        primitive.kind === "rect" && primitive.variant === "frame"
      )), kind).toBe(false);
      expect(diagram.primitives.some((primitive) => (
        primitive.kind === "text" && primitive.value.includes(label) && primitive.anchor === "start"
      )), kind).toBe(true);
    }

    for (const kind of ["attention", "recurrent"] as const) {
      const diagram = buildModuleDetail(kind, { x: 0, y: 0, ...expandedDetailSize(kind) });
      expect(diagram.primitives.some((primitive) => (
        primitive.kind === "rect"
          && primitive.variant === "frame"
          && primitive.frameRole === "semantic-group"
      )), kind).toBe(true);
    }
  });

  it("keeps attention fan-out continuous and connects masks to its internal semantic port", () => {
    const base = buildModuleDetail("transformer-encoder", {
      x: 0,
      y: 0,
      ...expandedDetailSize("transformer-encoder"),
    });
    const attention = listDetailNodes(base).find((node) => node.nestedKind === "attention")!;
    const branch: DetailExpansionBranch = { childId: attention.id };
    const size = expandedDetailSize("transformer-encoder", branch);
    const atomic = buildInlineDetailLayout(
      "transformer-encoder",
      { x: 0, y: 0, ...size },
      branch,
      {},
      "transformer-encoder",
      [],
      "atomic-bottom-up",
    );
    expect(visibleContainmentFrameBounds(atomic)).toBeUndefined();
    const content = detailLevelContentBounds(atomic);
    for (const node of atomic.nodes) {
      expect(node.bounds.x, `${node.label} left`).toBeGreaterThanOrEqual(content.x);
      expect(node.bounds.y, `${node.label} top`).toBeGreaterThanOrEqual(content.y);
      expect(node.bounds.x + node.bounds.width, `${node.label} right`).toBeLessThanOrEqual(content.x + content.width);
      expect(node.bounds.y + node.bounds.height, `${node.label} bottom ${JSON.stringify({ node: node.bounds, content })}`).toBeLessThanOrEqual(content.y + content.height);
    }

    const child = atomic.expandedChild!.level;
    const childEntry = inlineAtomicEntry(child)!;
    expect(childEntry.point).toEqual(child.diagram.entryPoint);
    expect(atomic.diagram.primitives.some((primitive) => (
      primitive.kind === "flow" && primitive.points.at(-1)
        && Math.abs(primitive.points.at(-1)!.x - childEntry.point.x) < 0.01
        && Math.abs(primitive.points.at(-1)!.y - childEntry.point.y) < 0.01
    ))).toBe(true);

    const entryBridge = child.diagram.primitives[2];
    expect(entryBridge.kind).toBe("flow");
    if (entryBridge.kind !== "flow") return;
    expect(entryBridge.points[0]).toEqual(child.diagram.entryPoint);
    const fanOutPoint = entryBridge.points.at(-1)!;
    expect(child.diagram.primitives.filter((primitive) => (
      primitive.kind === "flow"
        && primitive.points[0].x === fanOutPoint.x
        && primitive.points[0].y === fanOutPoint.y
    ))).toHaveLength(3);

    const softmax = child.nodes.find((node) => node.label === "Softmax")!;
    const maskPort = child.diagram.semanticInputPorts?.mask;
    expect(maskPort).toEqual({
      point: {
        x: softmax.bounds.x + softmax.bounds.width / 2,
        y: softmax.bounds.y,
      },
      side: "top",
    });
    const maskFlowIndex = atomic.diagram.primitives.findIndex((primitive) => (
      primitive.kind === "flow" && primitive.channel === "src-padding-mask"
    ));
    const maskFlow = atomic.diagram.primitives[maskFlowIndex];
    expect(maskFlow.kind).toBe("flow");
    if (maskFlow.kind !== "flow") return;
    expect(maskFlow.points.at(-1)).toEqual(maskPort?.point);
    expect(maskFlow.marker).not.toBe(false);

    const plan = buildAtomicHierarchyRoutingPlan(
      { encoder: atomic },
      new Set(["encoder"]),
      new Set(["encoder"]),
    );
    expect(plan.hiddenFlowIds.has(`${child.levelKey}:flow:2`)).toBe(false);
    expect(plan.foregroundFlowIds.has(`${atomic.levelKey}:flow:${maskFlowIndex}`)).toBe(true);
  });

  it("keeps child-frame entry and bridge visible in recursive routing mode", () => {
    const base = buildModuleDetail("transformer-encoder", {
      x: 0,
      y: 0,
      ...expandedDetailSize("transformer-encoder"),
    });
    const attention = listDetailNodes(base).find((node) => node.nestedKind === "attention")!;
    const branch: DetailExpansionBranch = { childId: attention.id };
    const size = expandedDetailSize("transformer-encoder", branch);
    const recursive = buildInlineDetailLayout(
      "transformer-encoder",
      { x: 0, y: 0, ...size },
      branch,
      {},
      "transformer-encoder",
      [],
      "recursive",
    );
    const child = recursive.expandedChild!.level;
    expect(recursive.diagram.primitives.some((primitive) => (
      primitive.kind === "flow" && primitive.points.at(-1)
        && Math.abs(primitive.points.at(-1)!.x - child.diagram.entryPoint.x) < 0.01
        && Math.abs(primitive.points.at(-1)!.y - child.diagram.entryPoint.y) < 0.01
    ))).toBe(true);
  });

  it("exports the source-specific structure without invalid geometry", () => {
    const decoder = transformer.nodes.find((node) => node.scene_node_id === "transformer-decoder")!;
    const expanded = expandScene(transformer, new Set([decoder.scene_node_id]));
    const { svg } = renderSceneSvg(expanded, DEFAULT_OPTIONS);

    expect(svg).toContain("DecoderLayer × 6");
    expect(svg).toContain("Masked self-attn");
    expect(svg).toContain("Cross-attention");
    expect(svg).toContain("Target pad ∧ causal mask");
    expect(svg).toContain("shared Wᵀ");
    expect(svg).not.toMatch(/NaN|undefined|Infinity/);
  });
});
