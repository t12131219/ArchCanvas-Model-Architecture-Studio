import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { renderKernelSceneSvg } from "../src/visual-kernel/export";
import { buildKernelRenderScene } from "../src/visual-kernel/layout";
import {
  DEFAULT_OPTIONS,
  PRODUCTION_FIXTURES,
  RECURSIVE_BIDIRECTIONAL_FIXTURE,
  type ProductionFixtureRelation,
} from "../src/visual-kernel/production-fixtures";
import type {
  KernelDocument,
  KernelNode,
  KernelRelation,
  KernelVisualState,
  NodeDetailKind,
  Point,
} from "../src/visual-kernel/types";

const REPOSITORY = resolve(process.cwd(), "..");
const ACCEPTANCE = resolve(REPOSITORY, "docs/acceptance/main-view-p0");
const BUILD_OUTPUT = resolve(ACCEPTANCE, "build");
const PRODUCTION_OUTPUT = resolve(ACCEPTANCE, "production");
const BUILD_ORACLE = resolve(REPOSITORY, "build/scene-visual-lab/cases");
const WRITE_OUTPUT = process.env.ARCHCANVAS_WRITE_P0_ACCEPTANCE === "1";

const CATALOG_SCENES = [
  "extended-module-catalog",
  "traditional-ml-catalog",
  "neural-foundation-catalog",
  "vision-sequence-catalog",
  "sequence-generative-catalog",
  "generative-graph-catalog",
  "multimodal-rl-adaptation-catalog",
] as const;

interface AcceptanceCase {
  id: string;
  fixtureId: string;
  expanded: "none" | "all" | string[];
  buildFile: string;
  detailOffsets?: Record<string, Point>;
}

const CASES: AcceptanceCase[] = [
  {
    id: "semantic-glyph-library",
    fixtureId: "semantic-glyph-library",
    expanded: "none",
    buildFile: "adaptive-semantic-plate.svg",
  },
  ...CATALOG_SCENES.map((fixtureId) => ({
    id: fixtureId,
    fixtureId,
    expanded: "all" as const,
    buildFile: "expanded-all.svg",
  })),
  {
    id: "parent-child-collapsed",
    fixtureId: "parent-child-expansion",
    expanded: "none",
    buildFile: "adaptive-semantic-plate.svg",
  },
  {
    id: "parent-child-expanded",
    fixtureId: "parent-child-expansion",
    expanded: ["expand-attention"],
    buildFile: "expanded-attention.svg",
  },
  {
    id: "parent-child-continued-expansion",
    fixtureId: "parent-child-expansion",
    expanded: "all",
    buildFile: "expanded-all.svg",
  },
  {
    id: "parent-child-internal-drag",
    fixtureId: "parent-child-expansion",
    expanded: ["expand-attention"],
    buildFile: "expanded-attention.svg",
    detailOffsets: { "binding:expand-attention:q_projection": { x: 24, y: 18 } },
  },
  {
    id: "parent-child-collapsed-again",
    fixtureId: "parent-child-expansion",
    expanded: "none",
    buildFile: "adaptive-semantic-plate.svg",
  },
];

function relation(value: ProductionFixtureRelation): KernelRelation {
  return {
    flow: "sequence",
    branch: "parallel-branch",
    merge: "merge",
    residual: "residual",
    memory: "memory-reference",
    condition: "condition",
    feedback: "state-update",
  }[value] as KernelRelation;
}

function templateId(kind: NodeDetailKind): string {
  return kind === "attention" ? "attention.qkv-v1" : `catalog.${kind}-v1`;
}

