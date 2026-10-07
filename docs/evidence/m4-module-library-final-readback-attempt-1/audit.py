#!/usr/bin/env python3
"""Independent readback for the BV module-library browse stage.

This script only reads files and reports exact byte/hash and source-contract
checks. It never starts the service or executes a model.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def exact_record(record: dict[str, Any]) -> dict[str, Any]:
    path = ROOT / record["path"]
    exists = path.is_file()
    actual_bytes = path.stat().st_size if exists else None
    actual_sha = sha256(path) if exists else None
    return {
        "path": record["path"],
        "exists": exists,
        "bytesExpected": record.get("bytes"),
        "bytesActual": actual_bytes,
        "sha256Expected": record.get("sha256"),
        "sha256Actual": actual_sha,
        "exact": exists and actual_bytes == record.get("bytes") and actual_sha == record.get("sha256"),
    }


def bv_record(record: dict[str, Any]) -> dict[str, Any]:
    """Keep live-path drift explicit and resolve only named BV source archives."""
    result = exact_record(record)
    archives = {
        "studio/src/AuthoringStudio.tsx": "docs/evidence/m4-module-library-work/candidate-attempt-1/AuthoringStudio.tsx",
        "studio/src/AuthoringStudio.css": "docs/evidence/m4-module-library-work/candidate-attempt-1/AuthoringStudio.css",
    }
    result["bvResolvedExact"] = result["exact"]
    if not result["exact"] and record["path"] in archives:
        archive = {**record, "path": archives[record["path"]]}
        result["bvArchive"] = exact_record(archive)
        result["bvResolvedExact"] = result["bvArchive"]["exact"]
    return result


def load(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main() -> int:
    status_path = "docs/evidence/m4-human-review-handoff-status-followup.json"
    seal_path = "docs/evidence/m4-module-library-verification-sealed-attempt-1.json"
    manifest_path = "docs/evidence/m4-module-library-work/browser-attempt-1/manifest.json"
    status = load(status_path)
    seal = load(seal_path)
    manifest = load(manifest_path)

    status_refs = [bv_record(item) for item in status.get("evidenceRefs", [])]
    seal_records = [bv_record(item) for item in seal.get("records", [])]
    self_paths = {seal_path, "docs/evidence/m4-module-library-final-readback-attempt-1/audit.py"}

    receipt_paths = {
        "target": "docs/evidence/m4-module-library-work/checks/target-attempt-1/receipt.json",
        "suite": "docs/evidence/m4-module-library-work/checks/suite-attempt-1/receipt.json",
        "build": "docs/evidence/m4-module-library-work/checks/build-attempt-1/receipt.json",
    }
    receipts: dict[str, Any] = {}
    for name, path in receipt_paths.items():
        receipt = load(path)
        receipts[name] = {
            "path": path,
            "kind": receipt.get("kind"),
            "exitCode": receipt.get("exitCode"),
            "sourceBeforeAfterExact": receipt.get("sourceBeforeAfterExact"),
            "dependenciesInstalled": receipt.get("dependenciesInstalled"),
            "modelsExecuted": receipt.get("modelsExecuted"),
            "exact": receipt.get("exitCode") == 0 and receipt.get("sourceBeforeAfterExact") is True,
            "inputsBefore": [bv_record(item) for item in receipt.get("inputsBefore", [])],
            "inputsAfter": [bv_record(item) for item in receipt.get("inputsAfter", [])],
            "logs": [exact_record(item) for item in receipt.get("logs", [])],
        }
        receipts[name]["allInputsResolvedToBvExact"] = all(item["bvResolvedExact"] for item in receipts[name]["inputsBefore"] + receipts[name]["inputsAfter"])
        receipts[name]["allLogsExact"] = all(item["exact"] for item in receipts[name]["logs"])

    def asset(path: str, expected_bytes: int, expected_sha: str) -> dict[str, Any]:
        return exact_record({"path": path, "bytes": expected_bytes, "sha256": expected_sha})

    build_js = asset(
        "studio/dist/assets/index-BV-fWDiR.js",
        477952,
        "34b2eb9990c12c4a2d3426b35f6873cfd1e7afc9f685e1954f22483043c5f830",
    )
    build_css = asset(
        "studio/dist/assets/index-QPVAzYp6.css",
        39454,
        "10afb70aa720ca53e01428e17d8487a4b4a0a06a994a69fd70d982335ceb9b08",
    )
    index = asset(
        "studio/dist/index.html",
        477,
        "d91160a58015deaa26d2df47b1c7056a6bdb75f293b9cc7da4f6cb0333111bd3",
    )

    tsx = (ROOT / "docs/evidence/m4-module-library-work/candidate-attempt-1/AuthoringStudio.tsx").read_text(encoding="utf-8")
    css = (ROOT / "docs/evidence/m4-module-library-work/candidate-attempt-1/AuthoringStudio.css").read_text(encoding="utf-8")
    draft_py = (ROOT / "src/archcanvas_authoring/draft.py").read_text(encoding="utf-8")
    presets_ts = (ROOT / "studio/src/authoringPresets.ts").read_text(encoding="utf-8")
    module_kinds = re.findall(r'_module\("([A-Za-z0-9]+)"', draft_py)
    preset_ids = re.findall(r"\{ id: '([^']+)'", presets_ts)

    before = (ROOT / "docs/evidence/m4-module-library-work/candidate-attempt-1/AuthoringStudio.before.tsx").read_text(encoding="utf-8")
    # The candidate archive is the bounded before/after source used for this
    # stage. Remove only the browse-view patch lines before comparing handler
    # snippets; this is a source readback, not a test of generated assets.
    def handler_slice(source: str) -> str:
        start = source.index("function add(module:")
        end = source.index("const categories:")
        return source[start:end]

    handler_unchanged = handler_slice(before) == handler_slice(tsx)
    source_contract = {
        "paletteViewState": "useState<'modules' | 'presets'>" in tsx,
        "defaultBasicFilter": "paletteView === 'modules'" in tsx,
        "queryCrossesBothKinds": "!!query || paletteView === 'modules'" in tsx and "!!query || paletteView === 'presets'" in tsx,
        "clearKeepsCurrentView": "清空后返回" in tsx and "setSearch('')" in tsx,
        "baseAddAndNativeDragStillPresent": "onClick={() => add(module)}" in tsx and "application/x-archcanvas-module" in tsx,
        "presetAddAndDragStillPresent": "onClick={() => addPreset(preset)}" in tsx and "application/x-archcanvas-preset" in tsx,
        "draftHandlersUnchangedAgainstCandidateBefore": handler_unchanged,
        "browseCssPresent": ".palette-browse" in css and ".palette-search-summary" in css,
    }
    source_contract["catalog17"] = len(module_kinds) == 17
    source_contract["presets3"] = len(preset_ids) == 3

    manifest_records = [exact_record(item) for item in manifest.get("records", [])]
    manifest_assets = [exact_record(item) for item in manifest.get("buildAssets", [])]
    manifest_self = manifest_path in {item.get("path") for item in manifest.get("records", [])}

    result = {
        "protocol": "archcanvas-module-library-independent-audit/1",
        "scope": "Read-only independent source, receipt, manifest, public JSON and JPEG readback for the BV module-library browse stage.",
        "status": {
            "path": status_path,
            "schemaVersion": status.get("schemaVersion"),
            "evidenceRefs": len(status.get("evidenceRefs", [])),
            "allEvidenceRefsExact": all(item["exact"] for item in status_refs),
            "allEvidenceRefsResolvedToBvExact": all(item["bvResolvedExact"] for item in status_refs),
            "records": status_refs,
        },
        "seal": {
            "path": seal_path,
            "recordCount": len(seal.get("records", [])),
            "allRecordsExact": all(item["exact"] for item in seal_records),
            "allRecordsResolvedToBvExact": all(item["bvResolvedExact"] for item in seal_records),
            "sealSelfRecordPresent": any(item["path"] in self_paths for item in seal_records),
            "records": seal_records,
        },
        "receipts": receipts,
        "buildAssets": {"index": index, "js": build_js, "css": build_css, "allExact": all(item["exact"] for item in (index, build_js, build_css))},
        "browserManifest": {
            "path": manifest_path,
            "frameCount": manifest.get("frameCount"),
            "rawFileCount": manifest.get("rawFileCount"),
            "allBuildAssetsExact": all(item["exact"] for item in manifest_assets),
            "allRawRecordsExact": all(item["exact"] for item in manifest_records),
            "manifestSelfRecordPresent": manifest_self,
            "buildAssets": manifest_assets,
            "rawRecords": manifest_records,
        },
        "sourceReadback": {
            "basis": "BV candidate archive after it was compared to the formal source at audit start; newer live source drift does not extend BV certification.",
            "catalogPath": "src/archcanvas_authoring/draft.py",
            "catalogModuleCount": len(module_kinds),
            "catalogKinds": module_kinds,
            "presetsPath": "studio/src/authoringPresets.ts",
            "presetCount": len(preset_ids),
            "presetIds": preset_ids,
            "contract": source_contract,
        },
        "conclusion": {
            "M4": "partial",
            "M5": "not_started",
            "humanParticipants": 0,
            "aiAgentsCountedAsHumans": False,
            "modelsExecuted": False,
            "dependenciesInstalled": False,
            "sourceReadbackPass": all(source_contract.values()),
            "receiptsPass": all(item["exact"] for item in receipts.values()),
            "status41Exact": len(status_refs) == 41 and all(item["exact"] for item in status_refs),
            "seal44Exact": len(seal_records) == 44 and all(item["exact"] for item in seal_records) and not any(item["path"] == seal_path for item in seal_records),
            "status41ResolvedToBvExact": len(status_refs) == 41 and all(item["bvResolvedExact"] for item in status_refs),
            "seal44ResolvedToBvExact": len(seal_records) == 44 and all(item["bvResolvedExact"] for item in seal_records) and not any(item["path"] == seal_path for item in seal_records),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
