#!/usr/bin/env python3
"""Create, verify and install a local ArchCanvas beta-preview bundle.

No network, global environment, host Skill directory or public registry is
modified. Every installation uses an explicit local prefix with immutable
version directories; activation and rollback change only its current pointer.
"""
from __future__ import annotations

import argparse
import datetime
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

try:
    from .check_m5_beta_release import validate, validate_schema
except ImportError:
    from check_m5_beta_release import validate, validate_schema


BUNDLE_MANIFEST = "BUNDLE-MANIFEST.json"
SOURCE_DIRS = ("src", "studio/dist", "studio/src", "fixtures", "skills", "schemas", "visual-assets",
               "docs/evidence/m5-beta-preflight-mlp-v1", "docs/evidence/m5-beta-preflight-transformer-v1",
               "docs/evidence/m5-beta2-preflight-mlp-v1", "docs/evidence/m5-beta2-preflight-transformer-v1")
SOURCE_FILES = (
    "README.md", "AGENTS.md", "THIRD_PARTY_NOTICES.md", "pyproject.toml", "requirements.lock", "requirements-runtime.lock",
    "studio/package.json", "studio/package-lock.json", "studio/tsconfig.json", "studio/vite.config.ts",
    "studio/index.html", "docs/m5-beta-release.md", "docs/capability-matrix.md",
    "docs/m4-routing-user-simulation-v2.md", "docs/m5-demo-export.md",
    "docs/evidence/m5-beta-release-manifest.json", "scripts/check_m5_beta_release.py",
    "scripts/m5_beta_bundle.py", "scripts/m5_beta_preflight.py", "scripts/export_canvas.mjs",
    "tests/test_m5_beta_release.py", "tests/test_m5_beta_bundle.py", "tests/test_m5_beta_preflight.py",
)
CURRENT_HELPERS = ("scripts/atomic_export.mjs", "scripts/canvas_bridge.mjs")
LIFECYCLE_FILES = (
    "scripts/m5_host_install.py", "scripts/m5_host_smoke.py", "scripts/m5_host_uninstall.py",
    "scripts/m5_reliability_smoke.py", "tests/test_m5_host_install.py", "tests/test_m5_host_smoke.py",
    "tests/test_m5_host_uninstall.py", "tests/test_m5_reliability_smoke.py",
    "docs/evidence/m5-beta2-preflight-mlp-v1/receipt.json",
    "docs/evidence/m5-beta2-preflight-transformer-v1/receipt.json",
)
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+-beta\.[0-9]+")
MAX_BYTES = 500 * 1024 * 1024
OPTIONAL_EVIDENCE_FILES = ("docs/evidence/m5-host-availability-v1.json",)


def required_release_files(version: str) -> set[str]:
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ValueError("invalid release version")
    numbers = tuple(int(part) for part in version.replace("-beta.", ".").split("."))
    # beta.1 is immutable and predates the host lifecycle utilities. Its own
    # recorded inventory remains valid for installation and rollback.
    return set(SOURCE_FILES) | (set(LIFECYCLE_FILES) if numbers >= (0, 1, 0, 2) else set()) | (set(CURRENT_HELPERS) if numbers >= (0, 1, 0, 3) else set())


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def valid_relative(path_text: str) -> bool:
    path = PurePosixPath(path_text)
    return bool(path_text) and "\\" not in path_text and "\x00" not in path_text and not path.is_absolute() and ".." not in path.parts and str(path) == path_text


