#!/usr/bin/env python3
"""Compare actual public SVG snapshots without repairing early operator fields."""
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]


def binding(path):
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def neutral(svg):
    root = ET.fromstring(svg)
    root.attrib.pop("data-revision")
    metadata = next(item for item in root if item.tag.endswith("}metadata"))
    facts = json.loads(metadata.text)
    facts.pop("revision")
    metadata.text = json.dumps(facts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return root


def changes(left, right):
    a, b = neutral(left), neutral(right)
    assert sum(1 for _ in a.iter()) == sum(1 for _ in b.iter())
    result = []
    for index, (x, y) in enumerate(zip(a.iter(), b.iter())):
        assert x.tag == y.tag and x.attrib == y.attrib and x.tail == y.tail and len(x) == len(y)
        if x.text != y.text:
            result.append({"elementIndex": index, "tag": x.tag, "beforeText": x.text, "afterText": y.text})
    return result


def facts(svg):
    root = ET.fromstring(svg)
    metadata = json.loads(next(item.text for item in root if item.tag.endswith("}metadata")))
    return {"documentBinding": {key: metadata[key] for key in ("documentId", "revision", "sourceDigest", "irDigest")},
            "visibleNodeCountFromUniqueDataNodeId": len({item.get("data-node-id") for item in root.iter() if "data-node-id" in item.attrib})}


def main():
    rows = []
    for fixture, case in (("cnn", "residual_cnn-edited-level2-paper-180"),
                          ("mlp", "mlp-edited-level1-paper-180"),
                          ("transformer", "transformer-edited-level3-paper-180")):
        paths = {state: WORK / "edited-journal" / f"{fixture}-{state}.json"
                 for state in ("before", "undo", "redo", "saved", "reopened")}
        documents = {state: json.loads(path.read_bytes()) for state, path in paths.items()}
        derived = {state: facts(item["svg"]) for state, item in documents.items()}
        assert all(item["documentBinding"] == derived[state]["documentBinding"] for state, item in documents.items())
        undo_redo = changes(documents["undo"]["svg"], documents["redo"]["svg"])
        assert len(undo_redo) == 1 and undo_redo[0]["tag"].endswith("}tspan")
        assert documents["redo"]["svg"] == documents["saved"]["svg"] == documents["reopened"]["svg"]
        final_path = WORK / "raw" / case / "browser-scene.svg"
        assert not changes(documents["reopened"]["svg"], final_path.read_text())
        before_undo = changes(documents["before"]["svg"], documents["undo"]["svg"])
        before_redo = changes(documents["before"]["svg"], documents["redo"]["svg"])
        rows.append({"fixture": fixture, "caseId": case,
                     "inputBindings": {state: binding(path) for state, path in paths.items()},
                     "publicSvgFacts": derived,
                     "declaredVisibleNodes": {state: item["visibleNodes"] for state, item in documents.items()},
                     "undoEqualsBeforeExceptRevision": not before_undo,
                     "beforeEqualsRedoExceptRevision": not before_redo,
                     "beforeSnapshotTiming": "before-edit" if not before_undo else "already-contains-edit",
                     "beforeUndoTextDifferences": before_undo, "undoRedoTextDifferences": undo_redo,
                     "redoSavedReopenedExactSvgBytesEqual": True,
                     "finalCaptureEqualsReopenedExceptRevision": True,
                     "finalCaptureSvgFacts": facts(final_path.read_text()), "finalRawScene": binding(final_path),
                     "cameraChangedOnReopen": documents["saved"]["camera"] != documents["reopened"]["camera"]})
    report = {"schemaVersion": 1, "checkedAt": datetime.now(timezone.utc).isoformat(),
              "auditorSource": binding(Path(__file__)), "journalJsonCount": 15, "fixtures": rows,
              "rawFilesModified": False, "allActualUndoRedoAnnotationChangesVerified": True,
              "allRedoSavedReopenedSvgBytesEqual": True,
              "revisionNeutralComparison": "Only root data-revision and metadata.revision removed. All other XML tags, attributes, tails and child counts equal; text differences reported exactly.",
              "limitations": ["All15 early visibleNodes fields are0 from an outdated operator selector. Actual unique SVG data-node-id counts are24/8/49 and raw JSON is preserved.",
                              "MLP and Transformer before snapshots already contain the edit; they cannot establish a pre-edit baseline. Actual undo→redo tspan changes and redo→save→reopen exact SVG prove those scene effects.",
                              "Changed cameras on reopen are expected viewport state. PublicSVG equality does not certify native pixels, publication aesthetics or human task completion.",
                              "AI auditor earlier implemented routing/capture helper; this is independent local comparison against root observations, not independence from all product implementation."],
              "priorFailedAssertion": binding(WORK / "audit-full-collection-attempt2-journal-failure.json"),
              "humanAcceptanceCertified": False}
    with (WORK / "edited-journal-svg-audit.json").open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"journalJsonCount": 15, "actualUndoRedoVerified": 3, "exactSaveReopenVerified": 3,
                      "correctPreEditBeforeSnapshots": 1, "alreadyEditedBeforeSnapshots": 2,
                      "derivedUniqueVisibleNodes": [24, 8, 49], "humanAcceptanceCertified": False}))


if __name__ == "__main__":
    main()
