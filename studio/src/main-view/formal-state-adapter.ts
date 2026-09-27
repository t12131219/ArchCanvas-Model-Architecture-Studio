import type {
  KernelDiagnostic,
  KernelDocument,
  KernelEdge,
  KernelModule,
  KernelNode,
  KernelNodeShape,
  KernelPort,
  KernelRelation,
  KernelTemplateBinding,
  KernelVisualState,
} from "../visual-kernel/types";

export interface FormalPort {
  port_id: string;
  name: string;
  direction: "input" | "output";
  role: string;
}

export interface FormalNode {
  node_id: string;
  semantic_name: string;
  kind: string;
  parent_id?: string | null;
  children?: string[];
  input_ports: FormalPort[];
  output_ports: FormalPort[];
  evidence_ids: string[];
  attributes: Record<string, unknown>;
}

export interface FormalEdge {
  edge_id: string;
  tensor_id: string;
  producer_id: string;
  producer_port: string;
  consumer_id: string;
  consumer_port: string;
  role: string;
  edge_type: string;
  evidence_ids: string[];
}

export interface FormalHierarchyNode {
  hierarchy_node_id: string;
  parent_hierarchy_node_id?: string | null;
  semantic_name: string;
  kind?: string;
  depth: number;
  canonical_node_ids: string[];
  evidence_ids?: string[];
  attributes?: Record<string, unknown>;
}

export interface FormalTemplateBinding {
  binding_id: string;
  template_id: string;
  template_version?: string;
  fidelity: "exact" | "opaque" | "schematic";
  root_canonical_node_ids?: string[];
  canonical_node_ids?: string[];
  node_slots?: Record<string, string[]>;
  edge_slots?: Record<string, string[]>;
  port_slots?: Record<string, string[]>;
  tensor_slots?: Record<string, string[]>;
  evidence_ids: string[];
  predicate_ids?: string[];
  binding_digest?: string;
  source_digest?: string;
}

export interface FormalSemanticAnnotation {
  annotation_id: string;
  pack_id: string;
  canonical_node_ids: string[];
  semantic_role: string;
  glyph?: string | null;
  predicate_ids: string[];
}

export interface FormalStudioState {
  architecture: {
    architecture_id: string;
    nodes: FormalNode[];
    edges: FormalEdge[];
  };
  hierarchy: {
    root_node_id: string;
    nodes: FormalHierarchyNode[];
  };
  document: {
    source_digest: string;
  };
  view_state: {
    module_expansion?: string[];
    pinned_node_ids?: string[];
    route_style?: KernelVisualState["routeStyle"];
    node_style?: KernelVisualState["nodeStyle"];
    label_style?: KernelVisualState["labelStyle"];
    node_shape_overrides?: Record<string, KernelNodeShape>;
    node_positions?: Record<string, { x: number; y: number }>;
    node_sizes?: Record<string, { width: number; height: number }>;
    detail_offsets?: Record<string, { x: number; y: number }>;
    route_hints?: Record<string, Array<{ x: number; y: number }>>;
    cameras?: Record<string, { x: number; y: number; zoom: number; width?: number; height?: number }>;
  };
  semantic_overlay?: {
    annotations?: FormalSemanticAnnotation[];
    template_bindings?: FormalTemplateBinding[];
  } | null;
}

function unique(values: string[]): string[] {
  return [...new Set(values)].sort();
}

function shapeFor(kind: string, attributes: Record<string, unknown>, annotationGlyph?: string): KernelNodeShape {
  const glyph = String(annotationGlyph ?? attributes.glyph ?? "").toLowerCase();
  const semanticRole = String(attributes.semantic_role ?? "").toLowerCase();
  const opType = String(attributes.op_type ?? attributes.source_kind ?? "").toLowerCase();
  if (kind === "module_container" || kind === "opaque_composite") return "container";
  if (kind === "input" || kind === "output" || kind === "io" || kind === "input_output") return "io";
  if (kind === "tensor" || kind === "tensor_value" || glyph === "tensor") return "tensor";
  if (kind === "condition" || kind === "condition_control" || glyph === "condition") return "condition";
  if (glyph === "attention") return "attention";
  if (glyph === "normalization") return "normalization";
  if (glyph === "add" || semanticRole === "add") return "add";
  if (glyph === "multiply" || semanticRole === "multiply") return "multiply";
  if (glyph === "concat" || semanticRole === "concat") return "concat";
  if (glyph === "merge" || kind === "merge" || kind === "merge_event") return "merge";
  if (/(^|\.)(conv1d|conv2d|conv3d|convolution)$/.test(opType)) return "convolution";
  if (/(^|\.)(layernorm|batchnorm|groupnorm|rmsnorm)$/.test(opType)) return "normalization";
  if (/(^|\.)(add|sum)$/.test(opType)) return "add";
  if (/(^|\.)(mul|multiply)$/.test(opType)) return "multiply";
  if (/(^|\.)(cat|concat)$/.test(opType)) return "concat";
  return "operation";
}

