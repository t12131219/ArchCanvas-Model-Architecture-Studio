"""Assemble concise named memory-stage facts; do not mutate current entries here."""
from argparse import ArgumentParser
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREFIX = "docs/evidence/m4-memory-continuity-current"
STAGE = "docs/m4-memory-continuity.md"


def load(path):
    return json.loads((ROOT / path).read_bytes())


def bind(path):
    raw = (ROOT / path).read_bytes()
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--final-inputs")
    args = parser.parse_args()
    assert not (ROOT / args.output).exists(), "Retain all attempts"
    receipt_path = PREFIX + "/checks-final-attempt-2/receipt.json"
    receipt = load(receipt_path)
    assert receipt["inputsUnchanged"] and receipt["publicationInputsUnchanged"]
    assert [len(receipt[k]) for k in ["inputs", "build", "publicationInputs"]] == [115, 3, 11]
    for row in receipt["inputs"] + receipt["build"] + receipt["publicationInputs"]:
        assert bind(row["path"]) == {k: row[k] for k in ["path", "bytes", "sha256"]}
    assert all(row["exitCode"] == 0 for row in receipt["checks"])
    implementation = load(PREFIX + "/implementation-work/report.json")
    assert implementation["checks"]["studio"]["tests"] == implementation["checks"]["studio"]["pass"] == 436
    assert implementation["productionMatrix"]["rows"] == 840 and implementation["productionMatrix"]["passed"] == 14623
    assert implementation["sourceSeal"]["relations"] == implementation["sourceSeal"]["passed"] == 450
    readiness_path = PREFIX + "/research-readiness-independent/report.json"
    readiness = load(readiness_path)
    assert readiness["readiness"] == {"passed": 313, "total": 313}
    old_archive_path = PREFIX + "/entry-update-work/before-entry-inputs/docs/evidence/m4-current-gate-audit.json"
    old = load(old_archive_path)
    final = load(args.final_inputs) if args.final_inputs else None
    if final:
        assert final["status"] == "final_browser_export_facts_ready"
        assert final["js"] == "index-CU5JhnoS.js" and final["m4"] == "partial" and final["m5"] == "not_started" and final["humans"] == 0
        assert final["evidencePaths"]
    evidence = [receipt_path, PREFIX + "/implementation-work/report.json",
                PREFIX + "/implementation-work/final-evidence-manifest.json",
                PREFIX + "/implementation-work/source-seal-attempt-2/report.json",
                PREFIX + "/implementation-work/source-seal-attempt-2/manifest.json",
                PREFIX + "/production-matrix-attempt-2/report.json",
                PREFIX + "/independent-guard-review/summary-final.json",
                PREFIX + "/independent-adopt-review/summary-final.json",
                PREFIX + "/independent-adopt-review/summary-gap.json",
                PREFIX + "/independent-frontier-review/summary-final.json",
                PREFIX + "/independent-frontier-review/summary-generalization.json",
                readiness_path, PREFIX + "/research-readiness-independent/manifest.json",
                "docs/evidence/m4-readable-grid-browser-next/README.md",
                "docs/evidence/m4-readable-grid-browser-next/continuous-browser/independent-readback-attempt-2/README.md"]
    if final:
        evidence += final["evidencePaths"] + [args.final_inputs]
    evidence = list(dict.fromkeys(evidence))
    evidence_bindings = [bind(path) for path in evidence]
    gate = deepcopy(old)
    gate.update({"schema": "archcanvas-m4-current-gate-audit/8", "updated": "2026-10-06", "currentStage": STAGE,
                 "historicalViewportResizeGateArchive": bind(old_archive_path),
                 "currentEntryPreChangeArchive": PREFIX + "/entry-update-work/before-entry-manifest.json",
                 "currentVisualApproval": "bounded_collapsed_memory_projection_accepted_global_visual_quality_unapproved"})
    gate["historicalViewportResizeBuild"] = old["build"]
    gate["build"] = {"js": "index-CU5JhnoS.js", "css": "index--unhoRTb.css", "checks": receipt_path,
                     "studioTests": 436, "skipped": 0, "cancelled": 0, "strictBuildExitCode": 0,
                     "publicationTests": 11, "publicationSkipped": 0, "sourceTestConfigBindings": 115,
                     "distBindings": 3, "totalSourceBuildBindings": 118, "publicationInputBindings": 11,
                     "historicalCoreInputsSeparate": 36, "externalDetailFixtureSeparate": 1,
                     "focusedSuiteCountsAreOverlapping": True,
                     "scope": "Frozen CU5 source/build only.115 is not full transitive inventory; source seal separately binds18precaptioncore,18immediatebeforecore and1externaldetailfixture."}
    historical_package = deepcopy(old["currentResearchPackage"])
    historical_package["currentVerification"] = "stale"
    historical_package["officialStaleReceipt"] = PREFIX + "/research-final-preparation/prior-package-verify.process.json"
    gate["historicalViewportResizeResearchPackage"] = historical_package
    gate["currentResearchPackage"] = {"path": readiness["package"], "manifestSha256": readiness["packageManifestSha256"],
        "pristineSlots": 5, "assigned": 0, "collected": 0, "humans": 0, "registeredPorts": list(range(43631, 43636)),
        "servicesStarted": False, "portsAvailabilityChecked": False, "currentVerification": "prepared_and_verified",
        "officialVerifyExitCode": 0, "independentReadiness": {"passed": 313, "total": 313},
        "implementationBindings": 87, "baselineBindings": 4, "oldPackagesPreserved": 25, "oldPackageFilesPreserved": 427,
        "preparationReport": readiness_path, "scope": "Pristine preparation only; no services/probes/assignment/collection/humans. Later implementation changes require a fresh named package."}
    req = {row["id"]: row for row in gate["requirements"]}
    if "currentViewportResizeBrowser" in gate:
        gate["historicalViewportResizeBrowser"] = gate.pop("currentViewportResizeBrowser")
    for key, field in [("browser-performance", "observedCurrentViewportResize"),
                       ("publication-review", "observedCurrentViewportResizeExportPreflight")]:
        if field in req[key]:
            req[key][field.replace("Current", "Historical")] = req[key].pop(field)
    req["visual-authoring"]["evidence"] += [STAGE, PREFIX + "/implementation-work/report.json", receipt_path]
    req["visual-authoring"]["scope"] = "CU5 bounded collapsed-memory side/midpoint continuity: production840rows14623relations; independent actual140cases18272relations and literal/port guards. Protected canonical facts and nonmemory paths remain exact. Narrow-gap transitions, expanded/retained paths, global masks/routing, resolved glyph/arrowhead pixels and human aesthetics remain open. " + (final["visualGateScope"] if final else "Final browser/export readback pending in this preview.")
    req["visual-authoring"]["observedCurrentMemoryContinuity"] = {"build": "index-CU5JhnoS.js", "productionRows": 840,
        "productionRelations": 14623, "productionAdoptions": 624, "yAdoptions": 576, "gapAdoptions": 48,
        "exampleDy14To15Lengths": [49, 50], "exampleEndpointDisplacements": [1, 0],
        "nineFrontierCases": 216, "nineFrontierRelations": 27716, "nineFrontierAdoptions": 0,
        "nineFrontierRetainedMemoryOccurrences": 168, "expandedEndpointRetainedOccurrences": 72,
        "opaqueSharedCases": 24, "opaqueSharedRelations": 1802, "opaqueSharedHasMemoryEdges": False,
        "globalVisualQualityApproved": False}
    req["browser-performance"]["evidence"] += ["docs/evidence/m4-readable-grid-browser-next/README.md",
        "docs/evidence/m4-readable-grid-browser-next/continuous-browser/independent-readback-attempt-2/README.md", STAGE]
    req["browser-performance"]["scope"] = "No current CU5 performance pass. Historical KAUB large viewport diagnostic has4matched toggle durations280/504/248/520ms,p95520,unrelatedpin0/maxanchor0.0001551px,malformedcollapsedoutputy-28236. Actual304bodies/300leaves geometry inside does not approve small fonts. Continuous readback26/29 retains3real DOM-proxy disagreements; independentpan994.9/drag1716.1/wheel45.2ms are not causal input-to-paint. Fixedfonts/hardwareA/Bx3,readable300,medium,fullpaint,presentedFPS remain open."
    req["browser-performance"]["observedCurrentMemoryContinuity"] = {"build": "index-CU5JhnoS.js", "newNativeTiming": False,
        "performanceGatePassed": False, "presentedFpsCertified": False}
    req["research-task"]["evidence"] += [readiness_path, PREFIX + "/research-final-preparation/prior-package-verify.process.json", STAGE]
    req["research-task"]["scope"] = "Fresh CU5 formalprepare/verify0 plus313/313readiness:87implementation4baseline,5pristine slots43631–43635. Old25packages427filesexact. Prior viewport officialverifyexit1stale. No assignment/collection/services/availability checks,humans0. Historical3AI roles do not satisfy3–5realresearcher/five-step/180seconds/80percent."
    req["publication-review"]["evidence"].append(STAGE)
    req["publication-review"]["scope"] = final["publicationGateScope"] if final else "Current CU5 UI export readback pending; no human publication approval."
    if final:
        req["visual-authoring"]["evidence"] += final["evidencePaths"]
        req["publication-review"]["evidence"] += final["evidencePaths"]
        gate["currentMemoryContinuityBrowser"] = final["browserGateFacts"]
        req["publication-review"]["observedCurrentMemoryContinuityExports"] = final["publicationGateFacts"]
    gate["decision"] = "M4partial, M5not_started,humans0. Bounded memory continuity does not close narrow-gap/expanded/global aesthetics, readable300/performance, researcher or physical publication gates."
    browser_cn = final["browserHeaderCn"] if final else "最终浏览器/导出独立读回待完成，本草案不认证当前UI持久化与工件一致性。"
    browser_en = final["browserHeaderEn"] if final else "Final browser/export readback pending; this draft certifies no current UI persistence/artifact identity."
    cn = """## 当前状态：受限 memory 连线连续性（2026-10-06）

当前 `index-CU5JhnoS.js` / `index--unhoRTb.css` 的[统一收据]({{checks}})为 Studio **436/436**、fail/skip/cancel0，strict TypeScript/Vite exit0、publication **11/11** skip0；115源码/测试/配置＋3dist＝**118**，另11publication输入。36历史core＋1detail夹具单独冻结，115不是完整传递依赖清单。见[阶段]({{stage}})、[门]({{gate}})及[source seal]({{sourceSeal}})。

collapsed memory在完整同场景原route batch完成后，才尝试Repeat轮廓感知的侧边/中点路线；完整fixed/chosen peers、nominal body/header/stroke、端口法向和两段6单位lead均保护，unknown/budget不足保留同场景batch。dy14→15例从49→644.3改善为49→50，端点仅1/0位移；非memory路线/端口与canonical事实保持。840production行14623关系、624adopt（y576/gap48）；实际140case18272独审为有限几何，不等于840模型、全域最少交叉或美观通过。窄gap、expanded/retained route、mask拥挤与字体/arrowhead仍开放。

BROWSER_CN

[原KAUB性能诊断]({{perf}})保留四toggle p95520ms、collapsed output y=-28236缺陷及300小字不批准。[continuous读回]({{continuous}})26/29保留三项真实proxy分歧：独立pan994.9/drag1716.1/wheel45.2ms只是首次DOM变化，非因果input-to-paint。rAF 不是实际呈现 FPS；当前readable300、continuous≤50ms、medium<500ms、固定硬件/字体A/B×3与presented≥50FPS未认证。

M4 `partial`、M5 `not_started`、真人 0。AI 不计真人；历史3AI角色和17基础模块＋3透明起点保持原范围，未逐种生成/执行。[新研究准备]({{research}})313/313仅readiness：87implementation/4baseline，5pristine席位43631–43635；旧25包427文件exact、上一viewport包正式verifyexit1stale。未服务/probe/分配/collect，3–5真人五步≤180秒/≥80%及85/180mm人审开放。13入口第二`##`后历史正文、旧stage/gold/failure/package原字节保留。正式工程从头实现、独立于Temp runtime/fallback，无新认证复用，未执行生成模型；后续字节变化不继承本阶段认证。
""".replace("BROWSER_CN", browser_cn)
    en = """## Current bounded memory route continuity (2026-10-06)

`index-CU5JhnoS.js` / `index--unhoRTb.css` [checks]({{checks}}): Studio **436/436**,0fail/skip/cancel,strict TypeScript/Vite exit0,publication **11/11**0skip.115source/test/config+3dist=**118**,11publication inputs separately;36historicalcore+1detailfixture separately frozen.115 is not complete transitive inventory. See [stage]({{stage}}),[gate]({{gate}}),[source seal]({{sourceSeal}}).

After the complete same-scene route batch, eligible collapsed memory tries Repeat-aware side/midpoint projection against fixed/chosen peers,nominal body/header/stroke,port normals and two6-unit leads. Unknown/budget exhaustion retains that same-scene batch. Exampledy14→15 length49→644.3 becomes49→50,endpoints1/0; nonmemory routes/ports/canonical facts stay exact.840production rows14623relations,624adoptions(y576/gap48);140actualcases18272independent relations are finite geometry,not840models/globalminimalcrossings/aesthetic approval. Narrow gaps,expanded/retained routes,mask congestion,fonts/arrowheads remain open.

BROWSER_EN

[Historical KAUB native diagnostic]({{perf}}) retains4togglep95520ms,collapsedoutputy-28236 defect and unapproved300small text. [Continuous readback]({{continuous}})26/29 retains3realproxy disagreements: independentpan994.9/drag1716.1/wheel45.2ms is firstDOMchange,not causal input-to-paint. rAF is not presented FPS. Currentreadable300,continuous≤50ms,medium<500ms,fixedhardware/fontsA/Bx3 andpresented≥50FPS remain unverified.

M4`partial`,M5`not_started`,humans 0. AI is not a human participant. Historical3AIroles and17basekinds+3transparentstarts retain original scope,no per-kindgeneration/execution. [Fresh readiness]({{research}})313/313:87implementation4baseline,5pristine seats43631–43635;old25packages427filesexact,priorviewportofficialverifyexit1stale. No service/probe/assignment/collection;real3–5researcher five-step≤180seconds/≥80percent and85/180mmphysicalreview remain open. History from second`##`,oldstage/gold/failure/packages remain exact. Formalfrom-scratch implementation is independent ofTemp runtime/fallback,no newreuse certified,and no generated model was executed. Laterbytes do not inherit this evidence.
""".replace("BROWSER_EN", browser_en)
    stage = """# M4 受限 memory 连线连续性

当前CU5JhnoS构建，[统一收据](evidence/m4-memory-continuity-current/checks-final-attempt-2/receipt.json)为Studio436/436、strict/build0、publication11/11skip0。115源码/测试/配置＋3dist为118，另11publication输入；[source seal](evidence/m4-memory-continuity-current/implementation-work/source-seal-attempt-2/report.json)450/450关系绑定129current、166frozen，144prechange copies exact。36历史core和1external detail fixture单列，非完整transitive清单。各审计分母不累加到436产品测试。M4partial、M5not_started、真人0。

## 实现与独立几何范围

[最终实现报告](evidence/m4-memory-continuity-current/implementation-work/report.json)记录：完整当前同场景batch先完成，collapsed effective endpoints有共同vertical band且两段6单位lead时尝试Repeat-aware side/midpoint。完整fixed batch和此前adopted peers保护centerline/contact/span、nominal stroke间距、body/backplate/header、selfcontact/normal与length不增长；unknown、非法或budget耗尽保留同场景batch。此保留不是旧runtime fallback，产品不导入旧core。nonmemory route不重新优化；route与chosen display port coverage原子改变，retained consumers几何保留，canonicalBindings依architecture原序。detail先独立构造original-policy whole及detail完整batch，再late projection，不把已adopted whole route喂回另一次peer优化。

production840行（624y/216gap）、14623/14623关系，adopt624（y576/gap48），96transition pairs；dy14→15典型长度49→644.3变49→50，source/target位移1/0。三个caption模式、paper/mono、85/180、whole/detail、signed/fractional endpoint和gap邻值均有named数据；这不是840model或实际UI导出。

actual source104ycases14528/14528独审，96adopt/8already-identical保留；36gapcases3744/3744，8adopt/28保留，共140cases18272关系。gap12.01/12可adopt、11.99及更小保留，窄gap政策转换仍存在。literal96cases480/480、ports31cases2480/2480＋44currentbinding关系为nominal guard evidence，不认证真实arrowhead/font pixels。

九frontier为同模型9种hierarchy而非9model：216cases27716/27716、memory168保留含72expandedendpoint，adopt0；不能称expanded continuity已修。另三historical source-grounded models×8cases=24cases1802/1802及18sourceassociation关系，opaque16/shared8，但没有memory edges，仅保护这些事实。原gold/oracle未变，窄兼容helper先比protected facts/nonmemory/ports，再独立推midpoint与全部consumer；不把该helper当安全审计。

实际发现并修复missing-budget own keys、detail canonical binding order与no-op projection port ordering；初suite425/430、统一attempt1 423/436、production14203/14623 observer错误、source443/450 git-diff oracle错误、literal/port/summary oracle纠正等原失败完整保留在实现报告。最终输入binding可信只按最终receipt/source seal读取，动态源码期间旧counterexample不反向绑定新hash。

## 真实浏览器与导出

BROWSER_STAGE

## 性能、研究与未完成门

[largeviewport诊断](evidence/m4-readable-grid-browser-next/README.md)绑定历史KAUB，不继承为CU5性能。真实window4096×2700/canvas3599×2506/DPR1，300叶几何入内但title9.9257/subtitle7.6351CSSpx，root仍不批准可靠inventory阅读，字体文件未知。四native toggles4captured/4valid/4matched：280/504/248/520ms、matchedp95520；unrelatedpin位移0、anchor最大0.0001551px。官方validator0只证明一致性，独审353/357四失败保留；共同body全不动期望过强，但collapsed output y=-28236/localy-28328是实际saved-frontier缺陷，expand才恢复。

[continuous独审attempt2](evidence/m4-readable-grid-browser-next/continuous-browser/independent-readback-attempt-2/README.md)26/29保留三真实DOM proxy分歧，首attempt25/29另含float oracle纠正。60trusted received events/60retained/drop0只覆盖声明event types；32coalesced单列，不能称全OSinput。七attempt含失败drag实际handtoolpan、undo/redo撤销恢复pin而非该drag；正确selectiondrag后complete SVG undo exact。wheel结束只128body intersect/84leaf fullyinside，inputpin offscreen。独立pan8movesp95994.9ms、drag8moves1716.1ms、wheel1event45.2ms是首次DOMchange，不是因果paint。Discrete14eligible/13matched、5interactionIDs，matchedsubsetp953024ms；641rAF wholewindow2.623Hz与wheel57.245Hz都不是presentedFPS。Observer成本重叠，未相减。300可读、continuous≤50ms、medium<500ms、pins/anchor完整条件、固定硬件/字体A/B×3与presented≥50FPS仍不通过。

[研究准备](evidence/m4-memory-continuity-current/research-readiness-independent/report.json)正式venv prepare/verify0；newpackage87implementation4baseline5pristine43631–43635，313/313readiness，旧25packages427filesexact。上一viewportpackage实际verifyexit1stale保留。未probe/serve/assign/collect，真人0。历史3AIroles保持原build范围，审计者不增参与者，AI不计真人；17基础模块＋3透明起点未逐种生成/执行认证。3–5真人五步≤180秒/≥80%和85/180mm物理人审未完成。

global masks/routing弯折交叉、窄gap与expanded memory、全部raster freshness/firstpaint、解析字体/embedding均开放。正式工程从头实现、独立于Temp runtime/fallback，无新认证复用，未执行用户/生成模型或semantic源码回写。13current headers第二`##`后历史body、旧stage/gold/failure/package保持原字节；后续源码/dist变更不沿用本stage认证。M4active/partial，M5not_started。
""".replace("BROWSER_STAGE", final["browserStageMarkdown"] if final else "最终root浏览器与export独立读回待落盘，原raw/root观察已经保留，未把当前draft作为通过认证。")
    index = """# Memory continuity evidence

See [stage](../../m4-memory-continuity.md),[gate](../m4-current-gate-audit.json),[final implementation](implementation-work/report.json) and[unified436/436 strict0 publication11/11](checks-final-attempt-2/receipt.json). Source115+dist3=118,publication11 separate;historical36core+1detailfixture separate. [450/450 source seal](implementation-work/source-seal-attempt-2/report.json) and[final evidence manifest](implementation-work/final-evidence-manifest.json) bind named finite evidence,not global acceptance.

[Production840/14623](production-matrix-attempt-2/report.json),[actualy104/14528](independent-adopt-review/summary-final.json),[gap36/3744](independent-adopt-review/summary-gap.json),[ninefrontier216/27716](independent-frontier-review/summary-final.json),[opaque/shared24/1802](independent-frontier-review/summary-generalization.json) and[literal/port guards](independent-guard-review/summary-final.json) retain distinct scope. Ninefrontieradopt0/168retained,opaque/shared hasno memory;retention is not aesthetics success.

FINAL_INDEX

[Research313/313](research-readiness-independent/report.json),[entry originals](entry-update-work/before-entry-manifest.json),[historical native failures](../m4-readable-grid-browser-next/README.md),[continuous26/29](../m4-readable-grid-browser-next/continuous-browser/independent-readback-attempt-2/README.md). M4partial,M5not_started,humans0;global routing/font/pixels/performance/realresearchers/physicalpublication gates remain open. No user/generatedmodel execution or semantic source writeback.
""".replace("FINAL_INDEX", final["indexMarkdown"] if final else "Final browser/export readback pending in this preview.")
    facts = {"schema": "archcanvas-memory-entry-facts/1", "createdUtc": datetime.now(timezone.utc).isoformat(),
        "status": "final_facts_ready" if final else "draft_browser_export_pending", "buildReceipt": receipt_path,
        "evidenceBindings": evidence_bindings, "targets": {"checks": receipt_path,
            "sourceSeal": PREFIX + "/implementation-work/source-seal-attempt-2/report.json",
            "perf": "docs/evidence/m4-readable-grid-browser-next/README.md",
            "continuous": "docs/evidence/m4-readable-grid-browser-next/continuous-browser/independent-readback-attempt-2/README.md",
            "research": readiness_path, **(final["targets"] if final else {})},
        "headers": {"cn": cn, "en": en}, "newMarkdown": {STAGE: stage, PREFIX + "/README.md": index}, "finalGate": gate}
    (ROOT / args.output).write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": facts["status"], "evidenceBindings": len(evidence_bindings), "sourceBindings": 129}))


if __name__ == "__main__":
    main()
