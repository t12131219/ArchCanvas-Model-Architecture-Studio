import { describe, expect, it } from "vitest";

import {
  buildAtomicHierarchyProjection,
  projectedAtomicExit,
  projectedAtomicExitForModule,
  projectedNestedExitBridgeIds,
  projectedSceneBoundaryPorts,
} from "./atomic-hierarchy";
import {
  buildInlineDetailLayout,
  expandedDetailSize,
  listDetailNodes,
} from "./detail-layout";
import type { DetailExpansionBranch, InlineDetailLevel } from "./detail-layout";
import { expandScene } from "./expansion";
import { buildModuleDetail, EXPANDED_DETAIL_SIZES } from "./module-details";
import { routeScene } from "./routing";
import { DEFAULT_OPTIONS, SCENARIOS } from "./scenarios";
import { renderSceneSvg } from "./svg-export";
import type { NodeDetailKind, Point } from "./types";

function pointsEqual(first: Point, second: Point): boolean {
  return Math.abs(first.x - second.x) < 0.01 && Math.abs(first.y - second.y) < 0.01;
}

function expandableChild(kind: NodeDetailKind, label: RegExp) {
  const size = EXPANDED_DETAIL_SIZES[kind];
  const diagram = buildModuleDetail(kind, { x: 0, y: 0, ...size });
  const child = listDetailNodes(diagram).find((node) => node.nestedKind && label.test(node.label));
  if (!child?.nestedKind) throw new Error(`Missing expandable ${kind}/${label}`);
  return child;
}

function deepDualEncoderBranch(): DetailExpansionBranch {
  const image = expandableChild("dual-encoder", /image/i);
  const transformer = expandableChild(image.nestedKind!, /Transformer/i);
  const linear = expandableChild(transformer.nestedKind!, /^Linear$/i);
  return {
    childId: image.id,
    child: {
      childId: transformer.id,
      child: { childId: linear.id },
    },
  };
}

function buildDeepTree(mode: "recursive" | "atomic-bottom-up" = "atomic-bottom-up") {
  const branch = deepDualEncoderBranch();
  const size = expandedDetailSize("dual-encoder", branch);
  return buildInlineDetailLayout(
    "dual-encoder",
    { x: 70, y: 90, ...size },
    branch,
    {},
    "dual-root",
    [],
    mode,
  );
}

function levels(root: InlineDetailLevel): InlineDetailLevel[] {
  const output: InlineDetailLevel[] = [];
  let current: InlineDetailLevel | undefined = root;
  while (current) {
    output.push(current);
    current = current.expandedChild?.level;
  }
  return output;
}