def source_paths(root: Path) -> list[Path]:
    paths: set[Path] = set()
    for directory in SOURCE_DIRS:
        start = root / directory
        if not start.is_dir() or start.is_symlink():
            raise ValueError(f"required source directory missing or symlink: {directory}")
        for path in start.rglob("*"):
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            if path.is_symlink():
                raise ValueError(f"bundle source symlink forbidden: {path}")
            if path.is_file():
                paths.add(path)
    for name in SOURCE_FILES + LIFECYCLE_FILES:
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"required source file missing or symlink: {name}")
        paths.add(path)
    for path in (root / "docs").glob("*.md"):
        if path.is_symlink():
            raise ValueError(f"bundle documentation symlink forbidden: {path}")
        paths.add(path)
    for name in OPTIONAL_EVIDENCE_FILES:
        path = root / name
        if path.is_symlink():
            raise ValueError(f"bundle optional evidence symlink forbidden: {path}")
        if path.is_file():
            paths.add(path)
    for name in CURRENT_HELPERS:
        path = root / name
        if path.is_symlink():
            raise ValueError(f"bundle helper symlink forbidden: {name}")
        if path.is_file():
            paths.add(path)
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def stage_current_candidate(root: Path, staging: Path, version: str) -> Path:
    """Materialize a release manifest for the current development bytes.

    Historical Beta manifests intentionally remain immutable.  This helper
    creates an isolated source tree whose release metadata is bound to the
    current Studio assets, so pack/verify/install can be rerun without editing
    the historical receipt in the formal checkout.
    """
    root, staging = Path(root).resolve(), Path(staging).resolve()
    if not VERSION.fullmatch(version):
        raise ValueError("candidate version must use beta semantic version")
    if any(staging.is_relative_to(root / directory) for directory in SOURCE_DIRS):
        raise ValueError("candidate staging must not be inside packaged source directories")
    if staging.exists():
        raise ValueError(f"candidate staging directory already exists: {staging}")
    staging.mkdir(parents=True)
    try:
        for source in source_paths(root):
            destination = staging / source.relative_to(root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        for name in CURRENT_HELPERS:
            source = root / name
            if source.is_file() and not source.is_symlink():
                destination = staging / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        metadata_path = staging / "docs/evidence/m5-beta-release-manifest.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["releaseVersion"] = version
        metadata["releaseId"] = f"archcanvas-m5-beta-{version}"
        metadata["generatedAt"] = datetime.date.today().isoformat()
        try:
            metadata["build"]["gitCommit"] = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL,
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            # A source archive can be candidate-built without its .git folder;
            # retain the checked-in commit only if it is already valid.
            pass
        metadata["build"]["workingTree"] = "dirty-uncommitted"
        artifacts = []
        for path in sorted((staging / "studio/dist").rglob("*")):
            if path.is_file():
                relative = path.relative_to(staging).as_posix()
                role = "entrypoint" if relative == "studio/dist/index.html" else "stylesheet" if path.suffix == ".css" else "javascript"
                artifacts.append({"path": relative, "sha256": digest(path.read_bytes()), "role": role})
        schema = staging / "schemas/m5-beta-release.schema.json"
        artifacts.append({"path": schema.relative_to(staging).as_posix(), "sha256": digest(schema.read_bytes()), "role": "schema"})
        metadata["artifacts"] = artifacts
        metadata["knownLimitations"] = [
            "Local unsigned beta-preview candidate; public Beta publication and host certification remain pending.",
            "The current runtime catalog is discovered by doctor; this candidate does not execute user models.",
            "Three-host client E2E, human research tasks, performance and publication-size review remain not-tested.",
            "Unknown source regions remain source-backed opaque boundaries until independent lowering evidence exists.",
        ]
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return staging
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def pack(root: Path, output: Path, version: str | None = None) -> dict:
    root = root.resolve()
    release = json.loads((root / "docs/evidence/m5-beta-release-manifest.json").read_text(encoding="utf-8"))
    errors = validate(release, root)
    if errors:
        raise ValueError("release scaffold invalid: " + "; ".join(errors))
    bundle_version = version or release["releaseVersion"]
    if not VERSION.fullmatch(bundle_version):
        raise ValueError("bundle version must use beta semantic version")
    if bundle_version != release["releaseVersion"]:
        raise ValueError("bundle version must match release manifest version")
    if output.exists():
        raise ValueError(f"refusing to replace an existing bundle: {output}")
    contents = {path.relative_to(root).as_posix(): path.read_bytes() for path in source_paths(root)}
    # Older frozen bundles retain their original inventories. New checkouts
    # bind every helper imported by the current runtime/export entry points.
    for name in CURRENT_HELPERS:
        if (root / name).is_file(): contents[name] = (root / name).read_bytes()
    manifest = {
        "schemaVersion": 1, "product": "archcanvas", "kind": "local-beta-preview",
        "version": bundle_version, "releaseMetadataVersion": release["releaseVersion"],
        "status": "in_progress", "gates": release["gates"],
        "hostE2E": {row["host"]: row["e2e"] for row in release["hostMatrix"]},
        "dependenciesBundled": False, "modelExecution": False,
        "releaseManifestSha256": digest(contents["docs/evidence/m5-beta-release-manifest.json"]),
        "files": [{"path": name, "sha256": digest(data), "bytes": len(data)} for name, data in contents.items()],
    }
    # Reject mixed snapshots if an editor changed an input while it was read.
    for name, data in contents.items():
        if (root / name).read_bytes() != data:
            raise ValueError(f"source changed during pack: {name}; retry after edits settle")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for name, data in {**contents, BUNDLE_MANIFEST: encode(manifest)}.items():
                    info = tarfile.TarInfo(f"archcanvas-{bundle_version}/{name}")
                    info.size, info.mode, info.mtime = len(data), 0o644, 0
                    archive.addfile(info, io.BytesIO(data))
    return {"status": "passed", "bundle": str(output), "sha256": digest(output.read_bytes()),
            "version": bundle_version, "fileCount": len(contents), "bytes": output.stat().st_size,
            "statusScope": "local-beta-preview-not-public-release"}


def validate_bundle_metadata(manifest: dict) -> None:
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != 1 or manifest.get("product") != "archcanvas" or manifest.get("kind") != "local-beta-preview":
        raise ValueError("unsupported bundle identity")
    if not isinstance(manifest.get("version"), str) or not VERSION.fullmatch(manifest["version"]):
        raise ValueError("invalid bundle version")
    if manifest.get("status") != "in_progress" or manifest.get("gates") != {"m4": "partial", "m5": "in_progress"}:
        raise ValueError("beta preview must retain partial/in_progress stage status")
    if manifest.get("hostE2E") != {"codex": "not-tested", "claude-code": "not-tested", "deepseek-harness": "not-tested"}:
        raise ValueError("beta preview cannot certify uncollected host E2E")
    if manifest.get("dependenciesBundled") is not False or manifest.get("modelExecution") is not False:
        raise ValueError("bundle cannot claim bundled dependencies or executed models")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise ValueError("bundle inventory is required")
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "bytes"}:
            raise ValueError("invalid bundle inventory row")
        if not isinstance(row["path"], str) or not valid_relative(row["path"]) or row["path"] == BUNDLE_MANIFEST:
            raise ValueError("invalid bundle inventory path")
        if not re.fullmatch(r"[0-9a-f]{64}", str(row["sha256"])) or type(row["bytes"]) is not int or row["bytes"] < 0:
            raise ValueError("invalid bundle hash or byte count")
    if len({row["path"] for row in rows}) != len(rows):
        raise ValueError("duplicate bundle inventory row")
    names = {row["path"] for row in rows} | {BUNDLE_MANIFEST}
    for name in names:
        if any(str(parent) in names for parent in PurePosixPath(name).parents if str(parent) != "."):
            raise ValueError(f"bundle file/directory prefix collision: {name}")


