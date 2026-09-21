"""Read-only, complete accounting for every statically discovered PyTorch entrypoint."""

from __future__ import annotations

import ast
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from archcanvas_core.models.architecture import ArchitectureIR
from archcanvas_core.models.common import sha256_digest
from archcanvas_core.semantic_validation import validate_architecture_semantics
from archcanvas_publication import PublicationCompiler, StageLayout
from archcanvas_python.source_revision import file_revision
from archcanvas_renderer import publication_preflight, render_svg

from ..capabilities import static_capability_report
from .project import ProjectScanIssue, PyTorchProjectScanner
from .project_adapter import PyTorchProjectStaticAdapter

_SKIPPED_DIRECTORIES = {".git", ".venv", "__pycache__", "build", "dist", "node_modules"}


@dataclass(frozen=True)
class ModelCensusItem:
    entrypoint: str
    discovery_source: str
    entrypoint_role: str
    owner: str
    status: str
    publication_status: str
    resolved_config: dict[str, object]
    source_revision: str | None
    file_revisions: dict[str, str]
    node_count: int
    edge_count: int
    unresolved_codes: list[str]
    error: str | None
    source_files_unchanged: bool
    publication_error: str | None = None
    publication_node_count: int = 0
    publication_edge_count: int = 0
    publication_svg_sha256: str | None = None


@dataclass(frozen=True)
class RegistryAlias:
    registry_export: str
    target_entrypoint: str


@dataclass(frozen=True)
class PublicationCensusAssessment:
    status: str
    error: str | None = None
    node_count: int = 0
    edge_count: int = 0
    svg_sha256: str | None = None


@dataclass(frozen=True)
class PyTorchModelCensusReport:
    python_files_scanned: int
    scan_issues: list[ProjectScanIssue]
    items: list[ModelCensusItem]
    explicit_aliases: list[RegistryAlias]
    source_files_unchanged: bool
    source_files_observed_count: int

    def as_dict(self) -> dict[str, object]:
        counts = Counter(item.status for item in self.items)
        return {
            "report_kind": "pytorch-model-census-v1",
            "approved_root": ".",
            "execution": {
                "read_only": True,
                "source_imported": False,
                "source_executed": False,
                "dependencies_installed": False,
                "source_written": False,
                "source_files_unchanged": self.source_files_unchanged,
                "source_files_observed_count": self.source_files_observed_count,
            },
            "capability_report": static_capability_report().as_dict(),
            "python_files_scanned": self.python_files_scanned,
            "scan_issues": [asdict(item) for item in self.scan_issues],
            "discovered_entrypoint_count": len(self.items) + len(self.explicit_aliases),
            "assessed_entrypoint_count": len(self.items),
            "explicit_alias_count": len(self.explicit_aliases),
            "explicit_aliases": [asdict(item) for item in self.explicit_aliases],
            "status_counts": dict(sorted(counts.items())),
            "entrypoint_role_counts": dict(
                sorted(Counter(item.entrypoint_role for item in self.items).items())
            ),
            "items": [asdict(item) for item in self.items],
        }


