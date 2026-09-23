from __future__ import annotations

import ast
import hashlib
import json
import operator
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from archcanvas_core.models import (
    ArchitectureEdge,
    ArchitectureIR,
    ArchitectureNode,
    ArchitectureParameter,
    Confidence,
    EdgeType,
    EvidenceKind,
    EvidenceRecord,
    FanoutRelation,
    NodeKind,
    ParameterOrigin,
    Port,
    SourceFile,
    SourceSnapshot,
    SourceSpan,
    TensorValue,
    UnresolvedFact,
)

ANALYZER_VERSION = "0.2.0"


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
class _ParameterDraft:
    name: str
    source_expression: str
    value: Any
    origin: ParameterOrigin
    config_names: list[str] = field(default_factory=list)


@dataclass
class _ModuleDraft:
    module_name: str
    op_type: str
    line: int
    end_line: int
    parameters: list[_ParameterDraft]


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
    module: _ModuleDraft | None = None


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
            if isinstance(attribute.value, ast.Name) and attribute.value.id in {
                "self",
                "torch",
                "nn",
            }:
                return
            self.generic_visit(attribute)

    Visitor().visit(node)
    return names


def _config_names(node: ast.AST, config: dict[str, Any]) -> list[str]:
    return sorted(
        {name.id for name in ast.walk(node) if isinstance(name, ast.Name)} & config.keys()
    )


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
}


def _resolve_expression(node: ast.AST, values: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return values.get(node.id, ast.unparse(node))
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    ):
        return values.get(node.attr, ast.unparse(node))
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_resolve_expression(item, values) for item in node.elts]
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _resolve_expression(node.left, values)
        right = _resolve_expression(node.right, values)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return _BINARY_OPERATORS[type(node.op)](left, right)
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return ast.unparse(node)


def _parameter_names(op_type: str, count: int) -> list[str]:
    if op_type.endswith("Linear"):
        names = ["in_features", "out_features", "bias"]
    elif op_type.endswith("LayerNorm"):
        names = ["normalized_shape", "eps", "elementwise_affine"]
    else:
        names = []
    return [names[index] if index < len(names) else f"arg{index}" for index in range(count)]


def _constructor_values(
    class_node: ast.ClassDef,
    config: dict[str, Any],
) -> tuple[ast.FunctionDef | None, dict[str, Any], dict[str, ParameterOrigin]]:
    initializer = next(
        (
            item
            for item in class_node.body
            if isinstance(item, ast.FunctionDef) and item.name == "__init__"
        ),
        None,
    )
    if initializer is None:
        return None, {}, {}
    arguments = [argument.arg for argument in initializer.args.args if argument.arg != "self"]
    defaults = [None] * (len(arguments) - len(initializer.args.defaults)) + list(
        initializer.args.defaults
    )
    values: dict[str, Any] = {}
    origins: dict[str, ParameterOrigin] = {}
    for name, default in zip(arguments, defaults, strict=True):
        if name in config:
            values[name] = config[name]
            origins[name] = ParameterOrigin.CONFIG
        elif default is not None:
            values[name] = _resolve_expression(default, values)
            origins[name] = ParameterOrigin.CONSTRUCTOR_DEFAULT
        else:
            values[name] = name
            origins[name] = ParameterOrigin.UNRESOLVED
    for statement in initializer.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        value = statement.value
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and value is not None
                and not isinstance(value, ast.Call)
            ):
                values[target.attr] = _resolve_expression(value, values)
                names = _config_names(value, config)
                origins[target.attr] = (
                    ParameterOrigin.CONFIG
                    if len(names) == 1 and isinstance(value, ast.Name)
                    else ParameterOrigin.COMPUTED
                )
    return initializer, values, origins


