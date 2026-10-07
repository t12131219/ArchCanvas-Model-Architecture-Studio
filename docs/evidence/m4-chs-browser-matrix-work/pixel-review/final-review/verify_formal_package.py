"""Read-only independent package/UUID/full-document audit; stdlib only, no renderer imports."""
from pathlib import Path
from collections import Counter
import datetime
import hashlib
import json
import re
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
WORK = OUT.parent.parent
ROOT = WORK.parents[2]
PACKAGE = ROOT / "docs/evidence/browser-visual-matrix-chs-current"
AUDIT = WORK / "collection/attempt-2/final-local-byte-audit.json"
SELECTED = OUT / "selected-39-independent-review.json"


def bind(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode())


def xml_value(node):
    return [node.tag, sorted(node.attrib.items()), node.text or "", node.tail or "", [xml_value(child) for child in node]]


def metadata(path):
    root = ET.parse(path).getroot()
    return root, json.loads(next(child for child in root if child.tag.endswith("metadata")).text)


audit_binding = bind(AUDIT)
assert audit_binding["sha256"] == "0d2e5c222677f43457ffb46b24e2deecbc15b3af57fbb2a3cd66ce6c1f584bc1"
audit = json.loads(AUDIT.read_text())
selection = json.loads(SELECTED.read_text())
manifest = json.loads((PACKAGE / "manifest.json").read_text())
spec_path = Path(audit["spec"]["path"])
index_path = Path(audit["captureIndex"]["path"])
spec = json.loads(spec_path.read_text())
index = json.loads(index_path.read_text())
expected = set(selection["selectedCaseIds"])
assert len(manifest["captures"]) == 39 and {case["caseId"] for case in manifest["captures"]} == expected
assert {case["caseId"] for case in index["captures"]} == expected
assert {case["caseId"] for case in audit["caseResults"]} == expected
assert len(manifest["variants"]) == 36
assert Counter(case["state"] for case in manifest["captures"]) == {"baseline": 36, "edited": 3}
assert len({(case["variantId"], case["state"]) for case in manifest["captures"]}) == 39
assert manifest["artifactCoverage"] == "complete" and manifest["visualAcceptance"] == "pending-human-review" and manifest["humanAcceptanceCertified"] is False
assert bind(spec_path)["sha256"] == manifest["specDigest"]
for field in ["manifest", "spec", "captureIndex"]:
    assert bind(audit[field]["path"]) == audit[field]
assert len(audit["inputBindings"]) == 1060
for binding in audit["inputBindings"]:
    assert bind(binding["path"]) == binding, "Pack audit input changed"
for binding in selection["rawBindingsStart"]:
    assert bind(binding["path"]) == binding, "Independently pixel-reviewed raw changed"

manifest_cases = {case["caseId"]: case for case in manifest["captures"]}
spec_variants = {variant["variantId"]: variant for variant in spec["variants"]}
index_cases = {case["caseId"]: case for case in index["captures"]}
selected_cases = {case["caseId"]: case for case in selection["cases"]}
inputs = {binding["path"]: binding for binding in audit["inputBindings"]}
for binding in selection["rawBindingsStart"]:
    previous = inputs.get(binding["path"])
    assert previous is None or previous == binding
    inputs[binding["path"]] = binding
for path in [AUDIT, SELECTED, Path(__file__), ROOT / "scripts/browser_visual_matrix.py", ROOT / "studio/src/core/nodeFacts.ts"]:
    binding = bind(path)
    inputs[binding["path"]] = binding
for path in PACKAGE.rglob("*"):
    if path.is_file():
        binding = bind(path)
        previous = inputs.get(binding["path"])
        assert previous is None or previous == binding
        inputs[binding["path"]] = binding
