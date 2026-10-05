"""Bind the completed AI usability scope without rewriting historical seals."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/evidence/m4-routing-current-verification-sealed.json"
WORK = ROOT / "docs/evidence/m4-ai-usability-next"
DOCS = [
    "README.md", "AGENTS.md", "docs/capability-matrix.md",
    "docs/acceptance.md", "docs/m4-completion.md", "docs/m4-exit-audit.md",
    "docs/m4-performance.md", "docs/browser-visual-matrix-protocol.md",
    "docs/evidence/README.md", "docs/m4-human-review-handoff.md",
    "docs/m4-ai-usability-audit.md", "docs/m4-holdout-integrity-audit.md",
    "docs/evidence/m4-human-review-handoff-status.json",
]


def binding(path: Path) -> dict:
    raw = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)), "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def main() -> None:
    if OUT.exists():
        raise SystemExit("Refuse to overwrite an existing seal.")
    status = json.loads((ROOT / DOCS[-1]).read_text())
    if status["currentBrowserRepresentative"]["status"] != "independently-audited-with-explicit-limitations":
        raise SystemExit("Final browser audit is not registered.")
    if status["phaseStatus"] != "partial" or status["research"]["researcherCount"] != 0:
        raise SystemExit("Unexpected phase or human acceptance claim.")

    snapshots = WORK / "current-docs-files"
    rows = []
    for name in DOCS:
        src = ROOT / name
        dst = snapshots / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            raise SystemExit(f"Refuse to overwrite snapshot: {name}")
        shutil.copyfile(src, dst)
        row = binding(src)
        row["archivePath"] = str(dst.relative_to(ROOT))
        rows.append(row)
    (WORK / "current-docs-manifest.json").write_text(
        json.dumps({"schemaVersion": 1, "files": rows}, ensure_ascii=False, indent=2) + "\n"
    )

    selected = {ROOT / name for name in DOCS}
    directories = [
        "src", "studio/src", "studio/tests", "studio/dist", "skills/archcanvas",
        "docs/evidence/m4-ai-usability-next",
        "docs/evidence/m4-holdout-integrity-audit",
        "docs/evidence/m4-current-native-cancellation-work",
        "docs/evidence/m4-research-readiness-work",
        "docs/evidence/visual-golds-routing-visible",
        "docs/evidence/before-ai-usability-next",
        "docs/evidence/before-routing-obstacle-fix",
        ".archcanvas/m4-research-trial-routing-visible",
        ".archcanvas/browser-visual-matrix-routing-visible",
    ]
    for name in directories:
        for path in (ROOT / name).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                selected.add(path)
    for name in [
        "tests/m4_holdout_integrity_oracle.py", "tests/test_m4_holdout_integrity.py",
        "scripts/check_m4_holdout_integrity.py",
        "docs/evidence/m4-boundary-current-verification-final-sealed-v2.json",
        "studio/package.json", "studio/package-lock.json", "studio/tsconfig.json",
    ]:
        selected.add(ROOT / name)

    for reference in status["references"].values():
        actual = binding(ROOT / reference["path"])
        if actual["sha256"] != reference["sha256"]:
            raise SystemExit(f"Stale current reference: {reference['path']}")
    old_resolution = json.loads((ROOT / "docs/evidence/before-ai-usability-next/v2-resolution.json").read_text())
    if old_resolution["resolved"] != 1589 or old_resolution["unresolved"]:
        raise SystemExit("Historical v2 byte resolution is incomplete.")
    for row in old_resolution["resolutions"]:
        actual = binding(ROOT / row["resolvedPath"])
        if (actual["sha256"], actual["bytes"]) != (row["sha256"], row["bytes"]):
            raise SystemExit(f"Historical resolution changed: {row['originalPath']}")

    bindings = [binding(path) for path in sorted(selected)]
    result = {
        "schemaVersion": 1, "createdAt": datetime.now(timezone.utc).isoformat(),
        "status": "current-byte-bindings-with-explicit-incomplete-m4-gates",
        "currentFacts": status,
        "bindingCount": len(bindings), "bindings": bindings,
        "limitations": [
            "Byte bindings are not human, publication or sustained presented-performance certification.",
            "Current full browser matrix is not collected; representative UI observations remain separate.",
            "Historical v2 resolves all 1589 original bytes; earlier b81 performance document is unresolved outside this scope.",
            "Five unsealed intermediate Dgt right captures were overwritten and are excluded with an explicit error ledger.",
        ],
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    reread = json.loads(OUT.read_text())
    for row in reread["bindings"]:
        if binding(ROOT / row["path"]) != row:
            raise SystemExit(f"New binding changed during sealing: {row['path']}")
    print(json.dumps({"seal": str(OUT.relative_to(ROOT)), "bindings": len(bindings),
                      "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