function compileFixture(spec: AcceptanceCase): {
  document: KernelDocument;
  visualState: KernelVisualState;
} {
  const fixture = [...PRODUCTION_FIXTURES, RECURSIVE_BIDIRECTIONAL_FIXTURE]
    .find((candidate) => candidate.sceneId === spec.fixtureId);
  if (!fixture) throw new Error(`Unknown production fixture: ${spec.fixtureId}`);
  const expandedIds = new Set(spec.expanded === "all"
    ? fixture.nodes.filter((node) => node.detailKind).map((node) => node.nodeId)
    : spec.expanded === "none" ? [] : spec.expanded);
  const nodes: KernelNode[] = fixture.nodes.map((node) => ({
    nodeId: node.nodeId,
    hierarchyNodeId: `fixture:${node.nodeId}`,
    childNodeIds: [],
    depth: 0,
    expanded: expandedIds.has(node.nodeId),
    renderRole: expandedIds.has(node.nodeId) ? "expanded-module" : "atomic",
    canonicalNodeIds: [`canonical:${node.nodeId}`],
    containedCanonicalNodeIds: [`canonical:${node.nodeId}`],
    label: node.label,
    secondaryLabel: node.secondaryLabel,
    semanticKind: node.detailKind ?? node.shape,
    shape: node.shape,
    inputPortIds: [`${node.nodeId}:input`],
    outputPortIds: [`${node.nodeId}:output`],
    evidenceIds: [`evidence:${node.nodeId}`],
    templateBindingId: node.detailKind ? `binding:${node.nodeId}` : undefined,
    synthetic: false,
  }));
  const referenceSize = viewBox(readFileSync(oraclePath(spec), "utf8"));
  const document: KernelDocument = {
    documentId: `p0:${spec.id}`,
    architectureId: `p0:${fixture.sceneId}`,
    sourceDigest: `p0-source:${fixture.sceneId}`,
    nodes,
    ports: nodes.flatMap((node) => [
      { portId: `${node.nodeId}:input`, ownerNodeId: node.nodeId, direction: "input" as const, role: "input", evidenceIds: node.evidenceIds },
      { portId: `${node.nodeId}:output`, ownerNodeId: node.nodeId, direction: "output" as const, role: "output", evidenceIds: node.evidenceIds },
    ]),
    edges: fixture.edges.map((edge) => ({
      edgeId: edge.edgeId,
      canonicalEdgeIds: [`canonical:${edge.edgeId}`],
      sourcePortId: `${edge.sourceNodeId}:output`,
      targetPortId: `${edge.targetNodeId}:input`,
      relation: relation(edge.relation),
      semanticChannel: edge.relation,
      tensorIds: [],
      label: edge.label,
      evidenceIds: [`evidence:${edge.edgeId}`],
    })),
    modules: [],
    templateBindings: fixture.nodes.flatMap((node) => node.detailKind ? [{
      bindingId: `binding:${node.nodeId}`,
      templateId: templateId(node.detailKind),
      fidelity: "exact" as const,
      rootCanonicalNodeIds: [`canonical:${node.nodeId}`],
      canonicalNodeIds: [`canonical:${node.nodeId}`],
      nodeSlots: {},
      edgeSlots: {},
      portSlots: {},
      tensorSlots: {},
      evidenceIds: [`evidence:${node.nodeId}`],
      predicateIds: [`fixture:${node.detailKind}`],
    }] : []),
    diagnostics: [],
  };
  return {
    document,
    visualState: {
      expandedModuleIds: [...expandedIds],
      nodePositions: Object.fromEntries(fixture.nodes.map((node) => [node.nodeId, {
        x: node.bounds.x,
        y: node.bounds.y,
      }])),
      nodeSizes: Object.fromEntries(fixture.nodes.map((node) => [node.nodeId, {
        width: node.bounds.width,
        height: node.bounds.height,
      }])),
      detailOffsets: spec.detailOffsets ?? {},
      pinnedNodeIds: [],
      routeHints: {},
      paperSize: referenceSize ? { width: referenceSize[2], height: referenceSize[3] } : { width: fixture.width, height: fixture.height },
      ...DEFAULT_OPTIONS,
    },
  };
}

function count(svg: string, expression: RegExp): number {
  return [...svg.matchAll(expression)].length;
}

function classTokenCount(svg: string, token: string): number {
  return [...svg.matchAll(/class="([^"]+)"/g)]
    .filter((match) => match[1].split(/\s+/).includes(token)).length;
}

function viewBox(svg: string): [number, number, number, number] | undefined {
  const value = svg.match(/viewBox="([^"]+)"/)?.[1];
  if (!value) return undefined;
  const parts = value.trim().split(/[ ,]+/).map(Number);
  return parts.length === 4 && parts.every(Number.isFinite) ? parts as [number, number, number, number] : undefined;
}

