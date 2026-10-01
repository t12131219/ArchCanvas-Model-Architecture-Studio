import type { StudioState } from "../app/studio-types";
import { resolveDefinitionId } from "../module-registry/registry";
import type {
  GraphDiagnostic,
  PrototypeEdge,
  PrototypeGraphDocument,
  PrototypeNode,
} from "../prototype-graph/types";
import { compilePyTorchDraft } from "./compile";
import type { PrintedPyTorchDraft } from "./pytorch-ir";
import { printPyTorchDraft } from "./printer";

export interface StudioCodegenPreviewResult {
  preview: PrintedPyTorchDraft | null;
  diagnostics: GraphDiagnostic[];
}

function externalInputNode(sourcePortId: string, ordinal: number): PrototypeNode {
  const definition = resolveDefinitionId("archcanvas.input.tensor");
  if (!definition) throw new Error("the registry has no tensor input definition");
  const nodeId = `draft:codegen-input.${ordinal}`;
  return {
    node_id: nodeId,
    semantic_name: `input_${ordinal + 1}`,
    definition_ref: {
      definition_id: definition.definition_id,
      version: definition.version,
      digest: definition.digest,
    },
    parameters: { shape: ["?"] },
    ports: [{
      port_id: `${nodeId}.output`,
      name: "output",
      direction: "output",
      definition_port_id: "output",
      min_connections: 0,
      max_connections: "many",
      ordering: "ordered",
      accepted_relations: ["main"],
    }],
    parameter_group_id: sourcePortId,
  };
}

export function studioDraftCodegenGraph(
  draft: StudioState["draft"],
): PrototypeGraphDocument {
  const nodes: PrototypeNode[] = draft.nodes.map((node) => ({
    node_id: node.node_id,
    semantic_name: node.semantic_name,
    definition_ref: node.definition_ref ?? null,
    parameters: structuredClone(node.parameters),
    ports: node.ports.map((port) => ({ ...port })),
  }));
  const draftPortIds = new Set(nodes.flatMap((node) => node.ports.map((port) => port.port_id)));
  const externalSources = [...new Set(
    draft.edges
      .filter((edge) => !draftPortIds.has(edge.source_port_id) && draftPortIds.has(edge.target_port_id))
      .map((edge) => edge.source_port_id),
  )].sort();
  const externalPortByCanonical = new Map<string, string>();
  for (const [index, sourcePortId] of externalSources.entries()) {
    const input = externalInputNode(sourcePortId, index);
    nodes.push(input);
    externalPortByCanonical.set(sourcePortId, input.ports[0].port_id);
  }
  const edges: PrototypeEdge[] = draft.edges.flatMap((edge) => {
    if (!draftPortIds.has(edge.target_port_id)) return [];
    const sourcePortId = draftPortIds.has(edge.source_port_id)
      ? edge.source_port_id
      : externalPortByCanonical.get(edge.source_port_id);
    if (!sourcePortId) return [];
    return [{
      edge_id: edge.edge_id,
      source_port_id: sourcePortId,
      target_port_id: edge.target_port_id,
      relation: edge.relation,
      target_ordinal: edge.target_ordinal,
    }];
  });
  return {
    draft_id: draft.draft_id,
    base_registry_digest: draft.base_registry_digest,
    nodes,
    edges,
  };
}

export function compileStudioDraftPreview(
  draft: StudioState["draft"],
): StudioCodegenPreviewResult {
  if (!draft.nodes.length) {
    return {
      preview: null,
      diagnostics: [{
        diagnosticId: `codegen:empty:${draft.draft_id}`,
        code: "CODEGEN_GRAPH_EMPTY",
        severity: "blocking",
        message: "Code generation requires at least one registered draft node.",
        targetIds: [draft.draft_id],
        relatedPortIds: [],
      }],
    };
  }
  const result = compilePyTorchDraft(studioDraftCodegenGraph(draft), "GeneratedDraft");
  if (!result.draft) return { preview: null, diagnostics: result.diagnostics };
  try {
    return { preview: printPyTorchDraft(result.draft), diagnostics: result.diagnostics };
  } catch (error) {
    return {
      preview: null,
      diagnostics: [{
        diagnosticId: `codegen:printer:${draft.draft_id}`,
        code: "CODEGEN_PRINTER_FAILED",
        severity: "blocking",
        message: error instanceof Error ? error.message : String(error),
        targetIds: [draft.draft_id],
        relatedPortIds: [],
      }],
    };
  }
}
