# M4 原生输入匹配与当前验收准备

2026-10-06，正式构建为 `index-D60-bDcz.js` / `index-QPVAzYp6.css`。本次修复原生事件匹配，复核基础模型与 holdout，补采两个视图建模流程，并准备新构建的五个未分配研究席位。M4 仍为 `partial`，M5 未开始，真人参与者为 0；完整门状态见 [当前审计](evidence/m4-current-gate-audit.json)。

## 匹配修复与回归

旧 collector 按操作顺序从事件池中取匹配。两个 trial 同时符合一个 event 时，第一个 trial 会抢占它；独立 validator 原先也采用同样的逐次移除策略，无法拒绝这个错误。

现在先计算完整候选关系，只有 trial 有且仅有一个候选，并且该 event 也有且仅有一个候选 trial 时才匹配。竞争、重复条目和候选重叠均保留 `null`。产品从 trial 建图，validator 从 event 反向建图，独立手写反例验证 2→1、2×2、偏斜候选链、±8 ms 边界、不同目标/事件和顺序交换。

修复前专项为 5 fail / 4 pass，修复后专项 9/9，另一独立 suite 为 9/9；它们包含在最终 Studio **314/314、0 skipped** 中，不相加。strict TypeScript/Vite 退出 0，输入前后哈希一致，构建与源码原字节保留在 [checks-final](evidence/m4-native-matching-work/checks-final/receipt.json)。[修复收据](evidence/m4-native-matching-work/receipt.json)和[独立合同](evidence/m4-native-matching-work/independent/report.json)按各自采集时点读取；它们的 `buildRun=false` 是当时事实，最终 build 由 checks-final 单列。

## 静态模型事实

| 独立检查 | 当前结果 | 范围 |
|---|---|---|
| [MLP / Residual CNN](evidence/m4-base-model-current-audit/report.json) | 11/11 | 两模型全部节点、端口、tensor、producer、containment、call/instance/repeat，及九个故意腐坏反例。 |
| [无模板 holdout](evidence/m4-holdout-current-audit/report.json) | 28/28 | 六个源码入口，可恢复事实与保守 opaque。 |
| 同一 holdout 审计的 integrity suite | 22/22 | 完整合同与腐坏拒绝。 |
| 同一审计的本地 cross-suite | 58/58 | 三份声明的静态 suite；与独立子集分列。 |

独立运行采用正式源码副本、Python `-I -S`，未导入或执行 fixture/model/framework。MLP 为 8 节点/8 边，CNN 为 24/24；两者没有 opaque 节点。不推广为任意 Python、实际 tensor shape、数值等价或训练正确性。正式工程未使用 Temp runtime 或回退，未新增认证复用片段。

## 当前浏览器证据

新 build 的[原生 collector smoke](evidence/m4-native-matching-work/browser-smoke/receipt.json)采两个可信自动化 click：Encoder 展开再收起，visible frontier `12→14→12`，revision `0→1→2`，两个事件双向唯一匹配，均为 **1008 ms**，匹配子集 p95 1008 ms。rAF 回调约 2.02/s；零 pin 采样。[独立复算与实图检查](evidence/m4-native-matching-work/browser-smoke-independent/report.json)保留 67 Event Timing entries 中九个正 interaction entry 与三个 interaction ID 的完整分母；两个 trial 不等于全部输入覆盖。

这份收据未通过性能门。rAF 不等于屏幕呈现 FPS，空 longTask 列表不证明没有系统停顿；没有固定字体/硬件 A/B×3、持续呈现 trace 或完整连续 input-to-paint。旧 thbum 的[40 trial 诊断](evidence/m4-current-performance-diagnostic/manifest.json)仍保留为原构建失败证据，不改写为新 build 的测试。

新 build 另有[43 帧/129 原件视图建模补采](evidence/m4-native-matching-work/authoring-smoke/manifest.json)：从空白点击基础模块并连接 Input→Linear 16→32→GELU→Output，保存重开、静态生成并打开新 managed figure；残差 MLP 从搜索后的可见卡片原生拖入，六模块六边，检查、保存重开与静态生成。Add 通过键盘向四方向各移 16 world unit，并逐项撤销重做；相机用原生拖动向四方向各移 40 CSS px。两个流程的实际保存草稿和一个 managed source 保留在 [工件快照](evidence/m4-native-matching-work/authoring-artifacts/manifest.json)。

