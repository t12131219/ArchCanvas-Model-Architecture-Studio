import { describe, expect, it } from "vitest";

import {
  materializeDraftNode,
  migrateParameterValues,
  MODULE_REGISTRY,
  moduleDefinitionCategory,
  moduleDefinitionLabel,
  parameterChangeInvalidation,
  resolveDefinitionRef,
  resolveQualifiedName,
} from "./registry";

describe("canonical module registry ABI", () => {
  it("loads the Python-exported bundle with unique definitions and ports", () => {
    expect(MODULE_REGISTRY.bundle_digest).toMatch(/^[a-f0-9]{64}$/);
    expect(new Set(MODULE_REGISTRY.definitions.map((item) => item.definition_id)).size)
      .toBe(MODULE_REGISTRY.definitions.length);
    for (const definition of MODULE_REGISTRY.definitions) {
      expect(new Set(definition.ports.map((port) => port.port_id)).size)
        .toBe(definition.ports.length);
    }
  });

  it("resolves Conv2d and MHA through exact references and qualified names", () => {
    const conv = resolveQualifiedName("torch.nn.Conv2d")!;
    const attention = resolveQualifiedName("torch.nn.MultiheadAttention")!;

    expect(conv.definition_id).toBe("pytorch.nn.conv2d");
    expect(conv.ports.map((port) => port.port_id)).toEqual(["input", "output"]);
    expect(attention.ports.filter((port) => port.direction === "input").map((port) => port.port_id))
      .toEqual(["query", "key", "value", "key_padding_mask", "attention_mask"]);
    expect(resolveDefinitionRef({
      definition_id: conv.definition_id,
      version: conv.version,
      digest: conv.digest,
    })).toEqual(conv);
  });

  it("materializes schema defaults and exact named draft ports", () => {
    const conv = resolveQualifiedName("torch.nn.Conv2d")!;
    const node = materializeDraftNode(
      conv,
      "draft:conv",
      "stem_conv",
      "pytorch",
      "node:parent",
    );

    expect(node.definition_ref).toEqual({
      definition_id: conv.definition_id,
      version: conv.version,
      digest: conv.digest,
    });
    expect(node.parameters).toMatchObject({ stride: 1, padding: 0, bias: true });
    expect(node.ports.map((port) => [port.name, port.direction, port.max_connections]))
      .toEqual([["input", "input", 1], ["output", "output", "many"]]);
    expect(moduleDefinitionLabel(conv)).toBe("Conv2d");
    expect(moduleDefinitionCategory(conv)).toBe("Vision - Convolution");
  });

  it("round-trips every definition schema and performs its pinned parameter migration", () => {
    for (const definition of MODULE_REGISTRY.definitions) {
      const roundTrip = JSON.parse(JSON.stringify(definition));
      expect(roundTrip).toEqual(definition);
      expect(resolveDefinitionRef({
        definition_id: definition.definition_id,
        version: definition.version,
        digest: definition.digest,
      })).toBe(definition);

      const node = materializeDraftNode(
        definition,
        `draft:${definition.definition_id.replaceAll(".", "-")}`,
        definition.definition_id,
        "pytorch",
        null,
      );
      const defaults = Object.fromEntries(
        definition.parameters.map((parameter) => [parameter.parameter_id, parameter.default]),
      );
      expect(node.parameters).toEqual(defaults);
      expect(migrateParameterValues(
        definition,
        definition.parameter_schema_version,
        JSON.parse(JSON.stringify(node.parameters)),
      )).toEqual(defaults);
      expect(() => migrateParameterValues(definition, "0.0", {}))
        .toThrow("No registered parameter migration");
    }
  });

  it("derives cache invalidation from declared parameter impact domains", () => {
    const conv = resolveQualifiedName("torch.nn.Conv2d")!;
    const before = migrateParameterValues(conv, "1.0", {});
    const after = { ...before, out_channels: 32 };

    expect(parameterChangeInvalidation(conv, before, after))
      .toEqual(["shape", "cost", "code", "visual"]);
    expect(parameterChangeInvalidation(conv, before, before)).toEqual([]);
  });
});
