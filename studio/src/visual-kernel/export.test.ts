import { describe, expect, it } from "vitest";

import { kernelSceneDigest, KERNEL_EXPORT_VERSION, renderKernelSceneSvg } from "./export";
import type { KernelDocument, KernelRenderScene, KernelVisualState } from "./types";

function fixture() {
  const document: KernelDocument = {
    documentId: "kernel-document:test",
    architectureId: "architecture:test",
    sourceDigest: "sha256:source-test",
    nodes: [{
      nodeId: "view:root",
      hierarchyNodeId: "hierarchy:root",
      childNodeIds: ["view:child"],
      depth: 0,
      expanded: true,
      renderRole: "expanded-module",
      canonicalNodeIds: ["node:root"],
      containedCanonicalNodeIds: ["node:root", "node:child"],
      label: "Root & <model>",
      semanticKind: "module",
      shape: "container",
      inputPortIds: ["port:root:in"],
      outputPortIds: ["port:root:out"],
      evidenceIds: ["evidence:root"],
      templateBindingId: "binding:test",
      synthetic: false,
    }, {
      nodeId: "view:child",
      hierarchyNodeId: "hierarchy:child",
      parentNodeId: "view:root",
      parentModuleId: "module:root",
      childNodeIds: [],
      depth: 1,
      expanded: false,
      renderRole: "atomic",
      canonicalNodeIds: ["node:child"],
      containedCanonicalNodeIds: ["node:child"],
      label: "Child",
      secondaryLabel: "Linear",
      semanticKind: "operation",
      shape: "operation",
      inputPortIds: ["port:child:in"],
      outputPortIds: ["port:child:out"],
      evidenceIds: ["evidence:child"],
      synthetic: false,
    }],
    ports: [
      { portId: "port:root:out", ownerNodeId: "view:root", direction: "output", role: "data", evidenceIds: [] },
      { portId: "port:child:in", ownerNodeId: "view:child", direction: "input", role: "data", evidenceIds: [] },
    ],
    edges: [{
      edgeId: "kernel-edge:test",
      canonicalEdgeIds: ["edge:test"],
      sourcePortId: "port:root:out",
      targetPortId: "port:child:in",
      relation: "residual",
      semanticChannel: "data",
      tensorIds: ["tensor:test"],
      label: "skip & merge",
      evidenceIds: ["evidence:edge"],
    }],
    modules: [],
    templateBindings: [{
      bindingId: "binding:test",
      templateId: "attention.qkv-v1",
      fidelity: "exact",
      rootCanonicalNodeIds: ["node:root"],
      canonicalNodeIds: ["node:child"],
      nodeSlots: { q_projection: ["node:child"] },
      edgeSlots: {},
      portSlots: {},
      tensorSlots: {},
      evidenceIds: ["evidence:binding"],
      predicateIds: ["predicate:test"],
    }],
    diagnostics: [],
  };
  const visualState: KernelVisualState = {
    expandedModuleIds: ["hierarchy:root"],
    nodePositions: {},
    nodeSizes: {},
    detailOffsets: {},
    pinnedNodeIds: [],
    routeHints: {},
    routeStyle: "adaptive",
    nodeStyle: "technical",
    labelStyle: "plate",
  };
  const scene: KernelRenderScene = {
    sceneId: "kernel:architecture:test",
    sourceDigest: document.sourceDigest,
    width: 640,
    height: 420,
    nodes: [
      { ...document.nodes[0], bounds: { x: 30, y: 30, width: 560, height: 340 } },
      { ...document.nodes[1], bounds: { x: 220, y: 170, width: 160, height: 90 } },
    ],
    edges: [{
      ...document.edges[0],
      points: [{ x: 100, y: 110 }, { x: 220, y: 215 }],
      path: "M100 110L220 215",
      labelPoint: { x: 160, y: 162.5 },
      labelAngle: 0,
    }],
    portals: [{ portalId: "portal:test", moduleNodeId: "view:root", edgeId: "kernel-edge:test", direction: "entry", point: { x: 30, y: 200 } }],
    details: [{
      nodeId: "view:root",
      bindingId: "binding:test",
      templateId: "attention.qkv-v1",
      evidenceIds: ["evidence:binding"],
      bounds: { x: 70, y: 100, width: 480, height: 220 },
      entryPoint: { x: 70, y: 210 },
      exitPoint: { x: 550, y: 210 },
      primitives: [
        { primitiveId: "binding:test:q_projection", kind: "box", slotId: "q_projection", canonicalIds: ["node:child"], x: 120, y: 170, width: 80, height: 44, label: "Q <proj>", tone: "blue" },
        { primitiveId: "binding:test:flow", kind: "flow", slotId: "visual:flow", canonicalIds: [], points: [{ x: 70, y: 210 }, { x: 120, y: 192 }], tone: "blue", marker: true },
      ],
    }],
    diagnostics: [],
  };
  return { document, visualState, scene };
}

describe("kernel main-view export", () => {
  it("produces a stable digest without camera or selection state", () => {
    const { document, visualState, scene } = fixture();
    const first = kernelSceneDigest(document, visualState, scene);
    const second = kernelSceneDigest(document, { ...visualState }, { ...scene });
    expect(second).toBe(first);
    expect(first).toMatch(/^kernel-render:[0-9a-f]{16}$/);
  });

  it("serializes the already routed scene with complete provenance", () => {
    const { document, visualState, scene } = fixture();
    const artifact = renderKernelSceneSvg(document, visualState, scene);

    expect(artifact.svg).toContain(`data-kernel-version="${KERNEL_EXPORT_VERSION}"`);
    expect(artifact.svg).toContain(`data-render-digest="${artifact.renderDigest}"`);
    expect(artifact.svg).toContain('data-source-digest="sha256:source-test"');
    expect(artifact.svg).toContain('data-canonical-node-ids="node:child"');
    expect(artifact.svg).toContain('data-canonical-edge-ids="edge:test"');
    expect(artifact.svg).toContain('data-source-port-id="port:root:out"');
    expect(artifact.svg).toContain('data-target-port-id="port:child:in"');
    expect(artifact.svg).toContain('data-template-binding-id="binding:test"');
    expect(artifact.svg).toContain('data-template-fidelity="exact"');
    expect(artifact.svg).toContain('data-portal-id="portal:test"');
    expect(artifact.svg).toContain('d="M100 110L220 215"');
    expect(artifact.svg).toContain('transform="translate(160 162.5) rotate(0)"');
    expect(artifact.svg).toContain('data-detail-primitive-id="binding:test:q_projection"');
    expect(artifact.svg).toContain('data-relation="residual"');
    expect(artifact.svg).toContain('class="kernel-detail-layer"');
    expect([...artifact.svg.matchAll(/class="kernel-template-detail"/g)]).toHaveLength(1);
  });

  it("escapes model and detail labels as XML", () => {
    const { document, visualState, scene } = fixture();
    const { svg } = renderKernelSceneSvg(document, visualState, scene);
    expect(svg).toContain("Root &amp; &lt;model&gt;");
    expect(svg).toContain("skip &amp; merge");
    expect(svg).toContain("Q &lt;proj&gt;");
    expect(svg).not.toContain("Root & <model>");
  });
});
