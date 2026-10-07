"""Assemble frozen CXutz4Vh documentation facts without importing the product."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STAGE = "docs/evidence/m4-caption-stability-current/"


def load(path):
    return json.loads((ROOT / path).read_text())


def bind(path):
    raw = (ROOT / path).read_bytes()
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


facts = load(STAGE + "entry-update-work/draft-facts-attempt-2.json")
gate = facts["finalGate"]
receipt_path = STAGE + "checks-final-attempt-2/receipt.json"
receipt = load(receipt_path)
browser_path = STAGE + "independent-review/final-material-review/browser-readback-final/report.json"
browser = load(browser_path)
export_path = STAGE + "actual-export-readback/report.json"
exports = load(export_path)
research_path = STAGE + "research-readiness-independent/report.json"
research = load(research_path)
assert len(receipt["inputs"]) == 110 and len(receipt["build"]) == 3 and len(receipt["publicationInputs"]) == 11
assert browser["passed"] == browser["total"] == 262
assert exports["relationCount"] == 669 and not exports["failedRelations"]
assert research["independentReadiness"]["passed"] == research["independentReadiness"]["total"] == 304
facts["status"] = "final_facts_ready"
facts["buildReceipt"] = receipt_path
gate["schema"] = "archcanvas-m4-current-gate-audit/6"
gate["build"] = {
    "js": "index-CXutz4Vh.js", "css": "index--unhoRTb.css", "checks": receipt_path,
    "studioTests": 409, "skipped": 0, "cancelled": 0, "strictBuildExitCode": 0,
    "publicationTests": 11, "publicationSkipped": 0,
    "sourceTestConfigBindings": 110, "distBindings": 3, "totalSourceBuildBindings": 113,
    "publicationInputBindings": 11, "helperFrozenTransitiveCoreInputsSeparate": 18,
    "focusedSuiteCountsAreOverlapping": True,
    "scope": "Frozen CXutz4Vh source/build bytes only; later source edits or builds are not certified by this receipt. 110 is not a complete transitive inventory."
}
reqs = {r["id"]: r for r in gate["requirements"]}
visual = reqs["visual-authoring"]
visual["scope"] = "CXutz4Vh accepted default memory naming and per-document session camera preference. Production2708/2708; bounded browser262/262 data relations retain first reset-centre failure39. Four camera and four Encoder directions observed in DOM, screenshot27 lags. Existing dy14→15 display endpoint/route discontinuity and global aesthetics remain open; rejected candidates excluded. No human acceptance."
visual["observedCurrentCaptionStabilityCamera"].update({
    "status": "bounded_frozen_current_evidence",
    "build": "index-CXutz4Vh.js",
    "browserReport": browser_path,
    "browserDataRelations": {"passed": 262, "total": 262, "notAllFunctionalSuccesses": True},
    "cameraRestorePairs": browser["cameraRestorePairs"],
    "cameraCardinalDirections": 4, "cameraCardinalDistanceCssPx": 32,
    "encoderCardinalDirections": 4, "encoderDistanceWorld": 24, "encoderUndoCases": 4,
    "savedRevision": 31, "storageRevision": 5, "savedDeltaFrom20": browser["savedDeltaFrom20"],
    "crossViewport": browser["crossViewport"], "servedBytesHashVerified": False,
    "staleUpScreenshotRetained": True, "liveResizeObserver": False,
    "continuousGestureQualityCertified": False,
})
for path in ["docs/m4-caption-stability-camera.md", receipt_path, STAGE + "implementation-work/report.json",
             STAGE + "independent-review/production-label-only-audit/report.json", browser_path,
             STAGE + "camera-work/correction-attempt-4/report.json", STAGE + "root-observation.json"]:
    visual["evidence"].append(path)
perf = reqs["browser-performance"]
perf["observedCurrentCaptionStability"] = {"build": "index-CXutz4Vh.js", "status": "preparation_only_no_timing_sample", "newTimingSample": False, "performanceGatePassed": False, "presentedFpsCertified": False, "gridBodiesReadable": False}
perf["evidence"] += [STAGE + "performance-workload/preparation-report.json", STAGE + "camera-performance-review/report.json"]
pub = reqs["publication-review"]
pub["scope"] = "Three actual revision31 UI exports (whole180PDF/whole180SVG/rootdetail180SVG),669/669 independent artifact/facts/digest/XML/PDF relationships. First audit668 has72 failed relations caused by three oracle assumptions; original retained. Limited root-reviewed pixels only; whole180 minimum6.56018pt/detail7.41862pt/whole85 calculated3.09786pt. No actual85 artifact, physical human approval, font embedding/shaping or global routing certification."
pub["observedCurrentCaptionStabilityExportPreflight"] = {
    "build": "index-CXutz4Vh.js", "revision": 31, "storageRevision": 5,
    "independentRelations": {"passed": 669, "total": 669, "failures": 0},
    "firstAudit": {"relations": 668, "failures": 72, "oracleCorrections": 3, "retained": True},
    **exports["physicalMeasurements"],
    "actualUiExports": [{"id": x["serviceArtifact"].split("/")[-2], "format": x["receipt"]["format"], "scope": "root-detail" if key == "detailSvg" else "whole", "widthMm": 180, "revision": 31} for key, x in exports["exports"].items()],
    "fontsAndEmbeddingCertified": False, "globalVisualQualityApproved": False,
    "report": export_path,
}
pub["evidence"] += [export_path, STAGE + "actual-export-readback/audit-first-attempt-report.json", STAGE + "root-observation.json", "docs/m4-caption-stability-camera.md"]
task = reqs["research-task"]
task["scope"] = "Fresh frozen CXutz4Vh package prepared/verified with304/304 readiness relationships;85implementation4baseline,5pristine seats43611–43615. Old23packages393files exact. No availability check, service, assignment or collection; humans0. Preparation and historical three AI roles do not satisfy real-user five-step/180seconds/80% acceptance. Later source/build changes make this package stale."
task["evidence"] += [research_path, STAGE + "research-readiness-independent/manifest.json", STAGE + "research-final-preparation/process.json", STAGE + "research-final-preparation/prior-package-verify.process.json"]
gate["currentResearchPackage"] = {
    "path": research["package"], "manifestSha256": research["packageManifestSha256"],
    "pristineSlots": 5, "assigned": 0, "collected": 0, "humans": 0,
    "registeredPorts": research["registeredPorts"], "servicesStarted": False, "portsAvailabilityChecked": False,
    "currentVerification": "prepared_and_verified", "officialVerifyExitCode": 0,
    "independentReadiness": {"passed": 304, "total": 304}, "implementationBindings": 85, "baselineBindings": 4,
    "oldPackagesPreserved": 23, "oldPackageFilesPreserved": 393,
    "preparationReport": research_path,
    "scope": "Frozen CXutz4Vh readiness at recorded preparation only. Registered ports are not availability checks; later source/build edits require a fresh package."
}
gate["historicalCaptionRouteResearchPackage"]["currentVerification"] = "stale"
gate["historicalCaptionRouteResearchPackage"]["officialStaleReceipt"] = STAGE + "research-final-preparation/prior-package-verify.process.json"
facts["targets"] = {"checks": receipt_path, "browser": browser_path, "exports": export_path, "research": research_path}
facts["headers"]["cn"] = """## 当前状态：memory 名称稳定性与相机重开（2026-10-06）

