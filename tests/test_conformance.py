from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from archcanvas_core.models import TransactionState
from archcanvas_python import analyze_project
from archcanvas_studio.bundle import prepare_studio_bundle

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "tier_a" / "transformer"


@pytest.fixture
def studio_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    analyzed = analyze_project(
        project,
        "model:Transformer",
        "inference",
        "eval",
        (project / "config.json").read_bytes(),
        project / "config.json",
    )
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    artifact = analysis / "architecture.json"
    artifact.write_text(analyzed.architecture.model_dump_json(), encoding="utf-8")
    (analysis / "source-snapshot.json").write_text(
        analyzed.snapshot.model_dump_json(), encoding="utf-8"
    )
    (analysis / "evidence-ledger.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in analyzed.evidence]),
        encoding="utf-8",
    )
    return project, artifact, tmp_path / ".archcanvas"


def test_source_view_report_is_exact_zero_write_and_persistent(
    studio_paths: tuple[Path, Path, Path],
) -> None:
    _, artifact, workspace = studio_paths
    bundle = prepare_studio_bundle(artifact, workspace, write_static=False)

    reports = [
        report for report in bundle.round_trip_reports or [] if report.path == "source-view"
    ]
    assert len(reports) == 1
    report = reports[0]
    assert report.semantic_isomorphism == "exact"
    assert report.expected_delta_digest == report.observed_delta_digest
    assert report.base_source_digest == bundle.document.source_digest
    assert report.result_source_digest == bundle.document.source_digest
    assert report.base_exact_ir_digest == report.result_exact_ir_digest
    assert report.source_writes == []
    generator_context = next(
        item
        for item in bundle.state()["parameter_edit_contexts"]
        if item["target_node_id"] == "node:generator"
        and item["parameter_name"] == "out_features"
    )
    assert generator_context["value_origin"]["kind"] == "config-key"
    assert generator_context["default_scope"] == "config-value"

    reopened = prepare_studio_bundle(artifact, workspace, write_static=False)
    assert reopened.round_trip_reports == bundle.round_trip_reports
    persisted = list((workspace / "conformance").glob("source-view.*.json"))
    assert len(persisted) == 1


def test_parameter_report_tracks_result_digests_and_discard_has_zero_writes(
    studio_paths: tuple[Path, Path, Path],
) -> None:
    project, artifact, workspace = studio_paths
    before = (project / "config.json").read_bytes()
    bundle = prepare_studio_bundle(artifact, workspace, write_static=False)

    payload = {
        "patch_id": "patch:conformance-parameter-discard",
        "target_node_id": "node:generator",
        "parameter_name": "out_features",
        "new_value": 16000,
    }
    bundle.prepare_parameter(payload)

    transaction = bundle.active_transaction
    assert transaction is not None
    assert transaction.state is TransactionState.REVIEW_READY
    assert transaction.result_source_corpus_digest is not None
    assert transaction.result_exact_ir_digest is not None
    report = next(
        item
        for item in bundle.round_trip_reports or []
        if item.report_id.endswith(transaction.transaction_id.removeprefix("transaction:"))
    )
    assert report.path == "intent-source"
    assert report.semantic_isomorphism == "exact"
    assert report.expected_delta_digest == report.observed_delta_digest
    assert report.result_source_digest == transaction.result_source_corpus_digest
    assert report.result_exact_ir_digest == transaction.result_exact_ir_digest
    assert report.source_writes == []

    bundle.prepare_parameter(payload)
    assert bundle.active_transaction == transaction
    assert len(list((workspace / "transactions").iterdir())) == 1
    assert len(
        [item for item in bundle.round_trip_reports or [] if item.path == "intent-source"]
    ) == 1

    bundle.discard_parameter()

    assert bundle.active_transaction is not None
    assert bundle.active_transaction.state is TransactionState.DISCARDED
    discarded = next(
        item for item in bundle.round_trip_reports or [] if item.report_id == report.report_id
    )
    assert discarded.semantic_isomorphism == "exact"
    assert discarded.source_writes == []
    assert (project / "config.json").read_bytes() == before

    reopened = prepare_studio_bundle(artifact, workspace, write_static=False)
    assert discarded in (reopened.round_trip_reports or [])


def test_committed_report_lists_exact_transaction_file_changes(
    studio_paths: tuple[Path, Path, Path],
) -> None:
    _, artifact, workspace = studio_paths
    bundle = prepare_studio_bundle(artifact, workspace, write_static=False)
    bundle.prepare_parameter(
        {
            "patch_id": "patch:conformance-parameter-commit",
            "target_node_id": "node:generator",
            "parameter_name": "out_features",
            "new_value": 16000,
        }
    )
    assert bundle.active_transaction is not None
    expected_writes = sorted(item.path for item in bundle.active_transaction.file_changes)

    bundle.commit_parameter()

    assert bundle.active_transaction is not None
    assert bundle.active_transaction.state is TransactionState.COMMITTED
    report = next(
        item
        for item in bundle.round_trip_reports or []
        if item.report_id.endswith(
            bundle.active_transaction.transaction_id.removeprefix("transaction:")
        )
    )
    assert report.semantic_isomorphism == "exact"
    assert report.source_writes == expected_writes


def test_structural_transaction_emits_exact_intent_source_report(
    studio_paths: tuple[Path, Path, Path],
) -> None:
    project, artifact, workspace = studio_paths
    before = (project / "model.py").read_bytes()
    bundle = prepare_studio_bundle(artifact, workspace, write_static=False)

    bundle.prepare_structural(
        {
            "patch_id": "patch:conformance-activation",
            "operation": "replace_activation",
            "target_node_id": "node:activation",
            "parameters": {"replacement": "ReLU"},
        }
    )

    assert bundle.active_transaction is not None
    transaction = bundle.active_transaction
    assert transaction.state is TransactionState.REVIEW_READY
    report = next(
        item
        for item in bundle.round_trip_reports or []
        if item.report_id.endswith(transaction.transaction_id.removeprefix("transaction:"))
    )
    assert report.path == "intent-source"
    assert report.semantic_isomorphism == "exact"
    assert report.expected_delta_digest == report.observed_delta_digest
    assert report.source_writes == []
    assert (project / "model.py").read_bytes() == before
