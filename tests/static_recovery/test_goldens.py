from __future__ import annotations

import json
from pathlib import Path

import pytest

from archcanvas_core.models.architecture import ArchitectureIR
from archcanvas_core.models.source_identity import SourceIdentityDocument
from archcanvas_core.semantic_validation import validate_architecture_semantics
from archcanvas_pytorch.static import PyTorchStaticAdapter

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("fixture_name", "project_id", "entrypoint"),
    [
        ("transformer_static_v1", "fixture:transformer_static_v1", "model.py:EncoderModel"),
        ("resnet_static_v1", "fixture:resnet_static_v1", "model.py:ResidualBlock"),
    ],
)
def test_static_fixture_goldens_are_exact_and_semantically_valid(
    fixture_name: str, project_id: str, entrypoint: str
) -> None:
    root = ROOT / "fixtures" / fixture_name
    source, ir = PyTorchStaticAdapter().analyze(
        (root / "source" / "model.py").read_bytes(),
        project_id=project_id,
        relative_file="model.py",
        entrypoint=entrypoint,
    )
    expected_source = SourceIdentityDocument.model_validate_json(
        (root / "expected" / "source-identity.json").read_bytes()
    )
    expected_ir = ArchitectureIR.model_validate_json(
        (root / "expected" / "architecture.json").read_bytes()
    )
    assert source == expected_source
    assert ir == expected_ir
    assert validate_architecture_semantics(ir, source) == []


def test_static_goldens_are_canonical_json_documents() -> None:
    for path in ROOT.glob("fixtures/*_static_v1/expected/*.json"):
        assert path.read_bytes().endswith(b"\n")
        assert json.loads(path.read_text(encoding="utf-8"))
