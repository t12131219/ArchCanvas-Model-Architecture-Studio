from archcanvas_python.transforms.registry import (
    available_parameter_names,
    registered_parameter_names,
    resolve_parameter_transform,
)


def test_stage7_parameter_registry_exposes_reviewed_aliases() -> None:
    assert resolve_parameter_transform("num_heads").transform_id == "num_heads"
    assert resolve_parameter_transform("dropout").transform_id == "dropout"
    assert resolve_parameter_transform("d_model").transform_id == "hidden_size"
    assert resolve_parameter_transform("dim_feedforward").label == "Hidden size"
    assert resolve_parameter_transform("d_model").runtime_validation_required
    assert resolve_parameter_transform("activation").transform_id == "activation"
    assert "batch_first" not in registered_parameter_names()
    assert resolve_parameter_transform("batch_first") is None
    assert "d_model" not in available_parameter_names(runtime_validation_available=False)
    assert "d_model" in available_parameter_names(runtime_validation_available=True)


def test_stage7_parameter_registry_rejects_invalid_value_domains() -> None:
    assert resolve_parameter_transform("num_heads").validate_values(8, 16) is None
    assert resolve_parameter_transform("num_heads").validate_values(8, 0) is not None
    assert resolve_parameter_transform("num_heads").validate_values(8, 16.0) is not None
    assert resolve_parameter_transform("dropout").validate_values(0.1, 0.2) is None
    assert resolve_parameter_transform("dropout").validate_values(0.1, 1.2) is not None
    assert resolve_parameter_transform("activation").validate_values("relu", "gelu") is None
    assert resolve_parameter_transform("activation").validate_values("relu", "") is not None
    assert resolve_parameter_transform("activation").validate_values("relu", "silu") is not None