本阶段仅认证 `index-CXutz4Vh.js` / `index--unhoRTb.css` 的冻结源码与构建。Studio **409/409**、fail/skip/cancel 0，strict TypeScript/Vite exit 0；publication **11/11**、skip 0。[统一收据]({{checks}})绑定 110 源码/测试/配置＋3 dist＝**113**，另 11 publication 输入；18 份兼容 helper 历史 core 单独核验，110 不是完整传递依赖清单。见[阶段]({{stage}})、[门状态]({{gate}})与[138 项更新前原字节]({{archive}})。后续源码或构建变化不能沿用这些认证。

默认 memory 名称持续显示，自定义及显式空名保留；标签矩阵为一个 Transformer、45 detached 输入、360 whole/detail 输出、2708/2708 关系，canonical、原路径与端点在匹配输入上不变。dy14→15 的 display 端口阈值仍使路线 49→644.3 世界单位；新增 peer 接触/相交的候选已拒绝冻结。标签稳定不等于全域连线美观通过。

独立 session 相机按 document/source/IR 与 visualRevision 保存 zoom/世界中心。clone 初始化错误和原失败保留；修后 focused 24/24 不是 React 挂载证明。[浏览器读回]({{browser}})262/262 是数据关系：同视口刷新、模型返回、四向相机 32 CSSpx、Encoder 四向 24 世界单位与 undo、保存重开已记录。883×786 重开保持中心；第一次回到 672×711 的 capture39 中心失败，第二次稳定重开成功；无 live ResizeObserver。上移 capture27 截图滞后于 DOM；served JS 只核文件名，未独立取 HTTP bytes。最终 Canvas revision31、storage counter5，相对旧 revision20 除 revision 外 root 移动＋4,＋4。

