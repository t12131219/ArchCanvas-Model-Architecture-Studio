#!/usr/bin/env python3
"""Read-only, bounded performance evidence audit. Does not connect a browser."""
from __future__ import annotations

import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PLAN = ROOT.parent / "ArchCanvas_双向模型可视化与编辑框架_技术计划书.md"
SELECTED = [
    ROOT / "AGENTS.md",
    ROOT / "skills/archcanvas/SKILL.md",
    PLAN,
    ROOT / "docs/m4-performance.md",
    ROOT / "docs/evidence/m4-human-review-handoff-status.json",
    ROOT / "studio/src/nativePerformance.ts",
    ROOT / "studio/src/perf.ts",
    ROOT / "scripts/validate_native_performance.mjs",
    ROOT / "scripts/m4_input_observer.mjs",
    ROOT / "scripts/validate_input_observation.mjs",
    ROOT / "docs/evidence/m4-performance-controls-work/measurement-contract.json",
    ROOT / "docs/evidence/m4-performance-controls-work/observer.mjs",
    ROOT / "docs/evidence/m4-performance-controls-work/analysis-attempt-3/receipt.json",
    ROOT / "docs/evidence/m4-performance-controls-work/browser-batch-1/control-raf-idle-r1.json",
    ROOT / "docs/evidence/m4-performance-controls-work/browser-batch-1/control-full-click-r1.json",
    ROOT / "docs/evidence/m4-performance-controls-work/browser-batch-1/control-full-idle-r1.json",
    OUT / "live-capabilities.json",
    OUT / "host-readonly-observation.json",
    OUT / "browser-process-flags-supplement-1.json",
    OUT / "host-config-excerpts.json",
]


