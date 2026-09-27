import { routeRenderEdge } from "./routing";
import { layoutHierarchy } from "./detail-layout";
import { buildTemplateDetail } from "./template-details";
import type { KernelDocument, KernelRenderScene, KernelVisualState, RenderNode, RenderPortal } from "./types";

const PAPER_PADDING = 72;

export function buildKernelRenderScene(
  document: KernelDocument,
  visualState: KernelVisualState,
): KernelRenderScene {
  const byPort = new Map(document.ports.map((port) => [port.portId, port]));
  const renderNodes = layoutHierarchy(document, visualState);
  const renderNodeById = new Map(renderNodes.map((node) => [node.nodeId, node]));
  const bindingById = new Map(document.templateBindings.map((binding) => [binding.bindingId, binding]));
  const details = renderNodes.flatMap((node) => {
    if (node.renderRole !== "expanded-module") return [];
    const detail = buildTemplateDetail(node.nodeId, bindingById.get(node.templateBindingId ?? ""), node.bounds, visualState.detailOffsets);
    return detail ? [detail] : [];
  });
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
  const renderEdges = document.edges.flatMap((edge) => {
    const sourceId = byPort.get(edge.sourcePortId)?.ownerNodeId;
    const targetId = byPort.get(edge.targetPortId)?.ownerNodeId;
    const source = sourceId ? renderNodeById.get(sourceId) : undefined;
    const target = targetId ? renderNodeById.get(targetId) : undefined;
    if (!source || !target) return [];
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
    portals.push(...sourcePortals, ...targetPortals);
    return [routeRenderEdge(edge, source, target, visualState.routeStyle, [...sourcePortals, ...targetPortals].map((portal) => portal.point))];
  });
  const maxX = Math.max(640, ...renderNodes.map((node) => node.bounds.x + node.bounds.width + PAPER_PADDING));
  const maxY = Math.max(520, ...renderNodes.map((node) => node.bounds.y + node.bounds.height + PAPER_PADDING));
  return {
    sceneId: `kernel:${document.architectureId}:${document.sourceDigest.slice(0, 12)}`,
    sourceDigest: document.sourceDigest,
    width: maxX,
    height: maxY,
    nodes: renderNodes,
    edges: renderEdges,
    portals,
    details,
    diagnostics: document.diagnostics,
  };
}