[实际导出]({{exports}})669/669 关系核对 revision31 的整图180mm PDF/SVG及 root-detail SVG；初次668关系中的72失败由三项 oracle 假设纠正，原报告保留。整图最低6.56018pt、detail7.41862pt，85mm计算预览3.09786pt，没有实际85mm产物。有限像素观察不认证字体嵌入、物理人审或全域美观。

历史 DuFX/CC91/B_XH 三个 AI 角色保持原 build 范围；审计者不新增参与者，AI 不计真人。左库仍17基础模块＋3透明网络起点，无逐种生成/执行认证。旧 BTw 性能只按旧条件读取；304 DOM 不等于300可读可见对象，rAF 不是实际呈现 FPS。300卡 grid 名义文字仍小于1 CSSpx；固定硬件/字体 A/B×3、连续输入完整分母、pins/anchor 与 presented 性能未认证。

M4 `partial`、M5 `not_started`、真人 0。[研究准备]({{research}})304/304 仅冻结 readiness：新包85 implementation/4 baseline，5 pristine席位43611–43615；旧23包393文件 exact。未查可用性、开席位服务、分配或采集；3–5真人五步任务≤180秒/≥80%与85/180mm人审仍开放。旧gold、失败、包与第二个`##`起历史正文保持原字节。正式工程从头实现，独立于Temp runtime/fallback，无新认证复用；未执行生成模型。下方旧“当前/最终”仅按各自冻结版本读取。
"""
facts["headers"]["en"] = """## Current formal checkout: persistent memory names and camera reopen (2026-10-06)

This stage certifies frozen `index-CXutz4Vh.js` / `index--unhoRTb.css` only. Studio **409/409**, fail/skip/cancel 0; strict TypeScript/Vite exit 0; publication **11/11**, skip 0. The [unified receipt]({{checks}}) binds 110 source/test/config plus3 dist = **113**, with11 publication inputs separate. Eighteen historical helper core inputs are separately checked;110 is not a complete transitive inventory. See the [stage]({{stage}}), [gate]({{gate}}) and [138-input original archive]({{archive}}). Later source edits or builds cannot inherit this certification.

Default memory names persist; custom and explicit empty names retain their meaning. One Transformer,45 detached inputs and360 whole/detail outputs yield2708/2708 relationships, with matched canonical facts, paths and endpoints unchanged. The existing dy14→15 display-port threshold still changes route length49→644.3 world units. Candidates introducing peer contacts/crossings were rejected and frozen. Stable text does not approve global routing aesthetics.

