import type { InlineDetailLevel } from "./detail-layout";
import type { Bounds, Point, PortSide, SceneBoundaryPortMap } from "./types";

export interface AtomicNodeRecord {
  atomId: string;
  levelKey: string;
  primitiveIndex: number;
  label: string;
  semanticKind: string;
  bounds: Bounds;
}

export interface AtomicEdgeRecord {
  atomicEdgeId: string;
  levelKey: string;
  primitiveIndex: number;
  sourceId: string;
  targetId: string;
  semanticChannel: string;
  points: Point[];
  markerEnd: boolean;
}

export interface BoundaryPortal {
  portalId: string;
  moduleId: string;
  parentModuleId?: string;
  hostNodeId?: string;
  side: "left" | "right";
  point: Point;
  atomicEdgeIds: string[];
}

export interface PortalChain {
  chainId: string;
  parentModuleId: string;
  childModuleId: string;
  hostNodeId: string;
  entryPortalId: string;
  exitPortalId: string;
}

export interface AtomicHierarchyProjection {
  rootId: string;
  nodes: AtomicNodeRecord[];
  edges: AtomicEdgeRecord[];
  portals: BoundaryPortal[];
  portalChains: PortalChain[];
}

export interface ProjectedAtomicExit {
  atomId: string;
  point: Point;
  side: PortSide;
  bridgeEdgeIds: string[];
}

function samePoint(first: Point, second: Point): boolean {
  return Math.abs(first.x - second.x) < 0.01 && Math.abs(first.y - second.y) < 0.01;
}

function pointOnBounds(point: Point, bounds: Bounds): boolean {
  const onVertical = (Math.abs(point.x - bounds.x) < 0.01
    || Math.abs(point.x - bounds.x - bounds.width) < 0.01)
    && point.y >= bounds.y - 0.01
    && point.y <= bounds.y + bounds.height + 0.01;
  const onHorizontal = (Math.abs(point.y - bounds.y) < 0.01
    || Math.abs(point.y - bounds.y - bounds.height) < 0.01)
    && point.x >= bounds.x - 0.01
    && point.x <= bounds.x + bounds.width + 0.01;
  return onVertical || onHorizontal;
}

function descendantAtomIdAt(level: InlineDetailLevel, point: Point): string | undefined {
  const expandedId = level.expandedChild?.node.id;
  const node = level.nodes.find((candidate) => (
    candidate.id !== expandedId && pointOnBounds(point, candidate.bounds)
  ));
  if (node) return `${level.levelKey}:atom:${node.primitiveIndex}`;
  return level.expandedChild ? descendantAtomIdAt(level.expandedChild.level, point) : undefined;
}

function endpointId(level: InlineDetailLevel, point: Point, edgeIndex: number, role: "source" | "target"): string {
  if (samePoint(point, level.diagram.entryPoint)) return `${level.levelKey}:portal:entry`;
  if (samePoint(point, level.diagram.exitPoint)) return `${level.levelKey}:portal:exit`;
  const node = level.nodes.find((candidate) => pointOnBounds(point, candidate.bounds));
  if (node && level.expandedChild?.node.id === node.id) {
    const childLevelKey = level.expandedChild.level.levelKey;
    const leftDistance = Math.abs(point.x - node.bounds.x);
    const rightDistance = Math.abs(point.x - node.bounds.x - node.bounds.width);
    return `${childLevelKey}:portal:${leftDistance <= rightDistance ? "entry" : "exit"}`;
  }
  const descendantAtomId = level.expandedChild
    ? descendantAtomIdAt(level.expandedChild.level, point)
    : undefined;
  if (descendantAtomId) return descendantAtomId;
  return node
    ? `${level.levelKey}:atom:${node.primitiveIndex}`
    : `${level.levelKey}:junction:${edgeIndex}:${role}`;
}

