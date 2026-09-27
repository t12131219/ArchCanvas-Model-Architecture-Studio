import { describe, expect, it } from "vitest";

import { buildKernelRenderScene } from "./layout";
import type { KernelDocument, KernelNode, KernelRelation, KernelVisualState, NodeDetailKind } from "./types";

function fixture(expandedKinds: NodeDetailKind[]): { document: KernelDocument; visualState: KernelVisualState } {
  const specs: Array<[string, number, NodeDetailKind | undefined]> = [
    ["input", 32, undefined],
    ["attention", 194, "attention"],
    ["norm", 408, "add-norm"],
    ["output", 616, undefined],
  ];
  const expanded = new Set(expandedKinds);
  const nodes: KernelNode[] = specs.map(([nodeId, , detailKind]) => ({
    nodeId,
    hierarchyNodeId: `hierarchy:${nodeId}`,
    childNodeIds: [],
    depth: 0,
    expanded: Boolean(detailKind && expanded.has(detailKind)),
    renderRole: detailKind && expanded.has(detailKind) ? "expanded-module" : "atomic",
    canonicalNodeIds: [`canonical:${nodeId}`],
    containedCanonicalNodeIds: [`canonical:${nodeId}`],
    label: nodeId,
    semanticKind: detailKind ?? "operation",
    shape: detailKind === "attention" ? "attention" : "operation",
    inputPortIds: [`${nodeId}:input`],
    outputPortIds: [`${nodeId}:output`],
    evidenceIds: [`evidence:${nodeId}`],
    templateBindingId: detailKind ? `binding:${nodeId}` : undefined,
    synthetic: false,
  }));
  const edges = specs.slice(0, -1).map(([source], index) => {
    const target = specs[index + 1][0];
    return {
      edgeId: `edge:${source}:${target}`,
      canonicalEdgeIds: [`canonical-edge:${source}:${target}`],
      sourcePortId: `${source}:output`,
      targetPortId: `${target}:input`,
      relation: "sequence" as KernelRelation,
      semanticChannel: "flow",
      tensorIds: [],
      label: "flow",
      evidenceIds: [],
    };
  });
  return {
    document: {
      documentId: "document:expansion",
      architectureId: "architecture:expansion",
      sourceDigest: "source:expansion",
      nodes,
      ports: nodes.flatMap((node) => [
        { portId: `${node.nodeId}:input`, ownerNodeId: node.nodeId, direction: "input" as const, role: "input", evidenceIds: [] },
        { portId: `${node.nodeId}:output`, ownerNodeId: node.nodeId, direction: "output" as const, role: "output", evidenceIds: [] },
      ]),
      edges,
      modules: [],
      templateBindings: specs.flatMap(([nodeId, , detailKind]) => detailKind ? [{
        bindingId: `binding:${nodeId}`,
        templateId: detailKind === "attention" ? "attention.qkv-v1" : `catalog.${detailKind}-v1`,
        fidelity: "exact" as const,
        rootCanonicalNodeIds: [`canonical:${nodeId}`],
        canonicalNodeIds: [`canonical:${nodeId}`],
        nodeSlots: {},
        edgeSlots: {},
        portSlots: {},
        tensorSlots: {},
        evidenceIds: [],
        predicateIds: [],
      }] : []),
      diagnostics: [],
    },
    visualState: {
      expandedModuleIds: [],
      nodePositions: Object.fromEntries(specs.map(([nodeId, x]) => [nodeId, { x, y: 344 }])),
      nodeSizes: Object.fromEntries(specs.map(([nodeId]) => [nodeId, { width: 160, height: 92 }])),
      detailOffsets: {},
      pinnedNodeIds: [],
      routeHints: {},
      routeStyle: "adaptive",
      nodeStyle: "semantic",
      labelStyle: "plate",
    },
  };
}

describe("exact detail expansion", () => {
  it("shifts downstream roots by the expanded width and restores collapsed geometry", () => {
    const collapsed = buildKernelRenderScene(...Object.values(fixture([])) as [KernelDocument, KernelVisualState]);
    const expandedFixture = fixture(["attention"]);
    const first = buildKernelRenderScene(expandedFixture.document, expandedFixture.visualState);
    const second = buildKernelRenderScene(expandedFixture.document, expandedFixture.visualState);
    const collapsedOutput = collapsed.nodes.find((node) => node.nodeId === "output")!;
    const expandedOutput = first.nodes.find((node) => node.nodeId === "output")!;

    expect(first).toEqual(second);
    expect(expandedOutput.bounds.x - collapsedOutput.bounds.x).toBe(900 - 160);
    expect(collapsed.nodes.map((node) => node.bounds)).toEqual(
      buildKernelRenderScene(...Object.values(fixture([])) as [KernelDocument, KernelVisualState])
        .nodes.map((node) => node.bounds),
    );
  });

  it("connects external routes to the exact detail entry and exit portals", () => {
    const { document, visualState } = fixture(["attention"]);
    const scene = buildKernelRenderScene(document, visualState);
    const detail = scene.details.find((item) => item.nodeId === "attention")!;
    const incoming = scene.edges.find((edge) => edge.targetPortId === "attention:input")!;
    const outgoing = scene.edges.find((edge) => edge.sourcePortId === "attention:output")!;

    expect(incoming.points.at(-1)).toEqual(detail.entryPoint);
    expect(outgoing.points[0]).toEqual(detail.exitPoint);
    expect(scene.routingMetrics?.nodeIntersections).toBe(0);
    expect(scene.routingMetrics?.reverseExits).toBe(0);
  });
});