describe("bottom-up atomic hierarchy routing", () => {
  it("keeps the root portals on the natural data-flow axis after recursive growth", () => {
    const atomic = buildDeepTree();
    const recursive = buildDeepTree("recursive");
    const naturalHeight = EXPANDED_DETAIL_SIZES["dual-encoder"].height;

    expect(atomic.bounds.height).toBeGreaterThan(naturalHeight);
    expect(atomic.diagram.entryPoint.y).toBe(atomic.bounds.y + naturalHeight / 2);
    expect(atomic.diagram.exitPoint.y).toBe(atomic.bounds.y + naturalHeight / 2);
    expect(atomic.diagram.entryPoint.x).toBe(atomic.bounds.x);
    expect(atomic.diagram.exitPoint.x).toBe(atomic.bounds.x + atomic.bounds.width);
    expect(atomic.diagram.entryPoint.y).not.toBe(atomic.bounds.y + atomic.bounds.height / 2);
    expect(recursive.diagram.entryPoint.y).toBe(recursive.bounds.y + recursive.bounds.height / 2);
  });

  it("connects every parent level from its child's deepest atomic exit", () => {
    const root = buildDeepTree();
    const hierarchy = levels(root);
    const projection = buildAtomicHierarchyProjection(root);

    expect(hierarchy).toHaveLength(4);
    for (const parent of hierarchy.slice(0, -1)) {
      const child = parent.expandedChild!.level;
      const parentFlows = parent.diagram.primitives.filter((primitive) => primitive.kind === "flow");
      const childFlows = child.diagram.primitives.filter((primitive) => primitive.kind === "flow");
      const incoming = parentFlows.filter((flow) => pointsEqual(flow.points.at(-1)!, child.diagram.entryPoint));
      const atomicExit = projectedAtomicExitForModule(projection, child.levelKey)!;
      const outgoing = parentFlows.filter((flow) => pointsEqual(flow.points[0], atomicExit.point));
      const childEntry = childFlows.filter((flow) => pointsEqual(flow.points[0], child.diagram.entryPoint));
      const childExit = childFlows.filter((flow) => pointsEqual(flow.points.at(-1)!, child.diagram.exitPoint));

      expect(incoming.length, `${parent.levelKey} incoming`).toBeGreaterThan(0);
      expect(outgoing.length, `${parent.levelKey} outgoing`).toBeGreaterThan(0);
      expect(childEntry.length, `${child.levelKey} entry`).toBeGreaterThan(0);
      expect(childExit.length, `${child.levelKey} exit`).toBeGreaterThan(0);
      expect(incoming.every((flow) => flow.marker === false)).toBe(true);
      expect(childExit.every((flow) => flow.marker === false)).toBe(true);
    }
    expect(projectedNestedExitBridgeIds(projection).length).toBeGreaterThanOrEqual(hierarchy.length - 1);
  });

  it("builds stable atomic identities, semantic channels, and portal chains", () => {
    const first = buildAtomicHierarchyProjection(buildDeepTree());
    const second = buildAtomicHierarchyProjection(buildDeepTree());

    expect(first).toEqual(second);
    expect(first.portalChains).toHaveLength(3);
    expect(new Set(first.edges.map((edge) => edge.atomicEdgeId)).size).toBe(first.edges.length);
    expect(new Set(first.edges.map((edge) => edge.semanticChannel)).size).toBe(first.edges.length);
    for (const chain of first.portalChains) {
      const entry = first.portals.find((portal) => portal.portalId === chain.entryPortalId);
      const exit = first.portals.find((portal) => portal.portalId === chain.exitPortalId);
      expect(entry).toBeDefined();
      expect(exit).toBeDefined();
      expect(first.edges.some((edge) => edge.sourceId === chain.entryPortalId
        || edge.targetId === chain.entryPortalId)).toBe(true);
      expect(first.edges.some((edge) => edge.sourceId === chain.exitPortalId
        || edge.targetId === chain.exitPortalId)).toBe(true);
    }
  });

  it("traces a terminal expanded child through every exit portal", () => {
    const childDiagram = {
      kind: "mlp" as const,
      entryPoint: { x: 100, y: 140 },
      exitPoint: { x: 200, y: 140 },
      primitives: [
        { kind: "flow" as const, points: [{ x: 100, y: 140 }, { x: 130, y: 140 }] },
        { kind: "rect" as const, x: 130, y: 120, width: 40, height: 40, rx: 4, label: "deep output", tone: "blue" as const },
        { kind: "flow" as const, points: [{ x: 170, y: 140 }, { x: 200, y: 140 }] },
      ],
    };
    const child: InlineDetailLevel = {
      kind: "mlp",
      bounds: { x: 100, y: 100, width: 100, height: 80 },
      diagram: childDiagram,
      nodes: listDetailNodes(childDiagram),
      levelKey: "root/detail-node-1",
      routingMode: "atomic-bottom-up",
    };
    const rootDiagram = {
      kind: "autoencoder" as const,
      entryPoint: { x: 0, y: 140 },
      exitPoint: { x: 300, y: 140 },
      primitives: [
        { kind: "flow" as const, points: [{ x: 0, y: 140 }, { x: 100, y: 140 }] },
        { kind: "rect" as const, x: 100, y: 100, width: 100, height: 80, rx: 4, label: "expanded", tone: "violet" as const },
        { kind: "flow" as const, points: [{ x: 200, y: 140 }, { x: 300, y: 140 }] },
      ],
    };
    const rootNodes = listDetailNodes(rootDiagram);
    const root: InlineDetailLevel = {
      kind: "autoencoder",
      bounds: { x: 0, y: 80, width: 300, height: 120 },
      diagram: rootDiagram,
      nodes: rootNodes,
      levelKey: "root",
      routingMode: "atomic-bottom-up",
      expandedChild: { node: rootNodes[0], level: child },
    };

    const projection = buildAtomicHierarchyProjection(root);
    const atomicExit = projectedAtomicExit(projection)!;

    expect(projection.nodes.find((node) => node.atomId === atomicExit.atomId)?.label).toBe("deep output");
    expect(atomicExit.point).toEqual({ x: 170, y: 140 });
    expect(atomicExit.bridgeEdgeIds).toEqual([
      "root:flow:2",
      "root/detail-node-1:flow:2",
    ]);
  });

  it("routes outgoing edges from the terminal atom while keeping root entry portals", () => {
    const base = SCENARIOS.find((scene) => scene.scene_id === "multimodal-rl-adaptation-catalog")!;
    const dual = base.nodes.find((node) => node.detail_kind === "dual-encoder")!;
    const branch = deepDualEncoderBranch();
    const scene = expandScene(base, new Set([dual.scene_node_id]), {
      [dual.scene_node_id]: expandedDetailSize("dual-encoder", branch),
    });
    const expandedDual = scene.nodes.find((node) => node.scene_node_id === dual.scene_node_id)!;
    expect(expandedDual.bounds.y + EXPANDED_DETAIL_SIZES["dual-encoder"].height / 2)
      .toBe(dual.bounds.y + dual.bounds.height / 2);
    const tree = buildInlineDetailLayout(
      "dual-encoder",
      expandedDual.bounds,
      branch,
      {},
      dual.scene_node_id,
    );
    const projection = buildAtomicHierarchyProjection(tree);
    const atomicExit = projectedAtomicExit(projection)!;
    const ports = projectedSceneBoundaryPorts({ [dual.scene_node_id]: projection });
    const routes = routeScene(scene, "adaptive", ports);
    const incoming = routes.filter((route) => route.edge.target_scene_node_id === dual.scene_node_id);
    const outgoing = routes.filter((route) => route.edge.source_scene_node_id === dual.scene_node_id);

    expect(incoming.length).toBeGreaterThan(0);
    expect(outgoing.length).toBeGreaterThan(0);
    expect(incoming.every((route) => pointsEqual(route.points.at(-1)!, tree.diagram.entryPoint))).toBe(true);
    expect(incoming.every((route) => route.markerEnd === false)).toBe(true);
    expect(atomicExit.bridgeEdgeIds.length).toBeGreaterThan(0);
    expect(pointsEqual(atomicExit.point, tree.diagram.exitPoint)).toBe(false);
    expect(ports[dual.scene_node_id].exitIsInterior).toBe(true);
    expect(outgoing.every((route) => pointsEqual(route.points[0], atomicExit.point))).toBe(true);
    expect(outgoing.every((route) => route.foreground)).toBe(true);
    expect(outgoing.every((route) => route.markerEnd !== false)).toBe(true);
  });

  it("connects a drilled-down VAE terminal directly to the next scene module", () => {
    const base = SCENARIOS.find((scene) => scene.scene_id === "sequence-generative-catalog")!;
    const vae = base.nodes.find((node) => node.detail_kind === "variational-autoencoder")!;
    const encoder = expandableChild("variational-autoencoder", /^Encoder$/i);
    const branch: DetailExpansionBranch = { childId: encoder.id };
    const scene = expandScene(base, new Set([vae.scene_node_id]), {
      [vae.scene_node_id]: expandedDetailSize("variational-autoencoder", branch),
    });
    const expandedVae = scene.nodes.find((node) => node.scene_node_id === vae.scene_node_id)!;
    const tree = buildInlineDetailLayout(
      "variational-autoencoder",
      expandedVae.bounds,
      branch,
      {},
      vae.scene_node_id,
    );
    const projection = buildAtomicHierarchyProjection(tree);
    const atomicExit = projectedAtomicExit(projection)!;
    const expandedEncoder = tree.expandedChild!;
    const encoderAtomicExit = projectedAtomicExitForModule(projection, expandedEncoder.level.levelKey)!;
    const encoderOutgoing = tree.diagram.primitives.filter((primitive) => (
      primitive.kind === "flow"
      && pointsEqual(primitive.points[0], encoderAtomicExit.point)
      && !pointsEqual(primitive.points.at(-1)!, encoderAtomicExit.point)
    ));
    const terminal = projection.nodes.find((node) => node.atomId === atomicExit.atomId);
    const ports = projectedSceneBoundaryPorts({ [vae.scene_node_id]: projection });
    const outgoing = routeScene(scene, "adaptive", ports)
      .filter((route) => route.edge.source_scene_node_id === vae.scene_node_id);

    expect(terminal?.label).toBe("x̂");
    expect(atomicExit.side).toBe("right");
    expect(projection.nodes.find((node) => node.atomId === encoderAtomicExit.atomId)?.label).toBe("y");
    expect(encoderOutgoing).toHaveLength(2);
    expect(pointsEqual(encoderAtomicExit.point, expandedEncoder.level.diagram.exitPoint)).toBe(false);
    expect(outgoing.length).toBeGreaterThan(0);
    expect(outgoing.every((route) => pointsEqual(route.points[0], atomicExit.point))).toBe(true);

    const { svg } = renderSceneSvg(scene, DEFAULT_OPTIONS, {}, { [vae.scene_node_id]: branch });
    const hiddenBridgeIds = [
      ...atomicExit.bridgeEdgeIds,
      ...projectedNestedExitBridgeIds(projection),
    ];
    for (const bridgeEdgeId of hiddenBridgeIds) {
      expect(svg).not.toContain(`data-atomic-edge-id="${bridgeEdgeId}"`);
    }
    const externalEdge = outgoing[0].edge.scene_edge_id;
    expect(svg.indexOf(`data-edge-id="${externalEdge}"`))
      .toBeGreaterThan(svg.indexOf(`data-node-id="${vae.scene_node_id}"`));
  });
});
