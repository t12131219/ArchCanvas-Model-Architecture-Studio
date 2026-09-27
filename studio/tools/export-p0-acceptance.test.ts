import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { adaptFormalState } from "../src/main-view/formal-state-adapter";
import type { FormalStudioState } from "../src/app/studio-types";
import { renderKernelSceneSvg } from "../src/visual-kernel/export";
import { buildKernelRenderScene } from "../src/visual-kernel/layout";
import {
  DEFAULT_OPTIONS,
  PRODUCTION_FIXTURES,
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
  const fixture = PRODUCTION_FIXTURES.find((candidate) => candidate.sceneId === spec.fixtureId);
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
      ...DEFAULT_OPTIONS,
    },
  };
}

function count(svg: string, expression: RegExp): number {
  return [...svg.matchAll(expression)].length;
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
  return resolve(BUILD_ORACLE, spec.fixtureId, spec.buildFile);
}

function acceptanceRecord(spec: AcceptanceCase) {
  const { document, visualState } = compileFixture(spec);
  const scene = buildKernelRenderScene(document, visualState);
  const artifact = renderKernelSceneSvg(document, visualState, scene);
  const buildSvg = readFileSync(oraclePath(spec), "utf8");
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
        nodes: count(buildSvg, /class="lab-node/g),
        edges: count(buildSvg, /class="lab-edge/g),
        detail_primitives: count(buildSvg, /class="detail-(?:shape|matrix|text)/g),
      },
      production: {
        source: `docs/acceptance/main-view-p0/production/${spec.id}.svg`,
        render_digest: artifact.renderDigest,
        width: artifact.width,
        height: artifact.height,
        nodes: scene.nodes.length,
        edges: scene.edges.length,
        details: scene.details.length,
        detail_primitives: scene.details.reduce((sum, detail) => sum + detail.primitives.length, 0),
        portals: scene.portals.length,
        routing_metrics: scene.routingMetrics,
      },
      checks: {
        build_nonempty: buildSvg.includes("<svg"),
        production_nonempty: artifact.svg.includes("<svg"),
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
  const state = JSON.parse(readFileSync(
    resolve(REPOSITORY, "studio/src/main-view/fixtures/transformer.json"),
    "utf8",
  )) as FormalStudioState;
  const adapted = adaptFormalState(state);
  const scene = buildKernelRenderScene(adapted.document, adapted.visualState);
  const artifact = renderKernelSceneSvg(adapted.document, adapted.visualState, scene);
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
  return {
    artifact,
    buildSource,
    buildSvg,
    report: {
      id: "recursive-formal-hierarchy",
      fixture_id: "transformer",
      build: {
        source: "build/scene-visual-lab/cases/sequence-generative-catalog/expanded-bidirectional-recurrent.svg",
        bytes: Buffer.byteLength(buildSvg),
        nodes: count(buildSvg, /class="lab-node/g),
        edges: count(buildSvg, /class="lab-edge/g),
        detail_primitives: count(buildSvg, /class="detail-(?:shape|matrix|text)/g),
      },
      production: {
        source: "docs/acceptance/main-view-p0/production/recursive-formal-hierarchy.svg",
        render_digest: artifact.renderDigest,
        width: artifact.width,
        height: artifact.height,
        nodes: scene.nodes.length,
        edges: scene.edges.length,
        details: scene.details.length,
        detail_primitives: scene.details.reduce((sum, detail) => sum + detail.primitives.length, 0),
        portals: scene.portals.length,
        portal_discontinuities: portalDiscontinuities,
        routing_metrics: scene.routingMetrics,
      },
      checks: {
        build_nonempty: buildSvg.includes("<svg"),
        production_nonempty: artifact.svg.includes("<svg"),
        finite_geometry: !/NaN|Infinity|undefined/.test(artifact.svg),
        recursive_depth: scene.nodes.some((node) => node.depth >= 2),
        nested_expanded_surfaces: scene.nodes.filter((node) => node.renderRole === "expanded-module").length >= 2,
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
