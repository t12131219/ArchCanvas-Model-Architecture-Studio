"""Read-only resolution of local PyTorch module imports within an approved project root."""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .project import PyTorchProjectScanReport


@dataclass(frozen=True)
class LocalModuleSymbol:
    relative_file: str
    class_name: str


@dataclass(frozen=True)
class LocalModuleBinding:
    importing_relative_file: str
    local_name: str
    target_relative_file: str
    target_class_name: str
    line: int


@dataclass(frozen=True)
class SymbolResolutionIssue:
    relative_file: str
    line: int
    code: str
    message: str


@dataclass(frozen=True)
class EntrypointSymbolResolution:
    relative_file: str
    model_class: str
    local_module_bindings: list[LocalModuleBinding]
    issues: list[SymbolResolutionIssue]

    def as_dict(self) -> dict[str, object]:
        return {
            "entrypoint": {"relative_file": self.relative_file, "model_class": self.model_class},
            "local_module_bindings": [asdict(item) for item in self.local_module_bindings],
            "issues": [asdict(item) for item in self.issues],
        }


@dataclass(frozen=True)
class PyTorchProjectSymbolTable:
    root: str
    module_symbols: list[LocalModuleSymbol]
    bindings: list[LocalModuleBinding]
    issues: list[SymbolResolutionIssue]

    def resolve_entrypoint(self, entrypoint: str) -> EntrypointSymbolResolution:
        try:
            relative_file, model_class = entrypoint.split(":", maxsplit=1)
        except ValueError as error:
            raise ValueError("entrypoint must use 'relative_file:ClassName'") from error
        if not any(
            symbol.relative_file == relative_file and symbol.class_name == model_class
            for symbol in self.module_symbols
        ):
            raise ValueError("entrypoint is not a discovered local nn.Module class")
        return EntrypointSymbolResolution(
            relative_file=relative_file,
            model_class=model_class,
            local_module_bindings=[
                binding for binding in self.bindings if binding.importing_relative_file == relative_file
            ],
            issues=[issue for issue in self.issues if issue.relative_file == relative_file],
        )


def build_symbol_table(
    root: Path, scan_report: PyTorchProjectScanReport
) -> PyTorchProjectSymbolTable:
    """Resolve direct local imports to discovered `nn.Module` classes without importing code."""

    resolved_root = root.resolve(strict=True)
    symbols = [
        LocalModuleSymbol(item.relative_file, item.model_class) for item in scan_report.entrypoints
    ]
    symbols_by_file = _symbols_by_file(symbols)
    bindings: list[LocalModuleBinding] = []
    issues: list[SymbolResolutionIssue] = []
    for path in sorted(resolved_root.rglob("*.py")):
        relative = path.relative_to(resolved_root).as_posix()
        if relative not in {symbol.relative_file for symbol in symbols}:
            continue
        try:
            source = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for statement in source.body:
            if not isinstance(statement, ast.ImportFrom):
                continue
            target_file, is_local = _resolve_import_target(
                resolved_root, path, statement.module, statement.level
            )
            if target_file is None:
                if is_local:
                    issues.append(
                        SymbolResolutionIssue(
                            relative,
                            statement.lineno,
                            "UNRESOLVED_LOCAL_IMPORT",
                            statement.module or "relative import",
                        )
                    )
                continue
            if any(item.name == "*" for item in statement.names):
                issues.append(
                    SymbolResolutionIssue(
                        relative,
                        statement.lineno,
                        "UNRESOLVED_WILDCARD_IMPORT",
                        target_file,
                    )
                )
                continue
            for imported in statement.names:
                if imported.name not in symbols_by_file.get(target_file, set()):
                    continue
                bindings.append(
                    LocalModuleBinding(
                        importing_relative_file=relative,
                        local_name=imported.asname or imported.name,
                        target_relative_file=target_file,
                        target_class_name=imported.name,
                        line=statement.lineno,
                    )
                )
    return PyTorchProjectSymbolTable(
        root=str(resolved_root),
        module_symbols=sorted(symbols, key=lambda item: (item.relative_file, item.class_name)),
        bindings=sorted(
            set(bindings),
            key=lambda item: (item.importing_relative_file, item.line, item.local_name),
        ),
        issues=sorted(set(issues), key=lambda item: (item.relative_file, item.line, item.code)),
    )


def _symbols_by_file(symbols: list[LocalModuleSymbol]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for symbol in symbols:
        result.setdefault(symbol.relative_file, set()).add(symbol.class_name)
    return result


def _resolve_import_target(
    root: Path, importing_path: Path, module: str | None, level: int
) -> tuple[str | None, bool]:
    importing_parent = importing_path.parent
    if level:
        base = importing_parent
        for _ in range(level - 1):
            base = base.parent
        is_local = True
    else:
        module_parts = (module or "").split(".")
        module_head = module_parts[0]
        # A project may be opened at its package root while source uses fully-qualified
        # imports such as ``ts_benchmark.baselines...``.  Treat only that exact root
        # package name as local; unrelated absolute imports remain external.
        if module_head == root.name:
            module_parts = module_parts[1:]
            is_local = bool(module_parts)
            base = root
        else:
            is_local = (root / module_head).exists() or (root / f"{module_head}.py").exists()
            base = root
        if not is_local:
            return None, False
    module_path = base.joinpath(*(module_parts if not level else (module or "").split(".")))
    candidates = [module_path.with_suffix(".py"), module_path / "__init__.py"]
    for candidate in candidates:
        if candidate.is_file() and candidate.resolve().is_relative_to(root):
            return candidate.relative_to(root).as_posix(), True
    return None, is_local
