#!/usr/bin/env python3
"""Bind current operator observations to exact local files; never control a browser.

The formal helper supplies the authoritative Canvas/export/Scene contract. This
workflow only saves exclusive byte snapshots, stamps separate receipts and makes
collect indices. Nothing here discovers a replacement export or grants a human,
pixel, native-performance or publication acceptance result.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import prepare_hierarchy_matrix_capture as formal
from browser_visual_matrix import PROTOCOL, semantic_svg_digest, verified_spec

MATRIX = ROOT / ".archcanvas/browser-visual-matrix-authoring-feedback-bcf"
STORE = ROOT / ".archcanvas/m4-bcf-browser-matrix/documents"
ORIGIN = "http://127.0.0.1:8968"
GUARD = HERE / "preparation-guard.json"
STAMPED = "screen-receipt-stamped.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(path: Path, data: bytes) -> None:
    current = path.absolute()
    while current != current.parent:
        if current.is_symlink():
            raise ValueError(f"Output symlink refused: {path}")
        current = current.parent
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def checked() -> list[tuple[Path, bytes]]:
    guard_input = formal.frozen(GUARD)
    guard = formal.decoded(guard_input[1], "capture guard")
    inputs = [guard_input]
    for entry in guard["frozenInputs"]:
        item = formal.frozen(Path(entry["path"]))
        if formal.binding(*item) != entry:
            raise ValueError(f"Frozen preparation input changed: {entry['path']}")
        inputs.append(item)
    for path, expected in guard["frozenSourceAndBuild"].items():
        item = formal.frozen(ROOT / path)
        if formal.sha(item[1]) != expected:
            raise ValueError(f"Current product source/build changed: {path}")
        inputs.append(item)
    spec = verified_spec(MATRIX)
    if len(spec["variants"]) != 36 or len(spec["frontiers"]) != 9:
        raise ValueError("Expected the current 36 variants and nine source frontiers.")
    for field, parent in (("implementationFiles", ROOT), ("buildFiles", ROOT / "studio/dist"),
                          ("coreFiles", Path(spec["coreDirectory"]))):
        for entry in spec[field]:
            item = formal.frozen(parent / entry["path"])
            if formal.binding(item[0], item[1], parent) != entry:
                raise ValueError(f"Frozen matrix {field} changed.")
            inputs.append(item)
    inputs.append(formal.frozen(Path(spec["coreDirectory"]) / "visual-gold-report.json"))
    formal.recheck(inputs)
    return inputs


def observed(raw_path: Path, *, bound: bool = False) -> tuple[dict, tuple[Path, bytes]]:
    item = formal.frozen(raw_path)
    raw = formal.decoded(item[1], "current operator DOM observation")
    if not isinstance(raw.get("caseId"), str) or not formal.SAFE_CASE.fullmatch(raw["caseId"]):
        raise ValueError("Actual observation needs a safe caseId.")
    if raw.get("studioUrl") != ORIGIN + "/":
        raise ValueError("Only the current isolated8968 Studio origin is accepted.")
    if ("actualStoredEnvelope" in raw) != bound:
        raise ValueError("Use an unbound raw observation for snapshot; use its bound copy for package.")
    formal.timezone_timestamp(raw.get("capturedAt"), "capturedAt")
    formal.validate_environment(raw)
    spec = verified_spec(MATRIX)
    variants = [entry for entry in spec["variants"] if entry["variantId"] == raw.get("variantId")]
    if len(variants) != 1 or raw.get("state") not in ("baseline", "edited"):
        raise ValueError("Actual variantId/state must identify the frozen current matrix.")
    variant = variants[0]
    binding = formal.obj(raw.get("documentBinding"), "observed document binding")
    if (binding.get("documentId") != variant["documentId"]
            or binding.get("sourceDigest") != variant["sourceDigest"]
            or binding.get("irDigest") != variant["irDigest"]
            or type(binding.get("revision")) is not int or binding["revision"] < 0):
        raise ValueError("Observed document/source/IR/revision is not the declared current variant.")
    if (raw.get("pageSpec") != {"widthMm": variant["widthMm"], "preset": variant["preset"]}
            or sorted(raw.get("expandedIds", [])) != sorted(variant["expandedIds"])):
        raise ValueError("Observed page/frontier differs from the exact current variant.")
    if raw.get("captureScope") != "studio-viewport" or not isinstance(raw.get("limitations"), list):
        raise ValueError("Capture scope and actual limitations are required.")
    href = formal.obj(raw.get("actualExport"), "actual export link").get("observedUrl")
    if not isinstance(href, str):
        raise ValueError("Read the newly completed export's current direct href for this case.")
    url = urlsplit(href)
    if (url.query or url.fragment or (url.netloc and f"{url.scheme}://{url.netloc}" != ORIGIN)
            or not formal.EXPORT_PATH.fullmatch(url.path)):
        raise ValueError("Only this case's exact current-origin whole-document SVG export link is accepted.")
    return raw, item


def snapshot(raw_path: Path) -> dict:
    inputs = checked()
    raw, raw_input = observed(raw_path)
    inputs.append(raw_input)
    case, binding = raw["caseId"], raw["documentBinding"]
    output = HERE / "bound-observations" / case
    if output.exists():
        raise ValueError("Snapshot already exists; preserve it and use a new case ID.")
    source = STORE / (binding["documentId"] + ".json")
    stored = formal.frozen(source)
    inputs.append(stored)
    envelope = formal.decoded(stored[1], "actual saved store envelope")
    document = formal.obj(envelope.get("document"), "actual saved Canvas")
    if (type(envelope.get("revision")) is not int or envelope["revision"] < 1
            or document.get("id") != binding["documentId"]
            or document.get("revision") != binding["revision"]
            or document.get("sourceBindingDigest") != binding["sourceDigest"]
            or document.get("architecture", {}).get("irDigest") != binding["irDigest"]
            or sorted(document.get("expandedIds", [])) != sorted(raw["expandedIds"])
            or {key: document.get("pageSpec", {}).get(key) for key in raw["pageSpec"]} != raw["pageSpec"]):
        raise ValueError("Current saved Canvas differs from the operator's DOM. Save before exporting/copying.")
    href = urlsplit(raw["actualExport"]["observedUrl"])
    artifact_id = formal.EXPORT_PATH.fullmatch(href.path).group(1)
    actual_export = formal.frozen(STORE.parent / "exports" / artifact_id / "document.json")
    inputs.append(actual_export)
    if formal.decoded(actual_export[1], "exact linked export Canvas") != document:
        raise ValueError("The exact observed export href is stale or refers to an unsaved Canvas. No fallback.")
    copied = {"observedSourcePath": str(source), "snapshotPath": str(output / "actual-document-store.json"),
              "copiedAt": now(), "sha256": formal.sha(stored[1]), "bytes": len(stored[1])}
    bound = {**raw, "actualStoredEnvelope": copied}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".bcf-snapshot-", dir=output.parent))
    try:
        emit(temporary / "actual-document-store.json", stored[1])
        emit(temporary / "actual-document-store.json.receipt.json", formal.encode(copied))
        emit(temporary / "dom-observation.json", formal.encode(bound))
        receipt = {"schemaVersion": 1, "protocol": "archcanvas-bcf-matrix-store-snapshot/1", "caseId": case,
                   "createdAt": now(), "sourceObservation": formal.binding(*raw_input),
                   "actualStoredEnvelope": copied, "exactExportArtifactId": artifact_id,
                   "fullSavedAndExportCanvasEquality": True, "replacementExportSearch": "not-attempted",
                   "inputBindings": [formal.binding(*item) for item in inputs],
                   "browserOperationExecuted": False, "humanAcceptanceCertified": False,
                   "scope": "Direct local file copy, not native provenance or screenshot content certification."}
        emit(temporary / "snapshot-receipt.json", formal.encode(receipt))
        formal.recheck(inputs)
        if output.exists():
            raise ValueError("Snapshot appeared during validation; refusing replacement.")
        temporary.rename(output)
        return receipt
    except Exception:
        shutil.rmtree(temporary)
        raise


def package_case(raw_path: Path, scene_path: Path, screenshot_path: Path, saved_envelope: Path) -> dict:
    inputs = checked()
    raw, raw_input = observed(raw_path, bound=True)
    inputs.extend([raw_input, formal.frozen(scene_path), formal.frozen(screenshot_path),
                   formal.frozen(saved_envelope), formal.frozen(Path(str(saved_envelope) + ".receipt.json"))])
    case = raw["caseId"]
    output = HERE / "cases" / case
    if output.exists():
        raise ValueError("Actual case already packaged; no overwrite permitted.")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".bcf-package-", dir=output.parent))
    try:
        result = formal.prepare_case(MATRIX, STORE, raw_path, scene_path, screenshot_path,
                                     temporary / "prepared", saved_envelope)
        receipt = {"schemaVersion": 1, "protocol": "archcanvas-bcf-matrix-package/1", "caseId": case,
                   "createdAt": now(), "inputBindings": [formal.binding(*item) for item in inputs],
                   "liveStoreReread": False, "exactExportArtifactId": result["exactExportArtifactId"],
                   "replacementExportSearch": "not-attempted", "browserOperationExecuted": False,
                   "humanAcceptanceCertified": False, "scope": "Frozen actual observations and exact linked local export bytes."}
        emit(temporary / "prepared" / "bcf-package-receipt.json", formal.encode(receipt))
        formal.recheck(inputs)
        if output.exists():
            raise ValueError("Case appeared during validation; refusing replacement.")
        (temporary / "prepared").rename(output)
        temporary.rmdir()
        return {"caseId": case, "caseDirectory": str(output), "exactExportArtifactId": result["exactExportArtifactId"],
                "matrixSpecDigest": result["matrixSpecDigest"], "screenHashesStamped": False,
                "humanAcceptanceCertified": False}
    except Exception:
        shutil.rmtree(temporary)
        raise


def stamp(case: str) -> dict:
    if not formal.SAFE_CASE.fullmatch(case):
        raise ValueError("Safe case ID required.")
    inputs = checked()
    directory = HERE / "cases" / case
    actual = [formal.frozen(directory / name) for name in
              ("screen-receipt-unstamped.json", "screenshot.jpg", "browser-scene.svg", "case-helper.json")]
    inputs.extend(actual)
    original = formal.decoded(actual[0][1], "unstamped screen receipt")
    if original.get("caseId") != case or original.get("screenshotDigest") is not None or original.get("browserSceneDigest") is not None:
        raise ValueError("Require this case's untouched unstamped screen receipt.")
    stamped = {**original, "screenshotDigest": formal.sha(actual[1][1]),
               "browserSceneDigest": semantic_svg_digest(actual[2][1])}
    target = directory / STAMPED
    formal.recheck(inputs)
    emit(target, formal.encode(stamped))
    receipt = {"schemaVersion": 1, "protocol": "archcanvas-bcf-matrix-separate-stamp/1", "caseId": case,
               "createdAt": now(), "stampedReceipt": formal.binding(*formal.frozen(target)),
               "inputBindings": [formal.binding(*item) for item in actual],
               "originalReceiptModified": False, "factsModified": False, "humanAcceptanceCertified": False}
    emit(directory / "bcf-stamp-receipt.json", formal.encode(receipt))
    return receipt


def index(output: Path) -> dict:
    output = output.absolute()
    if output.parent != HERE or not re.fullmatch(r"captures-\d{3}\.json", output.name):
        raise ValueError("Write a fresh captures-NNN.json directly in this work directory.")
    inputs = checked()
    spec_input = formal.frozen(MATRIX / "spec.json")
    inputs.append(spec_input)
    captures, seen, baselines = [], set(), set()
    helper_paths = sorted((HERE / "cases").glob("*/case-helper.json"))
    if not helper_paths:
        raise ValueError("No actual prepared cases; a template is not a capture.")
    for path in helper_paths:
        helper_input = formal.frozen(path)
        inputs.append(helper_input)
        helper = formal.decoded(helper_input[1], "case helper")
        if (helper.get("protocol") != formal.HELPER_PROTOCOL
                or helper.get("matrixSpecDigest") != formal.sha(spec_input[1])):
            raise ValueError("Case helper does not bind the exact current matrix.")
        files = {}
        for entry in helper["copiedFiles"]:
            item = formal.frozen(path.parent / entry["path"])
            inputs.append(item)
            if formal.binding(item[0], item[1], path.parent) != entry:
                raise ValueError("Actual copied case bytes changed after packaging.")
            files[entry["path"]] = item[1]
        record = helper["capture"]
        if record["caseId"] in seen or (record["state"] == "baseline" and record["variantId"] in baselines):
            raise ValueError("Duplicate case ID or baseline variant.")
        seen.add(record["caseId"])
        if record["state"] == "baseline":
            baselines.add(record["variantId"])
        screen_input = formal.frozen(path.parent / STAMPED)
        inputs.append(screen_input)
        screen = formal.decoded(screen_input[1], "separately stamped receipt")
        original = formal.decoded(files["screen-receipt-unstamped.json"], "original screen receipt")
        omit = {"screenshotDigest", "browserSceneDigest"}
        if {k: v for k, v in screen.items() if k not in omit} != {k: v for k, v in original.items() if k not in omit}:
            raise ValueError("Observation facts changed during hash stamping.")
        if (screen.get("screenshotDigest") != formal.sha(files[formal.NAMES["screenshot"]])
                or screen.get("browserSceneDigest") != semantic_svg_digest(files[formal.NAMES["browserScene"]])):
            raise ValueError("Separate stamp differs from the exact actual screenshot or Scene.")
        names = {**formal.NAMES, "screenReceipt": STAMPED}
        captures.append({"caseId": record["caseId"], "variantId": record["variantId"], "state": record["state"],
                         **{field: str((path.parent / name).relative_to(HERE)) for field, name in names.items()}})
    result = {"schemaVersion": 1, "protocol": PROTOCOL, "captures": captures}
    receipt = {"schemaVersion": 1, "protocol": "archcanvas-bcf-matrix-index/1", "createdAt": now(),
               "captureCount": len(captures), "baselineCount": len(baselines),
               "matrixSpecDigest": formal.sha(spec_input[1]), "inputBindings": [formal.binding(*item) for item in inputs],
               "formalCollectionExecuted": False, "humanAcceptanceCertified": False}
    sidecar = Path(str(output) + ".receipt.json")
    if output.exists() or sidecar.exists():
        raise ValueError("Capture index or sidecar exists; choose a new numbered filename.")
    formal.recheck(inputs)
    emit(output, formal.encode(result))
    emit(sidecar, formal.encode(receipt))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify-frozen")
    snap = commands.add_parser("snapshot")
    snap.add_argument("--raw", type=Path, required=True)
    case = commands.add_parser("package")
    for name in ("raw", "browser-scene", "screenshot", "saved-envelope"):
        case.add_argument("--" + name, type=Path, required=True)
    hash_command = commands.add_parser("stamp")
    hash_command.add_argument("--case", required=True)
    index_command = commands.add_parser("index")
    index_command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "verify-frozen":
            inputs = checked()
            result = {"frozenInputsUnchanged": True, "inputBindingsChecked": len(inputs),
                      "scope": "Preparation guard only; no actual captures evaluated."}
        elif args.command == "snapshot":
            result = snapshot(args.raw)
        elif args.command == "package":
            result = package_case(args.raw, args.browser_scene, args.screenshot, args.saved_envelope)
        elif args.command == "stamp":
            result = stamp(args.case)
        else:
            result = index(args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, str(error) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
