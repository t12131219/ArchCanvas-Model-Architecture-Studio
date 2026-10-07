"""Freeze only this round's bounded evidence; never rewrite a prior seal.

Run from the formal project with .venv/bin/python. No product, model, browser,
network, dependency installation, or build execution occurs here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
WORK = Path("docs/evidence/m4-move-recovery-presets-work")
BROWSER = Path("docs/evidence/m4-move-recovery-presets-browser")
FINAL = BROWSER / "final-ChS0wIgb"
BROWSER_MANIFEST = BROWSER / "evidence-manifest.json"
SEAL = Path("docs/evidence/m4-move-recovery-presets-current-verification-sealed.json")
STATUS = Path("docs/evidence/m4-human-review-handoff-status.json")
PRODUCT = WORK / "root/final-product-validation.json"
ARCHIVE = Path("docs/evidence/before-m4-move-recovery-presets/manifest.json")
LEGACY_SEAL = Path("docs/evidence/m4-bcf-browser-matrix-current-verification-sealed.json")
DOCS = [
    "README.md", "AGENTS.md", "docs/acceptance.md", "docs/capability-matrix.md",
    "docs/evidence/README.md", "docs/m4-authoring-feedback.md",
    "docs/m4-exit-audit.md", "docs/m4-human-review-handoff.md",
    "docs/m4-ai-usability-audit.md", "docs/m4-bcf-browser-matrix.md",
    "docs/m4-performance.md", "docs/m4-routing-refinement.md",
    "docs/browser-visual-matrix-protocol.md", "docs/m4-completion.md",
    "docs/m4-authoring.md", "docs/m4-move-recovery-presets.md",
]


def read(path: Path):
    return json.loads((ROOT / path).read_text())


def binding(path: Path):
    raw = (ROOT / path).read_bytes()
    return {"path": path.as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def check(row, path=None):
    actual = binding(Path(path or row["path"]))
    assert actual["sha256"] == row["sha256"], actual["path"]
    if "bytes" in row:
        assert actual["bytes"] == row["bytes"], actual["path"]


def write_exclusive(path: Path, value):
    with (ROOT / path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def files(directory: Path):
    return {path.relative_to(ROOT) for path in (ROOT / directory).rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
            and path.suffix != ".pyc"}


def guards():
    product = read(PRODUCT)
    for path, sha in product["sourceBindings"].items():
        check({"path": path, "sha256": sha})
    for row in product["assets"]:
        check(row)
    assert product["studio"] == {
        "passed": 152, "failed": 0, "skipped": 0, "exit": 0,
        "log": "studio-full-final.log"}
    assert product["strictBuild"]["exit"] == 0
    assert product["independence"]["passed"]
    assert len(product["independence"]["checks"]) == 9
    archive = read(ARCHIVE)
    assert archive["bindingCount"] == len(archive["bindings"]) == 2894
    for row in archive["bindings"]:
        check(row, row["archivePath"])
    check({"path": LEGACY_SEAL.as_posix(),
           "sha256": archive["previousSealSha256"]})
    return product, archive


def sample_range():
    captures = sorted((ROOT / FINAL).glob("*.public.json"))
    images = sorted((ROOT / FINAL).glob("*.png"))
    assert len(captures) == 23 and len(images) == 46
    for capture in captures:
        stem = capture.name.removesuffix(".public.json")
        for suffix in [".png", ".primer.png", ".before.dom.txt", ".after.dom.txt"]:
            assert (ROOT / FINAL / (stem + suffix)).is_file(), stem + suffix
        public = json.loads(capture.read_text())
        assert public["scripts"] == ["/assets/index-ChS0wIgb.js"]
    assert all(image.read_bytes().startswith(b"\xff\xd8") for image in images)
    return {"publicDomStems": 23, "imageFiles": 46,
            "imageEncoding": "JPEG; filenames retain .png suffix",
            "full39Matrix": False, "humanCount": 0,
            "imageDimensionCorrection": (BROWSER / "work/final-ChS0wIgb-independent/dimensions-format-correction.json").as_posix()}


def freeze_browser():
    product, _ = guards()
    audit = ROOT / BROWSER / "work/final-ChS0wIgb-independent/final-audit-summary.json"
    assert audit.is_file(), "Independent final audit must finish before freeze"
    selected = files(BROWSER) - {BROWSER_MANIFEST}
    selected |= {PRODUCT} | {Path(row["path"]) for row in product["assets"]}
    rows = [binding(path) for path in sorted(selected)]
    value = {"schemaVersion": 1, "frozenAt": datetime.now(timezone.utc).isoformat(),
             "scope": "This round's original attempts, failures, separate intermediate/final captures and independent audits; hash identity is not visual/human certification.",
             "productionBuild": "index-ChS0wIgb.js", "finalSampleRange": sample_range(),
             "bindingCount": len(rows), "bindings": rows,
             "excluded": ["**/__pycache__/**", "**/*.pyc", "this manifest itself"],
             "limits": ["46 images were independently viewed for coarse state only",
                        "23 public SVGs and 140 routes are bounded geometry observations",
                        "Retained earlier mismatches are not successful captures",
                        "No full39, presented-performance, physical publication or human certification"]}
    write_exclusive(BROWSER_MANIFEST, value)
    print(json.dumps({"manifest": binding(BROWSER_MANIFEST), "bindings": len(rows)}))


def freeze_seal():
    product, archive = guards()
    browser = read(BROWSER_MANIFEST)
    for row in browser["bindings"]:
        check(row)
    status = read(STATUS)
    assert status["phaseStatus"] == "partial" and status["nextPhaseStarted"] is False
    for row in status["references"].values():
        check(row)
    selected = files(WORK) | files(BROWSER)
    selected = {path for path in selected
                if "final-audit" not in path.parts
                and not path.name.startswith("server-attempt-")}
    selected |= {Path(path) for path in DOCS}
    selected |= files(Path("skills/archcanvas"))
    selected |= files(Path("src"))
    selected |= {Path(path) for path in product["sourceBindings"]}
    selected |= {Path(row["path"]) for row in product["assets"]}
    selected |= {STATUS, ARCHIVE, LEGACY_SEAL}
    selected |= {WORK / "final-audit/attempt-1/export-input-reconstruction.json",
                 WORK / "final-audit/attempt-1/reconstructed-export-input.svg"}
    rows = [binding(path) for path in sorted(selected)]
    value = {"schemaVersion": 1, "sealedAt": datetime.now(timezone.utc).isoformat(),
             "state": "bounded-current-UI-static-source-and-build-evidence-M4-partial",
             "scope": "New ChS product, tests/build, original representative browser attempts and independent audits; original Bc bytes remain in their archive. No new full39 or human acceptance.",
             "productionBuild": "index-ChS0wIgb.js",
             "productionJsSha256": product["assets"][0]["sha256"],
             "currentStatus": binding(STATUS), "browserManifest": binding(BROWSER_MANIFEST),
             "verification": {"productSourceBindingsExact": len(product["sourceBindings"]),
                              "productionAssetsExact": len(product["assets"]),
                              "studioPassed": 152, "strictBuildExit": 0,
                              "standaloneChecks": 9,
                              "statusReferencesExact": len(status["references"]),
                              "legacyArchiveBindingsExact": archive["bindingCount"],
                              "legacyArchive": binding(ARCHIVE), "legacySeal": binding(LEGACY_SEAL),
                              "finalSampleRange": sample_range()},
             "bindingCount": len(rows), "bindings": rows,
             "excludedMutableOrPostSealPaths": ["**/__pycache__/**", "**/*.pyc",
                 (WORK / "root/server-attempt-*.log").as_posix(),
                 ".archcanvas/** live stores and service state",
                 (WORK / "final-audit/** (except two pre-seal export reconstruction files)").as_posix(),
                 "this seal itself"],
             "limits": ["AI users and auditors do not count as humans; human count0",
                        "M4 partial; no M5 started; full new39 matrix pending",
                        "Downward conflict image is retained and not counted clear",
                        "Pinned refusal preserves geometry but creates noop revision18; saved/export17",
                        "Screen and publication SVG are not whole-byte or whole-text-geometry identical",
                        "No global aesthetics, presented FPS/INP, held-pointer cancellation or physical publication certification"]}
    write_exclusive(SEAL, value)
    print(json.dumps({"seal": binding(SEAL), "bindings": len(rows)}))


def verify():
    guards()
    seal = read(SEAL)
    assert seal["bindingCount"] == len(seal["bindings"])
    for row in seal["bindings"]:
        check(row)
    print(json.dumps({"seal": binding(SEAL), "bindingsExact": len(seal["bindings"])}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["browser", "seal", "verify"])
    stage = parser.parse_args().stage
    {"browser": freeze_browser, "seal": freeze_seal, "verify": verify}[stage]()