Separate session camera preferences bind document/source/IR and visualRevision, storing zoom/world centre. The clone initialization failure is retained; focused24/24 does not mount React. The [browser readback]({{browser}})262/262 verifies data relationships: same-viewport reload/model returns, four camera directions32CSSpx, four Encoder directions24world with undo, save/reopen. Reopen at883×786 preserves centre; first reset capture39 at672×711 fails it, second stable reopen passes. No live ResizeObserver exists. Capture27 pixels lag the up-move DOM; served JS filenames match but HTTP bytes were not independently fetched. Canvas revision31/storage counter5 differs from old revision20 by revision and root layout+4,+4.

[Actual exports]({{exports}})669/669 relationships cover revision31 whole180mmPDF/SVG and root-detailSVG. The first668-relation audit has72 failed relations from three oracle assumptions; original retained. Whole minimum6.56018pt/detail7.41862pt, calculated85mm preview3.09786pt; no actual85mm artifact. Limited pixels do not certify font embedding, physical human review or global aesthetics.

Historical DuFX/CC91/B_XH AI roles remain version-bound; auditors add no participants. AI is not a human participant. The library remains17base modules/3transparent starts without per-kind generation/execution certification. Historical BTw timings retain their conditions;304DOM objects are not300readable visible objects. rAF is not presented FPS. Grid nominal text remains below1CSSpx; fixed hardware/fonts A/B×3, continuous full denominator, pins/anchors and presented performance remain unverified.

M4 partial, M5 not_started, humans 0. [Research readiness]({{research}})304/304 is frozen preparation only:85implementation/4baseline,5pristine seats43611–43615;23older packages393files exact. No availability checks, seat services, assignments or collection occurred. Real3–5user five-step≤180seconds/≥80% and85/180mm human review remain open. Old gold/failures/packages and historical bodies from the second level-two section stay exact. The formal implementation is independent of Temp/fallback; no reuse candidate is newly certified and no generated model was executed. Earlier current/final statements apply only to their named frozen versions.
"""
stage = (HERE / "stage-final-candidate.md").read_text()
stage = stage.replace("真实browser最终范围、导出与保存链在正式最终摘要到齐后填入；初DRsn失败始终保留。", "真实browser最终范围、导出与保存链如下；初DRsn失败始终保留。")
insert = """## 有限真实浏览器与实际导出

[最终浏览器读回](evidence/m4-caption-stability-current/independent-review/final-material-review/browser-readback-final/report.json)检查27份数据capture、3次UI导出，共262/262关系；关系通过包括忠实记录失败，不等于27个功能成功。正式CXutz4Vh下13→14同视口pan刷新恢复，14→17 Transformer返回与16→18 MLP返回各自恢复；相机四向32 CSSpx、Encoder四向24世界单位及四次undo都有公共DOM。保存33→重开34的Canvas revision31与场景相同，storage counter5；相对历史revision20，除revision外root从(50,92)到(54,96)，＋4,＋4，不能称只有revision变化。

重开38的viewport883×786保持中心(350,405)、zoom1；首次reset39已回672×711但平移仍旧，中心(244.5,367.5)失败。再次稳定重开40才恢复(350,405)；final fit41为76.4%。没有live ResizeObserver，首帧协调仍待下一阶段。capture27的上移截图显示前rev25，DOM才是rev26，不能认证上移像素；servedBytesHashVerified=false，资产仅以公共DOM文件名和current/frozen收据核对。[root有限观察](evidence/m4-caption-stability-current/root-observation.json)保留上述时序问题；01–04缺文件、35下载等待超时均不改为成功。

[实际导出独立读回](evidence/m4-caption-stability-current/actual-export-readback/report.json)为669/669关系，三份document.json与保存revision31 exact：整图180mmPDF `560507709172409ca6e87253999b0479`、整图SVG `a0f5b6e9b4f64376b45b06f1632bf830`、root-detailSVG `72a40cc1a38048ba8b3b8ae2b88001ac`。初次668关系有72失败，来自callCount分组、派生provenance annotation和PDF尺寸精度三项oracle假设；[原报告](evidence/m4-caption-stability-current/actual-export-readback/audit-first-attempt-report.json)保留，产品未为此修改。整图最低6.56018pt、detail7.41862pt；85mm计算预览3.09786pt，没有实际85mm产物。系统Poppler只读render成功；bundled GLIBC失败保留。root亲看有限PDF像素有memory/guide且该有限区域无clip，但mask线重叠、小文字、字体嵌入/塑形、物理人审与全域美观仍未认证。