function relationFor(edge: FormalEdge): KernelRelation {
  const type = edge.edge_type.toLowerCase();
  const role = edge.role.toLowerCase();
  if (type.includes("residual") || role.includes("residual") || role.includes("skip")) return "residual";
  if (type.includes("condition") || role.includes("mask") || role.includes("condition")) return "condition";
  if (type.includes("memory") || role.includes("memory")) return "memory-reference";
  if (type.includes("state") || role.includes("state")) return "state-update";
  if (type.includes("shape") || role.includes("reshape") || role.includes("transpose")) return "shape-transform";
  if (type.includes("share") || role.includes("parameter")) return "parameter-share";
  if (type.includes("training")) return "training-only";
  if (type.includes("branch") || type.includes("fanout")) return "parallel-branch";
  if (type.includes("merge") || role.includes("concat")) return "merge";
  if (type.includes("routing")) return "routing";
  return "sequence";
}

interface VisibleHierarchyNode {
  item: FormalHierarchyNode;
  expanded: boolean;
  childIds: string[];
}

function visibleHierarchy(
  hierarchy: FormalStudioState["hierarchy"],
  expanded: Set<string>,
  exactTemplateRoots: Set<string>,
): VisibleHierarchyNode[] {
  const byParent = new Map<string, FormalHierarchyNode[]>();
  for (const item of hierarchy.nodes) {
    if (!item.parent_hierarchy_node_id) continue;
    byParent.set(item.parent_hierarchy_node_id, [
      ...(byParent.get(item.parent_hierarchy_node_id) ?? []),
      item,
    ]);
  }
  for (const children of byParent.values()) {
    children.sort((left, right) => left.hierarchy_node_id.localeCompare(right.hierarchy_node_id));
  }
  const root = hierarchy.nodes.find((item) => item.hierarchy_node_id === hierarchy.root_node_id)
    ?? hierarchy.nodes.find((item) => !item.parent_hierarchy_node_id);
  if (!root) return [];
  const result: VisibleHierarchyNode[] = [];
  const visit = (item: FormalHierarchyNode, forceExpanded = false) => {
    const children = byParent.get(item.hierarchy_node_id) ?? [];
    const hasExactDetail = item.canonical_node_ids.some((id) => exactTemplateRoots.has(id));
    const isExpanded = (children.length > 0 || hasExactDetail) && (forceExpanded || expanded.has(item.hierarchy_node_id));
    result.push({ item, expanded: isExpanded, childIds: isExpanded ? children.map((child) => child.hierarchy_node_id) : [] });
    if (isExpanded) children.forEach((child) => visit(child));
  };
  visit(root, true);
  return result;
}

function canonicalClosure(hierarchy: FormalStudioState["hierarchy"]): Map<string, string[]> {
  const byId = new Map(hierarchy.nodes.map((item) => [item.hierarchy_node_id, item]));
  const children = new Map<string, string[]>();
  for (const item of hierarchy.nodes) {
    if (!item.parent_hierarchy_node_id) continue;
    children.set(item.parent_hierarchy_node_id, [
      ...(children.get(item.parent_hierarchy_node_id) ?? []),
      item.hierarchy_node_id,
    ]);
  }
  const cache = new Map<string, string[]>();
  const visiting = new Set<string>();
  const collect = (id: string): string[] => {
    const cached = cache.get(id);
    if (cached) return cached;
    if (visiting.has(id)) return [];
    visiting.add(id);
    const item = byId.get(id);
    const result = unique([
      ...(item?.canonical_node_ids ?? []),
      ...(children.get(id) ?? []).flatMap((childId) => collect(childId)),
    ]);
    visiting.delete(id);
    cache.set(id, result);
    return result;
  };
  for (const id of byId.keys()) collect(id);
  return cache;
}

