import { describe, expect, it } from "vitest";

import { buildAtomicHierarchyRoutingPlan } from "./atomic-hierarchy";
import {
  buildInlineDetailLayout,
  expandedDetailSize,
  inlineAtomicEntry,
  listDetailNodes,
} from "./detail-layout";
import type { DetailExpansionBranch } from "./detail-layout";
import { expandScene, expandableNodeIds } from "./expansion";
import { buildModuleDetail } from "./module-details";
import { measureScene, routeScene } from "./routing";
import { DEFAULT_OPTIONS, SCENARIOS } from "./scenarios";
import { renderSceneSvg } from "./svg-export";

const transformer = SCENARIOS.find((scene) => scene.scene_id === "tensor2tensor-transformer")!;

describe("Tensor2Tensor Transformer source-grounded scene", () => {
  it("models prepare steps, attention biases, encoder memory and shared softmax", () => {
    expect(transformer).toBeTruthy();
    expect(transformer.nodes.map((node) => node.scene_node_id)).toEqual(expect.arrayContaining([
      "t2t-target-space",
      "t2t-encoder-prep",
      "t2t-encoder-bias",
      "t2t-memory",
      "t2t-decoder-prep",
      "t2t-decoder-bias",
      "t2t-softmax",
    ]));
    expect(transformer.edges.map((edge) => edge.label)).toEqual(expect.arrayContaining([
      "space embedding",
      "encoder bias",
      "enc-dec bias",
      "decoder bias",
      "shared logits",
    ]));
    expect(transformer.nodes.find((node) => node.scene_node_id === "t2t-encoder-prep")?.secondary_label)
      .toContain("timing signal");
    expect(transformer.nodes.find((node) => node.scene_node_id === "t2t-softmax")?.secondary_label)
      .toContain("W_shared");
  });

  it("keeps both stacks expandable and routes every expanded edge cleanly", () => {
    expect(expandableNodeIds(transformer)).toEqual([
      "t2t-encoder-prep",
      "t2t-encoder",
      "t2t-decoder-prep",
      "t2t-decoder",
    ]);
    const expanded = expandScene(transformer, new Set(expandableNodeIds(transformer)));
    const metrics = measureScene(expanded, routeScene(expanded, "adaptive"));
    expect(metrics.nodeIntersections).toBe(0);
    expect(metrics.clearanceViolations).toBe(0);
    expect(metrics.endpointCongestion).toBe(0);
    expect(metrics.reverseExits).toBe(0);
  });

  it("supports the same recursive attention drill-down as the classic comparison scene", () => {
    for (const kind of ["tensor2tensor-encoder", "tensor2tensor-decoder"] as const) {
      const natural = buildModuleDetail(kind, { x: 0, y: 0, ...expandedDetailSize(kind) });
      const attention = listDetailNodes(natural).find((node) => node.nestedKind === "attention");
      expect(attention).toBeTruthy();
      const layout = buildInlineDetailLayout(kind, { x: 0, y: 0, ...expandedDetailSize(kind, { childId: attention!.id }) }, { childId: attention!.id }, {}, kind);
      expect(layout.expandedChild?.level.diagram.primitives.some((primitive) => (
        primitive.kind === "rect" && primitive.label === "Softmax"
      ))).toBe(true);
    }
  });

  it("keeps QKV fan-out continuous and routes encoder attention bias into Softmax", () => {
    const kind = "tensor2tensor-encoder" as const;
    const base = buildModuleDetail(kind, { x: 0, y: 0, ...expandedDetailSize(kind) });
    const attention = listDetailNodes(base).find((node) => node.nestedKind === "attention")!;
    const branch: DetailExpansionBranch = { childId: attention.id };
    const atomic = buildInlineDetailLayout(
      kind,
      { x: 0, y: 0, ...expandedDetailSize(kind, branch) },
      branch,
      {},
      kind,
      [],
      "atomic-bottom-up",
    );
    const child = atomic.expandedChild!.level;
    const childEntry = inlineAtomicEntry(child)!;

    expect(childEntry.point).toEqual(child.diagram.entryPoint);
    const entryBridge = child.diagram.primitives[2];
    expect(entryBridge.kind).toBe("flow");
    if (entryBridge.kind !== "flow") return;
    expect(entryBridge.points[0]).toEqual(childEntry.point);
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
    const biasFlowIndex = atomic.diagram.primitives.findIndex((primitive) => (
      primitive.kind === "flow" && primitive.channel === "src-padding-mask"
    ));
    const biasFlow = atomic.diagram.primitives[biasFlowIndex];
    expect(biasFlow.kind).toBe("flow");
    if (biasFlow.kind !== "flow") return;
    expect(biasFlow.points.at(-1)).toEqual(maskPort?.point);
    expect(biasFlow.marker).not.toBe(false);

    const plan = buildAtomicHierarchyRoutingPlan(
      { encoder: atomic },
      new Set(["encoder"]),
      new Set(["encoder"]),
    );
    expect(plan.hiddenFlowIds.has(`${child.levelKey}:flow:2`)).toBe(false);
    expect(plan.foregroundFlowIds.has(`${atomic.levelKey}:flow:${biasFlowIndex}`)).toBe(true);
  });

  it("exports the Tensor2Tensor-specific labels without invalid geometry", () => {
    const expanded = expandScene(transformer, new Set(["t2t-encoder", "t2t-decoder"]));
    const { svg } = renderSceneSvg(expanded, DEFAULT_OPTIONS);
    expect(svg).toContain("Encoder Stack ×6");
    expect(svg).toContain("Decoder Stack ×6");
    expect(svg).toContain("Shared softmax");
    expect(svg).toContain("encoder bias");
    expect(svg).toContain("conv_hidden_relu");
    expect(svg).toContain("Tensor2Tensor Encoder Layer × 6");
    expect(svg).not.toMatch(/NaN|undefined|Infinity/);
  });
});
