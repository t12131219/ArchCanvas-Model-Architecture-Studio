"""Finalize this stage's reviewed documentation material from sealed receipts."""
from copy import deepcopy
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def load(path):
    return json.loads((ROOT / path).read_bytes())


def main():
    output = HERE / "final-facts.json"
    assert not output.exists(), "Never overwrite an earlier facts file"
    facts = load("docs/evidence/m4-caption-route-current/entry-update-work/draft-facts.json")
    ready = load("docs/evidence/m4-caption-route-current/research-export-final-preparation/report.json")
    browser = load("docs/evidence/m4-caption-route-current/final-browser/receipt.json")
    exports = load("docs/evidence/m4-caption-route-current/browser-export-final/report.json")
    gestures = load("docs/evidence/m4-caption-route-current/browser-gesture-final/report.json")
    gap = load("docs/evidence/m4-caption-route-current/browser-caption-investigation/report.json")
    gate = facts["finalGate"]
    gate["build"]["checks"] = "docs/evidence/m4-caption-route-current/checks-final-attempt-4/receipt.json"
    gate["build"]["publicationTests"] = 11
    gate["historicalFirstCaptionRouteBuild"] = {
        **deepcopy(gate["build"]), "checks": "docs/evidence/m4-caption-route-current/checks-final-attempt-3/receipt.json",
        "publicationTests": 9, "publicationInputsNowStale": True,
        "scope": "Studio/dist bytes unchanged; publication exporter/test changed after actual UI rejection. Keep attempt3 frozen; current full unified receipt is attempt4.",
    }
    gate["historicalFirstCaptionRouteResearchPackage"] = {
        **deepcopy(gate["currentResearchPackage"]), "currentVerification": "stale",
        "officialStaleRefusal": ready["oldFirstCaptionRoutePackageNowStale"],
        "scope": "First caption-route package remains exact but official verify refuses changed publication exporter. 295 frozen readiness does not apply to current publication inputs.",
    }
    gate["currentResearchPackage"] = {
        "path": ready["package"], "manifestSha256": ready["packageManifest"]["sha256"],
        "pristineSlots": 5, "assigned": 0, "collected": 0, "humans": 0,
        "registeredPorts": ready["readiness"]["portsRegistered"],
        "servicesStarted": False, "portsAvailabilityChecked": False,
        "currentVerification": "prepared_and_verified",
        "independentReadiness": ready["currentBuild"]["independentReadiness"],
        "implementationBindings": 84, "baselineBindings": 4,
        "preparationReport": "docs/evidence/m4-caption-route-current/research-export-final-preparation/report.json",
        "oldPackagesPreserved": 22, "oldPackageFilesPreserved": 376,
        "scope": "Frozen preparation/pristine readiness only; no browser task, human participants, service, assignment or collection. Registered ports not checked for availability.",
    }
    gate["currentVisualApproval"] = "not_approved_existing_memory_label_movement_gap"
    reqs = {item["id"]: item for item in gate["requirements"]}
    visual = reqs["visual-authoring"]
    visual["scope"] = "Divs derived owned caption guide and bounded final shortcut implemented with finite nominal/source/adversarial proof, current discrete four-direction camera/selectedleaf gestures, history/baselinerecovery, current saved scene and successful whole/detail SVG/PDF integration. Existing Encoder+24y drops default memorylabel/guide before placement because absdy>=15; tensor edge/facts stay exact, undo restores. No general gesture stability or global visual approval. Three historical AI roles remain DuFX/CC91/B_XH, auditors add no participants;17base modules/3transparentstarts unchanged, no perkindgeneration/execution/human certification."
    caption = visual["observedCurrentCaptionRoute"]
    caption["browserFollowup"] = "bounded_current_browser_and_exports_reviewed"
    caption["rootBrowserReceipt"] = "docs/evidence/m4-caption-route-current/final-browser/receipt.json"
    caption["currentCaption"] = browser["currentCaption"]
    caption["discreteCameraDirectionsObserved"] = browser["cameraDirections"]
    caption["discreteSelectedLeafNodeDirectionsObserved"] = browser["selectedLeafNodeDirections"]
    caption["discreteGestureDelta"] = {"cameraPixels": 32, "leafNodeWorld": 32}
    caption["undoRedoAndBaselineRecoveryObserved"] = True
    caption["independentGestureAndStorageRelations"] = {"passed": gestures["passed"], "total": gestures["total"], "scope": "Read-only public SVG/DOM and stored-envelope relationships, not product tests or continuous pixel/input proof"}
    caption["sameDocumentReopen"] = gestures["additionalObservations"]["saveReopen"]
    caption["finalSavedDocument"] = {"documentId": browser["documentId"], "revision": 20,
                                    "storageCounter": 3, "changedDocumentFields": ["revision"],
                                    "sourceIrCanonicalBindingsChanged": False}
    caption["continuousGestureQualityCertified"] = False
    caption["allMemoryLabelsStableAfterMovement"] = False
    caption["currentExperienceGap"] = {**browser["unresolvedExperienceGap"],
                                       "investigation": "docs/evidence/m4-caption-route-current/browser-caption-investigation/report.json",
                                       "rootCause": gap["rootCause"], "thresholdMatrix": gap["thresholdMatrix"],
                                       "status": "unresolved_existing_presentation_stability_gap"}
    visual["evidence"] = [path for path in visual["evidence"] if path != "docs/evidence/m4-caption-route-current/checks-final-attempt-3/receipt.json"] + [
        gate["build"]["checks"], caption["rootBrowserReceipt"],
        "docs/evidence/m4-caption-route-current/final-browser/manifest.json",
        "docs/evidence/m4-caption-route-current/browser-gesture-final/report.json",
        "docs/evidence/m4-caption-route-current/browser-export-final/report.json",
        "docs/evidence/m4-caption-route-current/browser-caption-investigation/report.json",
        "docs/evidence/m4-caption-route-current/export-integration-repair/report.json",
    ]
    research = reqs["research-task"]
    research["scope"] = "Fresh caption-route-export Divs package prepare/verify and296/296 independent frozen readiness only. Five pristine seats43571–43575; none assigned/collected/served, availability notchecked. Twenty-two old packages376files exact, including firstcaption-route nowofficialstale after exporterfix. Human participants0;3–5 realresearchers five-step tasks<=180s and>=80percentcompletion notdone. AI is not human evidence."
    research["evidence"] += [ready_path := gate["currentResearchPackage"]["preparationReport"],
                             "docs/evidence/m4-caption-route-current/research-export-final-preparation/manifest.json"]
    publication = reqs["publication-review"]
    publication["scope"] = "Actual current saved revision20 whole180SVG/rootdetail180SVG/rootdetail180PDF allgenerated; independent178/178 exact export/facts/bindings/decorativeguide/receipt relations, no humanacceptance. Whole180min6.60pt/detail180min7.42pt/whole85preview3.12pt are dimensional advice only. Unarrowedguide survives sharedvalidatedSVG; PDFsame detaildigest. SystemPoppler page180x297.189mm confirmed; bundledGLIBCfailure retained. Root/AI finite screenshots/rasters reviewed, no physical85/180mm humanreview, resolvedfonts/embedding/generalmarkergeometry approval."
    publication["observedCurrentExportPreflight"] = {
        "build": "index-Divs1MJA.js", "documentId": browser["documentId"], "revision": 20,
        **exports["physicalAdvice"], "actualUiExports": browser["actualUiExports"],
        "independentRelations": {"passed": exports["relationCount"], "total": exports["relationCount"], "failures": len(exports["failedRelations"])},
        "pdfGenerated": True, "humanReviewCertified": False,
        "guideDecorationNotCanonicalTensor": True, "guideUnarrowed": True,
        "fontsAndEmbeddingCertified": False,
    }
    publication["evidence"] += ["docs/evidence/m4-caption-route-current/browser-export-final/report.json",
                               "docs/evidence/m4-caption-route-current/browser-export-final/manifest.json",
                               "docs/evidence/m4-caption-route-current/export-integration-repair/report.json",
                               caption["rootBrowserReceipt"]]
    facts["status"] = "final_facts_ready"
    facts["buildReceipt"] = gate["build"]["checks"]
    facts["browserReceipt"] = caption["rootBrowserReceipt"]
    facts["researchReadiness"] = ready_path
    facts["headers"] = {
        "cn": """## 当前状态：连线说明关联、路径缩短与导出修复（2026-10-06）

当前资产为 `index-Divs1MJA.js` / `index--unhoRTb.css`；Studio **389/389、0 skipped/cancelled**，strict TypeScript/Vite 退出 0，publication **11/11、0 skipped**。[统一检查]({{checks}})绑定 105 个源码/测试/配置＋3 个构建文件，共 108 个精确绑定；11 个 publication inputs 另列。见 [当前阶段]({{stage}})与 [当前门状态]({{gate}})。

连线说明使用所属路线关联与派生无箭头 guide；memory 总览引导线 29 世界单位，不新增 canonical edge、tensor 或 Document/history 字段。9 个源模型前沿、198 次 route 出现实际缩短 3 次，减少 161 世界单位和 4 个弯；历史 21 项候选未全采纳。有限独立矩阵的 148 个概览/detail capture、183 组 stroke 检查及自身接触反例已核验，名义范围不等于真实字形或全局最佳路线。[当前浏览器]({{browser}})实际完成相机四方向与一个 leaf 四方向的 32 单位离散动作、undo/redo、保存/重开；515/515 是独立关系，未认证连续手势。Encoder 下移 24 世界单位时，旧 `abs(dy)<15` 默认标签规则仍会使 memory 文字与 guide 消失，tensor 线保留、undo 恢复；未判整体视觉通过。

当前保存 document revision 20、storage counter 3，仅 revision 改变；重开 Scene 与事实保持，相机不保留。真实 whole/detail 180 mm SVG 与 root-detail PDF 已生成，导出白名单的真实失败已修复并保留原记录。[独立导出复核]({{exports}})178/178 只核工件链与有限像素；whole 最小字 6.60 pt、detail 7.42 pt、whole 85 mm 预览 3.12 pt，仅尺寸建议，不是真人出版审看。历史 3 位 DuFX/CC91/B_XH AI 模拟者保持原版本范围，审计者不是新增参与者；AI 不计真人。左库仍为 17 基础模块＋3 透明网络起点，无逐种生成/执行认证。

本构建没有新性能采样。历史 BTw 三次匹配子集 160/72/160 ms、p95 160 ms、rAF 58.605395179 Hz，仅对应旧版；304 DOM 正文当时仅 6 与视口相交/4 完整入内，不是 300 可见对象门。rAF 不是实际呈现 FPS；固定硬件/字体 A/B×3、连续输入、完整输入分母与无关 pins/锚点仍未认证。

M4 为 `partial`、M5 为 `not_started`、真人 0。[最新研究包]({{research}})已 prepare/verify，296/296 仅为独立冻结准备关系；5 空白席位 43571–43575 仅登记，未查端口/启动席位服务/分配/采集。旧 22 包共 376 文件原字节保留，首 caption-route 包与 BTw 包现 stale。真人五步任务、85/180 mm 人审与实际呈现性能门仍待完成。正式工程从头实现，无 Temp runtime/fallback、无新增认证复用；未执行生成模型。[126 项更新前字节]({{archive}})完整保留；下方旧“当前/最终”只按各自版本和冻结时点读取。
""",
        "en": """## Current formal checkout: caption association, bounded shortcuts and export repair (2026-10-06)

Current assets are `index-Divs1MJA.js` / `index--unhoRTb.css`. Studio passes **389/389 with zero skipped/cancelled**, strict TypeScript/Vite exits 0, and publication passes **11/11 with zero skipped**. The [unified receipt]({{checks}}) binds 105 source/test/config and three build files, 108 exact bindings; 11 publication inputs are separate. See the [current stage]({{stage}}) and [gate state]({{gate}}).

Owned-route caption association derives an unarrowed guide: the overview memory guide is 29 world units and adds no canonical edge, tensor or Document/history field. Nine source frontiers contain 198 route occurrences; three change, saving 161 world units and four bends. The historical 21 proposals were not all accepted. The finite independent matrix checks 148 overview/detail captures, 183 stroke cases and the self-contact counterexample; nominal envelopes are not measured glyphs or globally optimal routing. The [current browser]({{browser}}) performs four camera directions and four directions for one leaf through discrete 32-unit operations, undo/redo, save and reopen. Its 515/515 independent relations do not certify continuous gestures. Moving Encoder down 24 world units still removes memory text and its guide under the existing abs(dy)<15 default-label rule; the tensor remains and undo restores the caption. Overall visual quality is not approved.

The final saved document is revision 20, storage counter 3, with only revision changed. Reopened Scene/facts match; camera is not preserved. Actual whole/detail 180 mm SVG and root-detail PDF now succeed after a real publication-whitelist rejection was repaired and retained. The [independent export audit]({{exports}}) has 178/178 artifact relationships and limited reviewed pixels only. Whole minimum text is 6.60 pt, detail 7.42 pt and the whole 85 mm preview 3.12 pt; these measurements are not human publication approval. The three historical DuFX/CC91/B_XH AI roles remain version-qualified; reviewers do not add participants. AI is not a human participant. The catalog remains 17 base modules and three transparent starts, without per-kind generation/execution certification.

This build has no new performance sample. Historical BTw matched durations 160/72/160 ms, subset p95 160 ms and rAF 58.605395179 Hz remain historical. Of 304 DOM bodies, six intersected the viewport and four were fully inside; this is not the 300 visible-object gate. Callback cadence is not presented FPS. Fixed hardware/fonts A/B×3, continuous input, the full denominator and unrelated pins/anchors remain unverified.

M4 remains partial, M5 not_started, humans 0. The [fresh research package]({{research}}) is prepared/verified with 296/296 independent frozen readiness relations only. Five pristine seats register ports 43571–43575; no availability checks, seat services, assignment or collection occurred. All 22 older packages and 376 files remain exact; the first caption-route and BTw packages are stale. Human five-step tasks, 85/180 mm human review and presented performance remain open. The formal implementation is independent of Temp, no reuse candidate is newly certified, and no generated model was executed. The [126 input pre-change archive]({{archive}}) preserves original bytes; earlier current/final statements apply only to their named frozen versions.
""",
    }
    facts["researchCommandSection"] = """### 当前 Caption/route 包：只读开场复核

```bash
cd /home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio
.venv/bin/python scripts/research_trial.py verify --package .archcanvas/m4-research-trial-caption-route-export-current
```

manifest SHA256 为 `009089b5dd5e0ed868a7b1ab34d842671ee9cb47ee5428640dbac675579cea82`。296/296 是准备关系，不是研究验收；5 席位空白、43571–43575 未实际查可用性。正式实现或 dist 变化时保留本包并另建新路径。BTw 的 280/280、首 caption-route 的 295/295 只记录各自冻结时点，现被 verify 拒绝为 stale。下方 D60 和其他旧命令不可作为此版本开场命令。
"""
    output.write_text(json.dumps(facts, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"facts": str(output.relative_to(ROOT)), "status": facts["status"], "entriesApplied": False}, indent=2))


if __name__ == "__main__":
    main()
