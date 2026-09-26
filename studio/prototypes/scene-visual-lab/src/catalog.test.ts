import { describe, expect, it } from "vitest";

import { MODEL_FAMILY_CATALOG } from "./model-family-catalog";
import { buildModuleDetail, DETAIL_KIND_NAMES, EXPANDED_DETAIL_SIZES } from "./module-details";
import { expandScene } from "./expansion";
import { DEFAULT_OPTIONS, SCENARIOS } from "./scenarios";
import { renderSceneSvg } from "./svg-export";
import type { NodeDetailKind } from "./types";

const NEW_KINDS: readonly NodeDetailKind[] = [
  "linear-model", "kernel-machine", "decision-tree", "ensemble", "clustering", "decomposition",
  "mlp", "normalization", "residual-block", "dense-connection", "inception", "depthwise-convolution",
  "unet", "vision-transformer", "gru", "bidirectional-recurrent", "seq2seq", "state-space",
  "autoencoder", "variational-autoencoder", "gan", "diffusion", "normalizing-flow",
  "graph-message-passing", "time-series-forecast", "dual-encoder", "dqn", "actor-critic",
  "distillation", "adapter-lora",
];

const CATALOG_SCENE_IDS = [
  "traditional-ml-catalog",
  "neural-foundation-catalog",
  "vision-sequence-catalog",
  "sequence-generative-catalog",
  "generative-graph-catalog",
  "multimodal-rl-adaptation-catalog",
] as const;

describe("expanded model family catalog", () => {
  it("provides a named, sized and buildable diagram for every new family", () => {
    expect(NEW_KINDS).toHaveLength(30);
    for (const kind of NEW_KINDS) {
      const size = EXPANDED_DETAIL_SIZES[kind];
      expect(DETAIL_KIND_NAMES[kind]).toBeTruthy();
      expect(size.width).toBeGreaterThanOrEqual(700);
      expect(buildModuleDetail(kind, { x: 20, y: 40, ...size }).primitives.length).toBeGreaterThan(8);
    }
  });

  it("catalogs aliases and the evidence axes needed to distinguish variants", () => {
    const catalogKinds = new Set(MODEL_FAMILY_CATALOG.map((entry) => entry.kind));
    expect(MODEL_FAMILY_CATALOG.length).toBeGreaterThanOrEqual(30);
    expect(MODEL_FAMILY_CATALOG.flatMap((entry) => entry.aliases).length).toBeGreaterThan(300);
    expect(MODEL_FAMILY_CATALOG.every((entry) => entry.aliases.length > 0 && entry.differenceAxes.length > 0)).toBe(true);
    for (const kind of NEW_KINDS) expect(catalogKinds.has(kind)).toBe(true);
  });

  it("places every new family exactly once in the six catalog scenes", () => {
    const familyCounts = new Map<NodeDetailKind, number>();
    for (const sceneId of CATALOG_SCENE_IDS) {
      const scene = SCENARIOS.find((item) => item.scene_id === sceneId);
      expect(scene, `missing catalog scene ${sceneId}`).toBeTruthy();
      for (const node of scene!.nodes) {
        if (!node.detail_kind || !NEW_KINDS.includes(node.detail_kind)) continue;
        familyCounts.set(node.detail_kind, (familyCounts.get(node.detail_kind) ?? 0) + 1);
      }
    }
    expect([...familyCounts.keys()].sort()).toEqual([...NEW_KINDS].sort());
    expect([...familyCounts.values()].every((count) => count === 1)).toBe(true);
  });

  it("renders distinguishing labels for representative expanded families", () => {
    const expectations: Array<[string, string, string]> = [
      ["traditional-ml-catalog", "decision-tree", "feature j ≤ t?"],
      ["vision-sequence-catalog", "unet", "skip: copy / crop / concat"],
      ["sequence-generative-catalog", "state-space", "Selective SSM"],
      ["generative-graph-catalog", "graph-message-passing", "message φ"],
      ["multimodal-rl-adaptation-catalog", "adapter-lora", "y = Wx + αBAx"],
    ];
    for (const [sceneId, kind, label] of expectations) {
      const base = SCENARIOS.find((scene) => scene.scene_id === sceneId)!;
      const node = base.nodes.find((item) => item.detail_kind === kind)!;
      const { svg } = renderSceneSvg(expandScene(base, new Set([node.scene_node_id])), DEFAULT_OPTIONS);
      expect(svg).toContain(label);
      expect(svg).not.toContain("undefined");
    }
  });
});
