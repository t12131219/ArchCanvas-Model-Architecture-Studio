from __future__ import annotations

import json
from pathlib import Path

import pytest

from archcanvas_core.models import PatternDistribution
from archcanvas_core.validation import validate_architecture
from archcanvas_engine.cli import main
from archcanvas_patterns import (
    PatternRegistry,
    apply_pattern_packs,
    build_candidate_reviews,
    exact_ir_digest,
    load_registry,
)
from archcanvas_patterns.registry import manifest_digest
from archcanvas_publication import (
    build_scene,
    build_visual_spec,
    compile_views,
    validate_geometry,
    validate_publication,
)
from archcanvas_python import analyze_project

ROOT = Path(__file__).resolve().parents[1]
PROFILES = [
    ("transformer", "model:Transformer", "inference", "transformer-attention"),
    ("autoformer", "models.Autoformer:Model", "long_term_forecast", "autoformer-decomposition"),
    ("itransformer", "model.iTransformer:Model", "long_term_forecast", "itransformer-variable-token"),
    ("patchtst", "models.PatchTST:Model", "long_term_forecast", "patchtst-patching"),
    ("timemixer", "models.TimeMixer:Model", "long_term_forecast", "timemixer-multiscale"),
]
HOLDOUT_FAMILIES = [
    ("cnn-vit", "vision_tokens", "model:VisionTokenStem", "classification"),
    ("state-space", "state_space", "model:SelectiveStateCell", "inference"),
    ("gnn", "graph_message", "model:NeighborhoodExchange", "inference"),
    ("diffusion", "diffusion_denoiser", "model:TimestepDenoiser", "denoising"),
    ("moe", "sparse_moe", "model:DualExpertRouter", "inference"),
    ("time-series", "seasonal_timeseries", "model:SeasonalTrendForecaster", "forecast"),
    ("custom-hybrid", "residual_mlp", "model:CrossBlendRegressor", "forecast"),
]


def _analyze_fixture(name: str, entrypoint: str, task: str, *, patterns: bool = True):
    fixture = ROOT / "fixtures" / "tier_a" / name
    return analyze_project(
        fixture,
        entrypoint,
        task,
        "eval",
        (fixture / "config.json").read_bytes(),
        fixture / "config.json",
        pattern_packs_enabled=patterns,
    )


def _holdout():
    fixture = ROOT / "fixtures" / "holdout" / "residual_mlp"
    return analyze_project(
        fixture,
        "model:CrossBlendRegressor",
        "forecast",
        "eval",
        (fixture / "config.json").read_bytes(),
        fixture / "config.json",
        pattern_packs_enabled=False,
    )


def _holdout_family(fixture_name: str, entrypoint: str, task: str):
    fixture = ROOT / "fixtures" / "holdout" / fixture_name
    return analyze_project(
        fixture,
        entrypoint,
        task,
        "eval",
        (fixture / "config.json").read_bytes(),
        fixture / "config.json",
        pattern_packs_enabled=False,
    )


def _write_manifest(path: Path, payload: dict[str, object]) -> str:
    payload = dict(payload)
    payload.pop("pack_digest", None)
    digest = manifest_digest(payload)
    payload["pack_digest"] = digest
    path.mkdir(parents=True)
    (path / "pattern.json").write_text(json.dumps(payload), encoding="utf-8")
    return digest


@pytest.mark.parametrize(("fixture_name", "entrypoint", "task", "pack_id"), PROFILES)
def test_builtin_pack_positive_negative_mutation_and_digest_invariance(
    fixture_name: str,
    entrypoint: str,
    task: str,
    pack_id: str,
) -> None:
    registry = load_registry()
    architecture = _analyze_fixture(fixture_name, entrypoint, task).architecture
    before = exact_ir_digest(architecture)
    overlay, receipt = apply_pattern_packs(architecture, registry)
    assert overlay.status == "matched"
    assert overlay.applied_pack_ids == [pack_id]
    assert receipt.exact_ir_digest_before == receipt.exact_ir_digest_after == before
    assert exact_ir_digest(architecture) == before

    negative_overlay, negative_receipt = apply_pattern_packs(_holdout().architecture, registry)
    assert negative_overlay.status == "generic"
    assert next(item for item in negative_receipt.matches if item.pack_id == pack_id).status == "rejected"

    manifest = next(item for item in registry.manifests if item.pack_id == pack_id)
    mutated_required = [
        manifest.required[0].model_copy(update={"min_count": 10_000}),
        *manifest.required[1:],
    ]
    mutated = manifest.model_copy(update={"required": mutated_required})
    isolated = PatternRegistry(
        manifests=[mutated],
        loads=[next(item for item in registry.loads if item.pack_id == pack_id)],
    )
    mutated_overlay, mutated_receipt = apply_pattern_packs(architecture, isolated)
    assert mutated_overlay.status == "generic"
    assert mutated_receipt.matches[0].status == "rejected"
    assert mutated_receipt.matches[0].reasons[0].startswith("required_failed:")


