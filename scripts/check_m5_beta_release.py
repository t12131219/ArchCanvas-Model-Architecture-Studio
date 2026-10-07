#!/usr/bin/env python3
"""Validate the conservative M5 beta release scaffold and its build hashes.

This checker deliberately validates release metadata only. It does not claim
that a host E2E run, human study, publication review, or model execution has
occurred. The manifest must point at the formal project tree and may not use
the failed prototype as a runtime or artifact source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


HOSTS = {"codex", "claude-code", "deepseek-harness"}
E2E = {"not-tested", "smoke-tested", "passed", "failed"}


def validate_schema(value: object, schema: dict, path: str = "$manifest") -> list[str]:
    """Apply the finite JSON Schema vocabulary used by the release schema."""
    errors: list[str] = []
    if not isinstance(schema, dict):
        return [f"{path}: unsupported schema structure"]
    expected_type = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "integer": int}
    if expected_type is not None and (not isinstance(expected_type, str) or expected_type not in types):
        return [f"{path}: unsupported schema type"]
    if "enum" in schema and not isinstance(schema["enum"], list):
        return [f"{path}: invalid schema enum"]
    if "pattern" in schema and not isinstance(schema["pattern"], str):
        return [f"{path}: invalid schema pattern"]
    if "properties" in schema and not isinstance(schema["properties"], dict):
        return [f"{path}: invalid schema properties"]
    if "required" in schema and (not isinstance(schema["required"], list) or not all(isinstance(name, str) for name in schema["required"])):
        return [f"{path}: invalid schema required fields"]
    if "minItems" in schema and (type(schema["minItems"]) is not int or schema["minItems"] < 0):
        return [f"{path}: invalid schema item limit"]
    if expected_type in types and (not isinstance(value, types[expected_type]) or
                                  expected_type == "integer" and isinstance(value, bool)):
        return [f"{path}: expected {expected_type}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: not in allowed enum")
    if isinstance(value, str) and "pattern" in schema:
        try:
            if not re.search(schema["pattern"], value):
                errors.append(f"{path}: pattern mismatch")
        except re.error:
            errors.append(f"{path}: invalid schema regular expression")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path}.{name}: required")
        if schema.get("additionalProperties") is False:
            for name in value.keys() - properties.keys():
                errors.append(f"{path}.{name}: unknown field")
        for name, item in value.items():
            if name in properties:
                errors.extend(validate_schema(item, properties[name], f"{path}.{name}"))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: too few items")
        for index, item in enumerate(value):
            errors.extend(validate_schema(item, schema.get("items", {}), f"{path}[{index}]"))
    return errors


def _error(errors: list[str], message: str) -> None:
    errors.append(message)


def validate(manifest: dict, project_root: Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest must be an object"]
    schema_path = project_root / "schemas/m5-beta-release.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"release schema unavailable: {exc}"]
    schema_errors = validate_schema(manifest, schema)
    if schema_errors:
        return schema_errors
    required = {
        "schemaVersion", "releaseId", "releaseVersion", "stage", "status",
        "generatedAt", "build", "artifacts", "hostMatrix", "knownLimitations", "gates",
    }
    missing = sorted(required - manifest.keys())
    if missing:
        _error(errors, f"missing top-level fields: {', '.join(missing)}")
        return errors
    unknown = sorted(manifest.keys() - required)
    if unknown:
        _error(errors, f"unknown top-level fields: {', '.join(unknown)}")
    if manifest["schemaVersion"] != 1:
        _error(errors, "schemaVersion must be 1")
    if manifest["stage"] != "M5-beta":
        _error(errors, "stage must be M5-beta")
    if manifest["status"] not in {"in_progress", "ready_for_review", "released"}:
        _error(errors, "status is not a supported M5 state")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-beta\.[0-9]+", str(manifest["releaseVersion"])):
        _error(errors, "releaseVersion must be semantic beta form, e.g. 0.1.0-beta.1")
    if not re.fullmatch(r"archcanvas-m5-beta-[a-z0-9][a-z0-9.-]*", str(manifest["releaseId"])):
        _error(errors, "releaseId must use the archcanvas-m5-beta- prefix")
    if manifest["releaseId"] != f"archcanvas-m5-beta-{manifest['releaseVersion']}":
        _error(errors, "releaseId must match releaseVersion")

    build = manifest["build"]
    if not isinstance(build, dict):
        _error(errors, "build must be an object")
        return errors
    if build.get("runtimeSource") != "formal-project":
        _error(errors, "build.runtimeSource must be formal-project")
    if build.get("prototypeDependency") not in (None, "forbidden"):
        _error(errors, "prototypeDependency must be forbidden when present")
    commit = str(build.get("gitCommit", ""))
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        _error(errors, "build.gitCommit must be a 40-character lowercase SHA")

    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        _error(errors, "artifacts must be a non-empty list")
    else:
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                _error(errors, "artifact must be an object")
                continue
            path_text = str(artifact.get("path", ""))
            if Path(path_text).is_absolute() or ".." in Path(path_text).parts:
                _error(errors, f"artifact path must stay inside project: {path_text}")
                continue
            path = project_root / path_text
            if not path.resolve().is_relative_to(project_root.resolve()):
                _error(errors, f"artifact resolves outside formal project: {path_text}")
                continue
            if not path.is_file():
                _error(errors, f"artifact missing: {path_text}")
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != artifact.get("sha256"):
                _error(errors, f"artifact hash mismatch: {path_text}")
            if "ArchCanvas_Model Architecture Studio_Temp" in str(path.resolve()):
                _error(errors, f"prototype artifact path forbidden: {path_text}")

    rows = manifest["hostMatrix"]
    if not isinstance(rows, list):
        _error(errors, "hostMatrix must be a list")
    else:
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                _error(errors, "host row must be an object")
                continue
            host = row.get("host")
            if host in seen:
                _error(errors, f"duplicate host row: {host}")
            seen.add(host)
            if host not in HOSTS:
                _error(errors, f"unknown host: {host}")
            if row.get("contractStatus") not in {"contract-reviewed", "unreviewed"}:
                _error(errors, f"invalid contract status for {host}")
            if row.get("e2e") not in E2E:
                _error(errors, f"invalid e2e state for {host}")
            if row.get("e2e") != "not-tested":
                _error(errors, f"M5 scaffold cannot certify host E2E: {host}")
            if not row.get("discovery"):
                _error(errors, f"missing discovery paths for {host}")
        if seen != HOSTS:
            _error(errors, f"host matrix must contain exactly {sorted(HOSTS)}")

    gates = manifest["gates"]
    if not isinstance(gates, dict):
        _error(errors, "gates must be an object")
        return errors
    if gates.get("m4") != "partial":
        _error(errors, "M4 gate must remain partial in the M5 scaffold")
    if gates.get("m5") != "in_progress":
        _error(errors, "M5 gate must be in_progress in the M5 scaffold")
    if not isinstance(manifest["knownLimitations"], list) or not manifest["knownLimitations"]:
        _error(errors, "knownLimitations must be non-empty")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("docs/evidence/m5-beta-release-manifest.json"))
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 2
    errors = validate(manifest, args.project_root.resolve())
    result = {"status": "passed" if not errors else "failed", "manifest": str(args.manifest), "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
