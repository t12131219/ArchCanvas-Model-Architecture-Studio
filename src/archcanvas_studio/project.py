from __future__ import annotations

import ast
import hashlib
import os
from collections import defaultdict, deque
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from archcanvas_core.models import ProjectSession, SourceSnapshot
from archcanvas_python.source_index import (
    absolute_import_module,
    framework_evidence,
    module_name_from_path,
    resolve_module_path,
)

EXCLUDED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    "data",
    "datasets",
    "weights",
    "checkpoints",
}
CONFIG_SUFFIXES = {".json", ".yaml", ".yml", ".toml"}
CONDA_ROOT_NAMES = ("anaconda3", "miniconda3", "miniforge3", "mambaforge")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _confined(root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("project path escapes the selected project root")
    return resolved


def _conda_environment(path: Path, active: Path | None) -> dict[str, Any] | None:
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        return None
    python = resolved / ("python.exe" if os.name == "nt" else "bin/python")
    if not resolved.is_dir() or not (resolved / "conda-meta").is_dir() or not python.is_file():
        return None
    name = "base" if resolved.name in CONDA_ROOT_NAMES else resolved.name
    return {
        "name": name,
        "path": str(resolved),
        "python": str(python),
        "active": active == resolved,
    }


def discover_conda_environments(
    *,
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Discover registered Conda environments without executing Conda or Python."""
    variables = os.environ if environ is None else environ
    home = (home or Path.home()).expanduser().resolve()
    active_value = variables.get("CONDA_PREFIX")
    active = Path(active_value).expanduser().resolve() if active_value else None
    candidates: set[Path] = set()

    if active is not None:
        candidates.add(active)
    conda_executable = variables.get("CONDA_EXE")
    if conda_executable:
        executable = Path(conda_executable).expanduser().resolve()
        candidates.add(executable.parent.parent)
    for name in CONDA_ROOT_NAMES:
        candidates.add(home / name)

    registry = home / ".conda" / "environments.txt"
    if registry.is_file():
        try:
            candidates.update(
                Path(line.strip()).expanduser()
                for line in registry.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        except (OSError, UnicodeError):
            pass

    roots = list(candidates)
    for root in roots:
        envs = root / "envs"
        if not envs.is_dir():
            continue
        try:
            candidates.update(path for path in envs.iterdir() if path.is_dir())
        except OSError:
            continue

    environments = [
        item
        for item in (_conda_environment(path, active) for path in candidates)
        if item is not None
    ]
    environments.sort(key=lambda item: (not item["active"], item["name"].lower(), item["path"]))
    return {
        "schema_version": "1.0",
        "environments": environments,
        "selected": next(
            (item["path"] for item in environments if item["active"]),
            environments[0]["path"] if environments else None,
        ),
        "source_execution": False,
    }


def resolve_conda_environment(path: str | None) -> dict[str, Any] | None:
    discovered = discover_conda_environments()
    if path is None:
        selected = discovered["selected"]
        return next(
            (item for item in discovered["environments"] if item["path"] == selected),
            None,
        )
    resolved = str(Path(path).expanduser().resolve())
    selected = next(
        (item for item in discovered["environments"] if item["path"] == resolved),
        None,
    )
    if selected is None:
        raise ValueError("selected Conda environment is not registered or valid")
    return selected


def create_project_session(
    root: Path,
    workspace: Path,
    *,
    generation: int,
    snapshot: SourceSnapshot | None = None,
    entrypoint: str | None = None,
    framework: str = "auto",
    task: str = "inference",
    config_path: str | None = None,
    environment: Mapping[str, Any] | None = None,
) -> ProjectSession:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("project root is not a directory")
    config_digest = _digest(b"{}")
    normalized_config: str | None = None
    selected_config = config_path or (snapshot.config_path if snapshot else None)
    if selected_config:
        candidate = Path(selected_config)
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = _confined(root, candidate)
        if not candidate.is_file() or candidate.is_symlink():
            raise ValueError("project config is not a regular in-root file")
        config_digest = _digest(candidate.read_bytes())
        normalized_config = str(candidate.relative_to(root))
    elif snapshot is not None:
        config_digest = snapshot.config_digest
    suffix = _digest(str(root).encode())[:16]
    return ProjectSession(
        project_id=f"project:{suffix}",
        root=str(root),
        generation=generation,
        entrypoint=entrypoint or (snapshot.entrypoint if snapshot else None),
        framework=framework if framework != "auto" else (snapshot.framework if snapshot else "auto"),
        task=task if snapshot is None else snapshot.task,
        config_path=normalized_config,
        config_digest=config_digest,
        environment_path=(str(environment["path"]) if environment else None),
        python_executable=(str(environment["python"]) if environment else None),
        workspace=str(workspace.resolve()),
        opened_at=datetime.now(UTC).isoformat(),
    )


def _framework_evidence(tree: ast.AST) -> tuple[str, list[str]]:
    framework, evidence = framework_evidence(tree)
    return framework or "unknown", evidence


def _dotted_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _dotted_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    return None


def _import_aliases(tree: ast.Module, module: str, *, is_package: bool = False) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom):
            imported_module = absolute_import_module(
                module,
                is_package,
                node.module,
                node.level,
            )
            for alias in node.names:
                if alias.name == "*":
                    continue
                aliases[alias.asname or alias.name] = ".".join(
                    part for part in (imported_module, alias.name) if part
                )
    return aliases


def _resolve_entrypoint_reference(
    name: str,
    *,
    module: str,
    aliases: Mapping[str, str],
    entrypoint_by_symbol: Mapping[str, str],
    entrypoints_by_name: Mapping[str, list[str]],
) -> str | None:
    parts = name.split(".")
    imported = aliases.get(parts[0])
    expanded = ".".join([imported, *parts[1:]]) if imported else name
    direct = entrypoint_by_symbol.get(expanded)
    if direct is None and "." in expanded:
        suffix_matches = [
            entrypoint
            for symbol, entrypoint in entrypoint_by_symbol.items()
            if symbol.endswith(f".{expanded}")
        ]
        if len(suffix_matches) == 1:
            direct = suffix_matches[0]
    if direct is None and "." not in expanded:
        direct = entrypoint_by_symbol.get(f"{module}.{expanded}")
    if direct is None:
        candidates = entrypoints_by_name.get(parts[-1], [])
        if len(candidates) == 1:
            direct = candidates[0]
    return direct


def _entrypoint_category(name: str, kind: str, top_level: bool) -> str:
    if kind in {"model-artifact", "function"} or top_level:
        return "model"
    normalized = name.lower().replace("_", "")
    for marker, category in (
        ("attention", "attention"),
        ("attn", "attention"),
        ("head", "head"),
        ("block", "block"),
        ("layer", "layer"),
        ("encoder", "encoder"),
        ("decoder", "decoder"),
        ("backbone", "backbone"),
    ):
        if marker in normalized:
            return category
    return "component"


def _resolve_instantiated_entrypoints(
    node: ast.ClassDef,
    *,
    module: str,
    aliases: Mapping[str, str],
    entrypoint_by_symbol: Mapping[str, str],
    entrypoints_by_name: Mapping[str, list[str]],
) -> set[str]:
    resolved: set[str] = set()
    for descendant in ast.walk(node):
        if not isinstance(descendant, ast.Call):
            continue
        call_name = _dotted_name(descendant.func)
        if not call_name:
            continue
        direct = _resolve_entrypoint_reference(
            call_name,
            module=module,
            aliases=aliases,
            entrypoint_by_symbol=entrypoint_by_symbol,
            entrypoints_by_name=entrypoints_by_name,
        )
        if direct is not None:
            resolved.add(direct)
    return resolved


def _is_top_level_model(item: Mapping[str, Any], has_parent: bool) -> bool:
    if has_parent:
        return False
    return item["kind"] in {"model-artifact", "function", "class", "re-export"}


def _analysis_scope(
    root: Path,
    item: Mapping[str, Any],
    configs: list[dict[str, Any]],
) -> tuple[str, str, list[str]]:
    source_path = Path(item["path"])
    scope = Path(".")
    if item["kind"] != "model-artifact":
        absolute_imports: set[str] = set()
        try:
            tree = ast.parse((root / source_path).read_bytes(), filename=source_path.as_posix())
            absolute_imports = {
                node.module
                for node in tree.body
                if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module
            }
            absolute_imports.update(
                alias.name
                for node in tree.body
                if isinstance(node, ast.Import)
                for alias in node.names
            )
        except (OSError, SyntaxError, UnicodeError):
            pass
        candidates = [Path(".")]
        parent = source_path.parent
        candidates.extend(
            Path(*parent.parts[:index]) for index in range(1, len(parent.parts) + 1)
        )
        scored = [
            (
                sum(
                    resolve_module_path((root / candidate).resolve(), imported) is not None
                    for imported in absolute_imports
                ),
                -len(candidate.parts),
                candidate,
            )
            for candidate in candidates
        ]
        best_score, _, best_scope = max(scored, key=lambda value: (value[0], value[1]))
        if best_score:
            scope = best_scope
    scope_path = scope.as_posix()
    entrypoint = str(item["entrypoint"])
    if item["kind"] == "model-artifact":
        entrypoint = Path(entrypoint).relative_to(scope).as_posix()
    elif ":" in entrypoint and scope != Path("."):
        module, symbol = entrypoint.split(":", 1)
        prefix = f"{scope_path.replace('/', '.')}."
        if module.startswith(prefix):
            entrypoint = f"{module.removeprefix(prefix)}:{symbol}"
    scoped_configs = [
        config["path"]
        for config in configs
        if Path(config["path"]).is_relative_to(scope)
    ]
    return scope_path, entrypoint, scoped_configs


def browse_directories(path: Path | None = None) -> dict[str, Any]:
    """Return a deterministic directory listing for the local Studio picker."""
    current = (path or Path.home()).expanduser().resolve()
    if not current.is_dir():
        raise ValueError("selected folder does not exist or is not a directory")
    try:
        directories = sorted(
            (
                child
                for child in current.iterdir()
                if child.is_dir() and not child.is_symlink()
            ),
            key=lambda child: (child.name.startswith("."), child.name.lower()),
        )
    except OSError as error:
        raise ValueError("selected folder cannot be read") from error
    breadcrumbs: list[dict[str, str]] = []
    cursor = Path(current.anchor)
    breadcrumbs.append({"name": current.anchor or "/", "path": str(cursor)})
    for part in current.parts[1:]:
        cursor /= part
        breadcrumbs.append({"name": part, "path": str(cursor)})
    return {
        "schema_version": "1.0",
        "path": str(current),
        "parent": str(current.parent) if current.parent != current else None,
        "breadcrumbs": breadcrumbs,
        "directories": [
            {"name": child.name, "path": str(child)} for child in directories[:500]
        ],
        "truncated": len(directories) > 500,
    }


def discover_project(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("project root is not a directory")
    entrypoints: list[dict[str, Any]] = []
    configs: list[dict[str, Any]] = []
    warnings: list[str] = []
    class_nodes: dict[str, tuple[ast.ClassDef, str, dict[str, str]]] = {}
    all_class_nodes: dict[
        str, tuple[ast.ClassDef, str, dict[str, str], str, list[str], str]
    ] = {}
    function_nodes: list[
        tuple[ast.FunctionDef | ast.AsyncFunctionDef, str, dict[str, str], str, list[str], str]
    ] = []
    package_modules: set[str] = set()
    package_aliases: dict[str, tuple[dict[str, str], str, list[str], str]] = {}
    scanned_files = 0
    for current, directory_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name not in EXCLUDED_DIRECTORIES and not (current_path / name).is_symlink()
        )
        for filename in sorted(file_names):
            path = current_path / filename
            if path.is_symlink():
                continue
            relative = path.relative_to(root)
            if path.suffix.lower() in CONFIG_SUFFIXES and path.stat().st_size <= 2_000_000:
                configs.append(
                    {
                        "path": relative.as_posix(),
                        "sha256": _digest(path.read_bytes()),
                        "format": path.suffix.lower().lstrip("."),
                    }
                )
            if path.suffix.lower() == ".onnx":
                entrypoints.append(
                    {
                        "entrypoint": relative.as_posix(),
                        "path": relative.as_posix(),
                        "framework": "onnx",
                        "kind": "model-artifact",
                        "confidence": "exact",
                        "evidence": [".onnx suffix"],
                        "line": 1,
                    }
                )
                scanned_files += 1
                continue
            if path.suffix != ".py" or path.stat().st_size > 2_000_000:
                continue
            scanned_files += 1
            try:
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=relative.as_posix())
            except (OSError, UnicodeError, SyntaxError) as error:
                warnings.append(f"{relative.as_posix()}: {type(error).__name__}")
                continue
            framework, evidence = _framework_evidence(tree)
            module = module_name_from_path(relative)
            is_package = path.name == "__init__.py"
            if is_package:
                package_modules.add(module)
            aliases = _import_aliases(tree, module, is_package=is_package)
            if is_package:
                package_aliases[module] = (
                    aliases,
                    relative.as_posix(),
                    evidence,
                    framework,
                )
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    bases = [ast.unparse(base) for base in node.bases]
                    entrypoint = f"{module}:{node.name}"
                    all_class_nodes[entrypoint] = (
                        node,
                        module,
                        aliases,
                        framework,
                        evidence,
                        relative.as_posix(),
                    )
                    model_like = any(
                        marker in base
                        for base in bases
                        for marker in ("Module", "Model", "Layer")
                    )
                    methods = {
                        child.name for child in node.body if isinstance(child, ast.FunctionDef)
                    }
                    if model_like or {"forward", "call", "__call__"} & methods:
                        entrypoints.append(
                            {
                                "entrypoint": entrypoint,
                                "path": relative.as_posix(),
                                "framework": framework,
                                "kind": "class",
                                "confidence": "inferred" if framework == "unknown" else "exact",
                                "evidence": [*evidence, *bases],
                                "line": node.lineno,
                            }
                        )
                        class_nodes[entrypoint] = (
                            node,
                            module,
                            aliases,
                        )
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    function_nodes.append(
                        (node, module, aliases, framework, evidence, relative.as_posix())
                    )

    all_entrypoint_by_symbol = {
        entrypoint.replace(":", "."): entrypoint for entrypoint in all_class_nodes
    }
    all_entrypoints_by_name: dict[str, list[str]] = defaultdict(list)
    for entrypoint in all_class_nodes:
        all_entrypoints_by_name[entrypoint.rsplit(":", 1)[-1]].append(entrypoint)
    class_parents: dict[str, set[str]] = defaultdict(set)
    for entrypoint, (node, module, aliases, _, _, _) in all_class_nodes.items():
        for base in node.bases:
            base_name = _dotted_name(base)
            if not base_name:
                continue
            resolved = _resolve_entrypoint_reference(
                base_name,
                module=module,
                aliases=aliases,
                entrypoint_by_symbol=all_entrypoint_by_symbol,
                entrypoints_by_name=all_entrypoints_by_name,
            )
            if resolved and resolved != entrypoint:
                class_parents[entrypoint].add(resolved)

    selected_classes = set(class_nodes)
    changed = True
    while changed:
        changed = False
        for entrypoint, parents in class_parents.items():
            if entrypoint in selected_classes or not (parents & selected_classes):
                continue
            node, module, aliases, framework, evidence, relative = all_class_nodes[entrypoint]
            inherited_framework = next(
                (
                    str(item["framework"])
                    for item in entrypoints
                    if item["entrypoint"] in parents and item["framework"] != "unknown"
                ),
                framework,
            )
            bases = [ast.unparse(base) for base in node.bases]
            entrypoints.append(
                {
                    "entrypoint": entrypoint,
                    "path": relative,
                    "framework": inherited_framework,
                    "kind": "class",
                    "confidence": "inferred",
                    "evidence": [*evidence, *bases, "model-like local base class"],
                    "line": node.lineno,
                }
            )
            class_nodes[entrypoint] = (node, module, aliases)
            selected_classes.add(entrypoint)
            changed = True

    framework_by_class = {
        str(item["entrypoint"]): str(item["framework"])
        for item in entrypoints
        if item["kind"] == "class"
    }
    changed = True
    while changed:
        changed = False
        for item in entrypoints:
            entrypoint = str(item["entrypoint"])
            if item["kind"] != "class" or item["framework"] != "unknown":
                continue
            inherited = next(
                (
                    framework_by_class[parent]
                    for parent in class_parents[entrypoint]
                    if framework_by_class.get(parent, "unknown") != "unknown"
                ),
                None,
            )
            if inherited:
                item["framework"] = inherited
                item["evidence"] = [*item["evidence"], "framework inherited from local base"]
                framework_by_class[entrypoint] = inherited
                changed = True

    selected_entrypoint_by_symbol = {
        entrypoint.replace(":", "."): entrypoint for entrypoint in selected_classes
    }
    selected_entrypoints_by_name: dict[str, list[str]] = defaultdict(list)
    for entrypoint in selected_classes:
        selected_entrypoints_by_name[entrypoint.rsplit(":", 1)[-1]].append(entrypoint)
    framework_roots = {"torch", "tensorflow", "keras", "jax", "flax"}
    for node, module, aliases, framework, evidence, relative in function_nodes:
        if node.name.startswith("_") or not any(isinstance(item, ast.Return) for item in ast.walk(node)):
            continue
        constructed = _resolve_instantiated_entrypoints(
            node,
            module=module,
            aliases=aliases,
            entrypoint_by_symbol=selected_entrypoint_by_symbol,
            entrypoints_by_name=selected_entrypoints_by_name,
        )
        framework_call = False
        for descendant in ast.walk(node):
            if not isinstance(descendant, ast.Call):
                continue
            call_name = _dotted_name(descendant.func)
            if not call_name:
                continue
            first, *rest = call_name.split(".")
            expanded = ".".join([aliases.get(first, first), *rest])
            if expanded.split(".", 1)[0] in framework_roots:
                framework_call = True
                break
        legacy_factory = node.name in {"model", "build_model", "create_model", "forward"}
        if not (constructed or framework_call or legacy_factory):
            continue
        inferred_framework = framework
        if inferred_framework == "unknown" and constructed:
            inferred_framework = next(
                (
                    framework_by_class[target]
                    for target in sorted(constructed)
                    if framework_by_class.get(target, "unknown") != "unknown"
                ),
                "unknown",
            )
        entrypoints.append(
            {
                "entrypoint": f"{module}:{node.name}",
                "path": relative,
                "framework": inferred_framework,
                "kind": "function",
                "confidence": "inferred",
                "evidence": [
                    *evidence,
                    *(sorted(constructed) if constructed else []),
                    *(("framework call in returned dataflow",) if framework_call else ()),
                ],
                "line": node.lineno,
            }
        )

    for module in sorted(package_modules):
        aliases, relative, evidence, framework = package_aliases[module]
        for alias_name, expanded in sorted(aliases.items()):
            target = selected_entrypoint_by_symbol.get(expanded)
            if target is None:
                continue
            entrypoint = f"{module}:{alias_name}"
            if entrypoint in selected_classes:
                continue
            target_framework = framework_by_class.get(target, framework)
            entrypoints.append(
                {
                    "entrypoint": entrypoint,
                    "path": relative,
                    "framework": target_framework,
                    "kind": "re-export",
                    "confidence": "exact",
                    "evidence": [*evidence, f"re-export of {target}"],
                    "line": 1,
                }
            )

    entrypoint_by_symbol = {
        item["entrypoint"].replace(":", "."): item["entrypoint"]
        for item in entrypoints
        if item["kind"] == "class"
    }
    entrypoints_by_name: dict[str, list[str]] = defaultdict(list)
    for item in entrypoints:
        if item["kind"] == "class":
            entrypoints_by_name[item["entrypoint"].rsplit(":", 1)[-1]].append(
                item["entrypoint"]
            )

    children_by_parent: dict[str, set[str]] = defaultdict(set)
    parents_by_child: dict[str, set[str]] = defaultdict(set)
    for parent, (node, module, aliases) in class_nodes.items():
        children = _resolve_instantiated_entrypoints(
            node,
            module=module,
            aliases=aliases,
            entrypoint_by_symbol=entrypoint_by_symbol,
            entrypoints_by_name=entrypoints_by_name,
        )
        for child in children - {parent}:
            children_by_parent[parent].add(child)
            parents_by_child[child].add(parent)

    all_ids = {item["entrypoint"] for item in entrypoints}
    roots = sorted(all_ids - set(parents_by_child))
    depths = {entrypoint: 0 for entrypoint in roots}
    queue = deque(roots)
    while queue:
        parent = queue.popleft()
        for child in sorted(children_by_parent[parent]):
            candidate_depth = depths[parent] + 1
            if child not in depths or candidate_depth < depths[child]:
                depths[child] = candidate_depth
                queue.append(child)
    for entrypoint in sorted(all_ids - set(depths)):
        depths[entrypoint] = 0

    primary_parent: dict[str, str] = {}
    for child, parents in parents_by_child.items():
        shallower = [
            parent for parent in parents if depths[parent] < depths[child]
        ]
        if shallower:
            primary_parent[child] = min(
                shallower,
                key=lambda parent: (depths[child] - depths[parent], parent),
            )

    roots_by_entrypoint: dict[str, str] = {}
    for entrypoint in sorted(all_ids, key=lambda item: (depths[item], item)):
        parent = primary_parent.get(entrypoint)
        roots_by_entrypoint[entrypoint] = (
            roots_by_entrypoint.get(parent, parent) if parent else entrypoint
        )

    for item in entrypoints:
        entrypoint = item["entrypoint"]
        name = entrypoint.rsplit(":", 1)[-1]
        top_level = _is_top_level_model(item, entrypoint in parents_by_child)
        analysis_root, analysis_entrypoint, scoped_configs = _analysis_scope(root, item, configs)
        item.update(
            {
                "parent_entrypoint": primary_parent.get(entrypoint),
                "parent_entrypoints": sorted(parents_by_child[entrypoint]),
                "root_entrypoint": roots_by_entrypoint[entrypoint],
                "depth": depths[entrypoint],
                "contains": sorted(children_by_parent[entrypoint]),
                "child_count": len(children_by_parent[entrypoint]),
                "top_level": top_level,
                "analysis_root": analysis_root,
                "analysis_entrypoint": analysis_entrypoint,
                "config_paths": scoped_configs,
                "category": _entrypoint_category(
                    name, item["kind"], top_level
                ),
            }
        )

    top_level_ids = {
        item["entrypoint"] for item in entrypoints if item["top_level"]
    }
    entrypoints.sort(
        key=lambda item: (
            item["root_entrypoint"] not in top_level_ids,
            item["root_entrypoint"],
            item["depth"],
            item["parent_entrypoint"] or "",
            item["path"],
            item.get("line", 0),
            item["entrypoint"],
        )
    )
    configs.sort(key=lambda item: item["path"])
    return {
        "schema_version": "1.0",
        "root": str(root),
        "entrypoints": entrypoints,
        "configs": configs,
        "warnings": warnings,
        "scanned_files": scanned_files,
        "source_execution": False,
    }
