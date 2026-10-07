#!/usr/bin/env python3
"""Read-only readiness and local availability check for an M4 trial package.

The official ``research_trial.py verify`` command proves the frozen package
and implementation bytes still match.  It intentionally does not inspect the
operator's machine or touch a slot.  This companion check adds that missing
boundary: it confirms that every slot is still pristine and probes whether
each registered loopback port is free *right now*.  It never assigns a code,
starts a service, writes inside the package, or treats a free port as a
running service or a human participant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "archcanvas-m4-research-readiness/1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def regular(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def package_snapshot(package: Path) -> dict[str, Any]:
    """Capture a small immutable inventory without following symlink files."""
    files: list[dict[str, Any]] = []
    if not package.is_dir() or package.is_symlink():
        return {"exists": False, "files": files, "fileCount": 0}
    for path in sorted(package.rglob("*")):
        if path.is_symlink():
            files.append({"path": str(path.relative_to(package)), "symlink": True})
        elif path.is_file():
            files.append({
                "path": str(path.relative_to(package)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            })
    return {"exists": True, "files": files, "fileCount": len(files)}


def probe_port(port: int, host: str = "127.0.0.1") -> dict[str, Any]:
    """Probe occupancy by binding and releasing the exact loopback endpoint."""
    result: dict[str, Any] = {"host": host, "port": port, "status": "error"}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except OSError as exc:
        # Managed execution can deny AF_INET entirely.  Keep this distinct
        # from an occupied port; an indeterminate probe must never be called
        # free or running.
        result["status"] = "probe-blocked"
        result["errno"] = exc.errno
        result["error"] = str(exc)
        result["serviceRunning"] = "unknown"
        return result
    try:
        # Do not set SO_REUSEADDR: an occupied endpoint must remain occupied.
        sock.bind((host, port))
        result["status"] = "available"
        result["serviceRunning"] = False
    except OSError as exc:
        if exc.errno in (98, 48, 10048):  # Linux, macOS, Windows EADDRINUSE
            result["status"] = "occupied"
            result["serviceRunning"] = "unknown"
        elif exc.errno in (13, 10013):
            result["status"] = "permission-denied"
        else:
            result["status"] = "error"
        result["errno"] = exc.errno
        result["error"] = str(exc)
    finally:
        sock.close()
    return result


def verify_official(package: Path) -> dict[str, Any]:
    command = [sys.executable, str(ROOT / "scripts/research_trial.py"), "verify", "--package", str(package)]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
    result: dict[str, Any] = {
        "command": command,
        "exitCode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "passed": completed.returncode == 0,
    }
    if completed.returncode == 0:
        try:
            result["receipt"] = json.loads(completed.stdout)
        except json.JSONDecodeError:
            result["passed"] = False
            result["parseError"] = "official verify returned non-JSON stdout"
    return result


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def relative_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def inspect_slots(package: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    slots = manifest.get("slots")
    if not isinstance(slots, list) or not 3 <= len(slots) <= 5:
        return {"passed": False, "slotCount": 0 if not isinstance(slots, list) else len(slots), "slots": [], "errors": ["manifest.slots must contain 3–5 slots"]}
    seen_ids: set[str] = set()
    seen_ports: set[int] = set()
    records: list[dict[str, Any]] = []
    for raw in slots:
        if not isinstance(raw, dict):
            errors.append("slot record is not an object")
            continue
        slot_id = raw.get("slotId")
        port = raw.get("port")
        slot = package / "slots" / str(slot_id)
        slot_errors: list[str] = []
        if not isinstance(slot_id, str) or not slot_id or slot_id in seen_ids:
            slot_errors.append("slotId missing or duplicated")
        else:
            seen_ids.add(slot_id)
        if not isinstance(port, int) or not 1024 <= port <= 65535 or port in seen_ports:
            slot_errors.append("port missing, out of range, or duplicated")
        else:
            seen_ports.add(port)
        if raw.get("participantCode") is not None or raw.get("assignment") != "unassigned":
            slot_errors.append("manifest slot is already assigned")
        if not slot.is_dir() or slot.is_symlink():
            slot_errors.append("slot directory is missing or symlinked")
        else:
            assignment = slot / "assignment.json"
            collected = slot / "collected"
            if assignment.exists() or collected.exists():
                slot_errors.append("assignment.json or collected exists")
            incoming = slot / "incoming"
            if incoming.exists() and any(incoming.iterdir()):
                slot_errors.append("incoming is not empty")
            workspace = slot / "workspace"
            for group in ("exports", "projects", "transactions"):
                directory = workspace / group
                if directory.exists() and any(directory.iterdir()):
                    slot_errors.append(f"workspace/{group} is not empty")
            binding = raw.get("baselineEnvelope")
            if not isinstance(binding, dict) or not isinstance(binding.get("path"), str):
                slot_errors.append("baselineEnvelope binding missing")
            else:
                envelope = package / binding["path"]
                if not relative_inside(envelope, package) or not regular(envelope):
                    slot_errors.append("baseline envelope is missing, symlinked, or escapes package")
                elif sha256(envelope) != binding.get("sha256") or envelope.stat().st_size != binding.get("bytes"):
                    slot_errors.append("baseline envelope hash/size mismatch")
            template = slot / "review-template.json"
            if not regular(template):
                slot_errors.append("review-template.json missing or symlinked")
            else:
                try:
                    review = read_json(template)
                    if review.get("slotId") != slot_id or review.get("participantCode") is not None or review.get("status") != "pending-independent-review":
                        slot_errors.append("review template is not blank for this slot")
                except (OSError, json.JSONDecodeError):
                    slot_errors.append("review template is invalid JSON")
        records.append({"slotId": slot_id, "port": port, "passed": not slot_errors, "errors": slot_errors})
        errors.extend(f"{slot_id}: {item}" for item in slot_errors)
    return {"passed": not errors, "slotCount": len(slots), "slots": records, "errors": errors}


def evaluate(package: Path) -> dict[str, Any]:
    package = package.resolve()
    before = package_snapshot(package)
    official = verify_official(package)
    errors: list[str] = []
    if not package.is_dir() or package.is_symlink():
        errors.append("package directory is missing or symlinked")
        after = package_snapshot(package)
        return {"passed": False, "errors": errors, "officialVerify": official, "packageBefore": before, "packageAfter": after}
    manifest_path = package / "manifest.json"
    if not regular(manifest_path):
        errors.append("manifest.json is missing or symlinked")
        manifest: dict[str, Any] = {}
    else:
        try:
            manifest = read_json(manifest_path)
        except (OSError, json.JSONDecodeError):
            manifest = {}
            errors.append("manifest.json is invalid JSON")
    if manifest.get("state") != "prepared-no-participants":
        errors.append(f"unexpected package state: {manifest.get('state')!r}")
    if manifest.get("researcherCount") != 0:
        errors.append("manifest researcherCount is not zero")
    if manifest.get("researchGate") != "not_run":
        errors.append(f"unexpected researchGate: {manifest.get('researchGate')!r}")
    slots = inspect_slots(package, manifest) if manifest else {"passed": False, "slotCount": 0, "slots": [], "errors": ["manifest unavailable"]}
    errors.extend(slots["errors"])
    port_probes = [probe_port(record["port"]) for record in slots["slots"] if isinstance(record.get("port"), int) and record.get("passed")]
    unavailable = [probe for probe in port_probes if probe["status"] != "available"]
    if unavailable:
        if any(probe["status"] == "probe-blocked" for probe in unavailable):
            errors.append("one or more registered ports could not be probed in this execution environment")
        else:
            errors.append("one or more registered ports are not proven free")
    after = package_snapshot(package)
    package_unchanged = before == after
    if not package_unchanged:
        errors.append("package inventory changed during read-only check")
    package_ready = official.get("passed") and not errors
    return {
        "schema": SCHEMA,
        "createdAt": now(),
        "package": str(package),
        "packageManifestSha256": sha256(manifest_path) if regular(manifest_path) else None,
        "officialVerify": official,
        "manifestState": {key: manifest.get(key) for key in ("state", "researcherCount", "researchGate")} if manifest else {},
        "slots": slots,
        "ports": {"host": "127.0.0.1", "probes": port_probes, "allFree": not unavailable},
        "packageInventoryUnchanged": package_unchanged,
        "packageReadyForOperatorLaunch": bool(package_ready),
        "serviceStatus": "not-started; all registered ports are free" if not unavailable else "not-started-or-port-occupied",
        "humanResearchStatus": "not-ready; no participant assignment or service start was performed",
        "humanAcceptance": False,
        "humanPublicationReview": False,
        "modelExecuted": False,
        "errors": errors,
        "nextActions": [
            "Record the actual browser, viewport, DPR, hardware and font environment in environment.json.",
            "For each real participant, run research_trial.py assign once immediately before the timed task.",
            "Start one service per assigned slot on its registered port and retain its process log.",
            "Collect the participant JSON, final Canvas, actual SVG/PDF and screenshots, then obtain independent review.",
        ],
        "packageBefore": before,
        "packageAfter": after,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_symlink():
        raise SystemExit(f"Refusing to overwrite existing readiness evidence: {output}")
    report = evaluate(args.package)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "schema": SCHEMA,
        "packageReadyForOperatorLaunch": report.get("packageReadyForOperatorLaunch", False),
        "ports": report.get("ports", {}),
        "humanResearchStatus": report.get("humanResearchStatus"),
        "errors": report.get("errors", []),
        "output": str(output),
    }, ensure_ascii=False, indent=2))
    return 0 if report.get("packageReadyForOperatorLaunch") else 1


if __name__ == "__main__":
    raise SystemExit(main())
