from __future__ import annotations

from pathlib import Path

import pytest

from archcanvas_python import analyze_project_v2

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "frontend_v2"


@pytest.mark.parametrize(
    ("fixture", "entrypoint", "pack_id", "template_id"),
    [
        (
            "autoformer_family",
            "model:Autoformer",
            "pattern-pack:autoformer-v2",
            "template:autoformer.family",
        ),
        (
            "itransformer_family",
            "model:ITransformer",
            "pattern-pack:itransformer-v2",
            "template:itransformer.family",
        ),
        (
            "patchtst_family",
            "model:PatchTST",
            "pattern-pack:patchtst-v2",
            "template:patchtst.family",
        ),
        (
            "timemixer_family",
            "model:TimeMixer",
            "pattern-pack:timemixer-v2",
            "template:timemixer.family",
        ),
    ],
)
def test_family_pack_is_evidence_bounded_and_schematic(
    tmp_path: Path,
    fixture: str,
    entrypoint: str,
    pack_id: str,
    template_id: str,
) -> None:
    bundle = analyze_project_v2(
        FIXTURES / fixture,
        entrypoint,
        "inference",
        "eval",
        tmp_path / fixture,
    )

    binding = next(item for item in bundle.exact_ir.pattern_bindings if item.pack_id == pack_id)
    semantic_ids = {
        *[item.definition_id for item in bundle.exact_ir.definitions],
        *[item.instance_id for item in bundle.exact_ir.instances],
        *[item.call_id for item in bundle.exact_ir.calls],
        *[item.repeat_id for item in bundle.exact_ir.repeats],
    }
    evidence_ids = {item.evidence_id for item in bundle.exact_ir.evidence}

    assert binding.fidelity == "schematic"
    assert binding.template_id == template_id
    assert set(binding.subject_ids) <= semantic_ids
    assert set(binding.evidence_ids) <= evidence_ids
    assert binding.pack_digest in bundle.analysis_input.pattern_pack_digests
    assert all(item.fidelity != "exact" for item in bundle.exact_ir.pattern_bindings)


def test_builtin_pattern_packs_can_be_excluded_from_analysis_identity(
    tmp_path: Path,
) -> None:
    bundle = analyze_project_v2(
        FIXTURES / "transformer_classic",
        "model:Transformer",
        "inference",
        "eval",
        tmp_path / "without-patterns",
        pattern_packs_enabled=False,
    )

    assert bundle.analysis_input.pattern_pack_digests == []
    assert bundle.semantic_graph.pattern_bindings == []
    assert bundle.exact_ir.pattern_bindings == []
    assert "V2_COMPAT_PATTERN_BINDING_LOSSY" not in {
        item.code for item in bundle.compatibility.architecture.unresolved
    }
