from __future__ import annotations

import pytest

from archcanvas_core.models.architecture import ParameterOriginKind
from archcanvas_python.transforms.set_parameter import TransformRejected, apply_set_parameter


def test_transform_matches_after_oracle(before_raw, before_ir, patch_set, source_document, fixture_path) -> None:
    result = apply_set_parameter(
        before_raw,
        patch_set.patches[0],
        source_document.anchors[0],
        before_ir.parameter("node:encoder.layers", "num_heads"),
        patch_set.base_source_revision,
    )
    assert result.output_bytes == (fixture_path / "source" / "after" / "model.py").read_bytes()
    assert result.changed_calls == result.changed_arguments == 1
    assert b"# edited by the v1 fixture" in result.output_bytes


def test_transform_rejects_stale_source_revision(before_raw, before_ir, patch_set, source_document) -> None:
    with pytest.raises(TransformRejected, match="STALE_TARGET_FILE_REVISION"):
        apply_set_parameter(
            before_raw + b"\n# concurrent change\n",
            patch_set.patches[0],
            source_document.anchors[0],
            before_ir.parameter("node:encoder.layers", "num_heads"),
            patch_set.base_source_revision,
        )


def test_transform_rejects_non_literal_parameter(before_raw, before_ir, patch_set, source_document) -> None:
    parameter = before_ir.parameter("node:encoder.layers", "num_heads")
    non_literal = parameter.model_copy(
        update={"origin": parameter.origin.model_copy(update={"kind": ParameterOriginKind.COMPUTED})}
    )
    with pytest.raises(TransformRejected, match="NON_LITERAL_ORIGIN"):
        apply_set_parameter(
            before_raw,
            patch_set.patches[0],
            source_document.anchors[0],
            non_literal,
            patch_set.base_source_revision,
        )
