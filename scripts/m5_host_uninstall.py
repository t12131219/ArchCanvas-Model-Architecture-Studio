#!/usr/bin/env python3
"""Remove one verified project-local Skill from host discovery, recoverably.

``preview`` binds the current installation bytes. ``uninstall`` requires that
digest, verifies again, and atomically moves the complete Skill to a private
archive in the selected workspace. ``restore`` verifies the archive and moves
it back only if the host discovery path is absent. No release bytes, global
host configuration, external data directory or other Skill is removed.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import sys
import uuid

try:
    from .m5_host_install import (
        CONTRACT_NAME, HOST_CHOICES, _inventory, _normal_directory,
        _normal_file, _prepare_parent, _reject_link_ancestors, _target_for,
        digest, encode, verify_install,
    )
except ImportError:
    from m5_host_install import (
        CONTRACT_NAME, HOST_CHOICES, _inventory, _normal_directory,
        _normal_file, _prepare_parent, _reject_link_ancestors, _target_for,
        digest, encode, verify_install,
    )


ARCHIVE_ROOT = Path(".archcanvas/host-skill-archives")
ARCHIVE_RECEIPT = "archive.json"
ARCHIVE_SCHEMA = "archcanvas-project-local-skill-archive/1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def installed_snapshot(skill: Path) -> dict:
    """Include the contract as well as all inventoried bytes in the token."""
    checked = verify_install(skill)
    rows = _inventory(skill)
    return {
        "host": checked["host"], "version": checked["version"],
        "installationSha256": digest(encode(rows)), "files": rows,
        "bundleManifestSha256": checked["bundleManifestSha256"],
        "releaseManifestSha256": checked["releaseManifestSha256"],
    }


def preview(workspace: Path, host: str) -> dict:
    target = _target_for(Path(workspace), host)
    snapshot = installed_snapshot(target)
    if snapshot["host"] != host:
        raise ValueError("installed Skill host differs from selected discovery path")
    return {
        "status": "passed", "action": "preview-recoverable-uninstall",
        "scope": "explicit-workspace", "host": host,
        "workspace": str(Path(workspace).resolve()), "skillDirectory": str(target),
        "version": snapshot["version"],
        "installationSha256": snapshot["installationSha256"],
        "fileCount": len(snapshot["files"]),
        "archiveRoot": str(Path(workspace).resolve() / ARCHIVE_ROOT),
        "deletesFiles": False, "writesPerformed": False,
        "externalDataChanged": False, "hostE2E": "not-tested",
    }


def _checked_token(value: str) -> None:
    import re
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("expected installation digest must be a lowercase SHA256 from preview")


def _write_receipt(path: Path, receipt: dict) -> None:
    path.write_bytes(encode(receipt))


def _rename_no_replace(source: Path, destination: Path) -> None:
    """Move a directory atomically without clobbering an appeared target.

    POSIX ``Path.rename`` can replace an empty directory created after the
    existence check. Linux exposes RENAME_NOREPLACE for this exact contract;
    Windows rename already fails on an existing destination. Other systems
    fail closed until the equivalent exclusive operation is implemented.
    """
    if sys.platform == "win32":
        os.rename(source, destination)
        return
    if not sys.platform.startswith("linux"):
        raise ValueError("recoverable host lifecycle requires an atomic no-replace rename on this platform")
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise ValueError("this platform lacks atomic no-replace rename; installation was preserved")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    flags = os.O_RDONLY | os.O_DIRECTORY | nofollow
    source_fd = os.open(source.parent, flags)
    try:
        destination_fd = os.open(destination.parent, flags)
        try:
            if rename(source_fd, os.fsencode(source.name), destination_fd, os.fsencode(destination.name), 1) != 0:
                code = ctypes.get_errno()
                if code in (errno.ENOSYS, errno.EINVAL, errno.ENOTSUP):
                    raise ValueError("filesystem lacks atomic no-replace rename; installation was preserved")
                raise OSError(code, os.strerror(code), str(destination))
        finally:
            os.close(destination_fd)
    finally:
        os.close(source_fd)


def uninstall(workspace: Path, host: str, expected_installation_sha256: str) -> dict:
    """Archive a byte-verified install; unknown or changed content is retained."""
    _checked_token(expected_installation_sha256)
    workspace = Path(workspace)
    target = _target_for(workspace, host)
    snapshot = installed_snapshot(target)
    if snapshot["host"] != host:
        raise ValueError("installed Skill host differs from selected discovery path")
    if snapshot["installationSha256"] != expected_installation_sha256:
        raise ValueError("installation changed since preview; refusing stale uninstall")
    archive_root = workspace.resolve() / ARCHIVE_ROOT
    _prepare_parent(archive_root)
    archive = archive_root / f"{host}-{snapshot['version']}-{uuid.uuid4().hex}"
    archive.mkdir(mode=0o700, exist_ok=False)
    receipt_path = archive / ARCHIVE_RECEIPT
    archived_skill = archive / "skill"
    receipt = {
        "schema": ARCHIVE_SCHEMA, "status": "pending-move",
        "host": host, "version": snapshot["version"],
        "originalWorkspace": str(workspace.resolve()),
        "originalSkillDirectory": str(target), "archivedAt": now(),
        "installationSha256": snapshot["installationSha256"],
        "fileCount": len(snapshot["files"]),
        "bundleManifestSha256": snapshot["bundleManifestSha256"],
        "releaseManifestSha256": snapshot["releaseManifestSha256"],
        "deletesFiles": False, "externalDataChanged": False,
        "hostE2E": "not-tested",
    }
    moved = False
    try:
        _write_receipt(receipt_path, receipt)
        # Recheck immediately before the move. The private archive owns the
        # destination; any concurrent changed bytes remain in the archive and
        # are explicitly quarantined rather than deleted or silently accepted.
        if installed_snapshot(target) != snapshot:
            raise ValueError("installation changed before archive move; refusing uninstall")
        _rename_no_replace(target, archived_skill)
        moved = True
        if installed_snapshot(archived_skill) != snapshot:
            raise ValueError("installation changed during archive move")
        receipt["status"] = "archived"
        _write_receipt(receipt_path, receipt)
    except Exception as exc:
        if moved:
            receipt["status"] = "quarantined-needs-review"
            receipt["error"] = str(exc)
            _write_receipt(receipt_path, receipt)
            raise ValueError(f"uninstall interrupted; all moved files preserved for review at {archive}: {exc}") from exc
        # Only our own pending receipt exists here; never recursively remove
        # a directory that another process may have populated.
        receipt_path.unlink(missing_ok=True)
        try:
            archive.rmdir()
        except OSError:
            pass
        raise
    return {
        "status": "passed", "action": "recoverable-uninstall",
        "scope": "explicit-workspace", "host": host,
        "version": snapshot["version"], "skillDirectory": str(target),
        "archiveDirectory": str(archive), "receipt": str(receipt_path),
        "installationSha256": snapshot["installationSha256"],
        "fileCount": len(snapshot["files"]), "discoveryPathAbsent": not (target.exists() or target.is_symlink()),
        "deletesFiles": False, "externalDataChanged": False, "hostE2E": "not-tested",
    }


def _archive_receipt(archive: Path, workspace: Path, host: str) -> dict:
    _reject_link_ancestors(archive, "Skill archive")
    _normal_directory(archive, "Skill archive")
    archive = archive.resolve()
    expected_root = workspace.resolve() / ARCHIVE_ROOT
    _reject_link_ancestors(expected_root, "Skill archive root")
    if archive.parent != expected_root:
        raise ValueError("archive must be one direct child of the selected workspace archive root")
    receipt_path = archive / ARCHIVE_RECEIPT
    _normal_file(receipt_path, "Skill archive receipt")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Skill archive receipt is not valid JSON") from exc
    required = {"schema", "status", "host", "version", "originalWorkspace", "originalSkillDirectory",
                "archivedAt", "installationSha256", "fileCount", "bundleManifestSha256",
                "releaseManifestSha256", "deletesFiles", "externalDataChanged", "hostE2E"}
    if not isinstance(receipt, dict) or set(receipt) != required:
        raise ValueError("Skill archive receipt fields are invalid")
    if receipt["schema"] != ARCHIVE_SCHEMA or receipt["status"] != "archived" or receipt["host"] != host:
        raise ValueError("Skill archive is not an unconsumed archive for the selected host")
    if receipt["deletesFiles"] is not False or receipt["externalDataChanged"] is not False or receipt["hostE2E"] != "not-tested":
        raise ValueError("Skill archive receipt contains unsupported lifecycle claims")
    _checked_token(receipt["installationSha256"])
    expected_entries = {ARCHIVE_RECEIPT, "skill"}
    if {path.name for path in archive.iterdir()} != expected_entries:
        raise ValueError("Skill archive contains unexpected files; preserving it")
    checked = installed_snapshot(archive / "skill")
    fields = ("host", "version", "installationSha256", "bundleManifestSha256", "releaseManifestSha256")
    if any(receipt[field] != checked[field] for field in fields) or receipt["fileCount"] != len(checked["files"]):
        raise ValueError("Skill archive bytes differ from its uninstall receipt")
    return receipt


def restore(workspace: Path, host: str, archive_directory: Path) -> dict:
    """Restore a verified archive without replacing an existing Skill."""
    workspace = Path(workspace)
    target = _target_for(workspace, host)
    archive = Path(archive_directory)
    receipt = _archive_receipt(archive, workspace, host)
    if target.exists() or target.is_symlink():
        raise ValueError(f"refusing to overwrite existing Skill directory: {target}")
    _prepare_parent(target.parent)
    # Revalidate archive and receipt directly before the move. The archive
    # receipt remains as an audit after restore; it can never be replayed when
    # the archived Skill no longer exists.
    if _archive_receipt(archive, workspace, host) != receipt:
        raise ValueError("Skill archive receipt changed before restoration")
    _rename_no_replace(archive / "skill", target)
    result = installed_snapshot(target)
    if result["installationSha256"] != receipt["installationSha256"]:
        raise ValueError(f"restored content changed concurrently; preserved at {target}")
    receipt["status"] = "restored"
    receipt["restoredAt"] = now()
    receipt["restoredSkillDirectory"] = str(target)
    _write_receipt(archive / ARCHIVE_RECEIPT, receipt)
    return {
        "status": "passed", "action": "restore-uninstalled-skill",
        "scope": "explicit-workspace", "host": host, "version": result["version"],
        "skillDirectory": str(target), "archiveDirectory": str(archive.resolve()),
        "installationSha256": result["installationSha256"],
        "fileCount": len(result["files"]), "externalDataChanged": False,
        "hostE2E": "not-tested",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("preview", "uninstall", "restore"):
        command = commands.add_parser(name)
        command.add_argument("--host", choices=HOST_CHOICES, required=True)
        roots = command.add_mutually_exclusive_group(required=True)
        roots.add_argument("--workspace", type=Path)
        roots.add_argument("--prefix", type=Path)
        if name == "uninstall":
            command.add_argument("--expected-installation-sha256", required=True)
        elif name == "restore":
            command.add_argument("--archive-directory", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    options = _parser().parse_args(argv)
    workspace = options.workspace or options.prefix
    try:
        if options.command == "preview":
            result = preview(workspace, options.host)
        elif options.command == "uninstall":
            result = uninstall(workspace, options.host, options.expected_installation_sha256)
        else:
            result = restore(workspace, options.host, options.archive_directory)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
