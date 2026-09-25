from __future__ import annotations

import json
from pathlib import Path

from archcanvas_adapters import analyze_with_adapter
from archcanvas_core.models import NodeKind, ParameterOrigin
from archcanvas_core.validation import validate_architecture
from archcanvas_studio.project import discover_project


def _write_unknown_benchmark(root: Path) -> None:
    (root / "layers").mkdir(parents=True)
    (root / "models").mkdir()
    (root / "forecasting").mkdir()
    (root / "layers" / "base.py").write_text(
        "from torch import nn\n"
        "class FrameworkBase(nn.Module):\n"
        "    pass\n",
        encoding="utf-8",
    )
    (root / "models" / "forecast.py").write_text(
        "from layers.base import FrameworkBase\n"
        "class Forecaster(FrameworkBase):\n"
        "    def forward(self, *inputs, **kwargs):\n"
        "        value = inputs[0]\n"
        "        if kwargs.get('return_aux'):\n"
        "            return value, kwargs\n"
        "        return value\n"
        "class WrappedForecaster(FrameworkBase):\n"
        "    pass\n"
        "def assemble_forecaster(settings):\n"
        "    return WrappedForecaster(settings)\n"
        "def unrelated_helper(value):\n"
        "    return value\n",
        encoding="utf-8",
    )
    (root / "forecasting" / "__init__.py").write_text(
        "from models.forecast import WrappedForecaster as PublicForecaster\n",
        encoding="utf-8",
    )
    (root / "configured.py").write_text(
        "from torch import nn\n"
        "class ConfiguredForecaster(nn.Module):\n"
        "    def __init__(self, settings):\n"
        "        super().__init__()\n"
        "        self.projection = nn.Linear(settings.width, settings.width)\n"
        "    def forward(self, values):\n"
        "        return self.projection(values)\n",
        encoding="utf-8",
    )


def _assert_semantically_closed(bundle: object) -> None:
    gates, diagnostics = validate_architecture(
        bundle.architecture,
        bundle.evidence,
        bundle.snapshot,
    )
    assert next(gate for gate in gates if gate.gate == "B-semantic-closure").status == "passed"
    assert not diagnostics


def test_discovery_uses_structure_across_modules_without_model_name_rules(
    tmp_path: Path,
) -> None:
    _write_unknown_benchmark(tmp_path)
    (tmp_path / "broken.py").write_text("def unfinished(\n", encoding="utf-8")

    discovered = discover_project(tmp_path)
    by_id = {item["entrypoint"]: item for item in discovered["entrypoints"]}

    assert by_id["models.forecast:Forecaster"]["framework"] == "pytorch"
    assert by_id["models.forecast:Forecaster"]["top_level"] is True
    assert by_id["models.forecast:Forecaster"]["analysis_root"] == "."
    assert "models.forecast:WrappedForecaster" in by_id
    assert "models.forecast:assemble_forecaster" in by_id
    assert "models.forecast:unrelated_helper" not in by_id
    assert by_id["forecasting:PublicForecaster"]["kind"] == "re-export"
    assert discovered["warnings"] == ["broken.py: SyntaxError"]


def test_auto_analysis_keeps_control_flow_and_dynamic_execution_as_unresolved_ir(
    tmp_path: Path,
) -> None:
    _write_unknown_benchmark(tmp_path)

    control_flow = analyze_with_adapter(
        tmp_path,
        "models.forecast:Forecaster",
        "forecast",
        "eval",
        b"{}",
        None,
        framework="auto",
        pattern_packs_enabled=True,
    )
    assert control_flow.architecture.framework == "pytorch"
    assert any(
        node.kind is NodeKind.OPAQUE_COMPOSITE
        and node.attributes.get("unresolved_reason") == "static_control_flow_not_expanded"
        for node in control_flow.architecture.nodes
    )
    _assert_semantically_closed(control_flow)

    inherited = analyze_with_adapter(
        tmp_path,
        "forecasting:PublicForecaster",
        "forecast",
        "eval",
        b"{}",
        None,
        framework="auto",
        pattern_packs_enabled=True,
    )
    assert inherited.architecture.framework == "pytorch"
    assert any(
        fact.code == "EXECUTION_METHOD_NOT_LOCALLY_DEFINED"
        for fact in inherited.architecture.unresolved
    )
    _assert_semantically_closed(inherited)


def test_config_object_attributes_are_resolved_without_executing_source(
    tmp_path: Path,
) -> None:
    _write_unknown_benchmark(tmp_path)
    config = json.dumps({"width": 12}).encode()
    bundle = analyze_with_adapter(
        tmp_path,
        "configured:ConfiguredForecaster",
        "forecast",
        "eval",
        config,
        None,
        framework="auto",
        pattern_packs_enabled=False,
    )

    projection = next(
        node for node in bundle.architecture.nodes if node.attributes.get("module_path") == "self.projection"
    )
    assert [parameter.value for parameter in projection.parameters[:2]] == [12, 12]
    assert {parameter.origin for parameter in projection.parameters[:2]} == {ParameterOrigin.CONFIG}
    _assert_semantically_closed(bundle)


def test_common_mapping_config_formats_share_the_static_resolution_path(
    tmp_path: Path,
) -> None:
    _write_unknown_benchmark(tmp_path)
    for name, content in (
        ("settings.toml", "width = 16\n"),
        ("settings.yaml", "width: 16\n"),
    ):
        config_path = tmp_path / name
        config_path.write_text(content, encoding="utf-8")
        bundle = analyze_with_adapter(
            tmp_path,
            "configured:ConfiguredForecaster",
            "forecast",
            "eval",
            config_path.read_bytes(),
            config_path,
            framework="auto",
            pattern_packs_enabled=False,
        )
        assert bundle.snapshot.resolved_config == {"width": 16}
        _assert_semantically_closed(bundle)
