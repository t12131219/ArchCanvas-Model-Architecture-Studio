import type {
  DraftEdge,
  DraftNode,
  ExactEdge,
  ExactNode,
  SceneBinding,
  SourceBackedScene,
  StudioStatePayload,
  ViewPresetId,
} from "../domain/source-backed-scene";
import { resolveDefinitionRef } from "../../module-registry/registry";
import { resolveViewPreset } from "../domain/view-preset";
import type { EdgeRelation, LabEdge, LabNode, NodeShape } from "../types";

interface ProjectedNode extends ExactNode {
  projected_canonical_node_ids?: string[];
}

interface ProjectedEdge extends ExactEdge {
  projected_canonical_edge_ids?: string[];
  projected_tensor_ids?: string[];
}

function unique(values: string[]): string[] {
  return [...new Set(values)].sort();
}

function nodeShape(node: ExactNode, glyph?: string): NodeShape {
  const kind = node.kind.toLowerCase();
  const semanticGlyph = String(glyph ?? node.attributes.glyph_id ?? node.attributes.glyph ?? "").toLowerCase();
  const opType = String(node.attributes.op_type ?? node.attributes.semantic_kind ?? node.attributes.source_kind ?? "").toLowerCase();
  if (["input", "output", "io", "input_output"].includes(kind)) return "io";
  if (kind.includes("tensor") || semanticGlyph === "tensor") return "tensor";
  if (kind.includes("condition") || semanticGlyph === "condition") return "condition";
  if (semanticGlyph.includes("attention")) return "attention";
  if (semanticGlyph.includes("norm") || /(^|\.)(layernorm|batchnorm|groupnorm|rmsnorm)$/.test(opType)) return "normalization";
  if (semanticGlyph.includes("conv") || /(^|\.)(conv1d|conv2d|conv3d|convolution)$/.test(opType)) return "convolution";
  if (semanticGlyph === "add" || kind === "merge_event" && opType.includes("add")) return "add";
  if (semanticGlyph === "multiply" || /(^|\.)(mul|multiply)$/.test(opType)) return "multiply";
  if (semanticGlyph === "concat" || /(^|\.)(cat|concat)$/.test(opType)) return "concat";
  if (kind.includes("merge")) return "merge";
  return "operation";
}

function canonicalIdsFor(node: ProjectedNode): string[] {
  return node.projected_canonical_node_ids ?? [node.node_id];
}

function canonicalEdgeIdsFor(edge: ProjectedEdge): string[] {
  return edge.projected_canonical_edge_ids ?? [edge.edge_id];
}

function tensorIdsFor(edge: ProjectedEdge): string[] {
  return edge.projected_tensor_ids ?? [edge.tensor_id];
}