def _registered_modules(
    initializer: ast.FunctionDef | None,
    values: dict[str, Any],
    origins: dict[str, ParameterOrigin],
    config: dict[str, Any],
) -> dict[str, _ModuleDraft]:
    modules: dict[str, _ModuleDraft] = {}
    if initializer is None:
        return modules
    for statement in initializer.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        value = statement.value
        if not isinstance(value, ast.Call):
            continue
        op_type = _call_name(value.func)
        parameter_names = _parameter_names(op_type, len(value.args))
        positional = [
            _ParameterDraft(
                name=parameter_names[index],
                source_expression=ast.unparse(argument),
                value=_resolve_expression(argument, values),
                origin=(
                    origins.get(argument.id, ParameterOrigin.UNRESOLVED)
                    if isinstance(argument, ast.Name)
                    else ParameterOrigin.COMPUTED
                    if _config_names(argument, config)
                    else ParameterOrigin.LITERAL
                ),
                config_names=_config_names(argument, config),
            )
            for index, argument in enumerate(value.args)
        ]
        keywords = [
            _ParameterDraft(
                name=keyword.arg or "**kwargs",
                source_expression=ast.unparse(keyword.value),
                value=_resolve_expression(keyword.value, values),
                origin=(
                    origins.get(keyword.value.id, ParameterOrigin.UNRESOLVED)
                    if isinstance(keyword.value, ast.Name)
                    else ParameterOrigin.COMPUTED
                    if _config_names(keyword.value, config)
                    else ParameterOrigin.LITERAL
                ),
                config_names=_config_names(keyword.value, config),
            )
            for keyword in value.keywords
        ]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                modules[target.attr] = _ModuleDraft(
                    module_name=target.attr,
                    op_type=op_type,
                    line=statement.lineno,
                    end_line=getattr(statement, "end_lineno", statement.lineno),
                    parameters=[*positional, *keywords],
                )
    return modules


def _operation(
    expression: ast.AST,
    target: str,
    modules: dict[str, _ModuleDraft],
) -> tuple[str, NodeKind, _ModuleDraft | None, dict[str, Any]]:
    if isinstance(expression, ast.BinOp):
        names = {
            ast.Add: "Add",
            ast.Mult: "Multiply",
            ast.MatMult: "MatMul",
            ast.Div: "Scale",
            ast.FloorDiv: "Floor divide",
        }
        kind = (
            NodeKind.MERGE_EVENT
            if isinstance(expression.op, (ast.Add, ast.Mult))
            else NodeKind.OPERATOR
        )
        return names.get(type(expression.op), type(expression.op).__name__), kind, None, {}
    if isinstance(expression, ast.Call):
        call = _call_name(expression.func)
        if call.startswith("self."):
            module_name = call.split(".", 1)[1]
            module = modules.get(module_name)
            if module:
                return (
                    module_name,
                    NodeKind.OPERATOR,
                    module,
                    {
                        "module_path": call,
                        "op_type": module.op_type,
                    },
                )
        if target.endswith("_split"):
            return "Split heads", NodeKind.OPERATOR, None, {"op_type": call}
        if target.endswith("_k_t"):
            return "Transpose K", NodeKind.OPERATOR, None, {"op_type": call}
        if target.endswith("_concat"):
            return "Concat heads", NodeKind.OPERATOR, None, {"op_type": call}
        if target == "masked_scores":
            return "Apply target mask", NodeKind.OPERATOR, None, {"op_type": call}
        if call in {"torch.cat", "torch.stack", "torch.add"}:
            return (
                call.removeprefix("torch.").title(),
                NodeKind.MERGE_EVENT,
                None,
                {"op_type": call},
            )
        return call, NodeKind.OPERATOR, None, {"op_type": call}
    return (
        type(expression).__name__,
        NodeKind.OPERATOR,
        None,
        {"op_type": type(expression).__name__},
    )


def _symbolic_dimension(expression: str, config: dict[str, Any]) -> str:
    compact = expression.replace(" ", "")
    aliases = {
        "d_model": "D",
        "vocab_size": "V",
        "num_heads": "H",
        "d_model//num_heads": "Dh",
        "d_model*4": "4D",
        "4*d_model": "4D",
    }
    if compact in aliases:
        return aliases[compact]
    value = config.get(expression)
    for name, alias in (("d_model", "D"), ("vocab_size", "V"), ("num_heads", "H")):
        if value is not None and value == config.get(name):
            return alias
    return str(value if value is not None else expression)


