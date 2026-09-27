import { describe, expect, it } from "vitest";

import { kernelSceneDigest } from "../visual-kernel/export";
import { buildKernelRenderScene } from "../visual-kernel/layout";
import type { KernelRenderScene } from "../visual-kernel/types";
import { adaptFormalState, type FormalStudioState } from "./formal-state-adapter";
import autoformer from "./fixtures/autoformer.json";
import generic from "./fixtures/generic.json";
import itransformer from "./fixtures/itransformer.json";
import patchtst from "./fixtures/patchtst.json";
import timemixer from "./fixtures/timemixer.json";
import transformer from "./fixtures/transformer.json";

const fixtures = {
  transformer,
  autoformer,
  itransformer,
  patchtst,
  timemixer,
  generic,
} as Record<string, FormalStudioState>;

function finiteScene(scene: KernelRenderScene): boolean {
  const values = [
    scene.width,
    scene.height,
    ...scene.nodes.flatMap((node) => Object.values(node.bounds)),
    ...scene.edges.flatMap((edge) => [
      edge.labelPoint.x,
      edge.labelPoint.y,
      edge.labelAngle,
      ...edge.points.flatMap((point) => [point.x, point.y]),
    ]),
    ...scene.portals.flatMap((portal) => [portal.point.x, portal.point.y]),
  ];
  return values.every(Number.isFinite);
}

function reordered(state: FormalStudioState): FormalStudioState {
  return {
    ...state,
    architecture: {
      ...state.architecture,
      nodes: [...state.architecture.nodes].reverse(),
      edges: [...state.architecture.edges].reverse(),
    },
    hierarchy: { ...state.hierarchy, nodes: [...state.hierarchy.nodes].reverse() },
    semantic_overlay: state.semantic_overlay ? {
      ...state.semantic_overlay,
      annotations: [...(state.semantic_overlay.annotations ?? [])].reverse(),
      template_bindings: [...(state.semantic_overlay.template_bindings ?? [])].reverse(),
    } : state.semantic_overlay,
  };
}

describe("formal Tier-A model fixtures", () => {
  for (const [name, state] of Object.entries(fixtures)) {
    it(`${name} generates a deterministic finite KernelDocument and scene`, () => {
      const first = adaptFormalState(state);
      const second = adaptFormalState(state);
      const firstScene = buildKernelRenderScene(first.document, first.visualState);
      const secondScene = buildKernelRenderScene(second.document, second.visualState);

      expect(first.document.diagnostics.filter((item) => item.severity === "blocking")).toEqual([]);
      expect(first.document.nodes.length).toBeGreaterThan(1);
      expect(first.document.ports.length).toBe(first.document.nodes.length * 2);
      expect(firstScene.nodes.length).toBe(first.document.nodes.length);
      expect(finiteScene(firstScene)).toBe(true);
      expect(second).toEqual(first);
      expect(kernelSceneDigest(second.document, second.visualState, secondScene))
        .toBe(kernelSceneDigest(first.document, first.visualState, firstScene));
    });

    it(`${name} is invariant to formal input ordering`, () => {
      const first = adaptFormalState(state);
      const shuffled = adaptFormalState(reordered(state));
      const firstScene = buildKernelRenderScene(first.document, first.visualState);
      const shuffledScene = buildKernelRenderScene(shuffled.document, shuffled.visualState);

      expect(shuffled.document).toEqual(first.document);
      expect(kernelSceneDigest(shuffled.document, shuffled.visualState, shuffledScene))
        .toBe(kernelSceneDigest(first.document, first.visualState, firstScene));
    });
  }
});
