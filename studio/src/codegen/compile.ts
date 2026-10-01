import { MODULE_REGISTRY, resolveDefinitionRef } from "../module-registry/registry";
import type { ModuleDefinition, ParameterContract } from "../module-registry/types";
import type { GraphDiagnostic, PrototypeEdge, PrototypeGraphDocument, PrototypeNode } from "../prototype-graph/types";
import {
  attribute,
  call,
  literal,
  name,
  type AssignmentTarget,
  type ModuleInitStatement,
  type PyTorchDraft,
  type PythonExpression,
  type PythonLiteral,
} from "./pytorch-ir";

const PYTHON_RESERVED = new Set([
  "False", "None", "True", "and", "as", "assert", "async", "await", "break", "class",
  "continue", "def", "del", "elif", "else", "except", "finally", "for", "from", "global",
  "if", "import", "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise", "return",
  "try", "while", "with", "yield",
]);

class IdentifierAllocator {
  private readonly counts = new Map<string, number>();

  allocate(preferred: string): string {
    let base = preferred.normalize("NFKD").replace(/[^A-Za-z0-9_]+/g, "_").replace(/^_+|_+$/g, "");
    if (!base || /^[0-9]/.test(base)) base = `value_${base || "item"}`;
    if (PYTHON_RESERVED.has(base)) base = `${base}_value`;
    const next = (this.counts.get(base) ?? 0) + 1;
    this.counts.set(base, next);
    return next === 1 ? base : `${base}_${next}`;
  }
}

export interface CodegenResult {
  draft: PyTorchDraft | null;
  diagnostics: GraphDiagnostic[];
}

function diagnostic(code: string, message: string, targetIds: string[], relatedPortIds: string[] = []): GraphDiagnostic {
  return {
    diagnosticId: `codegen:${code.toLowerCase()}:${targetIds.join(":")}`,
    code,
    severity: "blocking",
    message,
    targetIds,
    relatedPortIds,
  };
}

function pythonLiteral(value: unknown): PythonLiteral {
  if (value === null || typeof value === "string" || typeof value === "boolean") return value;
  if (typeof value === "number") {
    if (!Number.isFinite(value) || (Number.isInteger(value) && !Number.isSafeInteger(value))) {
      throw new Error("numeric parameter is outside the portable Python literal range");
    }
    return value;
  }
  if (Array.isArray(value)) return value.map(pythonLiteral);
  if (typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, pythonLiteral(item)]),
    );
  }
  throw new Error(`unsupported parameter literal: ${typeof value}`);
}

function constructorExpression(definition: ModuleDefinition, node: PrototypeNode): PythonExpression {
  const qualified = definition.qualified_names.find((item) => item.startsWith("torch.nn."));
  if (!qualified) throw new Error(`definition ${definition.definition_id} has no torch.nn constructor`);
  const className = qualified.split(".").at(-1)!;
  const positional: PythonExpression[] = [];
  const keywords: Array<{ name: string; value: PythonExpression }> = [];
  const contracts = [...definition.parameters].sort((left, right) =>
    (left.positional_index ?? Number.MAX_SAFE_INTEGER) - (right.positional_index ?? Number.MAX_SAFE_INTEGER),
  );
  let positionalOpen = true;
  for (const contract of contracts) {
    const provided = Object.hasOwn(node.parameters, contract.parameter_id);
    if (!provided && contract.required) throw new Error(`missing required parameter ${contract.parameter_id}`);
    const isDefault = provided && !contract.required
      && JSON.stringify(node.parameters[contract.parameter_id]) === JSON.stringify(contract.default);
    if (!provided || isDefault) {
      positionalOpen = false;
      continue;
    }
    const expression = literal(pythonLiteral(node.parameters[contract.parameter_id]));
    if (positionalOpen && contract.positional_index === positional.length) positional.push(expression);
    else {
      positionalOpen = false;
      keywords.push({ name: contract.parameter_id, value: expression });
    }
  }
  return call(attribute(name("nn"), className), positional, keywords);
}