function hierarchyFrontier(state: StudioStatePayload): { nodes: ProjectedNode[]; edges: ProjectedEdge[] } {
  if (!state.hierarchy.nodes.length) {
    return { nodes: state.architecture.nodes, edges: state.architecture.edges };
  }
  const hierarchyById = new Map(state.hierarchy.nodes.map((item) => [item.hierarchy_node_id, item]));
  const childrenById = new Map<string, string[]>();
  for (const item of state.hierarchy.nodes) {
    if (!item.parent_hierarchy_node_id) continue;
    childrenById.set(item.parent_hierarchy_node_id, [
      ...(childrenById.get(item.parent_hierarchy_node_id) ?? []),
      item.hierarchy_node_id,
    ]);
  }
  for (const children of childrenById.values()) children.sort();
  const closureCache = new Map<string, string[]>();
  const collectCanonical = (id: string, visiting = new Set<string>()): string[] => {
    const cached = closureCache.get(id);
    if (cached) return cached;
    if (visiting.has(id)) return [];
    visiting.add(id);
    const item = hierarchyById.get(id);
    const result = unique([
      ...(item?.canonical_node_ids ?? []),
      ...(childrenById.get(id) ?? []).flatMap((childId) => collectCanonical(childId, visiting)),
    ]);
    visiting.delete(id);
    closureCache.set(id, result);
    return result;
  };
  const expanded = new Set(state.view_state?.module_expansion ?? []);
  const rootId = hierarchyById.has(state.hierarchy.root_node_id)
    ? state.hierarchy.root_node_id
    : state.hierarchy.nodes.find((item) => !item.parent_hierarchy_node_id)?.hierarchy_node_id;
  if (!rootId) return { nodes: state.architecture.nodes, edges: state.architecture.edges };
  const frontierIds: string[] = [];
  const visit = (id: string, forceExpanded = false) => {
    const children = childrenById.get(id) ?? [];
    if (children.length && (forceExpanded || expanded.has(id))) {
      children.forEach((childId) => visit(childId));
      return;
    }
    frontierIds.push(id);
  };
  visit(rootId, true);
  const canonicalById = new Map(state.architecture.nodes.map((node) => [node.node_id, node]));
  const representativeByCanonical = new Map<string, string>();
  const nodes: ProjectedNode[] = frontierIds.flatMap((id) => {
    const item = hierarchyById.get(id);
    if (!item) return [];
    const canonicalIds = collectCanonical(id);
    canonicalIds.forEach((canonicalId) => representativeByCanonical.set(canonicalId, id));
    const facts = canonicalIds.map((canonicalId) => canonicalById.get(canonicalId)).filter((node): node is ExactNode => Boolean(node));
    const direct = item.canonical_node_ids.length === 1 ? canonicalById.get(item.canonical_node_ids[0]) : undefined;
    return [{
      node_id: id,
      semantic_name: item.semantic_name,
      kind: childrenById.has(id) ? "module_container" : direct?.kind ?? item.kind ?? "module_container",
      parent_id: item.parent_hierarchy_node_id,
      evidence_ids: unique([...(item.evidence_ids ?? []), ...facts.flatMap((fact) => fact.evidence_ids)]),
      attributes: {
        ...(direct?.attributes ?? {}),
        hierarchy_node_id: id,
        hierarchy_depth: item.depth,
        child_count: childrenById.get(id)?.length ?? 0,
        source_kind: childrenById.has(id) ? "module_container" : direct?.attributes.source_kind,
      },
      input_ports: direct?.input_ports ?? [],
      output_ports: direct?.output_ports ?? [],
      projected_canonical_node_ids: canonicalIds,
    }];
  });
  const groupedEdges = new Map<string, ExactEdge[]>();
  for (const edge of state.architecture.edges) {
    const source = representativeByCanonical.get(edge.producer_id);
    const target = representativeByCanonical.get(edge.consumer_id);
    if (!source || !target || source === target) continue;
    const key = `${source}\u0000${target}\u0000${edgeRelation(edge)}\u0000${edge.role}`;
    groupedEdges.set(key, [...(groupedEdges.get(key) ?? []), edge]);
  }
  const edges: ProjectedEdge[] = [...groupedEdges.entries()].map(([key, facts]) => {
    const [source, target, relation, role] = key.split("\u0000");
    const canonicalEdgeIds = facts.map((edge) => edge.edge_id).sort();
    return {
      edge_id: `frontier:${canonicalEdgeIds.join("+")}`,
      tensor_id: facts[0].tensor_id,
      producer_id: source,
      producer_port: facts[0].producer_port,
      consumer_id: target,
      consumer_port: facts[0].consumer_port,
      role,
      edge_type: relation,
      evidence_ids: unique(facts.flatMap((edge) => edge.evidence_ids)),
      projected_canonical_edge_ids: canonicalEdgeIds,
      projected_tensor_ids: unique(facts.map((edge) => edge.tensor_id)),
    };
  });
  return { nodes, edges };
}

function edgeRelation(edge: ExactEdge): EdgeRelation {
  const type = edge.edge_type.toLowerCase();
  const role = edge.role.toLowerCase();
  if (type.includes("residual") || role.includes("residual") || role.includes("skip")) return "residual";
  if (type.includes("condition") || role.includes("mask") || role.includes("condition") || role.includes("bias")) return "condition";
  if (type.includes("memory") || role.includes("memory")) return "memory";
  if (type.includes("feedback") || type.includes("state")) return "feedback";
  if (type.includes("merge") || role.includes("concat")) return "merge";
  if (type.includes("branch") || type.includes("fanout")) return "branch";
  return "flow";
}

