"""Read-only current-entry/frozen-history review. Uses only stdlib; no product calls."""
from __future__ import annotations

from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASE = ROOT / "docs/evidence/m4-ai-simulated-current"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path, base: Path = ROOT) -> dict:
    raw = path.read_bytes()
    return {"path": str(path.relative_to(base)), "bytes": len(raw), "sha256": sha(raw)}


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_bytes())


def inventory(path: Path) -> dict:
    return {str(p.relative_to(path)): {"bytes": len(p.read_bytes()), "sha256": sha(p.read_bytes())}
            for p in sorted(path.rglob("*")) if p.is_file()}


def sections(text: str) -> tuple[str, str]:
    headings = list(re.finditer(r"^## ", text, re.M))
    return text[:headings[1].start()], text[headings[1].start():]


def links(path: Path, text: str) -> list[dict]:
    result = []
    for target in re.findall(r"!?\[[^\]]*\]\(([^\)]+)\)", text):
        target = target.strip().removeprefix("<").removesuffix(">")
        if re.match(r"(?:[a-zA-Z][a-zA-Z0-9+.-]*:|#)", target):
            continue
        clean = unquote(target.split("#")[0].split("?")[0])
        resolved = (path.parent / clean).resolve()
        result.append({"from": str(path.relative_to(ROOT)), "target": target,
                       "resolved": str(resolved), "exists": resolved.exists()})
    return result


