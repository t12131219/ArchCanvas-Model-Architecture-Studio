from __future__ import annotations

from pathlib import Path

import pytest

from archcanvas_core.models.architecture import ArchitectureIR
from archcanvas_core.models.patch import PatchSet
from archcanvas_core.models.source_identity import SourceIdentityDocument


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "transformer_set_parameter_v1"


@pytest.fixture
def fixture_path() -> Path:
    return FIXTURE


@pytest.fixture
def before_raw(fixture_path: Path) -> bytes:
    return (fixture_path / "source" / "before" / "model.py").read_bytes()


@pytest.fixture
def source_document(fixture_path: Path) -> SourceIdentityDocument:
    return SourceIdentityDocument.model_validate_json(
        (fixture_path / "expected" / "source-identity.before.json").read_bytes()
    )


@pytest.fixture
def before_ir(fixture_path: Path) -> ArchitectureIR:
    return ArchitectureIR.model_validate_json(
        (fixture_path / "expected" / "architecture.before.json").read_bytes()
    )


@pytest.fixture
def patch_set(fixture_path: Path) -> PatchSet:
    return PatchSet.model_validate_json((fixture_path / "request.patch.json").read_bytes())
