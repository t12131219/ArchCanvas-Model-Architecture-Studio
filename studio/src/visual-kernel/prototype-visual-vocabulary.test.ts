import { describe, expect, it } from "vitest";

import { renderKernelSceneSvg } from "./export";
import type { KernelDocument, KernelNodeShape, KernelRenderScene, KernelVisualState } from "./types";

const shapes: KernelNodeShape[] = [
  "operation", "container", "tensor", "convolution", "attention", "normalization",
  "condition", "merge", "add", "multiply", "concat", "io",
];

function classCount(svg: string, token: string): number {
  return [...svg.matchAll(/class="([^"]+)"/g)]
    .filter((match) => match[1].split(/\s+/).includes(token)).length;
}

function vocabularyFixture() {
  const nodes = shapes.map((shape, index) => ({
    nodeId: `node:${shape}`,
    hierarchyNodeId: `hierarchy:${shape}`,
    childNodeIds: [],
    depth: 0,
    expanded: false,
    renderRole: "atomic" as const,
    canonicalNodeIds: [`canonical:${shape}`],
    containedCanonicalNodeIds: [`canonical:${shape}`],
    label: shape,
    secondaryLabel: "prototype vocabulary",
    semanticKind: shape,
    shape,
    inputPortIds: [`port:${shape}:in`],
    outputPortIds: [`port:${shape}:out`],
    evidenceIds: [],
    synthetic: false,
    bounds: { x: 30 + (index % 4) * 220, y: 30 + Math.floor(index / 4) * 130, width: 180, height: 90 },
  }));
  const document: KernelDocument = {
    documentId: "vocabulary-document",
    architectureId: "vocabulary-architecture",
    sourceDigest: "sha256:vocabulary",
    nodes: nodes.map(({ bounds: _bounds, ...node }) => node),
    ports: nodes.flatMap((node) => [
      { portId: node.inputPortIds[0], ownerNodeId: node.nodeId, direction: "input" as const, role: "data", evidenceIds: [] },
      { portId: node.outputPortIds[0], ownerNodeId: node.nodeId, direction: "output" as const, role: "data", evidenceIds: [] },
    ]),
    edges: [],
    modules: [],
    templateBindings: [],
    diagnostics: [],
  };
  const scene: KernelRenderScene = {
    sceneId: "vocabulary-scene",
    sourceDigest: document.sourceDigest,
    width: 940,
    height: 430,
    nodes,
    edges: [],
    portals: [],
    details: [],
    diagnostics: [],
  };
  const visualState: KernelVisualState = {
    expandedModuleIds: [], nodePositions: {}, nodeSizes: {}, detailOffsets: {}, pinnedNodeIds: [],
    routeHints: {}, routeStyle: "adaptive", nodeStyle: "semantic", labelStyle: "plain",
  };
  return { document, scene, visualState };
}

describe("prototype visual vocabulary", () => {
  it("renders every semantic node glyph used by the Scene Visual Lab", () => {
    const { document, scene, visualState } = vocabularyFixture();
    const { svg } = renderKernelSceneSvg(document, visualState, scene);

    expect(classCount(svg, "scene-node")).toBe(shapes.length);
    expect(classCount(svg, "node-surface")).toBe(shapes.length);
    for (const token of ["matrix-glyph", "convolution-glyph", "attention-glyph", "normalization-glyph", "operation-glyph", "container-glyph"]) {
      expect(svg, token).toContain(token);
    }
    expect(svg).toContain("node-symbol");
    expect(svg).toContain("×");
    expect(svg).toContain("||");
    expect(svg).toContain("node-detail");
  });

  it("keeps prototype detail vocabulary aliases on formal primitives", () => {
    const { document, scene, visualState } = vocabularyFixture();
    scene.details = [{
      nodeId: "node:attention",
      bindingId: "binding:attention",
      templateId: "attention.qkv-v1",
      evidenceIds: [],
      bounds: { x: 20, y: 20, width: 900, height: 380 },
      entryPoint: { x: 20, y: 210 },
      exitPoint: { x: 920, y: 210 },
      primitives: [
        { primitiveId: "flow", kind: "flow", slotId: "flow", canonicalIds: [], points: [{ x: 20, y: 210 }, { x: 80, y: 210 }], tone: "blue", marker: true },
        { primitiveId: "matrix", kind: "matrix", slotId: "matrix", canonicalIds: [], x: 90, y: 180, width: 60, height: 50, label: "Q", columns: 4, rows: 3, depth: 4, tone: "blue" },
        { primitiveId: "operator", kind: "operator", slotId: "operator", canonicalIds: [], cx: 180, cy: 205, radius: 13, label: "×", tone: "orange" },
        { primitiveId: "box", kind: "box", slotId: "box", canonicalIds: [], x: 210, y: 180, width: 70, height: 48, label: "Softmax", tone: "green" },
        { primitiveId: "text", kind: "text", slotId: "text", canonicalIds: [], x: 300, y: 250, value: "Q / K / V", emphasis: false, tone: "neutral" },
      ],
    }];
    const { svg } = renderKernelSceneSvg(document, visualState, scene);
    for (const token of ["detail-flow", "detail-shape", "detail-matrix", "detail-symbol", "detail-box-label", "detail-text", "node-grid"]) {
      expect(svg, token).toContain(token);
    }
  });
});
