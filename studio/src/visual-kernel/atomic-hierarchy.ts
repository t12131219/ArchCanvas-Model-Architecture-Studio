import { inlineExpandedChildren } from "./recursive-detail-layout";
import type { InlineDetailLevel } from "./recursive-detail-layout";
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
  side: PortSide;
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

export interface ProjectedAtomicEntry {
  atomId?: string;
  point: Point;
  side: PortSide;
  bridgeEdgeIds: string[];
}

export interface AtomicHierarchyRoutingPlan {
  projections: Record<string, AtomicHierarchyProjection>;
  boundaryPorts: SceneBoundaryPortMap;
  hiddenFlowIds: Set<string>;
  foregroundFlowIds: Set<string>;
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
  const expandedChildren = inlineExpandedChildren(level);
  const expandedIds = new Set(expandedChildren.map((child) => child.node.id));
  const node = level.nodes.find((candidate) => (
    !expandedIds.has(candidate.id) && pointOnBounds(point, candidate.bounds)
  ));
  if (node) return `${level.levelKey}:atom:${node.primitiveIndex}`;
  for (const child of expandedChildren) {
    const atomId = descendantAtomIdAt(child.level, point);
    if (atomId) return atomId;
  }
  return undefined;
}

function endpointId(level: InlineDetailLevel, point: Point): string {
  if (samePoint(point, level.diagram.entryPoint)) return `${level.levelKey}:portal:entry`;
  if (samePoint(point, level.diagram.exitPoint)) return `${level.levelKey}:portal:exit`;
  const node = level.nodes.find((candidate) => pointOnBounds(point, candidate.bounds));
  const expandedChildren = inlineExpandedChildren(level);
  const expanded = node ? expandedChildren.find((child) => child.node.id === node.id) : undefined;
  if (node && expanded) {
    const childLevelKey = expanded.level.levelKey;
    const entry = expanded.level.diagram.entryPoint;
    const exit = expanded.level.diagram.exitPoint;
    const entrySide = pointSide(entry, expanded.level.bounds);
    const exitSide = pointSide(exit, expanded.level.bounds);
    const horizontal = ["left", "right"].includes(entrySide) && ["left", "right"].includes(exitSide);
    const vertical = ["top", "bottom"].includes(entrySide) && ["top", "bottom"].includes(exitSide);
    if (horizontal && entrySide !== exitSide) {
      return `${childLevelKey}:portal:${Math.abs(point.x - entry.x) <= Math.abs(point.x - exit.x) ? "entry" : "exit"}`;
    }
    if (vertical && entrySide !== exitSide) {
      return `${childLevelKey}:portal:${Math.abs(point.y - entry.y) <= Math.abs(point.y - exit.y) ? "entry" : "exit"}`;
    }
    const entryDistance = Math.hypot(point.x - entry.x, point.y - entry.y);
    const exitDistance = Math.hypot(point.x - exit.x, point.y - exit.y);
    return `${childLevelKey}:portal:${entryDistance <= exitDistance ? "entry" : "exit"}`;
  }
  const descendantAtomId = expandedChildren
    .map((child) => descendantAtomIdAt(child.level, point))
    .find(Boolean);
  if (descendantAtomId) return descendantAtomId;
  return node
    ? `${level.levelKey}:atom:${node.primitiveIndex}`
    : `${level.levelKey}:junction:${point.x.toFixed(3)},${point.y.toFixed(3)}`;
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
    const expandedChildren = inlineExpandedChildren(level);
    const expandedIds = new Set(expandedChildren.map((child) => child.node.id));
    for (const node of level.nodes) {
      if (expandedIds.has(node.id)) continue;
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
        sourceId: endpointId(level, first),
        targetId: endpointId(level, last),
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
      side: pointSide(level.diagram.entryPoint, level.bounds),
      point: { ...level.diagram.entryPoint },
      atomicEdgeIds: edgeIdsAt(level.diagram.entryPoint),
    }, {
      portalId: `${level.levelKey}:portal:exit`,
      moduleId: level.levelKey,
      parentModuleId,
      hostNodeId,
      side: pointSide(level.diagram.exitPoint, level.bounds),
      point: { ...level.diagram.exitPoint },
      atomicEdgeIds: edgeIdsAt(level.diagram.exitPoint),
    });

    for (const child of expandedChildren) {
      portalChains.push({
        chainId: `${level.levelKey}:child:${child.node.id}`,
        parentModuleId: level.levelKey,
        childModuleId: child.level.levelKey,
        hostNodeId: child.node.id,
        entryPortalId: `${child.level.levelKey}:portal:entry`,
        exitPortalId: `${child.level.levelKey}:portal:exit`,
      });
      visit(child.level, level.levelKey, child.node.id);
    }
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
    entrySide: pointSide(level.diagram.entryPoint, level.bounds),
    exitSide: pointSide(level.diagram.exitPoint, level.bounds),
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
    portal.portalId === `${moduleId}:portal:exit`
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

