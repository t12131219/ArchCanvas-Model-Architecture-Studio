"""Independent final browser JSON/XML/file evidence inspection.

No product imports, models, runtime renderer/history, UI or service operations.
"""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from check_directional_roles_v3 import NS, ensure, geometric_findings, matrix_of, read_capture, sha


def binding(path):
    path = Path(path).resolve(); raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": sha(raw)}


def public_facts(scene):
    return {key: scene["metadata"].get(key) for key in ("documentId", "sourceDigest", "irDigest", "sourceFactScope", "sourceFacts")}


def document_matches_scene(document, capture):
    scene, metadata = capture["scene"], capture["scene"]["metadata"]
    architecture = document["architecture"]
    ensure(document["id"] == metadata["documentId"] and document["revision"] == metadata["revision"], "Persisted document identity/revision differs")
    ensure(document["sourceBindingDigest"] == architecture["sourceDigest"] == metadata["sourceDigest"] and architecture["irDigest"] == metadata["irDigest"], "Persisted source/IR identity differs")
    nodes = {node["id"]: node for node in architecture["nodes"]}
    facts = {fact["id"]: fact for fact in metadata["sourceFacts"]}
    ensure(set(nodes) == set(facts), "Complete stored nodes differ from complete sourceFacts")
    source_receipts = []
    for source in architecture["sources"]:
        ensure(sha(source["content"].encode()) == source["digest"], "Stored source file digest differs from actual source bytes")
        source_receipts.append({"path": source["path"], "bytes": len(source["content"].encode()), "sha256": source["digest"]})
    for identity, node in nodes.items():
        fact = facts[identity]
        ensure(all(node.get(key) == fact.get(key) for key in ("id", "kind", "category", "source", "instanceId", "callId", "evidence", "repeat", "outputPath")), "Stored canonical node facts differ from public facts")
        ensure(node["label"] == fact["sourceLabel"], "Stored source label differs from public source label")
    edges = {edge["id"]: edge for edge in architecture["edges"]}
    for record in metadata["renderedBindings"]:
        ensure(len(record["canonicalEdgeIds"]) == 1, "This stored MLP check requires explicit single canonical edge")
        edge = edges[record["canonicalEdgeIds"][0]]
        ensure(all(edge[key] == record[key] for key in ("source", "target", "tensorId", "role")), "Stored canonical edge differs from rendered binding")
        for side in ("source", "target"):
            ensure(any(port["id"] == edge[side]["portId"] for port in nodes[edge[side]["nodeId"]]["ports"]), "Stored edge endpoint has no canonical port")
    layout = document["layout"]
    def global_position(identity, active=None):
        active = set() if active is None else active
        ensure(identity not in active, "Stored parent/layout cycle")
        active.add(identity)
        local = layout[identity]
        parent = nodes[identity].get("parentId")
        parent_xy = global_position(parent, active) if parent else (0, 0)
        return (local["x"] + parent_xy[0], local["y"] + parent_xy[1])
    for identity, body in scene["bodies"].items():
        ensure((body["x"], body["y"]) == global_position(identity), "Persisted local anchor differs from actual reopened SVG body")
    expanded, pinned = json.loads(capture["capture"]["expandedIds"]), json.loads(capture["capture"]["pinnedIds"])
    ensure(document["expandedIds"] == expanded and document["pinnedObjects"] == pinned, "Stored frontier/pinned membership differs")
    return {"completeCanonicalFactsMatched": True, "renderedBindingsMatchedStoredCanonicalPorts": True, "visibleBodyAnchorsMatchStoredParentLocalCoordinates": True, "sourceFileDigestsRecomputed": source_receipts, "architectureDigestAlgorithmRecomputed": False}


