import { existsSync, readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The prototype is the visual contract for the production kernel. This test
 * deliberately reads the generated Lab artifacts instead of duplicating their
 * geometry in TypeScript, so a catalog can only be considered covered when its
 * actual SVG exposes the same semantic vocabulary.
 */
const casesRoot = resolve(process.cwd(), "../build/scene-visual-lab/cases");

function svgFiles(directory: string): string[] {
  return readdirSync(resolve(casesRoot, directory))
    .filter((name: string) => name.endsWith(".svg"))
    .map((name: string) => resolve(casesRoot, directory, name));
}

describe("Scene Visual Lab prototype vocabulary", () => {
  it("scans every prototype case and keeps the scene grammar present", () => {
    expect(existsSync(casesRoot)).toBe(true);
    const directories = readdirSync(casesRoot, { withFileTypes: true })
      .filter((entry: { isDirectory(): boolean }) => entry.isDirectory())
      .map((entry: { name: string }) => entry.name);
    expect(directories.length).toBeGreaterThanOrEqual(26);

    const allSvgs = directories.flatMap(svgFiles);
    expect(allSvgs.length).toBeGreaterThanOrEqual(1170);
    for (const file of allSvgs) {
      const svg = readFileSync(file, "utf8");
      expect(svg, file).toContain('class="scene-node');
      expect(svg, file).toContain('class="scene-edge');
      expect(svg, file).toContain('class="node-surface');
    }
  });

  it("contains the complete semantic glyph and expanded-detail vocabulary", () => {
    const semantic = readFileSync(resolve(casesRoot, "semantic-glyph-library/direct-semantic-plain.svg"), "utf8");
    expect(semantic).toContain('class="node-glyph"');
    expect(semantic).toContain('class="node-grid"');
    expect(semantic).toContain("operation-glyph");
    expect(semantic).toContain("&#215;");
    expect(semantic).toContain("class=\"node-symbol\"");

    const expanded = readFileSync(resolve(casesRoot, "parent-child-expansion/expanded-attention.svg"), "utf8");
    for (const token of ["detail-matrix", "detail-tone-blue", "detail-tone-green", "detail-tone-pink", "detail-tone-orange", "detail-tone-violet", "detail-symbol", "detail-flow"]) {
      expect(expanded, token).toContain(token);
    }
    expect(expanded).toContain("Q");
    expect(expanded).toContain("K");
    expect(expanded).toContain("V");
    expect(expanded).toContain(">×<");
  });

  it("keeps every formal catalog detail kind represented by a prototype fixture", () => {
    const catalogs = [
      "extended-module-catalog",
      "traditional-ml-catalog",
      "neural-foundation-catalog",
      "vision-sequence-catalog",
      "sequence-generative-catalog",
      "generative-graph-catalog",
      "multimodal-rl-adaptation-catalog",
    ];
    for (const catalog of catalogs) {
      const source = svgFiles(catalog).map((file) => readFileSync(file, "utf8")).join("\n");
      expect(source, catalog).toContain("module-detail");
      expect(source, catalog).toContain("detail-shape");
      expect(source, catalog).toContain("detail-flow");
      expect(source, catalog).toContain("detail-matrix");
    }
  });

  it("binds every formal detail kind to a concrete local prototype label", () => {
    const labels = new Set<string>();
    for (const directory of readdirSync(casesRoot, { withFileTypes: true }).filter((entry: { isDirectory(): boolean }) => entry.isDirectory())) {
      for (const file of readdirSync(resolve(casesRoot, directory.name)).filter((name: string) => name.endsWith(".json"))) {
        const value = JSON.parse(readFileSync(resolve(casesRoot, directory.name, file), "utf8")) as { scene?: { nodes?: Array<{ label?: string }> } };
        for (const node of value.scene?.nodes ?? []) if (node.label) labels.add(node.label);
      }
    }
    const bindings: Record<string, string[]> = {
      attention: ["QKV attention", "Multi-head attention"], feedforward: ["Feed-forward"], "add-norm": ["Add & Norm"],
      convolution: ["Convolution"], "tensor-transform": ["Tensor transform"], embedding: ["Embedding"], recurrent: ["Recurrent cell", "LSTM cell"],
      "mixture-of-experts": ["Sparse MoE"], pooling: ["Pooling"], "linear-model": ["Linear / GLM"], "kernel-machine": ["Kernel machine"],
      "decision-tree": ["Decision tree"], ensemble: ["Forest / Boosting"], clustering: ["Clustering"], decomposition: ["Matrix decomposition"],
      mlp: ["MLP / gated FFN"], normalization: ["Norm layer"], "residual-block": ["Residual block"], "dense-connection": ["Dense connection"],
      inception: ["Inception"], "depthwise-convolution": ["Depthwise separable"], unet: ["U-Net"], "vision-transformer": ["Vision Transformer"],
      gru: ["GRU cell"], "bidirectional-recurrent": ["Bidirectional RNN"], seq2seq: ["Seq2Seq"], "state-space": ["Mamba / SSM"],
      autoencoder: ["Autoencoder"], "variational-autoencoder": ["Variational AE"], gan: ["GAN"], diffusion: ["Diffusion"],
      "normalizing-flow": ["Normalizing flow"], "graph-message-passing": ["Message-passing GNN"], "time-series-forecast": ["Time-series model"],
      "dual-encoder": ["Dual encoder"], dqn: ["DQN"], "actor-critic": ["Actor-Critic"], distillation: ["Distillation"], "adapter-lora": ["LoRA / Adapter"],
    };
    expect(Object.keys(bindings)).toHaveLength(39);
    for (const [kind, candidates] of Object.entries(bindings)) {
      expect(candidates.some((label) => labels.has(label)), kind).toBe(true);
    }
  });
});
