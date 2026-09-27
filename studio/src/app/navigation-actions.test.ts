import { describe, expect, it } from "vitest";

import { navigationExpansion } from "./navigation-actions";

describe("navigation action boundary", () => {
  it("serializes expansion state deterministically for the API", () => {
    const payload = navigationExpansion("module", {
      module: new Set(["module:z", "module:a"]),
      source: new Set(["source:b"]),
    });

    expect(payload).toEqual({
      projection: "module",
      expansions: {
        module: ["module:a", "module:z"],
        source: ["source:b"],
      },
    });
  });
});
