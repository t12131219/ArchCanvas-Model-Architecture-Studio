from __future__ import annotations

from pathlib import Path

import pytest

from archcanvas_core.schema_registry import SchemaRegistry, SchemaValidationError


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("schema", "document"),
    [
        ("architecture-ir-v1.schema.json", "expected/architecture.before.json"),
        ("patch-protocol-v1.schema.json", "request.patch.json"),
        ("source-identity-v1.schema.json", "expected/source-identity.before.json"),
    ],
)
def test_committed_fixture_documents_validate(schema: str, document: str, fixture_path: Path) -> None:
    registry = SchemaRegistry(ROOT / "schemas")
    registry.load_and_validate(schema, (fixture_path / document).read_bytes())


def test_schema_rejects_unknown_protocol_field(fixture_path: Path) -> None:
    raw = (fixture_path / "request.patch.json").read_text(encoding="utf-8")
    registry = SchemaRegistry(ROOT / "schemas")
    with pytest.raises(SchemaValidationError, match="Additional properties"):
        registry.load_and_validate(
            "patch-protocol-v1.schema.json",
            raw.replace('"schema_version":"1.0"', '"schema_version":"1.0","unexpected":true').encode(),
        )


def test_schema_loader_rejects_duplicate_keys() -> None:
    registry = SchemaRegistry(ROOT / "schemas")
    with pytest.raises(SchemaValidationError, match="duplicate JSON key"):
        registry.load_and_validate(
            "patch-protocol-v1.schema.json", b'{"schema_version":"1.0","schema_version":"1.0"}'
        )