def validate_release_contents(contents: dict[str, bytes]) -> dict:
    required = set(SOURCE_FILES)
    missing = required - contents.keys()
    if missing:
        raise ValueError(f"bundle lacks required release files: {sorted(missing)}")
    release = json.loads(contents["docs/evidence/m5-beta-release-manifest.json"])
    schema = json.loads(contents["schemas/m5-beta-release.schema.json"])
    if not isinstance(release, dict) or not isinstance(schema, dict):
        raise ValueError("bundle release metadata and schema must be objects")
    errors = validate_schema(release, schema)
    if errors:
        raise ValueError("bundle release schema invalid: " + "; ".join(errors))
    missing = required_release_files(release["releaseVersion"]) - contents.keys()
    if missing:
        raise ValueError(f"bundle lacks version-required release files: {sorted(missing)}")
    if (release.get("stage") != "M5-beta" or release.get("status") != "in_progress"
            or release.get("gates") != {"m4": "partial", "m5": "in_progress"}
            or not isinstance(release.get("build"), dict)
            or release["build"].get("runtimeSource") != "formal-project"
            or release["build"].get("prototypeDependency") not in (None, "forbidden")):
        raise ValueError("bundle release metadata violates formal preview scope")
    if release.get("releaseId") != f"archcanvas-m5-beta-{release.get('releaseVersion')}":
        raise ValueError("bundle release id and version differ")
    rows = release.get("hostMatrix", [])
    if (not isinstance(rows, list) or len(rows) != 3 or not all(isinstance(row, dict) and isinstance(row.get("host"), str) for row in rows)
            or {row["host"] for row in rows} != {"codex", "claude-code", "deepseek-harness"}
            or any(row.get("e2e") != "not-tested" for row in rows)):
        raise ValueError("bundle release matrix needs exactly three unique hosts")
    artifacts = release.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("bundle release artifacts must be a non-empty list")
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str) or not isinstance(artifact.get("sha256"), str):
            raise ValueError("bundle release artifact row is malformed")
        name = artifact["path"]
        if not valid_relative(name):
            raise ValueError("bundle release artifact path is malformed")
        if name not in contents or digest(contents[name]) != artifact["sha256"]:
            raise ValueError(f"inner release artifact hash mismatch: {name}")
    return release


