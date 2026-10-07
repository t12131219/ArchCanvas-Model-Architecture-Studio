"""Independently read back and bind finite routing proposal evidence."""
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
out = HERE / "sealed-readback-attempt-1"
assert not out.exists(), "Evidence is append-only"
out.mkdir()
checks, inputs = [], {}


def bind(p):
    data = p.read_bytes()
    return {"path": str(p.relative_to(ROOT)), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check(name, value):
    checks.append({"name": name, "passed": bool(value)})


proposal_path = HERE / "frozen-proposal-attempt-1/report.json"
frontier_path = HERE / "historical-frontier-proposal-attempt-1/report.json"
proposal = json.loads(proposal_path.read_text())
frontier = json.loads(frontier_path.read_text())
for report in [proposal, frontier]:
    for expected in report["inputBindings"]:
        p = ROOT / expected["path"]
        actual = bind(p)
        check("exact sealed input " + expected["path"], actual == expected)
        inputs[expected["path"]] = actual
check("504 rows exactly", len(proposal["rows"]) == proposal["proposalRows"] == proposal["scenes"] == 504)
check("312 eligible 192 retained no rejected", Counter(x["status"] for x in proposal["rows"]) == {"eligible": 312, "retained": 192})
for row in proposal["rows"]:
    if row["status"] != "eligible":
        continue
    check("eligible no body/peer/stroke geometry failure " + row["case"],
          not row["reasons"] and not row["bodyHits"] and not row["peerChanges"] and not row["strokeContacts"])
    check("proposal length never longer " + row["case"], row["lengthAfter"] <= row["lengthBefore"] + 1e-6)
rows = {r["case"]: r for r in proposal["rows"] if r["group"] == "production-label-only"}
thresholds = []
for sign in ["", "-"]:
    for mode in ["default", "empty", "custom"]:
        for preset in ["paper", "monochrome"]:
            for width in [85, 180]:
                for scope in ["whole", "detail"]:
                    a = rows[f"{mode}-dy{sign}14-{preset}-{width}-{scope}"]
                    b = rows[f"{mode}-dy{sign}15-{preset}-{width}-{scope}"]
                    delta = {"cases": [a["case"], b["case"]], "bothEligible": a["status"] == b["status"] == "eligible",
                             "lengthDelta": b["lengthAfter"] - a["lengthAfter"],
                             "sourceDisplacement": math.dist(a["proposalPoints"][0], b["proposalPoints"][0]),
                             "targetDisplacement": math.dist(a["proposalPoints"][-1], b["proposalPoints"][-1])}
                    thresholds.append(delta)
                    check("signed threshold continuous " + a["case"], delta["bothEligible"] and
                          abs(delta["lengthDelta"] - 1) < 1e-6 and abs(delta["sourceDisplacement"] - 1) < 1e-6 and delta["targetDisplacement"] == 0)
check("48 signed threshold presentation pairs", len(thresholds) == 48)
check("nine198frontierssevenmemory", frontier["sourceFrontierCount"] == 9 and frontier["routeOccurrences"] == 198 and frontier["memoryOccurrences"] == 7)
check("historical one eligible six retained", frontier["statusCounts"] == {"eligible": 1, "retained": 6})
report = {"schema": "archcanvas-routing-research-sealed-readback/1", "createdUtc": datetime.now(timezone.utc).isoformat(),
          "passed": sum(x["passed"] for x in checks), "total": len(checks), "checks": checks,
          "failedChecks": [x for x in checks if not x["passed"]], "thresholdPairs": thresholds,
          "uniqueExternalInputBindings": len(inputs),
          "scope": "Artifact and finite geometric proposal relationships only. No implemented product, product test pass, browser, physical publication, human acceptance or global aesthetics certification."}
(out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
files = sorted(p for p in HERE.rglob("*") if p.is_file())
product_refs = [ROOT / "studio/src/core" / n for n in ["scene.ts", "orthogonalRouter.ts", "edgeLabelPlacement.ts", "nodeVisualOutline.ts"]]
manifest = {"schema": "archcanvas-routing-research-seal/1", "externalInputs": sorted(inputs.values(), key=lambda x: x["path"]),
            "researchFiles": [bind(p) for p in files], "productReadOnlyReferences": [bind(p) for p in product_refs],
            "scope": "Research outputs and scripts sealed with current source references. Does not imply every transitive product source dependency is inventoried; no product bytes were written by these scripts."}
(out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"passed": report["passed"], "total": report["total"], "uniqueExternalInputs": len(inputs),
                  "researchFiles": len(files), "productReadOnlyReferences": len(product_refs)}))
raise SystemExit(0 if report["passed"] == report["total"] else 1)
