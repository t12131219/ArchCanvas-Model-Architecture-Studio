import { describe, expect, it } from "vitest";

import { initialSceneStudioState, sceneStudioReducer } from "./store";

describe("sceneStudioReducer", () => {
  it("keeps visual history separate from source and semantic identity", () => {
    const selected = sceneStudioReducer(initialSceneStudioState, { type: "selection", selection: { kind: "node", id: "node:1" } });
    expect(sceneStudioReducer(selected, { type: "selection", selection: { kind: "node", id: "node:1" } })).toBe(selected);
    const patched = sceneStudioReducer(selected, {
      type: "visual-patch",
      patch: { operation: "update-node", nodeId: "node:1", changes: { bounds: { x: -40, y: 20, width: 120, height: 60 } } },
    });
    expect(patched.viewSlice.visualRevision).toBe(1);
    expect(patched.semanticSlice).toBe(selected.semanticSlice);
    expect(patched.projectSlice).toBe(selected.projectSlice);
  });

  it("switches modes without replacing the canvas scene state", () => {
    const next = sceneStudioReducer(initialSceneStudioState, { type: "mode", mode: "layout" });
    expect(next.interactionSlice.mode).toBe("layout");
    expect(next.viewSlice).toBe(initialSceneStudioState.viewSlice);
  });
});
