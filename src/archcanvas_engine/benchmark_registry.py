"""Validate an explicit, source-relative benchmark entrypoint registry."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

from archcanvas_python.source_revision import file_revision

_DISCOVERY_BASES = {
    "static_nn_module",
    "registry_declaration",
    "config_reference",
    "recipe_reference",
    "manual_seed",
}


@dataclass(frozen=True)
class BenchmarkRegistryEntry:
    """One registry candidate, always relative to its selected project root."""

    relative_file: str
    symbol: str
    entrypoint_role: str
    discovery_basis: str
    source_anchor: dict[str, object] | None = None
    resolved_config: dict[str, object] | None = None

    @property
    def entrypoint(self) -> str:
        return f"{self.relative_file}:{self.symbol}"


@dataclass(frozen=True)
class BenchmarkEntrypointRegistry:
    """A versioned registry tied to one catalog record and one selected source root."""

    schema_version: str
    benchmark_id: str
    entries: list[BenchmarkRegistryEntry]
    registry_revision: str

    @classmethod
    def load(cls, path: Path, *, benchmark_id: str) -> BenchmarkEntrypointRegistry:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("entrypoint registry must be a JSON object")
        if payload.get("schema_version") != "1.0":
            raise ValueError("unsupported entrypoint registry schema version")
        if payload.get("benchmark_id") != benchmark_id:
            raise ValueError("entrypoint registry benchmark_id does not match selected record")
        raw_entries = payload.get("entries")
        if not isinstance(raw_entries, list):
            raise TypeError("entrypoint registry entries must be a list")
        entries = [cls._entry(value) for value in raw_entries]
        identifiers = [entry.entrypoint for entry in entries]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("entrypoint registry contains duplicate entries")
        return cls(
            schema_version="1.0",
            benchmark_id=benchmark_id,
            entries=entries,
            registry_revision=file_revision(raw),
        )

    @staticmethod
    def _entry(value: object) -> BenchmarkRegistryEntry:
        if not isinstance(value, dict):
            raise TypeError("entrypoint registry entry must be an object")
        relative_file = value.get("relative_file")
        symbol = value.get("symbol")
        role = value.get("entrypoint_role")
        basis = value.get("discovery_basis")
        if not all(isinstance(item, str) and item for item in (relative_file, symbol, role, basis)):
            raise ValueError("registry entries require relative_file, symbol, role and discovery_basis")
        relative = PurePosixPath(relative_file)
        if relative.is_absolute() or ".." in relative.parts or relative_file != relative.as_posix():
            raise ValueError("registry relative_file must be normalized and remain relative")
        if basis not in _DISCOVERY_BASES:
            raise ValueError(f"unsupported registry discovery_basis: {basis}")
        anchor = value.get("source_anchor")
        if anchor is not None and (
            not isinstance(anchor, dict)
            or not isinstance(anchor.get("line"), int)
            or anchor["line"] < 1
        ):
            raise ValueError("source_anchor must contain a positive line")
        config = value.get("resolved_config")
        if config is not None and not isinstance(config, dict):
            raise ValueError("resolved_config must be an object")
        return BenchmarkRegistryEntry(
            relative_file=relative_file,
            symbol=symbol,
            entrypoint_role=role,
            discovery_basis=basis,
            source_anchor=anchor,
            resolved_config=config,
        )

    def validate_source_root(self, source_root: Path) -> list[str]:
        """Return explicit registry issues without importing or executing source."""

        root = source_root.resolve(strict=True)
        issues: list[str] = []
        for entry in self.entries:
            path = (root / entry.relative_file).resolve(strict=False)
            if not path.is_relative_to(root):
                issues.append(f"{entry.entrypoint}:REGISTRY_PATH_OUTSIDE_ROOT")
            elif not path.is_file():
                issues.append(f"{entry.entrypoint}:REGISTRY_SOURCE_FILE_MISSING")
        return issues

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "benchmark_id": self.benchmark_id,
            "registry_revision": self.registry_revision,
            "entries": [asdict(entry) for entry in self.entries],
        }
