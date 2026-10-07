"""Prepare/apply only five documentation paths for the measurement correction."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[4]
WORK = Path(__file__).resolve().parent
STAGE = "docs/evidence/m4-continuous-proxy-correction-current"
BEFORE = WORK / "before-entry-inputs"

stage_text = """# M4 连续 DOM 观测代理修正

本次修正测量工具：旧 full boundary 包含 304 个对象，而连续 frame 只记录声明的 target/anchor/pin；直接比较不同对象集合，会把首次部分观测误判为状态变化。现在用相同、排序去重的声明 ID 集合及固定字段比较，完整 boundary 签名仍保留原用途。Studio/runtime 产品、当前 memory 构建与 M4 门状态保持原范围，没有重新采集浏览器数据。

正式变更是 [基础 validator](../scripts/validate_input_observation.mjs)、[连续 wrapper](../scripts/validate_continuous_observation.mjs) 和新增 [独立反例](../tests/m4_continuous_projection_independent.test.mjs)。[正式组合测试](evidence/m4-continuous-proxy-correction-current/formal-constraint-attempt-1.tap) **71/71**，由原 27 项与新增 44 项组成，exit0、fail/cancel/skip0；独立候选 44/44 单列，计数有重叠，不加入 Studio 436。见 [独立报告](evidence/m4-continuous-proxy-correction-current/independent-report.json)及[审查说明](evidence/m4-continuous-proxy-correction-current/independent-review.md)。其 13 条字节绑定不是完整产品依赖清单。

## 修正后的代理合同

`same-declared-ids-dom-state/1` 比较 revision、数值 camera、canvas/screen rect 和 label。required ID 缺少 own property 会拒绝 coverage binding；显式 null 是不完整观测，返回 null proxy 与 `required-object-unavailable`。截断、dropped/errors 或 ledger/capture 不完整返回 `incomplete-capture`；没有后续变化返回 `no-later-observed-change`。缺失不会作为零加入 p95。

document/canonical 不一致会拒绝；frame 未提供 source/IR 时只报告 boundary 范围，提供却不一致仍拒绝。空声明集只能观测 camera/revision；revision-only 标签明确，不能证明几何变化。failed、wrong-tool 或 no-input 任务不能因 proxy 存在而变为成功。

对每个输入，查找 observedAt ≥ 该输入 capturedAt 的首次已变化 DOM 观测；duration 为 observedAt−eventAt，多个输入可能共享一个观测 frame。它不识别哪次输入造成变化，不证明中间未记录的对象运动，也不认证 input-to-paint、画面已呈现或 presented FPS。

## 原 KAUB 数据的只读重放

[新派生重放](evidence/m4-continuous-proxy-correction-current/replay-attempt-1/report.json) **33/33** 有限关系、**17/17** 独立逐输入值 exact。原记录保留 33 个可信连续输入，17 个分配到 eligible trials、16 个在其外；17 measured、0 unmeasured，measured subset p95 **1716.1 ms**。completeCapture=true 只说明所记录的捕获完整，presentedPaintCertified=false、causalInputIdentified=false。

| 原 trial | 首输入 proxy：旧→修正（ms） | 修正后 trial p95（ms） |
| --- | --- | --- |
| trial-1 pan，8 inputs | 960→965.4 | 994.9 |
| trial-5 成功 drag，8 inputs | 772.9→1015.4 | 1716.1 |
| trial-7 wheel，1 input | 39.5→45.2 | 45.2 |

其余逐输入数字保持。discrete 的 14 eligible / 13 matched / 5 interaction IDs / matched-subset p95 3024 ms、cadence、observer cost、errors、dropped、count/duration 和 full-boundary diagnostics 保持；trial-2 no-input drag 仍失败。原 [26/29 失败报告](evidence/m4-readable-grid-browser-next/continuous-browser/independent-readback-attempt-2/report.json)及原 raw 不回写、不改绿。历史 validator 的新合同 baseline 是 39 unmet / 5 wrapper excluded，很多断言针对新增报告字段，不等于 39 产品缺陷；首轮 file-level 日志也保留，正式逐项计数来自后续 TAP。

重放绑定原 18,831,519 字节 raw、历史报告/validator output、expected-proxies 快照、memory 收据、before-change manifest 和两个当前 validators，共 8 个输入；原 6 条历史输入或快照 exact、产品收据的 **129** 有限绑定 exact。[root 有限读回](evidence/m4-continuous-proxy-correction-current/root-final-readback.json)确认 independent13/13、replay8/8、product129/129 字节及 TAP71/71 与报告33/33、17/17，不额外跑测试。数据来自历史 KAUB，不是当前 CU5 的新浏览器性能测试。本次未重跑 Studio/publication 全套、未执行模型、未增加真人。

## 当前产品与研究门

