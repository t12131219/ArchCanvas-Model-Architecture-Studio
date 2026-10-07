"""Read current docs, frozen receipts and history; no product helper/test imports."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def binding(path, base=ROOT):
    raw = path.read_bytes()
    return {"path": str(path.relative_to(base)), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def load(path):
    return json.loads((ROOT / path).read_bytes())


def inventory(directory):
    return {str(p.relative_to(directory)): {"bytes": len(p.read_bytes()), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(directory.rglob("*")) if p.is_file()}


def main():
    checks = []

    def check(name, condition):
        checks.append({"name": name, "passed": bool(condition)})
        assert condition, name

    initial = json.loads((HERE / "initial-entry-update.json").read_bytes())
    archive = load("docs/evidence/m4-performance-next-current/before-change/manifest.json")
    old = {item["path"]: item for item in archive["inputs"]}
    check("121 exact pre-change snapshots", len(old) == 121)
    for item in archive["inputs"]:
        actual = binding(ROOT / item["snapshot"])
        check("pre-change original bytes " + item["path"], actual["bytes"] == item["bytes"] and actual["sha256"] == item["sha256"])
    current_paths = [item["path"] for item in initial["entries"]] + ["docs/evidence/m4-current-gate-audit.json", "docs/m4-native-drain-caption.md", "docs/evidence/m4-performance-next-current/README.md", "skills/archcanvas/SKILL.md"]
    before = {path: binding(ROOT / path) for path in current_paths}
    histories, headers, markdown_links, diffs = [], [], [], []
    cn_common, en_common = [], []
    visual_intro = "Use this reference for figure creation, visual refinement, expansion, and export. These are acceptance contracts for a compatible Studio, not assertions that every installed runtime supports them. Check operations before invoking them."
    notice = "\n> 历史阶段记录：以下事实仅对应本篇原有 DuFX/CC91/B_XH 冻结时点，不继承为当前 BTw7 认证。最新采样边界/连线文字修复与研究包见 [当前阶段](m4-native-drain-caption.md)及 [当前门状态](evidence/m4-current-gate-audit.json)。旧正文和证据保留。\n"
    for item in initial["entries"]:
        path = item["path"]
        old_text = (ROOT / old[path]["snapshot"]).read_text()
        text = (ROOT / path).read_text()
        diffs.append({"path": path, "diff": "".join(difflib.unified_diff(old_text.splitlines(keepends=True), text.splitlines(keepends=True), fromfile=old[path]["snapshot"], tofile=path))})
        if item["scope"].startswith("Current header"):
            old_parts = list(re.finditer(r"^## ", old_text, re.M))
            parts = list(re.finditer(r"^## ", text, re.M))
            header, body = text[:parts[1].start()], text[parts[1].start():]
            old_body = old_text[old_parts[1].start():]
            if path == "docs/m4-research-protocol.md":
                correction = initial["historicalResearchCorrection"]
                check("one explicit research historical context correction", old_body.count(correction["before"]) == body.count(correction["after"]) == 1)
                old_body = old_body.replace(correction["before"], correction["after"])
                check("current exact verify command", ".venv/bin/python scripts/research_trial.py verify --package .archcanvas/m4-research-trial-btw-current" in header and "8a8be05f0ebbfde11e4fa208bee1b7e12a5a49f7e7cc74529e5215d4416b3a96" in header and "不是研究验收" in header)
            check("historical body preserved " + path, old_body == body)
            histories.append({"path": path, "historicalBodySha256": hashlib.sha256(body.encode()).hexdigest(), "singleResearchContextCorrection": path == "docs/m4-research-protocol.md"})
            for token in ["index-BTw7OHsD.js", "index--unhoRTb.css", "358/358", "9/9", "106", "280/280", "43551–43555", "160/72/160", "58.605395179", "672×641"]:
                check("current header token " + path + " " + token, token in header)
            normalized = re.sub(r"(!?\[[^\]]*\])\([^\)]+\)", r"\1", header)
            common = normalized[normalized.index("## "):].split("### 当前 BTw7 包")[0].split(visual_intro)[0].rstrip()
            if path.startswith("skills/"):
                en_common.append(common)
                check("English acceptance boundaries " + path, all(token in header for token in ["partial", "not_started", "humans 0", "AI is not a human participant", "visual quality is not approved", "preclude A/B or an improvement claim", "not presented FPS", "no generated model was executed"]))
            else:
                cn_common.append(common)
                check("Chinese acceptance boundaries " + path, all(token in header for token in ["partial", "not_started", "真人 0", "AI 不计真人", "未判视觉通过", "不作 A/B 或性能改善结论", "不是实际呈现 FPS", "未执行生成模型"]))
            headers.append({"path": path, "headerSha256": hashlib.sha256(header.encode()).hexdigest()})
        else:
            check("whole old stage preserved " + path, text.count(notice) == 1 and text.replace(notice, "", 1) == old_text)
            histories.append({"path": path, "entireOldContentExactAfterRemovingNotice": True})
    check("13 matching current headers", len(headers) == 13 and len(cn_common) == 10 and len(en_common) == 3 and len(set(cn_common)) == len(set(en_common)) == 1)
    check("old AI index untouched", (ROOT / "docs/evidence/m4-ai-simulated-current/README.md").read_bytes() == (ROOT / old["docs/evidence/m4-ai-simulated-current/README.md"]["snapshot"]).read_bytes())

    for path in current_paths:
        if not path.endswith(".md"):
            continue
        source = ROOT / path
        for target in re.findall(r"!?\[[^\]]*\]\(([^\)]+)\)", source.read_text()):
            target = target.strip().removeprefix("<").removesuffix(">")
            if re.match(r"(?:[a-zA-Z][a-zA-Z0-9+.-]*:|#)", target):
                continue
            resolved = (source.parent / unquote(target.split("#")[0].split("?")[0])).resolve()
            markdown_links.append({"from": path, "target": target, "resolved": str(resolved), "exists": resolved.exists()})
    check("all local Markdown links resolve", all(item["exists"] for item in markdown_links))
    gate = load("docs/evidence/m4-current-gate-audit.json")
    old_gate = load(old["docs/evidence/m4-current-gate-audit.json"]["snapshot"])
    reqs = {item["id"]: item for item in gate["requirements"]}
    old_reqs = {item["id"]: item for item in old_gate["requirements"]}
    gate_links = [{"path": path, "exists": (ROOT / path).is_file()} for item in gate["requirements"] for path in item["evidence"]]
    check("all current gate links resolve", all(item["exists"] for item in gate_links))
    check("M4partial M5notstarted human0", gate["overall"] == "partial" and gate["m5"] == "not_started" and gate["humanParticipants"] == 0)
    check("open human/publication/performance gates", reqs["research-task"]["status"] == reqs["publication-review"]["status"] == "not_done" and reqs["browser-performance"]["status"] == "failed_or_unverified")
    for key in ["base-models", "semantic-holdout", "shared-repeat-opaque"]:
        check("old static requirement exact " + key, reqs[key] == old_reqs[key])
    for key in ["observedHistorical", "observedPreviousThbumDiagnostic", "observedHistoricalD60NativeSmoke", "observedHistoricalDuFXDiagnostic"]:
        check("old performance data exact " + key, reqs["browser-performance"][key] == old_reqs["browser-performance"][key])
    check("three old AI roles only", gate["aiSimulatedRoles"]["count"] == 3 and gate["aiSimulatedRoles"]["humanParticipants"] == 0 and gate["aiSimulatedRoles"]["initialBrowserBuild"] == "index-DuFXKOwG.js" and gate["aiSimulatedRoles"]["finalTargetedReadbackBuild"] == "index-B_XHk-wz.js")
    receipt = load("docs/evidence/m4-performance-next-current/checks-final-attempt-2/receipt.json")
    check("106 current source/dist and strict0", len(receipt["inputs"]) == 103 and len(receipt["build"]) == 3 and all(item["exitCode"] == 0 for item in receipt["checks"]) and gate["build"]["js"] == "index-BTw7OHsD.js" and gate["build"]["totalSourceBuildBindings"] == 106)
    for item in receipt["inputs"] + receipt["build"]:
        check("current product bytes " + item["path"], binding(ROOT / item["path"]) == {key: item[key] for key in ["path", "bytes", "sha256"]})
    check("358product9publication separate", gate["build"]["studioTests"] == 358 and gate["build"]["skipped"] == 0 and gate["build"]["publicationTests"] == 9 and gate["build"]["publicationSkipped"] == 0 and gate["build"]["strictBuildExitCode"] == 0)
    native = load("docs/evidence/m4-performance-next-current/final-native-browser/receipt.json")
    observed = reqs["browser-performance"]["observedCurrentBtw7"]
    check("native 3 matched subset exact", native["summary"]["capturedTrials"] == native["summary"]["validSceneTrials"] == native["summary"]["matchedNativeTrials"] == observed["matchedNativeTrials"] == 3 and native["durationsMs"] == observed["nativeDurationMs"] == [160, 72, 160] and native["summary"]["nativeInputToNextPaintP95Ms"] == observed["matchedSubsetInputToNextPaintP95Ms"] == 160 and native["rAFCallbackCadenceHz"] == observed["rAFCallbackCadenceHz"])
    check("native viewport and nonacceptance", native["bodyCoverage"]["renderedFrontier"] == 304 and observed["geometricViewportIntersections"] == native["bodyCoverage"]["geometricViewportIntersections"] == 6 and native["bodyCoverage"]["fullyInsideViewport"] == 4 and native["environment"]["viewport"]["width"] == 1102 and native["environment"]["viewport"]["height"] == 835 and native["bodyCoverage"]["viewport"]["width"] == 672 and native["bodyCoverage"]["viewport"]["height"] == 641 and not observed["performanceGatePassed"] and not observed["presentedFpsCertified"] and not observed["sameBeforeAfterViewport"] and not observed["improvementClaimed"])
    browser = load("docs/evidence/m4-performance-next-current/final-browser/receipt.json")
    caption = reqs["visual-authoring"]["observedCurrentCaption"]
    check("same document reselect caption bounded", caption["sameDocumentReopen"] == browser["sameDocumentReopen"] and caption["associationBaselineDistanceWorld"] == 56 and not caption["visualQualityApproved"] and not caption["sameDocumentReopen"]["cameraPreservationClaim"] and caption["sameDocumentReopen"]["revision"] == 0 and 'y="388.1"' in caption["sameDocumentReopen"]["memoryXml"])
    export = reqs["publication-review"]["observedCurrentExportPreflight"]
    check("physical export preflight not human", export["whole180MinTextPt"] == browser["exports"][0]["physicalPreflight"]["minTextPt"] and export["detail180MinTextPt"] == browser["exports"][1]["physicalPreflight"]["minTextPt"] and export["pdfGenerated"] and not export["humanReviewCertified"])
    package = ROOT / gate["currentResearchPackage"]["path"]
    package_manifest = json.loads((package / "manifest.json").read_bytes())
    ready = load("docs/evidence/m4-performance-next-current/research-final-preparation/readiness-report.json")
    check("280ready notresearch acceptance", gate["currentResearchPackage"]["independentReadiness"] == {"passed": 280, "total": 280} and ready["passed"] == ready["total"] == 280 and gate["currentResearchPackage"]["humans"] == 0 and not gate["currentResearchPackage"]["servicesStarted"] and not gate["currentResearchPackage"]["portsAvailabilityChecked"])
    check("current exact package path ports hash", gate["currentResearchPackage"]["path"] == ".archcanvas/m4-research-trial-btw-current" and gate["currentResearchPackage"]["manifestSha256"] == binding(package / "manifest.json")["sha256"] == "8a8be05f0ebbfde11e4fa208bee1b7e12a5a49f7e7cc74529e5215d4416b3a96" and gate["currentResearchPackage"]["registeredPorts"] == [slot["port"] for slot in package_manifest["slots"]] == list(range(43551, 43556)))
    check("new package17files pristine", inventory(package) == ready["packageFilesBeforeAfter"] and all(slot["participantCode"] is None and slot["assignment"] == "unassigned" for slot in package_manifest["slots"]))
    preflight = load("docs/evidence/m4-performance-next-current/research-final-preparation/preflight.json")
    for path, original in preflight["oldResearchPackages"].items():
        check("old research package exact " + path, inventory(ROOT / path) == original)
    check("20oldpackages342files", len(preflight["oldResearchPackages"]) == 20 and sum(len(items) for items in preflight["oldResearchPackages"].values()) == 342)
    frozen_manifests = []
    for name in ["final-native-browser/manifest.json", "final-browser/manifest.json", "research-final-preparation/manifest.json"]:
        manifest_path = ROOT / "docs/evidence/m4-performance-next-current" / name
        manifest = json.loads(manifest_path.read_bytes())
        for item in manifest["artifacts"]:
            check("frozen artifact " + name + " " + item["path"], binding(manifest_path.parent / item["path"], manifest_path.parent) == item)
        for item in manifest["externalBindings"]:
            check("frozen external " + name + " " + item["path"], binding(ROOT / item["path"]) == item)
        frozen_manifests.append({"manifest": binding(manifest_path), "artifactsExact": len(manifest["artifacts"]), "externalBindingsExact": len(manifest["externalBindings"])})
    stage = (ROOT / "docs/m4-native-drain-caption.md").read_text()
    check("stage boundary wording", all(token in stage for token in ["358/358", "280/280", "160、72、160", "不形成A/B或性能改善证据", "标签避障不是全局视觉通过", "模型未执行", "三个 AI 模拟角色", "20个旧包342文件"]))
    check("no current doc changed during readback", all(binding(ROOT / path) == expected for path, expected in before.items()))
    snapshots = []
    for path in current_paths:
        target = HERE / "final-inputs" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as file:
            file.write((ROOT / path).read_bytes())
        snapshots.append({**binding(ROOT / path), "snapshot": str(target.relative_to(ROOT))})
    result = {"createdUtc": datetime.now(timezone.utc).isoformat(), "status": "passed-current-entry-history-links-and-receipt-readback", "findings": [],
              "productTests": {"studio": 358, "skipped": 0, "publication": 9, "publicationSkipped": 0, "strictBuildExitCode": 0, "sourceBuildBindingsExact": 106},
              "researchReadinessChecks": 280, "entryRelations": {"passed": len(checks), "total": len(checks), "notProductTestsOrParticipants": True},
              "ownedMarkdownEntries": 15, "currentHeaders": 13, "archiveSnapshotBindingsExact": 121,
              "historyPreservation": histories, "currentSnapshots": snapshots,
              "markdownLinks": {"total": len(markdown_links), "allExist": True, "links": markdown_links}, "gateEvidenceLinks": gate_links,
              "frozenManifests": frozen_manifests, "checks": checks,
              "scope": "Owned current documentation updates and readback only. No new build/product test/model/browser/service/assign/collect. Current stage/index by root are read inputs; future root final report is deliberately not bound.",
              "limits": ["Links establish local target existence only, not external availability or anchor semantics.", "Geometry/receipts do not certify pixels, font masks, camera persistence, label association, physical publication, complete input denominator or presented FPS.", "Previous three AI simulated users remain historical; document auditors do not add users. The three counts358/280/entryRelations are distinct and not additive."],
              "m4": "partial", "m5": "not_started", "humans": 0}
    for name, value in [("final-report.json", result), ("final-entry-diffs.json", diffs)]:
        with (HERE / name).open("x") as file:
            file.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "entryRelations": len(checks), "markdownLinks": len(markdown_links), "gateEvidenceLinks": len(gate_links), "archiveSnapshots": 121, "productBindings": 106, "findings": []}))


if __name__ == "__main__":
    main()