"""
stage = stage.replace("## 可读300对象与性能尚未闭合", insert + "## 可读300对象与性能尚未闭合")
stage += "\n此阶段只绑定CXutz4Vh冻结源码和上述收据时点。以后修改源码、测试或dist不反向认证本阶段，也会使该研究包失去current资格；应保留旧包并新建具名准备包。\n"
facts["newMarkdown"] = {
    "docs/m4-caption-stability-camera.md": stage,
    STAGE + "README.md": """# Caption stability and camera stage evidence

This frozen stage accepts persistent default memory naming and separate per-document session camera preferences on `index-CXutz4Vh.js` / `index--unhoRTb.css`. Later source/build edits cannot inherit these claims.

- [Stage scope and remaining gaps](../../m4-caption-stability-camera.md)
- [Unified checks](checks-final-attempt-2/receipt.json):409/409 Studio,11/11 publication,strict0;110source/test/config+3dist=113,11publication separate,18frozen helper-core separately bound.
- [Production label-only audit](independent-review/production-label-only-audit/report.json):2708/2708 relationships across45detached inputs/360outputs; no global aesthetics certification.
- [Browser data readback](independent-review/final-material-review/browser-readback-final/report.json):262/262 relationships retain first reset39 failure and stale up27 pixels.
- [Actual exports](actual-export-readback/report.json):669/669 relationships for revision31; first668/72fail report retained, no physical human approval.
- [Research readiness](research-readiness-independent/report.json):304/304 preparation only;85implementation/4baseline/5pristine seats,old23packages393files exact.
- [Original138inputs](before-change/manifest.json) and [root bounded pixel observations](root-observation.json) retain failures and limitations.

M4 partial, M5 not_started, humans0. Historical three AI roles do not count as human participants;304DOM is not300readable visible objects; rAF is not presented FPS. No generated model was executed, no new Temp reuse was certified, and no semantic source writeback occurred.
""",
}
evidence_paths = [receipt_path, STAGE + "checks-final-attempt-2/studio.txt", STAGE + "checks-final-attempt-2/publication.txt",
    STAGE + "independent-review/production-label-only-audit/report.json", STAGE + "independent-review/production-label-only-audit/production-exact-readback.json",
    STAGE + "independent-review/independent-seal-attempt-2/report.json", STAGE + "implementation-work/report.json", STAGE + "implementation-work/manifest.json",
    STAGE + "camera-work/correction-attempt-4/report.json", STAGE + "camera-work/correction-attempt-4/manifest.json",
    STAGE + "independent-review/final-material-review/checks-readback-attempt-2/report.json", STAGE + "independent-review/final-material-review/checks-readback-attempt-2/manifest.json",
    browser_path, STAGE + "independent-review/final-material-review/browser-readback-final/manifest.json", STAGE + "root-observation.json",
    export_path, STAGE + "actual-export-readback/audit-first-attempt-report.json", STAGE + "actual-export-readback/capture-receipt.json",
    research_path, STAGE + "research-readiness-independent/readiness-report.json", STAGE + "research-readiness-independent/manifest.json",
    STAGE + "research-final-preparation/process.json", STAGE + "research-final-preparation/old-packages-before.json", STAGE + "research-final-preparation/prior-package-verify.process.json",
    research["package"] + "/manifest.json"]
evidence_paths += [x["artifact"] for x in exports["exports"].values()]
facts["evidenceBindings"] = [bind(p) for p in evidence_paths]
out = HERE / "final-facts-attempt-1.json"
assert not out.exists()
out.write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n")
print(out.relative_to(ROOT))
