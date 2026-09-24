from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path, PureWindowsPath
from typing import Any

from archcanvas_core.models import (
    ArchitectureIR,
    OfflineBundleFile,
    OfflineBundleManifest,
    SemanticAnnotationOverlay,
    SourceSnapshot,
)
from archcanvas_patterns import exact_ir_digest
from archcanvas_publication import (
    build_scene,
    build_visual_spec,
    compile_hierarchy,
    compile_views,
    render_html,
    render_pdf,
    render_png,
    render_svg,
    validate_geometry,
    validate_publication,
)

from .support import release_support_matrix

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _compact(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and (
        Path(value).is_absolute() or PureWindowsPath(value).is_absolute()
    ):
        name = PureWindowsPath(value).name if PureWindowsPath(value).is_absolute() else Path(value).name
        return f"<redacted>/{name}"
    return value


def _write_json(path: Path, value: Any, *, redact: bool = False) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if redact:
        value = _redact(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_compact(value), encoding="utf-8")


def _overlay(artifact: Path, architecture: ArchitectureIR) -> SemanticAnnotationOverlay | None:
    path = artifact.parent / "semantic-annotation-overlay.json"
    if not path.is_file():
        return None
    overlay = SemanticAnnotationOverlay.model_validate_json(path.read_text(encoding="utf-8"))
    if (
        overlay.architecture_id != architecture.architecture_id
        or overlay.exact_ir_digest != exact_ir_digest(architecture)
    ):
        raise ValueError("semantic annotation overlay binding is stale")
    return overlay


def _bundle_files(root: Path) -> list[OfflineBundleFile]:
    return [
        OfflineBundleFile(
            path=path.relative_to(root).as_posix(),
            sha256=_sha256(path),
            size=path.stat().st_size,
        )
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "bundle-manifest.json"
    ]


def create_bundle(artifact: Path, output: Path) -> tuple[OfflineBundleManifest, list[str]]:
    artifact = artifact.resolve()
    output = output.resolve()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"bundle output already exists: {output}")
    architecture = ArchitectureIR.model_validate_json(artifact.read_text(encoding="utf-8"))
    snapshot_path = artifact.parent / "source-snapshot.json"
    if not snapshot_path.is_file():
        raise ValueError("offline bundle requires source-snapshot.json beside architecture.json")
    snapshot = SourceSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
    if snapshot.snapshot_id != architecture.source_snapshot_id:
        raise ValueError("source snapshot does not match architecture")
    semantic_overlay = _overlay(artifact, architecture)
    views = compile_views(architecture, semantic_overlay)
    hierarchy = compile_hierarchy(architecture, semantic_overlay)
    publication_gates, diagnostics = validate_publication(architecture, views)
    gates = [gate.model_dump(mode="json") for gate in publication_gates]
    if diagnostics or any(gate.status == "failed" for gate in publication_gates):
        raise ValueError("publication validation failed; refusing to create release bundle")

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".archcanvas-bundle-", dir=output.parent))
    try:
        analysis_target = staging / "analysis"
        analysis_target.mkdir()
        allowlisted = {
            "architecture.json",
            "source-snapshot.json",
            "evidence-ledger.json",
            "module-ledger.json",
            "tensor-ledger.json",
            "edge-ledger.json",
            "discrepancy-ledger.json",
            "omission-ledger.json",
            "capability-report.json",
            "semantic-annotation-overlay.json",
            "pattern-pack-receipt.json",
            "pattern-candidate-review.json",
            "source-correction-report.json",
            "runtime-receipt.json",
            "runtime-trace.json",
            "runtime-evidence-ledger.json",
            "runtime-evidence-overlay.json",
            "analysis-receipt.json",
        }
        for source in sorted(artifact.parent.iterdir()):
            if source.is_file() and source.name in allowlisted:
                try:
                    payload = json.loads(source.read_text(encoding="utf-8"))
                except json.JSONDecodeError as error:
                    raise ValueError(f"bundle JSON artifact is invalid: {source.name}") from error
                _write_json(analysis_target / source.name, payload, redact=True)

        _write_json(staging / "publication" / "hierarchy.json", hierarchy)
        for view in views:
            projection_name = "full" if view.fully_expanded else "collapsed"
            target = staging / "publication" / projection_name
            spec = build_visual_spec(view)
            scene = build_scene(view, spec)
            geometry_gate, geometry_diagnostics = validate_geometry(scene)
            gates.append(geometry_gate.model_dump(mode="json"))
            if geometry_gate.status == "failed" or geometry_diagnostics:
                raise ValueError(
                    f"geometry validation failed for {view.projection_id}"
                )
            _write_json(target / "publication-view.json", view)
            _write_json(target / "visual-spec.json", spec)
            _write_json(target / "visual-scene.json", scene)
            (target / "scene.svg").write_text(render_svg(scene), encoding="utf-8")
            (target / "view.html").write_text(render_html(scene, view, spec), encoding="utf-8")
            (target / "scene.png").write_bytes(render_png(scene))
            (target / "scene.pdf").write_bytes(render_pdf(scene))

        shutil.copytree(REPOSITORY_ROOT / "schemas", staging / "schemas")
        _write_json(staging / "support-matrix.json", release_support_matrix())
        _write_json(
            staging / "verification-receipt.json",
            {
                "schema_version": "1.0",
                "status": "ok",
                "source_execution": False,
                "network_required": False,
                "gates": gates,
                "visual_review": "not-included",
            },
        )
        files = _bundle_files(staging)
        digest = exact_ir_digest(architecture)
        manifest = OfflineBundleManifest(
            bundle_id=f"bundle:{hashlib.sha256(f'{architecture.architecture_id}:{digest}'.encode()).hexdigest()[:16]}",
            architecture_id=architecture.architecture_id,
            source_snapshot_id=snapshot.snapshot_id,
            exact_ir_digest=digest,
            absolute_paths_redacted=True,
            files=files,
        )
        _write_json(staging / "bundle-manifest.json", manifest)
        os.replace(staging, output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest, [item["gate"] for item in gates if item["status"] == "passed"]


def verify_bundle(root: Path) -> OfflineBundleManifest:
    root = root.resolve()
    manifest_path = root / "bundle-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("bundle-manifest.json is missing")
    manifest = OfflineBundleManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    expected = {item.path: item for item in manifest.files}
    actual = {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() and path.name != "bundle-manifest.json"
    }
    if set(actual) != set(expected):
        raise ValueError("offline bundle file inventory does not match its manifest")
    for relative, path in actual.items():
        record = expected[relative]
        if _sha256(path) != record.sha256 or path.stat().st_size != record.size:
            raise ValueError(f"offline bundle file digest mismatch: {relative}")
    architecture = ArchitectureIR.model_validate_json(
        (root / "analysis" / "architecture.json").read_text(encoding="utf-8")
    )
    if (
        architecture.architecture_id != manifest.architecture_id
        or exact_ir_digest(architecture) != manifest.exact_ir_digest
    ):
        raise ValueError("offline bundle architecture binding is invalid")
    return manifest