补采明确保留失败：`four-added` JPEG 落后对应 Output 状态；预制库切换、搜索和上下移截图也有跨状态滞后，提示原图未捕获 tooltip，最终图的选择/平移模式标记与 DOM 不同；原始预制卡片裁切后的拖动无变化；相机右返程时 CUA batch 超时，观察到 +30 px 残留，再一次补偿仍剩 +10 px，最后单次移动才恢复。公开几何不替代失败像素。局部 100% 只代表局部视图，不认证全图同时可读。节点键盘位移不称四向节点原生拖动，生成不等于执行。像素结论仅以[独立亲看报告](evidence/m4-native-matching-work/authoring-pixel-independent/receipt.json)覆盖图为准；公开几何/保存/AST结论见[独立工件合同](evidence/m4-native-matching-work/authoring-contract-independent/report.json)。

左库当前实际为 **17 基础模块＋3 透明网络起点**（MLP、CNN、残差 MLP），可点击或拖入。新增补采不认证 17 种逐模块完整任务或复杂图最少交叉/弯折；Attention/LSTM、模型执行与训练不在作者子集内。此前 AI 角色与各自旧 build 覆盖列于 [AI 体验审查汇总](evidence/m4-ai-usability-current-review/README.md)，不能计为真人参与者。

独立审查失败后仅补五个稳定状态：搜索、上下移、端口提示和最终预览。CUA capture 函数仍写入原目录，首次补采 manifest 因此为空；该空清单保留为落盘失败。15 份实际原件已按字节复制到[第二次补采清单](evidence/m4-native-matching-work/authoring-supplement/attempt-2/manifest.json)，源文件和原 43 帧绑定不改，未重做浏览器动作。[补采独立像素审查](evidence/m4-native-matching-work/authoring-pixel-independent/supplement-review.json)亲看五图，在其观察范围内均与对应状态一致；原 19 图审查为 11 有界一致、1 managed selector 范围不足、7 不同步，总亲看 24 图不称全部 48 图认证。补采不覆盖原七处失败。53% 的小端口、标题省略、残差与普通线同色、第三起点位于首屏下方仍是具体体验限制。

## 新研究包与下一门

`.archcanvas/m4-research-trial-native-matching-current` 已实际 prepare/verify。独立检查确认 81/81 实施绑定、四份 baseline、136/136 readiness checks、五席 pristine；登记端口 43151–43155，服务未启动，端口可用性未测，0 分配/收集/真人。包 manifest SHA256 为 `321c1c2c83126f57b2cb96f1debafd07849c946afce60a95e5db73b6778dd13c`。见 [实际进程](evidence/research-trial/native-matching-current/process.json)、[独立复核](evidence/m4-research-native-matching-independent/report.json)和[开场协议](m4-research-protocol.md)。

五步真人研究任务与 85/180 mm 出版尺寸审看仍待取得；[新增探索任务卡](evidence/m4-research-handoff-audit-attempt-1/novice-and-view-task-card.md)覆盖从零搭建、预制模块、四向操作与箭头视觉，作为独立扩展任务，不混入原五步 180 秒分母。AI 自动化不用真人席位。

当前阶段的检查服务/标签页仅用于隔离自动化，未操作原有用户标签页；[当前预览生命周期](evidence/m4-native-matching-work/final-current-readback/preview-lifecycle.json)保留 session39008 / tab63 的实际记录，不承诺 URL 长期在线。[当前输入与链接回读](evidence/m4-native-matching-work/final-current-readback/report.json)核 99 项源码/构建绑定、入口与 gate 链接、Skill 校验和包 verify；范围不扩大到历史所有封印。[文档更新前归档](evidence/m4-native-matching-work/before-current-doc-update/manifest.json)保留旧入口原字节；旧 raw、seal、manifest 和失败记录不回写。
