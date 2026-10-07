"""Narrow documentation closure; no test, product or browser execution."""
from pathlib import Path
from urllib.parse import unquote
import datetime
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[4]
WORK = Path(__file__).resolve().parent
STAGE = "docs/evidence/m4-continuous-proxy-correction-current"
BEFORE = WORK / "before-entry-inputs"
DOCS = [
    "docs/m4-performance.md", "docs/evidence/README.md",
    "docs/evidence/m4-current-gate-audit.json",
    "docs/m4-continuous-proxy-correction.md", f"{STAGE}/README.md",
]
SEAL = f"{STAGE}/entry-update-work/document-seal-final-attempt-1/manifest.json"
READBACK = f"{STAGE}/entry-update-work/document-readback.json"


def read(path):
    return json.loads((ROOT / path).read_text())


def binding(path):
    data = (ROOT / path).read_bytes()
    return {"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def exact(row, path=None):
    value = binding(path or row["path"])
    return value["bytes"] == row["bytes"] and value["sha256"] == row["sha256"]


relations = []


def require(name, passed):
    relations.append({"relation": name, "passed": bool(passed)})
    assert passed, name


old_gate = json.loads((BEFORE / DOCS[2]).read_text())
gate = read(DOCS[2])
correction = gate["latestMeasurementCorrection"]
require("only-one-gate-key-appended", {k: v for k, v in gate.items() if k != "latestMeasurementCorrection"} == old_gate)
require("memory-product-stage-retained", gate["currentStage"] == "docs/m4-memory-continuity.md" and gate["build"] == old_gate["build"])
require("m4-partial-m5-not-started-human-zero", gate["overall"] == "partial" and gate["m5"] == "not_started" and gate["humanParticipants"] == 0)
require("research-package-metadata-retained", gate["currentResearchPackage"] == old_gate["currentResearchPackage"])
require("correction-gate-honest-scope", correction["formalTests"]["passed"] == 71 and correction["formalTests"]["newIndependent"] == 44 and not correction["formalTests"]["addedToStudioTestCount"] and not correction["performanceGatePassed"] and not correction["frontierScopeImplemented"])
for path in DOCS[:2]:
    before = (BEFORE / path).read_bytes()
    current = (ROOT / path).read_bytes()
    require(path + ":historical-body-exact", before.split(b"\n## ", 2)[2] == current.split(b"\n## ", 2)[2])
    require(path + ":current-memory-header-retained", before.split(b"\n## ", 2)[1].split(b"\n", 1)[0] == current.split(b"\n## ", 2)[1].split(b"\n", 1)[0])
for path in DOCS:
    require(path + ":prepared-bytes-exact", (ROOT / path).read_bytes() == (WORK / "preview-final-attempt-1" / path).read_bytes())

freeze = read(f"{STAGE}/entry-update-work/before-entry-inputs/manifest.json")
for row in freeze["frozenEntries"]:
    require(row["path"] + ":before-snapshot-exact", exact(row, row["snapshot"]))
old_seal = freeze["oldMemoryDocumentSeal"]
require("old-memory-seal-manifest-live-and-copy-exact", exact(old_seal) and exact(old_seal, old_seal["snapshot"]))
resolution = freeze["oldMemorySealResolution"]["bindings"]
resolved = sum(exact(row, row["resolvedPath"]) for row in resolution)
require("old-memory-248-seal-explicit-resolution-exact", len(resolution) == resolved == 248 and sum(row["path"] != row["resolvedPath"] for row in resolution) == 3)

root_readback = read(f"{STAGE}/root-final-readback.json")
require("root-finite-readback-matches-reported-counts", all(root_readback["bindings"][k]["exact"] == n == root_readback["bindings"][k]["total"] for k, n in [("independentFinite", 13), ("replayFinite", 8), ("productFinite", 129)]) and root_readback["formalTAPCounts"] == {"tests": 71, "pass": 71, "fail": 0, "cancelled": 0, "skipped": 0, "todo": 0})
replay = read(f"{STAGE}/replay-attempt-1/report.json")
require("replay-33-relations-17-exact-retained", replay["passedRelations"] == replay["totalRelations"] == 33 and replay["exactIndependentRows"] == 17 and not replay["productChanged"] and not replay["browserRerun"] and not replay["performanceGatePassed"])
require("per-input-observation-boundary-explicit", "observedAt ≥ 该输入 capturedAt" in (ROOT / DOCS[3]).read_text())
require("historical-failure-and-frontier-design-scope-explicit", all(text in (ROOT / DOCS[3]).read_text() for text in ["26/29", "no-input drag 仍失败", "scope 尚未实现", "不是当前 CU5 的新浏览器性能测试"]))
research = read(f"{STAGE}/entry-update-work/research-listed-bindings-readback.json")
require("finite-research-list-not-new-readiness", research["listedImplementationBindingsPassed"] == research["listedImplementationBindingsTotal"] == 87 and len(research["validatorsOutsideListedInventory"]) == 2 and exact(research["manifest"]))

# Recheck the same five documentation files after the capturedAt wording change.
diff_rows = []
for path in DOCS:
    baseline = BEFORE / path
    if not baseline.exists():
        baseline = WORK / "new-file-empty-baseline"
    proc = subprocess.run(["git", "diff", "--no-index", "--check", "--", str(baseline), str(ROOT / path)], capture_output=True, text=True)
    passed = proc.returncode in (0, 1) and not proc.stdout and not proc.stderr
    diff_rows.append({"path": path, "exitCode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "whitespaceCheckPassed": passed})
require("five-owned-document-whitespace-checks", all(row["whitespaceCheckPassed"] for row in diff_rows))
(WORK / "scoped-diff-check.json").write_text(json.dumps({"schema": "archcanvas-continuous-proxy-doc-scoped-diff/1", "driverExitCode": 0, "paths": diff_rows, "scope": "git --no-index exit1 denotes differences with empty diagnostics; only exit0/1 and no whitespace/error output accepted."}, ensure_ascii=False, indent=2) + "\n")
require("skill-structure-check-exit0", read(f"{STAGE}/entry-update-work/skill-check.json")["exitCode"] == 0)


def links(deferred):
    rows = []
    for path in [DOCS[0], DOCS[1], DOCS[3], DOCS[4]]:
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", (ROOT / path).read_text()):
            target = target.split(" \"", 1)[0].strip("<>")
            if target.startswith(("https:", "http:", "app:", "codex:", "mailto:", "#")):
                continue
            target = unquote(target.split("#", 1)[0])
            resolved = ((ROOT / path).parent / target).resolve()
            relative = resolved.relative_to(ROOT).as_posix()
            state = "exists" if resolved.exists() else "deferred-output" if relative in deferred else "missing"
            rows.append({"source": path, "target": target, "resolvedPath": relative, "state": state})
    return rows


link_rows = links({READBACK, SEAL})
require("five-file-local-links-or-declared-closing-output", all(row["state"] != "missing" for row in link_rows))
report = {
    "schema": "archcanvas-continuous-proxy-document-readback/1",
    "createdUtc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "passedRelations": len(relations), "totalRelations": len(relations),
    "relationships": relations,
    "oldMemorySealResolved": {"passed": 248, "total": 248, "snapshotPaths": 3, "unchangedPaths": 245},
    "localLinks": {"checked": len(link_rows), "existing": sum(row["state"] == "exists" for row in link_rows), "deferredClosingOutput": [row for row in link_rows if row["state"] == "deferred-output"], "rows": link_rows},
    "scope": "Five owned documentation paths, unchanged old gate fields/history, explicit old248seal resolution, retained finite root/report facts and links. No product tests, research protocol or browser rerun; deferred closing links are checked after sealing.",
}
(ROOT / READBACK).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

inputs = set(DOCS + [
    READBACK, f"{STAGE}/entry-update-work/prepare_documents.py",
    f"{STAGE}/entry-update-work/seal_documents.py",
    f"{STAGE}/entry-update-work/before-entry-inputs/manifest.json",
    f"{STAGE}/entry-update-work/before-entry-inputs/memory-document-seal.manifest.json",
    f"{STAGE}/entry-update-work/research-listed-bindings-readback.json",
    f"{STAGE}/entry-update-work/scoped-diff-check.json",
    f"{STAGE}/entry-update-work/skill-check.json",
    f"{STAGE}/entry-update-work/verification-attempt-1.json",
    f"{STAGE}/root-final-readback.json", f"{STAGE}/independent-report.json",
    f"{STAGE}/independent-review.md", f"{STAGE}/replay-attempt-1/report.json",
    f"{STAGE}/replay-attempt-1/validator.stdout.json", f"{STAGE}/replay-attempt-1/validator.stderr.log",
    old_seal["path"], research["manifest"]["path"],
])
inputs.update(row["snapshot"] for row in freeze["frozenEntries"])
inputs.update(row["path"] for row in read(f"{STAGE}/independent-report.json")["bindings"])
inputs.update(row["path"] for row in replay["inputBindings"])
inputs.update(["docs/evidence/m4-continuous-proxy-correction-next/README.md", "docs/evidence/m4-frontier-cache-analysis-next/README.md"])
rows = [binding(path) for path in sorted(inputs)]
manifest = {
    "schema": "archcanvas-continuous-proxy-document-seal/1",
    "createdUtc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "documentationRelationsPassed": len(relations), "documentationRelationsTotal": len(relations),
    "externalBindingCount": len(rows), "externalBindings": rows,
    "scope": "Finite documentation closure and its selected exact sources, reports and logs. Original memory248seal is preserved and resolves its three changed paths to explicit old snapshots. This seal is not a new transitive product inventory, independent browser audit, research participant record, paint/performance certificate or M4 pass.",
}
(ROOT / SEAL).parent.mkdir(exist_ok=False)
(ROOT / SEAL).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
final_links = links(set())
assert all(row["state"] == "exists" for row in final_links)
assert all(exact(row) for row in rows)
closure = {
    "schema": "archcanvas-continuous-proxy-document-seal-readback/1",
    "manifest": binding(SEAL), "bindingsPassed": len(rows), "bindingsTotal": len(rows),
    "localLinksPassed": len(final_links), "localLinksTotal": len(final_links),
    "localLinks": final_links,
    "scope": "Final finite seal-byte and five-document link existence confirmation after closing outputs were written; no tests or browser actions.",
}
(ROOT / SEAL).with_name("seal-readback.json").write_text(json.dumps(closure, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"relations": f"{len(relations)}/{len(relations)}", "oldMemorySealResolved": "248/248", "documentSealBindings": len(rows), "links": f"{len(final_links)}/{len(final_links)}", "manifest": closure["manifest"]}, ensure_ascii=False))
