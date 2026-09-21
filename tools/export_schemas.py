"""Regenerate committed protocol schemas after a deliberate model change."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from archcanvas_core.models.architecture import ArchitectureIR
from archcanvas_core.models.patch import PatchSet
from archcanvas_core.models.publication import PublicationIR, VisualScene
from archcanvas_core.models.runtime import RuntimeTraceResult, TraceRequest
from archcanvas_core.models.source_identity import SourceIdentityDocument

SCHEMAS: tuple[tuple[str, type[BaseModel]], ...] = (
    ("architecture-ir-v1.schema.json", ArchitectureIR),
    ("patch-protocol-v1.schema.json", PatchSet),
    ("source-identity-v1.schema.json", SourceIdentityDocument),
    ("runtime-trace-request-v1.schema.json", TraceRequest),
    ("runtime-trace-result-v1.schema.json", RuntimeTraceResult),
    ("publication-ir-v1.schema.json", PublicationIR),
    ("visual-scene-v1.schema.json", VisualScene),
)


def main() -> None:
    schema_dir = Path(__file__).resolve().parents[1] / "schemas"
    schema_dir.mkdir(exist_ok=True)
    for filename, model in SCHEMAS:
        schema = model.model_json_schema(mode="validation")
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"https://archcanvas.dev/schemas/{filename}"
        (schema_dir / filename).write_text(
            json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