def _shape_parts(shape: str) -> list[str]:
    if not shape.startswith("[") or not shape.endswith("]"):
        return []
    return [part.strip() for part in shape[1:-1].split(",") if part.strip()]


def _shape_axes(shape: str) -> list[str]:
    axes = {
        "B": "batch",
        "H": "head",
        "S": "source_length",
        "T": "target_length",
        "D": "model_depth",
        "Dh": "head_depth",
        "4D": "feature_depth",
        "V": "vocabulary",
        "1": "broadcast",
    }
    return [axes.get(part, "unknown") for part in _shape_parts(shape)]


def _infer_shape(
    target: str,
    expression: ast.AST,
    module: _ModuleDraft | None,
    dependencies: list[tuple[str, str]],
    shapes: dict[str, str],
    config: dict[str, Any],
) -> str:
    dependency_shapes = [shapes.get(name, "[?]") for name, _ in dependencies]
    first = dependency_shapes[0] if dependency_shapes else "[?]"
    if target.endswith("_split"):
        parts = _shape_parts(first)
        return f"[B,H,{parts[1]},Dh]" if len(parts) == 3 else "[?]"
    if target.endswith("_k_t"):
        parts = _shape_parts(first)
        return f"[{','.join([*parts[:-2], parts[-1], parts[-2]])}]" if len(parts) >= 2 else "[?]"
    if target.endswith("_scores_raw") and len(dependency_shapes) >= 2:
        query = _shape_parts(dependency_shapes[0])
        key = _shape_parts(dependency_shapes[1])
        return f"[B,H,{query[-2]},{key[-1]}]" if len(query) == 4 and len(key) == 4 else "[?]"
    if target.endswith("_context_heads") and len(dependency_shapes) >= 2:
        weights = _shape_parts(dependency_shapes[0])
        value = _shape_parts(dependency_shapes[1])
        return (
            f"[B,H,{weights[-2]},{value[-1]}]" if len(weights) == 4 and len(value) == 4 else "[?]"
        )
    if target.endswith("_concat"):
        parts = _shape_parts(first)
        return f"[B,{parts[-2]},D]" if len(parts) == 4 else "[?]"
    if module and module.op_type.endswith("Linear"):
        parts = _shape_parts(first)
        if parts and len(module.parameters) >= 2:
            parts[-1] = _symbolic_dimension(module.parameters[1].source_expression, config)
            return f"[{','.join(parts)}]"
    if module and (module.op_type.endswith("LayerNorm") or module.op_type.endswith("GELU")):
        return first
    if isinstance(expression, ast.BinOp) or target.endswith(("_scores", "_weights")):
        return first
    return first


def _edge_type(variable: str, consumer: _NodeDraft) -> EdgeType:
    lowered = variable.lower()
    if "mask" in lowered:
        return EdgeType.CONDITION
    if "memory" in lowered:
        return EdgeType.MEMORY
    if consumer.kind is NodeKind.MERGE_EVENT:
        return EdgeType.RESIDUAL
    return EdgeType.MAIN


