"""Corrupt actual raw copies to check independent-accounting rejection paths.

These are offline evidence-integrity checks, not browser trials or product tests.
The actual receipts, frozen helper contract and baseline remain byte-identical.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("independent_controls_analyzer", HERE / "analyze.py")
analyzer = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(analyzer)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=HERE / "analyzer-negative-attempt-1")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(exist_ok=False)
    raw_path = HERE / "browser-batch-1/control-full-click-r1.json"
    baseline_path = HERE / "helper-baseline-attempt-1/manifest.json"
    source_paths = [Path(__file__).resolve(), HERE / "analyze.py", raw_path, baseline_path]
    before = [analyzer.binding(path) for path in source_paths]
    raw = json.loads(raw_path.read_text())
    baseline = json.loads(baseline_path.read_text())
    good = analyzer.inspect_receipt(raw, baseline)
    assert good["validRawAccounting"], good["errors"]
    mutations: list[tuple[str, dict, str, str | None]] = []

    def mutate(name: str, modify, expected_error: str, reconstructed_status: str | None = None) -> None:
        damaged = copy.deepcopy(raw)
        modify(damaged)
        mutations.append((name, damaged, expected_error, reconstructed_status))

    mutate("discrete-denominator-underreported", lambda d: d["denominators"].update(discreteCandidatesInCapture=2), "reported denominators/matching differ")
    mutate("capture-selectively-prolonged", lambda d: d["deadlines"].update(captureEnd=d["deadlines"]["captureEnd"] + 500), "captureEnd was changed from the fixed capture clock")
    mutate("native-phase-relabelled", lambda d: d["inputs"][1].update(eventPhase="warmup"), "native eventPhase mismatch")
    mutate("gesture-includes-settle", lambda d: d["gestures"]["gestures"][0].update(nativeDurationMs=20000), "reported native gesture bounds differ")
    mutate("buffer-drop-hidden", lambda d: d["buffers"]["inputs"].update(dropped=1), "buffer attempted/recorded/dropped differs for inputs")
    mutate("false-viewport-coverage", lambda d: d["environment"]["flags"]["coverage"]["viewport"].update(height=700), "coverage inside flag differs from rect arithmetic")
    mutate("presented-certification-invented", lambda d: d.update(presentedPerformanceCertified=True), "diagnostic receipt claims forbidden certification")
    mutate("raf-only-native-observation-invented", lambda d: d.update(mode="raf-only"), "raf-only unexpectedly captured native/performance events")

    def erase_final_drain(d: dict) -> None:
        d["drains"] = [item for item in d["drains"] if not (item["type"] == "event" and item["origin"] == "final-fixed-drain")]
        d["buffers"]["drains"]["attempted"] -= 1

    mutate("pending-final-drain-omitted", erase_final_drain, "complete event lacks exactly one final-fixed-drain")

    def remove_pointerup_entry(d: dict) -> None:
        pointerup_match = next(item for item in d["denominators"]["matches"] if item["inputId"] == "input-3")
        raw_index = d["denominators"]["measuredCaptureEntryRawIndexes"][pointerup_match["entryIndex"]]
        del d["eventTiming"][raw_index]
        d["buffers"]["eventTiming"]["attempted"] -= 1

    mutate("missing-pointerup-treated-as-matched", remove_pointerup_entry, "reported denominators/matching differ", "missing")

    def impute_pointerup_zero(d: dict) -> None:
        remove_pointerup_entry(d)
        next(item for item in d["denominators"]["matches"] if item["inputId"] == "input-3")["durationMs"] = 0

    mutate("missing-pointerup-imputed-zero", impute_pointerup_zero, "reported denominators/matching differ", "missing")

    def ambiguous_duplicate(d: dict) -> None:
        match = next(item for item in d["denominators"]["matches"] if item["inputId"] == "input-3")
        raw_index = d["denominators"]["measuredCaptureEntryRawIndexes"][match["entryIndex"]]
        d["eventTiming"].append(copy.deepcopy(d["eventTiming"][raw_index]))
        d["buffers"]["eventTiming"]["attempted"] += 1

    mutate("duplicate-pointerup-entry-ambiguous", ambiguous_duplicate, "reported denominators/matching differ", "ambiguous")

    results = []
    for index, (name, damaged, expected_error, status) in enumerate(mutations, 1):
        attempt = output / f"{index:02d}-{name}"
        attempt.mkdir()
        with (attempt / "mutated-raw.json").open("x") as stream:
            json.dump(damaged, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        result = analyzer.inspect_receipt(damaged, baseline)
        rejected = not result["validRawAccounting"] and any(expected_error in error for error in result["errors"])
        missing_stays_unknown = None
        if status is not None:
            match = next(item for item in result["recomputedDenominators"]["matches"] if item["inputId"] == "input-3")
            missing_stays_unknown = match["status"] == status and match["durationMs"] is None and match["interactionId"] is None
            rejected = rejected and missing_stays_unknown
        with (attempt / "independent-audit.json").open("x") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        results.append({"name": name, "expectedError": expected_error, "rejectedForExpectedReason": rejected,
                        "reconstructedStatus": status, "missingOrAmbiguousDurationRetainedUnknown": missing_stays_unknown,
                        "mutatedRawBinding": analyzer.binding(attempt / "mutated-raw.json"),
                        "auditBinding": analyzer.binding(attempt / "independent-audit.json")})
    after = [analyzer.binding(path) for path in source_paths]
    receipt = {"protocol": "archcanvas-performance-controls-analyzer-negative-check/1",
               "createdUtc": datetime.now(timezone.utc).isoformat(),
               "scope": "Offline mutations of copies of one actual top-level control receipt; no new browser/service/product execution.",
               "unalteredActualRawAccountingPassed": good["validRawAccounting"],
               "mutations": results, "mutationsCount": len(results),
               "allRejectedForExpectedReason": all(item["rejectedForExpectedReason"] for item in results),
               "inputBindingsBefore": before, "inputBindingsAfter": after, "inputsUnchanged": before == after,
               "browserOperated": False, "serviceLaunched": False, "modelExecuted": False,
               "productTestsOrBuildRun": False, "presentedPerformanceCertified": False, "humanParticipants": 0}
    with (output / "receipt.json").open("x") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"receipt": analyzer.binding(output / "receipt.json"), "mutations": len(results),
                      "allRejected": receipt["allRejectedForExpectedReason"], "inputsUnchanged": before == after}))
    raise SystemExit(0 if receipt["allRejectedForExpectedReason"] and before == after else 2)


if __name__ == "__main__":
    main()