当前产品仍是 [memory continuity](m4-memory-continuity.md) 的 `index-CU5JhnoS.js` / `index--unhoRTb.css`，Studio 436/436、strict/build0、publication 11/11 是该阶段原冻结收据。本次 validator 确实改变，不能泛称所有源码不变。当前 research 包仅[确认 manifest 列出的 87 个 implementation bindings](evidence/m4-continuous-proxy-correction-current/entry-update-work/research-listed-bindings-readback.json) exact；这两个 validators 不在该清单中。本次没有重跑研究协议、prepare 新包、启动服务、probe、分配或 collect，也不新增 313 readiness 认证。

M4 `partial`、M5 `not_started`、真人 0。3–5 真人五步任务、85/180 mm 真人审看、当前 readable300、continuous≤50 ms、medium<500 ms、固定硬件/字体 A/B×3 及 presented≥50 FPS 仍开放；历史三个 AI 角色不计真人，17 基础模块＋3 透明网络起点不等于逐种生成/执行。

[历史代理设计](evidence/m4-continuous-proxy-correction-next/README.md)保留其设计冻结时点；本文只认证已落的测量修正。[saved-frontier 分析](evidence/m4-frontier-cache-analysis-next/README.md)仍是只读设计，`current-frontier` scope 尚未实现。旧 rev5 collapse 候选及其失败不修写；新候选应从 unbroken grid rev4 准备。

## 文档字节边界

只新增本文与[阶段索引](evidence/m4-continuous-proxy-correction-current/README.md)，在 performance/evidence 索引当前 memory 第一节追加说明，并给 gate 追加 `latestMeasurementCorrection`。其他 gate 字段及两个入口第二个 `##` 后历史正文 exact。

[更新前快照](evidence/m4-continuous-proxy-correction-current/entry-update-work/before-entry-inputs/manifest.json)冻结这三个将改的旧路径，并保留原 memory 文档 seal；旧 seal 的 248 条绑定通过三个明确旧快照及其余 245 条未变路径解析。旧 seal 不直接绑定后续修改的 live 文档，也不替换旧 hash。本次窄[文档读回](evidence/m4-continuous-proxy-correction-current/entry-update-work/document-readback.json)和[新文档封包](evidence/m4-continuous-proxy-correction-current/entry-update-work/document-seal-final-attempt-1/manifest.json)仅证明列明的字节与文档关系，不扩大产品、视觉、性能或真人认证。
"""

index_text = """# 连续 DOM 观测代理修正证据

本目录记录测量工具修正，当前产品仍为 memory continuity 的 CU5 构建；M4 partial、M5 not_started、真人0。见[阶段说明](../../m4-continuous-proxy-correction.md)。

- [正式组合测试](formal-constraint-attempt-1.tap)：71/71（原27＋新增44），exit0、fail/cancel/skip0；不计入 Studio436。
- [独立反例报告](independent-report.json)与[审查说明](independent-review.md)：13有限字节绑定；历史 baseline39 unmet/5wrapperexcluded 是新合同断言，不等于39产品bugs。首轮file-level日志原样保留。
- [只读重放](replay-attempt-1/report.json)：33/33关系、17/17逐输入exact，pan/drag/wheel p95为994.9/1716.1/45.2ms；首次DOM变化不是因果input-to-paint或presented FPS。
- [root 有限读回](root-final-readback.json)：independent13/13、replay8/8、product129/129 字节exact，TAP/报告范围确认，不额外跑测试。
- [原测量代码快照](before-change/manifest.json)：旧validator、原27测试与expected-proxies保留。原26/29报告、no-input失败及历史raw不改绿、不回写。
- [研究清单有限确认](entry-update-work/research-listed-bindings-readback.json)：87/87列明implementation字节exact，两个validators不在清单，不是研究协议重跑或新readiness。
- [文档更新前快照](entry-update-work/before-entry-inputs/manifest.json)：三条旧路径供memory旧248seal明确解析；[文档读回](entry-update-work/document-readback.json)、[新文档seal](entry-update-work/document-seal-final-attempt-1/manifest.json)仅认证本次有限范围。

