from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from archcanvas_core.models import (
    ArchitectureEdge,
    ArchitectureNode,
    Confidence,
    EdgeType,
    FanoutRelation,
    NodeKind,
    Port,
    TensorValue,
)

from .analyzer import AnalysisError


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identifier(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._:-]+", "-", value.lower()).strip("-.")
    return normalized if normalized and normalized[0].isalpha() else f"id-{normalized or 'unknown'}"


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return "call"


@dataclass(frozen=True)
class SourceDocument:
    path: str
    data: bytes
    digest: str
    tree: ast.Module
    profile: str

    def class_node(self, class_name: str) -> ast.ClassDef:
        class_node = next(
            (
                node
                for node in self.tree.body
                if isinstance(node, ast.ClassDef) and node.name == class_name
            ),
            None,
        )
        if class_node is None:
            raise AnalysisError(
                f"{self.profile.upper()}_SOURCE_CONTRACT",
                f"{self.path} is missing class {class_name}",
            )
        return class_node

    def method(self, class_name: str, method_name: str) -> ast.FunctionDef:
        class_node = self.class_node(class_name)
        method = next(
            (
                node
                for node in class_node.body
                if isinstance(node, ast.FunctionDef) and node.name == method_name
            ),
            None,
        )
        if method is None:
            raise AnalysisError(
                f"{self.profile.upper()}_SOURCE_CONTRACT",
                f"{self.path}:{class_name} is missing {method_name}",
            )
        return method


