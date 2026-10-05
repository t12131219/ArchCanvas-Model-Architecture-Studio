"""Freeze this routing/AI exploration scope without rewriting historical seals."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "docs/evidence/m4-routing-refinement"
OUT = ROOT / "docs/evidence/m4-routing-refinement-current-verification-sealed.json"
DOCS = ["README.md", "AGENTS.md", "docs/capability-matrix.md", "docs/acceptance.md",
        "docs/m4-completion.md", "docs/m4-exit-audit.md", "docs/m4-performance.md",
        "docs/browser-visual-matrix-protocol.md", "docs/evidence/README.md",
        "docs/m4-human-review-handoff.md", "docs/m4-authoring.md",
        "docs/m4-routing-refinement.md", "docs/evidence/m4-human-review-handoff-status.json"]


def binding(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def verify_prior(path: str, expected: int):
    manifest = json.loads((ROOT / path).read_text())
    if len(manifest["bindings"]) != expected:
        raise ValueError(f"Incomplete historical archive: {path}")
    for row in manifest["bindings"]:
        actual = binding(ROOT / row["archivePath"])
        if (actual["sha256"], actual["bytes"]) != (row["sha256"], row["bytes"]):
            raise ValueError(f"Historical bytes changed: {row['path']}")


def main():
    if OUT.exists():
        raise SystemExit("Refuse to rewrite a frozen routing seal.")
    status = json.loads((ROOT / DOCS[-1]).read_text())
    assert status["phaseStatus"] == "partial" and not status["nextPhaseStarted"]
    assert status["research"]["researcherCount"] == 0
    assert status["proxyExploration"]["status"] == "three-roles-completed-with-explicit-limitations"
    assert status["productionJsSha256"] == binding(ROOT / "studio/dist/assets/index-CVO3JbfE.js")["sha256"]
    for row in status["references"].values():
        assert binding(ROOT / row["path"])["sha256"] == row["sha256"], row["path"]
    verify_prior("docs/evidence/before-m4-routing-refinement/manifest.json", 327)
    verify_prior("docs/evidence/before-m4-authoring-next/manifest.json", 904)

    snapshots = WORK / "current-docs-files"
    docs = []
    for name in DOCS:
        source, target = ROOT / name, snapshots / name
        if target.exists():
            raise SystemExit(f"Refuse to replace a snapshot: {name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        docs.append({**binding(source), "archivePath": str(target.relative_to(ROOT))})
    (WORK / "current-docs-manifest.json").write_text(json.dumps({"files": docs}, indent=2) + "\n")

    selected = {ROOT / n for n in DOCS}
    for folder in ["src", "schemas", "studio/src", "studio/tests", "studio/dist",
                   "skills/archcanvas", "docs/evidence/m4-routing-refinement",
                   "docs/evidence/m4-proxy-exploration",
                   "docs/evidence/visual-golds-routing-refinement",
                   ".archcanvas/browser-visual-matrix-routing-refinement",
                   ".archcanvas/research-trial-routing-refinement"]:
        selected.update(p for p in (ROOT / folder).rglob("*")
                        if p.is_file() and "__pycache__" not in p.parts)
    for name in ["studio/package.json", "studio/package-lock.json", "studio/tsconfig.json",
                 "pyproject.toml", "requirements-runtime.lock", "scripts/check_independence.py",
                 "scripts/export_canvas.mjs", "scripts/check_visual_golds.py",
                 "scripts/browser_visual_matrix.py", "scripts/browser_visual_core.mjs",
                 "scripts/research_trial.py", "scripts/research_trial_core.mjs",
                 "docs/evidence/m4-authoring-current-verification-sealed.json",
                 "docs/evidence/before-m4-routing-refinement/manifest.json",
                 "docs/evidence/before-m4-authoring-next/manifest.json"]:
        selected.add(ROOT / name)
    if any(p.name == "approval-key.bin" for p in selected):
        raise SystemExit("Private signing keys are not shareable evidence.")
    rows = [binding(p) for p in sorted(selected)]
    seal = {"schemaVersion": 1, "createdAt": datetime.now(timezone.utc).isoformat(),
            "status": "routing-and-proxy-engineering-scope-with-open-m4-gates",
            "currentFacts": status, "bindingCount": len(rows), "bindings": rows,
            "previousScopes": [{"archive": "docs/evidence/before-m4-routing-refinement/manifest.json",
                                "bindingsResolved": 327},
                               {"archive": "docs/evidence/before-m4-authoring-next/manifest.json",
                                "bindingsResolved": 904}],
            "limits": status["limitations"]}
    OUT.write_text(json.dumps(seal, ensure_ascii=False, indent=2) + "\n")
    for row in rows:
        assert binding(ROOT / row["path"]) == row, row["path"]
    print(json.dumps({"seal": str(OUT.relative_to(ROOT)), "bindings": len(rows),
                      "sha256": binding(OUT)["sha256"], "priorResolved": [327, 904]}))


if __name__ == "__main__":
    main()
