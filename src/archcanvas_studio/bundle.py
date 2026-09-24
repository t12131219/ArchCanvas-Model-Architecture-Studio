from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter

from archcanvas_core.models import (
    AgentProposal,
    ArchitectureIR,
    CanvasDocument,
    Diagnostic,
    EvidenceRecord,
    ProposedConnection,
    PublicationView,
    RuntimeTrace,
    SemanticAnnotationOverlay,
    SemanticParameterPatch,
    SemanticStructuralPatch,
    SourceSnapshot,
    SourceTransaction,
    VisualScene,
    VisualSpec,
)
from archcanvas_patterns import exact_ir_digest
from archcanvas_publication import (
    build_scene,
    build_visual_spec,
    compile_views,
    render_svg,
    validate_geometry,
)
from archcanvas_transactions import (
    commit_transaction,
    discard_transaction,
    plan_connection,
    prepare_transaction,
    verify_transaction,
)

from .document import (
    create_canvas_document,
    derive_view_state,
    load_canvas_document,
    materialize_scene,
    persist_canvas_document,
    source_binding_digest,
)

STATIC_ROOT = Path(__file__).resolve().parent / "static"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


@dataclass
class StudioBundle:
    artifact_path: Path
    workspace: Path
    static_dir: Path
    document_path: Path
    architecture: ArchitectureIR
    snapshot: SourceSnapshot
    evidence: list[EvidenceRecord]
    runtime_trace: RuntimeTrace | None
    runtime_node_evidence: dict[str, list[str]]
    semantic_overlay: SemanticAnnotationOverlay | None
    views: dict[str, PublicationView]
    specs: dict[str, VisualSpec]
    base_scenes: dict[str, VisualScene]
    document: CanvasDocument
    active_transaction: SourceTransaction | None = None
    active_proposal: AgentProposal | None = None

    def materialized_scenes(self) -> dict[str, VisualScene]:
        return {
            level: materialize_scene(scene, self.document)
            for level, scene in self.base_scenes.items()
        }

    def diagnostics(self) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        for scene in self.materialized_scenes().values():
            _, scene_diagnostics = validate_geometry(scene)
            diagnostics.extend(scene_diagnostics)
        return diagnostics

    def state(self) -> dict[str, object]:
        scenes = self.materialized_scenes()
        return {
            "schema_version": "1.0",
            "architecture": self.architecture.model_dump(mode="json"),
            "snapshot": self.snapshot.model_dump(mode="json"),
            "evidence": [record.model_dump(mode="json") for record in self.evidence],
            "runtime": (
                {
                    "trace": self.runtime_trace.model_dump(mode="json"),
                    "node_evidence": self.runtime_node_evidence,
                }
                if self.runtime_trace is not None
                else None
            ),
            "semantic_overlay": (
                self.semantic_overlay.model_dump(mode="json")
                if self.semantic_overlay is not None
                else None
            ),
            "views": {
                level: view.model_dump(mode="json") for level, view in self.views.items()
            },
            "specs": {
                level: spec.model_dump(mode="json") for level, spec in self.specs.items()
            },
            "scenes": {
                level: scene.model_dump(mode="json") for level, scene in scenes.items()
            },
            "document": self.document.model_dump(mode="json"),
            "view_state": derive_view_state(self.document),
            "diagnostics": [item.model_dump(mode="json") for item in self.diagnostics()],
            "transaction": (
                self.active_transaction.model_dump(mode="json")
                if self.active_transaction is not None
                else None
            ),
            "proposal": (
                self.active_proposal.model_dump(mode="json")
                if self.active_proposal is not None
                else None
            ),
            "capabilities": {
                "visual_editing": True,
                "source_editing": True,
                "semantic_transforms": [
                    "set_parameter",
                    "replace_activation",
                    "insert_layer_norm",
                ],
                "proposed_connection": True,
                "runtime_evidence": self.runtime_trace is not None,
            },
        }

    def prepare_parameter(self, payload: dict[str, object]) -> None:
        request = SemanticParameterPatch(
            patch_id=str(payload["patch_id"]),
            artifact_path=str(self.artifact_path),
            target_node_id=str(payload["target_node_id"]),
            parameter_name=str(payload["parameter_name"]),
            new_value=payload.get("new_value"),
            targeted_tests=payload.get("targeted_tests", []),
            runtime_input_spec=payload.get("runtime_input_spec"),
        )
        transaction, _ = prepare_transaction(request, self.workspace)
        transaction, _ = verify_transaction(
            self.workspace / "transactions" / transaction.transaction_id
        )
        self.active_transaction = transaction

    def prepare_structural(self, payload: dict[str, object]) -> None:
        request = SemanticStructuralPatch(
            patch_id=str(payload["patch_id"]),
            operation=str(payload["operation"]),
            artifact_path=str(self.artifact_path),
            target_node_id=str(payload["target_node_id"]),
            parameters=payload.get("parameters", {}),
            targeted_tests=payload.get("targeted_tests", []),
            runtime_input_spec=payload.get("runtime_input_spec"),
        )
        transaction, _ = prepare_transaction(request, self.workspace)
        transaction, _ = verify_transaction(
            self.workspace / "transactions" / transaction.transaction_id
        )
        self.active_transaction = transaction
        self.active_proposal = None

    def propose_connection(self, payload: dict[str, object]) -> None:
        request = ProposedConnection(
            proposal_id=str(payload["proposal_id"]),
            artifact_path=str(self.artifact_path),
            source_node_id=str(payload["source_node_id"]),
            source_port_id=str(payload["source_port_id"]),
            target_node_id=str(payload["target_node_id"]),
            target_port_id=str(payload["target_port_id"]),
            role=str(payload.get("role", "main")),
        )
        self.active_proposal = plan_connection(request, self.architecture)

    def commit_parameter(self) -> None:
        if self.active_transaction is None:
            raise ValueError("there is no active source transaction")
        transaction, _ = commit_transaction(
            self.workspace / "transactions" / self.active_transaction.transaction_id
        )
        self.active_transaction = transaction

    def discard_parameter(self) -> None:
        if self.active_transaction is None:
            raise ValueError("there is no active source transaction")
        transaction, _ = discard_transaction(
            self.workspace / "transactions" / self.active_transaction.transaction_id
        )
        self.active_transaction = transaction

    def save_document(self, document: CanvasDocument) -> None:
        if document.source_digest != self.document.source_digest:
            raise ValueError("CanvasDocument source digest cannot change")
        persist_canvas_document(self.document_path, document)
        self.document = document

    def export_svg(self, level: str) -> str:
        if level not in self.base_scenes:
            raise ValueError(f"unknown Studio level: {level}")
        return render_svg(materialize_scene(self.base_scenes[level], self.document))


