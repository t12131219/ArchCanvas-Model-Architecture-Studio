from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from archcanvas_core import builtin_registry_bundle
from archcanvas_core.models import (
    CanvasDocument,
    DraftGraphDocument,
    OfflineBundleFile,
    OfflineBundleManifest,
    StateMigrationPlan,
)
from archcanvas_core.protocols import (
    read_canvas_document_protocol,
    read_draft_graph_document_protocol,
    read_exact_architecture_ir_v2_protocol,
    read_module_registry_bundle_protocol,
    read_offline_bundle_manifest_protocol,
    read_state_migration_plan_protocol,
    read_versioned_protocol,
)
from archcanvas_python import analyze_project_v2

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "protocol_migration"
    / "canvas-document-0.9.json"
)
FRONTEND_FIXTURE = Path(__file__).parent / "fixtures" / "frontend_v2" / "conv_relu"


def test_canvas_document_previous_minor_migrates_with_fixed_receipt() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document, receipt = read_canvas_document_protocol(payload)

    assert document.schema_version == "1.0"
    assert document.base_hierarchy_id is None
    assert receipt.status == "migrated"
    assert receipt.migration_id == "migration:canvas-document.0-9-to-1-0"
    assert receipt.input_digest == (
        "f473a53e6d6c0fd022fa75660bdfc32897593158f607940fe0683ed73b3e8e8b"
    )
    assert receipt.output_digest == (
        "151efe3932d66e06f8c2cac98f0edb983c9d4f2b4128708f0fe91cd7d0c29f4b"
    )


def test_protocol_reader_rejects_unknown_major() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["schema_version"] = "2.0"
    with pytest.raises(ValueError, match="unsupported canvas-document schema major"):
        read_canvas_document_protocol(payload)


def test_protocol_reader_accepts_known_additive_minor_only_after_validation() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload.pop("base_scene_ids")
    payload["schema_version"] = "1.1"
    document, receipt = read_versioned_protocol(
        CanvasDocument,
        payload,
        protocol="canvas-document",
        current_version="1.0",
    )
    assert document.schema_version == "1.0"
    assert receipt.status == "compatible-minor"

    payload["unknown_additive_field"] = True
    with pytest.raises(ValidationError):
        read_versioned_protocol(
            CanvasDocument,
            payload,
            protocol="canvas-document",
            current_version="1.0",
        )


def test_named_persistent_protocol_readers_enforce_major_minor_policy(
    tmp_path: Path,
) -> None:
    frontend = analyze_project_v2(
        FRONTEND_FIXTURE,
        "app.model:Model",
        "inference",
        "eval",
        tmp_path / "analysis",
    )
    digest = "0" * 64
    values = [
        (
            read_exact_architecture_ir_v2_protocol,
            frontend.exact_ir.model_dump(mode="json"),
            "2.1",
            "3.0",
        ),
        (
            read_draft_graph_document_protocol,
            DraftGraphDocument(
                draft_id="draft:protocol-test",
                base_architecture_id="architecture:protocol-test",
                base_source_digest=digest,
                revision=0,
            ).model_dump(mode="json"),
            "1.1",
            "2.0",
        ),
        (
            read_module_registry_bundle_protocol,
            builtin_registry_bundle().model_dump(mode="json"),
            "1.1",
            "2.0",
        ),
        (
            read_state_migration_plan_protocol,
            StateMigrationPlan(
                plan_id="state-migration:protocol-test",
                framework="pytorch",
                base_source_digest=digest,
                result_source_digest=digest,
                source_state_digest=digest,
                target_state_schema_digest=digest,
                entries=[],
                status="verified",
            ).model_dump(mode="json"),
            "1.1",
            "2.0",
        ),
        (
            read_offline_bundle_manifest_protocol,
            OfflineBundleManifest(
                bundle_id="bundle:protocol-test",
                architecture_id="architecture:protocol-test",
                source_snapshot_id="snapshot:protocol-test",
                exact_ir_digest=digest,
                support_matrix_digest=digest,
                absolute_paths_redacted=True,
                files=[OfflineBundleFile(path="analysis.json", sha256=digest, size=0)],
            ).model_dump(mode="json"),
            "1.1",
            "2.0",
        ),
    ]

    for reader, payload, additive_version, unknown_major in values:
        additive = {**payload, "schema_version": additive_version}
        parsed, receipt = reader(additive)
        assert parsed.schema_version != additive_version
        assert receipt.status == "compatible-minor"
        with pytest.raises(ValueError, match="unsupported .* schema major"):
            reader({**payload, "schema_version": unknown_major})
