"""Bind exact native-action-log and screenshot files to the three actual raws."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
ROOT = WORK.parents[2]
BATCH = WORK / "browser-batch-1"
INPUTS = [Path(__file__).resolve(), HERE / "receipt.json", *sorted(HERE.glob("raw-*-audit.json")),
          BATCH / "control-raf-idle-r1.json", BATCH / "control-full-click-r1.json", BATCH / "control-full-idle-r1.json",
          BATCH / "tool-action-log.json", BATCH / "tool-action-log-supplement-1.json", BATCH / "control-full-click-r1-after.jpg"]

def binding(path: Path) -> dict:
    body = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}

def main() -> None:
    destination = HERE / "supplemental-inputs"
    destination.mkdir(exist_ok=False)
    before = [binding(path) for path in INPUTS]
    for index, path in enumerate(INPUTS):
        with (destination / f"{index:02d}-{path.name}").open("xb") as stream:
            stream.write(path.read_bytes())
    primary = json.loads((BATCH / "tool-action-log.json").read_text())
    supplement = json.loads((BATCH / "tool-action-log-supplement-1.json").read_text())
    primary_retained = primary["sessions"] == supplement["sessions"][:len(primary["sessions"])]
    records = []
    for session in supplement["sessions"]:
        raw = json.loads((BATCH / session["evidence"]).read_text())
        records.append({"label": session["label"], "recordMatchesRawLabelModeOperation": all(session[key] == raw[key] for key in ["label", "mode", "operation"]),
                        "rawBinding": binding(BATCH / session["evidence"]), "actionsRetainedVerbatim": session["actions"],
                        "toolLogScope": session["scope"], "actualCaptureWindowMs": raw["deadlines"]["captureEnd"] - raw["deadlines"]["captureStart"]})
    image = (BATCH / "control-full-click-r1-after.jpg").read_bytes()
    valid_jpeg = image.startswith(b"\xff\xd8") and image.endswith(b"\xff\xd9")
    after = [binding(path) for path in INPUTS]
    receipt = {"protocol": "archcanvas-performance-controls-firstbatch-supplement-audit/1",
               "createdUtc": datetime.now(timezone.utc).isoformat(), "scope": "Read-only exact file/log association. Transcribed native-action strings are retained, not independently synchronized OS trace or proof of presented response.",
               "inputBindingsBefore": before, "inputBindingsAfter": after, "inputsUnchanged": before == after,
               "archiveCopiesExact": all(hashlib.sha256((destination / f"{index:02d}-{path.name}").read_bytes()).hexdigest() == before[index]["sha256"] for index,path in enumerate(INPUTS)),
               "primaryLogRetainedExactlyAsSupplementPrefix": primary_retained, "actualRawCount": len(records), "sessions": records,
               "browserId": supplement["browserId"], "tabCreatedVisible": supplement["createdVisible"],
               "screenshotBinding": binding(BATCH / "control-full-click-r1-after.jpg"), "actualScreenshotJpegMagic": valid_jpeg,
               "screenshotIsAfterCaptureOnly": True, "screenshotPixelsReviewedByThisScript": False,
               "externalPresentationCertified": False, "causeIdentified": False,
               "helperChanged": False, "modelExecuted": False, "productTestsOrBuildRun": False, "browserOperatedByThisAuditor": False,
               "fullMatchedMatrixCompleted": False, "humanParticipants": 0}
    with (HERE / "supplement-receipt.json").open("x") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2); stream.write("\n")
    print(json.dumps({"receipt": binding(HERE / "supplement-receipt.json"), "inputsUnchanged":before == after,"logsAssociate": all(record["recordMatchesRawLabelModeOperation"] for record in records),"validJpeg": valid_jpeg}))
    assert before == after and primary_retained and valid_jpeg and all(record["recordMatchesRawLabelModeOperation"] for record in records)

if __name__ == "__main__":
    main()
