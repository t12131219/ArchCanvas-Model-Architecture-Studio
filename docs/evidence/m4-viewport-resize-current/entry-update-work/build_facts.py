"""Assemble source-bound resize-stage documentation; final browser facts are external.

Without --final-inputs this produces a preview-only draft. The final input must
name frozen browser/material readbacks, their bounded findings and limitations.
No product source, old evidence, package or documentation entry is edited here.
"""
from argparse import ArgumentParser
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREFIX = "docs/evidence/m4-viewport-resize-current"
STAGE = "docs/m4-viewport-resize.md"


def read(path):
    return json.loads((ROOT / path).read_bytes())


def bind(path):
    raw = (ROOT / path).read_bytes()
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--final-inputs")
    args = parser.parse_args()
    assert not (ROOT / args.output).exists(), "Retain all draft/final attempts"
    old = read(PREFIX + "/entry-update-work/before-entry-inputs/docs/evidence/m4-current-gate-audit.json")
    checks_path = PREFIX + "/checks-final-attempt-2/receipt.json"
    checks = read(checks_path)
    assert checks["inputsUnchanged"] and checks["publicationInputsUnchanged"]
    assert [len(checks[k]) for k in ["inputs", "build", "publicationInputs"]] == [112, 3, 11]
    assert all(item["exitCode"] == 0 for item in checks["checks"])
    for item in checks["inputs"] + checks["build"] + checks["publicationInputs"]:
        assert bind(item["path"]) == {k: item[k] for k in ["path", "bytes", "sha256"]}
    readiness_path = PREFIX + "/research-readiness-independent/report.json"
    readiness = read(readiness_path)
    assert readiness["independentReadiness"] == {"passed": 308, "total": 308, "source": PREFIX + "/research-readiness-independent/readiness-report.json"}
    final = read(args.final_inputs) if args.final_inputs else None
    evidence = [checks_path, PREFIX + "/before-change/manifest.json", PREFIX + "/implementation-work/report.json",
                PREFIX + "/implementation-work/manifest.json", PREFIX + "/implementation-work/focused-attempt-4/receipt.json",
                readiness_path, PREFIX + "/research-readiness-independent/manifest.json",
                PREFIX + "/research-final-preparation/prior-package-verify.process.json",
                "docs/evidence/m4-readable-grid-next-work/manifest.json",
                "docs/evidence/m4-readable-grid-next-work/independent-report-attempt-2.json"]
    if final:
        assert final["status"] == "final_browser_material_facts_ready"
        assert final["js"] == "index-_KAUBMcR.js" and final["css"] == "index--unhoRTb.css"
        assert final["humanParticipants"] == 0 and final["m4"] == "partial" and final["m5"] == "not_started"
        assert final["browserEvidence"] and final["materialEvidence"] and final["publicationEvidence"]
        evidence += final["browserEvidence"] + final["materialEvidence"] + final["publicationEvidence"] + [args.final_inputs]
    evidence = list(dict.fromkeys(evidence))
    bindings = [bind(path) for path in evidence]
    gate = deepcopy(old)
    gate.update({"schema": "archcanvas-m4-current-gate-audit/7", "updated": "2026-10-06",
                 "currentStage": STAGE, "currentEntryPreChangeArchive": PREFIX + "/entry-update-work/before-entry-manifest.json",
                 "currentVisualApproval": "not_approved_existing_display_port_route_discontinuity",
                 "historicalCaptionStabilityGate": old})
    gate["build"] = {"js": "index-_KAUBMcR.js", "css": "index--unhoRTb.css", "checks": checks_path,
                     "studioTests": 430, "skipped": 0, "cancelled": 0, "strictBuildExitCode": 0,
                     "publicationTests": 11, "publicationSkipped": 0, "sourceTestConfigBindings": 112,
                     "distBindings": 3, "totalSourceBuildBindings": 115, "publicationInputBindings": 11,
                     "helperFrozenTransitiveCoreInputsSeparate": 18, "focusedSuiteCountsAreOverlapping": True,
                     "scope": "Frozen KAUB source/build bytes only; later edits are not certified. 112 is not a complete transitive inventory; 18 historical test core files remain separately frozen."}
    gate["historicalCaptionStabilityBuild"] = old["build"]
    previous_package = deepcopy(old["currentResearchPackage"])
    previous_package["currentVerification"] = "stale"
    previous_package["officialStaleReceipt"] = PREFIX + "/research-final-preparation/prior-package-verify.process.json"
    gate["historicalCaptionStabilityResearchPackage"] = previous_package
    gate["currentResearchPackage"] = {"path": readiness["package"], "manifestSha256": readiness["packageManifestSha256"],
                                     "pristineSlots": 5, "assigned": 0, "collected": 0, "humans": 0,
                                     "registeredPorts": list(range(43621, 43626)), "servicesStarted": False,
                                     "portsAvailabilityChecked": False, "currentVerification": "prepared_and_verified",
                                     "officialVerifyExitCode": 0, "independentReadiness": {"passed": 308, "total": 308},
                                     "implementationBindings": 86, "baselineBindings": 4, "oldPackagesPreserved": 24,
                                     "oldPackageFilesPreserved": 410, "preparationReport": readiness_path,
                                     "scope": "Frozen KAUB readiness at preparation only. No assignment, collection, service, availability check or humans; later source/build edits require a fresh package."}
    req = {item["id"]: item for item in gate["requirements"]}
    for requirement, prior, historical in [
        ("visual-authoring", "observedCurrentCaptionStabilityCamera", "observedHistoricalCaptionStabilityCamera"),
        ("browser-performance", "observedCurrentCaptionStability", "observedHistoricalCaptionStability"),
        ("publication-review", "observedCurrentCaptionStabilityExportPreflight", "observedHistoricalCaptionStabilityExportPreflight"),
    ]:
        req[requirement][historical] = req[requirement].pop(prior)
    req["visual-authoring"]["evidence"] += [STAGE, PREFIX + "/implementation-work/report.json", checks_path]
    req["visual-authoring"]["scope"] = "KAUB viewport resize coordination preserves world centre/zoom while idle and protects active coordinate mapping. Actual-App callback/observer effect harness45/45 is not mounted React or browser paint proof. Global routes and dy14→15 discontinuity remain open. " + (final["visualGateScope"] if final else "Final CUA browser/material audit pending; no final browser certification in this draft.")
    req["browser-performance"]["evidence"] += ["docs/evidence/m4-readable-grid-next-work/manifest.json", "docs/evidence/m4-readable-grid-next-work/independent-report-attempt-2.json", STAGE]
    req["browser-performance"]["scope"] = "No KAUB presented/performance gate certification. Typed output move shrinks frozen300-leaf workload bounds to4588x1952 with658/658 finite document/geometry relations; default672x711 nominal font1.632CSSpx is unreadable. Large viewport projections are preparation, not browser/font/readability/timing proof. Historical BTw metrics retain original version scope."
    req["browser-performance"]["observedCurrentViewportResize"] = {"build": "index-_KAUBMcR.js", "newTimingSample": False, "performanceGatePassed": False, "presentedFpsCertified": False, "gridBrowserReadabilityCertified": False}
    req["research-task"]["evidence"] += [readiness_path, PREFIX + "/research-readiness-independent/manifest.json", PREFIX + "/research-final-preparation/prior-package-verify.process.json", STAGE]
    req["research-task"]["scope"] = "Fresh KAUB package prepare/verify0 and308/308 independent readiness:86implementation4baseline5pristine slots43621–43625. All24old packages410files exact; prior caption package actual verify exit1 stale. No services, port availability check, assignment, collection or humans. Three historical AI roles cannot meet real3–5researcher/five-step/180seconds/80percent acceptance."
    req["publication-review"]["evidence"].append(STAGE)
    req["publication-review"]["scope"] = final["publicationGateScope"] if final else "Final current KAUB actual UI publication artifact readback is pending. Prior CXutz4Vh revision31 UI exports669/669 remain frozen historical evidence. No actual85 artifact, resolved fonts/embedding, physical review or global routing approval."
    if final:
        req["visual-authoring"]["evidence"] += final["browserEvidence"] + final["materialEvidence"]
        req["publication-review"]["evidence"] += final["publicationEvidence"]
        req["publication-review"]["observedCurrentViewportResizeExportPreflight"] = final["publicationGateFacts"]
        gate["currentViewportResizeBrowser"] = final["browserGateFacts"]
    else:
        gate["currentViewportResizeBrowser"] = {"status": "awaiting_final_browser_and_material_evidence"}
    gate["decision"] = "M4 remains partial and active; viewport coordination, finite automated audits and prepared slots do not close real readable300object/performance, global route aesthetics, researcher task or physical publication gates. M5 not_started, humans0."
    browser_cn = final["browserHeaderCn"] if final else "最终 CUA 与独立材料审计正在采集，本草案不认证最终版浏览器表现。"
    browser_en = final["browserHeaderEn"] if final else "Final CUA and independent material audit are pending; this draft certifies no final browser behavior."
    publication_cn = final["publicationHeaderCn"] if final else "当前KAUB实际UI导出读回待完成；旧CXutz4Vh revision31导出669/669只作原build历史证据，未认证85/180mm人审。"
    publication_en = final["publicationHeaderEn"] if final else "Current KAUB actual UI export readback is pending; prior CXutz4Vh revision31 exports669/669 remain historical evidence only. No85/180mm human approval."
    cn = """## 当前状态：视口尺寸与相机坐标协调（2026-10-06）

本阶段绑定 `index-_KAUBMcR.js` / `index--unhoRTb.css`。Studio **430/430**、fail/skip/cancel 0，strict TypeScript/Vite exit 0；publication **11/11**、skip 0。[统一收据]({{checks}})为 112 源码/测试/配置＋3 dist＝**115**，另 11 publication 输入；18 份兼容测试历史 core 单独冻结，112 不是全部传递依赖清单。见[阶段]({{stage}})、[门状态]({{gate}})与[143 项源码变更前归档]({{before}})。只认证对应冻结字节。

新增 live ResizeObserver，在空闲视口变大或变小时保持世界中心和 zoom；相机持久化沿用已协调的坐标框尺寸。active pan、对象拖动、框选与端口输入保留原坐标映射，终止/取消后再协调。有限初始化等待可在可用视口/重新挂载时续行，旧 load/intent 不能覆盖新操作。focused45/45包含21项新增 resize 测试，是实际 App callback/effect harness，未挂载 React，不证明浏览器 paint 或初始零闪动。窗口 fallback 不能感知所有内部元素改尺寸。

BROWSER_CN

[可读300对象准备]({{grid}})用一条 typed output move 将冻结 workload bounds 从4588×30542缩到4588×1952；658/658是有限 document/中心线路径关系。300叶身份/事实与canonical保持，默认672×711名义字号仍仅1.632 CSSpx；大视口9.362/10.495px只是投影计算，未认证实际字体/可读性/完整连续输入性能。rAF 不是实际呈现 FPS，固定硬件/字体 A/B×3、≤50ms连续输入、medium p95<500ms、pins/anchor及presented≥50FPS仍开放。

memory默认名与原路由保持上一阶段范围；dy14→15 display端口仍令路线49→644.3世界单位，全域交叉/弯折美观未通过。PUBLICATION_CN 左库仍17基础模块＋3透明网络起点，未逐种生成/执行认证；历史三个AI角色范围保持，审计者不增参与者，AI 不计真人。

M4 `partial`、M5 `not_started`、真人 0。[新研究准备]({{research}})308/308仅readiness：86 implementation/4 baseline、五个pristine席位43621–43625；旧24包410文件exact，上一caption包正式verify已exit1 stale。未开席位服务/查端口可用性/分配/collect；3–5真人五步任务≤180秒/≥80%与出版人审尚未完成。旧gold、失败、研究包与第二个`##`起历史正文原字节保留。正式工程从头实现、独立于Temp runtime/fallback、无新认证复用，未执行生成模型。下方旧“当前/最终”只按各自冻结版本读取。
""".replace("BROWSER_CN", browser_cn).replace("PUBLICATION_CN", publication_cn)
    en = """## Current viewport and camera coordination evidence (2026-10-06)

This stage binds `index-_KAUBMcR.js` / `index--unhoRTb.css`: Studio **430/430**, zero failures/skips/cancellations; strict TypeScript/Vite exit0; publication **11/11**, zero skips. The [receipt]({{checks}}) binds112source/test/config plus3dist=**115**, with11publication inputs separately. Eighteen historical compatibility core files are frozen separately;112 is not a full transitive inventory. See the [stage]({{stage}}),[gate]({{gate}}) and[143 before-change source bindings]({{before}}). Later bytes do not inherit these results.

Live ResizeObserver keeps idle world centre/zoom and persists using an established coordinate-frame size. Active pan/move/box/port input keeps its original mapping until terminal/cancel coordination. Bounded initialization can resume on a usable viewport/remount; stale load/intent work cannot override new actions. Focused45/45 includes21new resize tests but executes actual App callback/effect source in a controlled harness, not mounted React or browser paint; no zero initial-load flicker claim. Window fallback misses arbitrary internal element resizing.

BROWSER_EN

[300-object workload preparation]({{grid}}) uses one typed output move to shrink frozen bounds4588x30542→4588x1952. Its658/658 finite document/centreline relations preserve300leaf identities/facts/canonical bindings. Default672x711 nominal font1.632CSSpx remains too small; larger9.362/10.495px projections are not real fonts/readability or timed browser acceptance. rAF is not presented FPS. Continuous input≤50ms,medium p95<500ms,pins/anchor,fixed hardware/fonts A/Bx3 and presented≥50FPS remain open.

Prior default memory naming remains; dy14→15display endpoints still change route49→644.3world units. No global route/aesthetic approval. PUBLICATION_EN The catalog remains17base kinds plus3transparent starts, without per-kind generation/execution certification. Three historical AI roles retain their original build scope; auditors add no participants. AI is not a human participant.

M4`partial`,M5`not_started`,humans 0. [Fresh research readiness]({{research}})308/308 covers86implementation4baseline and5pristine seats43621–43625. Old24packages410files exact; prior caption package official verification exit1 stale is retained. No slot services,port availability checks,assignment or collection. Real3–5researcher five-step≤180seconds/≥80percent and publication reviews remain unfulfilled. Old gold/failures/packages and history from the second`##` are exact. The formal project remains independent of Temp runtime/fallback; no new reused candidate is certified and no generated model was executed.
""".replace("BROWSER_EN", browser_en).replace("PUBLICATION_EN", publication_en)
    browser_stage = final["browserStageMarkdown"] if final else "最终版真实 CUA resize、gesture、remount 与 save/reopen证据仍在采集；以下草案不把 callback 测试计为原生事件或绘制认证。"
    material_stage = final["materialStageMarkdown"] if final else "最终独立材料审计待落盘；本草案仅验证当前收据112＋3＋11共126绑定exact。"
    publication_stage = final["publicationStageMarkdown"] if final else "当前KAUB实际UI导出读回待完成；旧CXutz4Vh实际revision31整图180mmPDF/SVG与detailSVG的669/669是历史导出关系，最低整图6.56018pt/detail7.41862pt；85计算3.09786pt没有actual85工件。不认证新导出或人审。"
    stage = """# M4 视口尺寸与相机坐标协调

本轮修复实时视口改变后相机平移仍沿用旧尺寸的问题。正式构建 `index-_KAUBMcR.js` / `index--unhoRTb.css`；[统一收据](evidence/m4-viewport-resize-current/checks-final-attempt-2/receipt.json)为 Studio430/430、fail/skip/cancel0、strict TypeScript/Vite exit0、publication11/11skip0。112源码/测试/配置＋3dist为115条，另11publication输入；兼容测试引用的18历史core独立冻结，112不是完整传递依赖清单。M4partial、M5not_started、真人0。

## 触发与坐标契约

上一CXutz4Vh阶段capture38按883×786重开保持中心(350,405)，第一次回672×711的capture39却留下大视口平移，中心变(244.5,367.5)，再次稳定reload40才恢复。[旧阶段](m4-caption-stability-camera.md)与原失败没有被改为通过。本阶段变更前143项[原字节归档](evidence/m4-viewport-resize-current/before-change/manifest.json)保留旧App/core/tests/publication输入和18历史兼容core。

cameraViewport独立验证可用尺寸，并按宽高差的一半平移相机，保持中心的世界坐标与zoom。App以useLayoutEffect订阅当前实际元素；ResizeObserver交付使用flushSync提交匹配平移。没有ResizeObserver时window resize仅作有限fallback，不能发现所有浏览器窗口未变的内部尺寸改变。

持久化读已建立camera viewport anchor，避免DOM尺寸先变、observer未交付时保存错误中心。相机仍在UI/session状态，独立于CanvasDocument、undo历史、source/IR与publication scene。explicit fit、zoom、focus以及document初始化建立新anchor；旧document/element或load/intent票据不能应用到当前视图。

## 手势与初始化顺序

active pan、对象拖动、框选与port输入保持开始时的坐标映射；pointer终止/取消在实际结果之后协调resize。早于restore的空间手势使用用户当时看到的坐标并取消延迟restore。隐藏或暂时未挂载的初始化在有限frame重试后停止主动排队但保留合法ticket，后来可用observer/重挂载再续行；新显式intent会清pending。

[实现报告](evidence/m4-viewport-resize-current/implementation-work/report.json)与[focused attempt4](evidence/m4-viewport-resize-current/implementation-work/focused-attempt-4/receipt.json)记录45/45、其中21新增resize测试，strict0。测试读取实际App callback和useLayoutEffect本体，使用独立数值期望及正式typed undo断言；未挂载React，不认证真实observer调度、native pointer或paint。首次错误、attempt2/3和最终attempt4均保留；45是430的重叠范围，不能相加。

初始load仍可能先显示默认相机后再完成延迟初始化，本阶段不承诺zero first-frame load flicker。正确性还依赖最终版真实浏览器验证。

## 最终浏览器与材料范围

BROWSER_STAGE

MATERIAL_STAGE

## 可读300对象准备

[独立workload](evidence/m4-readable-grid-next-work/README.md)通过一条已有typed move，把冻结DenseStress300的source-backed output从(80,30346)移到(80,1756)，network保持(80,254)。root自然缩高、bounds从4588×30542缩到4588×1952；304node/302edge身份与300leaf事实保持。revision4→5、output active及两个saved frontiers的layout位移是允许变化；只有edge303路线变短，总中心线长度142405→113815世界单位。

[attempt2](evidence/m4-readable-grid-next-work/independent-report-attempt-2.json)为658/658有限document/hash/中心线关系：无unrelated leaf body穿越、无没有共同端点peer的proper crossing/positive overlap。endpoint相关peer、外框contact、stroke/marker/glyph没有认证。第一attempt655/656因oracle误拒output派生localY而失败，原报告/script/log保留；产品/preparer输出未为此更改。

672×711下300叶完整几何入内但名义13单位字仅1.632CSSpx；3400×1900为9.362px，3800×2100为10.495px，均只是projection。42文件seal冻结26inputs并只绑定其命名历史core，不反向认证当前live renderer。未采browser timing、实际解析字体、硬件/遮挡、continuous输入或presentedFPS，不能关闭300可读对象性能门。

## 研究准备与尚未通过的门

[新研究readiness](evidence/m4-viewport-resize-current/research-readiness-independent/report.json)为`.archcanvas/m4-research-trial-viewport-resize-current`，manifest SHA256`PACKAGE_SHA`，正式venv prepare/verify0。86implementation、4baseline、五pristine席位43621–43625；308/308仅准备关系。24旧包410文件exact，新包17文件未变；上一caption包正式verify实际exit1 stale并保留原包。未查端口可用性、开席位服务、分配或collect，真人0。

左库仍17基础模块＋3透明起点，未逐种生成或执行。历史三AI角色不变，审计者不计新参与者，AI不计真人。3–5真实研究者五步任务≤180秒/≥80%、实际85/180mm出版人审、字体嵌入/塑形、全域route弯折/交叉美观均未闭合。memory默认名已稳定，但dy14→15display端口仍令路线49→644.3世界单位；拒绝候选继续冻结，不以warning记为美观通过。

旧BTw连续输入/medium样本只按原条件读取，rAF不是实际呈现FPS。当前continuous≤50ms、medium p95<500ms、300可读object、pins/anchor、固定硬件/字体A/B×3、presented≥50FPS未认证。

PUBLICATION_STAGE

正式工程从头实现、独立于Temp runtime/fallback，无新认证复用；未执行用户/生成模型、未semantic源码回写。13入口只更新current header，第二个`##`之后历史body exact；旧gold、failures、packages和旧stage原字节保留。后续源码/build变化不能沿用本阶段认证，应保留本包并准备新具名研究包。M4active/partial，M5not_started。
""".replace("BROWSER_STAGE", browser_stage).replace("MATERIAL_STAGE", material_stage).replace("PUBLICATION_STAGE", publication_stage).replace("PACKAGE_SHA", readiness["packageManifestSha256"])
    index = """# Viewport resize evidence index

See the [stage](../../m4-viewport-resize.md) and [gate](../m4-current-gate-audit.json). Final source assets are `index-_KAUBMcR.js` / `index--unhoRTb.css`; [checks](checks-final-attempt-2/receipt.json) bind112source/test/config plus3dist=115 and11separate publication inputs. Studio430/430,strict/build0,publication11/11skip0. Historical compatibility core remains separately frozen. No semantic model writeback, model execution, human acceptance or presented performance certification are inferred from this index.

- [143 pre-change source/publication/core bindings](before-change/manifest.json)
- [Implementation and rejected/retained attempts](implementation-work/report.json)
- [Focused45/45 callback/effect harness](implementation-work/focused-attempt-4/receipt.json), not mounted React or actual browser paint
- [Fresh package independent readiness308/308](research-readiness-independent/report.json), [610-binding seal](research-readiness-independent/manifest.json)
- [Prior caption package stale exit1](research-final-preparation/prior-package-verify.process.json)
- [13-entry original headers/history archive](entry-update-work/before-entry-manifest.json)
- [Compact source-backed300leaf workload preparation](../m4-readable-grid-next-work/README.md), finite658/658 relations only

FINAL_INDEX

M4partial,M5not_started,humans0. Registered research ports43621–43625 were not availability-checked or served; no slot assignment/collection. Historical three AI roles do not replace real participants. Global routing,dy14→15display discontinuity,readable300objects,continuous/medium/pins/anchor/fixed hardware/fonts/presented timing,and85/180mm physical review remain open. Old gold/failures/evidence/packages/history remain original bytes.
""".replace("FINAL_INDEX", final["indexMarkdown"] if final else "Final CUA and independent material artifacts are pending in this preview-only draft.")
    targets = {"checks": checks_path, "before": PREFIX + "/before-change/manifest.json", "research": readiness_path,
               "grid": "docs/evidence/m4-readable-grid-next-work/README.md",
               "camera": PREFIX + "/independent-routing-agent/browser-camera-readback-final/report.json",
               "node": PREFIX + "/independent-routing-agent/browser-node-readback-attempt-4/report.json",
               "export": PREFIX + "/actual-export-readback/independent-attempt-2/report.json"}
    facts = {"schema": "archcanvas-viewport-entry-facts/1", "createdUtc": datetime.now(timezone.utc).isoformat(),
             "status": "final_facts_ready" if final else "draft_browser_material_pending", "buildReceipt": checks_path,
             "evidenceBindings": bindings, "targets": targets, "headers": {"cn": cn, "en": en},
             "newMarkdown": {STAGE: stage, PREFIX + "/README.md": index}, "finalGate": gate}
    (ROOT / args.output).write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": facts["status"], "output": args.output, "evidenceBindings": len(bindings), "finalSourceBindings": 126}))


if __name__ == "__main__":
    main()