function templateBindings(state: FormalStudioState): KernelTemplateBinding[] {
  return (state.semantic_overlay?.template_bindings ?? []).map((binding) => {
    const nodeSlots = Object.fromEntries(Object.entries(binding.node_slots ?? {}).map(([slot, ids]) => [slot, unique(ids)]));
    const rootCanonicalNodeIds = unique(binding.root_canonical_node_ids ?? binding.canonical_node_ids ?? []);
    return {
      bindingId: binding.binding_id,
      templateId: binding.template_id,
      templateVersion: binding.template_version,
      fidelity: binding.source_digest && binding.source_digest !== state.document.source_digest ? "opaque" : binding.fidelity,
      rootCanonicalNodeIds,
      canonicalNodeIds: unique([...rootCanonicalNodeIds, ...Object.values(nodeSlots).flat()]),
      nodeSlots,
      edgeSlots: Object.fromEntries(Object.entries(binding.edge_slots ?? {}).map(([slot, ids]) => [slot, unique(ids)])),
      portSlots: Object.fromEntries(Object.entries(binding.port_slots ?? {}).map(([slot, ids]) => [slot, unique(ids)])),
      tensorSlots: Object.fromEntries(Object.entries(binding.tensor_slots ?? {}).map(([slot, ids]) => [slot, unique(ids)])),
      evidenceIds: unique(binding.evidence_ids),
      predicateIds: unique(binding.predicate_ids ?? []),
      bindingDigest: binding.binding_digest,
    };
  }).sort((left, right) => left.bindingId.localeCompare(right.bindingId));
}

