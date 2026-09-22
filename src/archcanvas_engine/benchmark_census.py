"""Build a complete, read-only L1 ledger for a Benchmark Model Reference catalog."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path

from archcanvas_pytorch.static import PyTorchModelCensus

from .benchmark_catalog import BenchmarkCatalogBuilder, BenchmarkCatalogRecord
from .benchmark_registry import BenchmarkEntrypointRegistry


@dataclass(frozen=True)
class BenchmarkCensusRecord:
    """One visible L0/L1 result for an index record.

    The optional PyTorch report remains relative to its explicitly approved project root. The
    wrapper records that root relative to the benchmark root, so no workstation path becomes
    part of the persisted protocol.
    """

    benchmark_id: str
    benchmark: str
    catalog_status: str
    l1_status: str
    language: str | None
    framework: str | None
    owner: str
    relative_source_root: str | None
    entrypoint_count: int
    status_counts: dict[str, int]
    unresolved_codes: list[str]
    source_files_unchanged: bool
    pytorch_census: dict[str, object] | None = None
    registry_revision: str | None = None
    registry_entrypoint_count: int = 0
    registry_unresolved_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BenchmarkCensusReport:
    """The generic L0/L1 report; it never serializes the approved absolute root."""

    index_revision: str
    records: list[BenchmarkCensusRecord]

    def as_dict(self) -> dict[str, object]:
        l1_counts = Counter(record.l1_status for record in self.records)
        return {
            "schema_version": "1.0",
            "report_kind": "benchmark-census-v1",
            "index_revision": self.index_revision,
            "approved_benchmark_root": ".",
            "execution": {
                "read_only": True,
                "source_imported": False,
                "source_executed": False,
                "dependencies_installed": False,
                "source_written": False,
            },
            "record_count": len(self.records),
            "l1_status_counts": dict(sorted(l1_counts.items())),
            "records": [asdict(record) for record in self.records],
        }


class BenchmarkCensusBuilder:
    """Connect the catalog to explicitly approved framework-specific L1 adapters.

    A project selection is deliberately an explicit ``benchmark_id -> relative root`` mapping.
    It prevents an index path or a benchmark name from implicitly authorizing a broader scan.
    """

    def __init__(self, catalog_builder: BenchmarkCatalogBuilder | None = None) -> None:
        self._catalog_builder = catalog_builder or BenchmarkCatalogBuilder()

    def build(
        self,
        approved_root: Path,
        *,
        pytorch_projects: Mapping[str, str] | None = None,
        pytorch_configs: Mapping[str, Mapping[str, Mapping[str, object]]] | None = None,
        pytorch_registries: Mapping[str, BenchmarkEntrypointRegistry] | None = None,
    ) -> BenchmarkCensusReport:
        root = approved_root.resolve(strict=True)
        catalog = self._catalog_builder.build(root)
        selected_projects = dict(pytorch_projects or {})
        selected_configs = dict(pytorch_configs or {})
        selected_registries = dict(pytorch_registries or {})
        known_ids = {record.benchmark_id for record in catalog.records}
        unknown_ids = sorted(set(selected_projects) - known_ids)
        if unknown_ids:
            raise ValueError(f"PyTorch project selections reference unknown benchmark ids: {unknown_ids}")
        unknown_config_ids = sorted(set(selected_configs) - known_ids)
        if unknown_config_ids:
            raise ValueError(f"PyTorch config selections reference unknown benchmark ids: {unknown_config_ids}")
        unknown_registry_ids = sorted(set(selected_registries) - known_ids)
        if unknown_registry_ids:
            raise ValueError(f"PyTorch registry selections reference unknown benchmark ids: {unknown_registry_ids}")

        records = [
            self._record(
                root,
                record,
                selected_project=selected_projects.get(record.benchmark_id),
                resolved_configs=selected_configs.get(record.benchmark_id, {}),
                registry=selected_registries.get(record.benchmark_id),
            )
            for record in catalog.records
        ]
        return BenchmarkCensusReport(index_revision=catalog.index_revision, records=records)

    @staticmethod
    def _record(
        root: Path,
        catalog_record: BenchmarkCatalogRecord,
        *,
        selected_project: str | None,
        resolved_configs: Mapping[str, Mapping[str, object]],
        registry: BenchmarkEntrypointRegistry | None,
    ) -> BenchmarkCensusRecord:
        if catalog_record.catalog_status == "no_local_model":
            return BenchmarkCensusRecord(
                benchmark_id=catalog_record.benchmark_id,
                benchmark=catalog_record.benchmark,
                catalog_status=catalog_record.catalog_status,
                l1_status="no_local_model",
                language=None,
                framework=None,
                owner="benchmark-catalog",
                relative_source_root=None,
                entrypoint_count=0,
                status_counts={},
                unresolved_codes=[],
                source_files_unchanged=True,
                registry_unresolved_codes=[],
            )
        if catalog_record.catalog_status != "ready_for_source_census":
            return BenchmarkCensusRecord(
                benchmark_id=catalog_record.benchmark_id,
                benchmark=catalog_record.benchmark,
                catalog_status=catalog_record.catalog_status,
                l1_status="blocked",
                language=None,
                framework=None,
                owner="benchmark-catalog",
                relative_source_root=None,
                entrypoint_count=0,
                status_counts={},
                unresolved_codes=["CATALOG_PATH_VALIDATION_FAILED", *catalog_record.issues],
                source_files_unchanged=True,
                registry_unresolved_codes=[],
            )
        if selected_project is None:
            return BenchmarkCensusRecord(
                benchmark_id=catalog_record.benchmark_id,
                benchmark=catalog_record.benchmark,
                catalog_status=catalog_record.catalog_status,
                l1_status="unsupported",
                language=None,
                framework=None,
                owner="archcanvas-benchmark-census",
                relative_source_root=None,
                entrypoint_count=0,
                status_counts={},
                unresolved_codes=["SOURCE_CENSUS_ADAPTER_NOT_APPROVED"],
                source_files_unchanged=True,
                registry_unresolved_codes=[],
            )

        project_root = (root / selected_project).resolve(strict=False)
        benchmark_root = (root / (catalog_record.relative_benchmark_path or ".")).resolve()
        if (
            not project_root.is_relative_to(root)
            or not project_root.is_relative_to(benchmark_root)
            or not project_root.is_dir()
        ):
            raise ValueError(
                "PyTorch project root for benchmark "
                f"{catalog_record.benchmark_id} must be a directory under its approved benchmark root"
            )
        relative_project_root = project_root.relative_to(root).as_posix()
        registry_issues = registry.validate_source_root(project_root) if registry is not None else []
        report = PyTorchModelCensus().build(
            project_root,
            project_id=f"benchmark:{catalog_record.benchmark_id}",
            resolved_configs=resolved_configs,
        ).as_dict()
        item_statuses = report["status_counts"]
        assert isinstance(item_statuses, dict)
        discovered = {
            str(item["entrypoint"])
            for item in report["items"]
            if isinstance(item, dict) and isinstance(item.get("entrypoint"), str)
        }
        if registry is not None:
            registry_issues.extend(
                f"{entry.entrypoint}:REGISTRY_ENTRYPOINT_NOT_DISCOVERED"
                for entry in registry.entries
                if entry.entrypoint not in discovered
            )
        overall_status = "supported"
        if any(status in item_statuses for status in ("blocked", "unresolved")):
            overall_status = "unresolved"
        if registry_issues:
            overall_status = "unresolved"
        return BenchmarkCensusRecord(
            benchmark_id=catalog_record.benchmark_id,
            benchmark=catalog_record.benchmark,
            catalog_status=catalog_record.catalog_status,
            l1_status=overall_status,
            language="python",
            framework="pytorch",
            owner="archcanvas-static-adapter",
            relative_source_root=relative_project_root,
            entrypoint_count=int(report["discovered_entrypoint_count"]),
            status_counts={str(key): int(value) for key, value in item_statuses.items()},
            unresolved_codes=[],
            source_files_unchanged=bool(report["execution"]["source_files_unchanged"]),
            pytorch_census=report,
            registry_revision=registry.registry_revision if registry is not None else None,
            registry_entrypoint_count=len(registry.entries) if registry is not None else 0,
            registry_unresolved_codes=sorted(set(registry_issues)),
        )
