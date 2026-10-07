"""Run only after the root reports current stage/gate/entry updates complete.

This reads mutable entries once, snapshots that exact observed state into this
new evidence directory, and compares new links with the frozen previous docs.
It never changes current docs, product, research package or old evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
BEFORE = PROJECT / "docs/evidence/m4-draft-port-legibility-work/before-current-doc-update/manifest.json"
STAGE = "docs/m4-draft-port-legibility.md"


def binding(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.relative_to(PROJECT)), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main() -> None:
    before_data = json.loads(BEFORE.read_text())
    baseline = {item["path"]: item for item in before_data["inputs"]}
    paths = [*baseline, STAGE]
    snapshot = HERE / "current-doc-snapshots"
    snapshot.mkdir(exist_ok=False)
    bindings = []
    link_checks = []
    status_observations = []
    all_text = {}
    for name in paths:
        path = PROJECT / name
        raw = path.read_bytes()
        text = raw.decode()
        all_text[name] = text
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        bindings.append({**binding(path), "snapshot": str(target.relative_to(PROJECT))})
        old_text = ""
        if name in baseline:
            frozen_path = PROJECT / baseline[name]["snapshot"]
            frozen = frozen_path.read_bytes()
            assert hashlib.sha256(frozen).hexdigest() == baseline[name]["sha256"]
            old_text = frozen.decode()
        added = [line[1:] for line in difflib.unified_diff(old_text.splitlines(), text.splitlines())
                 if line.startswith("+") and not line.startswith("+++")]
        if path.suffix == ".md":
            for line in added:
                for dest in re.findall(r"\[[^\]]+\]\(([^)]+)\)", line):
                    dest = dest.strip("<>")
                    if "://" in dest or dest.startswith("#"):
                        continue
                    resolved = path.parent / unquote(dest.split("#")[0])
                    link_checks.append({"document": name, "target": dest, "exists": resolved.exists()})
            first_block = text.split("\n## ", 2)
            prefix = "\n## ".join(first_block[:2])
            status_observations.append({"path": name, "firstSectionPrefix": prefix,
                                        "newAddedLines": added,
                                        "hasDuFXInPrefix": "DuFXKOwG" in prefix,
                                        "has342InPrefix": "342" in prefix})
    gate = json.loads(all_text["docs/evidence/m4-current-gate-audit.json"])
    checks = json.loads((PROJECT / "docs/evidence/m4-draft-port-legibility-work/checks-final-attempt-3/receipt.json").read_text())
    source_matches = []
    for item in checks["inputs"] + checks["build"]:
        current = binding(PROJECT / item["path"])
        source_matches.append({"path": item["path"], "exact": current == item})
    report = {"createdUtc": datetime.now(timezone.utc).isoformat(),
              "status": "collected-current-document-links-and-status-for-independent-manual-review",
              "scope": "15 current entry/stage/gate byte snapshots; only newly added local links checked. Historical whole-document links and visual claims are not re-certified.",
              "documentBindings": bindings,
              "beforeArchiveCountExact": len(baseline),
              "newLocalLinks": link_checks,
              "missingNewLinks": [item for item in link_checks if not item["exists"]],
              "firstSectionStatusObservations": status_observations,
              "gateObserved": gate,
              "finalSourceBuildStillExact": source_matches,
              "humanParticipantsAdded": 0,
              "mutations": "Only new current-doc-snapshots and this new report. No product/current docs or existing evidence/package changed.",
              "manualSemanticReview": "Pending; this collector is not an automatic acceptance decision."}
    (HERE / "current-doc-collected-observations.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"documents": len(bindings), "newLocalLinks": len(link_checks),
                      "missing": len(report["missingNewLinks"]),
                      "sourceBuildBindingsExact": sum(item["exact"] for item in source_matches),
                      "sourceBuildBindingsTotal": len(source_matches)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
