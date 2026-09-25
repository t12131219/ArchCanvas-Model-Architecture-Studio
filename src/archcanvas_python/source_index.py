from __future__ import annotations

import ast
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path

FRAMEWORK_IMPORTS = {
    "torch": "pytorch",
    "tensorflow": "keras",
    "keras": "keras",
    "jax": "jax",
    "flax": "jax",
}


@dataclass(frozen=True)
class ParsedModule:
    name: str
    path: Path
    tree: ast.Module
    is_package: bool


@dataclass(frozen=True)
class ResolvedSymbol:
    module: ParsedModule
    node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef


def module_name_from_path(relative: Path) -> str:
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or "__init__"


def resolve_module_path(project: Path, module_name: str) -> Path | None:
    if not module_name or module_name == "__init__":
        candidates = [project / "__init__.py"]
    else:
        relative = Path(*module_name.split("."))
        candidates = [project / relative.with_suffix(".py"), project / relative / "__init__.py"]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_relative_to(project) and resolved.is_file():
            return resolved
    return None


def parse_module(project: Path, module_name: str) -> ParsedModule | None:
    path = resolve_module_path(project, module_name)
    if path is None:
        return None
    try:
        tree = ast.parse(path.read_bytes(), filename=str(path))
    except (OSError, SyntaxError, UnicodeError):
        return None
    return ParsedModule(
        name=module_name,
        path=path,
        tree=tree,
        is_package=path.name == "__init__.py",
    )


def absolute_import_module(
    current_module: str,
    is_package: bool,
    imported_module: str | None,
    level: int,
) -> str:
    if level == 0:
        return imported_module or ""
    package_parts = current_module.split(".") if is_package else current_module.split(".")[:-1]
    keep = max(0, len(package_parts) - level + 1)
    prefix = ".".join(package_parts[:keep])
    return ".".join(part for part in (prefix, imported_module or "") if part)


def imported_modules(module: ParsedModule) -> list[str]:
    result: list[str] = []
    for node in module.tree.body:
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = absolute_import_module(
                module.name,
                module.is_package,
                node.module,
                node.level,
            )
            if base:
                result.append(base)
    return list(dict.fromkeys(result))


def framework_evidence(tree: ast.AST) -> tuple[str | None, list[str]]:
    roots: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.append(node.module.split(".")[0])
    frameworks = Counter(FRAMEWORK_IMPORTS[root] for root in roots if root in FRAMEWORK_IMPORTS)
    if not frameworks:
        return None, []
    highest = max(frameworks.values())
    leaders = sorted(name for name, count in frameworks.items() if count == highest)
    return (leaders[0] if len(leaders) == 1 else None), sorted(set(roots) & FRAMEWORK_IMPORTS.keys())


def _symbol_alias(module: ParsedModule, symbol_name: str) -> tuple[str, str] | None:
    for node in module.tree.body:
        if isinstance(node, ast.ImportFrom):
            imported_module = absolute_import_module(
                module.name,
                module.is_package,
                node.module,
                node.level,
            )
            for alias in node.names:
                if (alias.asname or alias.name) == symbol_name and alias.name != "*":
                    return imported_module, alias.name
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if not isinstance(target, ast.Name) or target.id != symbol_name:
                continue
            if isinstance(node.value, ast.Name):
                return module.name, node.value.id
    return None


def resolve_symbol(project: Path, entrypoint: str) -> ResolvedSymbol | None:
    if ":" not in entrypoint:
        return None
    module_name, symbol_name = entrypoint.split(":", 1)
    seen: set[tuple[str, str]] = set()
    while (module_name, symbol_name) not in seen:
        seen.add((module_name, symbol_name))
        module = parse_module(project, module_name)
        if module is None:
            return None
        node = next(
            (
                item
                for item in module.tree.body
                if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name == symbol_name
            ),
            None,
        )
        if node is not None:
            return ResolvedSymbol(module=module, node=node)
        alias = _symbol_alias(module, symbol_name)
        if alias is None:
            return None
        module_name, symbol_name = alias
    return None


def detect_framework(project: Path, entrypoint: str) -> str:
    if entrypoint.lower().endswith(".onnx") or project.suffix.lower() == ".onnx":
        return "onnx"
    if ":" not in entrypoint:
        return "python"
    start_name, symbol_name = entrypoint.split(":", 1)
    queue = deque([(start_name, 0)])
    seen: set[str] = set()
    evidence_by_depth: dict[int, Counter[str]] = {}
    entry_methods: set[str] = set()
    while queue:
        module_name, depth = queue.popleft()
        if module_name in seen:
            continue
        seen.add(module_name)
        module = parse_module(project, module_name)
        if module is None:
            continue
        framework, _ = framework_evidence(module.tree)
        if framework:
            evidence_by_depth.setdefault(depth, Counter())[framework] += 1
        if depth == 0:
            symbol = next(
                (
                    item
                    for item in module.tree.body
                    if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                    and item.name == symbol_name
                ),
                None,
            )
            if isinstance(symbol, ast.ClassDef):
                entry_methods = {
                    item.name
                    for item in symbol.body
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
        for imported in imported_modules(module):
            if resolve_module_path(project, imported) is not None:
                queue.append((imported, depth + 1))
    for depth in sorted(evidence_by_depth):
        counts = evidence_by_depth[depth]
        highest = max(counts.values())
        leaders = sorted(name for name, count in counts.items() if count == highest)
        if len(leaders) == 1:
            return leaders[0]
    if "forward" in entry_methods:
        return "pytorch"
    if "call" in entry_methods:
        return "keras"
    if "__call__" in entry_methods:
        return "jax"
    return "python"
