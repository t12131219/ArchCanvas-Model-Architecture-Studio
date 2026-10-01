import { describe, expect, it } from "vitest";

import { buildAtomicHierarchyRoutingPlan } from "./atomic-hierarchy";
import {
  buildInlineDetailLayout,
  expandedDetailSize,
  fullyExpandedDetailTree,
  inlineExpandedChildren,
  listDetailNodes,
} from "./detail-layout";
import { expandScene } from "./expansion";
import { buildModuleDetail, EXPANDED_DETAIL_SIZES } from "./module-details";
import { measureScene, routeScene } from "./routing";
import { SCENARIOS } from "./scenarios";
import type { LabNode, LabScene, NodeDetailKind } from "./types";

const paperScenes = SCENARIOS.filter((scene) => scene.layout_profile === "paper");
const paperStackKinds = new Set<NodeDetailKind>([
  "paper-transformer-encoder",
  "paper-transformer-decoder",
  "paper-tensor2tensor-encoder",
  "paper-tensor2tensor-decoder",
]);

function paperStackNodes(scene: LabScene): LabNode[] {
  return scene.nodes.filter((node) => node.detail_kind && paperStackKinds.has(node.detail_kind));
}

function nodesInLane(scene: LabScene, lane: string): LabNode[] {
  return scene.nodes.filter((node) => node.layout_lane === lane);
}

function laneExtent(scene: LabScene, lane: string): { left: number; right: number } {
  const nodes = nodesInLane(scene, lane);
  return {
    left: Math.min(...nodes.map((node) => node.bounds.x)),
    right: Math.max(...nodes.map((node) => node.bounds.x + node.bounds.width)),
  };
}

