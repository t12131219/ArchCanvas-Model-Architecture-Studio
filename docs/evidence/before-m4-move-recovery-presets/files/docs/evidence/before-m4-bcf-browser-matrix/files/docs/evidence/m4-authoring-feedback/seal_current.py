"""Seal this engineering scope without rewriting historical evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "docs/evidence/m4-authoring-feedback"
OUT = ROOT / "docs/evidence/m4-authoring-feedback-current-verification-sealed.json"
DOCS = [
    "README.md", "AGENTS.md", "docs/capability-matrix.md", "docs/acceptance.md",
    "docs/m4-completion.md", "docs/m4-exit-audit.md", "docs/m4-performance.md",
    "docs/browser-visual-matrix-protocol.md", "docs/evidence/README.md",
    "docs/m4-human-review-handoff.md", "docs/m4-ai-usability-audit.md",
    "docs/m4-authoring.md", "docs/m4-routing-refinement.md",
    "docs/m4-authoring-feedback.md", "docs/evidence/m4-human-review-handoff-status.json",
]


def binding(path):
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def verify_rows(rows):
    for row in rows:
        path = ROOT / row.get("archivePath", row["path"])
        actual = binding(path)
        assert actual["sha256"] == row["sha256"], row["path"]
        assert actual["bytes"] == row["bytes"], row["path"]


def main():
    assert not OUT.exists(), "Refuse to rewrite an existing seal."
    status = json.loads((ROOT / DOCS[-1]).read_text())
    assert status["phaseStatus"] == "partial" and not status["nextPhaseStarted"]
    assert status["research"]["researcherCount"] == 0
    assert status["currentMatrix"]["baselineCases"] == 0
    assert status["currentMatrix"]["editedModels"] == 0
    assert status["currentBrowserRepresentative"]["childOwnBrowserActions"] == 0
    for row in status["references"].values():
        assert binding(ROOT / row["path"])["sha256"] == row["sha256"], row["path"]

    prior_path = ROOT / "docs/evidence/before-m4-authoring-feedback/manifest.json"
    prior = json.loads(prior_path.read_text())
    assert len(prior["bindings"]) == 1277
    verify_rows(prior["bindings"])
    prior_seal = ROOT / "docs/evidence/before-m4-authoring-feedback/previous-seal.json"
    assert binding(prior_seal)["sha256"] == prior["previousSealSha256"]

    snapshots = WORK / "current-docs-files"
    docs_rows = []
    for name in DOCS:
        source, target = ROOT / name, snapshots / name
        assert not target.exists(), name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        docs_rows.append({**binding(source), "archivePath": str(target.relative_to(ROOT))})
    (WORK / "current-docs-manifest.json").write_text(json.dumps({"files": docs_rows}, indent=2) + "\n")

    selected = {ROOT / name for name in DOCS}
    for name in ["src", "schemas", "tests", "fixtures", "studio/src", "studio/tests",
                 "studio/dist", "skills/archcanvas", "docs/evidence/m4-authoring-feedback",
                 ".archcanvas/browser-visual-matrix-authoring-feedback-bcf",
                 ".archcanvas/m4-research-trial-authoring-feedback-bcf",
                 ".archcanvas/browser-visual-matrix-authoring-feedback-obx",
                 ".archcanvas/m4-research-trial-authoring-feedback-obx"]:
        selected.update(p for p in (ROOT / name).rglob("*")
                        if p.is_file() and "__pycache__" not in p.parts)
    for name in ["studio/package.json", "studio/package-lock.json", "studio/tsconfig.json",
                 "pyproject.toml", "requirements.lock", "requirements-runtime.lock",
                 "scripts/check_independence.py", "scripts/export_canvas.mjs",
                 "scripts/browser_visual_matrix.py", "scripts/research_trial.py"]:
        selected.add(ROOT / name)
    selected.add(prior_path)
    selected.add(prior_seal)
    selected.update(ROOT / row["path"] for row in status["references"].values())
    assert not any(p.name == "approval-key.bin" for p in selected)
    rows = [binding(p) for p in sorted(selected)]
    result = {
        "schemaVersion": 1, "createdAt": datetime.now(timezone.utc).isoformat(),
        "status": "sealed-authoring-feedback-engineering-with-open-m4-gates",
        "currentFacts": status, "bindingCount": len(rows), "bindings": rows,
        "previousSeal": {"sha256": prior["previousSealSha256"], "resolvedBindings": 1277,
                         "manifest": str(prior_path.relative_to(ROOT))},
        "limits": [
            "AI proxies never count as humans; actual UI operated by root, child read-only.",
            "Bc30 DOM samples and obx19 samples remain separate, not a complete browser matrix.",
            "Python319 retains obx193 test-time binding; current Python-related119 bytes unchanged.",
            "Exact13 core source evidence does not inherit browser/native performance.",
            "Paper save/export observed, no paper reopen/physical/font/publication review.",
            "Screenshot .png filenames retain raw JPEG API bytes; actual formats recorded.",
            "No actual user model execution/source writeback, no M5 entry or M4 completion.",
        ],
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    verify_rows(rows)
    verify_rows(docs_rows)
    print(json.dumps({"seal": str(OUT.relative_to(ROOT)), "bindings": len(rows),
                      "sha256": binding(OUT)["sha256"], "priorBindingsResolved": 1277}))


if __name__ == "__main__":
    main()