def _parse_config(config_bytes: bytes) -> dict[str, Any]:
    try:
        value = json.loads(config_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AnalysisError("CONFIG_INVALID", f"config must be a JSON object: {error}") from error
    if not isinstance(value, dict):
        raise AnalysisError("CONFIG_INVALID", "config must be a JSON object")
    return value


def analyze_project(
    project: Path,
    entrypoint: str,
    task: str,
    execution_mode: str,
    config_bytes: bytes = b"{}",
    config_path: Path | None = None,
) -> AnalysisBundle:
    project = project.resolve()
    if ":" not in entrypoint:
        raise AnalysisError("ENTRYPOINT_FORMAT", "entrypoint must use module:Class syntax")
    module_name, class_name = entrypoint.split(":", 1)
    source_path = project / (module_name.replace(".", "/") + ".py")
    if not source_path.is_file() or not source_path.resolve().is_relative_to(project):
        raise AnalysisError("ENTRYPOINT_NOT_FOUND", f"source module not found: {source_path}")
    config = _parse_config(config_bytes)
    source_bytes = source_path.read_bytes()
    source_digest = _sha256(source_bytes)
    config_digest = _sha256(config_bytes)
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
        (
            node
            for node in class_node.body
            if isinstance(node, ast.FunctionDef) and node.name == "forward"
        ),
        None,
    )
    if forward is None:
        raise AnalysisError("FORWARD_NOT_FOUND", f"{class_name} has no forward method")

    relative_path = source_path.relative_to(project).as_posix()
    resolved_config_path: str | None = None
    if config_path:
        resolved = config_path.resolve()
        resolved_config_path = (
            resolved.relative_to(project).as_posix()
            if resolved.is_relative_to(project)
            else str(resolved)
        )
    snapshot_seed = f"{source_digest}:{config_digest}:{entrypoint}:{task}:{execution_mode}".encode()
    snapshot = SourceSnapshot(
        snapshot_id=f"snapshot:{_sha256(snapshot_seed)[:16]}",
        project_root=str(project),
        revision=f"content:{source_digest}",
        entrypoint=entrypoint,
        task=task,
        execution_mode=execution_mode,
        framework="pytorch",
        adapter_version=ANALYZER_VERSION,
        config_digest=config_digest,
        config_path=resolved_config_path,
        resolved_config=config,
        source_files=[SourceFile(path=relative_path, sha256=source_digest)],
    )

    predicate = f"task={task} && mode={execution_mode}"
    evidence: list[EvidenceRecord] = []
    config_evidence: dict[str, str] = {}
    for key in sorted(config):
        evidence_id = f"evidence:config.{_identifier(key)}"
        config_evidence[key] = evidence_id
        evidence.append(
            EvidenceRecord(
                evidence_id=evidence_id,
                kind=EvidenceKind.CONFIG,
                path=resolved_config_path,
                symbol=key,
                file_sha256=config_digest,
                revision=f"content:{config_digest}",
                claim=f"Resolved config provides {key}",
                confidence=Confidence.EXACT,
                execution_predicate=predicate,
            )
        )

    initializer, constructor_values, constructor_origins = _constructor_values(class_node, config)
    modules = _registered_modules(
        initializer,
        constructor_values,
        constructor_origins,
        config,
    )
    drafts: list[_NodeDraft] = []
    container = _NodeDraft(
        node_id=f"node:{_identifier(class_name)}",
        kind=NodeKind.MODULE_CONTAINER,
        semantic_name=class_name,
        source_symbol=class_name,
        line=class_node.lineno,
        end_line=getattr(class_node, "end_lineno", class_node.lineno),
        attributes={"model_class": class_name},
    )
    drafts.append(container)

    variable_producer: dict[str, str] = {}
    shapes: dict[str, str] = {}
    input_shapes = config.get("input_shapes", {})
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
            attributes={"io": "input", "assigned_symbol": argument},
        )
        drafts.append(draft)
        variable_producer[argument] = draft.node_id
        shapes[argument] = input_shapes.get(argument, "[?]")

    unresolved: list[UnresolvedFact] = []
    used_node_ids: set[str] = {draft.node_id for draft in drafts}
    for statement in forward.body:
        target: str | None = None
        expression: ast.AST | None = None
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
        ):
            target, expression = statement.targets[0].id, statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            target, expression = statement.target.id, statement.value
        elif isinstance(statement, ast.Return):
            dependencies = [
                (name, variable_producer[name])
                for name in (_loaded_names(statement.value) if statement.value else [])
                if name in variable_producer
            ]
            drafts.append(
                _NodeDraft(
                    node_id="node:output.model",
                    kind=NodeKind.INPUT_OUTPUT,
                    semantic_name="Model output",
                    source_symbol=f"{class_name}.forward",
                    line=statement.lineno,
                    end_line=getattr(statement, "end_lineno", statement.lineno),
                    dependencies=dependencies,
                    attributes={"io": "output", "assigned_symbol": "model_output"},
                )
            )
            continue
        elif isinstance(statement, (ast.If, ast.For, ast.While, ast.Try, ast.Match)):
            unresolved.append(
                UnresolvedFact(
                    code="CONTROL_FLOW_NOT_EXPANDED",
                    message=(
                        f"Static Stage 1 adapter did not expand {type(statement).__name__} "
                        f"at line {statement.lineno}."
                    ),
                    blocking=False,
                )
            )
        if not target or expression is None:
            continue
        semantic_name, kind, module, attributes = _operation(expression, target, modules)
        canonical = module.module_name if module else target
        base_node_id = f"node:{_identifier(canonical)}"
        node_id = base_node_id
        suffix = 2
        while node_id in used_node_ids:
            node_id = f"{base_node_id}.{suffix}"
            suffix += 1
        used_node_ids.add(node_id)
        dependencies = [
            (name, variable_producer[name])
            for name in _loaded_names(expression)
            if name in variable_producer
        ]
        draft = _NodeDraft(
            node_id=node_id,
            kind=kind,
            semantic_name=semantic_name,
            source_symbol=f"{class_name}.forward",
            line=statement.lineno,
            end_line=getattr(statement, "end_lineno", statement.lineno),
            target=target,
            dependencies=dependencies,
            attributes={
                **attributes,
                "assigned_symbol": target,
                "source_expression": ast.unparse(expression),
            },
            module=module,
        )
        drafts.append(draft)
        variable_producer[target] = node_id
        shapes[target] = _infer_shape(target, expression, module, dependencies, shapes, config)

    evidence_by_node: dict[str, list[str]] = {}

    def add_source_evidence(
        evidence_id: str,
        symbol: str,
        line: int,
        end_line: int,
        claim: str,
    ) -> None:
        evidence.append(
            EvidenceRecord(
                evidence_id=evidence_id,
                kind=EvidenceKind.SOURCE,
                path=relative_path,
                symbol=symbol,
                span=SourceSpan(start_line=line, end_line=end_line),
                file_sha256=source_digest,
                revision=f"content:{source_digest}",
                claim=claim,
                confidence=Confidence.EXACT,
                execution_predicate=predicate,
            )
        )

    for index, draft in enumerate(drafts):
        flow_id = f"evidence:{_identifier(class_name)}.forward.{index}"
        add_source_evidence(
            flow_id,
            draft.source_symbol,
            draft.line,
            draft.end_line,
            f"{draft.semantic_name} participates in the selected forward dependency path",
        )
        evidence_by_node[draft.node_id] = [flow_id]
        if draft.module:
            definition_id = (
                f"evidence:{_identifier(class_name)}.init.{_identifier(draft.module.module_name)}"
            )
            add_source_evidence(
                definition_id,
                f"{class_name}.__init__",
                draft.module.line,
                draft.module.end_line,
                f"self.{draft.module.module_name} is constructed as {draft.module.op_type}",
            )
            evidence_by_node[draft.node_id].append(definition_id)

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
    known_shape_evidence = [
        config_evidence[key]
        for key in ("input_shapes", "d_model", "num_heads", "vocab_size")
        if key in config_evidence
    ]
    for draft in drafts:
        for index, (variable, producer_id) in enumerate(draft.dependencies):
            consumer_port = Port(
                port_id=f"port:{draft.node_id.removeprefix('node:')}.in{index}",
                name=variable,
                direction="input",
                role=variable,
            )
            input_ports[draft.node_id].append(consumer_port)
            producer_port = output_ports[producer_id][0]
            tensor_id = f"tensor:{_identifier(variable)}"
            edge_id = (
                f"edge:{producer_id.removeprefix('node:')}:"
                f"{draft.node_id.removeprefix('node:')}:{index}"
            )
            edge_evidence = list(
                dict.fromkeys([*evidence_by_node[producer_id], *evidence_by_node[draft.node_id]])
            )
            edges.append(
                ArchitectureEdge(
                    edge_id=edge_id,
                    tensor_id=tensor_id,
                    producer_id=producer_id,
                    producer_port=producer_port.port_id,
                    consumer_id=draft.node_id,
                    consumer_port=consumer_port.port_id,
                    role=variable,
                    edge_type=_edge_type(variable, draft),
                    symbolic_shape=shapes.get(variable, "[?]"),
                    semantic_axes=_shape_axes(shapes.get(variable, "[?]")),
                    evidence_ids=edge_evidence,
                    confidence=Confidence.EXACT,
                    execution_predicate=predicate,
                )
            )
            prior = tensors.get(tensor_id)
            consumers = [*prior.consumer_ids, draft.node_id] if prior else [draft.node_id]
            tensor_evidence = list(
                dict.fromkeys(
                    [
                        *evidence_by_node[producer_id],
                        *evidence_by_node[draft.node_id],
                        *(known_shape_evidence if shapes.get(variable, "[?]") != "[?]" else []),
                    ]
                )
            )
            tensors[tensor_id] = TensorValue(
                tensor_id=tensor_id,
                role=variable,
                producer_id=producer_id,
                producer_port=producer_port.port_id,
                consumer_ids=consumers,
                symbolic_shape=shapes.get(variable, "[?]"),
                semantic_axes=_shape_axes(shapes.get(variable, "[?]")),
                dtype="unknown",
                provenance=(
                    "source+config" if shapes.get(variable, "[?]") != "[?]" else "static-source"
                ),
                confidence=(
                    Confidence.EXACT
                    if shapes.get(variable, "[?]") != "[?]"
                    else Confidence.UNRESOLVED
                ),
                evidence_ids=tensor_evidence,
            )

    child_ids = [draft.node_id for draft in drafts if draft is not container]
    nodes: list[ArchitectureNode] = []
    for draft in drafts:
        parameter_models: list[ArchitectureParameter] = []
        if draft.module:
            definition_ids = evidence_by_node[draft.node_id]
            for parameter in draft.module.parameters:
                parameter_evidence = list(
                    dict.fromkeys(
                        [
                            *definition_ids,
                            *(config_evidence[name] for name in parameter.config_names),
                        ]
                    )
                )
                parameter_models.append(
                    ArchitectureParameter(
                        name=parameter.name,
                        source_expression=parameter.source_expression,
                        value=parameter.value,
                        origin=parameter.origin,
                        evidence_ids=parameter_evidence,
                    )
                )
        nodes.append(
            ArchitectureNode(
                node_id=draft.node_id,
                kind=draft.kind,
                semantic_name=draft.semantic_name,
                source_symbol=draft.source_symbol,
                parent_id=None if draft is container else container.node_id,
                children=child_ids if draft is container else [],
                input_ports=input_ports[draft.node_id],
                output_ports=output_ports[draft.node_id],
                parameters=parameter_models,
                parameter_identity=(
                    "independent-module-parameters" if draft.module else "not-applicable"
                ),
                execution_predicate=predicate,
                evidence_ids=evidence_by_node[draft.node_id],
                confidence=Confidence.EXACT,
                attributes=draft.attributes,
            )
        )

    fanouts = [
        FanoutRelation(
            relation_id=f"fanout:{tensor.tensor_id.removeprefix('tensor:')}",
            tensor_id=tensor.tensor_id,
            producer_id=tensor.producer_id,
            consumer_ids=tensor.consumer_ids,
            evidence_ids=tensor.evidence_ids,
        )
        for tensor in tensors.values()
        if len(tensor.consumer_ids) > 1
    ]
    architecture = ArchitectureIR(
        architecture_id=f"architecture:{_sha256(snapshot_seed)[:16]}",
        source_snapshot_id=snapshot.snapshot_id,
        framework="pytorch",
        entrypoint=entrypoint,
        nodes=nodes,
        tensors=list(tensors.values()),
        edges=edges,
        fanouts=fanouts,
        unresolved=unresolved,
    )
    return AnalysisBundle(snapshot=snapshot, evidence=evidence, architecture=architecture)
