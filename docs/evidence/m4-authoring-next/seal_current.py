"""Freeze the new authoring scope and retain all 904 previous seal bytes."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "docs/evidence/m4-authoring-next"
OUT = ROOT / "docs/evidence/m4-authoring-current-verification-sealed.json"
DOCS = ["README.md", "AGENTS.md", "docs/capability-matrix.md", "docs/acceptance.md",
        "docs/m4-completion.md", "docs/m4-exit-audit.md", "docs/m4-performance.md",
        "docs/browser-visual-matrix-protocol.md", "docs/evidence/README.md",
        "docs/m4-human-review-handoff.md", "docs/m4-ai-usability-audit.md",
        "docs/m4-holdout-integrity-audit.md", "docs/m4-authoring.md",
        "docs/evidence/m4-human-review-handoff-status.json"]


def binding(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def main():
    if OUT.exists():
        raise SystemExit("Refuse to rewrite a frozen authoring seal.")
    status = json.loads((ROOT / DOCS[-1]).read_text())
    if status["phaseStatus"] != "partial" or status["research"]["researcherCount"] != 0:
        raise SystemExit("Unexpected M4 or human claim.")
    if status["currentBrowserRepresentative"]["status"] != "independently-audited-with-explicit-limitations":
        raise SystemExit("The final independent browser report is not registered.")
    for row in status["references"].values():
        if binding(ROOT / row["path"])["sha256"] != row["sha256"]:
            raise SystemExit(f"Stale current reference: {row['path']}")

    previous = json.loads((ROOT / "docs/evidence/before-m4-authoring-next/manifest.json").read_text())
    for row in previous["bindings"]:
        actual = binding(ROOT / row["archivePath"])
        if (actual["sha256"], actual["bytes"]) != (row["sha256"], row["bytes"]):
            raise SystemExit(f"Prior frozen bytes changed: {row['path']}")
    if len(previous["bindings"]) != 904:
        raise SystemExit("Incomplete prior 904-binding preservation.")

    snapshots = WORK / "current-docs-files"
    rows = []
    for name in DOCS:
        original = ROOT / name
        target = snapshots / name
        if target.exists():
            raise SystemExit(f"Refuse to rewrite a documentation snapshot: {name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        rows.append({**binding(original), "archivePath": str(target.relative_to(ROOT))})
    (WORK / "current-docs-manifest.json").write_text(json.dumps({"files": rows}, indent=2) + "\n")

    selected = {ROOT / name for name in DOCS}
    for name in ["src", "schemas", "studio/src", "studio/tests", "studio/dist",
                 "skills/archcanvas", "docs/evidence/m4-authoring-next"]:
        selected.update(p for p in (ROOT / name).rglob("*")
                        if p.is_file() and "__pycache__" not in p.parts)
    for name in ["tests/test_authoring.py", "tests/test_authoring_http_independent.py",
                 "studio/package.json", "studio/package-lock.json", "studio/tsconfig.json",
                 "pyproject.toml", "requirements-runtime.lock",
                 "scripts/check_independence.py", "scripts/export_canvas.mjs",
                 "docs/evidence/before-m4-authoring-next/manifest.json",
                 "docs/evidence/m4-routing-current-verification-sealed.json"]:
        selected.add(ROOT / name)
    if any(p.name == "approval-key.bin" for p in selected):
        raise SystemExit("Private signing keys are not shareable evidence.")
    current = [binding(p) for p in sorted(selected)]
    result = {"schemaVersion": 1, "createdAt": datetime.now(timezone.utc).isoformat(),
              "status": "current-authoring-engineering-scope-with-open-m4-gates",
              "currentFacts": status, "bindingCount": len(current), "bindings": current,
              "previousSeal": {"sha256": previous["previousSealSha256"],
                               "resolvedBindings": 904,
                               "manifest": "docs/evidence/before-m4-authoring-next/manifest.json"},
              "limits": ["AI roles never count as real research/publication reviewers.",
                         "No previous browser matrix, current full matrix, physical review or sustained performance certification.",
                         "Generated model static contracts do not imply numerical/runtime correctness.",
                         "Interrupted first left-pan return and pre-fix click failure retained."]}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    for row in current:
        if binding(ROOT / row["path"]) != row:
            raise SystemExit(f"File changed while sealing: {row['path']}")
    print(json.dumps({"seal": str(OUT.relative_to(ROOT)), "bindings": len(current),
                      "sha256": binding(OUT)["sha256"], "priorBindingsResolved": 904}))


if __name__ == "__main__":
    main()