function portKey(node: PrototypeNode, portId: string): string {
  const port = node.ports.find((item) => item.port_id === portId || item.definition_port_id === portId);
  return port?.definition_port_id ?? port?.name ?? portId;
}

function owners(graph: PrototypeGraphDocument): Map<string, { node: PrototypeNode; portId: string }> {
  const result = new Map<string, { node: PrototypeNode; portId: string }>();
  for (const node of graph.nodes) {
    for (const port of node.ports) {
      if (result.has(port.port_id)) throw new Error(`duplicate materialized port id: ${port.port_id}`);
      result.set(port.port_id, { node, portId: port.port_id });
    }
  }
  return result;
}

function topologicalNodes(graph: PrototypeGraphDocument, portOwners: Map<string, { node: PrototypeNode }>): PrototypeNode[] {
  const byId = new Map(graph.nodes.map((node) => [node.node_id, node]));
  const adjacency = new Map(graph.nodes.map((node) => [node.node_id, new Set<string>()]));
  const indegree = new Map(graph.nodes.map((node) => [node.node_id, 0]));
  for (const edge of graph.edges) {
    const source = portOwners.get(edge.source_port_id)?.node.node_id;
    const target = portOwners.get(edge.target_port_id)?.node.node_id;
    if (!source || !target) continue;
    if (!adjacency.get(source)!.has(target)) {
      adjacency.get(source)!.add(target);
      indegree.set(target, indegree.get(target)! + 1);
    }
  }
  const pending = [...indegree].filter(([, count]) => count === 0).map(([id]) => id).sort();
  const ordered: PrototypeNode[] = [];
  while (pending.length) {
    const id = pending.shift()!;
    ordered.push(byId.get(id)!);
    for (const target of [...adjacency.get(id)!].sort()) {
      indegree.set(target, indegree.get(target)! - 1);
      if (indegree.get(target) === 0) {
        pending.push(target);
        pending.sort();
      }
    }
  }
  if (ordered.length !== graph.nodes.length) throw new Error("graph contains a non-control-flow cycle");
  return ordered;
}

function incomingByPort(edges: PrototypeEdge[]): Map<string, PrototypeEdge[]> {
  const result = new Map<string, PrototypeEdge[]>();
  for (const edge of edges) result.set(edge.target_port_id, [...(result.get(edge.target_port_id) ?? []), edge]);
  for (const values of result.values()) values.sort((left, right) =>
    (left.target_ordinal ?? 0) - (right.target_ordinal ?? 0) || left.edge_id.localeCompare(right.edge_id),
  );
  return result;
}

function outputTarget(definitionId: string, values: Record<string, string>): AssignmentTarget {
  const target = (port: string): AssignmentTarget => ({ kind: "name", identifier: values[port] });
  if (definitionId === "pytorch.nn.multiheadattention") {
    return { kind: "tuple", items: [target("context"), target("weights")] };
  }
  if (definitionId === "pytorch.nn.lstm") {
    return {
      kind: "tuple",
      items: [target("sequence"), { kind: "tuple", items: [target("hn"), target("cn")] }],
    };
  }
  const names = Object.keys(values);
  return names.length === 1 ? target(names[0]) : { kind: "tuple", items: names.map(target) };
}

