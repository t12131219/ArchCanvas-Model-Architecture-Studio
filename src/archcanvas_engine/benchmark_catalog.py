"""Read a user-approved Benchmark Model Reference index without touching source code."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from archcanvas_core.models.common import sha256_digest

_RECORD_HEADING = re.compile(r"^## (?P<identifier>\d{2}) - (?P<title>.+)$", re.MULTILINE)
_FIELD = re.compile(r"^- `(?P<name>[a-z_]+)`: (?P<value>.+)$", re.MULTILINE)
_PATH_FIELDS = ("benchmark_path", "model_path", "config_path", "model_family_paths")


@dataclass(frozen=True)
class BenchmarkCatalogRecord:
    """One index record normalized to the approved root."""

    benchmark_id: str
    benchmark: str
    status: str
    relative_benchmark_path: str | None
    relative_model_paths: list[str]
    relative_config_paths: list[str]
    representative_models: list[str]
    notes: str | None
    catalog_status: str
    issues: list[str]
    source_files_unchanged: bool


@dataclass(frozen=True)
class BenchmarkCatalogReport:
    """L0 catalog output. All paths are relative; the approved root is never serialized."""

    index_revision: str
    records: list[BenchmarkCatalogRecord]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "report_kind": "benchmark-catalog-v1",
            "index_revision": self.index_revision,
            "approved_benchmark_root": ".",
            "record_count": len(self.records),
            "records": [asdict(record) for record in self.records],
        }


class BenchmarkCatalogBuilder:
    """Build the L0 benchmark catalog from a single approved index file."""

    index_name = "BENCHMARK_MODEL_INDEX.md"

    def build(self, approved_root: Path) -> BenchmarkCatalogReport:
        root = approved_root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("approved benchmark root must be a directory")
        index_path = root / self.index_name
        raw_index = index_path.read_bytes()
        text = raw_index.decode("utf-8")
        records = self._parse_records(text, root)
        if not records:
            raise ValueError("benchmark index contains no records")
        return BenchmarkCatalogReport(
            index_revision=sha256_digest(raw_index),
            records=records,
        )

    @classmethod
    def _parse_records(cls, text: str, root: Path) -> list[BenchmarkCatalogRecord]:
        headings = list(_RECORD_HEADING.finditer(text))
        records: list[BenchmarkCatalogRecord] = []
        for index, heading in enumerate(headings):
            body = text[heading.end() : headings[index + 1].start() if index + 1 < len(headings) else len(text)]
            fields = {
                match.group("name"): cls._field_value(match.group("value"))
                for match in _FIELD.finditer(body)
            }
            records.append(cls._record(heading.group("identifier"), fields, root))
        return records

    @staticmethod
    def _field_value(raw: str) -> str | None:
        values = re.findall(r"`([^`]*)`", raw)
        return ";".join(values) if values else raw.strip()

    @classmethod
    def _record(
        cls,
        benchmark_id: str,
        fields: dict[str, str | None],
        root: Path,
    ) -> BenchmarkCatalogRecord:
        issues: list[str] = []
        status = fields.get("status") or "invalid"
        benchmark = fields.get("benchmark") or f"index record {benchmark_id}"
        if status not in {"local_model", "benchmark_only"}:
            issues.append("INVALID_STATUS")
        normalized: dict[str, list[str]] = {}
        for field in _PATH_FIELDS:
            normalized[field] = cls._paths(fields.get(field), root, issues, field)
        relative_benchmark_path = (
            normalized["benchmark_path"][0] if len(normalized["benchmark_path"]) == 1 else None
        )
        if not normalized["benchmark_path"]:
            issues.append("MISSING_BENCHMARK_PATH")
        if status == "benchmark_only" or fields.get("model_path") in {None, "null"}:
            catalog_status = "no_local_model" if not issues else "blocked"
        elif not normalized["model_path"]:
            catalog_status = "blocked"
            issues.append("MISSING_MODEL_PATH")
        else:
            catalog_status = "ready_for_source_census" if not issues else "blocked"
        return BenchmarkCatalogRecord(
            benchmark_id=benchmark_id,
            benchmark=benchmark,
            status=status,
            relative_benchmark_path=relative_benchmark_path,
            relative_model_paths=normalized["model_path"],
            relative_config_paths=[
                *normalized["config_path"],
                *normalized["model_family_paths"],
            ],
            representative_models=cls._values(fields.get("representative_models")),
            notes=fields.get("notes"),
            catalog_status=catalog_status,
            issues=sorted(set(issues)),
            # Catalog parsing reads index/path metadata only, never benchmark source code.
            source_files_unchanged=True,
        )

    @staticmethod
    def _values(raw_value: str | None) -> list[str]:
        if raw_value in {None, "null"}:
            return []
        return [value for value in raw_value.split(";") if value]

    @staticmethod
    def _paths(
        raw_value: str | None,
        root: Path,
        issues: list[str],
        field: str,
    ) -> list[str]:
        if raw_value in {None, "null"}:
            return []
        paths: list[str] = []
        for raw_path in raw_value.split(";"):
            candidate = Path(raw_path)
            resolved = candidate.resolve(strict=False) if candidate.is_absolute() else (root / candidate).resolve(strict=False)
            if not resolved.is_relative_to(root):
                issues.append(f"{field.upper()}_OUTSIDE_APPROVED_ROOT")
                continue
            relative = resolved.relative_to(root).as_posix()
            if not resolved.exists():
                issues.append(f"{field.upper()}_MISSING")
                continue
            paths.append(relative)
        return sorted(set(paths))