export function projectedAtomicEntryForModule(
  projection: AtomicHierarchyProjection,
  moduleId: string,
): ProjectedAtomicEntry | undefined {
  const moduleEntry = projection.portals.find((portal) => (
    portal.portalId === `${moduleId}:portal:entry`
  ));
  if (!moduleEntry) return undefined;

  let cursorId = moduleEntry.portalId;
  let cursorPoint = moduleEntry.point;
  const visited = new Set<string>();
  const bridgeEdgeIds: string[] = [];
  for (let depth = 0; depth <= projection.edges.length; depth += 1) {
    const exact = projection.edges.filter((edge) => !visited.has(edge.atomicEdgeId) && edge.sourceId === cursorId);
    const candidates = exact.length ? exact : projection.edges.filter((edge) => (
      !visited.has(edge.atomicEdgeId) && samePoint(edge.points[0], cursorPoint)
    ));
    if (candidates.length !== 1) return undefined;

    const edge = candidates[0];
    visited.add(edge.atomicEdgeId);
    bridgeEdgeIds.push(edge.atomicEdgeId);
    const targetNode = projection.nodes.find((node) => node.atomId === edge.targetId);
    if (targetNode) {
      return {
        atomId: targetNode.atomId,
        point: { ...edge.points.at(-1)! },
        side: pointSide(edge.points.at(-1)!, targetNode.bounds),
        bridgeEdgeIds,
      };
    }

    const next = projection.edges.filter((candidate) => (
      !visited.has(candidate.atomicEdgeId)
      && (candidate.sourceId === edge.targetId || samePoint(candidate.points[0], edge.points.at(-1)!))
    ));
    if (next.length !== 1) {
      return next.length > 1
        ? { point: { ...moduleEntry.point }, side: moduleEntry.side, bridgeEdgeIds: [] }
        : undefined;
    }
    cursorId = edge.targetId;
    cursorPoint = edge.points.at(-1)!;
  }
  return undefined;
}

export function projectedAtomicEntry(
  projection: AtomicHierarchyProjection,
): ProjectedAtomicEntry | undefined {
  return projectedAtomicEntryForModule(projection, projection.rootId);
}

export function projectedNestedExitBridgeIds(
  projection: AtomicHierarchyProjection,
): string[] {
  return [...new Set(projection.portalChains.flatMap((chain) => (
    projectedAtomicExitForModule(projection, chain.childModuleId)?.bridgeEdgeIds ?? []
  )))];
}

export function projectedNestedEntryBridgeIds(
  projection: AtomicHierarchyProjection,
): string[] {
  return [...new Set(projection.portalChains.flatMap((chain) => (
    projectedAtomicEntryForModule(projection, chain.childModuleId)?.bridgeEdgeIds ?? []
  )))];
}

function endpointModuleId(
  projection: AtomicHierarchyProjection,
  endpointId: string,
): string | undefined {
  return projection.nodes.find((node) => node.atomId === endpointId)?.levelKey
    ?? projection.portals.find((portal) => portal.portalId === endpointId)?.moduleId;
}

export function projectedCrossLevelEdgeIds(
  projection: AtomicHierarchyProjection,
): string[] {
  return projection.edges.flatMap((edge) => {
    const sourceModuleId = endpointModuleId(projection, edge.sourceId);
    const targetModuleId = endpointModuleId(projection, edge.targetId);
    return sourceModuleId && sourceModuleId !== edge.levelKey
      || targetModuleId && targetModuleId !== edge.levelKey
      ? [edge.atomicEdgeId]
      : [];
  });
}

export function projectedSceneBoundaryPorts(
  projections: Readonly<Record<string, AtomicHierarchyProjection>>,
): SceneBoundaryPortMap {
  return Object.fromEntries(Object.entries(projections).flatMap(([nodeId, projection]) => {
    const entry = projection.portals.find((portal) => (
      portal.portalId === `${projection.rootId}:portal:entry`
    ));
    const exit = projection.portals.find((portal) => (
      portal.portalId === `${projection.rootId}:portal:exit`
    ));
    const atomicEntry = projectedAtomicEntry(projection);
    const atomicExit = projectedAtomicExit(projection);
    return entry && exit ? [[nodeId, {
      entry: { ...(atomicEntry?.point ?? entry.point) },
      exit: { ...(atomicExit?.point ?? exit.point) },
      entrySide: atomicEntry?.side ?? entry.side,
      exitSide: atomicExit?.side ?? exit.side,
      entryIsInterior: Boolean(atomicEntry?.atomId),
      exitIsInterior: Boolean(atomicExit),
    }]] : [];
  }));
}

export function buildAtomicHierarchyRoutingPlan(
  detailTrees: Readonly<Record<string, InlineDetailLevel>>,
  incomingNodeIds: ReadonlySet<string>,
  outgoingNodeIds: ReadonlySet<string>,
): AtomicHierarchyRoutingPlan {
  const projections = Object.fromEntries(Object.entries(detailTrees).map(([nodeId, tree]) => [
    nodeId,
    buildAtomicHierarchyProjection(tree),
  ]));
  const boundaryPorts = projectedSceneBoundaryPorts(projections);
  for (const [nodeId, tree] of Object.entries(detailTrees)) {
    const ports = boundaryPorts[nodeId];
    if (!ports || !tree.diagram.semanticInputPorts) continue;
    ports.semanticInputs = Object.fromEntries(Object.entries(tree.diagram.semanticInputPorts).map(([role, port]) => [
      role,
      {
        point: { ...port.point },
        side: port.side,
        isInterior: !pointOnBounds(port.point, tree.bounds),
      },
    ]));
  }
  const hiddenFlowIds = new Set(Object.entries(projections).flatMap(([nodeId, projection]) => [
    ...projectedNestedEntryBridgeIds(projection),
    ...projectedNestedExitBridgeIds(projection),
    ...(incomingNodeIds.has(nodeId) ? projectedAtomicEntry(projection)?.bridgeEdgeIds ?? [] : []),
    ...(outgoingNodeIds.has(nodeId) ? projectedAtomicExit(projection)?.bridgeEdgeIds ?? [] : []),
  ]));
  return {
    projections,
    boundaryPorts,
    hiddenFlowIds,
    foregroundFlowIds: new Set(Object.values(projections).flatMap(projectedCrossLevelEdgeIds)),
  };
}