function topologicalRanks(nodeIds: string[], edges: ExactEdge[]): Map<string, number> {
  const nodeSet = new Set(nodeIds);
  const outgoing = new Map<string, string[]>();
  const indegree = new Map(nodeIds.map((id) => [id, 0]));
  for (const edge of edges) {
    if (!nodeSet.has(edge.producer_id) || !nodeSet.has(edge.consumer_id) || edge.producer_id === edge.consumer_id) continue;
    outgoing.set(edge.producer_id, [...(outgoing.get(edge.producer_id) ?? []), edge.consumer_id]);
    indegree.set(edge.consumer_id, (indegree.get(edge.consumer_id) ?? 0) + 1);
  }
  const ranks = new Map(nodeIds.map((id) => [id, 0]));
  const queue = nodeIds.filter((id) => indegree.get(id) === 0).sort();
  for (let index = 0; index < queue.length; index += 1) {
    const source = queue[index];
    for (const target of [...(outgoing.get(source) ?? [])].sort()) {
      ranks.set(target, Math.max(ranks.get(target) ?? 0, (ranks.get(source) ?? 0) + 1));
      const next = (indegree.get(target) ?? 1) - 1;
      indegree.set(target, next);
      if (next === 0) queue.push(target);
    }
  }
  return ranks;
}

function draftTopologicalRanks(nodes: DraftNode[], edges: DraftEdge[]): Map<string, number> {
  const ownerByPort = new Map(nodes.flatMap((node) => node.ports.map((port) => [port.port_id, node.node_id] as const)));
  const nodeIds = nodes.map((node) => node.node_id);
  const nodeSet = new Set(nodeIds);
  const outgoing = new Map<string, string[]>();
  const indegree = new Map(nodeIds.map((id) => [id, 0]));
  for (const edge of edges) {
    const source = ownerByPort.get(edge.source_port_id);
    const target = ownerByPort.get(edge.target_port_id);
    if (!source || !target || source === target || !nodeSet.has(source) || !nodeSet.has(target)) continue;
    outgoing.set(source, [...(outgoing.get(source) ?? []), target]);
    indegree.set(target, (indegree.get(target) ?? 0) + 1);
  }
  const ranks = new Map(nodeIds.map((id) => [id, 0]));
  const queue = nodeIds.filter((id) => indegree.get(id) === 0).sort();
  for (let index = 0; index < queue.length; index += 1) {
    const source = queue[index];
    for (const target of [...new Set(outgoing.get(source) ?? [])].sort()) {
      ranks.set(target, Math.max(ranks.get(target) ?? 0, (ranks.get(source) ?? 0) + 1));
      const next = (indegree.get(target) ?? 1) - 1;
      indegree.set(target, next);
      if (next === 0) queue.push(target);
    }
  }
  return ranks;
}

function draftNodeShape(node: DraftNode): NodeShape {
  const definition = node.definition_ref ? resolveDefinitionRef(node.definition_ref) : undefined;
  const semanticKind = definition?.semantic_kind ?? node.node_type;
  return nodeShape({
    node_id: node.node_id,
    semantic_name: node.semantic_name,
    kind: semanticKind,
    evidence_ids: [],
    attributes: {
      semantic_kind: semanticKind,
      op_type: definition?.definition_id ?? node.node_type,
      glyph_id: definition?.glyph_id,
    },
    input_ports: node.ports.filter((port) => port.direction === "input"),
    output_ports: node.ports.filter((port) => port.direction === "output"),
  }, definition?.glyph_id);
}

