from __future__ import annotations

import tomllib
from pathlib import Path

from archcanvas_core.source_v2 import DiscoveryBudget, ProjectManifest, SourceRootSpec


def _setuptools_source_roots(pyproject: dict[str, object]) -> list[str]:
    tool = pyproject.get("tool")
    if not isinstance(tool, dict):
        return []
    setuptools = tool.get("setuptools")
    if not isinstance(setuptools, dict):
        return []
    packages = setuptools.get("packages")
    if not isinstance(packages, dict):
        return []
    find = packages.get("find")
    if not isinstance(find, dict):
        return []
    where = find.get("where")
    if not isinstance(where, list):
        return []
    return [item for item in where if isinstance(item, str) and item]


def discover_project_manifest(
    project_root: Path,
    project_id: str,
    *,
    budget: DiscoveryBudget | None = None,
) -> ProjectManifest:
    root = project_root.resolve()
    if not root.is_dir():
        raise ValueError("project root is not a directory")

    config_paths: list[str] = []
    root_paths: list[str] = []
    pyproject_path = root / "pyproject.toml"
    if pyproject_path.is_file() and not pyproject_path.is_symlink():
        config_paths.append("pyproject.toml")
        try:
            pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError):
            pyproject = {}
        root_paths.extend(_setuptools_source_roots(pyproject))
    if (root / "pyrightconfig.json").is_file():
        config_paths.append("pyrightconfig.json")
    if not root_paths:
        root_paths = ["src"] if (root / "src").is_dir() else ["."]

    source_roots = [
        SourceRootSpec(relative_path=path, precedence=index)
        for index, path in enumerate(dict.fromkeys(root_paths))
        if (root / path).is_dir()
    ]
    if not source_roots:
        source_roots = [SourceRootSpec(relative_path=".")]
    return ProjectManifest(
        project_id=project_id,
        project_root_hint=str(root),
        source_roots=source_roots,
        include_globs=["*.py", "**/*.py", "*.pyi", "**/*.pyi"],
        exclude_globs=[
            ".git/**",
            ".venv/**",
            "venv/**",
            "node_modules/**",
            "__pycache__/**",
            "**/__pycache__/**",
        ],
        config_paths=sorted(config_paths),
        discovery_budget=budget or DiscoveryBudget(),
    )