def test_weak_name_hint_cannot_rescue_failed_hard_constraint() -> None:
    architecture = _holdout().architecture
    registry = load_registry()
    transformer = next(
        item for item in registry.manifests if item.pack_id == "transformer-attention"
    )
    name_only = transformer.model_copy(
        update={
            "required": [
                transformer.required[0].model_copy(update={"min_count": 1000})
            ],
            "optional": [
                transformer.optional[0].model_copy(update={"value": "residual"})
            ],
        }
    )
    overlay, receipt = apply_pattern_packs(
        architecture,
        PatternRegistry(manifests=[name_only], loads=[]),
    )
    assert overlay.status == "generic"
    assert receipt.matches[0].score == 0
    assert receipt.matches[0].status == "rejected"


def test_overlay_adds_publication_metadata_without_changing_canonical_sets() -> None:
    architecture = _analyze_fixture("transformer", "model:Transformer", "inference").architecture
    overlay, _ = apply_pattern_packs(architecture, load_registry())
    generic_views = compile_views(architecture)
    annotated_views = compile_views(architecture, overlay)
    for generic, annotated in zip(generic_views, annotated_views, strict=True):
        assert generic.canonical_node_ids == annotated.canonical_node_ids
        assert generic.canonical_edge_ids == annotated.canonical_edge_ids
        assert generic.canonical_tensor_ids == annotated.canonical_tensor_ids
        assert generic.canonical_port_ids == annotated.canonical_port_ids
    assert any(
        node.attributes["semantic_annotations"]
        for view in annotated_views
        for node in view.nodes
    )
    stale = overlay.model_copy(update={"exact_ir_digest": "0" * 64})
    with pytest.raises(ValueError, match="overlay binding is stale"):
        compile_views(architecture, stale)


def test_workspace_requires_digest_lock_and_conflicts_fall_back_to_generic(
    tmp_path: Path,
) -> None:
    builtin = load_registry()
    transformer = next(
        item for item in builtin.manifests if item.pack_id == "transformer-attention"
    )
    payload = transformer.model_dump(mode="json")
    payload.update(
        {
            "pack_id": "workspace-transformer-review",
            "distribution": PatternDistribution.WORKSPACE.value,
            "required": [
                *payload["required"],
                {
                    "predicate_id": "layer-norm-fact",
                    "stage": "structure",
                    "fact": "node-attribute",
                    "field": "op_type",
                    "value": "nn.LayerNorm",
                    "min_count": 3,
                },
            ],
            "annotations": [
                {
                    **payload["annotations"][0],
                    "semantic_role": "conflicting projection interpretation",
                }
            ],
        }
    )
    workspace = tmp_path / "workspace-pack"
    digest = _write_manifest(workspace, payload)
    with pytest.raises(ValueError, match="requires an explicit digest lock"):
        load_registry(workspace_paths=[workspace])
    with pytest.raises(ValueError, match="digest lock mismatch"):
        load_registry(
            workspace_paths=[workspace],
            workspace_locks=[f"workspace-transformer-review={'0' * 64}"],
        )
    registry = load_registry(
        workspace_paths=[workspace],
        workspace_locks=[f"workspace-transformer-review={digest}"],
    )
    architecture = _analyze_fixture("transformer", "model:Transformer", "inference").architecture
    overlay, receipt = apply_pattern_packs(architecture, registry)
    assert overlay.status == "ambiguous"
    assert overlay.annotations == []
    assert "ambiguous_pattern" in overlay.reasons
    assert {item.status for item in receipt.matches if item.status == "ambiguous"} == {"ambiguous"}


def test_candidate_is_preview_only_and_grants_no_permissions(tmp_path: Path) -> None:
    base = load_registry().manifests[0].model_dump(mode="json")
    base.update(
        {
            "pack_id": "candidate-residual-flow",
            "distribution": PatternDistribution.SESSION_CANDIDATE.value,
            "required": [
                {
                    "predicate_id": "two-merges",
                    "stage": "structure",
                    "fact": "node-kind",
                    "value": "merge_event",
                    "min_count": 2,
                },
                {
                    "predicate_id": "residual-dataflow",
                    "stage": "dataflow",
                    "fact": "edge-type",
                    "value": "residual",
                    "min_count": 4,
                },
            ],
            "optional": [],
            "forbidden": [],
            "annotations": [],
            "known_limitations": ["Only the current holdout has been inspected."],
        }
    )
    candidate = tmp_path / "candidate"
    _write_manifest(candidate, base)
    registry = load_registry(candidate_paths=[candidate])
    architecture = _holdout().architecture
    overlay, receipt = apply_pattern_packs(architecture, registry)
    reviews = build_candidate_reviews(architecture, registry)
    candidate_match = next(
        item for item in receipt.matches if item.pack_id == "candidate-residual-flow"
    )
    assert candidate_match.status == "candidate-match"
    assert "candidate-residual-flow" not in overlay.applied_pack_ids
    assert reviews[0].status == "preview-only"
    assert reviews[0].activated is False
    assert not any(reviews[0].permissions.values())
    assert reviews[0].exact_ir_digest_before == reviews[0].exact_ir_digest_after