def bound(path: Path, content: bytes) -> dict:
    return {
        "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def read_json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def cadence(path: Path) -> dict:
    d = read_json(path)
    start, end = d["deadlines"]["captureStart"], d["deadlines"]["captureEnd"]
    frames = [f for f in d["frames"] if start <= f["timestamp"] < end]
    intervals = [b["timestamp"] - a["timestamp"] for a, b in zip(frames, frames[1:])]
    short = [x for x in intervals if 0 <= x <= 33]
    long = [x for x in intervals if 950 <= x <= 1050]
    sums = [intervals[i] + intervals[i + 1] for i in range(0, len(intervals) - 1, 2)]
    offsets = [f["observedAt"] - f["timestamp"] for f in frames]
    events = [e for e in d["eventTiming"] if start <= e["startAt"] < end
              and e["name"] in {"pointerdown", "pointerup", "click", "keydown", "keyup"}
              and e["interactionId"] > 0 and e["target"]["inMeasuredSurface"]]
    native = [e for e in d["inputs"] if start <= e["eventAt"] < end]
    return {
        "rawPath": str(path.relative_to(ROOT)), "mode": d["mode"], "operation": d["operation"],
        "historicalContext": d["context"], "plannedCaptureMs": end - start,
        "rawFrameRecords": len(d["frames"]), "timestampInCaptureFrames": len(frames),
        "intervalsMs": intervals,
        "shortIntervalCount": len(short), "longIntervalCount": len(long),
        "otherIntervalCount": len(intervals) - len(short) - len(long),
        "shortMedianMs": statistics.median(short) if short else None,
        "longMedianMs": statistics.median(long) if long else None,
        "successivePairSumsMs": sums,
        "pairRangeMs": [min(sums), max(sums)] if sums else None,
        "deliveryOffsetMedianMs": statistics.median(offsets) if offsets else None,
        "deliveryOffsetMaxMs": max(offsets) if offsets else None,
        "allRawLongTasks": d["longTasks"],
        "measuredPositiveDiscreteEntries": events,
        "allNativeInputsInCapture": native,
        "DOMFlagsAtStart": d["environment"]["flags"],
        "DOMFlagsArePresentationEvidence": False,
        "currentStudioMeasured": False,
    }


def main() -> None:
    # Snapshot precisely the bytes used. These inputs are never overwritten.
    input_dir = OUT / "inputs"
    input_dir.mkdir(exist_ok=True)
    bindings = []
    for i, p in enumerate(SELECTED):
        raw = p.read_bytes()
        copy = input_dir / f"{i:02d}-{p.name}"
        if copy.exists():
            if copy.read_bytes() != raw:
                raise RuntimeError(f"Existing audit input differs: {copy}; use a new attempt")
        else:
            copy.write_bytes(raw)
        bindings.append({**bound(p, raw), "snapshot": str(copy.relative_to(ROOT))})

    caps = read_json(OUT / "live-capabilities.json")
    status = read_json(ROOT / "docs/evidence/m4-human-review-handoff-status.json")
    records = [cadence(p) for p in SELECTED if p.name.startswith("control-")]
    host = read_json(OUT / "host-readonly-observation.json")
    flag_records = read_json(OUT / "browser-process-flags-supplement-1.json")["processes"]
    result = {
        "protocol": "archcanvas-performance-next-actionable-audit/1",
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "auditSource": bound(Path(__file__), Path(__file__).read_bytes()),
        "selectedInputCount": len(bindings), "inputBindings": bindings,
        "currentBuildAtAudit": {key: status.get(key) for key in
                               ["productionBuild", "build", "productionJs", "productionJsSha256"]},
        "currentPerformanceStatus": status["performance"],
        "actualToolCapabilities": caps,
        "actualTraceCapabilityAdvertised": any(x["id"] in {"cdp", "trace", "recording"}
                                              for x in caps["tabCapabilities"] + caps["browserCapabilities"]),
        "historicalCadence": records,
        "currentHostObservation": {
            "cpuQuery": host["queries"]["cpu"], "displayQuery": host["queries"]["currentDisplay"],
            "gpuQuery": host["queries"]["gpu"], "packageQuery": host["queries"]["packages"],
            "fontCandidateQueries": {k: v for k, v in host["queries"].items() if k.startswith("font")},
            "rendererFlagRecords": [r for r in flag_records if "--type=renderer" in r["whitelistedFlags"]],
            "resolvedBrowserGlyphBytesKnown": False,
            "historicalHostLockCertified": False,
            "configured60HzProvesBrowser60Fps": False,
        },
        "newFindings": [
            "Actual browser 2/tab60 capability list has visibility/viewport and pageAssets/webmcp; no CDP, tracing, presentation or recording API is advertised.",
            "All three retained simple controls show only 16.7ms/983ms alternating rAF intervals, with consecutive pair sums approximately 1000ms. The two full controls contain no raw long tasks. Product React and full geometry sampling are not necessary for this historical cadence.",
            "Current configured X11 display is 1920x1080 at60Hz. Current CPU is i5-13400F and GPU RTX2070 driver535.288.01. These are point observations, not a historical environment lock or actual presentation trace.",
            "Installed host source disables ordinary background throttling for a local page while its internal visible/browser-use-active/captured condition holds. Those conditions and effective runtime state were not inspected. A blanket explanation that local IAB is necessarily background-throttled is unsupported.",
            "The installed host has a native Start Performance Trace/Stop Performance Trace path and writes a pftrace. Native CUA APIs are disabled, and the connected browser has no trace capability. This code path was not executed and is not a newly callable tool.",
        ],
        "nextActionDecision": {
            "doNotRepeatSlowSamplingAsCure": True,
            "firstMeasurementPrerequisite": "A supported browser/native trace path that captures actual compositor presentation and input correlation, or a real operator-provided trace from the built-in native recorder.",
            "legalCurrentActions": [
                "Continue source, routing and interaction work; preserve current frozen performance records.",
                "If a fresh fixed-window discrete input diagnostic is independently needed after product change, root may use the existing public-DOM full observer through CUA with a new store and frozen workload. Report missing/ambiguous EventTiming as null and all attempts separately.",
                "Keep the new host/capability observation separate from old captures; do not backfill old hardware/font/foreground fields.",
            ],
            "whenSupportedTraceBecomesAvailable": [
                "Capture a short fresh actual source-imported Studio interaction in the fixed environment, bind build/source/document IDs and public input target, and retain whole trace plus action timestamps.",
                "Verify a renderer frame is joined to compositor presentation feedback for the same surface/sequence. Browser BeginFrame, rAF, Paint, composite submission or screenshot arrival alone are insufficient.",
                "Join actual input latency flow to the first presented frame containing the corresponding visual response, retaining dropped/unmatched/coalesced inputs. Report per-operation p95 with all input denominators; do not call a matched subset all-page INP.",
                "After a genuine presentation measurement succeeds, collect the prescribed matched A/B conditions and three replicates without fastest-sample selection. Keep 300 rendered members, viewport intersection and physical readability distinct.",
            ],
            "forbiddenFallbacks": [
                "No direct CDP/IPC/socket or standalone browser automation through exec.",
                "No disabling host background throttling, changing GPU/refresh/power settings or installing trace tools to force a passing result.",
                "No screenshot/rAF/DOM/next-task proxy promoted to presented FPS or continuous input-to-paint.",
                "No trace upload, host-private state invocation or hidden app method execution.",
            ],
        },
        "productSourceChanged": False, "productTestsOrBuildRun": False,
        "browserOperatedByAuditor": False, "browserCapabilitiesObservedByRootThroughCua": True,
        "hostSettingsModified": False, "dependenciesInstalled": False, "modelsExecuted": False,
        "presentedFpsCertified": False, "continuousInputToPaintCertified": False,
        "humanParticipants": 0, "M4Complete": False,
    }
    # Recheck source bytes after all reads. This is an audit, not product execution.
    result["selectedInputsUnchangedDuringAudit"] = all(
        bound(p, p.read_bytes())["sha256"] == b["sha256"] for p, b in zip(SELECTED, bindings))
    path = OUT / "receipt.json"
    if path.exists():
        raise RuntimeError("Audit receipt already exists; use a new attempt")
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"receipt": str(path.relative_to(ROOT)), "selectedInputs": len(bindings),
                      "inputsUnchanged": result["selectedInputsUnchangedDuringAudit"],
                      "actualTraceCapability": result["actualTraceCapabilityAdvertised"],
                      "historicalRecords": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
