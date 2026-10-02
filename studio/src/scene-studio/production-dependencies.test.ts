import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const PRODUCTION_ENTRYPOINTS = [
  "src/main.tsx",
  "src/scene-studio/SceneStudioApp.tsx",
  "src/scene-studio/App.tsx",
  "src/scene-studio/projection/project-to-scene.ts",
] as const;

describe("scene studio production dependencies", () => {
  it("does not import hand-authored scenario fixtures", () => {
    for (const relativePath of PRODUCTION_ENTRYPOINTS) {
      const source = readFileSync(resolve(process.cwd(), relativePath), "utf8");
      expect(source, relativePath).not.toContain("./scenarios");
      expect(source, relativePath).not.toContain("SCENARIOS");
    }
  });

  it("uses an explicit empty workspace before a source project is available", () => {
    const appSource = readFileSync(resolve(process.cwd(), "src/scene-studio/App.tsx"), "utf8");
    const shellSource = readFileSync(resolve(process.cwd(), "src/scene-studio/SceneStudioApp.tsx"), "utf8");
    expect(appSource).toContain("EMPTY_WORKSPACE_SCENES");
    expect(shellSource).toContain('status: "idle"');
    expect(shellSource).not.toContain('status: "fixture"');
  });
});