class PyTorchModelCensus:
    """Analyze every discovered ``nn.Module`` class without omitting unsupported cases."""

    def __init__(
        self,
        scanner: PyTorchProjectScanner | None = None,
        adapter: PyTorchProjectStaticAdapter | None = None,
    ) -> None:
        self._scanner = scanner or PyTorchProjectScanner()
        self._adapter = adapter or PyTorchProjectStaticAdapter(project_scanner=self._scanner)

    def build(
        self,
        root: Path,
        *,
        project_id: str,
        resolved_configs: Mapping[str, Mapping[str, object]] | None = None,
        assess_publication: bool = False,
        publication_artifact_root: Path | None = None,
    ) -> PyTorchModelCensusReport:
        """Return one final record for every static entrypoint under an approved root."""

        resolved_root = root.resolve(strict=True)
        artifact_root = self._publication_artifact_root(resolved_root, publication_artifact_root)
        if artifact_root is not None and not assess_publication:
            raise ValueError("publication artifact output requires publication assessment")
        before_revisions = self._source_revisions(resolved_root)
        scan = self._scanner.scan(resolved_root)
        symbols = self._scanner.build_symbol_table(resolved_root)
        configs = resolved_configs or {}
        items: list[ModelCensusItem] = []
        for discovery in scan.entrypoints:
            entrypoint = f"{discovery.relative_file}:{discovery.model_class}"
            config = dict(configs.get(entrypoint, {}))
            role = self._entrypoint_role(discovery.relative_file)
            try:
                source, ir = self._adapter.analyze_with_symbol_table(
                    resolved_root,
                    symbols=symbols,
                    project_id=project_id,
                    entrypoint=entrypoint,
                    resolved_config=config,
                )
                semantic_issues = validate_architecture_semantics(ir, source)
                if semantic_issues:
                    items.append(
                        ModelCensusItem(
                            entrypoint=entrypoint,
                            discovery_source="static_nn_module",
                            entrypoint_role=role,
                            owner="archcanvas-static-adapter",
                            status="blocked",
                            publication_status="publication_not_assessed",
                            resolved_config=config,
                            source_revision=source.source_revision,
                            file_revisions=source.file_revisions,
                            node_count=len(ir.nodes),
                            edge_count=len(ir.edges),
                            unresolved_codes=sorted({item.code for item in ir.unresolved}),
                            error="; ".join(semantic_issues),
                            source_files_unchanged=False,
                        )
                    )
                    continue
                unresolved_codes = sorted({item.code for item in ir.unresolved})
                status = "supported" if not unresolved_codes else "unresolved"
                publication_status = "publication_not_assessed"
                publication_error: str | None = None
                publication_node_count = 0
                publication_edge_count = 0
                publication_svg_sha256: str | None = None
                owner = "archcanvas-static-adapter"
                publication_eligible = self._publication_eligible(unresolved_codes)
                if assess_publication and publication_eligible:
                    assessment = self._assess_publication(
                        entrypoint=entrypoint,
                        architecture=ir,
                        artifact_root=artifact_root,
                    )
                    publication_status = (
                        "publication_svg_ready_with_unresolved_parameter_provenance"
                        if assessment.status == "publication_svg_ready" and unresolved_codes
                        else assessment.status
                    )
                    publication_error = assessment.error
                    publication_node_count = assessment.node_count
                    publication_edge_count = assessment.edge_count
                    publication_svg_sha256 = assessment.svg_sha256
                    if assessment.error is not None:
                        status = "unresolved"
                        owner = "archcanvas-publication-compiler"
                        unresolved_codes = sorted(
                            {*unresolved_codes, "PUBLICATION_COMPILATION_OR_PREFLIGHT_FAILED"}
                        )
                items.append(
                    ModelCensusItem(
                        entrypoint=entrypoint,
                        discovery_source="static_nn_module",
                        entrypoint_role=role,
                        owner=owner,
                        status=status,
                        publication_status=publication_status,
                        resolved_config=config,
                        source_revision=source.source_revision,
                        file_revisions=source.file_revisions,
                        node_count=len(ir.nodes),
                        edge_count=len(ir.edges),
                        unresolved_codes=unresolved_codes,
                        error=publication_error,
                        source_files_unchanged=False,
                        publication_error=publication_error,
                        publication_node_count=publication_node_count,
                        publication_edge_count=publication_edge_count,
                        publication_svg_sha256=publication_svg_sha256,
                    )
                )
            except (OSError, SyntaxError, UnicodeDecodeError, ValueError) as error:
                items.append(
                    ModelCensusItem(
                        entrypoint=entrypoint,
                        discovery_source="static_nn_module",
                        entrypoint_role=role,
                        owner="archcanvas-static-adapter",
                        status="blocked",
                        publication_status="publication_not_assessed",
                        resolved_config=config,
                        source_revision=None,
                        file_revisions={},
                        node_count=0,
                        edge_count=0,
                        unresolved_codes=[],
                        error=str(error),
                        source_files_unchanged=False,
                    )
                )
        registry_items, aliases = self._registry_items(
            resolved_root,
            discovered={item.entrypoint for item in items},
        )
        items.extend(registry_items)
        after_revisions = self._source_revisions(resolved_root)
        source_files_unchanged = before_revisions == after_revisions
        return PyTorchModelCensusReport(
            python_files_scanned=scan.python_files_scanned,
            scan_issues=scan.issues,
            items=[replace(item, source_files_unchanged=source_files_unchanged) for item in items],
            explicit_aliases=aliases,
            source_files_unchanged=source_files_unchanged,
            source_files_observed_count=len(before_revisions),
        )

    @staticmethod
    def _publication_eligible(unresolved_codes: list[str]) -> bool:
        """Permit SVG preflight only when remaining facts cannot change confirmed topology."""

        return not unresolved_codes or set(unresolved_codes) <= {
            "UNRESOLVED_PARAMETER_PROVENANCE"
        }

    @staticmethod
    def _publication_artifact_root(root: Path, artifact_root: Path | None) -> Path | None:
        if artifact_root is None:
            return None
        resolved = artifact_root.resolve()
        if resolved.is_relative_to(root):
            raise ValueError("publication artifact output must not be written under the inspected project root")
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    @staticmethod
    def _document_bytes(document: object) -> bytes:
        payload = document.model_dump(mode="json")  # type: ignore[attr-defined]
        return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")

    @classmethod
    def _assess_publication(
        cls,
        *,
        entrypoint: str,
        architecture: ArchitectureIR,
        artifact_root: Path | None,
    ) -> PublicationCensusAssessment:
        """Compile only confirmed Exact IR into reviewable, external D5 evidence files."""

        try:
            publication = PublicationCompiler().compile(architecture)
            layout = StageLayout()
            overview = layout.layout(publication)
            repeat_ids = {
                node.node_id for node in publication.nodes if node.kind.value == "repeat_group"
            }
            detail = layout.layout(publication, expanded_node_ids=repeat_ids)
            overview_svg = render_svg(publication, overview)
            detail_svg = render_svg(publication, detail)
            overview_report = publication_preflight(publication, overview, overview_svg)
            detail_report = publication_preflight(publication, detail, detail_svg)
            if overview_report.blocking or detail_report.blocking:
                errors = [
                    *(issue.code for issue in overview_report.issues),
                    *(issue.code for issue in detail_report.issues),
                ]
                return PublicationCensusAssessment(
                    status="publication_preflight_blocked",
                    error="; ".join(sorted(set(errors))) or "publication preflight blocked",
                )
            svg_sha256 = sha256_digest(overview_svg.encode("utf-8"))
            if artifact_root is not None:
                cls._write_publication_artifacts(
                    artifact_root,
                    entrypoint=entrypoint,
                    publication=publication,
                    overview=overview,
                    detail=detail,
                    overview_svg=overview_svg,
                    detail_svg=detail_svg,
                    svg_sha256=svg_sha256,
                )
            return PublicationCensusAssessment(
                status="publication_svg_ready",
                node_count=len(publication.nodes),
                edge_count=len(publication.edges),
                svg_sha256=svg_sha256,
            )
        except (TypeError, ValueError) as error:
            return PublicationCensusAssessment(
                status="publication_compilation_failed",
                error=str(error),
            )

    @classmethod
    def _write_publication_artifacts(
        cls,
        artifact_root: Path,
        *,
        entrypoint: str,
        publication: object,
        overview: object,
        detail: object,
        overview_svg: str,
        detail_svg: str,
        svg_sha256: str,
    ) -> None:
        token = sha256_digest(entrypoint.encode("utf-8")).removeprefix("sha256:")
        destination = artifact_root / token
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "publication.json").write_bytes(cls._document_bytes(publication))
        (destination / "scene-overview.json").write_bytes(cls._document_bytes(overview))
        (destination / "scene-detail.json").write_bytes(cls._document_bytes(detail))
        (destination / "overview.svg").write_text(overview_svg, encoding="utf-8")
        (destination / "detail.svg").write_text(detail_svg, encoding="utf-8")
        checklist = {
            "entrypoint": entrypoint,
            "overview_svg_sha256": svg_sha256,
            "machine_preflight": "passed",
            "manual_review": "pending",
            "manual_review_requirements": [
                "Verify the primary data flow is understandable without source paths.",
                "Verify every displayed scientific miniature has the intended disclosure.",
                "Verify each publication primitive reaches its Exact member/source evidence.",
            ],
        }
        (destination / "publication-checklist.json").write_text(
            json.dumps(checklist, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _source_revisions(root: Path) -> dict[str, str]:
        """Snapshot only approved Python files to prove the corpus scan did not write source."""

        revisions: dict[str, str] = {}
        for path in sorted(root.rglob("*.py")):
            relative_path = path.relative_to(root)
            if any(part in _SKIPPED_DIRECTORIES for part in relative_path.parts):
                continue
            if path.is_symlink() and not path.resolve().is_relative_to(root):
                continue
            revisions[relative_path.as_posix()] = file_revision(path.read_bytes())
        return revisions

    @staticmethod
    def _registry_items(
        root: Path, *, discovered: set[str]
    ) -> tuple[list[ModelCensusItem], list[RegistryAlias]]:
        """Account for benchmark registry exports without importing benchmark packages."""

        items: list[ModelCensusItem] = []
        aliases: list[RegistryAlias] = []
        baseline_root = root / "baselines"
        if not baseline_root.is_dir():
            return items, aliases
        for init_path in sorted(baseline_root.glob("*/__init__.py")):
            relative_file = init_path.relative_to(root).as_posix()
            raw_source = init_path.read_bytes()
            try:
                tree = ast.parse(raw_source.decode("utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            exports = PyTorchModelCensus._literal_all(tree)
            imports = PyTorchModelCensus._registry_imports(root, init_path, tree)
            revision = file_revision(raw_source)
            for export in exports:
                registry_export = f"registry:{relative_file}:{export}"
                target = imports.get(export)
                if target in discovered:
                    aliases.append(RegistryAlias(registry_export, target))
                    continue
                file_revisions = {relative_file: revision}
                if target is not None:
                    target_relative_file = target.split(":", maxsplit=1)[0]
                    target_path = root / target_relative_file
                    if target_path.is_file():
                        file_revisions[target_relative_file] = file_revision(target_path.read_bytes())
                items.append(
                    ModelCensusItem(
                        entrypoint=registry_export,
                        discovery_source="static_baseline_registry",
                        entrypoint_role="registered_model",
                        owner="archcanvas-static-adapter",
                        status="unsupported",
                        publication_status="publication_not_assessed",
                        resolved_config={},
                        source_revision=revision,
                        file_revisions=file_revisions,
                        node_count=0,
                        edge_count=0,
                        unresolved_codes=["REGISTRY_EXPORT_NOT_STATIC_PYTORCH_ENTRYPOINT"],
                        error=(
                            "registry export has no local static nn.Module target"
                            if target is None
                            else f"registry export resolves to non-nn.Module target {target}"
                        ),
                        source_files_unchanged=False,
                    )
                )
        return items, aliases

    @staticmethod
    def _literal_all(tree: ast.Module) -> list[str]:
        for statement in tree.body:
            if not (
                isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
                and statement.targets[0].id == "__all__"
                and isinstance(statement.value, (ast.List, ast.Tuple))
            ):
                continue
            values = [item.value for item in statement.value.elts if isinstance(item, ast.Constant)]
            if len(values) == len(statement.value.elts) and all(isinstance(item, str) for item in values):
                return sorted(values)
        return []

    @staticmethod
    def _registry_imports(root: Path, init_path: Path, tree: ast.Module) -> dict[str, str]:
        imports: dict[str, str] = {}
        for statement in tree.body:
            if not isinstance(statement, ast.ImportFrom) or statement.module is None:
                continue
            target = PyTorchModelCensus._registry_module_file(
                root, init_path, statement.module, statement.level
            )
            if target is None:
                continue
            for imported in statement.names:
                if imported.name != "*":
                    imports[imported.asname or imported.name] = f"{target}:{imported.name}"
        return imports

    @staticmethod
    def _registry_module_file(
        root: Path, init_path: Path, module: str, level: int
    ) -> str | None:
        if level:
            base = init_path.parent
            for _ in range(level - 1):
                base = base.parent
            module_path = base.joinpath(*module.split("."))
        else:
            parts = module.split(".")
            if not parts or parts[0] != root.name:
                return None
            module_path = root.joinpath(*parts[1:])
        for candidate in (module_path.with_suffix(".py"), module_path / "__init__.py"):
            if candidate.is_file() and candidate.resolve().is_relative_to(root):
                return candidate.relative_to(root).as_posix()
        return None

    @staticmethod
    def _entrypoint_role(relative_file: str) -> str:
        """Classify candidates from source layout only; this never removes a census item."""

        parts = Path(relative_file).parts[:-1]
        return "model_candidate_by_path" if {"model", "models"} & set(parts) else "module_component"
