import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import type { StudioStatePayload } from "../domain/source-backed-scene";
import { projectToScene } from "./project-to-scene";

const CASES = ["transformer", "autoformer", "itransformer", "patchtst", "timemixer", "generic"] as const;

function loadCase(name: string): StudioStatePayload {
  const raw = JSON.parse(readFileSync(resolve(process.cwd(), `src/scene-studio/fixtures/${name}.json`), "utf8")) as Partial<StudioStatePayload> & {
    architecture: StudioStatePayload["architecture"] & { framework?: string };
  };
  return {
    ...raw,
    project: {
      project_id: `test-project:${name}`,
      root: `/fixture/${name}`,
      generation: 1,
      framework: raw.architecture.framework ?? "pytorch",
    },
    snapshot: {
      project_root: `/fixture/${name}`,
      entrypoint: raw.architecture.entrypoint,
      revision: "fixture",
      source_files: [],
    },
    evidence: [],
    document: raw.document ?? { source_digest: "0".repeat(64) },
    architecture: raw.architecture,
    hierarchy: raw.hierarchy!,
  };
}

describe("Tier A generic source-to-view projection", () => {
  for (const name of CASES) {
    it(`projects ${name} into non-empty engineering and publication views`, () => {
      const state = loadCase(name);
      const engineering = projectToScene(state, "engineering-flow");
      const paper = projectToScene(state, "paper-publication");
      expect(engineering.nodes.length).toBeGreaterThan(0);
      expect(paper.nodes.length).toBeGreaterThan(0);
      expect(engineering.edges.length, `${name} engineering edges`).toBeGreaterThan(0);
      expect(paper.edges.length, `${name} publication edges`).toBeGreaterThan(0);
      expect(engineering.sourceDigest).toBe(paper.sourceDigest);
      expect(engineering.exactIrDigest).toBe(paper.exactIrDigest);
      expect(engineering.nodes.flatMap((node) => node.canonical_node_ids ?? []).sort())
        .toEqual(paper.nodes.flatMap((node) => node.canonical_node_ids ?? []).sort());
      expect(Object.keys(engineering.bindings).length).toBe(engineering.nodes.length + engineering.edges.length);
      expect(Object.keys(paper.bindings).length).toBe(paper.nodes.length + paper.edges.length);
    });
  }

  it("does not depend on production scenario data or fixture identities", () => {
    const source = readFileSync(resolve(process.cwd(), "src/scene-studio/projection/project-to-scene.ts"), "utf8");
    expect(source).not.toContain("SCENARIOS");
    for (const name of CASES) expect(source.toLowerCase()).not.toContain(`\"${name}\"`);
  });
});