def run(scope, repository, output):
    journal = json.loads((scope / "journal.json").read_text())
    ensure(journal["status"] == "representative-ui-captures-await-independent-audit", "Capture journal not declared complete")
    ensure(len(journal["captures"]) == 52 and len({item["path"] for item in journal["captures"]}) == 52, "Expected 52 unique representative captures")
    summaries, by_label, documents = [], {}, {}
    for item in journal["captures"]:
        path = Path(item["path"]).resolve()
        ensure(path.parent == scope and path.name == item["label"] + ".json" and "right-first" not in path.name, "Capture escapes scope or uses excluded first attempt")
        capture = read_capture(path); by_label[item["label"]] = capture
        dom, scene = capture["capture"], capture["scene"]
        ensure(dom["scripts"] == ["/assets/" + journal["build"]], "Capture script identity differs from journal")
        ensure(json.loads(dom["metadata"]) == scene["metadata"], "Public metadata differs from actual SVG metadata")
        identity = scene["metadata"]["documentId"]
        if identity in documents:
            ensure(public_facts(scene) == documents[identity], "Complete source/IR/facts change between views of same document")
        else:
            documents[identity] = public_facts(scene)
        summaries.append({"label": item["label"], "inputBinding": capture["binding"], "documentId": identity, "revision": scene["metadata"]["revision"], "renderedNodeCount": len(scene["nodes"]), "renderedBindingCount": len(scene["edges"]), "boundEndpointCount": len(scene["endpointChecks"]), "geometricFindings": geometric_findings(scene)})
    build = repository / "studio/dist/assets" / journal["build"]
    ensure(binding(build)["sha256"] == journal["buildSha256"], "Local dist build hash differs from journal")
    # Save and reopen bind real storage bytes, not the success notice alone.
    saved_transport = json.loads((scope / "save-transport.json").read_text())
    saved_actual = repository / saved_transport["actualPath"]
    saved_copy = repository / saved_transport["copiedPath"]
    for path in (saved_actual, saved_copy):
        ensure(binding(path)["sha256"] == saved_transport["sha256"] and binding(path)["bytes"] == saved_transport["bytes"], "Actual saved file/copy differs from transport record")
    ensure(saved_actual.read_bytes() == saved_copy.read_bytes(), "Actual DocumentStore copy is not byte-exact")
    envelope = json.loads(saved_copy.read_text()); document = envelope["document"]
    ensure(envelope["revision"] == 1 and document["revision"] == 21, "Actual storage envelope/document revisions differ")
    before, reopened = by_label["save-after"], by_label["save-reopened"]
    ensure(before["scene"]["svg"] == reopened["scene"]["svg"], "Save/reopen did not preserve exact public SVG/revision")
    saved_check = document_matches_scene(document, reopened)
    # Actual file generation, public link and browser endpoint are separate from
    # user-directory delivery; no link alone implies a download was received.
    transport = json.loads((scope / "export-transport.json").read_text())
    actual_export_bindings = []
    for record in transport["files"]:
        actual, copied = repository / record["actualPath"], repository / record["copiedPath"]
        ensure(actual.read_bytes() == copied.read_bytes(), "Actual export copy is not byte-exact")
        ensure(binding(actual)["sha256"] == record["sha256"] and binding(actual)["bytes"] == record["bytes"], "Actual export artifact digest/size differs")
        actual_export_bindings.append({"actual": binding(actual), "copy": binding(copied)})
    exported = read_capture(scope / "actual-export/figure.svg")
    browser = read_capture(scope / "actual-export-browser-dom.json")
    ensure(ET.tostring(exported["scene"]["root"]) == ET.tostring(browser["scene"]["root"]), "Actual SVG endpoint browser DOM differs from service SVG XML tree")
    browser_envelope = json.loads((scope / "actual-export-browser-dom.json").read_text())
    ensure(browser_envelope["url"] == "http://127.0.0.1:8912" + transport["publicHref"], "Browser endpoint URL differs from generated file URL")
    ensure(json.loads(browser_envelope["dom"]["metadata"]) == exported["scene"]["metadata"], "Browser endpoint metadata text differs")
    receipt = json.loads((scope / "actual-export/figure.svg.receipt.json").read_text())
    ensure(all(receipt[key] == exported["binding"]["sha256"] for key in ("outputDigest", "svgDigest")) and receipt["bytes"] == exported["binding"]["bytes"], "Publication receipt output digest/size differs from actual file")
    ensure(all(receipt[key] == exported["scene"]["metadata"][key] for key in ("documentId", "revision", "sourceDigest", "irDigest", "widthMm", "heightMm")), "Actual export receipt canonical facts/dimensions differ")
    generated = by_label["export-generated-settled"]["capture"]
    ensure(len(generated["receipts"]) == 1 and json.loads(generated["receipts"][0]) == receipt, "Visible export receipt differs from actual receipt file")
    links = {link["text"]: link["href"] for link in generated["links"]}
    ensure(links.get("查看 SVG") == links.get("下载文件") == transport["publicHref"] and links.get("查看导出收据") == transport["publicHref"].rsplit("/", 1)[0] + "/receipt", "Visible view/download/receipt URLs differ")
    export_document = json.loads((scope / "actual-export/document.json").read_text())
    ensure(export_document == document, "Frozen actual export document differs from saved document")
    export_doc_check = document_matches_scene(export_document, by_label["export-before"])
    # The interrupted down reverse remains failed and cannot inherit round2.
    down = [by_label[label] for label in ("pan-down-before", "pan-down-moved", "pan-down-after-timeout")]
    matrices = [matrix_of(capture["capture"]) for capture in down]
    ensure(down[0]["scene"]["svg"] == down[1]["scene"]["svg"] == down[2]["scene"]["svg"], "Failed pan changed exact SVG")
    failed_delta = [matrices[2][i] - matrices[0][i] for i in (4, 5)]
    ensure(failed_delta == [0, 25], "Interrupted pan residual no longer matches retained +25 evidence")
    # Navigation of the deep Transformer changes camera only; hierarchy stages
    # preserve complete facts but legitimately change visible projections.
    views = [by_label[label] for label in ("transformer-l3-fit-settled", "transformer-l3-100-settled", "transformer-l3-detail-pan-settled")]
    ensure(views[0]["scene"]["svg"] == views[1]["scene"]["svg"] == views[2]["scene"]["svg"], "Transformer zoom/pan changes exact public SVG")
    vm = [matrix_of(capture["capture"]) for capture in views]
    ensure(vm[1][0] == vm[2][0] == 1 and abs((vm[2][4] - vm[1][4]) + 350) < .001 and vm[2][5] - vm[1][5] == -250, "Transformer actual local camera delta differs")
    result = {"schema": "archcanvas-independent-final-browser-artifact-audit/1", "status": "passed-bounded-public-artifact-consistency-with-retained-findings", "journalBinding": binding(scope / "journal.json"), "checkerBinding": binding(Path(__file__)), "captureCount": len(summaries), "documentIdentityCount": len(documents), "matrixCases": journal["matrixCases"], "localBuildBinding": binding(build), "publicCaptureSummaries": summaries, "saveReopen": {"status": "passed-actual-file-and-reopened-public-svg-consistency", "storageEnvelopeRevision": envelope["revision"], "canvasRevision": document["revision"], "actualFileBinding": binding(saved_actual), "copyBinding": binding(saved_copy), "fullSvgByteExact": True, "cameraPersisted": matrix_of(before["capture"]) == matrix_of(reopened["capture"]), "canonicalAndAnchorCheck": saved_check, "browserActionReceiptExplicit": False, "scope": "Captured before/reopened public DOM plus actual DocumentStore bytes; no human acceptance or source execution"}, "export": {"status": "passed-actual-service-files-public-links-browser-endpoint-and-receipt-consistency", "fileBindings": actual_export_bindings, "actualServiceGeneratedBytesVerified": True, "browserEndpointSvgXmlTreeExact": True, "generatedDownloadUrlVerified": True, "downloadAttributeCaptured": False, "downloadClickedCertified": False, "downloadToUserDirectoryCertified": False, "fontEmbeddingCertified": False, "actualFrozenDocumentMatchesSaved": True, "canonicalAndAnchorCheck": export_doc_check, "receiptInputSvgDigestIndependentlyRecomputed": False}, "retainedFailedDownPan": {"status": "failed-reversal", "actualFinalCssDeltaFromBefore": failed_delta, "inputs": [capture["binding"] for capture in down], "successfulDirectionCoverageUsesOnlyRound2": True}, "transformerViews": {"publicSvgByteExactAcrossFit100AndPan": True, "completeSourceFactsStableAcrossL1L2L3": True, "actual100PercentScale": vm[1][0], "actualPanCssDelta": [vm[2][4] - vm[1][4], vm[2][5] - vm[1][5]], "allPresentedTextReadableCertified": False}, "issues": [], "humanParticipants": 0, "humanCertified": False, "publicationCertified": False, "presentedFramesCertified": False, "m4Complete": False}
    ensure(not output.exists(), "Final results must use a fresh filename")
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scope", type=Path); parser.add_argument("--repository", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.scope.resolve(), args.repository.resolve(), args.output.resolve())
    print(json.dumps({key: result[key] for key in ("status", "captureCount", "documentIdentityCount", "issues")}, indent=2))
