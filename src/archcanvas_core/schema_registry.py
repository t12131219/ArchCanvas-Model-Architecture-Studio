from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


class SchemaValidationError(ValueError):
    pass


def _reject_non_json_number(token: str) -> None:
    raise SchemaValidationError(f"non-JSON numeric token: {token}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SchemaValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


class SchemaRegistry:
    """The sole loader for committed protocol schemas."""

    def __init__(self, schema_dir: Path) -> None:
        self._schemas = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(schema_dir.glob("*.schema.json"))
        }
        for schema in self._schemas.values():
            Draft202012Validator.check_schema(schema)

    def validate(self, name: str, document: dict[str, Any]) -> None:
        try:
            schema = self._schemas[name]
        except KeyError as error:
            raise SchemaValidationError(f"unknown schema: {name}") from error
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path))
        if errors:
            lines = []
            for error in errors:
                pointer = "/" + "/".join(str(part) for part in error.absolute_path)
                lines.append(f"{pointer}: {error.message}")
            raise SchemaValidationError("\n".join(lines))

    def load_and_validate(self, name: str, raw: bytes) -> dict[str, Any]:
        document = json.loads(
            raw.decode("utf-8"),
            parse_constant=_reject_non_json_number,
            object_pairs_hook=_reject_duplicate_keys,
        )
        if not isinstance(document, dict):
            raise SchemaValidationError("top-level JSON value must be an object")
        self.validate(name, document)
        return document
