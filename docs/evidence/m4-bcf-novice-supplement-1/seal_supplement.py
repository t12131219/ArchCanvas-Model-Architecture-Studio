"""Append the real blank-draft browser sample without rewriting the main seal."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SEAL = HERE / "sealed.json"
MAIN = ROOT / "docs/evidence/m4-bcf-browser-matrix-current-verification-sealed.json"
FINAL_REVIEW = ROOT / "docs/evidence/m4-bcf-browser-matrix-work/final-seal-review-1/manifest.json"


def record(path):
    assert not path.is_symlink()
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check(item):
    assert record(ROOT / item["path"]) == item


assert not SEAL.exists(), "New evidence seals must not overwrite an existing file"
assert record(MAIN)["sha256"] == "170be658b4b76e2217bb0d58397f586fc1f8fdccd66278961d657116952a5551"
assert (HERE / "independent-review-1/manifest.json").exists()
operator = json.loads((HERE / "operator-summary.json").read_text())
assert operator["generatedSourceExact"] and operator["paperPublicSvgExact"]
assert operator["modelExecution"] == "not_run" and operator["humanResearchers"] == 0
files = [path for path in HERE.rglob("*") if path.is_file() and path != SEAL and "__pycache__" not in path.parts and path.suffix != ".pyc"]
bindings = [record(path) for path in sorted(files)]
document = {
    "schemaVersion": 1,
    "sealedAt": datetime.now(timezone.utc).isoformat(),
    "scope": "Root-operated actual Bc blank-draft four-module chain, public generated source and save/reopen SVG, independent AI file/pixel review; appended after main2894 freeze without modifying it.",
    "mainSeal": record(MAIN),
    "mainSealIndependentReview": record(FINAL_REVIEW),
    "bindingCount": len(bindings),
    "bindings": bindings,
    "phaseStatus": "partial",
    "nextPhaseStarted": False,
    "humanCertified": False,
    "modelExecution": "not_run",
    "all17ModulesBrowserTested": False,
    "publicationCertified": False,
    "presentedPerformanceCertified": False,
    "operator": "root native CUA; child independent read-only review",
    "limits": ["Four basic palette modules/one minimalMLP only", "DeltaAX receipts prove local results; root tool actions supply gesture attribution", "Old16-to32-to8 paper reopen remains outside this new16-to32ReLU sample", "No inferred savedCanvas/hiddenhistory/runtime or human learning-cost acceptance", "First exact-text wait failed; subsequent correct publicDOM/SVG observed", "No product edits/tests or mainseal/status rewrite"],
}
with SEAL.open("x") as stream:
    json.dump(document, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
for binding in bindings:
    check(binding)
check(document["mainSeal"])
check(document["mainSealIndependentReview"])
print(json.dumps({"supplementSeal": record(SEAL), "bindingCount": len(bindings), "mainSealUnchanged": True, "humanCertified": False}))