def read_bundle(bundle: Path) -> tuple[dict, dict[str, bytes]]:
    contents: dict[str, bytes] = {}
    package_roots: set[str] = set()
    total = 0
    with tarfile.open(bundle, mode="r:gz") as archive:
        for member in archive:
            if not member.isfile() or not valid_relative(member.name):
                raise ValueError(f"non-regular or unsafe archive member: {member.name}")
            parts = PurePosixPath(member.name).parts
            if len(parts) < 2:
                raise ValueError("all bundle members require one package root")
            package_roots.add(parts[0])
            name = PurePosixPath(*parts[1:]).as_posix()
            if name in contents:
                raise ValueError(f"duplicate archive path: {name}")
            total += member.size
            if total > MAX_BYTES or len(contents) >= 5000:
                raise ValueError("bundle exceeds bounded size or file count")
            reader = archive.extractfile(member)
            if reader is None:
                raise ValueError(f"unreadable archive file: {name}")
            contents[name] = reader.read()
    if len(package_roots) != 1 or BUNDLE_MANIFEST not in contents:
        raise ValueError("bundle needs one root and a bound manifest")
    manifest = json.loads(contents.pop(BUNDLE_MANIFEST))
    validate_bundle_metadata(manifest)
    version = manifest.get("version", "")
    if not VERSION.fullmatch(version) or package_roots != {f"archcanvas-{version}"}:
        raise ValueError("archive root does not match bundle version")
    rows = manifest.get("files", [])
    if len({row["path"] for row in rows}) != len(rows) or {row["path"] for row in rows} != set(contents):
        raise ValueError("inventory differs from complete archive contents")
    for row in rows:
        name = row["path"]
        if not valid_relative(name) or digest(contents[name]) != row["sha256"] or len(contents[name]) != row["bytes"]:
            raise ValueError(f"bundle inventory/hash mismatch: {name}")
    if digest(contents.get("docs/evidence/m5-beta-release-manifest.json", b"")) != manifest.get("releaseManifestSha256"):
        raise ValueError("release manifest hash mismatch")
    release = validate_release_contents(contents)
    if release.get("releaseVersion") != manifest["version"] or manifest.get("releaseMetadataVersion") != manifest["version"]:
        raise ValueError("bundle and release metadata versions differ")
    return manifest, contents


def write_directory(destination: Path, manifest: dict, contents: dict[str, bytes]) -> None:
    if destination.exists():
        raise ValueError(f"refusing to replace extraction directory: {destination}")
    destination.mkdir(parents=True)
    for name, data in contents.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (destination / BUNDLE_MANIFEST).write_bytes(encode(manifest))


def verify_directory(directory: Path) -> dict:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("installed release root must be a normal directory")
    if (directory / BUNDLE_MANIFEST).is_symlink():
        raise ValueError("installed manifest may not be a symlink")
    manifest = json.loads((directory / BUNDLE_MANIFEST).read_text(encoding="utf-8"))
    validate_bundle_metadata(manifest)
    expected = {row["path"]: row for row in manifest["files"]}
    observed = set()
    contents = {}
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"installed version contains symlink: {path}")
        if path.is_file():
            name = path.relative_to(directory).as_posix()
            if name == BUNDLE_MANIFEST:
                continue
            observed.add(name)
            data = path.read_bytes()
            contents[name] = data
            if name not in expected or digest(data) != expected[name]["sha256"] or len(data) != expected[name]["bytes"]:
                raise ValueError(f"installed inventory mismatch: {name}")
    if observed != set(expected):
        raise ValueError("installed version inventory is incomplete")
    validate_release_contents(contents)
    if digest((directory / "docs/evidence/m5-beta-release-manifest.json").read_bytes()) != manifest.get("releaseManifestSha256"):
        raise ValueError("installed release manifest hash mismatch")
    release = json.loads((directory / "docs/evidence/m5-beta-release-manifest.json").read_text(encoding="utf-8"))
    if release.get("releaseVersion") != manifest["version"] or manifest.get("releaseMetadataVersion") != manifest["version"]:
        raise ValueError("installed bundle and release metadata versions differ")
    errors = validate(release, directory)
    if errors:
        raise ValueError("installed release metadata invalid: " + "; ".join(errors))
    return manifest