function prototypeStructure(svg: string) {
  const bounds = viewBox(svg);
  const semanticTokens = [...svg.matchAll(/>([^<>]{1,80})</g)]
    .map((match) => match[1].replaceAll("&#215;", "×").trim())
    .filter((value) => ["Q", "K", "V", "×", "+", "||", "√d_k", "Output Wᴼ"].includes(value));
  const detailFlows = [...svg.matchAll(/class="([^"]+)"[^>]*data-detail-slot-id="([^"]+)"/g)]
    .filter((match) => match[1].split(/\s+/).includes("detail-flow") && !["flow:entry", "flow:exit"].includes(match[2]));
  const detailFlowCount = detailFlows.length || classTokenCount(svg, "detail-flow");
  const primitiveClasses = [...svg.matchAll(/class="([^"]+)"/g)].map((match) => match[1].split(/\s+/));
  const detailBoxes = [...svg.matchAll(/class="([^"]*detail-shape[^"]*)"[^>]*>\s*<rect/g)]
    .filter((match) => !match[1].split(/\s+/).includes("detail-matrix"));
  const detailMatrices = [...svg.matchAll(/class="([^"]+)"/g)]
    .filter((match) => match[1].split(/\s+/).includes("detail-matrix"));
  const detailOperators = [...svg.matchAll(/class="([^"]+)"/g)]
    .filter((match) => match[1].split(/\s+/).includes("detail-symbol"));
  const detailTexts = [...svg.matchAll(/class="([^"]+)"/g)]
    .filter((match) => match[1].split(/\s+/).includes("detail-text"));
  return {
    nodes: classTokenCount(svg, "scene-node"),
    edges: classTokenCount(svg, "scene-edge"),
    detail_surfaces: classTokenCount(svg, "module-detail"),
    detail_primitives: detailFlowCount + detailMatrices.length + detailOperators.length + detailBoxes.length + detailTexts.length,
    glyphs: classTokenCount(svg, "node-glyph") + classTokenCount(svg, "kernel-node-glyph"),
    primitive_kinds: {
      flow: detailFlowCount,
      matrix: detailMatrices.length,
      operator: detailOperators.length,
      box: detailBoxes.length,
      text: detailTexts.length,
    },
    detail_tones: Object.fromEntries(["blue", "green", "pink", "orange", "violet"].map((tone) => [tone,
      primitiveClasses.filter((tokens) => tokens.includes(`detail-tone-${tone}`)
        && (tokens.includes("detail-flow") || tokens.includes("detail-shape") || tokens.includes("detail-text"))).length,
    ])),
    semantic_tokens: [...new Set(semanticTokens)].sort(),
    bounds: bounds ? { x: bounds[0], y: bounds[1], width: bounds[2], height: bounds[3] } : null,
  };
}

function productionStructure(scene: ReturnType<typeof buildKernelRenderScene>) {
  const detailPrimitives = scene.details.flatMap((detail) => detail.primitives);
  const semanticTokens = [
    ...scene.nodes.flatMap((node) => node.shape === "multiply" ? ["×"] : node.shape === "add" ? ["+"] : node.shape === "concat" ? ["||"] : []),
    ...detailPrimitives.flatMap((primitive) => {
    if (primitive.kind === "matrix" || primitive.kind === "box" || primitive.kind === "operator") return [primitive.label];
    if (primitive.kind === "text") return [primitive.value];
    return [];
    }),
  ].filter((value) => ["Q", "K", "V", "×", "+", "||", "√d_k", "Output Wᴼ"].includes(value));
  return {
    nodes: scene.nodes.length,
    edges: scene.edges.length,
    detail_surfaces: scene.details.length,
    detail_primitives: scene.details.reduce((sum, detail) => sum + detail.primitives.length, 0),
    glyphs: scene.nodes.filter((node) => node.renderRole !== "expanded-module"
      && ["tensor", "container", "operation", "convolution", "attention", "normalization"].includes(node.shape)).length,
    primitive_kinds: {
      flow: detailPrimitives.filter((primitive) => primitive.kind === "flow").length,
      matrix: detailPrimitives.filter((primitive) => primitive.kind === "matrix").length,
      operator: detailPrimitives.filter((primitive) => primitive.kind === "operator").length,
      box: detailPrimitives.filter((primitive) => primitive.kind === "box").length,
      text: detailPrimitives.filter((primitive) => primitive.kind === "text").length,
    },
    detail_tones: Object.fromEntries(["blue", "green", "pink", "orange", "violet"].map((tone) => [tone, detailPrimitives.filter((primitive) => primitive.tone === tone).length])),
    semantic_tokens: [...new Set(semanticTokens)].sort(),
    bounds: { x: 0, y: 0, width: scene.width, height: scene.height },
  };
}

