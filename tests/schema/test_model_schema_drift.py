from __future__ import annotations

import json
from pathlib import Path

import pytest

from archcanvas_core.models.architecture import ArchitectureIR
from archcanvas_core.models.patch import PatchSet
from archcanvas_core.models.publication import PublicationIR, VisualScene
from archcanvas_core.models.runtime import RuntimeTraceResult, TraceRequest
from archcanvas_core.models.source_identity import SourceIdentityDocument

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("filename", "model"),
    [
        ("architecture-ir-v1.schema.json", ArchitectureIR),
        ("patch-protocol-v1.schema.json", PatchSet),
        ("source-identity-v1.schema.json", SourceIdentityDocument),
        ("runtime-trace-request-v1.schema.json", TraceRequest),
        ("runtime-trace-result-v1.schema.json", RuntimeTraceResult),
        ("publication-ir-v1.schema.json", PublicationIR),
        ("visual-scene-v1.schema.json", VisualScene),
    ],
)
def test_committed_schema_matches_validation_model(filename, model) -> None:
    committed = json.loads((ROOT / "schemas" / filename).read_text(encoding="utf-8"))
    assert committed.pop("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert committed.pop("$id") == f"https://archcanvas.dev/schemas/{filename}"
    assert committed == model.model_json_schema(mode="validation")
