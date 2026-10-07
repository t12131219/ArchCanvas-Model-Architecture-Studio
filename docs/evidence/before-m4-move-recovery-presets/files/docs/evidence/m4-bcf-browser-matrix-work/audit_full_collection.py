#!/usr/bin/env python3
"""Read frozen local files; compare byte chains and public edited SVG journals."""
from __future__ import annotations

import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
COLLECTION = ROOT / "docs/evidence/browser-visual-matrix-bcf-full"


def read(path: Path) -> bytes:
    path = path.absolute()
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError(f"Symlink is not a frozen input: {item}")
    return path.read_bytes()


def decoded(path: Path) -> dict:
    return json.loads(read(path))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def binding(path: Path) -> dict:
    data = read(path)
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(data), "bytes": len(data)}


def check(entry: dict, base: Path = ROOT) -> None:
    path = base / entry["path"]
    data = read(path)
    assert sha(data) == entry["sha256"], str(path)
    if "bytes" in entry:
        assert len(data) == entry["bytes"], str(path)


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    assert data.startswith(b"\xff\xd8\xff"), "Actual native bytes must be JPEG."
    offset = 2
    sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while offset < len(data):
        assert data[offset] == 0xFF, "Malformed JPEG marker."
        while data[offset] == 0xFF:
            offset += 1
        marker = data[offset]
        offset += 1
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            continue
        assert marker not in (0xD9, 0xDA), "Missing JPEG frame header."
        length = struct.unpack_from(">H", data, offset)[0]
        assert length >= 2 and offset + length <= len(data), "Invalid JPEG segment."
        if marker in sof:
            height, width = struct.unpack_from(">HH", data, offset + 3)
            assert width > 0 and height > 0
            return width, height
        offset += length
    raise ValueError("JPEG has no frame header.")