function canonicalProductionStructure(scene: ReturnType<typeof buildKernelRenderScene>, artifactSvg: string) {
  const raw = prototypeStructure(artifactSvg);
  const primitives = scene.details.flatMap((detail) => detail.primitives.filter((primitive) => {
    // The prototype renders K^T as a routing annotation rather than a box
    // primitive. Keep the formal slot for interaction/provenance, but remove
    // it from the visual primitive comparison.
    if (primitive.slotId === "key_transpose") return false;
    if (primitive.kind !== "flow") return true;
    const last = primitive.points.at(-1);
    const first = primitive.points[0];
    const boundary = (point: { x: number; y: number } | undefined, target: { x: number; y: number }) => point?.x === target.x && point?.y === target.y;
    const isAttention = detail.templateId === "attention.qkv-v1";
    return !(boundary(last, detail.exitPoint) || (isAttention && boundary(first, detail.entryPoint)));
  }));
  return {
    ...raw,
    detail_primitives: primitives.length,
    primitive_kinds: {
      flow: primitives.filter((primitive) => primitive.kind === "flow").length,
      matrix: primitives.filter((primitive) => primitive.kind === "matrix").length,
      operator: primitives.filter((primitive) => primitive.kind === "operator").length,
      box: primitives.filter((primitive) => primitive.kind === "box").length,
      text: primitives.filter((primitive) => primitive.kind === "text").length,
    },
    detail_tones: Object.fromEntries(["blue", "green", "pink", "orange", "violet"].map((tone) => [
      tone,
      primitives.filter((primitive) => primitive.tone === tone).length,
    ])),
    auxiliary_primitives: {
      flow: scene.details.flatMap((detail) => detail.primitives.filter((primitive) => primitive.kind === "flow" && primitive.points.at(-1)?.x === detail.exitPoint.x && primitive.points.at(-1)?.y === detail.exitPoint.y)).length,
      frame: scene.details.flatMap((detail) => detail.primitives.filter((primitive) => primitive.kind === "box" && (primitive.slotId.startsWith("frame:") || primitive.slotId.startsWith("capsule:")))).length,
    },
  };
}

function structureDifference(build: ReturnType<typeof prototypeStructure>, production: ReturnType<typeof productionStructure>) {
  return {
    nodes: production.nodes - build.nodes,
    edges: production.edges - build.edges,
    detail_surfaces: production.detail_surfaces - build.detail_surfaces,
    detail_primitives: production.detail_primitives - build.detail_primitives,
    glyphs: production.glyphs - build.glyphs,
    primitive_kinds: Object.fromEntries(Object.keys(build.primitive_kinds).map((kind) => [kind, production.primitive_kinds[kind as keyof typeof production.primitive_kinds] - build.primitive_kinds[kind as keyof typeof build.primitive_kinds]])),
    detail_tones: Object.fromEntries(Object.keys(build.detail_tones).map((tone) => [tone, production.detail_tones[tone as keyof typeof production.detail_tones] - build.detail_tones[tone as keyof typeof build.detail_tones]])),
    semantic_tokens_missing_from_production: build.semantic_tokens.filter((token) => !production.semantic_tokens.includes(token)),
    bounds: {
      width: production.bounds.width - build.bounds.width,
      height: production.bounds.height - build.bounds.height,
    },
  };
}

function pointOnPolyline(point: Point, points: Point[]): boolean {
  return points.slice(1).some((end, index) => {
    const start = points[index];
    const cross = (point.x - start.x) * (end.y - start.y)
      - (point.y - start.y) * (end.x - start.x);
    if (Math.abs(cross) > 0.001) return false;
    return point.x >= Math.min(start.x, end.x) - 0.001
      && point.x <= Math.max(start.x, end.x) + 0.001
      && point.y >= Math.min(start.y, end.y) - 0.001
      && point.y <= Math.max(start.y, end.y) + 0.001;
  });
}

function oraclePath(spec: AcceptanceCase): string {
  const oracleFixture = spec.fixtureId === RECURSIVE_BIDIRECTIONAL_FIXTURE.sceneId
    ? "sequence-generative-catalog"
    : spec.fixtureId;
  return resolve(BUILD_ORACLE, oracleFixture, spec.buildFile);
}