def main() -> None:
    checks = []

    def check(name: str, value: bool) -> None:
        checks.append({"name": name, "passed": bool(value)})
        assert value, name

    archive_path = BASE / "before-entry-update/manifest.json"
    archive = json.loads(archive_path.read_bytes())
    check("exactly fifteen entry snapshots", len(archive["inputs"]) == 15)
    entry_paths = [ROOT / item["path"] for item in archive["inputs"]]
    entry_paths.append(ROOT / "docs/m4-ai-simulated-current.md")
    frozen_at_start = {str(path.relative_to(ROOT)): bind(path) for path in entry_paths}
    current_snapshots = []
    histories = []
    document_links = []
    headers = []
    diffs = []
    cn_headers = []
    en_headers = []
    old_phrase = "以下命令和“当前包”措辞只记录 D60 的冻结时点。现在该包应被 verify 拒绝为 stale；不要按本节对 DuFX 执行 assign/serve/collect，也不要覆盖旧包。若开展 DuFX 真人研究，必须先在新路径另行 prepare/verify；本轮未执行这项准备。"
    corrected_phrase = "以下命令和“当前包”措辞只记录 D60 的冻结时点。该包现被 verify 拒绝为 stale；不要按本节对后续构建执行 assign/serve/collect，也不要覆盖旧包。旧 DuFX 入口冻结时尚未新准备；此后 DuFX/CC91 包先后准备并因实现变化失效，现行 B_XH 准备见上方，真人仍为 0。"
    notice = "\n> 历史 DuFX 阶段记录：下方“当前/本轮/最终”只指此文冻结时点。后续三角色 AI 测试、修复、DuFX 性能诊断和新研究包见 [最新阶段](m4-ai-simulated-current.md)及 [当前门状态](evidence/m4-current-gate-audit.json)。现行为 B_XH、347/347；旧证据与本篇事实不改写为新构建认证。\n"
    for item in archive["inputs"]:
        old_raw = (ROOT / item["snapshot"]).read_bytes()
        check("archived original bytes " + item["path"], len(old_raw) == item["bytes"] and sha(old_raw) == item["sha256"])
        old = old_raw.decode()
        current_path = ROOT / item["path"]
        current_raw = current_path.read_bytes()
        current = current_raw.decode()
        target = HERE / "current-inputs-attempt-2" / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as file:
            file.write(current_raw)
        current_snapshots.append({**bind(current_path), "snapshot": str(target.relative_to(ROOT))})
        diffs.append({"path": item["path"], "unifiedDiff": "".join(difflib.unified_diff(old.splitlines(keepends=True), current.splitlines(keepends=True), fromfile=item["snapshot"], tofile=item["path"]))})
        if current_path.suffix == ".json":
            continue
        document_links.extend(links(current_path, current))
        if item["path"] == "docs/m4-draft-port-legibility.md":
            check("port stage only historical notice added", current.count(notice) == 1 and current.replace(notice, "", 1) == old)
            histories.append({"path": item["path"], "preservation": "exact original bytes after removing one new historical notice"})
            continue
        header, body = sections(current)
        old_header, old_body = sections(old)
        check("intro title unchanged " + item["path"], current.splitlines()[0] == old.splitlines()[0])
        normalized_header = re.sub(r"(!?\[[^\]]*\])\([^\)]+\)", r"\1", header)
        (en_headers if item["path"].startswith("skills/") else cn_headers).append(normalized_header)
        for text in ["index-B_XHk-wz.js", "index--unhoRTb.css", "347/347", "100", "273/273", "43451–43455", "DuFX", "CC91"]:
            check("current header field " + item["path"] + " " + text, text in header)
        if item["path"].startswith("skills/"):
            check("English bounded header " + item["path"], all(value in header for value in ["three AI", "partial", "not_started", "humans 0", "AI is not a human participant", "final B_XH performance is unmeasured", "Historical failures and stale images remain", "17 base kinds and 3 transparent starts"]))
        else:
            check("Chinese bounded header " + item["path"], all(value in header for value in ["3 个 AI", "partial", "not_started", "真人 0", "AI 不计真人", "最终 B_XH 未测性能", "本轮未执行生成模型", "历史滞后/失败保留", "17 基础模块＋3 透明网络起点"]))
        if item["path"] == "docs/m4-research-protocol.md":
            check("protocol single historical context correction", old_body.count(old_phrase) == 1 and current.count(corrected_phrase) == 1 and old_body.replace(old_phrase, corrected_phrase) == body)
            check("protocol current verify exact command", ".venv/bin/python scripts/research_trial.py verify --package .archcanvas/m4-research-trial-bxh-current" in header and "准备不是研究验收" in header and "下方 D60 命令保留历史原貌，不能用于当前 B_XH 席位" in header)
            histories.append({"path": item["path"], "preservation": "exact nonheader historical body except one explicitly scoped stale/preparation context correction", "before": old_phrase, "after": corrected_phrase})
        else:
            check("history exact beyond current header " + item["path"], old_body == body)
            histories.append({"path": item["path"], "preservation": "exact historical body beyond replaced current header", "historicalBodySha256": sha(body.encode())})
        headers.append({"path": item["path"], "sha256": sha(header.encode())})
    check("thirteen current entry headers", len(headers) == 13 and len(cn_headers) == 10 and len(en_headers) == 3)
    # First-level titles differ; compare from the current heading, and research
    # adds an exact current verify block. This checks shared prose independently.
    common_cn = [value[value.index("## 当前状态"):].split("### 当前 B_XH 包")[0].rstrip() for value in cn_headers]
    visual_intro = "Use this reference for figure creation, visual refinement, expansion, and export. These are acceptance contracts for a compatible Studio, not assertions that every installed runtime supports them. Check operations before invoking them."
    check("visual reference preserved old introductory contract", en_headers[2].rstrip().endswith(visual_intro) and visual_intro in (ROOT / "docs/evidence/m4-ai-simulated-current/before-entry-update/inputs/skills/archcanvas/references/visual-workflow.md").read_text())
    common_en = [value[value.index("## Current formal checkout"):].split(visual_intro)[0].rstrip() for value in en_headers]
    check("ten Chinese header common prose matches", len(set(common_cn)) == 1)
    check("three English headers match", len(set(common_en)) == 1)

    stage_path = ROOT / "docs/m4-ai-simulated-current.md"
    stage = stage_path.read_text()
    snapshot = HERE / "current-inputs-attempt-2/docs/m4-ai-simulated-current.md"
    with snapshot.open("xb") as file:
        file.write(stage_path.read_bytes())
    current_snapshots.append({**bind(stage_path), "snapshot": str(snapshot.relative_to(ROOT))})
    document_links.extend(links(stage_path, stage))
    for value in ["3 个 AI 角色", "AI 不计真人", "347/347", "103 个绑定", "5 项新增回归包含在 347 项内", "原始测试绑定 **DuFX**", "不能改称最终 B_XH", "未逐种完成生成/执行", "本轮未新增模块种类", "未执行生成模型", "not-performed", "错误 oracle", "strict 失败", "自动审批拒绝", "最终 B_XH 无性能采样", "273/273", "真人 0", "19 个旧包共 325 文件", "85/180 mm"]:
        check("stage bounded statement " + value, value in stage)
    check("all local Markdown links exist", all(item["exists"] for item in document_links))

    gate = load("docs/evidence/m4-current-gate-audit.json")
    old_gate = load("docs/evidence/m4-ai-simulated-current/before-entry-update/inputs/docs/evidence/m4-current-gate-audit.json")
    receipt = load("docs/evidence/m4-ai-simulated-current/checks-final-attempt-3/receipt.json")
    source_build = receipt["inputs"] + receipt["build"]
    check("gate stage/human boundary", gate["overall"] == "partial" and gate["m5"] == "not_started" and gate["humanParticipants"] == 0)
    check("strict final347 receipt matches gate", receipt["studioTests"] == gate["build"]["studioTests"] == 347 and receipt["skipped"] == gate["build"]["skipped"] == 0 and receipt["focusedTests"] == gate["build"]["focusedTests"] == 5 and receipt["countsAreOverlapping"] and gate["build"]["focusedTestsAreSubset"] and all(item["exitCode"] == 0 for item in receipt["checks"]))
    check("final asset and binding inventory", gate["build"]["js"] == "index-B_XHk-wz.js" and gate["build"]["css"] == "index--unhoRTb.css" and len(receipt["inputs"]) == gate["build"]["sourceTestConfigBindings"] == 100 and len(receipt["build"]) == gate["build"]["distBindings"] == 3 and len(source_build) == 103)
    for item in source_build:
        check("current strict binding exact " + item["path"], bind(ROOT / item["path"]) == {key: item[key] for key in ["path", "bytes", "sha256"]})
    reqs = {item["id"]: item for item in gate["requirements"]}
    old_reqs = {item["id"]: item for item in old_gate["requirements"]}
    for key in ["base-models", "semantic-holdout", "shared-repeat-opaque"]:
        check("earlier static gate unchanged " + key, reqs[key] == old_reqs[key])
    check("open human/publication/performance gates", reqs["research-task"]["status"] == reqs["publication-review"]["status"] == "not_done" and reqs["browser-performance"]["status"] == "failed_or_unverified")
    check("historical performance fields preserved", all(reqs["browser-performance"][key] == old_reqs["browser-performance"][key] for key in ["observedHistorical", "observedPreviousThbumDiagnostic", "observedHistoricalD60NativeSmoke"]))
    gate_links = [{"path": path, "exists": (ROOT / path).is_file()} for requirement in gate["requirements"] for path in requirement["evidence"]]
    check("all gate evidence links exist", all(item["exists"] for item in gate_links))
    check("three AI roles do not count as people", gate["aiSimulatedRoles"]["count"] == 3 and gate["aiSimulatedRoles"]["humanParticipants"] == 0 and gate["aiSimulatedRoles"]["initialBrowserBuild"] == "index-DuFXKOwG.js" and gate["aiSimulatedRoles"]["finalTargetedReadbackBuild"] == "index-B_XHk-wz.js")

    research = load("docs/evidence/m4-ai-simulated-current/research-final-preparation/report.json")
    ready = load("docs/evidence/m4-ai-simulated-current/research-final-preparation/readiness-report.json")
    package = ROOT / gate["currentResearchPackage"]["path"]
    package_manifest = json.loads((package / "manifest.json").read_bytes())
    check("current research package hash", sha((package / "manifest.json").read_bytes()) == gate["currentResearchPackage"]["manifestSha256"] == research["packageManifest"]["sha256"] == "61ac9fbb61d26d1dd6b68bc0873955a3ec467bd2988b2e927e22f0a299162cdf")
    check("research path and five unassigned slots", research["package"] == gate["currentResearchPackage"]["path"] == ".archcanvas/m4-research-trial-bxh-current" and package_manifest["state"] == "prepared-no-participants" and package_manifest["researcherCount"] == 0 and len(package_manifest["slots"]) == 5 and all(slot["assignment"] == "unassigned" and slot["participantCode"] is None for slot in package_manifest["slots"]))
    check("research registered ports are not services", gate["currentResearchPackage"]["registeredPorts"] == [slot["port"] for slot in package_manifest["slots"]] == list(range(43451, 43456)) and not gate["currentResearchPackage"]["servicesStarted"] and not gate["currentResearchPackage"]["portsAvailabilityChecked"])
    check("273readiness not human success", ready["passed"] == ready["total"] == 273 and gate["currentResearchPackage"]["independentReadiness"] == {"passed": 273, "total": 273} and all(ready["boundaries"][key] == 0 for key in ["assigned", "collected", "researchers"]) and ready["boundaries"]["preparationIsNotHumanAcceptance"] and not ready["boundaries"]["modelExecuted"] and not ready["boundaries"]["humanPublicationReviewed"])
    for item in package_manifest["implementationFiles"]:
        check("research frozen implementation exact " + item["path"], bind(ROOT / item["path"]) == item)
    check("frozen new package17files exact", inventory(package) == ready["packageFilesBeforeAfter"])
    preflight = load("docs/evidence/m4-ai-simulated-current/research-final-preparation/preflight.json")
    for path, old_files in preflight["oldResearchPackages"].items():
        check("old research package preserved " + path, inventory(ROOT / path) == old_files)
    check("19oldpackages325files retained", len(preflight["oldResearchPackages"]) == 19 and sum(len(value) for value in preflight["oldResearchPackages"].values()) == 325)
    check("current stale package metadata matches independent preparation", gate["historicalResearchPackagesNowStale"] == research["oldCurrentPackagesNowStale"])
    final_verify = load("docs/evidence/m4-ai-simulated-current/research-final-preparation/verify-final.stdout.json")
    final_process = load("docs/evidence/m4-ai-simulated-current/research-final-preparation/verify-final.process.json")
    check("documented verify matches executed successful verify", final_process["exitCode"] == 0 and final_process["argv"] == [".venv/bin/python", "scripts/research_trial.py", "verify", "--package", ".archcanvas/m4-research-trial-bxh-current"] and final_verify["baselineAndImplementationUnchanged"] and final_verify["researchGate"] == "not_evaluated")
    check("old CC91 and DuFX refusals retained", all(load("docs/evidence/m4-ai-simulated-current/research-final-preparation/old-" + kind + "-stale.process.json")["exitCode"] == 1 and b"Formal implementation changed after preparation" in (BASE / ("research-final-preparation/old-" + kind + "-stale.stderr.txt")).read_bytes() for kind in ["cc91", "dufx"]))

    evidence_manifests = []
    for name in ["novice/manifest.json", "gestures/manifest.json", "catalog-visual/manifest.json", "browser-fixes/manifest.json", "catalog-followup/manifest.json", "zoom-followup/manifest.json", "fix-independent/final-manifest.json", "final-browser/manifest.json", "novice-followup/manifest.json", "research-final-preparation/manifest.json"]:
        manifest_path = BASE / name
        value = json.loads(manifest_path.read_bytes())
        artifacts = value.get("files", value.get("artifacts", []))
        for item in artifacts:
            path = manifest_path.parent / item["path"]
            check("retained evidence bytes " + str(path.relative_to(ROOT)), path.is_file() and len(path.read_bytes()) == item["bytes"] and sha(path.read_bytes()) == item["sha256"])
        evidence_manifests.append({"manifest": bind(manifest_path), "artifactsExact": len(artifacts)})
    failed_receipt = load("docs/evidence/m4-ai-simulated-current/checks-attempt-1/receipt.json")
    check("failed strict build retained", any(item["label"] == "strict-build" and item["exitCode"] != 0 for item in failed_receipt["checks"]) and (BASE / "checks-attempt-1/strict-build.txt").is_file())
    followup = load("docs/evidence/m4-ai-simulated-current/novice-followup/not-performed.json")
    check("unavailable novice followup still not performed", followup["humanParticipants"] == 0 and "not" in json.dumps(followup).lower())
    check("stale image counts retained", len(load("docs/evidence/m4-ai-simulated-current/catalog-followup/pixel-review.json")["mismatch"]) == 4 and load("docs/evidence/m4-ai-simulated-current/zoom-followup/independent-pixel-review.json")["counts"]["mismatchPreviousFrame"] == 2)
    check("failed independent oracle attempts retained", len(load("docs/evidence/m4-ai-simulated-current/fix-independent/final-static-receipt.json")["preservedFailedAttempts"]) == 2)
    check("all current entries unchanged during read-only audit", all(bind(ROOT / path) == original for path, original in frozen_at_start.items()))
    report = {"createdUtc": datetime.now(timezone.utc).isoformat(), "status": "passed-independent-current-document-and-history-readback",
              "reviewer": "AI independent document auditor; not human research/publication reviewer", "findings": [],
              "currentBuild": {"js": gate["build"]["js"], "css": gate["build"]["css"], "studioTests": 347, "sourceBuildBindingsExact": 103},
              "entrySnapshotsExact": 15, "currentReadbackFiles": 16, "currentHeaders": 13,
              "historyPreservation": histories, "currentSnapshots": current_snapshots,
              "markdownLinks": {"total": len(document_links), "allExist": True, "links": document_links},
              "gateEvidenceLinks": gate_links, "retainedEvidenceManifests": evidence_manifests,
              "checks": checks, "passed": len(checks), "total": len(checks), "newProductTestsRun": 0,
              "research": {"package": str(package.relative_to(ROOT)), "manifestSha256": sha((package / "manifest.json").read_bytes()), "readiness": "273/273 frozen readiness only", "humans": 0, "oldPackagesExact": 19, "oldPackageFilesExact": 325},
              "historicalReceiptQualification": "implementation-report.json freshResearchPackage=pending exact final package path is its preparation-before timestamp scope, preserved verbatim; latest gate/protocol/preparation report provide current fresh package. Earlier DuFX/CC91 receipts and removed current gate wording remain in archived bytes and dedicated historical stage.",
              "limits": ["No browser/pixel re-review, product test, model execution, service/assign/collect or dependency installation was performed.", "Link checks confirm target existence, not Markdown anchor semantics or external network availability.", "Local bytes/receipts support preservation; approval rejection history belongs to root tool history and was not independently replayed or certified here.", "AI roles, static/geometry assertions and273readiness do not satisfy human tasks, publication review or presented performance gates."],
              "m4": "partial", "m5": "not_started", "humans": 0}
    for name, value in [("report.json", report), ("entry-diffs.json", diffs)]:
        with (HERE / name).open("x") as file:
            file.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "passed": len(checks), "currentHeaders": 13, "markdownLinks": len(document_links), "gateLinks": len(gate_links), "findings": [], "sourceBuildBindingsExact": 103}, ensure_ascii=False))


if __name__ == "__main__":
    main()