产品129绑定exact来自重放；本次未新采浏览器、未重跑Studio/publication、未执行模型或增加真人。saved-frontier scope仍[仅设计](../m4-frontier-cache-analysis-next/README.md)，旧collapse候选与失败保持。
"""

updates = {
    "docs/m4-continuous-proxy-correction.md": stage_text,
    f"{STAGE}/README.md": index_text,
}
for path, stage_link, report_link in [
    ("docs/m4-performance.md", "m4-continuous-proxy-correction.md", "evidence/m4-continuous-proxy-correction-current/replay-attempt-1/report.json"),
    ("docs/evidence/README.md", "../m4-continuous-proxy-correction.md", "m4-continuous-proxy-correction-current/replay-attempt-1/report.json"),
]:
    old = (BEFORE / path).read_text()
    first, historical = old.split("\n## 历史版本记录", 1)
    addition = f"\n后续[连续 DOM proxy 测量修正]({stage_link})仅改 validator/wrapper 和独立反例，产品 CU5/上述门状态保持。正式组合 **71/71**（原27＋新增44）单列，不加入 Studio436；[历史 raw 重放]({report_link})33/33、17逐输入exact，纠正 pan/drag/wheel 首proxy为965.4/1015.4/45.2ms，trial p95为994.9/1716.1/45.2ms。旧26/29/no-input失败仍保留；这是同声明ID首次DOM变化，非因果input-to-paint/presented FPS，没有当前浏览器新测或真人认证。研究manifest列明87bindings仅有限字节确认，非协议重跑或新包；旧memory248文档seal对本次三条改动路径通过明确旧快照解析，不直接绑定后续live字节。\n"
    updates[path] = first + addition + "\n## 历史版本记录" + historical

gate_path = "docs/evidence/m4-current-gate-audit.json"
old_gate_text = (BEFORE / gate_path).read_text()
gate = json.loads(old_gate_text)
assert "latestMeasurementCorrection" not in gate
addition = {
    "stage": "docs/m4-continuous-proxy-correction.md",
    "scope": "Validator-only measurement correction; current product build, currentStage, research package and M4 gate state retain their existing scope.",
    "definition": "same-declared-ids-dom-state/1",
    "formalTests": {"passed": 71, "total": 71, "existing": 27, "newIndependent": 44, "failed": 0, "cancelled": 0, "skipped": 0, "exitCode": 0, "log": f"{STAGE}/formal-constraint-attempt-1.tap", "independentReport": f"{STAGE}/independent-report.json", "addedToStudioTestCount": False},
    "historicalNewContractBaseline": {"failed": 39, "wrapperExcluded": 5, "scope": "Unmet new-contract assertions, including added report fields, not 39 independent product bugs.", "log": f"{STAGE}/old-validator-independent-attempt-2.tap"},
    "replay": {"report": f"{STAGE}/replay-attempt-1/report.json", "passed": 33, "total": 33, "independentPerInputExact": 17, "retainedContinuousInputs": 33, "assignedInputs": 17, "outsideTrialInputs": 16, "measuredInputs": 17, "unmeasuredInputs": 0, "measuredSubsetP95Ms": 1716.0999999996275, "trialP95Ms": {"pan": 994.9, "successfulDrag": 1716.1, "wheel": 45.2}, "completeCapture": True, "presentedPaintCertified": False, "causalInputIdentified": False, "old26of29FailuresPreserved": True, "noInputTrialRemainsFailed": True, "scope": "Read-only historical KAUB raw replay, not new current-build browser measurement."},
    "productBindingsExact": 129,
    "rootFiniteReadback": f"{STAGE}/root-final-readback.json",
    "researchListedBindings": {"passed": 87, "total": 87, "report": f"{STAGE}/entry-update-work/research-listed-bindings-readback.json", "validatorsOutsideManifestInventory": True, "protocolRerun": False, "newPackagePrepared": False},
    "oldMemoryDocumentSealResolution": {"passed": 248, "total": 248, "changedPathsUseExplicitBeforeSnapshots": 3, "unchangedPaths": 245, "manifest": f"{STAGE}/entry-update-work/before-entry-inputs/manifest.json", "oldSealRewritten": False},
    "documentReadback": f"{STAGE}/entry-update-work/document-readback.json",
    "productChanged": False,
    "measurementToolsChanged": True,
    "browserRerun": False,
    "modelExecuted": False,
    "humanParticipantsAdded": 0,
    "performanceGatePassed": False,
    "frontierScopeImplemented": False,
}
# Retain every old gate byte except the final root brace, appending one key.
trimmed = old_gate_text.rstrip()
assert trimmed.endswith("\n}")
serialized = json.dumps(addition, ensure_ascii=False, indent=2)
updates[gate_path] = trimmed[:-2] + ",\n  \"latestMeasurementCorrection\": " + "\n  ".join(serialized.splitlines()) + "\n}\n"
new_gate = json.loads(updates[gate_path])
assert {k: v for k, v in new_gate.items() if k != "latestMeasurementCorrection"} == gate

preview = WORK / "preview-final-attempt-1"
preview.mkdir(exist_ok=False)
for path, content in updates.items():
    destination = preview / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content)
print(json.dumps({"preparedPaths": list(updates), "gateOldFieldsExact": True}, ensure_ascii=False))
if "--apply" in sys.argv:
    for path in ["docs/m4-performance.md", "docs/evidence/README.md", gate_path]:
        assert (ROOT / path).read_bytes() == (BEFORE / path).read_bytes(), path
    for path, content in updates.items():
        destination = ROOT / path
        assert path in ["docs/m4-performance.md", "docs/evidence/README.md", gate_path] or not destination.exists(), path
        destination.write_text(content)
    print("Applied five documentation paths.")