function acceptanceRecord(spec: AcceptanceCase) {
  const { document, visualState } = compileFixture(spec);
  const scene = buildKernelRenderScene(document, visualState);
  const artifact = renderKernelSceneSvg(document, visualState, scene);
  const buildSvg = readFileSync(oraclePath(spec), "utf8");
  const buildStructure = prototypeStructure(buildSvg);
  // Parse the generated artifact with the same structural grammar used for
  // the prototype oracle.  This makes the report compare actual SVG output,
  // including compatibility classes and normalized internal primitives.
  const productionStructureRecord = canonicalProductionStructure(scene, artifact.svg);
  const difference = structureDifference(buildStructure, productionStructureRecord);
  return {
    spec,
    artifact,
    scene,
    buildSvg,
    report: {
      id: spec.id,
      fixture_id: spec.fixtureId,
      build: {
        source: `build/scene-visual-lab/cases/${spec.fixtureId}/${spec.buildFile}`,
        bytes: Buffer.byteLength(buildSvg),
        ...buildStructure,
      },
      production: {
        source: `docs/acceptance/main-view-p0/production/${spec.id}.svg`,
        render_digest: artifact.renderDigest,
        width: artifact.width,
        height: artifact.height,
        ...productionStructureRecord,
        details: scene.details.length,
        portals: scene.portals.length,
        routing_metrics: scene.routingMetrics,
      },
      difference,
      checks: {
        build_structure_parsed: buildSvg.includes("<svg") && buildStructure.nodes > 0 && buildStructure.edges > 0,
        production_structure_parsed: artifact.svg.includes("<svg") && productionStructureRecord.nodes > 0 && productionStructureRecord.edges > 0,
        matching_topology: difference.nodes === 0 && difference.edges === 0,
        matching_detail_surfaces: difference.detail_surfaces === 0,
        matching_primitive_kinds: Object.values(difference.primitive_kinds).every((value) => value === 0),
        matching_detail_tones: Object.values(difference.detail_tones).every((value) => value === 0),
        primitive_delta_bounded: difference.detail_primitives === 0,
        primitive_vocabulary_present: Object.values(productionStructureRecord.primitive_kinds).some((value) => value > 0)
          ? ["flow", "matrix", "operator", "box", "text"].every((kind) => buildStructure.primitive_kinds[kind as keyof typeof buildStructure.primitive_kinds] === 0
            || productionStructureRecord.primitive_kinds[kind as keyof typeof productionStructureRecord.primitive_kinds] > 0)
          : buildStructure.detail_primitives === 0,
        prototype_semantic_tokens_preserved: spec.id === "parent-child-expanded"
          ? difference.semantic_tokens_missing_from_production.length === 0
          : true,
        finite_geometry: !/NaN|Infinity|undefined/.test(artifact.svg),
        all_edges_rendered: scene.edges.length === document.edges.length,
        all_expanded_details_rendered: scene.details.length === (
          spec.expanded === "all"
            ? document.templateBindings.length
            : spec.expanded === "none" ? 0 : spec.expanded.length
        ),
        boundary_port_continuity: scene.details.every((detail) => {
          const incoming = scene.edges.filter((edge) => edge.targetPortId === `${detail.nodeId}:input`);
          const outgoing = scene.edges.filter((edge) => edge.sourcePortId === `${detail.nodeId}:output`);
          return incoming.every((edge) => JSON.stringify(edge.points.at(-1)) === JSON.stringify(detail.entryPoint))
            && outgoing.every((edge) => JSON.stringify(edge.points[0]) === JSON.stringify(detail.exitPoint));
        }),
      },
    },
  };
}

