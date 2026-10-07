"""Resolve a literal matcher false alert using frozen prior audit results.

No mutable product/document paths are reread after subsequent product work.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIRST = "docs/evidence/m4-authoring-guidance-final-readback-attempt-1/report.json"
SECOND = "docs/evidence/m4-authoring-guidance-final-readback-attempt-2/report.json"
SEAL2 = "docs/evidence/m4-authoring-guidance-verification-sealed-attempt-2.json"


def identity(path):
    data = (ROOT / path).read_bytes()
    return {"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    first = json.loads((ROOT / FIRST).read_text())
    second = json.loads((ROOT / SECOND).read_text())
    errors = []
    intended_false_alert = {"check": "stageNamesCorrectedPreviewAndRetainsInvalidSelfRecord"}
    if second["mismatches"] != [intended_false_alert]:
        errors.append({"check": "priorReportHasExactlyTheKnownLiteralAlert"})
    for name, result in second["checks"].items():
        if result.get("mismatches"):
            errors.append({"check": name, "mismatches": result["mismatches"]})
    if any(row["missing"] for row in second["currentLeadAssertions"]):
        errors.append({"check": "allCurrentLeadAssertionsPass"})
    for row in second["inputs"]:
        if row["path"] in (FIRST, SEAL2):
            if identity(row["path"]) != row:
                errors.append({"check": "immutableInputStillExact", "path": row["path"]})
    if first["checks"]["localLinks"]["missingLocalDestinations"]:
        errors.append({"check": "earlierLocalLinksWereClear"})
    report = {
        "protocol": "archcanvas-guidance-independent-final-readback-interpretation/1",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "reviewer": "/root/guidance_acceptance", "reviewerType": "AI; not human",
        "verdict": "bounded-corrected-guidance-readback-pass-with-original-failures-retained" if not errors else "failed",
        "scope": "Interpretation of frozen attempt2 results. No343/431/333 binding rerun, local-link rescan or mutable file read after subsequent module-library product work began.",
        "literalMatcherCorrection": {
            "priorFalseAlert": intended_false_alert,
            "stagePath": "docs/m4-authoring-guidance.md",
            "observedBeforeSubsequentProductChange": {
                "line17": "恢复草稿并fit后的[预览交接](evidence/m4-authoring-guidance-work/preview-handoff-attempt-2/manifest.json)单列，不追加到22组验收原始目录",
                "line19": "独立末读发现首份交接manifest自记录为零字节（先打开文件再枚举目录造成），原件与首次封印保留为失败ledger。修正attempt2仅复制三份原始交接文件且排除自记录；没有重新操作浏览器或新增验收帧。首次封印只说明字节被冻结，不能证明其内部清单正确。",
                "readMethod": "Read-only rg -n immediately after attempt2; direct source line read, not inferred from hash.",
            },
            "finding": "The document names corrected preview attempt2 and explicitly retains the zero-byte self-record failure. Chinese 零字节 and literal0B have the same meaning. The matcher incorrectly demanded the latter spelling; document content is correct.",
            "auditMistakeAcknowledged": True,
        },
        "acceptedFrozenResults": {
            "currentSealBindings": {"exact": 343, "total": 343},
            "priorBsaResolvedBindings": {"exact": 431, "total": 431, "current": 426, "explicitArchive": 5},
            "initialSealResolvedBindings": {"exact": 333, "total": 333, "current": 331, "explicitArchive": 2},
            "statusRefs": {"exact": 33, "total": 33},
            "handoffFilesAndOriginalCopies": {"exact": 3, "total": 3},
            "currentStatusAssertions": second["checks"]["currentStatusAssertions"],
            "currentLeadFiles": len(second["currentLeadAssertions"]),
            "localFileLinks": second["reusedLocalLinkScan"]["localFileDestinations"],
            "missingLocalFileLinks": [],
        },
        "retainedActualFailures": first["failures"],
        "earlierSkillAssetMatcherClarification": second["earlierLeadMatcherClarification"],
        "inputs": [identity(FIRST), identity(SECOND), identity(SEAL2)],
        "mismatches": errors,
        "boundaries": second["boundaries"] + [
            "This pass is for the exact guidance snapshot read by attempt2 before module-library changes; it is not certification of any later product build.",
            "Original attempt1/attempt2 reports are unchanged; historical genuine failures and audit literal false alerts remain inspectable.",
        ],
        "auditSource": identity(str(Path(__file__).relative_to(ROOT))),
    }
    output = Path(__file__).with_name("report.json")
    with output.open("x") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"report": identity(str(output.relative_to(ROOT))),
                      "verdict": report["verdict"], "mismatches": errors}, ensure_ascii=False))


if __name__ == "__main__":
    main()
