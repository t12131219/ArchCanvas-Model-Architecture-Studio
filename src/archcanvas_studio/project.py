from __future__ import annotations

import ast
import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from archcanvas_core.models import ProjectSession, SourceSnapshot

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


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _confined(root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("project path escapes the selected project root")
    return resolved


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
        workspace=str(workspace.resolve()),
        opened_at=datetime.now(UTC).isoformat(),
    )


def _framework_evidence(tree: ast.AST) -> tuple[str, list[str]]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    evidence = sorted(imports & {"torch", "tensorflow", "keras", "jax", "flax"})
    if "torch" in imports:
        return "pytorch", evidence
    if {"tensorflow", "keras"} & imports:
        return "keras", evidence
    if {"jax", "flax"} & imports:
        return "jax", evidence
    return "unknown", evidence


def discover_project(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("project root is not a directory")
    entrypoints: list[dict[str, Any]] = []
    configs: list[dict[str, Any]] = []
    warnings: list[str] = []
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
                        "framework": "onnx",
                        "kind": "model-artifact",
                        "confidence": "exact",
                        "evidence": [".onnx suffix"],
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
            module = relative.with_suffix("").as_posix().replace("/", ".")
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    bases = [ast.unparse(base) for base in node.bases]
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
                                "entrypoint": f"{module}:{node.name}",
                                "framework": framework,
                                "kind": "class",
                                "confidence": "inferred" if framework == "unknown" else "exact",
                                "evidence": [*evidence, *bases],
                                "line": node.lineno,
                            }
                        )
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
                    "model",
                    "build_model",
                    "create_model",
                    "forward",
                }:
                    entrypoints.append(
                        {
                            "entrypoint": f"{module}:{node.name}",
                            "framework": framework,
                            "kind": "function",
                            "confidence": "inferred",
                            "evidence": evidence,
                            "line": node.lineno,
                        }
                    )
    entrypoints.sort(key=lambda item: (item["entrypoint"], item["kind"]))
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
