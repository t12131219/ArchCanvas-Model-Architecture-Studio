#!/usr/bin/env python3
"""Install the complete ArchCanvas Skill into one explicit project workspace.

This installer deliberately has a small scope.  It accepts a verified, already
unpacked local-beta release directory and copies that release into an embedded
``runtime/release`` directory beside a complete Skill copy.  The resulting
directory is portable: its launcher resolves the runtime relative to itself,
not relative to this checkout, a user's home directory, or an environment
variable.

No host-global directory is touched.  Existing Skill directories are never
replaced and all writes happen in a private staging directory before the final
directory rename.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import sys
import uuid

try:
    from .m5_beta_bundle import BUNDLE_MANIFEST, verify_directory
except ImportError:  # pragma: no cover - CLI execution from scripts/
    from m5_beta_bundle import BUNDLE_MANIFEST, verify_directory


CONTRACT_NAME = "archcanvas-install.json"
LAUNCHER = "scripts/archcanvas_runtime.py"
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+-beta\.[0-9]+\Z")
HOST_TARGETS = {
    "codex": Path(".agents/skills/archcanvas"),
    "claude-code": Path(".claude/skills/archcanvas"),
    "deepseek-harness": Path(".dsh/skills/archcanvas"),
}
HOST_CHOICES = tuple(HOST_TARGETS)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _normal_file(path: Path, label: str) -> None:
    if path.is_symlink():
        raise ValueError(f"{label} may not be a symlink: {path}")
    if not path.is_file():
        raise ValueError(f"{label} must be a regular file: {path}")


def _normal_directory(path: Path, label: str) -> None:
    if path.is_symlink():
        raise ValueError(f"{label} may not be a symlink: {path}")
    if not path.is_dir():
        raise ValueError(f"{label} must be a normal directory: {path}")


def _reject_link_ancestors(path: Path, label: str) -> Path:
    if ".." in path.parts:
        raise ValueError(f"{label} may not contain parent traversal")
    absolute = path.absolute()
    for component in reversed((absolute, *absolute.parents)):
        if component.is_symlink():
            raise ValueError(f"{label} may not follow symlink ancestors: {component}")
    return absolute


def _safe_relative(value: str) -> bool:
    parsed = PurePosixPath(value)
    return bool(value) and "\\" not in value and "\x00" not in value and not parsed.is_absolute() and ".." not in parsed.parts and str(parsed) == value


def _iter_regular_files(root: Path) -> list[Path]:
    _normal_directory(root, "tree root")
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symlinks are not allowed in an installation tree: {path}")
        if path.is_file():
            files.append(path)
        elif not path.is_dir():
            raise ValueError(f"special filesystem entries are not allowed: {path}")
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def _copy_tree(source: Path, destination: Path, *, exclude_prefixes: tuple[str, ...] = ()) -> None:
    """Copy a tree while rejecting links and special files."""
    _normal_directory(source, "source tree")
    destination.mkdir(parents=True, exist_ok=False)
    for source_path in _iter_regular_files(source):
        relative = source_path.relative_to(source)
        relative_posix = relative.as_posix()
        if any(relative_posix == prefix or relative_posix.startswith(prefix + "/") for prefix in exclude_prefixes):
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source_path.read_bytes())


def _release_metadata(release: Path, *, require_skill: bool = True) -> tuple[dict, dict]:
    """Verify release bytes and return its bundle/release metadata."""
    _reject_link_ancestors(release, "release directory")
    _normal_directory(release, "release directory")
    manifest_path = release / BUNDLE_MANIFEST
    _normal_file(manifest_path, "release bundle manifest")
    try:
        bundle_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("release bundle manifest is not valid JSON") from exc
    # verify_directory checks the complete inventory, release schema and all
    # artifact hashes.  It intentionally does not execute a model.
    verified = verify_directory(release)
    if verified != bundle_manifest:
        raise ValueError("release bundle manifest changed during verification")
    if require_skill:
        skill_entry = release / "skills/archcanvas/SKILL.md"
        _normal_file(skill_entry, "release Skill entry")
        if not any(row.get("path") == "skills/archcanvas/SKILL.md" for row in bundle_manifest.get("files", [])):
            raise ValueError("release bundle inventory does not contain the complete Skill")
    release_manifest_path = release / "docs/evidence/m5-beta-release-manifest.json"
    _normal_file(release_manifest_path, "release metadata")
    release_manifest = json.loads(release_manifest_path.read_text(encoding="utf-8"))
    version = bundle_manifest.get("version")
    if not isinstance(version, str) or not VERSION.fullmatch(version) or release_manifest.get("releaseVersion") != version:
        raise ValueError("release and bundle versions do not agree")
    return bundle_manifest, release_manifest


def _target_for(workspace: Path, host: str) -> Path:
    if host not in HOST_TARGETS:
        raise ValueError(f"unsupported host: {host}; choose one of {', '.join(HOST_CHOICES)}")
    _reject_link_ancestors(workspace, "workspace")
    _normal_directory(workspace, "workspace")
    # Resolve only after rejecting a symlink workspace.  The individual
    # ancestors below are checked again while preparing the destination.
    return workspace.resolve() / HOST_TARGETS[host]


def _prepare_parent(path: Path) -> None:
    """Create a target parent without following a symlink or replacing a file."""
    parts = list(path.parts)
    current = Path(parts[0]) if path.is_absolute() else Path()
    start = 1 if path.is_absolute() else 0
    for part in parts[start:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"installation parent may not be a symlink: {current}")
        if current.exists() and not current.is_dir():
            raise ValueError(f"installation parent is not a directory: {current}")
        current.mkdir(exist_ok=True)


def _split_link(raw: str) -> tuple[str, str]:
    """Return path and query/fragment suffix for a Markdown link target."""
    for marker in ("#", "?"):
        if marker in raw:
            left, right = raw.split(marker, 1)
            return left, marker + right
    return raw, ""


LINK_RE = re.compile(r"(\]\()(?P<target><[^>]+>|[^\s)]+)(?P<rest>[^)]*\))")


def _rewrite_skill_markdown(
    source_bytes: bytes,
    source_relative: str,
    release: Path,
    installed_skill: Path,
    unavailable: dict[str, str],
) -> bytes:
    """Bind docs links to the embedded release or a local unavailable note.

    Links internal to ``skills/archcanvas`` remain unchanged.  Links to the
    project ``docs`` tree are redirected into ``runtime/release`` when present;
    a missing historical file receives a local explanatory note so it cannot
    silently resolve into the development checkout.
    """
    text = source_bytes.decode("utf-8")
    source_parent = PurePosixPath(source_relative).parent

    def replace(match: re.Match[str]) -> str:
        original = match.group("target")
        angle = original.startswith("<") and original.endswith(">")
        target = original[1:-1] if angle else original
        path_part, suffix = _split_link(target)
        if not path_part or "\\" in path_part or path_part.startswith(("#", "/")) or "://" in path_part or path_part.startswith(("mailto:", "data:")):
            return match.group(0)
        normalized = posixpath.normpath(posixpath.join(source_parent.as_posix(), path_part))
        if normalized.startswith("../") or normalized == "..":
            return match.group(0)
        # Keep references within the Skill itself local to the copied Skill.
        if normalized == "skills/archcanvas" or normalized.startswith("skills/archcanvas/"):
            return match.group(0)
        # This package only rewrites references into the release's docs and
        # other checked-in resources.  An unresolved historical reference is
        # made explicit by a generated local note.
        candidate = release / normalized
        if candidate.is_file() and not candidate.is_symlink():
            destination = installed_skill / "runtime/release" / normalized
        else:
            unavailable_key = normalized
            unavailable[unavailable_key] = f"The local beta package did not include `{normalized}`."
            destination = installed_skill / "resources/unavailable" / normalized
        # source_relative is relative to release/skills/archcanvas; the actual
        # installed Markdown parent is relative to the Skill root.
        markdown_parent = installed_skill / PurePosixPath(source_relative).relative_to("skills/archcanvas").parent
        relative = os.path.relpath(destination, markdown_parent).replace(os.sep, "/")
        rendered = relative + suffix
        if angle:
            rendered = f"<{rendered}>"
        return match.group(1) + rendered + match.group("rest")

    return LINK_RE.sub(replace, text).encode("utf-8")


def _write_unavailable_notes(skill: Path, unavailable: dict[str, str]) -> None:
    for relative, reason in unavailable.items():
        destination = skill / "resources/unavailable" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            "# Local resource unavailable\n\n"
            "This link is intentionally local to the installed Skill. The beta "
            "release did not distribute the referenced historical evidence, so "
            "the installer did not resolve it through the development checkout.\n\n"
            f"{reason}\n",
            encoding="utf-8",
        )


def _copy_skill(release: Path, installed_skill: Path) -> None:
    source_skill = release / "skills/archcanvas"
    _normal_directory(source_skill, "release Skill")
    installed_skill.mkdir(parents=True, exist_ok=False)
    unavailable: dict[str, str] = {}
    for source_path in _iter_regular_files(source_skill):
        relative = source_path.relative_to(release).as_posix()
        skill_relative = source_path.relative_to(source_skill)
        destination = installed_skill / skill_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source_path.suffix.lower() == ".md":
            destination.write_bytes(_rewrite_skill_markdown(source_path.read_bytes(), relative, release, installed_skill, unavailable))
        else:
            destination.write_bytes(source_path.read_bytes())
    # Make the generated copy's resource/runtime binding discoverable to a
    # host user without changing the shared source Skill.  The contract is
    # deliberately named so a host or reviewer can inspect it directly.
    entry = installed_skill / "SKILL.md"
    entry_text = entry.read_text(encoding="utf-8")
    installation_note = (
        "## Project-local installation\n\n"
        "This project-local copy was installed with a verified embedded release. "
        "Inspect `archcanvas-install.json` for the bound version and hashes; "
        "the portable launcher is `scripts/archcanvas_runtime.py` and resolves "
        "`runtime/release` relative to this Skill. Host E2E remains `not-tested`.\n\n"
    )
    # Preserve YAML frontmatter at byte 0: host scanners parse metadata before
    # reading the Markdown body. Put the local note after its closing marker.
    if not entry_text.startswith("---\n"):
        raise ValueError("release Skill entry is missing YAML frontmatter")
    closing = entry_text.find("\n---", 4)
    if closing < 0:
        raise ValueError("release Skill entry has unterminated YAML frontmatter")
    split_at = closing + len("\n---")
    entry.write_text(entry_text[:split_at] + "\n\n" + installation_note + entry_text[split_at + 1:], encoding="utf-8")
    _write_unavailable_notes(installed_skill, unavailable)


LAUNCHER_SOURCE = '''#!/usr/bin/env python3
"""Portable ArchCanvas runtime launcher generated for this Skill install."""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
SKILL_DIRECTORY = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = SKILL_DIRECTORY / "runtime" / "release"
SOURCE_ROOT = RUNTIME_ROOT / "src"
if not RUNTIME_ROOT.is_dir() or not SOURCE_ROOT.is_dir():
    raise SystemExit("ArchCanvas embedded runtime is missing or damaged")
if "serve" in sys.argv[1:]:
    try:
        data_index = sys.argv.index("--data-dir")
        data_argument = sys.argv[data_index + 1]
    except (ValueError, IndexError):
        raise SystemExit("serve requires an explicit --data-dir outside the installed Skill")
    data_directory = Path(data_argument).expanduser().resolve()
    if data_directory == SKILL_DIRECTORY or data_directory.is_relative_to(SKILL_DIRECTORY):
        raise SystemExit("serve data directory must be outside the installed Skill")
sys.path.insert(0, str(SOURCE_ROOT))
from archcanvas_cli.__main__ import main  # noqa: E402

raise SystemExit(main())
'''


def _write_launcher(skill: Path) -> None:
    path = skill / LAUNCHER
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(LAUNCHER_SOURCE, encoding="utf-8")
    path.chmod(0o755)


def _inventory(skill: Path, *, exclude: set[str] = frozenset()) -> list[dict]:
    rows: list[dict] = []
    for path in _iter_regular_files(skill):
        relative = path.relative_to(skill).as_posix()
        if relative in exclude:
            continue
        data = path.read_bytes()
        rows.append({"path": relative, "sha256": digest(data), "bytes": len(data)})
    return rows


def _contract(
    *, skill: Path, metadata_skill_directory: Path, workspace: Path, host: str, bundle_manifest: dict, release_manifest: dict,
) -> dict:
    runtime = skill / "runtime/release"
    rows = _inventory(skill, exclude={CONTRACT_NAME})
    return {
        "schemaVersion": 1,
        "kind": "project-local-host-skill",
        "host": host,
        "scope": "explicit-workspace",
        "version": bundle_manifest["version"],
        "workspace": str(workspace),
        "skillDirectory": str(metadata_skill_directory),
        "runtimeRoot": "runtime/release",
        "embeddedSkillExcluded": "skills/archcanvas",
        "runtimeCommand": ["python3", "-I", "-B", LAUNCHER],
        "bundleManifestSha256": digest((runtime / BUNDLE_MANIFEST).read_bytes()),
        # ``bundleDigest`` is the digest of the embedded, filtered manifest;
        # the outer tarball is intentionally not reconstructed by this
        # project-local installer.
        "bundleDigest": digest((runtime / BUNDLE_MANIFEST).read_bytes()),
        "releaseManifestSha256": digest((runtime / "docs/evidence/m5-beta-release-manifest.json").read_bytes()),
        "hostE2E": "not-tested",
        "files": rows,
        "portable": True,
        "dependenciesInstalled": False,
    }


def verify_install(skill_directory: Path) -> dict:
    """Verify an installed Skill and return its portable runtime contract.

    ``skillDirectory`` and ``workspace`` in the on-disk contract are audit
    metadata.  Verification always derives the actual paths from this call so
    moving the complete Skill directory remains supported.
    """
    skill = Path(skill_directory)
    _reject_link_ancestors(skill, "installed Skill")
    _normal_directory(skill, "installed Skill")
    skill = skill.resolve()
    contract_path = skill / CONTRACT_NAME
    _normal_file(contract_path, "installation contract")
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("installation contract is not valid JSON") from exc
    required = {"schemaVersion", "kind", "host", "scope", "version", "workspace", "skillDirectory", "runtimeRoot", "embeddedSkillExcluded", "runtimeCommand", "bundleManifestSha256", "bundleDigest", "releaseManifestSha256", "hostE2E", "files", "portable", "dependenciesInstalled"}
    if not isinstance(contract, dict) or set(contract) != required:
        raise ValueError("installation contract fields are invalid")
    if contract["schemaVersion"] != 1 or contract["kind"] != "project-local-host-skill" or contract["scope"] != "explicit-workspace":
        raise ValueError("installation contract identity is invalid")
    if contract["host"] not in HOST_TARGETS or not isinstance(contract["version"], str) or not VERSION.fullmatch(contract["version"]):
        raise ValueError("installation contract host or version is invalid")
    if contract["runtimeRoot"] != "runtime/release" or contract["embeddedSkillExcluded"] != "skills/archcanvas" or contract["runtimeCommand"] != ["python3", "-I", "-B", LAUNCHER]:
        raise ValueError("installation contract runtime binding is invalid")
    if contract["hostE2E"] != "not-tested" or contract["portable"] is not True or contract["dependenciesInstalled"] is not False:
        raise ValueError("installation contract makes an unsupported host claim")
    runtime = skill / contract["runtimeRoot"]
    bundle_manifest, release_manifest = _release_metadata(runtime, require_skill=False)
    if bundle_manifest["version"] != contract["version"]:
        raise ValueError("installed runtime version differs from contract")
    if digest((runtime / BUNDLE_MANIFEST).read_bytes()) != contract["bundleManifestSha256"]:
        raise ValueError("installed bundle manifest hash differs from contract")
    if contract["bundleDigest"] != contract["bundleManifestSha256"]:
        raise ValueError("installed bundle digest differs from manifest hash")
    if digest((runtime / "docs/evidence/m5-beta-release-manifest.json").read_bytes()) != contract["releaseManifestSha256"]:
        raise ValueError("installed release manifest hash differs from contract")
    rows = contract["files"]
    if not isinstance(rows, list) or any(not isinstance(row, dict) or set(row) != {"path", "sha256", "bytes"} for row in rows):
        raise ValueError("installation file inventory is invalid")
    expected = {row["path"]: row for row in rows}
    if len(expected) != len(rows) or CONTRACT_NAME in expected:
        raise ValueError("installation file inventory has duplicate or contract entries")
    observed = set()
    for path in _iter_regular_files(skill):
        relative = path.relative_to(skill).as_posix()
        if relative == CONTRACT_NAME:
            continue
        observed.add(relative)
        row = expected.get(relative)
        if row is None or not _safe_relative(relative) or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256"))) or type(row.get("bytes")) is not int or digest(path.read_bytes()) != row["sha256"] or path.stat().st_size != row["bytes"]:
            raise ValueError(f"installed file inventory mismatch: {relative}")
    if observed != set(expected):
        raise ValueError("installed file inventory is incomplete")
    launcher = skill / LAUNCHER
    _normal_file(launcher, "portable runtime launcher")
    # Recheck links after relocation; none may resolve through the original
    # project because every rewritten docs target is inside this Skill.
    for markdown in skill.rglob("*.md"):
        if "runtime" in markdown.relative_to(skill).parts:
            continue
        text = markdown.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            target = match.group("target")
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            target, _ = _split_link(target)
            if not target or target.startswith(("#", "/")) or "://" in target or target.startswith(("mailto:", "data:")):
                continue
            candidate = (markdown.parent / target).resolve()
            if not candidate.is_relative_to(skill) or not candidate.is_file():
                raise ValueError(f"installed Skill link is not portable: {markdown}: {target}")
    return {
        "status": "passed",
        "host": contract["host"],
        "version": contract["version"],
        "skillDirectory": str(skill.resolve()),
        "runtimeRoot": str(runtime.resolve()),
        "runtimeCommand": [sys.executable, "-I", "-B", str(launcher.resolve())],
        "workspaceMetadata": contract["workspace"],
        "embeddedSkillExcluded": contract["embeddedSkillExcluded"],
        "bundleManifestSha256": contract["bundleManifestSha256"],
        "bundleDigest": contract["bundleDigest"],
        "releaseManifestSha256": contract["releaseManifestSha256"],
        "hostE2E": "not-tested",
        "dependenciesInstalled": False,
        "fileCount": len(expected),
        "release": release_manifest,
    }


def install_host(release_directory: Path, workspace: Path, host: str) -> dict:
    """Install one complete Skill into an explicit project workspace."""
    release = Path(release_directory)
    bundle_manifest, release_manifest = _release_metadata(release)
    workspace = Path(workspace)
    target = _target_for(workspace, host)
    parent = target.parent
    _prepare_parent(parent)
    if target.exists() or target.is_symlink():
        raise ValueError(f"refusing to overwrite existing Skill directory: {target}")
    staging = parent / f".archcanvas-install-{uuid.uuid4().hex}"
    staging.mkdir(mode=0o700)
    try:
        skill = staging / "archcanvas"
        _copy_skill(release, skill)
        runtime = skill / "runtime/release"
        runtime.parent.mkdir(parents=True, exist_ok=True)
        # The host Skill is copied separately above.  Excluding the source
        # Skill from the embedded release prevents recursive host scanners
        # (especially Codex) from discovering a second archcanvas Skill.
        _copy_tree(release, runtime, exclude_prefixes=("skills/archcanvas",))
        embedded_manifest = dict(bundle_manifest)
        embedded_manifest["files"] = [
            row for row in bundle_manifest["files"]
            if row["path"] != "skills/archcanvas" and not row["path"].startswith("skills/archcanvas/")
        ]
        (runtime / BUNDLE_MANIFEST).write_bytes(encode(embedded_manifest))
        _write_launcher(skill)
        contract = _contract(skill=skill, metadata_skill_directory=target, workspace=workspace.resolve(), host=host, bundle_manifest=bundle_manifest, release_manifest=release_manifest)
        (skill / CONTRACT_NAME).write_bytes(encode(contract))
        # Validate the fully materialized staged tree before making it visible.
        verify_install(skill)
        if target.exists() or target.is_symlink():
            raise ValueError("installation target appeared during staging; refusing to replace it")
        skill.rename(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    result = verify_install(target)
    result.update({"status": "passed", "installed": str(target), "scope": "explicit-workspace", "hostE2E": "not-tested"})
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    install_parser = commands.add_parser("install", help="Install from an independently verified release directory")
    install_parser.add_argument("--release-dir", "--release", dest="release", type=Path, required=True)
    install_parser.add_argument("--host", choices=HOST_CHOICES, required=True)
    roots = install_parser.add_mutually_exclusive_group(required=True)
    roots.add_argument("--workspace", type=Path)
    roots.add_argument("--prefix", type=Path, help="Explicit project workspace alias")
    verify_parser = commands.add_parser("verify", help="Verify one moved or installed Skill directory")
    verify_parser.add_argument("--skill-directory", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    options = _parser().parse_args(argv)
    try:
        if options.command == "install":
            workspace = options.workspace or options.prefix
            result = install_host(options.release, workspace, options.host)
        else:
            result = verify_install(options.skill_directory)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