def _render_index(template: str, state: dict[str, object]) -> str:
    payload = json.dumps(state, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    script = f'<script id="archcanvas-studio-data" type="application/json">{payload}</script>'
    if "<!--ARCHCANVAS_DATA-->" not in template:
        raise ValueError("Studio index is missing its data injection marker")
    return template.replace("<!--ARCHCANVAS_DATA-->", script)


def _write_static_bundle(bundle: StudioBundle) -> None:
    if not (STATIC_ROOT / "index.html").is_file():
        raise ValueError("Studio frontend has not been built")
    bundle.static_dir.mkdir(parents=True, exist_ok=True)
    for source in STATIC_ROOT.iterdir():
        target = bundle.static_dir / source.name
        if source.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
        elif source.name != "index.html":
            shutil.copy2(source, target)
    template = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    (bundle.static_dir / "index.html").write_text(
        _render_index(template, bundle.state()), encoding="utf-8"
    )
    _write_json(bundle.static_dir / "studio-state.json", bundle.state())


def prepare_studio_bundle(artifact: Path, workspace: Path) -> StudioBundle:
    artifact = artifact.resolve()
    workspace = workspace.resolve()
    architecture = ArchitectureIR.model_validate_json(artifact.read_text(encoding="utf-8"))
    snapshot_path = artifact.parent / "source-snapshot.json"
    if not snapshot_path.is_file():
        raise ValueError("Studio requires source-snapshot.json beside architecture.json")
    snapshot = SourceSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
    evidence_path = artifact.parent / "evidence-ledger.json"
    evidence = (
        TypeAdapter(list[EvidenceRecord]).validate_json(evidence_path.read_text(encoding="utf-8"))
        if evidence_path.is_file()
        else []
    )
    semantic_overlay_path = artifact.parent / "semantic-annotation-overlay.json"
    semantic_overlay = (
        SemanticAnnotationOverlay.model_validate_json(
            semantic_overlay_path.read_text(encoding="utf-8")
        )
        if semantic_overlay_path.is_file()
        else None
    )
    if semantic_overlay is not None and (
        semantic_overlay.architecture_id != architecture.architecture_id
        or semantic_overlay.exact_ir_digest != exact_ir_digest(architecture)
    ):
        raise ValueError("semantic annotation overlay binding is stale")
    runtime_trace_path = artifact.parent / "runtime-trace.json"
    runtime_evidence_path = artifact.parent / "runtime-evidence-ledger.json"
    runtime_overlay_path = artifact.parent / "runtime-evidence-overlay.json"
    runtime_receipt_path = artifact.parent / "runtime-receipt.json"
    runtime_trace: RuntimeTrace | None = None
    runtime_node_evidence: dict[str, list[str]] = {}
    runtime_paths = (runtime_trace_path, runtime_evidence_path, runtime_overlay_path)
    runtime_receipt = (
        json.loads(runtime_receipt_path.read_text(encoding="utf-8"))
        if runtime_receipt_path.is_file()
        else None
    )
    if any(path.is_file() for path in runtime_paths) and runtime_receipt is None:
        raise ValueError("Studio found runtime evidence without a runtime receipt")
    if runtime_receipt is not None and runtime_receipt.get("status") == "ok":
        if not all(
            path.is_file() for path in runtime_paths
        ):
            raise ValueError("Studio found an incomplete runtime evidence bundle")
        runtime_trace = RuntimeTrace.model_validate_json(
            runtime_trace_path.read_text(encoding="utf-8")
        )
        if (
            runtime_trace.architecture_id != architecture.architecture_id
            or runtime_trace.source_snapshot_id != snapshot.snapshot_id
            or runtime_trace.source_revision != snapshot.revision
        ):
            raise ValueError("runtime evidence belongs to a stale architecture or source snapshot")
        runtime_evidence = TypeAdapter(list[EvidenceRecord]).validate_json(
            runtime_evidence_path.read_text(encoding="utf-8")
        )
        overlay = json.loads(runtime_overlay_path.read_text(encoding="utf-8"))
        if (
            overlay.get("architecture_id") != architecture.architecture_id
            or overlay.get("trace_id") != runtime_trace.trace_id
            or runtime_receipt.get("details", {}).get("trace_id") != runtime_trace.trace_id
        ):
            raise ValueError("runtime evidence overlay binding is stale")
        runtime_node_evidence = TypeAdapter(dict[str, list[str]]).validate_python(
            overlay.get("node_evidence", {})
        )
        runtime_ids = {item.evidence_id for item in runtime_evidence}
        if any(
            evidence_id not in runtime_ids
            for ids in runtime_node_evidence.values()
            for evidence_id in ids
        ):
            raise ValueError("runtime evidence overlay references an unknown record")
        evidence.extend(runtime_evidence)
    compiled_views = compile_views(architecture, semantic_overlay)
    views = {view.level: view for view in compiled_views}
    specs = {level: build_visual_spec(view) for level, view in views.items()}
    base_scenes = {
        level: build_scene(views[level], specs[level]) for level in ("L1", "L2", "L3", "L4")
    }
    suffix = architecture.architecture_id.removeprefix("architecture:")
    document_path = workspace / "documents" / f"{suffix}.canvas.json"
    if document_path.is_file():
        document = load_canvas_document(document_path)
        expected_digest = source_binding_digest(snapshot)
        if document.architecture_id != architecture.architecture_id:
            raise ValueError("saved CanvasDocument belongs to a different architecture")
        if document.source_snapshot_id != snapshot.snapshot_id:
            raise ValueError("saved CanvasDocument belongs to a stale source snapshot")
        if document.source_digest != expected_digest:
            raise ValueError("saved CanvasDocument source digest is stale")
        if set(document.base_scene_ids) != {scene.scene_id for scene in base_scenes.values()}:
            raise ValueError("saved CanvasDocument base scenes do not match this compilation")
    else:
        document = create_canvas_document(architecture, snapshot, base_scenes.values())
        persist_canvas_document(document_path, document)

    bundle = StudioBundle(
        artifact_path=artifact,
        workspace=workspace,
        static_dir=workspace / "studio",
        document_path=document_path,
        architecture=architecture,
        snapshot=snapshot,
        evidence=evidence,
        runtime_trace=runtime_trace,
        runtime_node_evidence=runtime_node_evidence,
        semantic_overlay=semantic_overlay,
        views=views,
        specs=specs,
        base_scenes=base_scenes,
        document=document,
    )
    for level in ("L1", "L2", "L3", "L4"):
        _write_json(workspace / "views" / level.lower() / "publication-view.json", views[level])
        _write_json(workspace / "views" / level.lower() / "visual-spec.json", specs[level])
        _write_json(workspace / "scenes" / level.lower() / "visual-scene.json", base_scenes[level])
    _write_static_bundle(bundle)
    return bundle
