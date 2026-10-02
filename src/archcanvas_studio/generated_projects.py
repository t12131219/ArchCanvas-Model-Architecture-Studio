from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from archcanvas_adapters import framework_form_capability
from archcanvas_core.builtin_registry import BuiltinModuleRegistry
from archcanvas_core.digest_protocol import domain_digest
from archcanvas_core.models import (
    Diagnostic,
    DraftGraphDocument,
    DraftNode,
    Identifier,
    RoundTripConformanceReport,
    Sha256,
    StrictModel,
)
from archcanvas_python import FrontendV2Bundle, analyze_project_v2

from .draft_analysis import DraftAnalysis, analyze_draft_graph

GENERATOR_VERSION = "pytorch-sequential-v1"
NORMALIZATION_RULE_VERSION = "draft-source-sequential-v1"
SUPPORTED_DEFINITIONS = {
    "archcanvas.input.tensor",
    "pytorch.nn.conv2d",
    "pytorch.nn.relu",
}

PROJECT_DIGEST_DOMAIN = "archcanvas:generated-project:v1"
INVENTORY_DIGEST_DOMAIN = "archcanvas:generated-project-inventory:v1"
NORMALIZATION_DIGEST_DOMAIN = "archcanvas:round-trip-normalization-rule:v1"
NORMALIZED_GRAPH_DIGEST_DOMAIN = "archcanvas:normalized-generated-graph:v1"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_value(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            _json_value(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


class GeneratedProjectFile(StrictModel):
    path: str = Field(min_length=1)
    sha256: Sha256
    size: int = Field(ge=0)


class GeneratedSourceMapEntry(StrictModel):
    origin_kind: Literal["node", "port", "edge", "parameter"]
    origin_id: Identifier
    path: str = Field(min_length=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class GeneratedProjectReceipt(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    receipt_id: Identifier
    project_id: Identifier
    graph_digest: Sha256
    registry_digest: Sha256
    generator_version: Literal[GENERATOR_VERSION] = GENERATOR_VERSION
    inventory_digest: Sha256
    files: list[GeneratedProjectFile]
    source_map: list[GeneratedSourceMapEntry]
    status: Literal["generated-source-draft", "review-ready"]
    created_at: str = Field(min_length=1)


class MaterializationReceipt(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    receipt_id: Identifier
    project_id: Identifier
    target_directory: str = Field(min_length=1)
    inventory_digest: Sha256
    files: list[GeneratedProjectFile]
    status: Literal["opened-and-reanalyzed"]
    source_project_id: Identifier
    source_digest: Sha256
    exact_ir_digest: Sha256
    materialized_at: str = Field(min_length=1)


GeneratedProjectState = Literal[
    "generated-source-draft",
    "statically-validated",
    "review-ready",
    "materialized",
    "opened-and-reanalyzed",
    "failed",
    "discarded",
    "stale",
]


class GeneratedProjectRecord(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    project_id: Identifier
    state: GeneratedProjectState
    graph_digest: Sha256
    registry_digest: Sha256
    generator_version: Literal[GENERATOR_VERSION] = GENERATOR_VERSION
    target_framework: Literal["pytorch"] = "pytorch"
    form_id: Literal["form:pytorch-module-forward"] = "form:pytorch-module-forward"
    class_name: Literal["GeneratedModel"] = "GeneratedModel"
    entrypoint: Literal["model:GeneratedModel"] = "model:GeneratedModel"
    input_spec: dict[str, Any]
    candidate_directory: str = Field(min_length=1)
    files: list[GeneratedProjectFile]
    source_map: list[GeneratedSourceMapEntry]
    receipt: GeneratedProjectReceipt
    conformance_report: RoundTripConformanceReport | None = None
    materialization_receipt: MaterializationReceipt | None = None
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    created_at: str = Field(min_length=1)
    updated_at: str = Field(min_length=1)


class PrepareGeneratedProjectRequest(StrictModel):
    graph_digest: Sha256
    registry_digest: Sha256
    generator_version: Literal[GENERATOR_VERSION]
    target_framework: Literal["pytorch"]
    form_id: Literal["form:pytorch-module-forward"] = "form:pytorch-module-forward"
    class_name: Literal["GeneratedModel"] = "GeneratedModel"
    entrypoint: Literal["model:GeneratedModel"] = "model:GeneratedModel"
    input_spec: dict[str, Any]

    @model_validator(mode="after")
    def input_spec_is_structured(self) -> PrepareGeneratedProjectRequest:
        shape = self.input_spec.get("shape")
        if not isinstance(shape, list) or not shape:
            raise ValueError("generated project input_spec.shape must be a non-empty list")
        if any(
            isinstance(item, bool)
            or not isinstance(item, (int, str))
            or isinstance(item, int) and item <= 0
            or isinstance(item, str) and not item.strip()
            for item in shape
        ):
            raise ValueError("generated project input shape contains an invalid dimension")
        return self


class MaterializeGeneratedProjectRequest(StrictModel):
    target_directory: str = Field(min_length=1)
    graph_digest: Sha256
    registry_digest: Sha256
    generator_version: Literal[GENERATOR_VERSION]
    inventory_digest: Sha256


@dataclass(frozen=True)
class MaterializedGeneratedProject:
    record: GeneratedProjectRecord
    artifact_path: Path


@dataclass(frozen=True)
class _GeneratedFiles:
    files: dict[str, bytes]
    source_map: list[GeneratedSourceMapEntry]


def _safe_literal(value: object) -> str:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, (list, tuple)):
        parts = [_safe_literal(item) for item in value]
        if isinstance(value, tuple):
            return f"({', '.join(parts)}{',' if len(parts) == 1 else ''})"
        return f"[{', '.join(parts)}]"
    raise ValueError(f"generator refuses unsafe literal type: {type(value).__name__}")


def _safe_field_name(node: DraftNode, used: set[str]) -> str:
    base = re.sub(r"[^a-zA-Z0-9_]", "_", node.semantic_name).strip("_").lower()
    if not base or base[0].isdigit() or base.startswith("_"):
        base = node.definition_ref.definition_id.rsplit(".", 1)[-1] if node.definition_ref else "layer"
    candidate = base
    suffix = 2
    while candidate in used or candidate in {"forward", "training"}:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _port_owners(draft: DraftGraphDocument) -> dict[str, tuple[DraftNode, str]]:
    return {
        port.port_id: (node, port.definition_port_id or port.name)
        for node in draft.nodes
        for port in node.ports
    }


def _topological_nodes(draft: DraftGraphDocument) -> list[DraftNode]:
    nodes = {node.node_id: node for node in draft.nodes}
    owners = _port_owners(draft)
    indegree = {node_id: 0 for node_id in nodes}
    outgoing = {node_id: [] for node_id in nodes}
    for edge in draft.edges:
        source = owners.get(edge.source_port_id)
        target = owners.get(edge.target_port_id)
        if source is None or target is None:
            raise ValueError("generate-project requires every edge endpoint to be a draft port")
        if source[0].node_id == target[0].node_id:
            raise ValueError("generate-project does not support self edges")
        outgoing[source[0].node_id].append(target[0].node_id)
        indegree[target[0].node_id] += 1
    ready = sorted(node_id for node_id, count in indegree.items() if count == 0)
    ordered: list[DraftNode] = []
    while ready:
        node_id = ready.pop(0)
        ordered.append(nodes[node_id])
        for target_id in sorted(outgoing[node_id]):
            indegree[target_id] -= 1
            if indegree[target_id] == 0:
                ready.append(target_id)
        ready.sort()
    if len(ordered) != len(nodes):
        raise ValueError("generate-project requires an acyclic graph")
    return ordered


def _validate_p0_graph(
    draft: DraftGraphDocument,
    registry: BuiltinModuleRegistry,
) -> tuple[list[DraftNode], DraftAnalysis]:
    if len(draft.nodes) != 3 or len(draft.edges) != 2:
        raise ValueError("the fixed generator currently supports exactly Input -> Conv2d -> ReLU")
    ordered = _topological_nodes(draft)
    definition_ids: list[str] = []
    for node in ordered:
        if node.definition_ref is None:
            raise ValueError(f"draft node {node.node_id} has no exact definition reference")
        definition = registry.resolve_ref(
            node.definition_ref.definition_id,
            node.definition_ref.version,
            node.definition_ref.digest,
        )
        if definition is None:
            raise ValueError(f"draft node {node.node_id} has an unknown or stale definition")
        if definition.definition_id not in SUPPORTED_DEFINITIONS:
            raise ValueError(
                f"definition {definition.definition_id} has no implemented fixed generator rule"
            )
        if definition.definition_id != "archcanvas.input.tensor" and not definition.codegen_rule_id:
            raise ValueError(f"definition {definition.definition_id} has no codegen rule")
        definition_ids.append(definition.definition_id)
    if definition_ids != [
        "archcanvas.input.tensor",
        "pytorch.nn.conv2d",
        "pytorch.nn.relu",
    ]:
        raise ValueError("the fixed generator requires Input -> Conv2d -> ReLU in dataflow order")

    owners = _port_owners(draft)
    normalized_edges = []
    for edge in draft.edges:
        source_node, source_port = owners[edge.source_port_id]
        target_node, target_port = owners[edge.target_port_id]
        normalized_edges.append(
            (
                source_node.definition_ref.definition_id if source_node.definition_ref else "",
                source_port,
                target_node.definition_ref.definition_id if target_node.definition_ref else "",
                target_port,
            )
        )
    if sorted(normalized_edges) != sorted(
        [
            ("archcanvas.input.tensor", "output", "pytorch.nn.conv2d", "input"),
            ("pytorch.nn.conv2d", "output", "pytorch.nn.relu", "input"),
        ]
    ):
        raise ValueError("the fixed generator requires exact named-port adjacency")

    analysis = analyze_draft_graph(draft, registry)
    blocking = [item for item in analysis.diagnostics if item.severity == "blocking"]
    if blocking:
        raise ValueError(
            "draft graph has blocking diagnostics: "
            + ", ".join(sorted(item.code for item in blocking))
        )
    output = analysis.node_shapes.get(ordered[-1].node_id, {}).get("output")
    if output is None or output.status != "known" or output.shape is None:
        raise ValueError("the generated project requires a known terminal output shape")
    return ordered, analysis


def _parameter_lines(node: DraftNode, parameter_names: list[str]) -> str:
    return ", ".join(
        f"{name}={_safe_literal(node.parameters[name])}"
        for name in parameter_names
        if name in node.parameters
    )


def _generate_files(
    draft: DraftGraphDocument,
    ordered: list[DraftNode],
    analysis: DraftAnalysis,
    *,
    project_id: str,
    graph_digest: str,
    registry_digest: str,
    input_spec: dict[str, Any],
) -> _GeneratedFiles:
    input_node, conv_node, relu_node = ordered
    used: set[str] = set()
    conv_field = _safe_field_name(conv_node, used)
    relu_field = _safe_field_name(relu_node, used)
    conv_parameters = [
        "in_channels",
        "out_channels",
        "kernel_size",
        "stride",
        "padding",
        "dilation",
        "groups",
        "bias",
    ]
    relu_parameters = ["inplace"]
    lines = [
        "from __future__ import annotations",
        "",
        "from torch import Tensor, nn",
        "",
        "",
        "class GeneratedModel(nn.Module):",
        "    def __init__(self) -> None:",
        "        super().__init__()",
        f"        self.{conv_field} = nn.Conv2d({_parameter_lines(conv_node, conv_parameters)})",
        f"        self.{relu_field} = nn.ReLU({_parameter_lines(relu_node, relu_parameters)})",
        "",
        "    def forward(self, input_tensor: Tensor) -> Tensor:",
        f"        value = self.{conv_field}(input_tensor)",
        f"        value = self.{relu_field}(value)",
        "        return value",
        "",
    ]
    model_source = "\n".join(lines).encode("utf-8")
    source_map = [
        GeneratedSourceMapEntry(
            origin_kind="node", origin_id=input_node.node_id, path="model.py", start_line=13, end_line=13
        ),
        GeneratedSourceMapEntry(
            origin_kind="node", origin_id=conv_node.node_id, path="model.py", start_line=9, end_line=9
        ),
        GeneratedSourceMapEntry(
            origin_kind="node", origin_id=conv_node.node_id, path="model.py", start_line=13, end_line=13
        ),
        GeneratedSourceMapEntry(
            origin_kind="node", origin_id=relu_node.node_id, path="model.py", start_line=10, end_line=10
        ),
        GeneratedSourceMapEntry(
            origin_kind="node", origin_id=relu_node.node_id, path="model.py", start_line=14, end_line=14
        ),
    ]
    owners = _port_owners(draft)
    for edge in sorted(draft.edges, key=lambda item: item.edge_id):
        target_node = owners[edge.target_port_id][0]
        line = 13 if target_node.node_id == conv_node.node_id else 14
        source_map.append(
            GeneratedSourceMapEntry(
                origin_kind="edge",
                origin_id=edge.edge_id,
                path="model.py",
                start_line=line,
                end_line=line,
            )
        )
    source_map.extend(
        GeneratedSourceMapEntry(
            origin_kind="parameter",
            origin_id=f"{node.node_id}.{parameter_id}",
            path="model.py",
            start_line=line,
            end_line=line,
        )
        for node, parameter_ids, line in (
            (conv_node, sorted(conv_node.parameters), 9),
            (relu_node, sorted(relu_node.parameters), 10),
        )
        for parameter_id in parameter_ids
    )
    terminal = analysis.node_shapes[relu_node.node_id]["output"]
    assert terminal.shape is not None
    manifest = {
        "schema_version": "1.0",
        "project_id": project_id,
        "framework": "pytorch",
        "entrypoint": "model:GeneratedModel",
        "task": "inference",
        "generator_version": GENERATOR_VERSION,
        "graph_digest": graph_digest,
        "registry_digest": registry_digest,
        "input_spec": input_spec,
        "output_spec": {
            "shape": list(terminal.shape.dimensions),
            "layout": terminal.shape.layout,
            "dtype": terminal.shape.dtype or input_spec.get("dtype", "float32"),
        },
        "runtime": {"authorized": False, "seed": 0},
    }
    pyproject = (
        "[project]\n"
        f"name = \"archcanvas-{project_id.removeprefix('generated-project:')}\"\n"
        "version = \"0.1.0\"\n"
        "requires-python = \">=3.10\"\n"
        "dependencies = [\"torch>=2.0\"]\n"
    ).encode()
    generation = {
        "schema_version": "1.0",
        "project_id": project_id,
        "graph_digest": graph_digest,
        "registry_digest": registry_digest,
        "generator_version": GENERATOR_VERSION,
        "source_map": [item.model_dump(mode="json") for item in source_map],
        "generated_files": {
            "model.py": _sha256(model_source),
            "archcanvas-project.json": _sha256(_json_bytes(manifest)),
            "pyproject.toml": _sha256(pyproject),
        },
    }
    return _GeneratedFiles(
        files={
            "archcanvas-generation.json": _json_bytes(generation),
            "archcanvas-project.json": _json_bytes(manifest),
            "model.py": model_source,
            "pyproject.toml": pyproject,
        },
        source_map=source_map,
    )


def _inventory(root: Path) -> list[GeneratedProjectFile]:
    symlinks = [path for path in root.rglob("*") if path.is_symlink()]
    if symlinks:
        raise ValueError("generated project inventory cannot contain symlinks")
    return [
        GeneratedProjectFile(
            path=path.relative_to(root).as_posix(),
            sha256=_sha256(path.read_bytes()),
            size=path.stat().st_size,
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def _inventory_digest(files: list[GeneratedProjectFile]) -> str:
    return domain_digest(
        INVENTORY_DIGEST_DOMAIN,
        [item.model_dump(mode="json") for item in files],
    )


def _verify_inventory(root: Path, expected: list[GeneratedProjectFile]) -> list[GeneratedProjectFile]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("generated project candidate directory is missing or unsafe")
    actual = _inventory(root)
    if actual != expected:
        raise ValueError("generated project candidate inventory is stale")
    return actual


def _draft_normal_form(
    draft: DraftGraphDocument,
    ordered: list[DraftNode],
    analysis: DraftAnalysis,
) -> dict[str, Any]:
    _input, conv, relu = ordered
    output = analysis.node_shapes[relu.node_id]["output"]
    assert output.shape is not None
    return {
        "boundary_input": True,
        "definitions": ["pytorch.nn.conv2d", "pytorch.nn.relu"],
        "edges": [["input", "conv2d.input"], ["conv2d.output", "relu.input"], ["relu.output", "output"]],
        "parameters": [
            {
                "definition_id": "pytorch.nn.conv2d",
                "values": {key: conv.parameters[key] for key in sorted(conv.parameters)},
            },
            {
                "definition_id": "pytorch.nn.relu",
                "values": {key: relu.parameters[key] for key in sorted(relu.parameters)},
            },
        ],
        "output_shape": list(output.shape.dimensions),
        "control_regions": [],
        "shared_parameter_groups": [],
    }


def _observed_normal_form(frontend: FrontendV2Bundle, manifest: dict[str, Any]) -> dict[str, Any]:
    calls = [item for item in frontend.exact_ir.calls if item.definition_ref is not None]
    values = {item.value_id: item for item in frontend.exact_ir.values}
    instances = {item.instance_id: item for item in frontend.exact_ir.instances}
    call_index = {item.call_id: index for index, item in enumerate(calls)}
    definitions = [item.definition_ref.definition_id for item in calls if item.definition_ref]
    parameters: list[dict[str, Any]] = []
    for call in calls:
        instance = instances.get(call.instance_id) if call.instance_id else None
        parameters.append(
            {
                "definition_id": call.definition_ref.definition_id if call.definition_ref else "",
                "values": {
                    item.parameter_name: item.value
                    for item in sorted(
                        instance.constructor_arguments if instance else [],
                        key=lambda argument: argument.parameter_name,
                    )
                },
            }
        )
    edges: list[list[str]] = []
    for index, call in enumerate(calls):
        label = "conv2d" if definitions[index] == "pytorch.nn.conv2d" else "relu"
        for binding in call.input_bindings:
            value = values[binding.value_id]
            if value.producer_call_id is None:
                edges.append(["input", f"{label}.{binding.port_id}"])
            else:
                producer_index = call_index.get(value.producer_call_id)
                if producer_index is not None:
                    producer_label = (
                        "conv2d"
                        if definitions[producer_index] == "pytorch.nn.conv2d"
                        else "relu"
                    )
                    edges.append(
                        [f"{producer_label}.{value.producer_port_id}", f"{label}.{binding.port_id}"]
                    )
        for binding in call.output_bindings:
            value = values[binding.value_id]
            if not value.consumer_call_ids:
                edges.append([f"{label}.{binding.port_id}", "output"])
    return {
        "boundary_input": any(item.producer_call_id is None for item in values.values()),
        "definitions": definitions,
        "edges": edges,
        "parameters": parameters,
        "output_shape": manifest["output_spec"]["shape"],
        "control_regions": [
            item.kind for item in frontend.exact_ir.control_regions if item.kind != "function"
        ],
        "shared_parameter_groups": [
            item.binding_kind
            for item in frontend.exact_ir.parameter_groups
            if item.binding_kind == "tied"
        ],
    }


def _write_analysis_artifacts(frontend: FrontendV2Bundle, output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    compatibility = frontend.compatibility
    artifacts: dict[str, object] = {
        "architecture.json": compatibility.architecture,
        "source-snapshot.json": compatibility.snapshot,
        "evidence-ledger.json": compatibility.evidence,
        "project-manifest-v2.json": frontend.manifest,
        "source-corpus-v2.json": frontend.corpus,
        "analysis-input-v2.json": frontend.analysis_input,
        "semantic-graph-v2.json": frontend.semantic_graph,
        "architecture-v2.json": frontend.exact_ir,
    }
    for name, value in artifacts.items():
        _write_json(output / name, value)
    return output / "architecture.json"


class GeneratedProjectManager:
    def __init__(self, workspace: Path, registry: BuiltinModuleRegistry) -> None:
        self.workspace = workspace.resolve()
        self.registry = registry
        self.root = self.workspace / "generated-projects"
        self.records_dir = self.root / "records"
        self.candidates_dir = self.root / "candidates"
        self.analysis_dir = self.root / "analyses"
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self.candidates_dir.mkdir(parents=True, exist_ok=True)
        self._records: dict[str, GeneratedProjectRecord] = {}
        for path in sorted(self.records_dir.glob("*.json")):
            record = GeneratedProjectRecord.model_validate_json(path.read_text(encoding="utf-8"))
            self._records[record.project_id] = record

    def state(self) -> dict[str, object]:
        records = sorted(self._records.values(), key=lambda item: (item.updated_at, item.project_id))
        return {
            "generator_version": GENERATOR_VERSION,
            "active": records[-1].model_dump(mode="json") if records else None,
            "records": [item.model_dump(mode="json") for item in records[-10:]],
        }

    def conformance_reports(self) -> list[RoundTripConformanceReport]:
        return [
            record.conformance_report
            for record in sorted(
                self._records.values(), key=lambda item: (item.updated_at, item.project_id)
            )
            if record.conformance_report is not None
        ]

    def _path(self, project_id: str) -> Path:
        return self.records_dir / f"{project_id.removeprefix('generated-project:')}.json"

    def _save(self, record: GeneratedProjectRecord) -> GeneratedProjectRecord:
        self._records[record.project_id] = record
        _write_json(self._path(record.project_id), record)
        return record

    def _candidate_path(self, record: GeneratedProjectRecord) -> Path:
        candidate = Path(record.candidate_directory)
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.candidates_dir.resolve()):
            raise ValueError("generated project candidate escapes its managed workspace")
        return candidate

    def get(self, project_id: str) -> GeneratedProjectRecord:
        record = self._records.get(project_id)
        if record is None:
            raise ValueError("generated project does not exist")
        return record

    def prepare(
        self,
        draft: DraftGraphDocument,
        request: PrepareGeneratedProjectRequest,
    ) -> GeneratedProjectRecord:
        from .bundle import draft_document_digest

        code_generation = framework_form_capability(
            request.target_framework,
            request.form_id,
            "code_generation",
        )
        if code_generation not in {"verified", "partial"}:
            raise ValueError(
                "code generation is unavailable for the selected framework form"
            )

        current_digest = draft_document_digest(draft)
        if request.graph_digest != current_digest:
            raise ValueError("generated project graph digest is stale")
        if request.registry_digest != self.registry.bundle.bundle_digest:
            raise ValueError("generated project registry digest is stale")
        ordered, analysis = _validate_p0_graph(draft, self.registry)
        if request.input_spec["shape"] != list(ordered[0].parameters.get("shape", [])):
            raise ValueError("input_spec shape must exactly match the draft Input node")
        project_digest = domain_digest(
            PROJECT_DIGEST_DOMAIN,
            {
                "graph_digest": current_digest,
                "registry_digest": request.registry_digest,
                "generator_version": request.generator_version,
                "target_framework": request.target_framework,
                "class_name": request.class_name,
                "entrypoint": request.entrypoint,
                "input_spec": request.input_spec,
            },
        )
        project_id = f"generated-project:{project_digest[:24]}"
        existing = self._records.get(project_id)
        if existing is not None and existing.state not in {"discarded", "failed", "stale"}:
            _verify_inventory(self._candidate_path(existing), existing.files)
            return existing

        candidate = self.candidates_dir / project_digest
        if candidate.exists():
            shutil.rmtree(candidate)
        candidate.mkdir(parents=True)
        generated = _generate_files(
            draft,
            ordered,
            analysis,
            project_id=project_id,
            graph_digest=current_digest,
            registry_digest=request.registry_digest,
            input_spec=request.input_spec,
        )
        for relative, content in generated.files.items():
            path = candidate / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        files = _inventory(candidate)
        inventory_digest = _inventory_digest(files)
        now = _utc_now()
        receipt = GeneratedProjectReceipt(
            receipt_id=f"receipt:generated.{project_digest[:24]}",
            project_id=project_id,
            graph_digest=current_digest,
            registry_digest=request.registry_digest,
            inventory_digest=inventory_digest,
            files=files,
            source_map=generated.source_map,
            status="generated-source-draft",
            created_at=now,
        )
        return self._save(
            GeneratedProjectRecord(
                project_id=project_id,
                state="generated-source-draft",
                graph_digest=current_digest,
                registry_digest=request.registry_digest,
                target_framework=request.target_framework,
                form_id=request.form_id,
                class_name=request.class_name,
                entrypoint=request.entrypoint,
                input_spec=request.input_spec,
                candidate_directory=str(candidate),
                files=files,
                source_map=generated.source_map,
                receipt=receipt,
                created_at=now,
                updated_at=now,
            )
        )

    def validate(
        self,
        project_id: str,
        draft: DraftGraphDocument,
        *,
        graph_digest: str,
        registry_digest: str,
        generator_version: str,
    ) -> GeneratedProjectRecord:
        from .bundle import draft_document_digest

        record = self.get(project_id)
        if record.state in {"discarded", "failed", "stale"}:
            raise ValueError(f"generated project is {record.state}")
        if graph_digest != record.graph_digest or graph_digest != draft_document_digest(draft):
            raise ValueError("generated project graph digest is stale")
        if registry_digest != record.registry_digest or registry_digest != self.registry.bundle.bundle_digest:
            raise ValueError("generated project registry digest is stale")
        if generator_version != record.generator_version:
            raise ValueError("generated project generator version is stale")
        candidate = self._candidate_path(record)
        _verify_inventory(candidate, record.files)
        for file in record.files:
            if file.path.endswith(".py"):
                compile((candidate / file.path).read_text(encoding="utf-8"), file.path, "exec")
        ordered, analysis = _validate_p0_graph(draft, self.registry)
        frontend = analyze_project_v2(
            candidate,
            record.entrypoint,
            "inference",
            "eval",
            self.analysis_dir / record.project_id.removeprefix("generated-project:") / "candidate",
            registry=self.registry,
        )
        blocking = [item for item in frontend.exact_ir.diagnostics if item.severity == "blocking"]
        manifest = json.loads((candidate / "archcanvas-project.json").read_text(encoding="utf-8"))
        expected = _draft_normal_form(draft, ordered, analysis)
        observed = _observed_normal_form(frontend, manifest)
        expected_digest = domain_digest(NORMALIZED_GRAPH_DIGEST_DOMAIN, expected)
        observed_digest = domain_digest(NORMALIZED_GRAPH_DIGEST_DOMAIN, observed)
        exact = expected_digest == observed_digest and not blocking
        diagnostics = list(blocking)
        if not exact:
            diagnostics.append(
                Diagnostic(
                    code="GENERATED_PROJECT_CONFORMANCE_FAILED",
                    severity="blocking",
                    message="The reanalyzed generated project does not match the normalized Graph Draft.",
                    target_ids=[draft.draft_id],
                )
            )
        normalization_digest = domain_digest(
            NORMALIZATION_DIGEST_DOMAIN,
            {
                "version": NORMALIZATION_RULE_VERSION,
                "ignored": ["local-variable-names", "generated-identifiers", "source-formatting"],
                "preserved": [
                    "definition-ids",
                    "named-port-adjacency",
                    "parameters",
                    "boundary-input-output",
                    "output-shape",
                    "control-regions",
                    "parameter-sharing",
                ],
            },
        )
        report = RoundTripConformanceReport(
            report_id=f"round-trip:{record.project_id.removeprefix('generated-project:')}",
            path="draft-source",
            result_source_digest=frontend.corpus.source_corpus_digest,
            result_exact_ir_digest=frontend.exact_ir.exact_ir_digest,
            draft_digest=record.graph_digest,
            normalization_rule_digest=normalization_digest,
            expected_delta_digest=expected_digest,
            observed_delta_digest=observed_digest,
            semantic_isomorphism="exact" if exact else "failed",
            source_writes=[],
            diagnostics=diagnostics,
        )
        now = _utc_now()
        receipt = record.receipt.model_copy(
            update={"status": "review-ready" if exact else "generated-source-draft"}
        )
        updated = record.model_copy(
            update={
                "state": "review-ready" if exact else "failed",
                "receipt": receipt,
                "conformance_report": report,
                "diagnostics": diagnostics,
                "updated_at": now,
            }
        )
        self._save(updated)
        if not exact:
            raise ValueError("generated project failed round-trip conformance")
        return updated

    def materialize(
        self,
        project_id: str,
        draft: DraftGraphDocument,
        request: MaterializeGeneratedProjectRequest,
    ) -> MaterializedGeneratedProject:
        from .bundle import draft_document_digest

        record = self.get(project_id)
        if (
            framework_form_capability(
                record.target_framework,
                record.form_id,
                "artifact_commit",
            )
            == "unavailable"
        ):
            raise ValueError(
                "artifact commit is unavailable for the selected framework form"
            )
        if record.state != "review-ready" or record.conformance_report is None:
            raise ValueError("generated project is not review-ready")
        if record.conformance_report.semantic_isomorphism != "exact":
            raise ValueError("generated project conformance is not exact")
        if request.graph_digest != record.graph_digest or request.graph_digest != draft_document_digest(draft):
            raise ValueError("generated project graph digest is stale")
        if request.registry_digest != record.registry_digest or request.registry_digest != self.registry.bundle.bundle_digest:
            raise ValueError("generated project registry digest is stale")
        if request.generator_version != record.generator_version:
            raise ValueError("generated project generator version is stale")
        if request.inventory_digest != record.receipt.inventory_digest:
            raise ValueError("generated project inventory receipt is stale")
        candidate = self._candidate_path(record)
        _verify_inventory(candidate, record.files)

        target = Path(request.target_directory).expanduser()
        if not target.is_absolute():
            raise ValueError("generated project target directory must be absolute")
        target = target.absolute()
        if target.exists() or target.is_symlink():
            raise ValueError("generated project target directory must not already exist")
        if target.parent == target or target.name in {"", ".", ".."}:
            raise ValueError("generated project target directory is too broad")
        if not target.parent.is_dir() or target.parent.is_symlink():
            raise ValueError("generated project target parent must be an existing real directory")
        current = target.parent
        while current != current.parent:
            if current.is_symlink():
                raise ValueError("generated project target cannot traverse a symlink")
            current = current.parent
        if target in {Path.home(), self.workspace, self.workspace.parent}:
            raise ValueError("generated project target directory is protected")

        temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.archcanvas-", dir=target.parent))
        try:
            for file in record.files:
                source = candidate / file.path
                destination = temporary / file.path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination, follow_symlinks=False)
            copied = _inventory(temporary)
            if copied != record.files:
                raise ValueError("generated project materialization inventory changed during copy")
            os.replace(temporary, target)
        except Exception:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise

        real_inventory = _verify_inventory(target, record.files)
        materialized_frontend = analyze_project_v2(
            target,
            record.entrypoint,
            "inference",
            "eval",
            self.analysis_dir / record.project_id.removeprefix("generated-project:") / "materialized",
            registry=self.registry,
        )
        manifest = json.loads((target / "archcanvas-project.json").read_text(encoding="utf-8"))
        ordered, analysis = _validate_p0_graph(draft, self.registry)
        expected = _draft_normal_form(draft, ordered, analysis)
        observed = _observed_normal_form(materialized_frontend, manifest)
        if domain_digest(NORMALIZED_GRAPH_DIGEST_DOMAIN, expected) != domain_digest(
            NORMALIZED_GRAPH_DIGEST_DOMAIN, observed
        ):
            failed = record.model_copy(update={"state": "failed", "updated_at": _utc_now()})
            self._save(failed)
            raise ValueError("materialized project failed immediate round-trip reanalysis")

        artifacts = self.analysis_dir / record.project_id.removeprefix("generated-project:") / "opened"
        artifact_path = _write_analysis_artifacts(materialized_frontend, artifacts)
        now = _utc_now()
        receipt = MaterializationReceipt(
            receipt_id=f"receipt:materialized.{record.project_id.removeprefix('generated-project:')}",
            project_id=record.project_id,
            target_directory=str(target),
            inventory_digest=_inventory_digest(real_inventory),
            files=real_inventory,
            status="opened-and-reanalyzed",
            source_project_id=f"project:{materialized_frontend.corpus.source_corpus_digest[:24]}",
            source_digest=materialized_frontend.corpus.source_corpus_digest,
            exact_ir_digest=materialized_frontend.exact_ir.exact_ir_digest,
            materialized_at=now,
        )
        updated_report = record.conformance_report.model_copy(
            update={
                "result_source_digest": materialized_frontend.corpus.source_corpus_digest,
                "result_exact_ir_digest": materialized_frontend.exact_ir.exact_ir_digest,
                "source_writes": [item.path for item in real_inventory],
            }
        )
        updated = record.model_copy(
            update={
                "state": "opened-and-reanalyzed",
                "conformance_report": updated_report,
                "materialization_receipt": receipt,
                "updated_at": now,
            }
        )
        self._save(updated)
        return MaterializedGeneratedProject(record=updated, artifact_path=artifact_path)

    def discard(self, project_id: str) -> GeneratedProjectRecord:
        record = self.get(project_id)
        candidate = self._candidate_path(record)
        if candidate.is_dir() and candidate.is_relative_to(self.candidates_dir):
            shutil.rmtree(candidate)
        updated = record.model_copy(update={"state": "discarded", "updated_at": _utc_now()})
        return self._save(updated)
