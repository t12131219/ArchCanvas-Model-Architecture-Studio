from __future__ import annotations

import json
from pathlib import Path

import pytest

from archcanvas_core.models.source_identity import IdentityReconciliation, ReconciliationDecision
from archcanvas_python.analyzers import AnalyzerUnavailable, fixture_analyzer_registry
from archcanvas_python.fixture_analyzer import analyze_transformer_fixture
from archcanvas_python.cli import main
from archcanvas_python.transactions.set_parameter import (
    TransactionRejected,
    commit_candidate,
    plan_set_parameter,
)


def test_candidate_transaction_has_one_hunk_and_exact_delta(
    before_raw, before_ir, patch_set, source_document, fixture_path
) -> None:
    candidate = plan_set_parameter(before_raw, patch_set, source_document, before_ir)
    assert candidate.candidate_bytes == (fixture_path / "source" / "after" / "model.py").read_bytes()
    assert candidate.diff.count("@@ ") == 1
    assert "-                    nhead=8" in candidate.diff
    assert "+                    nhead=16" in candidate.diff
    assert not candidate.blocking
    assert candidate.validation.issues == []


def test_commit_is_atomic_after_final_revision_check(
    tmp_path: Path, before_raw, before_ir, patch_set, source_document, fixture_path
) -> None:
    target = tmp_path / "model.py"
    target.write_bytes(before_raw)
    candidate = plan_set_parameter(before_raw, patch_set, source_document, before_ir)
    revision = commit_candidate(target, candidate)
    assert revision == candidate.after_source.file_revisions["model.py"]
    assert target.read_bytes() == (fixture_path / "source" / "after" / "model.py").read_bytes()
    assert not list(tmp_path.glob(".model.py.*.tmp"))


def test_commit_rejects_concurrent_source_change(
    tmp_path: Path, before_raw, before_ir, patch_set, source_document
) -> None:
    target = tmp_path / "model.py"
    target.write_bytes(before_raw)
    candidate = plan_set_parameter(before_raw, patch_set, source_document, before_ir)
    target.write_bytes(before_raw + b"\n# concurrent edit\n")
    with pytest.raises(TransactionRejected, match="STALE_COMMIT_REVISION"):
        commit_candidate(target, candidate)
    assert target.read_bytes().endswith(b"# concurrent edit\n")


def test_transaction_rejects_ambiguous_identity(
    before_raw, before_ir, patch_set, source_document
) -> None:
    ambiguous = IdentityReconciliation(
        old_identity_id=None,
        new_discovery_id="discovery:ambiguous-layers",
        resolved_identity_id=None,
        score=0.90,
        decision=ReconciliationDecision.AMBIGUOUS,
        reasons=["top scores are too close"],
    )
    source = source_document.model_copy(update={"reconciliations": [ambiguous]})
    with pytest.raises(TransactionRejected, match="BEFORE_AMBIGUOUS_IDENTITY"):
        plan_set_parameter(before_raw, patch_set, source, before_ir)


def test_crlf_candidate_preserves_line_endings(before_raw, patch_set) -> None:
    crlf_source = before_raw.replace(b"\n", b"\r\n")
    source, ir = analyze_transformer_fixture(crlf_source)
    patch = patch_set.patches[0].model_copy(
        update={"anchor_content_fingerprint": source.anchors[0].content_fingerprint}
    )
    crlf_patch_set = patch_set.model_copy(
        update={"base_source_revision": source.file_revisions["model.py"], "patches": [patch]}
    )
    candidate = plan_set_parameter(crlf_source, crlf_patch_set, source, ir)
    assert b"\r\n" in candidate.candidate_bytes
    assert b"\n" not in candidate.candidate_bytes.replace(b"\r\n", b"")
    assert candidate.candidate_bytes.count(b"\r\n") == crlf_source.count(b"\r\n")


def test_analyzer_registry_fails_closed_for_unknown_project() -> None:
    with pytest.raises(AnalyzerUnavailable, match="no analyzer registered"):
        fixture_analyzer_registry().resolve("project:unregistered")


def test_cli_is_candidate_only_by_default(tmp_path: Path, fixture_path, before_raw, capsys) -> None:
    target = tmp_path / "model.py"
    target.write_bytes(before_raw)
    exit_code = main(["--fixture-dir", str(fixture_path), "--source-file", str(target)])
    result = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert result["status"] == "candidate"
    assert not result["committed"]
    assert not result["blocking"]
    assert target.read_bytes() == before_raw


def test_cli_commit_requires_explicit_flag(tmp_path: Path, fixture_path, before_raw) -> None:
    target = tmp_path / "model.py"
    target.write_bytes(before_raw)
    exit_code = main(
        ["--fixture-dir", str(fixture_path), "--source-file", str(target), "--commit"]
    )
    assert exit_code == 0
    assert b"nhead=16" in target.read_bytes()
