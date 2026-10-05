#!/usr/bin/env python3
"""Run the new runtime from a standalone temporary copy, without site packages.

The optional Studio check copies already installed project-local npm dependencies.
This proves source/build independence; it does not claim a clean dependency install.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


EXCLUDED = {
    ".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".archcanvas", ".DS_Store", ".env", ".env.local",
}
RELEASE_ITEMS = (
    "pyproject.toml", "requirements.lock", "requirements-runtime.lock", "README.md", "AGENTS.md", "LICENSE", "LICENSE.md", ".gitignore",
    "src", "fixtures", "studio", "docs", "scripts", "skills", "tests", "schemas",
)
MODULES = ("archcanvas_cli", "archcanvas_python", "archcanvas_transactions", "archcanvas_publication", "archcanvas_runtime")
FIXTURES = (
    ("transformer", "model:Transformer"),
    ("mlp", "model:MLP"),
    ("residual_cnn", "model:ResidualCNN"),
    ("holdout_vit", "model:PatchVisionEncoder"),
    ("holdout_families", "model:TemporalForecaster"),
)


def ignored(_directory: str, names: list[str]) -> set[str]:
    return {
        name for name in names
        if name in EXCLUDED or name.endswith((".pyc", ".pyo", ".egg-info", ".tsbuildinfo"))
    }


def checked_copy(source: Path, destination: Path) -> None:
    """Reject distribution source symlinks rather than following external content."""
    for current, directories, files in os.walk(source, followlinks=False):
        excluded = ignored(current, directories + files)
        directories[:] = [name for name in directories if name not in excluded]
        for name in directories + [name for name in files if name not in excluded]:
            item = Path(current) / name
            if item.is_symlink():
                raise RuntimeError(f"Distribution source contains a symlink: {item}")
    shutil.copytree(source, destination, ignore=ignored)


def clean_environment(temporary_root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX", "NODE_PATH"):
        environment.pop(key, None)
    # CLI execution always uses the explicit interpreter. Do not inherit an old
    # project's virtualenv/entrypoint through PATH during the optional npm build.
    environment["PATH"] = os.pathsep.join(
        part for part in environment.get("PATH", "").split(os.pathsep)
        if part and "Architecture Studio_Temp" not in part and "ArchCanvas" not in part
    )
    environment["PYTHONNOUSERSITE"] = "1"
    environment["npm_config_cache"] = str(temporary_root / "npm-cache")
    return environment


def run_checked(command: list[str], cwd: Path, environment: dict[str, str]) -> str:
    result = subprocess.run(
        command, cwd=cwd, env=environment, text=True, capture_output=True, timeout=120,
    )
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {command!r}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result.stdout


def python_command(source: Path, code: str, arguments: list[str] | None = None) -> list[str]:
    # -I disables environment/cwd injection; -S disables all site packages and
    # editable-install .pth processing. Only the copied formal src is added.
    bootstrap = f"import sys; sys.path.insert(0, {str(source)!r}); " + code
    return [str(Path(sys.executable).resolve()), "-I", "-S", "-B", "-c", bootstrap, *(arguments or [])]


def run_cli(copy: Path, arguments: list[str], environment: dict[str, str]) -> str:
    code = "import runpy; sys.argv[0] = 'archcanvas_cli'; runpy.run_module('archcanvas_cli', run_name='__main__')"
    return run_checked(python_command(copy / "src", code, arguments), copy, environment)


def manifest(copy: Path) -> list[dict[str, str]]:
    result = []
    for item in sorted(copy.rglob("*")):
        if item.is_file():
            result.append({
                "path": str(item.relative_to(copy)),
                "sha256": hashlib.sha256(item.read_bytes()).hexdigest(),
            })
    return result


def verify(project: Path, build: bool) -> tuple[Path, dict[str, object]]:
    if not (project / "src").is_dir():
        raise RuntimeError(f"Formal runtime source not yet present: {project / 'src'}")
    temporary = Path(tempfile.mkdtemp(prefix="archcanvas-independent-", dir="/tmp"))
    copy = temporary / "release"
    copy.mkdir()
    for name in RELEASE_ITEMS:
        item = project / name
        if item.is_symlink():
            raise RuntimeError(f"Distribution source contains a symlink: {item}")
        if item.is_dir():
            checked_copy(item, copy / name)
        elif item.is_file():
            shutil.copy2(item, copy / name)
    environment = clean_environment(temporary)
    report: dict[str, object] = {
        "schemaVersion": 1,
        "formalProject": str(project),
        "standaloneCopy": str(copy),
        "python": str(Path(sys.executable).resolve()),
        "pythonIsolation": "-I -S with only standalone src added",
        "sourceManifest": manifest(copy),
        "checks": [],
    }
    checks: list[dict[str, object]] = report["checks"]  # type: ignore[assignment]

    probe = (
        "import importlib.util, json; "
        f"names={MODULES!r}; "
        "print(json.dumps({name: importlib.util.find_spec(name).origin for name in names}))"
    )
    origins = json.loads(run_checked(python_command(copy / "src", probe), copy, environment))
    for name, origin in origins.items():
        if not origin or not Path(origin).resolve().is_relative_to(copy / "src"):
            raise RuntimeError(f"Module provenance mismatch for {name}: {origin}")
    checks.append({"name": "package-provenance", "passed": True, "origins": origins})

    capabilities = json.loads(run_cli(copy, ["capabilities"], environment))
    structural_runtime = capabilities.get("runtimeProfiles", {})
    if bool(capabilities.get("runtimeObservation")) != bool(structural_runtime.get("available")):
        raise RuntimeError("Runtime observation capability is not backed by its actual structural profile")
    if structural_runtime.get("available"):
        isolation = structural_runtime.get("isolation", {})
        if isolation.get("available") is not True or not isolation.get("checks") or not all(isolation["checks"].values()):
            raise RuntimeError("Available structural runtime lacks mandatory kernel isolation probe evidence")
    if capabilities.get("semanticWriteback"):
        scope = capabilities.get("semanticScope", {})
        if (
            capabilities.get("supportedIntents") != ["set_dropout_probability", "update_configuration", "replace_activation", "rebind_input"]
            or scope.get("operators") != {"Dropout": ["p"], "MultiheadAttention": ["dropout"]}
            or scope.get("origins") != ["explicit-float-literal", "unique-module-top-level-float-all-probability-readers"]
            or scope.get("httpCommit") != "managed-workspace-copy-only"
            or scope.get("runtimeVerified") is not False
            or capabilities.get("rebindScope") != {
                "operators": ["Identity", "Dropout", "ReLU", "GELU"],
                "control": "entry-forward-straight-line",
                "compatibility": "same-input-symbolic-shape-and-dtype",
                "runtimeVerified": False,
            }
            or capabilities.get("activationScope") != {
                "operators": ["ReLU", "GELU"], "constructors": "direct-no-argument",
                "structuralProfile": "root-straight-line-floating-input", "runtimeRequiredInStudio": True,
            }
            or capabilities.get("structuralRebindScope") != {
                "operators": ["Identity", "Dropout", "ReLU", "GELU", "MultiheadAttention"],
                "ports": ["input", "query", "key", "value", "attn_mask", "key_padding_mask"],
                "sourceArguments": ["positional-name", "keyword-name"], "control": "entry-forward-straight-line",
                "profile": "structural-verified", "inputs": "explicit-named-shape-dtype-seed-modes",
                "device": "cpu", "constructor": "source-default-only", "coverage": "frozen-samples-only", "runtimeRequired": True,
            }
        ):
            raise RuntimeError(f"Writeback capability is outside the independently tested M2/M3 scope: {scope}")
    provenance = capabilities.get("packageProvenance", {})
    if not provenance.get("independent") or Path(provenance.get("projectRoot", "")).resolve() != copy:
        raise RuntimeError(f"Capability receipt has wrong project provenance: {provenance}")
    for name in MODULES:
        reported_path = provenance.get("modules", {}).get(name)
        if not reported_path or Path(reported_path).resolve() != Path(origins[name]).resolve():
            raise RuntimeError(f"Capability receipt disagrees with independently resolved module: {name}")
    checks.append({"name": "capabilities", "passed": True, "receipt": capabilities})

    output_root = temporary / "analysis"
    output_root.mkdir()
    for fixture, entry in FIXTURES:
        output = output_root / f"{fixture}.json"
        stdout = run_cli(copy, [
            "analyze", "--root", str(copy / "fixtures" / fixture),
            "--entry", entry, "--output", str(output),
        ], environment)
        if not output.is_file():
            raise RuntimeError(f"Analysis did not create its output: {output}; stdout={stdout}")
        payload = json.loads(output.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not payload.get("nodes") or not payload.get("edges"):
            raise RuntimeError(f"Analysis output is not an object: {output}")
        checks.append({
            "name": f"analyze-{fixture}", "passed": True,
            "output": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        })

    for item in report["sourceManifest"]:
        source_file = copy / item["path"]
        if not source_file.is_file() or hashlib.sha256(source_file.read_bytes()).hexdigest() != item["sha256"]:
            raise RuntimeError(f"Static analysis changed copied source: {source_file}")
    checks.append({"name": "source-bytes-unchanged", "passed": True})

    if build:
        dependencies = project / "studio" / "node_modules"
        if not dependencies.is_dir():
            raise RuntimeError("Install project-local Studio dependencies before --build (npm ci in studio)")
        npm = shutil.which("npm", path=environment["PATH"])
        if npm is None:
            raise RuntimeError("npm is unavailable on the filtered system PATH")
        # npm's local .bin entries may be symlinks; preserve them inside the
        # copied dependency tree, which is separate from the source manifest.
        shutil.copytree(dependencies, copy / "studio" / "node_modules", symlinks=True)
        for item in (copy / "studio" / "node_modules").rglob("*"):
            if item.is_symlink() and not item.resolve().is_relative_to(copy / "studio" / "node_modules"):
                raise RuntimeError(f"External dependency symlink in copied build environment: {item}")
        output = run_checked([npm, "run", "build"], copy / "studio", environment)
        checks.append({
            "name": "studio-build", "passed": True,
            "dependencySource": str(dependencies),
            "scope": "standalone build using copied project-local installed dependencies",
            "output": output.strip(),
        })

    report["passed"] = True
    report_path = temporary / "independence-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report_path, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--build", action="store_true", help="also build Studio from copied local npm dependencies")
    arguments = parser.parse_args()
    try:
        report_path, report = verify(arguments.project.resolve(), arguments.build)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"passed": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({
        "passed": report["passed"], "report": str(report_path),
        "standaloneCopy": report["standaloneCopy"],
        "checks": [check["name"] for check in report["checks"]],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