function layoutNodes(
  state: StudioStatePayload,
  presetId: ViewPresetId,
  nodes: ProjectedNode[],
  edges: ProjectedEdge[],
): { nodes: LabNode[]; width: number; height: number } {
  const preset = resolveViewPreset(presetId);
  const ranks = topologicalRanks(nodes.map((node) => node.node_id), edges);
  const grouped = new Map<number, ExactNode[]>();
  for (const node of nodes) {
    const rank = ranks.get(node.node_id) ?? 0;
    grouped.set(rank, [...(grouped.get(rank) ?? []), node]);
  }
  for (const rankNodes of grouped.values()) rankNodes.sort((left, right) => left.node_id.localeCompare(right.node_id));
  const maxRank = Math.max(0, ...grouped.keys());
  const maxRows = Math.max(1, ...[...grouped.values()].map((items) => items.length));
  const width = preset.orientation === "left-to-right"
    ? Math.max(1120, 180 + (maxRank + 1) * 260)
    : Math.max(1120, 220 + maxRows * 230);
  const height = preset.orientation === "left-to-right"
    ? Math.max(720, 160 + maxRows * 126)
    : Math.max(760, 180 + (maxRank + 1) * 142);
  const annotations = state.semantic_overlay?.annotations ?? [];
  const glyphByNode = new Map<string, string>();
  const roleByNode = new Map<string, string>();
  for (const annotation of annotations) {
    for (const canonicalId of annotation.canonical_node_ids) {
      if (annotation.glyph) glyphByNode.set(canonicalId, annotation.glyph);
      roleByNode.set(canonicalId, annotation.semantic_role.toLowerCase());
    }
  }
  const result: LabNode[] = [];
  for (const [rank, rankNodes] of [...grouped.entries()].sort((left, right) => left[0] - right[0])) {
    rankNodes.forEach((node, index) => {
      const sceneNodeId = `${presetId}:node:${node.node_id}`;
      const hierarchyNodeId = String(node.attributes.hierarchy_node_id ?? "") || undefined;
      const storedPosition = state.view_state?.node_positions?.[sceneNodeId]
        ?? (hierarchyNodeId ? state.view_state?.node_positions?.[`view:${hierarchyNodeId}`] : undefined)
        ?? state.view_state?.node_positions?.[`view:${node.node_id}`]
        ?? state.view_state?.node_positions?.[node.node_id];
      const storedSize = state.view_state?.node_sizes?.[sceneNodeId]
        ?? (hierarchyNodeId ? state.view_state?.node_sizes?.[`view:${hierarchyNodeId}`] : undefined)
        ?? state.view_state?.node_sizes?.[`view:${node.node_id}`]
        ?? state.view_state?.node_sizes?.[node.node_id];
      const role = roleByNode.get(node.node_id) ?? "";
      const paperTone = role.includes("encoder") ? "encoder"
        : role.includes("decoder") ? "decoder"
          : node.kind.toLowerCase().includes("input") ? "input"
            : node.kind.toLowerCase().includes("output") ? "output"
              : "neutral";
      const defaultPosition = preset.orientation === "left-to-right"
        ? { x: 90 + rank * 250, y: 80 + index * 122 }
        : { x: 110 + index * 225, y: 70 + (maxRank - rank) * 138 };
      const shape = nodeShape(node, glyphByNode.get(node.node_id));
      result.push({
        scene_node_id: sceneNodeId,
        bounds: {
          x: storedPosition?.x ?? defaultPosition.x,
          y: storedPosition?.y ?? defaultPosition.y,
          width: storedSize?.width ?? 190,
          height: storedSize?.height ?? 72,
        },
        shape,
        label: node.semantic_name,
        secondary_label: String(node.attributes.op_type ?? node.attributes.source_kind ?? node.kind),
        detail_kind: shape === "attention" ? "attention" : shape === "normalization" ? "normalization" : undefined,
        layout_lane: `rank-${rank}`,
        layout_rank: rank,
        paper_tone: preset.templateProfile === "paper" ? paperTone : undefined,
        canonical_node_ids: canonicalIdsFor(node),
        evidence_ids: unique(node.evidence_ids),
        source_anchor_ids: unique(node.evidence_ids),
        input_ports: node.input_ports,
        output_ports: node.output_ports,
        fidelity: node.evidence_ids.length ? "exact" : "schematic",
        hierarchy_node_id: hierarchyNodeId,
        hierarchy_expandable: Number(node.attributes.child_count ?? 0) > 0,
        parent_hierarchy_node_id: node.parent_id ?? undefined,
      });
    });
  }
  return { nodes: result, width, height };
}