export function adaptFormalState(state: FormalStudioState): {
  document: KernelDocument;
  visualState: KernelVisualState;
} {
  const diagnostics: KernelDiagnostic[] = [];
  const expanded = new Set(state.view_state.module_expansion ?? []);
  const bindings = templateBindings(state);
  const annotationGlyphsByCanonical = new Map<string, Set<string>>();
  for (const annotation of state.semantic_overlay?.annotations ?? []) {
    if (!annotation.glyph) continue;
    for (const canonicalId of annotation.canonical_node_ids) {
      const glyphs = annotationGlyphsByCanonical.get(canonicalId) ?? new Set<string>();
      glyphs.add(annotation.glyph);
      annotationGlyphsByCanonical.set(canonicalId, glyphs);
    }
  }
  const exactTemplateRoots = new Set(bindings.filter((binding) => binding.fidelity === "exact").flatMap((binding) => binding.rootCanonicalNodeIds));
  const visible = visibleHierarchy(state.hierarchy, expanded, exactTemplateRoots);
  const canonicalByHierarchy = canonicalClosure(state.hierarchy);
  const formalNodes = new Map(state.architecture.nodes.map((node) => [node.node_id, node]));
  const representativeByCanonical = new Map<string, string>();
  const nodes: KernelNode[] = visible.map(({ item, expanded: isExpanded, childIds }) => {
    const nodeId = `view:${item.hierarchy_node_id}`;
    const containedCanonicalNodeIds = canonicalByHierarchy.get(item.hierarchy_node_id) ?? item.canonical_node_ids;
    const canonicalNodeIds = unique(item.canonical_node_ids);
    const facts = canonicalNodeIds.map((id) => formalNodes.get(id)).filter((node): node is FormalNode => Boolean(node));
    const containedFacts = containedCanonicalNodeIds.map((id) => formalNodes.get(id)).filter((node): node is FormalNode => Boolean(node));
    const primary = facts[0];
    const evidenceIds = unique([...(item.evidence_ids ?? []), ...containedFacts.flatMap((node) => node.evidence_ids)]);
    const binding = bindings.find((candidate) => candidate.rootCanonicalNodeIds.some((id) => canonicalNodeIds.includes(id)));
    const hasTemplateDetail = binding?.fidelity === "exact" && binding.templateId === "attention.qkv-v1";
    const annotationGlyphs = unique(canonicalNodeIds.flatMap((id) => [...(annotationGlyphsByCanonical.get(id) ?? [])]));
    const annotationGlyph = annotationGlyphs.length === 1 ? annotationGlyphs[0] : undefined;
    const hasChildren = hasTemplateDetail || childIds.length > 0 || state.hierarchy.nodes.some((candidate) => candidate.parent_hierarchy_node_id === item.hierarchy_node_id);
    return {
      nodeId,
      hierarchyNodeId: item.hierarchy_node_id,
      parentNodeId: item.parent_hierarchy_node_id ? `view:${item.parent_hierarchy_node_id}` : undefined,
      parentModuleId: item.parent_hierarchy_node_id ? `module:${item.parent_hierarchy_node_id}` : undefined,
      childNodeIds: childIds.map((id) => `view:${id}`),
      depth: item.depth,
      expanded: isExpanded,
      renderRole: isExpanded ? "expanded-module" : hasChildren ? "collapsed-module" : "atomic",
      canonicalNodeIds,
      containedCanonicalNodeIds,
      label: item.semantic_name,
      secondaryLabel: containedFacts.length > 1 ? `${containedFacts.length} operations` : primary?.kind,
      semanticKind: item.kind ?? primary?.kind ?? "unknown",
      shape: state.view_state.node_shape_overrides?.[nodeId]
        ?? (hasTemplateDetail ? "attention" : hasChildren ? "container" : primary ? shapeFor(primary.kind, primary.attributes, annotationGlyph) : shapeFor(item.kind ?? "unknown", {}, annotationGlyph)),
      inputPortIds: [`${nodeId}:input`],
      outputPortIds: [`${nodeId}:output`],
      evidenceIds,
      templateBindingId: binding?.bindingId,
      synthetic: Boolean(item.attributes?.synthetic ?? canonicalNodeIds.length === 0),
    };
  });

  for (const node of [...nodes].sort((left, right) => right.depth - left.depth || left.nodeId.localeCompare(right.nodeId))) {
    for (const canonicalId of node.containedCanonicalNodeIds) {
      if (!representativeByCanonical.has(canonicalId)) representativeByCanonical.set(canonicalId, node.nodeId);
    }
  }

  const ports: KernelPort[] = nodes.flatMap((node) => [
    { portId: node.inputPortIds[0], ownerNodeId: node.nodeId, direction: "input" as const, role: "projected-input", evidenceIds: node.evidenceIds },
    { portId: node.outputPortIds[0], ownerNodeId: node.nodeId, direction: "output" as const, role: "projected-output", evidenceIds: node.evidenceIds },
  ]);
  const edgeGroups = new Map<string, FormalEdge[]>();
  for (const edge of [...state.architecture.edges].sort((left, right) => left.edge_id.localeCompare(right.edge_id))) {
    const source = representativeByCanonical.get(edge.producer_id);
    const target = representativeByCanonical.get(edge.consumer_id);
    if (!source || !target) {
      diagnostics.push({
        code: "unprojected-canonical-edge",
        severity: "warning",
        message: `Canonical edge ${edge.edge_id} has no visible representative.`,
        targetIds: [edge.edge_id],
      });
      continue;
    }
    if (source === target) continue;
    const relation = relationFor(edge);
    const key = `${source}|${target}|${relation}|${edge.role}`;
    edgeGroups.set(key, [...(edgeGroups.get(key) ?? []), edge]);
  }
  const edges: KernelEdge[] = [...edgeGroups.entries()].map(([key, facts]) => {
    const [source, target, relation, semanticChannel] = key.split("|") as [string, string, KernelRelation, string];
    return {
      edgeId: `projected:${key}`,
      canonicalEdgeIds: facts.map((edge) => edge.edge_id).sort(),
      sourcePortId: `${source}:output`,
      targetPortId: `${target}:input`,
      relation,
      semanticChannel,
      tensorIds: unique(facts.map((edge) => edge.tensor_id)),
      label: semanticChannel || relation,
      evidenceIds: unique(facts.flatMap((edge) => edge.evidence_ids)),
    };
  }).sort((left, right) => left.edgeId.localeCompare(right.edgeId));

  const nodeById = new Map(nodes.map((node) => [node.nodeId, node]));
  const modules: KernelModule[] = nodes.filter((node) => node.renderRole !== "atomic").map((node) => ({
    hierarchyNodeId: node.hierarchyNodeId,
    hostNodeId: node.nodeId,
    moduleId: `module:${node.hierarchyNodeId}`,
    parentModuleId: node.parentNodeId ? `module:${nodeById.get(node.parentNodeId)?.hierarchyNodeId ?? ""}` : undefined,
    childModuleIds: node.childNodeIds.filter((id) => nodeById.get(id)?.renderRole !== "atomic").map((id) => `module:${nodeById.get(id)!.hierarchyNodeId}`),
    nodeIds: node.childNodeIds,
    label: node.label,
    evidenceIds: node.evidenceIds,
  })).sort((left, right) => left.moduleId.localeCompare(right.moduleId));

  return {
    document: {
      documentId: `kernel-document:${state.architecture.architecture_id}`,
      architectureId: state.architecture.architecture_id,
      sourceDigest: state.document.source_digest,
      nodes: nodes.sort((left, right) => left.nodeId.localeCompare(right.nodeId)),
      ports: ports.sort((left, right) => left.portId.localeCompare(right.portId)),
      edges,
      modules,
      templateBindings: bindings,
      diagnostics,
    },
    visualState: {
      expandedModuleIds: [...expanded].sort(),
      nodePositions: state.view_state.node_positions ?? {},
      nodeSizes: state.view_state.node_sizes ?? {},
      detailOffsets: state.view_state.detail_offsets ?? {},
      pinnedNodeIds: [...(state.view_state.pinned_node_ids ?? [])].sort(),
      routeHints: state.view_state.route_hints ?? {},
      routeStyle: state.view_state.route_style ?? "adaptive",
      nodeStyle: state.view_state.node_style ?? "semantic",
      labelStyle: state.view_state.label_style ?? "plate",
      nodeShapeOverrides: state.view_state.node_shape_overrides ?? {},
    },
  };
}
