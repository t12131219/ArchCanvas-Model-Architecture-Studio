from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Literal

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPOSITORY_ROOT / "skill"

HOST_TARGETS = {
    "codex": Path(".agents/skills/archcanvas"),
    "claude-code": Path(".claude/skills/archcanvas"),
}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_runtime(target: Path) -> None:
    runtime = target / "runtime" / "src"
    runtime.mkdir(parents=True)
    for source in sorted((REPOSITORY_ROOT / "src").glob("archcanvas*")):
        if source.is_dir() and not source.name.endswith(".egg-info"):
            shutil.copytree(
                source,
                runtime / source.name,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
    shutil.copytree(REPOSITORY_ROOT / "schemas", target / "schemas")


def install_skill(
    project: Path,
    host: Literal["codex", "claude-code"],
    mode: Literal["copy", "symlink"] = "copy",
) -> dict[str, object]:
    project = project.resolve()
    if not project.is_dir():
        raise ValueError(f"skill project root is not a directory: {project}")
    relative_target = HOST_TARGETS[host]
    target = project / relative_target
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"skill install target already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if mode == "symlink":
        target.symlink_to(SKILL_ROOT, target_is_directory=True)
        files = [
            {"path": path.relative_to(SKILL_ROOT).as_posix(), "sha256": _digest(path)}
            for path in sorted(SKILL_ROOT.rglob("*"))
            if path.is_file()
        ]
    else:
        staging = Path(tempfile.mkdtemp(prefix=".archcanvas-skill-", dir=target.parent))
        try:
            shutil.copytree(
                SKILL_ROOT,
                staging,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            _copy_runtime(staging)
            files = [
                {"path": path.relative_to(staging).as_posix(), "sha256": _digest(path)}
                for path in sorted(staging.rglob("*"))
                if path.is_file()
            ]
            receipt = {
                "schema_version": "1.0",
                "host": host,
                "mode": mode,
                "target": relative_target.as_posix(),
                "network_required": False,
                "source_writes": False,
                "files": files,
            }
            (staging / "install-receipt.json").write_text(
                json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n",
                encoding="utf-8",
            )
            os.replace(staging, target)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    return {
        "host": host,
        "mode": mode,
        "target": str(target),
        "network_required": False,
        "file_count": len(files),
    }