def load_sources(
    project: Path,
    source_paths: tuple[str, ...],
    profile: str,
) -> dict[str, SourceDocument]:
    try:
        provenance = json.loads((project / "provenance.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AnalysisError(f"{profile.upper()}_PROVENANCE_INVALID", str(error)) from error
    expected = provenance.get("members", {})
    documents: dict[str, SourceDocument] = {}
    for relative_path in source_paths:
        path = project / relative_path
        try:
            data = path.read_bytes()
            tree = ast.parse(data, filename=str(path))
        except (OSError, SyntaxError) as error:
            raise AnalysisError(f"{profile.upper()}_SOURCE_INVALID", str(error)) from error
        digest = sha256(data)
        if expected.get(relative_path) != digest:
            raise AnalysisError(
                f"{profile.upper()}_SOURCE_STALE",
                f"{relative_path} does not match provenance.json",
            )
        documents[relative_path] = SourceDocument(relative_path, data, digest, tree, profile)
    return documents


def method_calls(method: ast.FunctionDef) -> set[str]:
    return {call_name(node.func) for node in ast.walk(method) if isinstance(node, ast.Call)}


def require_calls(
    document: SourceDocument,
    class_name: str,
    method_name: str,
    required: set[str],
) -> ast.FunctionDef:
    method = document.method(class_name, method_name)
    missing = required - method_calls(method)
    if missing:
        raise AnalysisError(
            f"{document.profile.upper()}_SOURCE_CONTRACT",
            f"{document.path}:{class_name}.{method_name} is missing calls {sorted(missing)}",
        )
    return method


@dataclass
class _NodeSpec:
    node_id: str
    semantic_name: str
    kind: NodeKind
    parent_id: str | None
    evidence_ids: list[str]
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _Connection:
    producer_id: str
    role: str
    consumer_id: str
    edge_type: EdgeType
    shape: str
    evidence_ids: list[str]


def shape_axes(shape: str) -> list[str]:
    names = {
        "B": "batch",
        "L": "lookback_length",
        "S": "prediction_length",
        "N": "variable",
        "M": "covariate",
        "N+M": "variable_or_covariate_token",
        "C": "channel",
        "D": "model_depth",
        "P": "patch_length",
        "Np": "patch_count",
        "BC": "batch_channel",
        "K": "scale",
    }
    if not shape.startswith("[") or not shape.endswith("]"):
        return []
    return [names.get(part.strip(), "unknown") for part in shape[1:-1].split(",")]


class ProfileGraphBuilder:
    def __init__(self, profile: str, predicate: str) -> None:
        self.profile = profile
        self.predicate = predicate
        self.root_id = f"node:{profile}"
        self.nodes: dict[str, _NodeSpec] = {}
        self.connections: list[_Connection] = []

    def node(
        self,
        node_id: str,
        semantic_name: str,
        evidence_ids: list[str],
        *,
        kind: NodeKind = NodeKind.OPERATOR,
        parent_id: str | None | object = ...,
        **attributes: Any,
    ) -> str:
        resolved_parent = self.root_id if parent_id is ... else parent_id
        self.nodes[node_id] = _NodeSpec(
            node_id,
            semantic_name,
            kind,
            resolved_parent,
            evidence_ids,
            attributes,
        )
        return node_id

    def connect(
        self,
        producer_id: str,
        role: str,
        consumer_id: str,
        shape: str,
        evidence_ids: list[str],
        edge_type: EdgeType = EdgeType.MAIN,
    ) -> None:
        self.connections.append(
            _Connection(
                producer_id,
                role,
                consumer_id,
                edge_type,
                shape,
                evidence_ids,
            )
        )

    def build(
        self,
    ) -> tuple[
        list[ArchitectureNode],
        list[TensorValue],
        list[ArchitectureEdge],
        list[FanoutRelation],
    ]:
        input_ports: dict[str, list[Port]] = {node_id: [] for node_id in self.nodes}
        output_ports: dict[str, dict[str, Port]] = {node_id: {} for node_id in self.nodes}
        tensors: dict[str, dict[str, Any]] = {}
        edges: list[ArchitectureEdge] = []
        for index, connection in enumerate(self.connections):
            producer_key = connection.producer_id.removeprefix("node:")
            consumer_key = connection.consumer_id.removeprefix("node:")
            producer_port = output_ports[connection.producer_id].setdefault(
                connection.role,
                Port(
                    port_id=f"port:{producer_key}.{identifier(connection.role)}",
                    name=connection.role,
                    direction="output",
                    role=connection.role,
                ),
            )
            consumer_port = Port(
                port_id=f"port:{consumer_key}.in{len(input_ports[connection.consumer_id])}",
                name=connection.role,
                direction="input",
                role=connection.role,
            )
            input_ports[connection.consumer_id].append(consumer_port)
            tensor_id = f"tensor:{identifier(connection.role)}"
            current = tensors.get(tensor_id)
            if current is not None and current["producer_id"] != connection.producer_id:
                raise AnalysisError(
                    f"{self.profile.upper()}_TENSOR_IDENTITY",
                    f"tensor role {connection.role} has multiple producers",
                )
            if current is None:
                current = {
                    "producer_id": connection.producer_id,
                    "producer_port": producer_port.port_id,
                    "consumer_ids": [],
                    "shape": connection.shape,
                    "evidence_ids": [],
                }
                tensors[tensor_id] = current
            current["consumer_ids"].append(connection.consumer_id)
            current["evidence_ids"] = list(
                dict.fromkeys([*current["evidence_ids"], *connection.evidence_ids])
            )
            edges.append(
                ArchitectureEdge(
                    edge_id=f"edge:{producer_key}:{consumer_key}:{index}",
                    tensor_id=tensor_id,
                    producer_id=connection.producer_id,
                    producer_port=producer_port.port_id,
                    consumer_id=connection.consumer_id,
                    consumer_port=consumer_port.port_id,
                    role=connection.role,
                    edge_type=connection.edge_type,
                    symbolic_shape=connection.shape,
                    semantic_axes=shape_axes(connection.shape),
                    evidence_ids=connection.evidence_ids,
                    confidence=Confidence.EXACT,
                    execution_predicate=self.predicate,
                )
            )

        children: dict[str, list[str]] = {node_id: [] for node_id in self.nodes}
        for spec in self.nodes.values():
            if spec.parent_id:
                children[spec.parent_id].append(spec.node_id)
        nodes = [
            ArchitectureNode(
                node_id=spec.node_id,
                kind=spec.kind,
                semantic_name=spec.semantic_name,
                source_symbol=spec.attributes.get("source_symbol"),
                parent_id=spec.parent_id,
                children=children[spec.node_id],
                input_ports=input_ports[spec.node_id],
                output_ports=list(output_ports[spec.node_id].values()),
                parameter_identity=(
                    "independent-module-parameters"
                    if spec.kind is NodeKind.OPERATOR
                    else "not-applicable"
                ),
                execution_predicate=self.predicate,
                evidence_ids=spec.evidence_ids,
                confidence=Confidence.EXACT,
                attributes={
                    key: value for key, value in spec.attributes.items() if key != "source_symbol"
                },
            )
            for spec in self.nodes.values()
        ]
        tensor_models = [
            TensorValue(
                tensor_id=tensor_id,
                role=tensor_id.removeprefix("tensor:"),
                producer_id=data["producer_id"],
                producer_port=data["producer_port"],
                consumer_ids=data["consumer_ids"],
                symbolic_shape=data["shape"],
                semantic_axes=shape_axes(data["shape"]),
                dtype="unknown",
                provenance="source+config",
                confidence=Confidence.EXACT,
                evidence_ids=data["evidence_ids"],
            )
            for tensor_id, data in tensors.items()
        ]
        fanouts = [
            FanoutRelation(
                relation_id=f"fanout:{tensor.tensor_id.removeprefix('tensor:')}",
                tensor_id=tensor.tensor_id,
                producer_id=tensor.producer_id,
                consumer_ids=tensor.consumer_ids,
                evidence_ids=tensor.evidence_ids,
            )
            for tensor in tensor_models
            if len(tensor.consumer_ids) > 1
        ]
        return nodes, tensor_models, edges, fanouts