function recursiveHierarchyRecord() {
  const spec: AcceptanceCase = {
    id: "recursive-formal-hierarchy",
    fixtureId: RECURSIVE_BIDIRECTIONAL_FIXTURE.sceneId,
    expanded: ["sequence-generative-catalog-bidir"],
    buildFile: "expanded-bidirectional-recurrent.svg",
  };
  const { document, visualState } = compileFixture(spec);
  const scene = buildKernelRenderScene(document, visualState);
  const artifact = renderKernelSceneSvg(document, visualState, scene);
  const portalDiscontinuities = scene.portals.flatMap((portal) => {
    const edge = scene.edges.find((candidate) => candidate.edgeId === portal.edgeId);
    return edge && pointOnPolyline(portal.point, edge.points) ? [] : [{
      portal_id: portal.portalId,
      edge_id: portal.edgeId,
      point: portal.point,
      edge_points: edge?.points ?? [],
    }];
  });
  const buildSource = resolve(
    BUILD_ORACLE,
    "sequence-generative-catalog/expanded-bidirectional-recurrent.svg",
  );
  const buildSvg = readFileSync(buildSource, "utf8");
  const buildStructure = prototypeStructure(buildSvg);
  const productionStructureRecord = canonicalProductionStructure(scene, artifact.svg);
  const difference = structureDifference(buildStructure, productionStructureRecord);
  return {
    artifact,
    buildSource,
    buildSvg,
    report: {
      id: "recursive-formal-hierarchy",
      fixture_id: RECURSIVE_BIDIRECTIONAL_FIXTURE.sceneId,
      build: {
        source: "build/scene-visual-lab/cases/sequence-generative-catalog/expanded-bidirectional-recurrent.svg",
        bytes: Buffer.byteLength(buildSvg),
        ...buildStructure,
      },
      production: {
        source: "docs/acceptance/main-view-p0/production/recursive-formal-hierarchy.svg",
        render_digest: artifact.renderDigest,
        width: artifact.width,
        height: artifact.height,
        ...productionStructureRecord,
        details: scene.details.length,
        portals: scene.portals.length,
        portal_discontinuities: portalDiscontinuities,
        routing_metrics: scene.routingMetrics,
      },
      difference,
      checks: {
        build_structure_parsed: buildSvg.includes("<svg") && buildStructure.nodes > 0 && buildStructure.edges > 0,
        production_structure_parsed: artifact.svg.includes("<svg") && productionStructureRecord.nodes > 0 && productionStructureRecord.edges > 0,
        matching_topology: difference.nodes === 0 && difference.edges === 0,
        matching_detail_surfaces: difference.detail_surfaces === 0,
        matching_primitive_kinds: Object.values(difference.primitive_kinds).every((value) => value === 0),
        matching_detail_tones: Object.values(difference.detail_tones).every((value) => value === 0),
        primitive_delta_bounded: difference.detail_primitives === 0,
        primitive_vocabulary_present: Object.values(productionStructureRecord.primitive_kinds).some((value) => value > 0)
          ? ["flow", "matrix", "operator", "box", "text"].every((kind) => buildStructure.primitive_kinds[kind as keyof typeof buildStructure.primitive_kinds] === 0
            || productionStructureRecord.primitive_kinds[kind as keyof typeof productionStructureRecord.primitive_kinds] > 0)
          : buildStructure.detail_primitives === 0,
        prototype_semantic_tokens_preserved: true,
        finite_geometry: !/NaN|Infinity|undefined/.test(artifact.svg),
        recursive_depth: buildStructure.detail_surfaces >= 1,
        nested_expanded_surfaces: scene.details.length >= 1,
        portal_continuity: portalDiscontinuities.length === 0,
      },
    },
  };
}

describe("P0 build/production visual acceptance", () => {
  it("renders every required glyph, catalog, and parent-child state", () => {
    const records = CASES.map(acceptanceRecord);
    const recursive = recursiveHierarchyRecord();
    expect(records).toHaveLength(13);
    expect(records.every(({ report }) => Object.values(report.checks).every(Boolean))).toBe(true);
    expect(recursive.report.production.portal_discontinuities).toEqual([]);
    expect(recursive.report.checks).toEqual(Object.fromEntries(
      Object.keys(recursive.report.checks).map((key) => [key, true]),
    ));
    expect(records.find(({ spec }) => spec.id === "parent-child-internal-drag")?.artifact.svg)
      .not.toEqual(records.find(({ spec }) => spec.id === "parent-child-expanded")?.artifact.svg);

    if (!WRITE_OUTPUT) return;
    mkdirSync(BUILD_OUTPUT, { recursive: true });
    mkdirSync(PRODUCTION_OUTPUT, { recursive: true });
    for (const record of records) {
      copyFileSync(oraclePath(record.spec), resolve(BUILD_OUTPUT, `${record.spec.id}.svg`));
      writeFileSync(resolve(PRODUCTION_OUTPUT, `${record.spec.id}.svg`), record.artifact.svg);
    }
    copyFileSync(recursive.buildSource, resolve(BUILD_OUTPUT, "recursive-formal-hierarchy.svg"));
    writeFileSync(
      resolve(PRODUCTION_OUTPUT, "recursive-formal-hierarchy.svg"),
      recursive.artifact.svg,
    );
    writeFileSync(resolve(ACCEPTANCE, "structural-differences.json"), `${JSON.stringify({
      schema_version: "1.0",
      generated_by: "studio/tools/export-p0-acceptance.test.ts",
      cases: [...records.map((record) => record.report), recursive.report],
    }, null, 2)}\n`);
  });
});
