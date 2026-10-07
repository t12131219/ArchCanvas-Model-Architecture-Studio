"""Read-only hierarchy/cache diagnosis and exclusive pre-change snapshot.

Uses frozen actual documents and public SVG XML, never product runtime/model.
"""
from __future__ import annotations
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASE = ROOT / "docs/evidence/m4-monochrome-role-work/browser-current/cnn-level0-paper-180"
SOURCE_FILES = [ROOT / name for name in ["AGENTS.md", "skills/archcanvas/SKILL.md", "studio/src/core/document.ts",
                "studio/src/core/scene.ts", "studio/src/core/types.ts", "studio/src/core/validate.ts",
                "studio/tests/visual-fixture.test.ts", "studio/tests/core.test.ts", "studio/tests/hierarchy-tree.test.ts"]]
CASE_FILES = [CASE / name for name in ["document.json", "saved-envelope.json", "figure.svg", "figure.svg.receipt.json",
              "fit-before.json", "fit-after.json", "fit.jpg", "local-before.json", "local-after.json", "local.jpg",
              "export-binding.json", "artifact-copy-receipt.json"]]

def binding(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def visible_expansions(nodes: list[dict], expansions: set[str]) -> tuple[list[str], list[str]]:
    by_id = {node["id"]: node for node in nodes}
    effective, hidden = [], []
    for identity in sorted(expansions):
        node = by_id[identity]
        ancestors_expanded = True
        parent = node.get("parentId")
        while parent:
            if parent not in expansions:
                ancestors_expanded = False
                break
            parent = by_id[parent].get("parentId")
        (effective if ancestors_expanded else hidden).append(identity)
    return effective, hidden

def main() -> None:
    output = HERE / "diagnosis-attempt-1"
    output.mkdir(parents=True, exist_ok=False)
    inputs = [Path(__file__).resolve(), *SOURCE_FILES, *CASE_FILES]
    before = [binding(path) for path in inputs]
    for path in inputs:
        target = output / "files" / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream: stream.write(path.read_bytes())
    document = json.loads((CASE / "document.json").read_text())
    effective, hidden = visible_expansions(document["architecture"]["nodes"], set(document["expandedIds"]))
    raw_key = "|".join(sorted(document["expandedIds"]))
    effective_key = "|".join(effective)
    xml = ET.fromstring((CASE / "figure.svg").read_bytes())
    visible_geometry = {}
    for element in xml.iter():
        identity = element.get("data-node-id")
        if identity and element.get("data-canonical-id"):
            body = next((child for child in element if child.tag.split('}')[-1] == 'rect' and child.get('stroke-width') is not None), None)
            if body is not None:
                visible_geometry[identity] = {name: float(body.get(name)) for name in ["x", "y", "width", "height"]}
    repeat = "repeat:instance:model.ResidualCNN.blocks"
    pool = "call:instance:model.ResidualCNN.pool"
    repeated, pooled = visible_geometry[repeat], visible_geometry[pool]
    current_gap = pooled["y"] - (repeated["y"] + repeated["height"])
    snapshot = document["layoutByFrontier"][effective_key]
    snapshot_keys = []
    for key, positions in document["layoutByFrontier"].items():
        effective_saved, hidden_saved = visible_expansions(document["architecture"]["nodes"], set(key.split('|')) if key else set())
        snapshot_keys.append({"rawKey": key, "effectiveKey": '|'.join(effective_saved), "hiddenExpansionIds": hidden_saved,
                              "poolLocal": positions.get(pool), "repeatLocal": positions.get(repeat),
                              "entries": len(positions)})
    after = [binding(path) for path in inputs]
    report = {
        "protocol": "archcanvas-collapse-continuity-readonly-diagnosis/1", "createdUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "Actual saved CNN publication and canvas byte snapshot; independent ancestor walk and public XML geometry only. Product/model not executed.",
        "documentId": document["id"], "revision": document["revision"], "expandedIds": document["expandedIds"],
        "rawFrontierKey": raw_key, "effectiveVisibleExpansionIds": effective, "hiddenExpansionMemoryIds": hidden,
        "effectiveFrontierKey": effective_key, "rawKeySnapshotExists": raw_key in document["layoutByFrontier"],
        "effectiveKeySnapshotExists": effective_key in document["layoutByFrontier"],
        "currentPoolLocal": document["layout"][pool], "existingEffectiveSnapshotPoolLocal": snapshot[pool],
        "repeatPublicBody": repeated, "poolPublicBody": pooled,
        "repeatBodyBottom": repeated["y"] + repeated["height"], "poolBodyTop": pooled["y"],
        "currentBodyGap": current_gap, "publicViewBox": xml.get("viewBox"),
        "existingEffectiveSnapshotWouldMovePoolLocalYBy": snapshot[pool]["y"] - document["layout"][pool]["y"],
        "layoutSnapshots": snapshot_keys,
        "sourceFinding": "document.ts keys layout snapshots by all expandedIds; scene.ts recursively displays descendants only while every ancestor is expanded. Collapse restores nothing when latent descendant flags make the raw key new. Existing tests collapse descendants first, so their cache key returns to the original root key.",
        "sourceNotModified": True, "testsRun": False, "buildRun": False, "modelExecuted": False, "browserOperated": False,
        "inputBindingsBefore": before, "inputBindingsAfter": after, "inputsUnchanged": before == after,
        "archiveCopiesExact": all(hashlib.sha256((output / "files" / path.relative_to(ROOT)).read_bytes()).hexdigest() == before[index]["sha256"] for index,path in enumerate(inputs)),
        "humanParticipants": 0,
    }
    with (output / "diagnosis.json").open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write("\n")
    print(json.dumps({"report": binding(output / "diagnosis.json"), "inputsUnchanged": before == after,
                      "bodyGap": current_gap, "rawMissEffectiveHit": raw_key not in document["layoutByFrontier"] and effective_key in document["layoutByFrontier"]}))
    assert before == after

if __name__ == "__main__": main()