function moduleCall(
  fieldId: string,
  definition: ModuleDefinition,
  inputs: Record<string, PythonExpression[]>,
): PythonExpression {
  if (definition.definition_id === "pytorch.nn.multiheadattention") {
    const required = ["query", "key", "value"];
    const positional = required.map((port) => inputs[port][0]);
    const keywords = ["key_padding_mask", "attention_mask"]
      .filter((port) => inputs[port]?.length)
      .map((port) => ({ name: port === "attention_mask" ? "attn_mask" : port, value: inputs[port][0] }));
    return call(attribute(name("self"), fieldId), positional, keywords);
  }
  if (definition.definition_id === "pytorch.nn.lstm") {
    const positional = [inputs.input[0]];
    if (inputs.initial_state?.length) positional.push(inputs.initial_state[0]);
    return call(attribute(name("self"), fieldId), positional);
  }
  const inputPorts = definition.ports.filter((port) => port.direction === "input");
  return call(
    attribute(name("self"), fieldId),
    inputPorts.flatMap((port) => inputs[port.port_id] ?? []),
  );
}

function functionalCall(definition: ModuleDefinition, node: PrototypeNode, inputs: Record<string, PythonExpression[]>): PythonExpression {
  if (definition.definition_id === "pytorch.op.add") {
    const operands = inputs.operands ?? [];
    if (operands.length < 2) throw new Error("Add requires at least two operands");
    return operands.slice(1).reduce(
      (left, right) => call(attribute(name("torch"), "add"), [left, right]),
      operands[0],
    );
  }
  if (definition.definition_id === "pytorch.op.reshape") {
    const shape = node.parameters.shape;
    if (!Array.isArray(shape)) throw new Error("Reshape requires a shape parameter");
    return call(attribute(name("torch"), "reshape"), [inputs.input[0], literal(pythonLiteral(shape))]);
  }
  if (definition.definition_id === "pytorch.op.transpose") {
    const dim0 = node.parameters.dim0;
    const dim1 = node.parameters.dim1;
    if (typeof dim0 !== "number" || typeof dim1 !== "number") {
      throw new Error("Transpose code generation requires numeric dim0 and dim1 parameters");
    }
    return call(attribute(name("torch"), "transpose"), [inputs.input[0], literal(dim0), literal(dim1)]);
  }
  throw new Error(`unsupported functional codegen rule ${definition.codegen_rule_id}`);
}

