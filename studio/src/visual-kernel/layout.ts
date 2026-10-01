import { routeRenderEdge, routeRenderEdges } from "./routing";
import { layoutHierarchy } from "./detail-layout";
import { buildTemplateDetail } from "./template-details";
import type { KernelDocument, KernelRenderScene, KernelVisualState, RenderNode, RenderPortal } from "./types";

const PAPER_PADDING = 72;

function boundarySide(
  point: { x: number; y: number },
  bounds: { x: number; y: number; width: number; height: number },
) {
  return ([
    ["left", Math.abs(point.x - bounds.x)],
    ["right", Math.abs(point.x - bounds.x - bounds.width)],
    ["top", Math.abs(point.y - bounds.y)],
    ["bottom", Math.abs(point.y - bounds.y - bounds.height)],
  ] as const).reduce((best, candidate) => candidate[1] < best[1] ? candidate : best)[0];
}

export function buildKernelRenderScene(
  document: KernelDocument,
  visualState: KernelVisualState,
): KernelRenderScene {
  const byPort = new Map(document.ports.map((port) => [port.portId, port]));
  const renderNodes = layoutHierarchy(document, visualState);
  const renderNodeById = new Map(renderNodes.map((node) => [node.nodeId, node]));
  const bindingById = new Map(document.templateBindings.map((binding) => [binding.bindingId, binding]));
  const incomingNodeIds = new Set(document.edges.flatMap((edge) => {
    const ownerNodeId = byPort.get(edge.targetPortId)?.ownerNodeId;
    return ownerNodeId ? [ownerNodeId] : [];
  }));
  const outgoingNodeIds = new Set(document.edges.flatMap((edge) => {
    const ownerNodeId = byPort.get(edge.sourcePortId)?.ownerNodeId;
    return ownerNodeId ? [ownerNodeId] : [];
  }));
  const details = renderNodes.flatMap((node) => {
    if (node.renderRole !== "expanded-module") return [];
    const detail = buildTemplateDetail(
      node.nodeId,
      bindingById.get(node.templateBindingId ?? ""),
      node.bounds,
      visualState.detailOffsets,
      visualState.detailExpansionTrees?.[node.nodeId],
      {
        mode: visualState.hierarchyRoutingMode,
        hasIncoming: incomingNodeIds.has(node.nodeId),
        hasOutgoing: outgoingNodeIds.has(node.nodeId),
      },
    );
    return detail ? [detail] : [];
  });
  const detailBoundaryPorts = Object.fromEntries(details.map((detail) => [detail.nodeId, {
    entry: detail.entryPoint,
    exit: detail.exitPoint,
    entrySide: detail.entrySide ?? boundarySide(detail.entryPoint, detail.bounds),
    exitSide: detail.exitSide ?? boundarySide(detail.exitPoint, detail.bounds),
    entryIsInterior: detail.entryIsInterior,
    exitIsInterior: detail.exitIsInterior,
  }]));
  const expandedAncestors = (node: RenderNode): RenderNode[] => {
    const result: RenderNode[] = [];
    let parentId = node.parentNodeId;
    while (parentId) {
      const parent = renderNodeById.get(parentId);
      if (!parent) break;
      if (parent.renderRole === "expanded-module") result.push(parent);
      parentId = parent.parentNodeId;
    }
    return result;
  };
  const portals: RenderPortal[] = [];
  const regularRecords: Array<{
    edge: Parameters<typeof routeRenderEdge>[0];
    source: RenderNode;
    target: RenderNode;
  }> = [];
  const portalEdges: ReturnType<typeof routeRenderEdge>[] = [];
  document.edges.forEach((edge) => {
    const sourceId = byPort.get(edge.sourcePortId)?.ownerNodeId;
    const targetId = byPort.get(edge.targetPortId)?.ownerNodeId;
    const source = sourceId ? renderNodeById.get(sourceId) : undefined;
    const target = targetId ? renderNodeById.get(targetId) : undefined;
    if (!source || !target) return;
    const sourceAncestors = expandedAncestors(source);
    const targetAncestors = expandedAncestors(target);
    const sourceAncestorIds = new Set(sourceAncestors.map((node) => node.nodeId));
    const targetAncestorIds = new Set(targetAncestors.map((node) => node.nodeId));
    const clampPortalY = (module: RenderNode, desired: number) => Math.max(
      module.bounds.y + 68,
      Math.min(module.bounds.y + module.bounds.height - 18, desired),
    );
    const sourceCenterY = source.bounds.y + source.bounds.height / 2;
    const targetCenterY = target.bounds.y + target.bounds.height / 2;
    const sourcePortals = sourceAncestors.filter((module) => !targetAncestorIds.has(module.nodeId)).map((module, index) => ({
      portalId: `${edge.edgeId}:exit:${index}`,
      moduleNodeId: module.nodeId,
      edgeId: edge.edgeId,
      direction: "exit" as const,
      point: { x: module.bounds.x + module.bounds.width, y: clampPortalY(module, sourceCenterY) },
    }));
    const targetPortals = targetAncestors.filter((module) => !sourceAncestorIds.has(module.nodeId)).reverse().map((module, index) => ({
      portalId: `${edge.edgeId}:entry:${index}`,
      moduleNodeId: module.nodeId,
      edgeId: edge.edgeId,
      direction: "entry" as const,
      point: { x: module.bounds.x, y: clampPortalY(module, targetCenterY) },
    }));
    const edgePortals = [...sourcePortals, ...targetPortals];
    portals.push(...edgePortals);
    if (edgePortals.length > 0) {
      portalEdges.push(routeRenderEdge(edge, source, target, visualState.routeStyle, edgePortals.map((portal) => portal.point)));
    } else {
      regularRecords.push({ edge, source, target });
    }
  });
  const routed = routeRenderEdges(
    regularRecords,
    renderNodes,
    visualState.routeStyle,
    detailBoundaryPorts,
  );
  const renderEdges = [...routed.edges, ...portalEdges].sort((left, right) => left.edgeId.localeCompare(right.edgeId));
  const maxX = visualState.paperSize?.width
    ?? Math.max(640, ...renderNodes.map((node) => node.bounds.x + node.bounds.width + PAPER_PADDING));
  const maxY = visualState.paperSize?.height
    ?? Math.max(520, ...renderNodes.map((node) => node.bounds.y + node.bounds.height + PAPER_PADDING));
  return {
    sceneId: `kernel:${document.architectureId}:${document.sourceDigest.slice(0, 12)}`,
    sourceDigest: document.sourceDigest,
    width: maxX,
    height: maxY,
    nodes: renderNodes,
    edges: renderEdges,
    portals,
    details,
    routingMetrics: routed.metrics,
    diagnostics: document.diagnostics,
  };
}
