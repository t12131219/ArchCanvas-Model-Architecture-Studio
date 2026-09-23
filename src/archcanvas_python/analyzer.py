from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from archcanvas_core.models import (
    ArchitectureEdge,
    ArchitectureIR,
    ArchitectureNode,
    Confidence,
    EdgeType,
    EvidenceKind,
    EvidenceRecord,
    NodeKind,
    Port,
    SourceFile,
    SourceSnapshot,
    SourceSpan,
    TensorValue,
    UnresolvedFact,
)

ANALYZER_VERSION = "0.1.0"


class AnalysisError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class AnalysisBundle:
    snapshot: SourceSnapshot
    evidence: list[EvidenceRecord]
    architecture: ArchitectureIR


@dataclass
class _NodeDraft:
    node_id: str
    kind: NodeKind
    semantic_name: str
    source_symbol: str
    line: int
    end_line: int
    target: str | None = None
    dependencies: list[tuple[str, str]] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identifier(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._:-]+", "-", value.lower()).strip("-.")
    return normalized if normalized and normalized[0].isalpha() else f"id-{normalized or 'unknown'}"


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return "call"


def _loaded_names(node: ast.AST) -> list[str]:
    names: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_Name(self, name: ast.Name) -> None:
            if isinstance(name.ctx, ast.Load) and name.id not in names:
                names.append(name.id)

        def visit_Attribute(self, attribute: ast.Attribute) -> None:
            if isinstance(attribute.value, ast.Name) and attribute.value.id in {"self", "torch", "nn"}:
                return
            self.generic_visit(attribute)

    Visitor().visit(node)
    return names


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return ast.unparse(node)


