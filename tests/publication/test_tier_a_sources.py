"""Tier A diagrams are immutable source-checked examples, never runtime claims."""

import hashlib
import json
from zipfile import ZipFile

import pytest

from tools.build_tier_a import ASSETS, FIXTURES, MODELS, OUTPUT, build_model


def test_confirmed_tier_a_model_scope_matches_source_archives() -> None:
    scope = json.loads((FIXTURES / "acceptance-scope.json").read_text(encoding="utf-8"))
    assert scope["scope_status"] == "model_corpus_confirmed"
    assert scope["configuration_status"] == "parameter_and_task_branch_review_pending"
    assert [item["name"] for item in scope["models"]] == [
        "Autoformer-main",
        "iTransformer",
        "PatchTST",
        "TimeMixer-main",
        "Transformer",
    ]
    assert {item["model_id"] for item in scope["models"]} == set(MODELS)
    for item in scope["models"]:
        graph = build_model(item["model_id"])
        assert item["archive"] == graph["archive"]
        assert item["archive_sha256"] == graph["archive_sha256"]
        assert graph["selection_status"] == "implementation_selected_pending_human_review"


@pytest.mark.parametrize("model", MODELS)
def test_tier_a_evidence_and_generated_contract_are_current(model: str) -> None:
    graph = build_model(model)
    saved = json.loads((OUTPUT / f"{model}.json").read_text(encoding="utf-8"))
    assert graph == saved
    assert graph["selection_status"] == "implementation_selected_pending_human_review"
    assert (
        hashlib.sha256((ASSETS / graph["archive"]).read_bytes()).hexdigest()
        == graph["archive_sha256"]
    )
    ids = {node["id"] for node in graph["nodes"]}
    assert len(ids) == len(graph["nodes"])
    assert all(edge["source"] in ids and edge["target"] in ids for edge in graph["edges"])
    with ZipFile(ASSETS / graph["archive"]) as source:
        for node in graph["nodes"]:
            proof = node["evidence"]
            raw = source.read(proof["file"])
            assert hashlib.sha256(raw).hexdigest() == proof["file_sha256"]
            assert proof["expression"] in raw.decode("utf-8-sig").splitlines()[proof["line"] - 1]
        for edge in graph["edges"]:
            proof = edge["evidence"]
            raw = source.read(proof["file"])
            assert proof["expression"] in raw.decode("utf-8-sig").splitlines()[proof["line"] - 1]
            assert proof["grade"] in {"E1", "E3"}

    base = FIXTURES / model
    configuration = json.loads((base / "approved-config-snapshot.json").read_text())
    assert configuration["archive_sha256"] == graph["archive_sha256"]
    assert configuration["approval_status"] == graph["selection_status"]
    evidence = json.loads((base / "evidence-ledger.json").read_text())
    assert set(evidence["nodes"]) == ids
    assert set(evidence["edges"]) == {edge["id"] for edge in graph["edges"]}
    for discrepancy in graph["discrepancies"]:
        for image, digest in discrepancy["reference_sha256"].items():
            assert hashlib.sha256((ASSETS / image).read_bytes()).hexdigest() == digest
    for filename in (
        "module-ledger.json",
        "tensor-ledger.json",
        "edge-ledger.json",
        "source-identity.json",
        "reference-discrepancy-ledger.json",
        "capability-report.json",
    ):
        assert (base / filename).is_file()


def test_selected_branches_correct_reference_conflicts() -> None:
    transformer = build_model("transformer")
    assert "softmax" not in {node["id"] for node in transformer["nodes"]}
    assert {edge["target_port"] for edge in transformer["edges"] if edge["kind"] == "memory"} == {
        "K_in",
        "V_in",
    }
    assert {
        (edge["source"], edge["target"])
        for edge in transformer["edges"]
        if edge["kind"] == "residual"
    } == {
        ("enc_layer_in", "enc_add1"),
        ("enc_add1", "enc_add2"),
        ("dec_layer_in", "dec_add1"),
        ("dec_add1", "dec_add2"),
        ("dec_add2", "dec_add3"),
    }
    assert all(
        edge["target_port"] == "skip_in"
        for edge in transformer["edges"]
        if edge["kind"] == "residual"
    )
    assert any(
        edge["source"] == "s_mask" and edge["target"] == "s_apply_mask"
        for edge in transformer["edges"]
    )
    assert not any(
        edge["source"] == "s_scale" and edge["target"] == "s_softmax"
        for edge in transformer["edges"]
    )
    assert all(node["id"] != "position" for node in build_model("autoformer")["nodes"])
    assert all(
        "conv mixer" not in node["label"].lower() for node in build_model("timemixer")["nodes"]
    )
    assert any(
        node["id"] == "flatten" and "D*Np" in node["shape"]
        for node in build_model("patchtst")["nodes"]
    )
    assert any(
        node["id"] == "invert" and node["shape"] == "[B,N,L]"
        for node in build_model("itransformer")["nodes"]
    )
