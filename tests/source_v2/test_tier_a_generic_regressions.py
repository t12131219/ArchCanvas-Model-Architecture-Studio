from __future__ import annotations

from pathlib import Path

import pytest

from archcanvas_python import analyze_project_v2

ROOT = Path(__file__).resolve().parents[2]
TIER_A = ROOT / "fixtures" / "tier_a"
CASES = (
    ("transformer", "model:Transformer", "inference"),
    ("autoformer", "models.Autoformer:Model", "long_term_forecast"),
    ("itransformer", "model.iTransformer:Model", "long_term_forecast"),
    ("patchtst", "models.PatchTST:Model", "long_term_forecast"),
    ("timemixer", "models.TimeMixer:Model", "long_term_forecast"),
)


@pytest.fixture(scope="module")
def tier_a_bundles(tmp_path_factory: pytest.TempPathFactory):
    workspace = tmp_path_factory.mktemp("tier-a-v2")
    bundles = {}
    for fixture_name, entrypoint, task in CASES:
        fixture = TIER_A / fixture_name
        bundles[fixture_name] = analyze_project_v2(
            fixture,
            entrypoint,
            task,
            "eval",
            workspace / fixture_name,
            config_bytes=(fixture / "config.json").read_bytes(),
        )
    return bundles


@pytest.mark.parametrize("fixture_name", [item[0] for item in CASES])
def test_full_tier_a_projects_use_generic_v2_without_blocking(
    tier_a_bundles, fixture_name: str
) -> None:
    bundle = tier_a_bundles[fixture_name]
    compatibility = bundle.compatibility.architecture

    assert bundle.exact_ir.definitions
    assert bundle.exact_ir.instances
    assert bundle.exact_ir.calls
    assert compatibility.nodes
    assert compatibility.edges
    assert compatibility.tensors
    assert not [item for item in bundle.exact_ir.diagnostics if item.severity == "blocking"]


def test_cross_file_instance_uses_construction_site_anchor(tier_a_bundles) -> None:
    bundle = tier_a_bundles["autoformer"]

    instance = next(
        item for item in bundle.exact_ir.instances if item.instance_path == "model.decomp"
    )
    definition = next(
        item
        for item in bundle.exact_ir.definitions
        if item.definition_id == instance.local_definition_id
    )
    assert instance.anchor.logical_path == "models/Autoformer.py"
    assert definition.anchor.logical_path == "layers/Autoformer_EncDec.py"
    assert not [item for item in bundle.exact_ir.diagnostics if item.severity == "blocking"]


def test_residual_additions_preserve_transformer_value_flow(tier_a_bundles) -> None:
    bundle = tier_a_bundles["transformer"]

    residual_adds = [
        item
        for item in bundle.exact_ir.calls
        if item.definition_ref is not None
        and item.definition_ref.definition_id == "pytorch.op.add"
    ]
    assert len(residual_adds) == 4
    assert all(
        [binding.port_id for binding in item.input_bindings] == ["operands", "operands"]
        for item in residual_adds
    )
    assert not [item for item in bundle.exact_ir.diagnostics if item.severity == "blocking"]
