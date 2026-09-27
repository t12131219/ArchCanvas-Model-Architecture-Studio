import { describe, expect, it } from "vitest";

import { initialProjectSelection } from "./project-launch";

describe("initialProjectSelection", () => {
  it("selects a top-level model without guessing a configuration", () => {
    expect(initialProjectSelection([
      {
        entrypoint: "package.layers:Block",
        framework: "pytorch",
        top_level: false,
        depth: 0,
      },
      {
        entrypoint: "package.model:Model",
        framework: "unknown",
        top_level: true,
        depth: 1,
      },
    ])).toEqual({
      entrypoint: "package.model:Model",
      framework: "auto",
      configPath: "",
    });
  });

  it("falls back to a root entrypoint when no top-level model is marked", () => {
    expect(initialProjectSelection([
      {
        entrypoint: "package.child:Layer",
        framework: "pytorch",
        top_level: false,
        depth: 1,
      },
      {
        entrypoint: "package.root:Model",
        framework: "pytorch",
        top_level: false,
        depth: 0,
      },
    ])).toEqual({
      entrypoint: "package.root:Model",
      framework: "pytorch",
      configPath: "",
    });
  });

  it("prefers a model module over an unreferenced framework helper", () => {
    expect(initialProjectSelection([
      {
        entrypoint: "layers.embed:FeatureEmbedder",
        path: "layers/embed.py",
        framework: "pytorch",
        top_level: true,
        depth: 0,
        child_count: 8,
      },
      {
        entrypoint: "models.forecast:Forecaster",
        path: "models/forecast.py",
        framework: "pytorch",
        top_level: true,
        depth: 0,
        child_count: 2,
      },
    ])).toEqual({
      entrypoint: "models.forecast:Forecaster",
      framework: "pytorch",
      configPath: "",
    });
  });
});