export function projectToScene(state: StudioStatePayload, requestedPresetId: ViewPresetId): SourceBackedScene {
  const presetId = requestedPresetId;
  const preset = resolveViewPreset(presetId);
  const canonicalNodes = [...state.architecture.nodes].sort((left, right) => left.node_id.localeCompare(right.node_id));
  const canonicalEdges = [...state.architecture.edges].sort((left, right) => left.edge_id.localeCompare(right.edge_id));
  const frontier = hierarchyFrontier(state);
  const projectedNodes = [...frontier.nodes].sort((left, right) => left.node_id.localeCompare(right.node_id));
  const projectedEdges = [...frontier.edges].sort((left, right) => left.edge_id.localeCompare(right.edge_id));
  const layout = layoutNodes(state, presetId, projectedNodes, projectedEdges);
  const sceneIdByCanonical = new Map(layout.nodes.flatMap((node) => (
    node.canonical_node_ids?.map((id) => [id, node.scene_node_id] as const) ?? []
  )));
  const sceneIdByProjected = new Map(projectedNodes.map((node) => [node.node_id, `${presetId}:node:${node.node_id}`]));
  const edges: LabEdge[] = projectedEdges.flatMap((edge) => {
    const source = sceneIdByProjected.get(edge.producer_id) ?? sceneIdByCanonical.get(edge.producer_id);
    const target = sceneIdByProjected.get(edge.consumer_id) ?? sceneIdByCanonical.get(edge.consumer_id);
    if (!source || !target || source === target) return [];
    return [{
      scene_edge_id: `${presetId}:edge:${edge.edge_id}`,
      source_scene_node_id: source,
      target_scene_node_id: target,
      relation: edgeRelation(edge),
      label: edge.role || edge.edge_type,
      target_port_role: edge.consumer_port,
      canonical_edge_ids: canonicalEdgeIdsFor(edge),
      tensor_ids: tensorIdsFor(edge),
      evidence_ids: unique(edge.evidence_ids),
    }];
  });
  const draft = state.draft;
  const draftNodes = draft?.nodes ?? [];
  const draftRanks = draftTopologicalRanks(draftNodes, draft?.edges ?? []);
  const draftRows = new Map<number, number>();
  const canonicalBottom = Math.max(70, ...layout.nodes.map((node) => node.bounds.y + node.bounds.height));
  const draftStatusBySubject = new Map(
    (draft?.proofs ?? []).flatMap((proof) => proof.affected_subject_ids.map((id) => [id, proof.status] as const)),
  );
  const projectedDraftNodes: LabNode[] = [...draftNodes]
    .sort((left, right) => left.node_id.localeCompare(right.node_id))
    .map((node) => {
      const rank = draftRanks.get(node.node_id) ?? 0;
      const row = draftRows.get(rank) ?? 0;
      draftRows.set(rank, row + 1);
      const sceneNodeId = `${presetId}:node:${node.node_id}`;
      const storedPosition = state.view_state?.node_positions?.[sceneNodeId]
        ?? state.view_state?.node_positions?.[`view:${node.node_id}`]
        ?? state.view_state?.node_positions?.[node.node_id];
      const storedSize = state.view_state?.node_sizes?.[sceneNodeId]
        ?? state.view_state?.node_sizes?.[`view:${node.node_id}`]
        ?? state.view_state?.node_sizes?.[node.node_id];
      return {
        scene_node_id: sceneNodeId,
        bounds: {
          x: storedPosition?.x ?? 90 + rank * 250,
          y: storedPosition?.y ?? canonicalBottom + 70 + row * 112,
          width: storedSize?.width ?? 190,
          height: storedSize?.height ?? 72,
        },
        shape: draftNodeShape(node),
        label: node.semantic_name,
        secondary_label: `${node.node_type} · draft`,
        layout_lane: `draft-rank-${rank}`,
        layout_rank: rank,
        paper_tone: "neutral" as const,
        input_ports: node.ports.filter((port) => port.direction === "input"),
        output_ports: node.ports.filter((port) => port.direction === "output"),
        fidelity: "schematic" as const,
        draft_node_id: node.node_id,
        draft_status: draftStatusBySubject.get(node.node_id),
      };
    });
  const allNodes = [...layout.nodes, ...projectedDraftNodes];
  const draftSceneIdByNode = new Map(draftNodes.map((node) => [node.node_id, `${presetId}:node:${node.node_id}`]));
  const draftOwnerByPort = new Map(draftNodes.flatMap((node) => node.ports.map((port) => [port.port_id, node.node_id] as const)));
  const canonicalOwnerByPort = new Map(state.architecture.nodes.flatMap((node) => (
    [...node.input_ports, ...node.output_ports].map((port) => [port.port_id, node.node_id] as const)
  )));
  for (const edge of [...(draft?.edges ?? [])].sort((left, right) => left.edge_id.localeCompare(right.edge_id))) {
    const sourceOwner = draftOwnerByPort.get(edge.source_port_id) ?? canonicalOwnerByPort.get(edge.source_port_id);
    const targetOwner = draftOwnerByPort.get(edge.target_port_id) ?? canonicalOwnerByPort.get(edge.target_port_id);
    if (!sourceOwner || !targetOwner) continue;
    const source = draftSceneIdByNode.get(sourceOwner) ?? sceneIdByCanonical.get(sourceOwner);
    const target = draftSceneIdByNode.get(targetOwner) ?? sceneIdByCanonical.get(targetOwner);
    if (!source || !target || source === target) continue;
    edges.push({
      scene_edge_id: `${presetId}:edge:${edge.edge_id}`,
      source_scene_node_id: source,
      target_scene_node_id: target,
      relation: edge.relation === "residual" ? "residual" : edge.relation === "concat" ? "merge" : "flow",
      label: `${edge.relation ?? "main"} · draft`,
      target_port_role: edge.target_port_id.split(".").at(-1),
      draft_edge_id: edge.edge_id,
    });
  }
  const bindings: Record<string, SceneBinding> = {};
  for (const node of allNodes) {
    bindings[node.scene_node_id] = {
      sceneId: node.scene_node_id,
      canonicalNodeIds: node.canonical_node_ids ?? [],
      canonicalEdgeIds: [],
      sourceAnchorIds: node.source_anchor_ids ?? [],
      evidenceIds: node.evidence_ids ?? [],
      portBindings: Object.fromEntries([...(node.input_ports ?? []), ...(node.output_ports ?? [])].map((port) => [port.role, port.port_id])),
      fidelity: node.fidelity ?? "schematic",
      draftNodeIds: node.draft_node_id ? [node.draft_node_id] : [],
      draftEdgeIds: [],
    };
  }
  for (const edge of edges) {
    bindings[edge.scene_edge_id] = {
      sceneId: edge.scene_edge_id,
      canonicalNodeIds: [],
      canonicalEdgeIds: edge.canonical_edge_ids ?? [],
      sourceAnchorIds: edge.evidence_ids ?? [],
      evidenceIds: edge.evidence_ids ?? [],
      portBindings: {},
      fidelity: edge.evidence_ids?.length ? "exact" : "schematic",
      draftNodeIds: [],
      draftEdgeIds: edge.draft_edge_id ? [edge.draft_edge_id] : [],
    };
  }
  const sourceDigest = state.integrity?.source_digest ?? state.document.source_digest;
  const exactIrDigest = state.integrity?.exact_ir_digest ?? state.semantic_overlay?.exact_ir_digest ?? sourceDigest;
  return {
    scene_id: `source:${state.project.project_id}:${presetId}`,
    title: `${state.architecture.entrypoint} · ${preset.label}`,
    description: `${canonicalNodes.length} 个语义节点 · ${canonicalEdges.length} 条事实边${draftNodes.length ? ` · ${draftNodes.length} 个草稿节点` : ""} · ${state.project.framework}`,
    paper_width: Math.max(layout.width, ...projectedDraftNodes.map((node) => node.bounds.x + node.bounds.width + 80)),
    paper_height: Math.max(layout.height, ...projectedDraftNodes.map((node) => node.bounds.y + node.bounds.height + 80)),
    nodes: allNodes,
    edges,
    layout_profile: preset.templateProfile === "paper" ? "paper" : "freeform",
    sourceProjectId: state.project.project_id,
    architectureId: state.architecture.architecture_id,
    sourceDigest,
    exactIrDigest,
    presetId,
    bindings,
  };
}