def test_registry_rejects_stale_digest_and_executable_matcher(tmp_path: Path) -> None:
    payload = load_registry().manifests[0].model_dump(mode="json")
    payload.update({"pack_id": "workspace-untrusted", "distribution": "workspace"})
    stale = tmp_path / "stale"
    digest = _write_manifest(stale, payload)
    stale_payload = json.loads((stale / "pattern.json").read_text())
    stale_payload["version"] = "changed-without-redigest"
    (stale / "pattern.json").write_text(json.dumps(stale_payload), encoding="utf-8")
    with pytest.raises(ValueError, match="digest is stale"):
        load_registry(
            workspace_paths=[stale],
            workspace_locks=[f"workspace-untrusted={digest}"],
        )

    executable = tmp_path / "executable"
    executable_digest = _write_manifest(executable, payload)
    (executable / "matcher.py").write_text("raise RuntimeError('must not execute')\n")
    with pytest.raises(ValueError, match="executable Pattern Pack matchers"):
        load_registry(
            workspace_paths=[executable],
            workspace_locks=[f"workspace-untrusted={executable_digest}"],
        )


@pytest.mark.parametrize(("family", "fixture_name", "entrypoint", "task"), HOLDOUT_FAMILIES)
def test_holdout_without_pattern_pack_passes_semantic_publication_and_geometry(
    family: str, fixture_name: str, entrypoint: str, task: str
) -> None:
    bundle = _holdout_family(fixture_name, entrypoint, task)
    assert family
    assert bundle.snapshot.source_files
    assert all(record.evidence_ids for record in bundle.architecture.nodes)
    gates, diagnostics = validate_architecture(
        bundle.architecture,
        bundle.evidence,
        bundle.snapshot,
    )
    assert all(gate.status == "passed" for gate in gates if gate.status != "skipped")
    assert not diagnostics
    assert all(
        node.attributes.get("architecture_profile", "generic") == "generic"
        for node in bundle.architecture.nodes
    )
    for node in bundle.architecture.nodes:
        if node.kind.value == "opaque_composite":
            assert node.attributes.get("unresolved_reason")
            assert node.attributes.get("capabilities")
    views = compile_views(bundle.architecture)
    publication_gates, publication_diagnostics = validate_publication(
        bundle.architecture, views
    )
    assert all(gate.status == "passed" for gate in publication_gates)
    assert not publication_diagnostics
    assert {view.layout_family for view in views} == {"generic-dag"}
    for view in views:
        gate, geometry_diagnostics = validate_geometry(
            build_scene(view, build_visual_spec(view))
        )
        assert gate.status == "passed"
        assert not geometry_diagnostics


def test_cli_candidate_review_does_not_activate_candidate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = load_registry().manifests[0].model_dump(mode="json")
    base.update(
        {
            "pack_id": "candidate-holdout",
            "distribution": "session-candidate",
            "required": [
                {
                    "predicate_id": "merge-fact",
                    "stage": "structure",
                    "fact": "node-kind",
                    "value": "merge_event",
                    "min_count": 2,
                }
            ],
            "optional": [],
            "forbidden": [],
            "annotations": [],
        }
    )
    candidate = tmp_path / "candidate"
    _write_manifest(candidate, base)
    fixture = ROOT / "fixtures" / "holdout" / "residual_mlp"
    out = tmp_path / "analysis"
    assert main(
        [
            "analyze",
            "--project",
            str(fixture),
            "--entry",
            "model:CrossBlendRegressor",
            "--config",
            str(fixture / "config.json"),
            "--task",
            "forecast",
            "--mode",
            "eval",
            "--out",
            str(out),
            "--pattern-candidate",
            str(candidate),
            "--json",
        ]
    ) == 0
    receipt = json.loads(capsys.readouterr().out)
    review = json.loads((out / "pattern-candidate-review.json").read_text())
    overlay = json.loads((out / "semantic-annotation-overlay.json").read_text())
    assert receipt["details"]["candidate_pattern_packs"] == ["candidate-holdout"]
    assert review[0]["activated"] is False
    assert overlay["applied_pack_ids"] == []