def revision_neutral(svg: str) -> tuple:
    root = ET.fromstring(svg)
    root.attrib.pop("data-revision")
    metadata = next(item for item in root if item.tag.endswith("}metadata"))
    facts = json.loads(metadata.text)
    facts.pop("revision")
    metadata.text = json.dumps(facts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def node(element: ET.Element) -> tuple:
        return (element.tag, tuple(sorted(element.attrib.items())), element.text, element.tail,
                tuple(node(child) for child in element))

    return node(root)


def svg_facts(svg: str) -> dict:
    root = ET.fromstring(svg)
    metadata = json.loads(next(item.text for item in root if item.tag.endswith("}metadata")))
    return {"documentBinding": {key: metadata[key] for key in ("documentId", "revision", "sourceDigest", "irDigest")},
            "visibleNodeCountFromDataNodeId": sum("data-node-id" in element.attrib for element in root.iter())}


def emit(name: str, report: dict) -> None:
    with (WORK / name).open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main() -> None:
    index_path = WORK / "captures-039.json"
    manifest_path = COLLECTION / "manifest.json"
    spec_path = ROOT / ".archcanvas/browser-visual-matrix-authoring-feedback-bcf/spec.json"
    index, manifest, spec = decoded(index_path), decoded(manifest_path), decoded(spec_path)
    assert len(index["captures"]) == len(manifest["captures"]) == 39
    baseline_ids = [item["variantId"] for item in index["captures"] if item["state"] == "baseline"]
    assert len(baseline_ids) == len(set(baseline_ids)) == 36
    assert set(baseline_ids) == {item["variantId"] for item in spec["variants"]}
    assert manifest["capturedBaselineCount"] == 36
    assert not manifest["missingBaselineVariants"] and not manifest["editedAfterModelsMissing"]
    assert manifest["editedAfterModelsCaptured"] == ["mlp", "residual_cnn", "transformer"]
    assert manifest["artifactCoverage"] == "complete"
    assert manifest["visualAcceptance"] == "pending-human-review" and not manifest["humanAcceptanceCertified"]
    collected = {item["caseId"]: item for item in manifest["captures"]}
    assert len(collected) == 39 and set(collected) == {item["caseId"] for item in index["captures"]}
    rows = []
    for record in index["captures"]:
        case = record["caseId"]
        package = WORK / "cases" / case
        raw = WORK / "raw" / case
        bound = WORK / "bound-observations" / case
        helper = decoded(package / "case-helper.json")
        for entry in helper["copiedFiles"]:
            check(entry, package)
        for field, filename in (("screenshot", "screenshot.jpg"), ("browserScene", "browser-scene.svg")):
            assert read(raw / filename) == read(WORK / record[field])
        for source_name, package_name in (("dom-observation.json", "dom-observation.json"),
                                          ("actual-document-store.json", "actual-document-store.json"),
                                          ("actual-document-store.json.receipt.json", "actual-document-store-snapshot-receipt.json")):
            assert read(bound / source_name) == read(package / package_name)
        original_raw = decoded(raw / "dom-observation.json")
        bound_raw = decoded(bound / "dom-observation.json")
        assert original_raw == {key: value for key, value in bound_raw.items() if key != "actualStoredEnvelope"}
        assert decoded(bound / "actual-document-store.json")["document"] == decoded(package / "canvas.json")
        published = collected[case]
        assert published["variantId"] == record["variantId"] and published["state"] == record["state"]
        assert len(published["files"]) == 6
        for field, entry in published["files"].items():
            check(entry, COLLECTION)
            assert read(WORK / record[field]) == read(COLLECTION / entry["path"])
        screen = decoded(WORK / record["screenReceipt"])
        width, height = jpeg_dimensions(read(WORK / record["screenshot"]))
        viewport, dpr = screen["environment"]["viewport"], screen["environment"]["devicePixelRatio"]
        assert width == viewport["width"] * dpr and height == viewport["height"] * dpr
        rows.append({"caseId": case, "variantId": record["variantId"], "state": record["state"],
                     "exactExportArtifactId": helper["exactExportArtifactId"],
                     "rawSnapshotPackageCollectionBytesEqual": True,
                     "jpegPixels": {"width": width, "height": height}, "viewport": viewport, "dpr": dpr,
                     "screenshot": published["files"]["screenshot"], "browserScene": published["files"]["browserScene"]})
    for entry in manifest["buildFiles"]:
        check(entry, ROOT / "studio/dist")
    for entry in decoded(WORK / "captures-039.json.receipt.json")["inputBindings"]:
        check(entry)
    for entry in decoded(WORK / "processing-guard.json")["files"]:
        check(entry)
    prior_seals = []
    for name in ("prepared/obxXFNt", "prepared/BcFxpKDY", "independent"):
        path = ROOT / "docs/evidence/m4-authoring-feedback" / name / "manifest.json"
        seal = decoded(path)
        for filename, item in seal["files"].items():
            check({"path": filename, **item} if isinstance(item, dict) else {"path": filename, "sha256": item})
        prior_seals.append({"manifest": binding(path), "sealedFileCount": len(seal["files"]), "unchanged": True})
    now = datetime.now(timezone.utc).isoformat()
    inputs = [binding(path) for path in (Path(__file__), index_path, manifest_path, spec_path,
                                        WORK / "captures-039.json.receipt.json", WORK / "processing-guard.json")]
    emit("full-collection-byte-audit.json", {
        "schemaVersion": 1, "checkedAt": now, "inputBindings": inputs, "caseCount": 39,
        "baselineCount": 36, "editedModels": manifest["editedAfterModelsCaptured"], "cases": rows,
        "priorSeals": prior_seals, "allIndexInputBindingsUnchanged": True,
        "allBuildAndWorkerGuardBytesUnchanged": True, "humanAcceptanceCertified": False,
        "reviewerRole": "AI local-byte auditor; this agent earlier implemented routing and capture helper.",
        "scope": "Independent comparisons against root-created frozen observations. No browser operation, pixel aesthetics, current UA identity, font resolution, physical-size readability or human acceptance certified.",
        "earlierReceiptCountAudit": "An in-memory all-directory worker-count assertion failed before writing because two initial cases were direct helper runs. Final audit fixes its scope by selecting exactly39 indexed cases."})
    journals = []
    for fixture, case in (("cnn", "residual_cnn-edited-level2-paper-180"),
                          ("mlp", "mlp-edited-level1-paper-180"),
                          ("transformer", "transformer-edited-level3-paper-180")):
        paths = {state: WORK / "edited-journal" / f"{fixture}-{state}.json"
                 for state in ("before", "undo", "redo", "saved", "reopened")}
        documents = {state: decoded(path) for state, path in paths.items()}
        facts = {state: svg_facts(item["svg"]) for state, item in documents.items()}
        assert all(item["documentBinding"] == facts[state]["documentBinding"] for state, item in documents.items())
        assert revision_neutral(documents["before"]["svg"]) == revision_neutral(documents["undo"]["svg"])
        assert revision_neutral(documents["before"]["svg"]) != revision_neutral(documents["redo"]["svg"])
        assert documents["redo"]["svg"] == documents["saved"]["svg"] == documents["reopened"]["svg"]
        final_raw_scene = read(WORK / "raw" / case / "browser-scene.svg").decode()
        assert revision_neutral(documents["reopened"]["svg"]) == revision_neutral(final_raw_scene)
        journals.append({"fixture": fixture, "caseId": case,
                         "inputBindings": {state: binding(path) for state, path in paths.items()},
                         "publicSvgFacts": facts, "declaredVisibleNodes": {state: item["visibleNodes"] for state, item in documents.items()},
                         "undoEqualsBeforeExceptRevision": True, "redoChangesPublicSvg": True,
                         "redoSavedReopenedExactSvgBytesEqual": True,
                         "finalCaptureEqualsReopenedExceptRevision": True,
                         "cameraChangedOnReopen": documents["saved"]["camera"] != documents["reopened"]["camera"],
                         "finalRawScene": binding(WORK / "raw" / case / "browser-scene.svg")})
    emit("edited-journal-svg-audit.json", {
        "schemaVersion": 1, "checkedAt": now, "auditorSource": binding(Path(__file__)),
        "journalJsonCount": 15, "fixtures": journals, "rawFilesModified": False,
        "revisionNeutralComparison": "Only root data-revision attribute and metadata.revision JSON key removed; every other XML tag, attribute, text, tail and child order compared.",
        "limitation": "All15 early JSON visibleNodes fields are0 from an outdated operator selector; actual publicSVG data-node-id counts are reported separately. Raw JSON is preserved. PublicSVG undo/redo/save/reopen equality establishes scene effects, not viewport pixel aesthetics or human task completion.",
        "humanAcceptanceCertified": False})
    print(json.dumps({"caseCount": 39, "baselineCount": 36, "editedModels": 3,
                      "collectedFileByteComparisons": 234, "jpegHeadersMatchingViewportDpr": 39,
                      "journalJsonCount": 15, "undoRedoSaveReopenSvgChecks": 3,
                      "output": ["full-collection-byte-audit.json", "edited-journal-svg-audit.json"]}))


if __name__ == "__main__":
    main()