describe("paper-level Transformer scenes", () => {
  it("adds a source-faithful paper view for both Transformer implementations", () => {
    expect(paperScenes.map((scene) => scene.scene_id)).toEqual([
      "paper-classic-transformer",
      "paper-tensor2tensor-transformer",
    ]);
    for (const scene of paperScenes) {
      expect(nodesInLane(scene, "encoder").length).toBeGreaterThan(4);
      expect(nodesInLane(scene, "decoder").length).toBeGreaterThan(4);
      expect(laneExtent(scene, "encoder").right).toBeLessThan(laneExtent(scene, "decoder").left);
      expect(scene.nodes.filter((node) => node.detail_kind).length).toBe(4);
      expect(paperStackNodes(scene)).toHaveLength(2);
    }
  });

  it("preserves the source-backed top-level expansion hierarchy", () => {
    const paperKindBySourceKind: Partial<Record<NodeDetailKind, NodeDetailKind>> = {
      "sinusoidal-embedding": "paper-sinusoidal-embedding",
      "tensor-transform": "paper-tensor-transform",
      "transformer-encoder": "paper-transformer-encoder",
      "transformer-decoder": "paper-transformer-decoder",
      "tensor2tensor-encoder": "paper-tensor2tensor-encoder",
      "tensor2tensor-decoder": "paper-tensor2tensor-decoder",
    };
    const pairs = [
      ["classic-transformer", "paper-classic-transformer"],
      ["tensor2tensor-transformer", "paper-tensor2tensor-transformer"],
    ] as const;
    for (const [sourceId, paperId] of pairs) {
      const source = SCENARIOS.find((scene) => scene.scene_id === sourceId)!;
      const paper = SCENARIOS.find((scene) => scene.scene_id === paperId)!;
      expect(paper.nodes.filter((node) => node.detail_kind).map((node) => node.detail_kind)).toEqual(
        source.nodes.filter((node) => node.detail_kind).map((node) => (
          paperKindBySourceKind[node.detail_kind!] ?? node.detail_kind
        )),
      );
    }
  });

  it("keeps source-backed recursive expansion under paper Attention, FFN and Add & Norm", () => {
    const correspondingKinds = [
      ["attention", "paper-attention"],
      ["feedforward", "paper-feedforward"],
      ["add-norm", "paper-add-norm"],
    ] as const;
    for (const [sourceKind, paperKind] of correspondingKinds) {
      const sourceNodes = listDetailNodes(buildModuleDetail(sourceKind, {
        x: 0,
        y: 0,
        ...EXPANDED_DETAIL_SIZES[sourceKind],
      }));
      const paperNodes = listDetailNodes(buildModuleDetail(paperKind, {
        x: 0,
        y: 0,
        ...EXPANDED_DETAIL_SIZES[paperKind],
      }));
      expect(paperNodes.filter((node) => node.nestedKind).map((node) => [node.label, node.nestedKind])).toEqual(
        sourceNodes.filter((node) => node.nestedKind).map((node) => [node.label, node.nestedKind]),
      );
    }
  });

  it("expands every source-backed paper root instead of only the Encoder and Decoder stacks", () => {
    for (const base of paperScenes) {
      const expandable = base.nodes.filter((node) => node.detail_kind);
      const sizes = Object.fromEntries(expandable.map((node) => [
        node.scene_node_id,
        expandedDetailSize(node.detail_kind!, fullyExpandedDetailTree(node.detail_kind!)),
      ]));
      const expanded = expandScene(base, new Set(expandable.map((node) => node.scene_node_id)), sizes);
      expect(expanded.nodes.filter((node) => node.detail_expanded).map((node) => node.scene_node_id)).toEqual(
        expandable.map((node) => node.scene_node_id),
      );
      expect(laneExtent(expanded, "encoder").right).toBeLessThan(laneExtent(expanded, "decoder").left);
    }
  });

  it("keeps each expanded stack bottom-anchored and preserves lane order", () => {
    for (const base of paperScenes) {
      const stackIds = base.nodes
        .filter((node) => node.detail_kind && paperStackKinds.has(node.detail_kind))
        .map((node) => node.scene_node_id);
      const expanded = expandScene(base, new Set(stackIds));
      for (const stackId of stackIds) {
        const before = base.nodes.find((node) => node.scene_node_id === stackId)!;
        const after = expanded.nodes.find((node) => node.scene_node_id === stackId)!;
        const baseAnchor = nodesInLane(base, before.layout_lane!)[0];
        const expandedAnchor = expanded.nodes.find((node) => node.scene_node_id === baseAnchor.scene_node_id)!;
        const beforeGap = before.bounds.y + before.bounds.height - (baseAnchor.bounds.y + baseAnchor.bounds.height);
        const afterGap = after.bounds.y + after.bounds.height - (expandedAnchor.bounds.y + expandedAnchor.bounds.height);
        expect(afterGap).toBeCloseTo(beforeGap, 6);
      }
      expect(laneExtent(expanded, "encoder").right).toBeLessThan(laneExtent(expanded, "decoder").left);
    }
  });

  it("uses bottom entry, top exit, and the root surface as the containment frame", () => {
    const rootKinds: NodeDetailKind[] = [
      "paper-transformer-encoder",
      "paper-transformer-decoder",
      "paper-tensor2tensor-encoder",
      "paper-tensor2tensor-decoder",
      "paper-sinusoidal-embedding",
      "paper-tensor-transform",
    ];
    for (const kind of rootKinds) {
      const bounds = { x: 40, y: 60, ...EXPANDED_DETAIL_SIZES[kind] };
      const detail = buildModuleDetail(kind, bounds);
      expect(detail.entryPoint).toEqual({ x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height });
      expect(detail.exitPoint).toEqual({ x: bounds.x + bounds.width / 2, y: bounds.y });
      expect(detail.primitives.some((primitive) => primitive.kind === "rect" && primitive.variant === "frame"
        && (primitive.frameRole ?? "containment") === "containment")).toBe(false);
    }
  });

  it("fully expands every paper stack without losing atomic boundary routing", () => {
    for (const base of paperScenes) {
      const rootNodes = paperStackNodes(base);
      const branches = Object.fromEntries(rootNodes.map((node) => [
        node.scene_node_id,
        fullyExpandedDetailTree(node.detail_kind!),
      ]));
      const sizes = Object.fromEntries(rootNodes.map((node) => [
        node.scene_node_id,
        expandedDetailSize(node.detail_kind!, branches[node.scene_node_id]),
      ]));
      const expanded = expandScene(base, new Set(rootNodes.map((node) => node.scene_node_id)), sizes);
      const detailTrees = Object.fromEntries(rootNodes.map((rootNode) => {
        const node = expanded.nodes.find((candidate) => candidate.scene_node_id === rootNode.scene_node_id)!;
        return [node.scene_node_id, buildInlineDetailLayout(
          node.detail_kind!,
          node.bounds,
          branches[node.scene_node_id],
          {},
          node.scene_node_id,
        )];
      }));
      expect(Object.values(detailTrees).every((tree) => inlineExpandedChildren(tree).length >= 3)).toBe(true);
      const plan = buildAtomicHierarchyRoutingPlan(
        detailTrees,
        new Set(expanded.edges.map((edge) => edge.target_scene_node_id)),
        new Set(expanded.edges.map((edge) => edge.source_scene_node_id)),
      );
      expect(Object.keys(plan.boundaryPorts)).toHaveLength(rootNodes.length);
      expect(Object.values(plan.boundaryPorts).every((ports) => (
        Number.isFinite(ports.entry.x) && Number.isFinite(ports.entry.y)
        && Number.isFinite(ports.exit.x) && Number.isFinite(ports.exit.y)
      ))).toBe(true);
      const metrics = measureScene(expanded, routeScene(expanded, "adaptive", plan.boundaryPorts));
      expect(metrics.crossings, base.scene_id).toBe(0);
      expect(metrics.nodeIntersections, base.scene_id).toBe(0);
      expect(metrics.clearanceViolations, base.scene_id).toBe(0);
      expect(metrics.endpointCongestion, base.scene_id).toBe(0);
      expect(metrics.reverseExits, base.scene_id).toBe(0);
    }
  }, 20_000);

  it("routes the collapsed paper compositions without node crossings", () => {
    for (const scene of paperScenes) {
      const metrics = measureScene(scene, routeScene(scene, "adaptive"));
      expect(metrics.nodeIntersections, scene.scene_id).toBe(0);
      expect(metrics.reverseExits, scene.scene_id).toBe(0);
    }
  });

  it("routes expanded paper inputs to distinct structural and semantic ports", () => {
    for (const base of paperScenes) {
      const rootNodes = base.nodes.filter((node) => node.detail_kind);
      const expanded = expandScene(base, new Set(rootNodes.map((node) => node.scene_node_id)));
      const detailTrees = Object.fromEntries(rootNodes.map((rootNode) => {
        const node = expanded.nodes.find((candidate) => candidate.scene_node_id === rootNode.scene_node_id)!;
        return [node.scene_node_id, buildInlineDetailLayout(
          node.detail_kind!,
          node.bounds,
          undefined,
          {},
          node.scene_node_id,
        )];
      }));
      const plan = buildAtomicHierarchyRoutingPlan(
        detailTrees,
        new Set(expanded.edges.map((edge) => edge.target_scene_node_id)),
        new Set(expanded.edges.map((edge) => edge.source_scene_node_id)),
      );
      const routes = routeScene(expanded, "adaptive", plan.boundaryPorts);

      for (const edge of expanded.edges.filter((candidate) => candidate.target_port_role)) {
        const targetPorts = plan.boundaryPorts[edge.target_scene_node_id];
        const semanticPort = targetPorts.semanticInputs?.[edge.target_port_role!];
        const route = routes.find((candidate) => candidate.edge.scene_edge_id === edge.scene_edge_id)!;
        expect(semanticPort, `${base.scene_id}/${edge.scene_edge_id}`).toBeDefined();
        expect(route.points.at(-1), `${base.scene_id}/${edge.scene_edge_id}`).toEqual(semanticPort?.point);
        expect(route.targetSide, `${base.scene_id}/${edge.scene_edge_id}`).toBe(semanticPort?.side);
        expect(route.markerEnd, `${base.scene_id}/${edge.scene_edge_id}`).not.toBe(false);
        expect(route.foreground, `${base.scene_id}/${edge.scene_edge_id}`).toBe(true);
      }

      for (const edge of expanded.edges.filter((candidate) => (
        !candidate.target_port_role && plan.boundaryPorts[candidate.target_scene_node_id]
      ))) {
        const route = routes.find((candidate) => candidate.edge.scene_edge_id === edge.scene_edge_id)!;
        expect(route.points.at(-1), `${base.scene_id}/${edge.scene_edge_id}`).toEqual(
          plan.boundaryPorts[edge.target_scene_node_id].entry,
        );
        expect(route.markerEnd, `${base.scene_id}/${edge.scene_edge_id}`).toBe(false);
      }
      expect(measureScene(expanded, routes).endpointCongestion, base.scene_id).toBe(0);
    }
  });
});
