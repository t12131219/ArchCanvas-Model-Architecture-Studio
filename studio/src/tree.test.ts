import { describe, expect, it } from "vitest";

import {
  studioModelIdentity,
  visibleNavigationRows,
  visibleProjectEntrypoints,
} from "./tree";

describe("studioModelIdentity", () => {
  const state = {
    project: { project_id: "project:a", generation: 1 },
    architecture: { entrypoint: "models.forecast:Forecaster" },
    document: { source_digest: "digest-a" },
  };

  it("changes whenever navigation state belongs to another analyzed model", () => {
    expect(studioModelIdentity(null)).toBe("");
    expect(studioModelIdentity(state)).not.toBe(studioModelIdentity({
      ...state,
      architecture: { entrypoint: "models.embed:Embedder" },
    }));
    expect(studioModelIdentity(state)).not.toBe(studioModelIdentity({
      ...state,
      project: { ...state.project, generation: 2 },
    }));
    expect(studioModelIdentity(state)).not.toBe(studioModelIdentity({
      ...state,
      document: { source_digest: "digest-b" },
    }));
  });
});

describe("visibleNavigationRows", () => {
  it("rebuilds preorder even when flat input appends descendants late", () => {
    const rows = visibleNavigationRows(
      [
        { id: "root-a", parent_id: null },
        { id: "root-b", parent_id: null },
        { id: "child-a", parent_id: "root-a" },
        { id: "grandchild-a", parent_id: "child-a" },
      ],
      new Set(["root-a", "child-a"]),
    );

    expect(rows.map((row) => row.id)).toEqual([
      "root-a",
      "child-a",
      "grandchild-a",
      "root-b",
    ]);
  });
});

describe("visibleProjectEntrypoints", () => {
  it("requires every ancestor to be expanded", () => {
    const entries = [
      { entrypoint: "model", parent_entrypoint: null },
      { entrypoint: "encoder", parent_entrypoint: "model" },
      { entrypoint: "layer", parent_entrypoint: "encoder" },
    ];

    expect(
      visibleProjectEntrypoints(entries, new Set(["model"]))
        .map((entry) => entry.entrypoint),
    ).toEqual(["model", "encoder"]);
    expect(
      visibleProjectEntrypoints(entries, new Set(["model", "encoder"]))
        .map((entry) => entry.entrypoint),
    ).toEqual(["model", "encoder", "layer"]);
  });
});