start = [bind(path) for path in sorted(inputs)]
assert all(binding == inputs[binding["path"]] for binding in start)
cases = []
uuid_list = []
six_mapping_count = 0
route_count = 0
canonical_member_count = 0
for index_number, capture in enumerate(manifest["captures"]):
    case_id = capture["caseId"]
    variant = spec_variants[capture["variantId"]]
    raw = WORK / "raw" / case_id
    observation_path = raw / ("dom-observation-correct-variant.json" if (raw / "dom-observation-correct-variant.json").exists() else "dom-observation.json")
    observation = json.loads(observation_path.read_text())
    assert observation["caseId"] == case_id and observation["variantId"] == capture["variantId"] and observation["state"] == capture["state"]
    assert observation["documentBinding"] == capture["documentBinding"] == selected_cases[case_id]["documentBinding"]
    directory = PACKAGE / "captures" / case_id
    files = {field: PACKAGE / declaration["path"] for field, declaration in capture["files"].items()}
    copies = []
    for field, declaration in capture["files"].items():
        final = files[field]
        assert final.resolve().is_relative_to(PACKAGE.resolve()) and not final.is_symlink()
        current = bind(final)
        assert (current["bytes"], current["sha256"]) == (declaration["bytes"], declaration["sha256"])
        bound = index_path.parent / index_cases[case_id][field]
        assert bound.read_bytes() == final.read_bytes()
        copies.append({"field": field, "bound": bind(bound), "collected": current, "exact": True})
        six_mapping_count += 1
    assert raw.joinpath("screenshot.jpg").read_bytes() == files["screenshot"].read_bytes()
    assert raw.joinpath("browser-scene.svg").read_bytes() == files["browserScene"].read_bytes()
    canvas = json.loads(files["canvas"].read_text())
    envelope = json.loads((raw / "saved-envelope.json").read_text())
    assert canvas == envelope["document"], "Full document equality, including layoutByFrontier, required"
    assert canonical(canvas) == capture["canvasCanonicalDigest"]
    assert canvas["architecture"] == json.loads(Path(variant["canvasFile"]).read_text())["architecture"]
    assert canvas["id"] == variant["documentId"] and canvas["sourceBindingDigest"] == variant["sourceDigest"]
    assert sorted(canvas["expandedIds"]) == sorted(variant["expandedIds"]) == sorted(observation["expandedIds"])
    assert canvas["pageSpec"]["widthMm"] == variant["widthMm"] and canvas["pageSpec"]["preset"] == variant["preset"]
    actual_url = observation["actualExport"]["observedUrl"]
    href_path = raw / "observed-href.txt"
    if href_path.exists():
        actual_href = href_path.read_text().strip()
        href_scope = "raw observed-href.txt"
    elif (raw / "export-complete.dom.txt").exists():
        href_matches = set(re.findall(r"/api/exports/[a-f0-9]{32}/figure\.svg", (raw / "export-complete.dom.txt").read_text()))
        assert len(href_matches) == 1
        actual_href = href_matches.pop()
        href_scope = "raw export-complete DOM"
    else:
        actual_href = actual_url
        href_scope = "operator public observation actualExport; no separate raw export DOM/href file"
    assert actual_url == actual_href
    uuid = re.fullmatch(r"/api/exports/([a-f0-9]{32})/figure\.svg", actual_url).group(1)
    uuid_list.append(uuid)
    service = ROOT / ".archcanvas/m4-chs-browser-session/exports" / uuid
    screen = json.loads(files["screenReceipt"].read_text())
    receipt = json.loads(files["exportReceipt"].read_text())
    service_document = json.loads((service / "document.json").read_text())
    assert service_document.get("document", service_document) == canvas
    assert (service / "figure.svg").read_bytes() == files["svg"].read_bytes()
    assert (service / "figure.svg.receipt.json").read_bytes() == files["exportReceipt"].read_bytes()
    assert screen["actualExport"]["observedUrl"] == actual_url and screen["actualExport"]["serviceArtifactId"] == uuid
    assert Path(screen["actualExport"]["sourceDirectory"]).resolve() == service.resolve()
    assert Path(receipt["path"]).parent.resolve() == service.resolve()
    assert screen["caseId"] == case_id and screen["variantId"] == capture["variantId"] and screen["state"] == capture["state"]
    assert screen["documentBinding"] == capture["documentBinding"]
    assert screen["screenshotDigest"] == sha(files["screenshot"].read_bytes())
    browser_root, browser_metadata = metadata(files["browserScene"])
    figure_root, figure_metadata = metadata(files["svg"])
    assert canonical(xml_value(browser_root)) == screen["browserSceneDigest"] == capture["browserSceneDigest"]
    expected_interactive = PACKAGE / "expected" / f"{index_number}.interactive.svg"
    expected_publication = PACKAGE / "expected" / f"{index_number}.publication.svg"
    assert canonical(xml_value(ET.parse(expected_interactive).getroot())) == screen["browserSceneDigest"]
    assert sha(expected_publication.read_bytes()) == receipt["inputSvgDigest"] == receipt["sceneSvgDigest"]
    assert sha(files["svg"].read_bytes()) == receipt["outputDigest"] == receipt["svgDigest"] and receipt["bytes"] == files["svg"].stat().st_size
    assert receipt["exportScope"] == {"kind": "document"}
    assert browser_metadata == figure_metadata, "Full publication/browser metadata equality"
    assert browser_metadata["documentId"] == canvas["id"] and browser_metadata["revision"] == canvas["revision"]
    assert browser_metadata["sourceDigest"] == canvas["architecture"]["sourceDigest"] and browser_metadata["irDigest"] == canvas["architecture"]["irDigest"]
    nodes = {node["id"]: node for node in canvas["architecture"]["nodes"]}
    edges = {edge["id"]: edge for edge in canvas["architecture"]["edges"]}
    calls = {}
    for node in canvas["architecture"]["nodes"]:
        if node.get("instanceId") and node.get("callId"):
            calls.setdefault(node["instanceId"], set()).add(node["callId"])
    facts = []
    for node in canvas["architecture"]["nodes"]:
        fact = {"id": node["id"], "sourceLabel": node["label"], "kind": node["kind"], "category": node["category"], "evidence": node["evidence"]}
        if node.get("instanceId"):
            fact.update({"instanceId": node["instanceId"], "callCount": len(calls.get(node["instanceId"], set()))})
        for field in ["callId", "repeat", "outputPath"]:
            if field in node:
                fact[field] = node[field]
        if node.get("source"):
            fact["source"] = {field: node["source"][field] for field in ["path", "line", "endLine", "expression"] if field in node["source"]}
        facts.append(fact)
    assert browser_metadata["sourceFacts"] == facts
    checks = []
    for rendered in browser_metadata["renderedBindings"]:
        assert rendered["canonicalEdgeIds"] and len(set(rendered["canonicalEdgeIds"])) == len(rendered["canonicalEdgeIds"])
        members = [edges[edge_id] for edge_id in rendered["canonicalEdgeIds"]]
        assert all(member["role"] == rendered["role"] for member in members)
        for end in ["source", "target"]:
            endpoint = rendered[end]
            assert endpoint["nodeId"] in nodes
            assert any(port["id"] == endpoint["portId"] for port in nodes[endpoint["nodeId"]]["ports"])
        checks.append({**rendered, "fullCanonicalMembers": members, "declaredPortAndRoleChecks": True})
        canonical_member_count += len(members)
    route_count += len(checks)
    assert len(checks) == next(g["routeCount"] for g in json.loads(Path(selection["geometryAggregate"]["path"]).read_text())["cases"] if g["caseId"] == case_id)
    cases.append({"caseId": case_id, "variantId": capture["variantId"], "state": capture["state"], "uuid": uuid, "exactObservedHref": actual_href, "hrefEvidenceScope": href_scope, "documentBinding": capture["documentBinding"], "sixExactMappings": copies, "rawScreenshotAndSvgBytesExact": True, "fullSavedEnvelopeDocumentEqualsCollectedAndUUIDServiceDocument": True, "fullCanvasCanonicalDigest": canonical(canvas), "sourceArchitectureAndPageFrontierExact": True, "fullPublicationBrowserMetadataEqual": True, "allSourceFactsEqualCanonicalNodes": True, "canonicalRenderedBindings": checks, "semanticBrowserExpectedDigestEqual": True, "receiptInputEqualsStoredExpectedPublicationDigest": True, "exactUUIDFigureAndReceiptBytes": True})
