from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from archcanvas_core.models import (
    ArchitectureEdge,
    ArchitectureIR,
    ArchitectureNode,
    Confidence,
    EvidenceKind,
    EvidenceRecord,
    FanoutRelation,
    NodeKind,
    Port,
    SourceFile,
    SourceSnapshot,
    TensorValue,
)
from archcanvas_python.analyzer import AnalysisBundle, AnalysisError

ADAPTER_VERSION = "0.1.0"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identifier(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._:-]+", "-", value.lower()).strip("-.")
    return normalized if normalized and normalized[0].isalpha() else f"id-{normalized or 'unknown'}"


def _config(config_bytes: bytes) -> dict[str, Any]:
    try:
        value = json.loads(config_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AnalysisError("CONFIG_INVALID", f"config must be a JSON object: {error}") from error
    if not isinstance(value, dict):
        raise AnalysisError("CONFIG_INVALID", "config must be a JSON object")
    return value


def _shape(value_info: Any) -> str:
    tensor_type = value_info.type.tensor_type
    if not tensor_type.HasField("shape"):
        return "[?]"
    dimensions: list[str] = []
    for dimension in tensor_type.shape.dim:
        if dimension.dim_param:
            dimensions.append(dimension.dim_param)
        elif dimension.HasField("dim_value"):
            dimensions.append(str(dimension.dim_value))
        else:
            dimensions.append("?")
    return f"[{','.join(dimensions)}]"


def _axes(shape: str) -> list[str]:
    if shape == "[?]":
        return ["unknown"]
    aliases = {"B": "batch", "N": "batch", "L": "length", "D": "feature", "C": "channel"}
    return [
        aliases.get(part, "unknown")
        for part in shape.removeprefix("[").removesuffix("]").split(",")
    ]


def _model_path(project: Path, entrypoint: str) -> tuple[Path, Path]:
    resolved_project = project.resolve()
    if resolved_project.is_file():
        if resolved_project.suffix.lower() != ".onnx":
            raise AnalysisError("ENTRYPOINT_NOT_FOUND", "ONNX project file must end with .onnx")
        return resolved_project, resolved_project.parent
    relative = Path(entrypoint)
    if relative.is_absolute() or ".." in relative.parts:
        raise AnalysisError("ENTRYPOINT_INVALID", "ONNX entrypoint must be a project-relative file")
    path = (resolved_project / relative).resolve()
    if not path.is_relative_to(resolved_project) or not path.is_file():
        raise AnalysisError("ENTRYPOINT_NOT_FOUND", f"ONNX model not found: {path}")
    return path, resolved_project


def analyze_onnx(
    project: Path,
    entrypoint: str,
    task: str,
    execution_mode: str,
    config_bytes: bytes = b"{}",
    config_path: Path | None = None,
) -> AnalysisBundle:
    try:
        import onnx
    except ImportError as error:
        raise AnalysisError(
            "ADAPTER_DEPENDENCY_MISSING",
            "ONNX analysis requires the optional 'onnx' package",
        ) from error

    path, root = _model_path(project, entrypoint)
    source_bytes = path.read_bytes()
    source_digest = _sha256(source_bytes)
    config = _config(config_bytes)
    config_digest = _sha256(config_bytes)
    try:
        model = onnx.load(path, load_external_data=False)
        model = onnx.shape_inference.infer_shapes(model)
        onnx.checker.check_model(model, full_check=False)
    except Exception as error:
        raise AnalysisError("ONNX_INVALID", f"could not parse ONNX ModelProto: {error}") from error

    relative_path = path.relative_to(root).as_posix()
    resolved_config_path = str(config_path.resolve()) if config_path else None
    seed = f"{source_digest}:{config_digest}:{relative_path}:{task}:{execution_mode}:onnx".encode()
    snapshot = SourceSnapshot(
        snapshot_id=f"snapshot:{_sha256(seed)[:16]}",
        project_root=str(root),
        revision=f"content:{source_digest}",
        entrypoint=relative_path,
        task=task,
        execution_mode=execution_mode,
        framework="onnx",
        adapter_version=ADAPTER_VERSION,
        config_digest=config_digest,
        config_path=resolved_config_path,
        resolved_config=config,
        source_files=[SourceFile(path=relative_path, sha256=source_digest)],
    )
    predicate = f"task={task} && mode={execution_mode}"
    graph_name = model.graph.name or path.stem
    evidence: list[EvidenceRecord] = []

    def add_evidence(subject: str, claim: str) -> str:
        evidence_id = f"evidence:onnx.{_identifier(subject)}"
        suffix = 2
        existing = {item.evidence_id for item in evidence}
        base = evidence_id
        while evidence_id in existing:
            evidence_id = f"{base}.{suffix}"
            suffix += 1
        evidence.append(
            EvidenceRecord(
                evidence_id=evidence_id,
                kind=EvidenceKind.CHECKPOINT,
                path=relative_path,
                symbol=subject,
                file_sha256=source_digest,
                revision=f"content:{source_digest}",
                claim=claim,
                confidence=Confidence.EXACT,
                execution_predicate=predicate,
            )
        )
        return evidence_id

    shape_by_value = {
        item.name: _shape(item)
        for item in [*model.graph.input, *model.graph.value_info, *model.graph.output]
    }
    initializer_names = {item.name for item in model.graph.initializer}
    root_id = f"node:{_identifier(graph_name)}"
    node_records: list[dict[str, Any]] = []
    producer_by_value: dict[str, tuple[str, str, list[str]]] = {}

    for graph_input in model.graph.input:
        if graph_input.name in initializer_names:
            continue
        key = _identifier(graph_input.name)
        node_id = f"node:input.{key}"
        output_port = f"port:input.{key}.out"
        evidence_ids = [add_evidence(graph_input.name, "ONNX graph declares an external input")]
        node_records.append(
            {
                "node_id": node_id,
                "kind": NodeKind.INPUT_OUTPUT,
                "semantic_name": graph_input.name,
                "input_ports": [],
                "output_ports": [Port(port_id=output_port, name="out", direction="output", role=graph_input.name)],
                "evidence_ids": evidence_ids,
                "attributes": {"io": "input", "onnx_value": graph_input.name},
            }
        )
        producer_by_value[graph_input.name] = (node_id, output_port, evidence_ids)

    for initializer in model.graph.initializer:
        key = _identifier(initializer.name)
        node_id = f"node:initializer.{key}"
        output_port = f"port:initializer.{key}.out"
        evidence_ids = [add_evidence(initializer.name, "ONNX graph declares an initializer tensor")]
        shape_by_value.setdefault(initializer.name, f"[{','.join(map(str, initializer.dims))}]")
        node_records.append(
            {
                "node_id": node_id,
                "kind": NodeKind.STATE,
                "semantic_name": initializer.name,
                "input_ports": [],
                "output_ports": [Port(port_id=output_port, name="out", direction="output", role=initializer.name)],
                "evidence_ids": evidence_ids,
                "attributes": {"onnx_initializer": True, "data_type": int(initializer.data_type)},
            }
        )
        producer_by_value[initializer.name] = (node_id, output_port, evidence_ids)

    pending_edges: list[dict[str, Any]] = []
    for index, onnx_node in enumerate(model.graph.node):
        key = _identifier(onnx_node.name or f"{onnx_node.op_type}.{index}")
        node_id = f"node:onnx.{key}"
        evidence_ids = [
            add_evidence(
                onnx_node.name or f"{onnx_node.op_type}[{index}]",
                f"ONNX graph declares {onnx_node.op_type} with authored input/output order",
            )
        ]
        inputs: list[Port] = []
        for input_index, value_name in enumerate(onnx_node.input):
            if not value_name:
                continue
            port = Port(
                port_id=f"port:onnx.{key}.in{input_index}",
                name=value_name,
                direction="input",
                role=value_name,
            )
            inputs.append(port)
            pending_edges.append(
                {
                    "value": value_name,
                    "consumer_id": node_id,
                    "consumer_port": port.port_id,
                    "consumer_evidence": evidence_ids,
                }
            )
        outputs = [
            Port(
                port_id=f"port:onnx.{key}.out{output_index}",
                name=value_name or f"out{output_index}",
                direction="output",
                role=value_name or f"out{output_index}",
            )
            for output_index, value_name in enumerate(onnx_node.output)
        ]
        node_records.append(
            {
                "node_id": node_id,
                "kind": NodeKind.OPERATOR,
                "semantic_name": onnx_node.name or onnx_node.op_type,
                "input_ports": inputs,
                "output_ports": outputs,
                "evidence_ids": evidence_ids,
                "attributes": {
                    "op_type": onnx_node.op_type,
                    "domain": onnx_node.domain or "ai.onnx",
                    "opset": next(
                        (
                            item.version
                            for item in model.opset_import
                            if item.domain == onnx_node.domain
                        ),
                        None,
                    ),
                },
            }
        )
        for value_name, port in zip(onnx_node.output, outputs, strict=True):
            if value_name:
                producer_by_value[value_name] = (node_id, port.port_id, evidence_ids)

    for graph_output in model.graph.output:
        key = _identifier(graph_output.name)
        node_id = f"node:output.{key}"
        input_port = Port(
            port_id=f"port:output.{key}.in",
            name=graph_output.name,
            direction="input",
            role=graph_output.name,
        )
        output_port = Port(
            port_id=f"port:output.{key}.out",
            name="out",
            direction="output",
            role="output",
        )
        evidence_ids = [add_evidence(graph_output.name, "ONNX graph declares an external output")]
        node_records.append(
            {
                "node_id": node_id,
                "kind": NodeKind.INPUT_OUTPUT,
                "semantic_name": graph_output.name,
                "input_ports": [input_port],
                "output_ports": [output_port],
                "evidence_ids": evidence_ids,
                "attributes": {"io": "output", "onnx_value": graph_output.name},
            }
        )
        pending_edges.append(
            {
                "value": graph_output.name,
                "consumer_id": node_id,
                "consumer_port": input_port.port_id,
                "consumer_evidence": evidence_ids,
            }
        )

    child_ids = [record["node_id"] for record in node_records]
    root_evidence = [add_evidence(graph_name, "ONNX ModelProto contains the selected graph")]
    nodes = [
        ArchitectureNode(
            node_id=root_id,
            kind=NodeKind.MODULE_CONTAINER,
            semantic_name=graph_name,
            source_symbol=graph_name,
            children=child_ids,
            execution_predicate=predicate,
            evidence_ids=root_evidence,
            confidence=Confidence.EXACT,
            attributes={
                "architecture_profile": "generic",
                "framework_adapter": "onnx",
                "ir_version": int(model.ir_version),
            },
        ),
        *[
            ArchitectureNode(
                node_id=record["node_id"],
                kind=record["kind"],
                semantic_name=record["semantic_name"],
                source_symbol=record["semantic_name"],
                parent_id=root_id,
                input_ports=record["input_ports"],
                output_ports=record["output_ports"],
                execution_predicate=predicate,
                evidence_ids=record["evidence_ids"],
                confidence=Confidence.EXACT,
                attributes=record["attributes"],
            )
            for record in node_records
        ],
    ]

    edges: list[ArchitectureEdge] = []
    tensor_consumers: dict[str, list[str]] = {}
    tensor_evidence: dict[str, list[str]] = {}
    for index, pending in enumerate(pending_edges):
        value_name = pending["value"]
        producer = producer_by_value.get(value_name)
        if producer is None:
            raise AnalysisError("ONNX_GRAPH_OPEN", f"no producer found for ONNX value {value_name!r}")
        producer_id, producer_port, producer_evidence = producer
        tensor_id = f"tensor:onnx.{_identifier(value_name)}"
        evidence_ids = list(dict.fromkeys([*producer_evidence, *pending["consumer_evidence"]]))
        edges.append(
            ArchitectureEdge(
                edge_id=f"edge:onnx.{_identifier(value_name)}.{index}",
                tensor_id=tensor_id,
                producer_id=producer_id,
                producer_port=producer_port,
                consumer_id=pending["consumer_id"],
                consumer_port=pending["consumer_port"],
                role=value_name,
                edge_type="state" if producer_id.startswith("node:initializer.") else "main",
                symbolic_shape=shape_by_value.get(value_name, "[?]"),
                semantic_axes=_axes(shape_by_value.get(value_name, "[?]")),
                evidence_ids=evidence_ids,
                confidence=Confidence.EXACT,
                execution_predicate=predicate,
            )
        )
        tensor_consumers.setdefault(value_name, []).append(pending["consumer_id"])
        tensor_evidence.setdefault(value_name, []).extend(evidence_ids)

    tensors = []
    for value_name, consumers in tensor_consumers.items():
        producer_id, producer_port, _ = producer_by_value[value_name]
        shape = shape_by_value.get(value_name, "[?]")
        tensors.append(
            TensorValue(
                tensor_id=f"tensor:onnx.{_identifier(value_name)}",
                role=value_name,
                producer_id=producer_id,
                producer_port=producer_port,
                consumer_ids=list(dict.fromkeys(consumers)),
                symbolic_shape=shape,
                semantic_axes=_axes(shape),
                dtype="unknown",
                provenance="onnx-modelproto",
                confidence=Confidence.EXACT if shape != "[?]" else Confidence.UNRESOLVED,
                evidence_ids=list(dict.fromkeys(tensor_evidence[value_name])),
            )
        )
    fanouts = [
        FanoutRelation(
            relation_id=f"fanout:onnx.{_identifier(tensor.role)}",
            tensor_id=tensor.tensor_id,
            producer_id=tensor.producer_id,
            consumer_ids=tensor.consumer_ids,
            evidence_ids=tensor.evidence_ids,
        )
        for tensor in tensors
        if len(tensor.consumer_ids) > 1
    ]
    architecture = ArchitectureIR(
        architecture_id=f"architecture:{_sha256(seed + b':exact-ir')[:16]}",
        source_snapshot_id=snapshot.snapshot_id,
        framework="onnx",
        entrypoint=relative_path,
        nodes=nodes,
        tensors=tensors,
        edges=edges,
        fanouts=fanouts,
    )
    return AnalysisBundle(snapshot=snapshot, evidence=evidence, architecture=architecture)
