import { describe, expect, it } from "vitest";

import { buildAtomicHierarchyRoutingPlan } from "./atomic-hierarchy";
import { expandScene, expandableNodeIds } from "./expansion";
import { buildInlineDetailLayout, expandedDetailSize, fullyExpandedDetailTree, listDetailNodes } from "./detail-layout";
import type { DetailExpansionBranch } from "./detail-layout";
import { buildModuleDetail, EXPANDED_DETAIL_SIZES } from "./module-details";
import { measureScene, routeScene } from "./routing";
import { DEFAULT_OPTIONS, SCENARIOS } from "./scenarios";
import { renderSceneSvg } from "./svg-export";

const baseScene = SCENARIOS.find((scene) => scene.scene_id === "parent-child-expansion")!;

describe("parent and child module expansion", () => {
  it("expands deterministically and restores the base coordinates on collapse", () => {
    const attention = baseScene.nodes.find((node) => node.detail_kind === "attention")!;
    const downstream = baseScene.nodes.find((node) => node.scene_node_id === "expand-add-norm")!;
    const first = expandScene(baseScene, new Set([attention.scene_node_id]));
    const second = expandScene(baseScene, new Set([attention.scene_node_id]));
    const expandedAttention = first.nodes.find((node) => node.scene_node_id === attention.scene_node_id)!;
    const shiftedDownstream = first.nodes.find((node) => node.scene_node_id === downstream.scene_node_id)!;
    const collapsed = expandScene(baseScene, new Set());

    expect(first).toEqual(second);
    expect(expandedAttention.detail_expanded).toBe(true);
    expect(expandedAttention.bounds).toMatchObject({ width: 900, height: 380 });
    expect(shiftedDownstream.bounds.x - downstream.bounds.x).toBe(900 - attention.bounds.width);
    expect(collapsed.nodes.map((node) => node.bounds)).toEqual(baseScene.nodes.map((node) => node.bounds));
    expect(collapsed.paper_width).toBe(baseScene.paper_width);
  });

  it("preserves an expanded node above the legacy paper boundary", () => {
    const attention = baseScene.nodes.find((node) => node.detail_kind === "attention")!;
    const moved = {
      ...baseScene,
      nodes: baseScene.nodes.map((node) => node.scene_node_id === attention.scene_node_id
        ? { ...node, bounds: { ...node.bounds, y: -240 } }
        : node),
    };
    const expanded = expandScene(moved, new Set([attention.scene_node_id]));
    const expandedAttention = expanded.nodes.find((node) => node.scene_node_id === attention.scene_node_id)!;

    expect(expandedAttention.bounds.y).toBeLessThan(0);
    expect(expandedAttention.bounds.y).toBe(-240 + attention.bounds.height / 2 - EXPANDED_DETAIL_SIZES.attention.height / 2);
  });

  it("uses a single exact boundary entry and exit for every detail diagram", () => {
    for (const [kind, size] of Object.entries(EXPANDED_DETAIL_SIZES)) {
      const bounds = { x: 120, y: 80, ...size };
      const diagram = buildModuleDetail(kind as keyof typeof EXPANDED_DETAIL_SIZES, bounds);
      const flows = diagram.primitives.filter((primitive) => primitive.kind === "flow");
      const paperDetail = kind.startsWith("paper-");

      expect(diagram.entryPoint).toEqual(paperDetail
        ? { x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height }
        : { x: bounds.x, y: bounds.y + bounds.height / 2 });
      expect(diagram.exitPoint).toEqual(paperDetail
        ? { x: bounds.x + bounds.width / 2, y: bounds.y }
        : { x: bounds.x + bounds.width, y: bounds.y + bounds.height / 2 });
      expect(flows.some((primitive) => primitive.points[0].x === diagram.entryPoint.x
        && primitive.points[0].y === diagram.entryPoint.y)).toBe(true);
      expect(flows.some((primitive) => primitive.points.at(-1)!.x === diagram.exitPoint.x
        && primitive.points.at(-1)!.y === diagram.exitPoint.y)).toBe(true);
      if (!paperDetail) {
        expect(flows.every((primitive) => primitive.points.at(-1)!.x >= primitive.points[0].x)).toBe(true);
      }
    }
  });

  it("connects adaptive external routes to the same detail boundary ports", () => {
    for (const base of SCENARIOS.filter((scene) => expandableNodeIds(scene).length)) {
      const scene = expandScene(base, new Set(expandableNodeIds(base)));
      const nodes = new Map(scene.nodes.map((node) => [node.scene_node_id, node]));
      const paperDetailTrees = base.layout_profile === "paper"
        ? Object.fromEntries(scene.nodes.flatMap((node) => (
          node.detail_expanded && node.detail_kind
            ? [[node.scene_node_id, buildInlineDetailLayout(node.detail_kind, node.bounds, undefined, {}, node.scene_node_id)]]
            : []
        )))
        : undefined;
      const paperPlan = paperDetailTrees ? buildAtomicHierarchyRoutingPlan(
        paperDetailTrees,
        new Set(scene.edges.map((edge) => edge.target_scene_node_id)),
        new Set(scene.edges.map((edge) => edge.source_scene_node_id)),
      ) : undefined;
      for (const route of routeScene(scene, "adaptive", paperPlan?.boundaryPorts)) {
        const source = nodes.get(route.edge.source_scene_node_id)!;
        const target = nodes.get(route.edge.target_scene_node_id)!;
        if (source.detail_expanded && source.detail_kind) {
          const expected = paperPlan?.boundaryPorts[source.scene_node_id];
          expect(route.sourceSide).toBe(expected?.exitSide ?? "right");
          expect(route.points[0]).toEqual(expected?.exit ?? buildModuleDetail(source.detail_kind, source.bounds).exitPoint);
        }
        if (target.detail_expanded && target.detail_kind) {
          const expected = paperPlan?.boundaryPorts[target.scene_node_id];
          const semantic = route.edge.target_port_role
            ? expected?.semanticInputs?.[route.edge.target_port_role]
            : undefined;
          expect(route.targetSide).toBe(semantic?.side ?? expected?.entrySide ?? "left");
          expect(route.points.at(-1)).toEqual(
            semantic?.point ?? expected?.entry ?? buildModuleDetail(target.detail_kind, target.bounds).entryPoint,
          );
        }
      }
    }
  });

  it("branches the Add & Norm entry into both function and residual inputs", () => {
    const size = EXPANDED_DETAIL_SIZES["add-norm"];
    const bounds = { x: 100, y: 50, ...size };
    const diagram = buildModuleDetail("add-norm", bounds);
    const flows = diagram.primitives.filter((primitive) => primitive.kind === "flow");
    const junction = { x: bounds.x + 28, y: bounds.y + bounds.height / 2 };
    const branches = flows.filter((primitive) => primitive.points[0].x === junction.x
      && primitive.points[0].y === junction.y);

    expect(branches).toHaveLength(2);
    expect(new Set(branches.map((primitive) => primitive.points.at(-1)!.y)).size).toBe(2);
  });

  it("keeps every supplied expansion snapshot clear of external routing failures", () => {
    for (const expandableScene of SCENARIOS.filter((scene) => expandableNodeIds(scene).length)) {
      const expansionSets = [
        ...expandableNodeIds(expandableScene).map((nodeId) => new Set([nodeId])),
        new Set(expandableNodeIds(expandableScene)),
      ];
      for (const expandedIds of expansionSets) {
        const scene = expandScene(expandableScene, expandedIds);
        const paperDetailTrees = expandableScene.layout_profile === "paper"
          ? Object.fromEntries(scene.nodes.flatMap((node) => (
            node.detail_expanded && node.detail_kind
              ? [[node.scene_node_id, buildInlineDetailLayout(node.detail_kind, node.bounds, undefined, {}, node.scene_node_id)]]
              : []
          )))
          : undefined;
        const paperPlan = paperDetailTrees ? buildAtomicHierarchyRoutingPlan(
          paperDetailTrees,
          new Set(scene.edges.map((edge) => edge.target_scene_node_id)),
          new Set(scene.edges.map((edge) => edge.source_scene_node_id)),
        ) : undefined;
        const routes = routeScene(scene, "adaptive", paperPlan?.boundaryPorts);
        const metrics = measureScene(scene, routes);

        expect(routes).toHaveLength(scene.edges.length);
        const caseLabel = `${expandableScene.scene_id} expanded=${[...expandedIds].join(",")}`;
        if (expandableScene.layout_profile === "paper") {
          expect(metrics.crossings, caseLabel).toBe(0);
        }
        expect(metrics.nodeIntersections, caseLabel).toBe(0);
        expect(metrics.clearanceViolations, caseLabel).toBe(0);
        expect(metrics.endpointCongestion, caseLabel).toBe(0);
        expect(metrics.reverseExits, caseLabel).toBe(0);
      }
    }
  });

  it("moves lower lanes below recursively expanded Transformer modules", () => {
    for (const sceneId of ["classic-transformer", "tensor2tensor-transformer"]) {
      const base = SCENARIOS.find((scene) => scene.scene_id === sceneId)!;
      const expandedIds = new Set(expandableNodeIds(base));
      const trees = Object.fromEntries(base.nodes.flatMap((node) => node.detail_kind
        ? [[node.scene_node_id, fullyExpandedDetailTree(node.detail_kind)]]
        : []));
      const sizes = Object.fromEntries(base.nodes.flatMap((node) => node.detail_kind
        ? [[node.scene_node_id, expandedDetailSize(node.detail_kind, trees[node.scene_node_id])]]
        : []));
      const scene = expandScene(base, expandedIds, sizes);
      const metrics = measureScene(scene, routeScene(scene, "adaptive"));

      expect(metrics.nodeIntersections, sceneId).toBe(0);
      expect(metrics.clearanceViolations, sceneId).toBe(0);
      expect(metrics.endpointCongestion, sceneId).toBe(0);
    }
  });

  it("renders the full attention flow into static SVG output", () => {
    const attention = baseScene.nodes.find((node) => node.detail_kind === "attention")!;
    const scene = expandScene(baseScene, new Set([attention.scene_node_id]));
    const { svg } = renderSceneSvg(scene, DEFAULT_OPTIONS);

    expect(svg).toContain("Q / K / V projections");
    expect(svg).toContain("Scaled dot-product attention / head");
    expect(svg).toContain("Softmax");
    expect(svg).toContain("Output Wᴼ");
    expect(svg).toContain("internal-arrow");
    expect(svg).not.toContain("undefined");
  });

  it("exports recursive inline detail without dropping siblings", () => {
    const catalog = SCENARIOS.find((scene) => scene.scene_id === "sequence-generative-catalog")!;
    const node = catalog.nodes.find((item) => item.detail_kind === "bidirectional-recurrent")!;
    const natural = EXPANDED_DETAIL_SIZES[node.detail_kind!];
    const base = buildModuleDetail(node.detail_kind!, { x: 0, y: 0, ...natural });
    const forward = listDetailNodes(base).find((child) => child.label.startsWith("→"))!;
    const branch: DetailExpansionBranch = { childId: forward.id };
    const scene = expandScene(catalog, new Set([node.scene_node_id]), {
      [node.scene_node_id]: expandedDetailSize(node.detail_kind!, branch),
    });
    const { svg } = renderSceneSvg(scene, DEFAULT_OPTIONS, {}, { [node.scene_node_id]: branch });

    expect(svg).toContain("nested-inline-detail");
    expect(svg).toContain("← RNN / LSTM / GRU");
    expect(svg).toContain("Concat / Σ");
    expect(svg).toContain("update σ");
    expect(svg).not.toMatch(/NaN|undefined|Infinity/);
  });
});