export function compilePyTorchDraft(graph: PrototypeGraphDocument, className = "GeneratedModel"): CodegenResult {
  const diagnostics: GraphDiagnostic[] = [];
  let portOwners: Map<string, { node: PrototypeNode; portId: string }>;
  let ordered: PrototypeNode[];
  try {
    portOwners = owners(graph);
    ordered = topologicalNodes(graph, portOwners);
  } catch (error) {
    return { draft: null, diagnostics: [diagnostic("CODEGEN_GRAPH_INVALID", String(error), [graph.draft_id])] };
  }
  const incoming = incomingByPort(graph.edges);
  const names = new IdentifierAllocator();
  const valueByPort = new Map<string, PythonExpression>();
  const fields: ModuleInitStatement[] = [];
  const forward: PyTorchDraft["forward"] = [];
  const forwardParameters: string[] = [];
  const sharedFields = new Map<string, { fieldId: string; signature: string }>();

  for (const node of ordered) {
    if (!node.definition_ref) {
      diagnostics.push(diagnostic("CODEGEN_DEFINITION_REQUIRED", "Code generation requires an exact definition reference.", [node.node_id]));
      continue;
    }
    const definition = resolveDefinitionRef(node.definition_ref);
    if (!definition) {
      diagnostics.push(diagnostic("CODEGEN_DEFINITION_STALE", "The pinned registry definition is unavailable.", [node.node_id]));
      continue;
    }
    if (definition.definition_id === "archcanvas.input.tensor") {
      const parameter = names.allocate(node.semantic_name ?? node.node_id.replace(/^draft:/, ""));
      forwardParameters.push(parameter);
      for (const port of node.ports.filter((item) => item.direction === "output")) valueByPort.set(port.port_id, name(parameter));
      continue;
    }
    if (!definition.codegen_rule_id) {
      diagnostics.push(diagnostic("CODEGEN_RULE_MISSING", "The definition has no approved code generation rule.", [node.node_id]));
      continue;
    }
    const inputs: Record<string, PythonExpression[]> = {};
    for (const port of node.ports.filter((item) => item.direction === "input")) {
      const definitionPortId = port.definition_port_id ?? port.name;
      const edges = incoming.get(port.port_id) ?? [];
      inputs[definitionPortId] = edges.flatMap((edge) => {
        const value = valueByPort.get(edge.source_port_id);
        if (!value) {
          diagnostics.push(diagnostic("CODEGEN_INPUT_UNRESOLVED", "The source value is unavailable in topological order.", [node.node_id], [port.port_id]));
          return [];
        }
        return [value];
      });
      const contract = definition.ports.find((item) => item.port_id === definitionPortId);
      if (contract && inputs[definitionPortId].length < contract.min_connections) {
        diagnostics.push(diagnostic("CODEGEN_REQUIRED_PORT_MISSING", `Required port ${definitionPortId} is not bound.`, [node.node_id], [port.port_id]));
      }
    }
    const outputs: Record<string, string> = {};
    for (const port of node.ports.filter((item) => item.direction === "output")) {
      outputs[port.definition_port_id ?? port.name] = names.allocate(`${node.semantic_name ?? node.node_id}_${port.name}`);
    }
    if (diagnostics.some((item) => item.targetIds.includes(node.node_id))) continue;
    try {
      let expression: PythonExpression;
      if (definition.qualified_names.some((item) => item.startsWith("torch.nn."))) {
        const sharingKey = node.parameter_group_id ?? node.node_id;
        const signature = JSON.stringify({ ref: node.definition_ref, parameters: node.parameters });
        const shared = sharedFields.get(sharingKey);
        let fieldId: string;
        if (shared) {
          if (shared.signature !== signature) throw new Error("shared module instances have inconsistent constructor parameters");
          fieldId = shared.fieldId;
        } else {
          fieldId = names.allocate(node.semantic_name ?? node.node_id.replace(/^draft:/, ""));
          sharedFields.set(sharingKey, { fieldId, signature });
          fields.push({
            kind: "module-init",
            fieldId,
            value: constructorExpression(definition, node),
            source: { nodeId: node.node_id, portIds: node.ports.map((port) => port.port_id) },
          });
        }
        expression = moduleCall(fieldId, definition, inputs);
      } else {
        expression = functionalCall(definition, node, inputs);
      }
      forward.push({
        kind: "assignment",
        target: outputTarget(definition.definition_id, outputs),
        value: expression,
        source: { nodeId: node.node_id, portIds: node.ports.map((port) => port.port_id) },
      });
      for (const port of node.ports.filter((item) => item.direction === "output")) {
        valueByPort.set(port.port_id, name(outputs[portKey(node, port.port_id)]));
      }
    } catch (error) {
      diagnostics.push(diagnostic("CODEGEN_RULE_FAILED", error instanceof Error ? error.message : String(error), [node.node_id]));
    }
  }

  if (diagnostics.some((item) => item.severity === "blocking")) return { draft: null, diagnostics };
  const consumed = new Set(graph.edges.map((edge) => edge.source_port_id));
  const terminal = ordered.flatMap((node) => node.ports)
    .filter((port) => port.direction === "output" && !consumed.has(port.port_id))
    .map((port) => valueByPort.get(port.port_id))
    .filter((value): value is PythonExpression => value !== undefined);
  if (!terminal.length) {
    return { draft: null, diagnostics: [diagnostic("CODEGEN_OUTPUT_MISSING", "The graph has no materialized terminal output.", [graph.draft_id])] };
  }
  return {
    diagnostics,
    draft: {
      imports: [{ module: "torch" }, { module: "torch", name: "nn" }],
      className,
      forwardParameters,
      fields,
      forward,
      returns: terminal.length === 1 ? terminal[0] : { kind: "tuple", items: terminal },
    },
  };
}

export const CODEGEN_REGISTRY_DIGEST = MODULE_REGISTRY.bundle_digest;
