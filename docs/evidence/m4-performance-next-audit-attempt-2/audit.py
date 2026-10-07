#!/usr/bin/env python3
"""Bounded read-only audit of the current formal build's browser-performance path."""
from __future__ import annotations
import hashlib, json, re, subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent

def sha(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

def run(cmd: list[str]) -> dict:
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {"command": " ".join(cmd), "exitCode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}

assets = [ROOT / "studio/dist/index.html", ROOT / "studio/dist/assets/index-thbum3BQ.js", ROOT / "studio/dist/assets/index-QPVAzYp6.css"]
sources = [ROOT / "studio/src/PerfBenchmarkPanel.tsx", ROOT / "studio/src/perfBenchmark.ts", ROOT / "studio/src/nativePerformance.ts", ROOT / "studio/src/perf.ts", ROOT / "scripts/validate_studio_performance.mjs", ROOT / "scripts/validate_native_performance.mjs"]
status = json.loads((ROOT / "docs/evidence/m4-readable-canvas-status.json").read_text())
handoff = json.loads((ROOT / "docs/evidence/m4-human-review-handoff-status.json").read_text())
js = (ROOT / "studio/dist/assets/index-thbum3BQ.js").read_text(errors="replace")
receipt = {
  "protocol": "archcanvas-performance-current-formal-build-audit/1",
  "createdUtc": datetime.now(timezone.utc).isoformat(),
  "scope": "Read-only current formal dist/source/runtime-path audit; no browser operation, product edit, test/build rerun, model execution or dependency installation.",
  "currentFormalBuild": {
    "indexHtml": sha(assets[0]), "js": sha(assets[1]), "css": sha(assets[2]),
    "statusFile": {"path": "docs/evidence/m4-readable-canvas-status.json", "sha256": hashlib.sha256((ROOT / "docs/evidence/m4-readable-canvas-status.json").read_bytes()).hexdigest()},
    "statusBuild": status["build"],
  },
  "sourceBindings": [sha(p) for p in sources],
  "browserEntry": {
    "urlPattern": "http://127.0.0.1:<port>/?benchmark=1",
    "panelStringsPresentInCurrentAsset": {s: js.count(s) for s in ["运行 20 组性能采样", "原生输入与空间采样", "two-animation-frame-paint-proxy", "native-event-timing-to-next-paint"]},
    "scenario": "Synthetic DOM tree clicks; 20 expand/collapse pairs and fit; two animation frames are explicitly named a paint proxy.",
    "nativePanel": "Ordinary click/pointerdown capture plus PerformanceObserver Event Timing and two-frame geometry sampling; missing/ambiguous entries remain null.",
    "formalRuntimeCommand": "PYTHONPATH=src .venv/bin/python -m archcanvas_cli serve --host 127.0.0.1 --port <port> --data-dir <isolated-/tmp-dir> --studio-dir studio/dist",
    "runtimeProvenance": "The formal server's startup capabilities identify the project root, formal modules, and studio_dir path; this audit did not claim model execution or runtime verification.",
  },
  "validators": {
    "studioSmall": run(["node", "scripts/validate_studio_performance.mjs", "docs/evidence/m4-studio-performance.json"]),
    "studioStress": run(["node", "scripts/validate_studio_performance.mjs", "docs/evidence/m4-studio-performance-stress.json"]),
    "nativeSmoke": run(["node", "scripts/validate_native_performance.mjs", "docs/evidence/m4-native-performance-stress-smoke.json"]),
    "nativeIntrusion": run(["node", "scripts/validate_native_performance.mjs", "docs/evidence/m4-native-performance-intrusion-current.json"]),
  },
  "currentReceiptBuildStatus": {
    "readableCanvasBuild": "index-thbum3BQ.js / index-QPVAzYp6.css",
    "handoffPerformanceBuild": handoff.get("productionBuild"),
    "handoffPerformanceBuildSha256": handoff.get("productionJsSha256"),
    "historicalReceiptsAreCurrentBuildBound": False,
    "reason": "The retained Studio/native JSON receipts point at prior localhost URLs and do not bind the current thbum3BQ asset digest; they remain historical diagnostics.",
  },
  "claims": {
    "formalBenchmarkPathPresentInCurrentAsset": True,
    "browserRenderVerifiedByThisAuditor": False,
    "currentStudioABMeasured": False,
    "presentedFpsCertified": False,
    "continuousInputToPaintCertified": False,
    "nativeReceiptCertification": "pending-fixed-environment-and-review",
    "humanParticipants": status.get("humanParticipants", 0),
    "m4Complete": False,
  },
  "nextAction": {
    "first": "Run a fresh current-build browser sample only when an actual compositor/presentation trace is available, or have an operator use the host native performance recorder.",
    "requiredBinding": ["current dist asset hashes", "viewport/DPR/UA/font/hardware lock", "source/document/IR IDs", "whole trace and action timestamps"],
    "mustNotPromote": ["rAF callback cadence", "DOM geometry after two animation frames", "PerformanceObserver Event Timing subset", "screenshot arrival"],
    "allowedInterim": "Use ?benchmark=1 for engineering diagnostics and preserve unmatched/ambiguous Event Timing as null; do not call its proxy FPS presented FPS.",
  },
  "productSourceChanged": False,
  "browserOperatedByAuditor": False,
  "dependenciesInstalled": False,
  "modelsExecuted": False,
}
path = OUT / "receipt.json"
if path.exists(): raise SystemExit(f"refusing to overwrite {path}")
path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"receipt": str(path.relative_to(ROOT)), "assetHashes": [x["sha256"] for x in receipt["currentFormalBuild"].values() if isinstance(x, dict) and "sha256" in x], "validatorExitCodes": {k:v["exitCode"] for k,v in receipt["validators"].items()}}, ensure_ascii=False))
