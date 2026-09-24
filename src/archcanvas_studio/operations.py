from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from archcanvas_core.models import (
    Diagnostic,
    JobState,
    PatchBatch,
    SearchSubject,
    ValidationGateResult,
    ValidationRun,
    VisualPatch,
    VisualScene,
)
from archcanvas_core.validation import validate_architecture
from archcanvas_publication import validate_geometry

if TYPE_CHECKING:
    from .bundle import StudioBundle


def _now() -> str:
    return datetime.now(UTC).isoformat()


def studio_fingerprint(bundle: StudioBundle) -> str:
    payload = {
        "architecture": bundle.architecture.model_dump(mode="json"),
        "source_digest": bundle.document.source_digest,
        "visual_patches": [
            patch.model_dump(mode="json") for patch in bundle.document.visual_patches
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_search_index(bundle: StudioBundle) -> list[SearchSubject]:
    bindings: dict[str, list[dict[str, str]]] = {}
    for projection_id, scene in bundle.materialized_scenes().items():
        for node in scene.nodes:
            for canonical_id in node.canonical_node_ids:
                bindings.setdefault(canonical_id, []).append(
                    {
                        "projection_id": projection_id,
                        "scene_id": scene.scene_id,
                        "scene_node_id": node.scene_node_id,
                    }
                )

    subjects: list[SearchSubject] = []
    for node in bundle.architecture.nodes:
        aliases = [str(node.attributes.get(key, "")) for key in ("module_path", "op_type")]
        subjects.append(
            SearchSubject(
                id=node.node_id,
                kind="node",
                canonical_ids=[node.node_id],
                title=node.semantic_name,
                aliases=[alias for alias in aliases if alias],
                tokens=[node.kind.value, *[parameter.name for parameter in node.parameters]],
                view_bindings=bindings.get(node.node_id, []),
                facets={"kind": "node", "node-kind": node.kind.value},
            )
        )
        for port in [*node.input_ports, *node.output_ports]:
            subjects.append(
                SearchSubject(
                    id=port.port_id,
                    kind="port",
                    canonical_ids=[node.node_id, port.port_id],
                    title=f"{node.semantic_name}.{port.name}",
                    aliases=[port.role, node.semantic_name],
                    tokens=[port.direction, port.role],
                    view_bindings=bindings.get(node.node_id, []),
                    facets={
                        "kind": "port",
                        "direction": port.direction,
                        "role": port.role,
                    },
                )
            )
    for tensor in bundle.architecture.tensors:
        data = tensor.model_dump(mode="json")
        dtype = str(data.get("dtype") or data.get("element_type") or "unknown")
        subjects.append(
            SearchSubject(
                id=tensor.tensor_id,
                kind="tensor",
                canonical_ids=[tensor.tensor_id, tensor.producer_id, *tensor.consumer_ids],
                title=f"{tensor.role} {tensor.tensor_id}",
                aliases=[tensor.symbolic_shape, tensor.role],
                tokens=[dtype, tensor.symbolic_shape, *tensor.semantic_axes],
                view_bindings=bindings.get(tensor.producer_id, []),
                facets={
                    "kind": "tensor",
                    "dtype": dtype,
                    "role": tensor.role,
                    "shape": tensor.symbolic_shape,
                },
            )
        )
    for edge in bundle.architecture.edges:
        subjects.append(
            SearchSubject(
                id=edge.edge_id,
                kind="edge",
                canonical_ids=[
                    edge.edge_id,
                    edge.tensor_id,
                    edge.producer_id,
                    edge.consumer_id,
                ],
                title=f"{edge.producer_id} -> {edge.consumer_id}",
                aliases=[edge.role, edge.edge_type.value],
                tokens=[edge.producer_port, edge.consumer_port, edge.execution_predicate],
                view_bindings=[
                    *bindings.get(edge.producer_id, []),
                    *bindings.get(edge.consumer_id, []),
                ],
                facets={"kind": "edge", "edge-type": edge.edge_type.value, "role": edge.role},
            )
        )
    for evidence in bundle.evidence:
        source_spans: list[dict[str, Any]] = []
        if evidence.path and evidence.span:
            source_spans.append(
                {
                    "path": evidence.path,
                    "start_line": evidence.span.start_line,
                    "end_line": evidence.span.end_line,
                }
            )
        subjects.append(
            SearchSubject(
                id=evidence.evidence_id,
                kind="evidence",
                title=evidence.claim,
                aliases=[item for item in (evidence.path, evidence.symbol) if item],
                tokens=[evidence.kind.value, evidence.confidence.value],
                source_spans=source_spans,
                runtime_bindings=evidence.runtime_observation_ids,
                facets={
                    "kind": "evidence",
                    "confidence": evidence.confidence.value,
                    "evidence-kind": evidence.kind.value,
                },
            )
        )
    for diagnostic in bundle.diagnostics():
        digest = hashlib.sha256(
            f"{diagnostic.code}:{diagnostic.message}".encode()
        ).hexdigest()[:16]
        subjects.append(
            SearchSubject(
                id=f"diagnostic:{digest}",
                kind="diagnostic",
                canonical_ids=diagnostic.target_ids,
                title=diagnostic.message,
                aliases=[diagnostic.code],
                tokens=[diagnostic.severity],
                facets={"kind": "diagnostic", "status": diagnostic.severity},
            )
        )
    return subjects


def search_subjects(
    subjects: list[SearchSubject], query: str, limit: int = 50
) -> list[SearchSubject]:
    terms: list[str] = []
    facets: dict[str, str] = {}
    for token in query.lower().split():
        if ":" in token:
            key, value = token.split(":", 1)
            facets[key] = value.strip('"')
        else:
            terms.append(token.strip('"'))

    def score(subject: SearchSubject) -> int | None:
        if any(subject.facets.get(key, "").lower() != value for key, value in facets.items()):
            return None
        identifier = subject.id.lower()
        title = subject.title.lower()
        haystack = " ".join(
            [identifier, title, *subject.aliases, *subject.tokens, *subject.canonical_ids]
        ).lower()
        if any(term not in haystack for term in terms):
            return None
        return sum(
            100 if term == identifier else 70 if term == title else 40 if title.startswith(term) else 10
            for term in terms
        )

    ranked = [(score(subject), subject) for subject in subjects]
    return [
        subject
        for rank, subject in sorted(
            ((rank, subject) for rank, subject in ranked if rank is not None),
            key=lambda item: (-item[0], item[1].kind, item[1].title.lower()),
        )[:limit]
    ]


def run_validation(
    bundle: StudioBundle,
    profile: str,
    generation: int,
    *,
    runtime_execution_authorized: bool = False,
) -> ValidationRun:
    if profile not in {"fast-static", "publication", "full", "runtime-replay"}:
        raise ValueError("unknown validation profile")
    if profile == "runtime-replay" and not runtime_execution_authorized:
        raise ValueError("runtime replay requires explicit execution authorization")
    started_at = _now()
    gates, diagnostics = validate_architecture(
        bundle.architecture, bundle.evidence, bundle.snapshot
    )
    results = [
        ValidationGateResult(gate=gate.gate, status=gate.status, message=gate.message)
        for gate in gates
    ]
    if profile in {"publication", "full", "runtime-replay"}:
        for projection_id, scene in bundle.materialized_scenes().items():
            gate, found = validate_geometry(scene)
            results.append(
                ValidationGateResult(
                    gate=f"geometry-{projection_id.removeprefix('projection:')}",
                    status=gate.status,
                    message=gate.message,
                )
            )
            diagnostics.extend(found)
    if profile in {"full", "runtime-replay"}:
        if bundle.active_transaction is None:
            results.append(
                ValidationGateResult(
                    gate="transaction-consistency",
                    status="skipped",
                    message="No active source transaction requires consistency validation.",
                )
            )
        else:
            ready = bundle.active_transaction.state.value in {"review-ready", "committed"}
            results.append(
                ValidationGateResult(
                    gate="transaction-consistency",
                    status="passed" if ready else "failed",
                    message=f"Active transaction is {bundle.active_transaction.state.value}.",
                )
            )
    if profile == "runtime-replay":
        results.append(
            ValidationGateResult(
                gate="runtime-evidence",
                status="passed" if bundle.runtime_trace is not None else "unsupported",
                message=(
                    "Loaded runtime receipt contains replay evidence."
                    if bundle.runtime_trace is not None
                    else "No authorized runtime trace is loaded; no project code was executed."
                ),
            )
        )
    failed = any(result.status == "failed" for result in results)
    coverage = {
        "canonical_nodes": 1.0,
        "runtime_nodes": (
            len(bundle.runtime_node_evidence) / max(1, len(bundle.architecture.nodes))
            if bundle.runtime_trace is not None
            else 0.0
        ),
    }
    return ValidationRun(
        validation_id=f"validation:{generation}",
        profile=profile,
        input_fingerprint=studio_fingerprint(bundle),
        generation=generation,
        state=JobState.FAILED if failed else JobState.SUCCEEDED,
        gate_results=results,
        diagnostics=diagnostics,
        coverage=coverage,
        runtime_execution_authorized=runtime_execution_authorized,
        started_at=started_at,
        finished_at=_now(),
    )


def alignment_batch(
    scene: VisualScene,
    selected_ids: list[str],
    command: str,
    *,
    pinned_ids: set[str],
    gap: float | None = None,
    batch_id: str,
) -> PatchBatch:
    nodes = [node for node in scene.nodes if node.scene_node_id in selected_ids]
    if len(nodes) < 2:
        raise ValueError("alignment and distribution require at least two nodes")
    if any(node.scene_node_id in pinned_ids for node in nodes):
        raise ValueError("pinned nodes cannot be moved by alignment commands")
    primary = nodes[-1]
    positions = {node.scene_node_id: (node.bounds.x, node.bounds.y) for node in nodes}
    if command in {"left", "hcenter", "right", "top", "vcenter", "bottom"}:
        for node in nodes[:-1]:
            x, y = positions[node.scene_node_id]
            if command == "left":
                x = primary.bounds.x
            elif command == "hcenter":
                x = primary.bounds.x + (primary.bounds.width - node.bounds.width) / 2
            elif command == "right":
                x = primary.bounds.x + primary.bounds.width - node.bounds.width
            elif command == "top":
                y = primary.bounds.y
            elif command == "vcenter":
                y = primary.bounds.y + (primary.bounds.height - node.bounds.height) / 2
            else:
                y = primary.bounds.y + primary.bounds.height - node.bounds.height
            positions[node.scene_node_id] = (max(0, x), max(0, y))
    elif command in {"distribute-horizontal", "distribute-vertical"}:
        horizontal = command.endswith("horizontal")
        ordered = sorted(nodes, key=lambda node: node.bounds.x if horizontal else node.bounds.y)
        if gap is None:
            start = ordered[0].bounds.x if horizontal else ordered[0].bounds.y
            end = (
                ordered[-1].bounds.x + ordered[-1].bounds.width
                if horizontal
                else ordered[-1].bounds.y + ordered[-1].bounds.height
            )
            extent = sum(node.bounds.width if horizontal else node.bounds.height for node in ordered)
            gap = max(0.0, (end - start - extent) / (len(ordered) - 1))
        cursor = ordered[0].bounds.x if horizontal else ordered[0].bounds.y
        for node in ordered:
            x, y = positions[node.scene_node_id]
            positions[node.scene_node_id] = (cursor, y) if horizontal else (x, cursor)
            cursor += (node.bounds.width if horizontal else node.bounds.height) + gap
    else:
        raise ValueError("unknown alignment command")
    patches = [
        VisualPatch(
            patch_id=f"patch:{batch_id.removeprefix('batch:')}.{index}",
            operation="set-position",
            target_id=node.scene_node_id,
            value={"scene_id": scene.scene_id, "x": positions[node.scene_node_id][0], "y": positions[node.scene_node_id][1]},
        )
        for index, node in enumerate(nodes)
        if positions[node.scene_node_id] != (node.bounds.x, node.bounds.y)
    ]
    if not patches:
        raise ValueError("alignment command would not change the document")
    return PatchBatch(batch_id=batch_id, description=command, patches=patches)


def auto_layout_batch(
    scene: VisualScene, *, pinned_ids: set[str], batch_id: str
) -> PatchBatch:
    patches: list[VisualPatch] = []
    groups: dict[str, list[Any]] = {}
    for node in scene.nodes:
        if node.parent_scene_node_id and node.scene_node_id not in pinned_ids:
            groups.setdefault(node.parent_scene_node_id, []).append(node)
    by_id = {node.scene_node_id: node for node in scene.nodes}
    index = 0
    for parent_id, nodes in sorted(groups.items()):
        parent = by_id[parent_id]
        ordered = sorted(nodes, key=lambda node: (node.bounds.y, node.bounds.x, node.scene_node_id))
        columns = max(1, math.ceil(math.sqrt(len(ordered))))
        cell_width = max(node.bounds.width for node in ordered) + 28
        cell_height = max(node.bounds.height for node in ordered) + 28
        start_x = parent.bounds.x + 24
        start_y = parent.bounds.y + 44
        for offset, node in enumerate(ordered):
            x = start_x + (offset % columns) * cell_width
            y = start_y + (offset // columns) * cell_height
            if x + node.bounds.width > parent.bounds.x + parent.bounds.width - 16:
                x = node.bounds.x
            if y + node.bounds.height > parent.bounds.y + parent.bounds.height - 16:
                y = node.bounds.y
            if (x, y) == (node.bounds.x, node.bounds.y):
                continue
            patches.append(
                VisualPatch(
                    patch_id=f"patch:{batch_id.removeprefix('batch:')}.{index}",
                    operation="set-position",
                    target_id=node.scene_node_id,
                    value={"scene_id": scene.scene_id, "x": x, "y": y},
                )
            )
            index += 1
    if not patches:
        raise ValueError("the current scene is already at its deterministic layout")
    return PatchBatch(batch_id=batch_id, description="auto-layout", patches=patches)


def proof_severity(status: str) -> int:
    return {
        "invalid": 7,
        "stale": 6,
        "unproven": 5,
        "conditional": 4,
        "checking": 3,
        "proven": 2,
        "review-ready": 1,
    }.get(status, 0)


def diagnostics_for_validation(run: ValidationRun) -> list[Diagnostic]:
    return run.diagnostics