def standalone_analysis(directory: Path) -> dict:
    environment = os.environ.copy()
    for key in ("PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX", "NODE_PATH"):
        environment.pop(key, None)
    environment["PYTHONPATH"] = str(directory / "src")
    environment["PYTHONNOUSERSITE"] = "1"
    results = []
    for fixture, entry in (("mlp", "model:MLP"), ("residual_cnn", "model:ResidualCNN"), ("transformer", "model:Transformer")):
        run = subprocess.run([sys.executable, "-S", "-B", "-m", "archcanvas_cli", "analyze", "--root", str(directory / "fixtures" / fixture), "--entry", entry],
                             cwd=directory, env=environment, text=True, capture_output=True, timeout=30)
        if run.returncode:
            raise ValueError(f"standalone analysis failed: {fixture}: {run.stderr}")
        architecture = json.loads(run.stdout)
        if not architecture.get("nodes") or not architecture.get("sourceDigest"):
            raise ValueError(f"standalone analysis lacks source facts: {fixture}")
        results.append({"fixture": fixture, "entry": entry, "nodeCount": len(architecture["nodes"]), "sourceDigest": architecture["sourceDigest"]})
    origin = subprocess.run([sys.executable, "-S", "-B", "-c", "import archcanvas_cli,archcanvas_python,json; print(json.dumps([archcanvas_cli.__file__,archcanvas_python.__file__]))"],
                            cwd=directory, env=environment, text=True, capture_output=True, timeout=10)
    origins = json.loads(origin.stdout)
    if origin.returncode or not all(Path(path).resolve().is_relative_to(directory / "src") for path in origins):
        raise ValueError("standalone package provenance mismatch")
    return {"status": "passed", "pythonIsolation": "-S -B, explicit standalone PYTHONPATH", "origins": origins,
            "fixtures": results, "modelExecution": False}


def verify(bundle: Path, extract_to: Path | None = None, analyze: bool = True) -> dict:
    manifest, contents = read_bundle(bundle)
    if extract_to is None:
        temporary = Path(tempfile.mkdtemp(prefix="archcanvas-m5-beta-"))
        extract_to = temporary / "release"
    write_directory(extract_to, manifest, contents)
    verify_directory(extract_to)
    return {"status": "passed", "bundle": str(bundle), "sha256": digest(bundle.read_bytes()),
            "version": manifest["version"], "fileCount": len(contents), "standaloneDirectory": str(extract_to),
            "analysis": standalone_analysis(extract_to) if analyze else {"status": "not-run"}}


def prefix_paths(prefix: Path) -> tuple[Path, Path]:
    if prefix.is_symlink():
        raise ValueError("installation prefix may not be a symlink")
    prefix = prefix.resolve()
    prefix.mkdir(parents=True, exist_ok=True)
    releases = prefix / "releases"
    if releases.is_symlink():
        raise ValueError("releases directory may not be a symlink")
    releases.mkdir(exist_ok=True)
    return prefix, releases


def activate(prefix: Path, version: str) -> dict:
    if not VERSION.fullmatch(version):
        raise ValueError("activation version must use beta semantic version")
    prefix, releases = prefix_paths(prefix)
    directory = releases / version
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("requested local version is not installed")
    manifest = verify_directory(directory)
    if manifest["version"] != version:
        raise ValueError("installed version identity mismatch")
    pointer = prefix / "current"
    if pointer.exists() and not pointer.is_symlink():
        raise ValueError("current path is user content; refusing to replace")
    previous = None
    state_file = prefix / "activation.json"
    if state_file.is_symlink():
        raise ValueError("activation.json may not be a symlink")
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("activation.json is not a recognized local installation receipt") from exc
        if (not isinstance(state, dict) or set(state) != {"schemaVersion", "currentVersion", "previousVersion", "scope", "relativeTarget"}
                or state.get("schemaVersion") != 1 or state.get("scope") != "explicit-local-prefix"
                or not VERSION.fullmatch(str(state.get("currentVersion", "")))
                or state.get("relativeTarget") != f"releases/{state.get('currentVersion')}"
                or state.get("previousVersion") is not None and not VERSION.fullmatch(str(state["previousVersion"]))):
            raise ValueError("activation.json is not a recognized local installation receipt")
        if not pointer.is_symlink() or os.readlink(pointer) != state["relativeTarget"]:
            raise ValueError("current pointer differs from registered activation receipt")
        previous = state["currentVersion"]
    elif pointer.is_symlink():
        raise ValueError("current symlink is not registered; refusing to replace user content")
    temporary_pointer = prefix / ".current-next"
    if temporary_pointer.exists() or temporary_pointer.is_symlink():
        raise ValueError("stale .current-next pointer requires explicit cleanup")
    state_temp = prefix / ".activation-next.json"
    if state_temp.exists() or state_temp.is_symlink():
        raise ValueError("stale .activation-next.json requires explicit cleanup")
    state = {"schemaVersion": 1, "currentVersion": version, "previousVersion": previous,
             "scope": "explicit-local-prefix", "relativeTarget": f"releases/{version}"}
    # Exclusive creation prevents following a stale or concurrent symlink.
    with state_temp.open("xb") as file:
        file.write(encode(state))
    try:
        temporary_pointer.symlink_to(Path("releases") / version, target_is_directory=True)
    except OSError:
        state_temp.unlink()
        raise
    temporary_pointer.replace(pointer)
    state_temp.replace(state_file)
    return {"status": "passed", "prefix": str(prefix), "activeDirectory": str(directory), **state}


