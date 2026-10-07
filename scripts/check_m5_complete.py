#!/usr/bin/env python3
"""Check the bounded, local M5 exit without promoting the open M4 gates.

The input is a package-external ``archcanvas-m5-completion/1`` receipt. File
hashes, archive inventory, package smoke/lifecycle receipts, export preflights
and an honestly labelled 90-second snapshot presentation are checked here.
This is a finite evidence consistency check, not a human, host-client,
compositor-performance or publication certification.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any

try:
    from .m5_beta_bundle import BUNDLE_MANIFEST, encode, read_bundle
    from .m5_beta_preflight import check_receipt
except ImportError:
    from m5_beta_bundle import BUNDLE_MANIFEST, encode, read_bundle
    from m5_beta_preflight import check_receipt


HOSTS = {"codex", "claude-code", "deepseek-harness"}
DEMO_STEPS = {
    "catalog-discovery", "source-overview", "hierarchy-expand",
    "four-direction-move", "presentation-edit", "undo", "save-reopen",
    "current-export", "semantic-proposal",
}
SMOKE_CHECKS = {
    "cli-capabilities", "cli-analysis", "installed-studio-assets",
    "managed-proposal-unapproved-source-unchanged", "current-document-svg",
    "service-restart-document-project-export-persistence",
    "installed-inventory-and-fixture-unchanged",
}
RELIABILITY_CHECKS = {
    "wrong-port-direction", "shape-conflict-save", "draft-storage-conflict",
    "canvas-storage-conflict", "invalid-export-format", "stale-semantic-binding",
    "unapproved-source-commit", "restart-session-rotation-and-exact-persistence",
    "installed-inventory-and-fixtures-unchanged",
}
FORBIDDEN = "ArchCanvas_Model Architecture Studio_Temp"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _path(name: Any, root: Path, base: Path | None = None) -> Path:
    if not isinstance(name, str) or not name or "\\" in name or "\0" in name:
        raise ValueError("invalid evidence path")
    candidate = Path(name)
    if ".." in candidate.parts:
        raise ValueError("evidence traversal is forbidden")
    if not candidate.is_absolute():
        direct = root / candidate
        candidate = direct if direct.is_file() or base is None else base / candidate
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root) or FORBIDDEN in str(resolved):
        raise ValueError("evidence path leaves the formal project")
    if not resolved.is_file() or candidate.is_symlink():
        raise ValueError(f"evidence is missing or a symlink: {name}")
    return resolved


def _bound(ref: Any, root: Path, *, base: Path | None = None) -> tuple[Path, bytes]:
    if not isinstance(ref, dict):
        raise ValueError("bound evidence must be an object")
    path = _path(ref.get("path"), root, base)
    data = path.read_bytes()
    digest = ref.get("sha256")
    if not isinstance(digest, str) or len(digest) != 64 or digest != sha256(data):
        raise ValueError(f"evidence hash mismatch: {ref.get('path')}")
    if "bytes" in ref and (type(ref["bytes"]) is not int or ref["bytes"] != len(data)):
        raise ValueError(f"evidence byte count mismatch: {ref.get('path')}")
    return path, data


def _json(ref: Any, root: Path, *, base: Path | None = None) -> tuple[Path, dict]:
    path, data = _bound(ref, root, base=base)
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError(f"receipt must be an object: {path}")
    return path, value


def _checks(value: dict, required: set[str], context: str) -> None:
    rows = value.get("checks")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"{context}: checks must be an object list")
    names = [row.get("check") for row in rows]
    if len(names) != len(set(names)) or not required.issubset(names):
        raise ValueError(f"{context}: required checks are missing or duplicated")
    if any(row.get("status") != "passed" for row in rows):
        raise ValueError(f"{context}: a check did not pass")


def _inputs(value: dict, root: Path) -> None:
    rows = value.get("inputs")
    if not isinstance(rows, list) or not rows:
        raise ValueError("receipt has no input bindings")
    seen: set[Path] = set()
    for ref in rows:
        path, _ = _bound(ref, root)
        if path in seen:
            raise ValueError("duplicate receipt input binding")
        seen.add(path)


def _unapproved(value: dict) -> None:
    if value.get("hostE2E") != "not-tested" or value.get("humanApproval") is not False:
        raise ValueError("package smoke cannot certify host E2E or human approval")
    if value.get("modelExecution") is not False:
        raise ValueError("local static evidence must not claim model execution")


def _standalone(value: dict, bundle: dict, version: str) -> None:
    if value.get("status") != "passed" or value.get("sha256") != bundle["sha256"] or value.get("version") != version:
        raise ValueError("standalone receipt does not bind the selected bundle/version")
    analysis = value.get("analysis") or {}
    if analysis.get("status") != "passed" or analysis.get("modelExecution") is not False:
        raise ValueError("standalone static analysis did not pass")
    fixtures = analysis.get("fixtures")
    if not isinstance(fixtures, list) or {row.get("fixture") for row in fixtures if isinstance(row, dict)} != {"mlp", "residual_cnn", "transformer"}:
        raise ValueError("standalone verification must cover the three formal fixtures")
    directory = Path(str(value.get("standaloneDirectory", "")))
    origins = analysis.get("origins")
    if not directory.is_absolute() or not isinstance(origins, list) or len(origins) < 2:
        raise ValueError("standalone module provenance is missing")
    if any(not isinstance(origin, str) or FORBIDDEN in origin or not Path(origin).is_relative_to(directory / "src") for origin in origins):
        raise ValueError("standalone module provenance leaves the release")


def _installed(value: dict, root: Path, bundle: dict, version: str, inventory_digest: str, release_digest: str, receipt_bindings: dict[Path, str]) -> None:
    if value.get("status") != "passed" or (value.get("bundle") or {}).get("sha256") != bundle["sha256"]:
        raise ValueError("installed receipt does not bind the selected bundle")
    _unapproved(value)
    _inputs(value, root)
    rows = value.get("hosts")
    if not isinstance(rows, list) or len(rows) != 3 or {row.get("host") for row in rows if isinstance(row, dict)} != HOSTS:
        raise ValueError("installed receipt must have exactly three distinct hosts")
    for row in rows:
        host = row["host"]
        installation = row.get("installation") or {}
        if installation.get("status") != "passed" or installation.get("host") != host or installation.get("version") != version:
            raise ValueError(f"{host}: installation did not bind the selected version")
        if installation.get("bundleManifestSha256") != inventory_digest or installation.get("releaseManifestSha256") != release_digest:
            raise ValueError(f"{host}: installation inventory/release binding mismatch")
        if installation.get("hostE2E") != "not-tested":
            raise ValueError(f"{host}: project-local installation is not host E2E")
        for kind, required in (("cli-http", SMOKE_CHECKS), ("reliability", RELIABILITY_CHECKS)):
            summary = row.get(kind) or {}
            receipt_path = _path(summary.get("receipt"), root)
            if receipt_path not in receipt_bindings or receipt_bindings[receipt_path] != sha256(receipt_path.read_bytes()):
                raise ValueError(f"{host}: {kind} receipt is not bound by completion receiptBindings")
            receipt = json.loads(receipt_path.read_bytes())
            if not isinstance(receipt, dict) or summary.get("status") != "passed" or receipt.get("status") != "passed":
                raise ValueError(f"{host}: {kind} smoke did not pass")
            nested = receipt.get("installation") or {}
            if nested.get("bundleManifestSha256") != inventory_digest or nested.get("releaseManifestSha256") != release_digest or nested.get("host") != host or nested.get("version") != version:
                raise ValueError(f"{host}: {kind} smoke uses another release")
            _checks(receipt, required, f"{host}/{kind}")
            _unapproved(receipt)
            _inputs(receipt, root)
            if kind == "reliability" and any(check.get("storageUnchanged") is not True for check in receipt["checks"] if check.get("check") in RELIABILITY_CHECKS - {"restart-session-rotation-and-exact-persistence", "installed-inventory-and-fixtures-unchanged"}):
                raise ValueError(f"{host}: rejection changed stored bytes")


def _lifecycle(path: Path, value: dict, root: Path, bundle: dict, version: str) -> None:
    if value.get("schema") != "archcanvas-m5-beta2-independent-review/1" or value.get("status") != "passed" or value.get("candidateSha256") != bundle["sha256"]:
        raise ValueError("upgrade/rollback review does not bind the selected candidate")
    _unapproved(value)
    baseline = _path(value.get("baseline"), root)
    if sha256(baseline.read_bytes()) != value.get("baselineSha256"):
        raise ValueError("upgrade/rollback baseline hash mismatch")
    baseline_manifest, _ = read_bundle(baseline)
    baseline_version = baseline_manifest["version"]
    if baseline_version == version:
        raise ValueError("upgrade/rollback must use two different real versions")
    _checks(value, {"actual-beta1-beta2-beta1-install-upgrade-rollback", "both-frozen-input-archives-unchanged"}, "upgrade/rollback")
    upgrade_check = next(row for row in value["checks"] if row["check"] == "actual-beta1-beta2-beta1-install-upgrade-rollback")
    if upgrade_check.get("userDataUnchanged") is not True:
        raise ValueError("upgrade/rollback did not preserve user data")
    artifacts = value.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("lifecycle command artifacts are missing")
    bound_artifacts: dict[str, bytes] = {}
    for ref in artifacts:
        _, data = _bound(ref, root, base=path.parent)
        if ref["path"] in bound_artifacts:
            raise ValueError("duplicate lifecycle artifact")
        bound_artifacts[ref["path"]] = data
    commands = value.get("commands")
    if not isinstance(commands, list) or not all(isinstance(command, dict) for command in commands):
        raise ValueError("lifecycle commands are missing")
    command_names = [command.get("label") for command in commands]
    required = {"prefix-beta1-install", "prefix-beta2-upgrade", "prefix-beta1-rollback"}
    if len(command_names) != len(set(command_names)) or not required.issubset(command_names):
        raise ValueError("install/upgrade/rollback commands are missing or duplicated")
    for command in commands:
        name = command.get("result")
        if type(command.get("exitCode")) is not int or command["exitCode"] != 0 or name not in bound_artifacts or sha256(bound_artifacts[name]) != command.get("stdoutSha256"):
            raise ValueError("lifecycle command result/hash/exit status mismatch")
    expected = {"prefix-beta1-install": baseline_version, "prefix-beta2-upgrade": version, "prefix-beta1-rollback": baseline_version}
    for command in commands:
        if command["label"] in expected:
            result = json.loads(bound_artifacts[command["result"]])
            if result.get("status") != "passed" or result.get("version", result.get("currentVersion")) != expected[command["label"]]:
                raise ValueError("lifecycle command result used the wrong version")
    rows = value.get("hosts")
    if not isinstance(rows, list) or len(rows) != 3 or {row.get("host") for row in rows if isinstance(row, dict)} != HOSTS:
        raise ValueError("lifecycle review must cover exactly three host layouts")
    for row in rows:
        if row.get("status") != "passed" or row.get("versionSequence") != [baseline_version, "archived", version, "archived", baseline_version] or row.get("oldNewBytesPreserved") is not True or row.get("externalDataUnchanged") is not True or row.get("hostE2E") != "not-tested":
            raise ValueError("host lifecycle did not preserve both versions and user data")


def _preflight(path: Path, value: dict, root: Path, contents: dict[str, bytes]) -> str:
    if value.get("schema") != "archcanvas-m5-beta-preflight/1" or value.get("status") != "passed" or value.get("skipped") != [] or value.get("errors") != [] or value.get("sourceUnchanged") is not True or value.get("documentUnchanged") is not True:
        raise ValueError("export preflight did not pass all requested formats unchanged")
    _inputs(value, root)
    for ref in value["inputs"]:
        input_path = _path(ref["path"], root)
        name = str(input_path.relative_to(root))
        if name not in contents or sha256(contents[name]) != ref["sha256"]:
            raise ValueError("preflight input does not match the release inventory")
    rows = value.get("artifacts")
    expected = {(fmt, width) for fmt in ("svg", "pdf", "png") for width in (85, 180)}
    if not isinstance(rows, list) or len(rows) != 6 or {(row.get("format"), row.get("widthMm")) for row in rows if isinstance(row, dict)} != expected:
        raise ValueError("preflight must cover SVG/PDF/PNG at 85 and 180 mm exactly once")
    for row in rows:
        artifact, _ = _bound({"path": row.get("artifact"), "sha256": row.get("sha256"), "bytes": row.get("bytes")}, root, base=path.parent)
        receipt_path = _path(row.get("receipt"), root, path.parent)
        actual = check_receipt(artifact, receipt_path, width=row["widthMm"], fmt=row["format"])
        if row.get("errors") != [] or actual["errors"] or actual["physicalPreflight"] != row.get("physicalPreflight") or actual["fontEmbeddingGuaranteed"] != row.get("fontEmbeddingGuaranteed"):
            raise ValueError("export artifact/receipt geometry or font preflight mismatch")
    if value.get("fontPolicy", {}).get("embeddingGuaranteed") is not False:
        raise ValueError("local preflight cannot certify cross-machine font embedding")
    return str(value.get("fixture"))


def _host_matrix(value: Any, availability: dict) -> None:
    probes = availability.get("hosts")
    if not isinstance(probes, list) or not all(isinstance(probe, dict) for probe in probes):
        raise ValueError("host availability probes are missing")
    by_name = {probe.get("executableName"): probe for probe in probes}
    if not {"codex", "claude", "dsh", "deepseek-harness"}.issubset(by_name):
        raise ValueError("availability must probe Codex, Claude and both Harness executable names")
    if not isinstance(value, list) or len(value) != 3 or {row.get("host") for row in value if isinstance(row, dict)} != HOSTS:
        raise ValueError("host matrix must contain exactly three distinct hosts")
    for row in value:
        host = row["host"]
        commands = {"codex": ["codex"], "claude-code": ["claude"], "deepseek-harness": ["dsh", "deepseek-harness"]}[host]
        available = any(by_name[name].get("availableOnPath") is True for name in commands)
        if row.get("clientAvailable") is not available or row.get("e2e") != "not-tested" or not isinstance(row.get("degradationReason"), str) or not row["degradationReason"].strip():
            raise ValueError(f"{host}: availability, not-tested state and degradation reason must be explicit")


def _demo(path: Path, value: dict, root: Path, build_bindings: dict[str, str], candidate_sha256: str | None = None) -> None:
    if value.get("schema") != "archcanvas-m5-demo/1" or value.get("status") != "passed-bounded" or value.get("kind") != "snapshot-sequence":
        raise ValueError("demo must declare the bounded snapshot presentation contract")
    for field in ("recordingCertified", "continuousOperationCertified", "humanAcceptance"):
        if value.get(field) is not False:
            raise ValueError(f"snapshot demo cannot certify {field}")
    if not isinstance(value.get("operator"), str) or "AI" not in value["operator"]:
        raise ValueError("demo operator must explicitly identify AI")
    duration = value.get("durationSeconds")
    elapsed = value.get("operationElapsedSeconds")
    if type(duration) not in (int, float) or not math.isfinite(duration) or abs(duration - 90) > .001:
        raise ValueError("snapshot presentation duration must be 90 seconds")
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed <= 0:
        raise ValueError("demo must retain the real operation elapsed time separately")
    if value.get("sourceCommit") != "not-performed" or not isinstance(value.get("sourceCommitReason"), str) or not value["sourceCommitReason"].strip():
        raise ValueError("bounded demo must disclose the unperformed semantic commit")
    if candidate_sha256 is not None and (value.get("runtime") or {}).get("candidateSha256") != candidate_sha256:
        raise ValueError("demo runtime does not bind the selected candidate bundle")
    assets = value.get("buildAssets")
    if not isinstance(assets, list) or len(assets) != len(build_bindings) or {row.get("path"): row.get("sha256") for row in assets if isinstance(row, dict)} != build_bindings:
        raise ValueError("demo build assets do not match the selected release")
    frames = value.get("frames")
    if not isinstance(frames, list) or len(frames) < 5:
        raise ValueError("demo must retain at least five actual UI frames")
    timestamps: list[datetime] = []
    frame_paths: set[Path] = set()
    for frame in frames:
        frame_path, data = _bound(frame, root, base=path.parent)
        if frame_path in frame_paths or not (data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff")):
            raise ValueError("demo frames must be distinct PNG/JPEG artifacts")
        frame_paths.add(frame_path)
        timestamp = datetime.fromisoformat(str(frame.get("capturedAt", "")).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("frame capturedAt requires a timezone")
        timestamps.append(timestamp)
    if timestamps != sorted(timestamps):
        raise ValueError("demo capture times are not chronological")
    presentation = value.get("presentation")
    presentation_formats = {
        (row.get("format") or Path(str(row.get("path", ""))).suffix.removeprefix(".")).lower()
        for row in presentation if isinstance(row, dict)
    } if isinstance(presentation, list) else set()
    if not isinstance(presentation, list) or presentation_formats != {"gif", "html"}:
        raise ValueError("demo needs a bound GIF and standalone HTML presentation")
    for item in presentation:
        _, data = _bound(item, root, base=path.parent)
        fmt = (item.get("format") or Path(str(item.get("path", ""))).suffix.removeprefix(".")).lower()
        if fmt == "gif" and not data.startswith((b"GIF87a", b"GIF89a")):
            raise ValueError("demo GIF has no GIF signature")
        if fmt == "html" and b"snapshot" not in data.lower():
            raise ValueError("HTML presentation must disclose snapshot composition")
    steps = value.get("steps")
    if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps) or len(steps) != len(DEMO_STEPS) or {step.get("id") for step in steps} != DEMO_STEPS:
        raise ValueError("demo workflow steps are missing or duplicated")
    if any(step.get("status") != "passed" or not isinstance(step.get("detail"), str) or not step["detail"].strip() for step in steps):
        raise ValueError("demo steps need actual bounded results")
    exports = value.get("exports")
    if not isinstance(exports, list) or {row.get("format") for row in exports if isinstance(row, dict)} != {"svg", "pdf"}:
        raise ValueError("demo needs actual current SVG and PDF exports")
    for item in exports:
        _, data = _bound(item, root, base=path.parent)
        if item["format"] == "svg" and b"<svg" not in data[:1000] or item["format"] == "pdf" and not data.startswith(b"%PDF-"):
            raise ValueError("demo export has the wrong format signature")


def validate(receipt: Any, project_root: Path) -> list[str]:
    """Return finite contract violations; never execute a model or host client."""
    root = project_root.resolve()
    if not isinstance(receipt, dict):
        return ["completion receipt must be an object"]
    constants = {
        "schema": "archcanvas-m5-completion/1", "state": "complete-local-beta",
        "scope": "local-beta-preview", "m4": "partial", "runtimeSource": "formal-project",
        "publicRelease": False, "humanParticipants": 0, "publicationReviewCertified": False,
    }
    errors = [f"{key} must remain {value!r}" for key, value in constants.items() if receipt.get(key) != value or type(receipt.get(key)) is not type(value)]
    if not isinstance(receipt.get("knownLimitations"), list) or not receipt["knownLimitations"] or not all(isinstance(item, str) and item.strip() for item in receipt["knownLimitations"]):
        errors.append("knownLimitations must be non-empty explicit text")
    bundle = receipt.get("bundle")
    contents: dict[str, bytes] = {}
    inventory_digest = release_digest = ""
    build_bindings: dict[str, str] = {}
    try:
        bundle_path, _ = _bound(bundle, root)
        manifest, contents = read_bundle(bundle_path)
        if manifest.get("version") != receipt.get("version"):
            raise ValueError("completion version differs from bundle inventory")
        # read_bundle removes BUNDLE-MANIFEST from the payload after validating
        # it.  The bundle writer uses the stable ``encode`` function, so this
        # reproduces the exact bytes bound by the host installer receipts.
        # A host installation embeds the release under ``runtime/release``
        # and removes the source Skill subtree so host scanners cannot find a
        # recursive second Skill.  Match the installer’s intentionally
        # reduced manifest when binding its smoke receipts.
        embedded_manifest = dict(manifest)
        embedded_manifest["files"] = [
            row for row in manifest.get("files", [])
            if row["path"] != "skills/archcanvas" and not row["path"].startswith("skills/archcanvas/")
        ]
        inventory_digest = sha256(encode(embedded_manifest))
        release_digest = sha256(contents["docs/evidence/m5-beta-release-manifest.json"])
        expected_assets = {name: sha256(data) for name, data in contents.items() if name.startswith("studio/dist/")}
        bindings = receipt.get("buildBindings")
        if not isinstance(bindings, list) or len(bindings) != len(expected_assets):
            raise ValueError("completion must bind the complete Studio dist inventory")
        for ref in bindings:
            path, _ = _bound(ref, root)
            name = str(path.relative_to(root))
            if name in build_bindings:
                raise ValueError("duplicate build binding")
            build_bindings[name] = ref["sha256"]
        if build_bindings != expected_assets:
            raise ValueError("completion Studio bytes differ from the selected bundle")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"bundle/build: {exc}")
    evidence = receipt.get("evidence")
    if not isinstance(evidence, dict):
        return errors + ["evidence must be an object"]
    receipt_bindings: dict[Path, str] = {}
    try:
        refs = receipt.get("receiptBindings")
        if not isinstance(refs, list) or not refs:
            raise ValueError("receiptBindings must be a non-empty list")
        for ref in refs:
            bound_path, _ = _bound(ref, root)
            if bound_path in receipt_bindings:
                raise ValueError("duplicate receiptBinding")
            receipt_bindings[bound_path] = ref["sha256"]
    except (OSError, ValueError, TypeError) as exc:
        errors.append(f"receiptBindings: {exc}")
    validators = {
        "standalone": lambda p, v: _standalone(v, bundle, receipt.get("version")),
        "installed": lambda p, v: _installed(v, root, bundle, receipt.get("version"), inventory_digest, release_digest, receipt_bindings),
        "upgradeRollback": lambda p, v: _lifecycle(p, v, root, bundle, receipt.get("version")),
        "hostAvailability": lambda p, v: _host_matrix(receipt.get("hostMatrix"), v),
        "demo": lambda p, v: _demo(p, v, root, build_bindings, bundle.get("sha256") if isinstance(bundle, dict) else None),
    }
    for name, validator in validators.items():
        try:
            path, value = _json(evidence.get(name), root)
            validator(path, value)
        except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
            errors.append(f"{name}: {exc}")
    try:
        preflights = evidence.get("preflights")
        if not isinstance(preflights, list) or len(preflights) != 2:
            raise ValueError("two source-bound preflight receipts are required")
        fixtures: list[str] = []
        for ref in preflights:
            path, value = _json(ref, root)
            fixtures.append(_preflight(path, value, root, contents))
        if set(fixtures) != {"mlp", "transformer"}:
            raise ValueError("preflights must cover MLP and Transformer exactly once")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"preflights: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=Path("docs/evidence/m5-completion-v1/receipt.json"))
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    options = parser.parse_args()
    try:
        value = json.loads(options.receipt.read_text(encoding="utf-8"))
        errors = validate(value, options.project_root)
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
    print(json.dumps({"status": "passed" if not errors else "failed", "scope": "bounded-local-M5-evidence-consistency", "receipt": str(options.receipt), "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