export function buildAtomicHierarchyProjection(root: InlineDetailLevel): AtomicHierarchyProjection {
  const nodes: AtomicNodeRecord[] = [];
  const edges: AtomicEdgeRecord[] = [];
  const portals: BoundaryPortal[] = [];
  const portalChains: PortalChain[] = [];

  const visit = (
    level: InlineDetailLevel,
    parentModuleId?: string,
    hostNodeId?: string,
  ) => {
    const expandedId = level.expandedChild?.node.id;
    for (const node of level.nodes) {
      if (node.id === expandedId) continue;
      nodes.push({
        atomId: `${level.levelKey}:atom:${node.primitiveIndex}`,
        levelKey: level.levelKey,
        primitiveIndex: node.primitiveIndex,
        label: node.label,
        semanticKind: node.nestedKind ?? node.primitive.kind,
        bounds: { ...node.bounds },
      });
    }

    const levelEdges = level.diagram.primitives.flatMap((primitive, primitiveIndex) => {
      if (primitive.kind !== "flow") return [];
      const atomicEdgeId = `${level.levelKey}:flow:${primitiveIndex}`;
      const first = primitive.points[0];
      const last = primitive.points.at(-1)!;
      const edge: AtomicEdgeRecord = {
        atomicEdgeId,
        levelKey: level.levelKey,
        primitiveIndex,
        sourceId: endpointId(level, first, primitiveIndex, "source"),
        targetId: endpointId(level, last, primitiveIndex, "target"),
        semanticChannel: `${primitive.channel ?? level.kind}:${primitiveIndex}`,
        points: primitive.points.map((point) => ({ ...point })),
        markerEnd: primitive.marker !== false,
      };
      return [edge];
    });
    edges.push(...levelEdges);

    const edgeIdsAt = (point: Point) => levelEdges
      .filter((edge) => samePoint(edge.points[0], point) || samePoint(edge.points.at(-1)!, point))
      .map((edge) => edge.atomicEdgeId);
    portals.push({
      portalId: `${level.levelKey}:portal:entry`,
      moduleId: level.levelKey,
      parentModuleId,
      hostNodeId,
      side: "left",
      point: { ...level.diagram.entryPoint },
      atomicEdgeIds: edgeIdsAt(level.diagram.entryPoint),
    }, {
      portalId: `${level.levelKey}:portal:exit`,
      moduleId: level.levelKey,
      parentModuleId,
      hostNodeId,
      side: "right",
      point: { ...level.diagram.exitPoint },
      atomicEdgeIds: edgeIdsAt(level.diagram.exitPoint),
    });

    if (!level.expandedChild) return;
    const child = level.expandedChild;
    portalChains.push({
      chainId: `${level.levelKey}:child:${child.node.id}`,
      parentModuleId: level.levelKey,
      childModuleId: child.level.levelKey,
      hostNodeId: child.node.id,
      entryPortalId: `${child.level.levelKey}:portal:entry`,
      exitPortalId: `${child.level.levelKey}:portal:exit`,
    });
    visit(child.level, level.levelKey, child.node.id);
  };

  visit(root);
  return { rootId: root.levelKey, nodes, edges, portals, portalChains };
}

export function sceneBoundaryPorts(
  detailTrees: Readonly<Record<string, InlineDetailLevel>>,
): SceneBoundaryPortMap {
  return Object.fromEntries(Object.entries(detailTrees).map(([nodeId, level]) => [nodeId, {
    entry: { ...level.diagram.entryPoint },
    exit: { ...level.diagram.exitPoint },
  }]));
}

function pointSide(point: Point, bounds: Bounds): PortSide {
  const distances: Array<{ side: PortSide; distance: number }> = [
    { side: "left", distance: Math.abs(point.x - bounds.x) },
    { side: "right", distance: Math.abs(point.x - bounds.x - bounds.width) },
    { side: "top", distance: Math.abs(point.y - bounds.y) },
    { side: "bottom", distance: Math.abs(point.y - bounds.y - bounds.height) },
  ];
  distances.sort((first, second) => first.distance - second.distance);
  return distances[0].side;
}

export function projectedAtomicExitForModule(
  projection: AtomicHierarchyProjection,
  moduleId: string,
): ProjectedAtomicExit | undefined {
  const moduleExit = projection.portals.find((portal) => (
    portal.moduleId === moduleId && portal.side === "right"
  ));
  if (!moduleExit) return undefined;

  let cursorId = moduleExit.portalId;
  let cursorPoint = moduleExit.point;
  const visited = new Set<string>();
  const bridgeEdgeIds: string[] = [];
  for (let depth = 0; depth <= projection.edges.length; depth += 1) {
    const exact = projection.edges.filter((edge) => !visited.has(edge.atomicEdgeId) && edge.targetId === cursorId);
    const candidates = exact.length ? exact : projection.edges.filter((edge) => (
      !visited.has(edge.atomicEdgeId) && samePoint(edge.points.at(-1)!, cursorPoint)
    ));
    if (candidates.length !== 1) return undefined;

    const edge = candidates[0];
    visited.add(edge.atomicEdgeId);
    bridgeEdgeIds.push(edge.atomicEdgeId);
    const sourceNode = projection.nodes.find((node) => node.atomId === edge.sourceId);
    if (sourceNode) {
      const point = { ...edge.points[0] };
      return {
        atomId: sourceNode.atomId,
        point,
        side: pointSide(point, sourceNode.bounds),
        bridgeEdgeIds,
      };
    }
    cursorId = edge.sourceId;
    cursorPoint = edge.points[0];
  }
  return undefined;
}

export function projectedAtomicExit(
  projection: AtomicHierarchyProjection,
): ProjectedAtomicExit | undefined {
  return projectedAtomicExitForModule(projection, projection.rootId);
}

export function projectedNestedExitBridgeIds(
  projection: AtomicHierarchyProjection,
): string[] {
  return [...new Set(projection.portalChains.flatMap((chain) => (
    projectedAtomicExitForModule(projection, chain.childModuleId)?.bridgeEdgeIds ?? []
  )))];
}

export function projectedSceneBoundaryPorts(
  projections: Readonly<Record<string, AtomicHierarchyProjection>>,
): SceneBoundaryPortMap {
  return Object.fromEntries(Object.entries(projections).flatMap(([nodeId, projection]) => {
    const entry = projection.portals.find((portal) => (
      portal.moduleId === projection.rootId && portal.side === "left"
    ));
    const exit = projection.portals.find((portal) => (
      portal.moduleId === projection.rootId && portal.side === "right"
    ));
    const atomicExit = projectedAtomicExit(projection);
    return entry && exit ? [[nodeId, {
      entry: { ...entry.point },
      exit: { ...(atomicExit?.point ?? exit.point) },
      entrySide: "left",
      exitSide: atomicExit?.side ?? "right",
      exitIsInterior: Boolean(atomicExit),
    }]] : [];
  }));
}
