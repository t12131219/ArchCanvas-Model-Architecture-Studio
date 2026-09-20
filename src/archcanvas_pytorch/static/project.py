"""Read-only, bounded discovery of PyTorch model entrypoints in a project tree."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .scanner import PyTorchStaticScanner
from .symbols import PyTorchProjectSymbolTable, build_symbol_table

_SKIPPED_DIRECTORIES = {".git", ".venv", "__pycache__", "build", "dist", "node_modules"}


@dataclass(frozen=True)
class ModelEntrypointDiscovery:
    relative_file: str
    model_class: str


@dataclass(frozen=True)
class ProjectScanIssue:
    relative_file: str
    code: str
    message: str


@dataclass(frozen=True)
class PyTorchProjectScanReport:
    root: str
    python_files_scanned: int
    entrypoints: list[ModelEntrypointDiscovery]
    issues: list[ProjectScanIssue]

    def as_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "python_files_scanned": self.python_files_scanned,
            "entrypoints": [asdict(item) for item in self.entrypoints],
            "issues": [asdict(item) for item in self.issues],
        }


class PyTorchProjectScanner:
    """Find candidate `nn.Module` entrypoints without importing or executing user code."""

    def __init__(self, scanner: PyTorchStaticScanner | None = None, *, max_file_bytes: int = 1_000_000) -> None:
        if max_file_bytes < 1:
            raise ValueError("max_file_bytes must be positive")
        self._scanner = scanner or PyTorchStaticScanner()
        self._max_file_bytes = max_file_bytes

    def scan(self, root: Path) -> PyTorchProjectScanReport:
        resolved_root = root.resolve(strict=True)
        if not resolved_root.is_dir():
            raise ValueError("project root must be a directory")
        entrypoints: list[ModelEntrypointDiscovery] = []
        issues: list[ProjectScanIssue] = []
        scanned = 0
        for path in sorted(resolved_root.rglob("*.py")):
            relative = path.relative_to(resolved_root).as_posix()
            if any(part in _SKIPPED_DIRECTORIES for part in path.relative_to(resolved_root).parts):
                continue
            if path.is_symlink() and not path.resolve().is_relative_to(resolved_root):
                issues.append(ProjectScanIssue(relative, "SYMLINK_OUTSIDE_ROOT", "file resolves outside project root"))
                continue
            if path.stat().st_size > self._max_file_bytes:
                issues.append(ProjectScanIssue(relative, "FILE_TOO_LARGE", "file exceeds static scan byte limit"))
                continue
            raw_source = path.read_bytes()
            try:
                result = self._scanner.scan(raw_source)
            except (SyntaxError, UnicodeDecodeError, ValueError) as error:
                issues.append(ProjectScanIssue(relative, "UNPARSEABLE_SOURCE", str(error)))
                continue
            scanned += 1
            entrypoints.extend(
                ModelEntrypointDiscovery(relative, model_class) for model_class in result.model_classes
            )
        return PyTorchProjectScanReport(
            root=str(resolved_root),
            python_files_scanned=scanned,
            entrypoints=sorted(entrypoints, key=lambda item: (item.relative_file, item.model_class)),
            issues=sorted(issues, key=lambda item: (item.relative_file, item.code)),
        )

    def build_symbol_table(self, root: Path) -> PyTorchProjectSymbolTable:
        """Build direct local-module bindings from a fresh, bounded scan report."""

        report = self.scan(root)
        return build_symbol_table(root, report)