assert six_mapping_count == 234 and route_count == 817
assert len(set(uuid_list)) == 39
assert "transformer-level1-paper-85" not in expected and "residual_cnn-level0-paper-180-edited" not in expected
assert not any("primer" in item["path"] for capture in manifest["captures"] for item in capture["files"].values())
end = [bind(path) for path in sorted(inputs)]
assert start == end
result = {"kind": "Independent final formal package UUID/full-canonical/copy/hash audit", "at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "scope": "Read-only local stored-byte and full declaration comparison after pack freeze; no product/renderer imports, no new image views or runtime execution", "counts": {"cases": 39, "baseline": 36, "edited": 3, "uniqueVariantState": 39, "uniqueUUIDs": 39, "exactBoundCollectedMappings": 234, "renderedRouteBindings": route_count, "canonicalEdgeMembershipInstances": canonical_member_count, "packAuditInputsRechecked": 1060, "deduplicatedInputsBoundAndRechecked": len(start)}, "packAudit": audit_binding, "selectedPixelAggregate": bind(SELECTED), "manifest": bind(PACKAGE / "manifest.json"), "inputsStart": start, "inputsEnd": end, "inputsUnchanged": start == end, "allCasesPassed": True, "cases": cases, "coverage": {"artifactCoverage": "complete", "visualAcceptance": "pending-human-review", "humanAcceptanceCertified": False, "primersCounted": False, "excludedOriginalsCounted": False}, "limits": ["Full saved document/canonical/UUID/hash equality proves local declaration and copy consistency, not immutable first acquisition, native provenance, raster synchronization or live current bytes.", "Expected SVG hashes are stored artifacts. Renderer/export normalizer correctness was not re-executed or established by this read-only audit.", "Canonical roles/ports/members are all enumerated, including fused routes. Distinct intermediary tensor IDs are retained rather than forced equal; runtime semantics not certified.", "No new image views. Prior78selected/2excludedoriginal pixel observations, modal/grid/physical-readability limits and numerical route findings are unchanged.", "Product source/dist/spec/raw/collected outputs and earlier799seal/frozen reports are not modified."]}
target = OUT / "formal-package-39-independent-review.json"
with target.open("x") as handle:
    json.dump(result, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
md = target.with_suffix(".md")
with md.open("x") as handle:
    handle.write("# 正式证据包独立复核\n\n39 个有效 capture（36 基线＋3 编辑）、39 个唯一 variant/state、39 个唯一真实导出 UUID 均对应独立图片汇总中的案例；两失败原例与 primer 没有进入正式成功覆盖。\n\n234 个 bound→collected 文件映射均逐一字节相等，截图和 browser SVG 与已审 raw 相等。每个完整 CanvasDocument（包含 layoutByFrontier）与保存 envelope 和该 UUID 的 document.json 相等；Canvas canonical digest、完整 browser/publication metadata、源事实、817 条 rendered binding 的全部 canonical members/roles/declared ports 均已核对。\n\n公开 href、screen receipt 的 UUID、service 目录、figure/receipt 字节、输入 publication SVG 和输出哈希一致。包审计的 1,060 个输入重新哈希相符，本次共 "+str(len(start))+" 个去重输入前后哈希不变。\n\n这些是本地字节、关联和完整声明一致性证据，不认证首次采集不可变、实时存储、原生出处、截图同步、运行时语义或人工验收；未重新执行 renderer/export normalizer，未新增图片查看。原有像素与路线问题保持有效。\n")
for path in [target, md, Path(__file__)]:
    print(json.dumps(bind(path), ensure_ascii=False))
