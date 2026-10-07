"""Finite read-only arithmetic analysis; no product/model imports or old writes."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
rels = {
    "grid": "docs/evidence/m4-readable-grid-next-work/inputs/previous-workload/grid.canvas.json",
    "candidate": "docs/evidence/m4-readable-grid-next-work/candidate.canvas.json",
    "operation": "docs/evidence/m4-readable-grid-next-work/typed-operation.json",
    "gridScene": "docs/evidence/m4-readable-grid-next-work/inputs/previous-workload/grid.scene.json",
    "candidateScene": "docs/evidence/m4-readable-grid-next-work/candidate.scene.json",
    "currentDocument": "studio/src/core/document.ts",
    "frozenDocument": "docs/evidence/m4-readable-grid-next-work/inputs/formal-core/document.ts",
    "oldNativeAudit": "docs/evidence/m4-readable-grid-browser-next/root-readback-attempt-1/report.json",
    "movePreviewTests": "studio/tests/move-preview.test.ts",
    "collapseTests": "docs/evidence/m4-collapse-continuity-work/acceptance/collapse-continuity-independent.test.ts",
}
raw = {k: (PROJECT / p).read_bytes() for k, p in rels.items()}
parsed = {k: json.loads(raw[k]) for k in ("grid", "candidate", "operation", "gridScene", "candidateScene", "oldNativeAudit")}
grid, candidate, op = (parsed[k] for k in ("grid", "candidate", "operation"))
output = "output:model.DenseStress300:0"
compact_key = 'visible-frontier/1:["call:instance:model.DenseStress300"]'
deep_key = 'visible-frontier/1:["call:instance:model.DenseStress300","call:instance:model.DenseStress300.network"]'
expected = deepcopy(grid)
expected["revision"] += 1
for positions in [expected["layout"], *expected["layoutByFrontier"].values()]:
    if output in positions:
        positions[output]["x"] += op["dx"]
        positions[output]["y"] += op["dy"]
root_y = next(n["y"] for n in parsed["candidateScene"]["nodes"] if n["id"] == "call:instance:model.DenseStress300")
rows = []
for label, positions_before, positions_after in [
    ("active", grid["layout"], candidate["layout"]),
    ("compact-cache", grid["layoutByFrontier"][compact_key], candidate["layoutByFrontier"][compact_key]),
    ("deep-cache", grid["layoutByFrontier"][deep_key], candidate["layoutByFrontier"][deep_key]),
]:
    rows.append({"position": label, "localYBefore": positions_before[output]["y"], "localYAfter": positions_after[output]["y"],
                 "deltaY": positions_after[output]["y"] - positions_before[output]["y"],
                 "worldYBefore": root_y + positions_before[output]["y"], "worldYAfter": root_y + positions_after[output]["y"]})
report = {
    "schema": "archcanvas-frontier-cache-design-readback/1",
    "scope": "Independent JSON/arithmetic only; not corrected product/workload/browser acceptance.",
    "inputs": [{"role": k, "path": rels[k], "bytes": len(v), "sha256": hashlib.sha256(v).hexdigest()} for k, v in raw.items()],
    "currentDocumentEqualsFrozenPreparationDocument": raw["currentDocument"] == raw["frozenDocument"],
    "exactOrdinaryOperation": op,
    "candidateEqualsIndependentGlobalDeltaExpected": candidate == expected,
    "architectureSourceBindingExact": grid["architecture"] == candidate["architecture"] and grid["sourceBindingDigest"] == candidate["sourceBindingDigest"],
    "outputCoordinates": rows,
    "hypotheticalCurrentFrontierOnlyFromUnbrokenGrid": {"compactLocalY": 262, "compactWorldY": 354, "deepLocalY": 1664, "deepWorldY": 1756,
        "implemented": False, "candidateProduced": False},
    "oldNativeAudit": {"passed": parsed["oldNativeAudit"]["passed"], "total": parsed["oldNativeAudit"]["total"],
        "failures": [x["name"] for x in parsed["oldNativeAudit"]["checks"] if not x["passed"]]},
    "productChanged": False, "modelExecuted": False, "humanParticipantsAdded": 0, "performanceGatePassed": False,
}
with (HERE / "report.json").open("x", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(json.dumps({k: report[k] for k in ["currentDocumentEqualsFrozenPreparationDocument", "candidateEqualsIndependentGlobalDeltaExpected", "outputCoordinates", "oldNativeAudit"]}, ensure_ascii=False))