def _registered_modules(class_node: ast.ClassDef) -> dict[str, dict[str, Any]]:
    modules: dict[str, dict[str, Any]] = {}
    initializer = next(
        (item for item in class_node.body if isinstance(item, ast.FunctionDef) and item.name == "__init__"),
        None,
    )
    if initializer is None:
        return modules
    for statement in ast.walk(initializer):
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        value = statement.value
        if not isinstance(value, ast.Call):
            continue
        for target in targets:
            if not (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                continue
            modules[target.attr] = {
                "op_type": _call_name(value.func),
                "parameters": [_literal(argument) for argument in value.args],
                "keywords": {item.arg or "**": _literal(item.value) for item in value.keywords},
                "line": statement.lineno,
                "end_line": getattr(statement, "end_lineno", statement.lineno),
            }
    return modules


def _operation(expression: ast.AST, target: str, modules: dict[str, dict[str, Any]]) -> tuple[str, NodeKind, dict[str, Any]]:
    if isinstance(expression, ast.BinOp):
        names = {ast.Add: "Add", ast.Mult: "Multiply", ast.MatMult: "MatMul"}
        return names.get(type(expression.op), type(expression.op).__name__), NodeKind.MERGE_EVENT, {}
    if isinstance(expression, ast.Call):
        call = _call_name(expression.func)
        if call.startswith("self."):
            module_name = call.split(".", 1)[1]
            metadata = modules.get(module_name, {})
            return module_name, NodeKind.OPERATOR, {**metadata, "module_path": call}
        if call in {"torch.cat", "torch.stack", "torch.add"}:
            return call.removeprefix("torch.").title(), NodeKind.MERGE_EVENT, {}
        return call, NodeKind.OPERATOR, {}
    return type(expression).__name__, NodeKind.OPERATOR, {}


def _edge_type(variable: str, consumer: _NodeDraft) -> EdgeType:
    lowered = variable.lower()
    if "mask" in lowered:
        return EdgeType.CONDITION
    if "memory" in lowered or "encoder" in lowered and "decoder" in consumer.node_id:
        return EdgeType.MEMORY
    if consumer.kind is NodeKind.MERGE_EVENT:
        return EdgeType.RESIDUAL
    return EdgeType.MAIN


def analyze_project(
    project: Path,
    entrypoint: str,
    task: str,
    execution_mode: str,
    config_bytes: bytes = b"{}",
) -> AnalysisBundle:
    project = project.resolve()
    if ":" not in entrypoint:
        raise AnalysisError("ENTRYPOINT_FORMAT", "entrypoint must use module:Class syntax")
    module_name, class_name = entrypoint.split(":", 1)
    source_path = project / (module_name.replace(".", "/") + ".py")
    if not source_path.is_file() or not source_path.resolve().is_relative_to(project):
        raise AnalysisError("ENTRYPOINT_NOT_FOUND", f"source module not found: {source_path}")
    source_bytes = source_path.read_bytes()
    source_digest = _sha256(source_bytes)
    try:
        tree = ast.parse(source_bytes, filename=str(source_path))
    except SyntaxError as error:
        raise AnalysisError("SOURCE_SYNTAX_ERROR", str(error)) from error
    class_node = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name),
        None,
    )
    if class_node is None:
        raise AnalysisError("ENTRYPOINT_SYMBOL_NOT_FOUND", f"class {class_name!r} was not found")
    forward = next(
        (node for node in class_node.body if isinstance(node, ast.FunctionDef) and node.name == "forward"),
        None,
    )
    if forward is None:
        raise AnalysisError("FORWARD_NOT_FOUND", f"{class_name} has no forward method")

    relative_path = source_path.relative_to(project).as_posix()
    config_digest = _sha256(config_bytes)
    snapshot_seed = f"{source_digest}:{entrypoint}:{task}:{execution_mode}".encode()
    snapshot_id = f"snapshot:{_sha256(snapshot_seed)[:16]}"
    snapshot = SourceSnapshot(
        snapshot_id=snapshot_id,
        project_root=str(project),
        revision=f"content:{source_digest}",
        entrypoint=entrypoint,
        task=task,
        execution_mode=execution_mode,
        framework="pytorch",
        adapter_version=ANALYZER_VERSION,
        config_digest=config_digest,
        source_files=[SourceFile(path=relative_path, sha256=source_digest)],
    )

    evidence: list[EvidenceRecord] = []
    drafts: list[_NodeDraft] = []
    predicate = f"task={task} && mode={execution_mode}"

    def add_evidence(node: _NodeDraft, suffix: str) -> str:
        evidence_id = f"evidence:{_identifier(class_name)}.{_identifier(suffix)}"
        evidence.append(
            EvidenceRecord(
                evidence_id=evidence_id,
                kind=EvidenceKind.SOURCE,
                path=relative_path,
                symbol=node.source_symbol,
                span=SourceSpan(start_line=node.line, end_line=node.end_line),
                revision=f"content:{source_digest}",
                claim=f"{node.semantic_name} participates in the selected forward path",
                confidence=Confidence.EXACT,
                execution_predicate=predicate,
            )
        )
        return evidence_id

    container = _NodeDraft(
        node_id=f"node:{_identifier(class_name)}",
        kind=NodeKind.MODULE_CONTAINER,
        semantic_name=class_name,
        source_symbol=class_name,
        line=class_node.lineno,
        end_line=getattr(class_node, "end_lineno", class_node.lineno),
    )
    drafts.append(container)
    variable_producer: dict[str, str] = {}
    forward_args = [argument.arg for argument in forward.args.args if argument.arg != "self"]
    for argument in forward_args:
        draft = _NodeDraft(
            node_id=f"node:input.{_identifier(argument)}",
            kind=NodeKind.INPUT_OUTPUT,
            semantic_name=argument,
            source_symbol=f"{class_name}.forward",
            line=forward.lineno,
            end_line=forward.lineno,
            target=argument,
            attributes={"io": "input"},
        )
        drafts.append(draft)
        variable_producer[argument] = draft.node_id

    modules = _registered_modules(class_node)
    call_counts: dict[str, int] = {}
    unresolved: list[UnresolvedFact] = []
    for statement in forward.body:
        target: str | None = None
        expression: ast.AST | None = None
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
            target, expression = statement.targets[0].id, statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            target, expression = statement.target.id, statement.value
        elif isinstance(statement, ast.Return):
            dependencies = [
                (name, variable_producer[name])
                for name in (_loaded_names(statement.value) if statement.value else [])
                if name in variable_producer
            ]
            output = _NodeDraft(
                node_id="node:output.model",
                kind=NodeKind.INPUT_OUTPUT,
                semantic_name="Model output",
                source_symbol=f"{class_name}.forward",
                line=statement.lineno,
                end_line=getattr(statement, "end_lineno", statement.lineno),
                dependencies=dependencies,
                attributes={"io": "output"},
            )
            drafts.append(output)
            continue
        elif isinstance(statement, (ast.If, ast.For, ast.While, ast.Try, ast.Match)):
            unresolved.append(
                UnresolvedFact(
                    code="CONTROL_FLOW_NOT_EXPANDED",
                    message=f"Static baseline did not expand {type(statement).__name__} at line {statement.lineno}.",
                    blocking=False,
                )
            )
        if not target or expression is None:
            continue
        operation, kind, attributes = _operation(expression, target, modules)
        key = _identifier(operation)
        call_counts[key] = call_counts.get(key, 0) + 1
        suffix = "" if call_counts[key] == 1 else f".{call_counts[key]}"
        node_id = f"node:{key}{suffix}"
        dependencies = [
            (name, variable_producer[name])
            for name in _loaded_names(expression)
            if name in variable_producer
        ]
        draft = _NodeDraft(
            node_id=node_id,
            kind=kind,
            semantic_name=operation.split(".")[-1],
            source_symbol=f"{class_name}.forward",
            line=statement.lineno,
            end_line=getattr(statement, "end_lineno", statement.lineno),
            target=target,
            dependencies=dependencies,
            attributes={**attributes, "assigned_symbol": target},
        )
        drafts.append(draft)
        variable_producer[target] = node_id

    evidence_by_node: dict[str, str] = {}
    for index, draft in enumerate(drafts):
        evidence_by_node[draft.node_id] = add_evidence(draft, f"{index}.{draft.node_id.removeprefix('node:')}")

    input_ports: dict[str, list[Port]] = {draft.node_id: [] for draft in drafts}
    output_ports: dict[str, list[Port]] = {draft.node_id: [] for draft in drafts}
    for draft in drafts:
        if draft.kind is not NodeKind.MODULE_CONTAINER:
            output_ports[draft.node_id].append(
                Port(
                    port_id=f"port:{draft.node_id.removeprefix('node:')}.out",
                    name="out",
                    direction="output",
                    role=draft.target or "output",
                )
            )

    tensors: dict[str, TensorValue] = {}
    edges: list[ArchitectureEdge] = []
    for draft in drafts:
        for index, (variable, producer_id) in enumerate(draft.dependencies):
            if producer_id == draft.node_id:
                continue
            consumer_port = Port(
                port_id=f"port:{draft.node_id.removeprefix('node:')}.in{index}",
                name=variable,
                direction="input",
                role=variable,
            )
            input_ports[draft.node_id].append(consumer_port)
            producer_port = output_ports[producer_id][0]
            tensor_id = f"tensor:{_identifier(variable)}"
            edge_id = f"edge:{producer_id.removeprefix('node:')}:{draft.node_id.removeprefix('node:')}:{index}"
            edge_type = _edge_type(variable, draft)
            edges.append(
                ArchitectureEdge(
                    edge_id=edge_id,
                    tensor_id=tensor_id,
                    producer_id=producer_id,
                    producer_port=producer_port.port_id,
                    consumer_id=draft.node_id,
                    consumer_port=consumer_port.port_id,
                    role=variable,
                    edge_type=edge_type,
                    evidence_ids=[evidence_by_node[draft.node_id]],
                    confidence=Confidence.EXACT,
                    execution_predicate=predicate,
                )
            )
            prior = tensors.get(tensor_id)
            consumers = ([*prior.consumer_ids, draft.node_id] if prior else [draft.node_id])
            tensors[tensor_id] = TensorValue(
                tensor_id=tensor_id,
                role=variable,
                producer_id=producer_id,
                producer_port=producer_port.port_id,
                consumer_ids=consumers,
                symbolic_shape="[?]",
                semantic_axes=[],
                dtype="unknown",
                provenance="static-source",
                confidence=Confidence.INFERRED,
                evidence_ids=[evidence_by_node[producer_id], evidence_by_node[draft.node_id]],
            )

    nodes = [
        ArchitectureNode(
            node_id=draft.node_id,
            kind=draft.kind,
            semantic_name=draft.semantic_name,
            source_symbol=draft.source_symbol,
            parent_id=None if draft.kind is NodeKind.MODULE_CONTAINER else container.node_id,
            input_ports=input_ports[draft.node_id],
            output_ports=output_ports[draft.node_id],
            parameter_identity=(
                "independent-module-parameters" if draft.kind is NodeKind.OPERATOR else "not-applicable"
            ),
            execution_predicate=predicate,
            evidence_ids=[evidence_by_node[draft.node_id]],
            confidence=Confidence.EXACT,
            attributes=draft.attributes,
        )
        for draft in drafts
    ]
    architecture = ArchitectureIR(
        architecture_id=f"architecture:{_sha256(snapshot_seed)[:16]}",
        source_snapshot_id=snapshot.snapshot_id,
        framework="pytorch",
        entrypoint=entrypoint,
        nodes=nodes,
        tensors=list(tensors.values()),
        edges=edges,
        unresolved=unresolved,
    )
    return AnalysisBundle(snapshot=snapshot, evidence=evidence, architecture=architecture)