def install(bundle: Path, prefix: Path, activate_now: bool = False) -> dict:
    manifest, contents = read_bundle(bundle)
    prefix, releases = prefix_paths(prefix)
    destination = releases / manifest["version"]
    if destination.is_symlink():
        raise ValueError("version directory may not be a symlink")
    if destination.exists():
        installed = verify_directory(destination)
        if installed != manifest:
            raise ValueError("same version has different bytes; use a new version")
    else:
        # Materialize and validate in our exclusive staging directory. Failed
        # extraction never leaves a version directory that looks installed.
        staging_root = Path(tempfile.mkdtemp(prefix=f".install-{manifest['version']}-", dir=releases))
        staged_release = staging_root / "release"
        try:
            write_directory(staged_release, manifest, contents)
            verify_directory(staged_release)
            if destination.exists() or destination.is_symlink():
                raise ValueError("version appeared during installation; retry after inspection")
            staged_release.rename(destination)
        finally:
            shutil.rmtree(staging_root)
    activation = activate(prefix, manifest["version"]) if activate_now else {"status": "not-run"}
    return {"status": "passed", "installedDirectory": str(destination), "version": manifest["version"],
            "activation": activation, "dependenciesInstalled": False, "hostSkillInstalled": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    candidate_parser = commands.add_parser("candidate", help="Stage current bytes, bind a new manifest, pack and independently verify")
    candidate_parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    candidate_parser.add_argument("--output", type=Path, required=True)
    candidate_parser.add_argument("--version", required=True)
    pack_parser = commands.add_parser("pack", help="Create a new local preview archive from settled formal bytes")
    pack_parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    pack_parser.add_argument("--output", type=Path, required=True)
    pack_parser.add_argument("--version")
    verify_parser = commands.add_parser("verify", help="Check complete inventory and analyze three fixtures independently")
    verify_parser.add_argument("--bundle", type=Path, required=True)
    verify_parser.add_argument("--extract-to", type=Path)
    install_parser = commands.add_parser("install", help="Install/upgrade into an explicit local prefix without dependencies")
    install_parser.add_argument("--bundle", type=Path, required=True)
    install_parser.add_argument("--prefix", type=Path, required=True)
    install_parser.add_argument("--activate", action="store_true")
    for action in ("activate", "rollback"):
        action_parser = commands.add_parser(action, help=f"{action.capitalize()} an already verified local version")
        action_parser.add_argument("--prefix", type=Path, required=True)
        action_parser.add_argument("--version", required=True)
    args = parser.parse_args()
    try:
        if args.command == "candidate":
            if args.output.exists():
                raise ValueError(f"refusing to replace an existing bundle: {args.output}")
            with tempfile.TemporaryDirectory(prefix="archcanvas-candidate-") as temporary:
                staging = stage_current_candidate(args.project_root, Path(temporary) / "source", args.version)
                packed = pack(staging, args.output, args.version)
                checked = verify(args.output, Path(temporary) / "verified")
                result = {**packed, "verification": checked, "historicalManifestChanged": False}
        elif args.command == "pack":
            result = pack(args.project_root, args.output, args.version)
        elif args.command == "verify":
            result = verify(args.bundle, args.extract_to)
        elif args.command == "install":
            result = install(args.bundle, args.prefix, args.activate)
        else:
            result = activate(args.prefix, args.version)
            result["action"] = args.command
    except (ValueError, KeyError, OSError, json.JSONDecodeError, tarfile.TarError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
