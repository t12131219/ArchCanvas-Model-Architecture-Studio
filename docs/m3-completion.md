# 完整 M3 完成清单：待验收

依据正式技术计划 §10、§12、§14、§17.2、§17.3 与 §18。此文档是完整 M3 的出口记录；已有 `stage3-report.json` / `m3-browser-report.json` 只证明首个静态 unary RebindInput 片段。103 项测试、一次浏览器提交或同源导出不构成下列缺失运行门的替代证据。

所有新增项先为 pending，取得实际证据后逐项更新。未达到必需门时保留草稿/failed/unknown，不能将 `structural-verified` 自动降级为静态 profile。

## M3 硬出口

| 编号 | 要求与计划依据 | 必需独立证据 | 当前状态 |
|---|---|---|---|
| M3-01 | 至少一种实际连接写回；注册来源/控制/端口/type/shape 合同，§10.3、§17.2 | 明确调用和准确实参 source anchor；producer 支配目标且可引用；不同 named port/ordinal 不混淆；unsupported 明确拒绝 | MHA `key`→ReLU output 实际提交通过；独立关系/字节 oracle 与 `m3-complete-review.json` / commit 收据 |
| M3-02 | 独立完整结构 oracle，§10.6、§11.2–11.3 | 手写 source/bytes/producer-consumer/端口/mask/repeat/sharing/output 预期，在 lowering 前冻结；staged 错改 key/value/mask/第二输出时 gate 失败 | 多输入 oracle、key/value 长度/端口/tuple 第二输出 holdouts 全通过 |
| M3-03 | `structural-verified` 的 G0–G6 相关门必须通过，§12.2 | 源码/名称/完整重分析/独立 delta/shape-type/隔离运行 receipts；运行能力缺失、错误或未知不能进入 ReviewReady | MHA 与 verified activation G6 passed；invalid/missing/tampered runtime 均拒绝 |
| M3-04 | 多输入运行 profile，§17.2、§14.1–14.2 | 同一冻结 input spec 的独立多输入样本；Lq≠Lk 的 MHA q/key/value/mask 角色与实际 shape/dtype；模式、seed、device、构造输入明确 | 通过；见 [m3-complete-original-runtime.json](evidence/m3-complete-original-runtime.json)，q `[2,3,8]` / memory `[2,5,8]` / bool mask `[3,5]`，eval/train |
| M3-05 | 环境与执行隔离，§14.1 | 锁定正式解释器/框架/backend/依赖清单；只读不可变 source generation、独立 writable scratch、默认禁网、timeout 与 memory/CPU/process 限额；真实越界/网络/子进程/资源 probes | 通过；Bubblewrap namespaces/seccomp、host/file/socket/spawn/AS-limit probes 全通过；scope limitations 保留在 receipt |
| M3-06 | train/eval、随机与状态行为区分，§14.2 | train 和 eval 独立执行，模式记录准确；dropout/随机不伪报无条件数值一致；如 profile 要求 gradient，则实际 backward 与失败证据 | eval/train、seed、finite backward/gradients 通过；不宣称 old/new numerical equivalence |
| M3-07 | 结构 replay，§14.2 | 相同 frozen inputs 下对预期调用/shape/绑定的比较；明确 sample trace coverage，不能从一次样本推广为完整程序事实；数值等价只在另声明容差/确定性时验证 | structure/binding/gradients/state replay passed；receipt 明确 sample coverage |
| M3-08 | 模型状态 CompatibilityReport，§14.3 | state_dict keys/shape/dtype、parameters/buffers、tied weights，前后变化与加载策略；optimizer/scheduler/progress/random 状态分别报告，未加载不算验证 | state entries, empty buffers/sharing, checkpointLoaded=false and explicit unprovided external state all reported |
| M3-09 | 完整批准绑定与 freshness，§12.3、§12.4 | approval 绑定 transaction/revision、full corpus/staged、Expected/Observed、运行输入/profile/seed/mode/device/环境/依赖锁与 receipts；改变任一项拒绝或 Stale | input/mode/lock/env/staged role tamper holdouts pass; approved MHA commit is `Committed` |
| M3-10 | 失败、取消与恢复，§12.1、§12.4、§17.2 | runtime timeout/cancel/failure 原件零覆盖；备份、replace、写后验证/进程中断 guards；后续外部编辑不被恢复覆盖；错误状态与 journal 真实 | timeout/cancel, kernel failure and transaction recovery holdouts pass; source bytes unchanged on failed runs |
| M3-11 | 完整具体人审与受管理副本闭环，§12.3、§17.2 | intent/scope、before/after port diff、精确源码 diff、state/runtime gates/unresolved；approve/commit/reanalysis/save/reopen 真实浏览器任务，原导入目录不变 | independent MHA review/approve/commit/reanalysis passed; browser profile task evidence staged separately |
| M3-12 | 制图体验不因审核流程退化，§17.2 | POST structural-rebind-jobs / activation-jobs 返回异步任务；token/project 绑定的 GET runtime-jobs/id 轮询及 POST runtime-jobs/id/cancel；新 prepare/run/cancel/review 页面仍可读；重分析唯一 identity 保留 alias/styles/legend/note/pin/layout，旧任务不覆盖新 revision，当前同源导出有效 | **passed**：异步运行/取消、拖线提案、review 页面与 Studio 14/14/build；视觉属性和注释保留。 |
| M3-13 | 正式发行独立性，AGENTS、§16、§18.3 | 新正式目录 `/tmp` 独立副本运行/构建；实际模块/解释器/框架来源；无失败原型路径；声明能力与真实 profile 一致 | `/tmp/archcanvas-independent-2fyoa8t3` independence/M2/stage3/full-M3 and Studio build passed; UI wording build separately recorded |

## 继承的首期产品欠项

这些项目不能从完整 M3 清单消失。它们分别来自 M0–M2 或 §17.3 的首期最小产品合同；若本轮没有完成，仍须登记未完成，不能以 M3 单一连接闭环代替整个首期产品。

| 编号 | 实际要求 | 当前证据与缺口 |
|---|---|---|
| I-01 | literal/config 参数修改，§17.2 M2、§17.3、§10.4 | 新 `UpdateConfiguration` 只修改同模块唯一顶层 float 定义，并审看全部可分析 Dropout.p/MHA.dropout readers；shared 两次调用、其他 literal 不改、derived/unregistered/hidden/shadow 拒绝的独立 oracle 已通过。派生表达式不改写。完整副本证据重跑中 |
| I-02 | 激活替换，§17.3 与 §10.2 的 P0 ReplaceActivation | 新 `ReplaceActivation` 只支持直接空参 nn.ReLU()/nn.GELU() constructor；精确一个类 token、共享调用全部影响、custom args 拒绝的独立 oracle 通过；Studio/CLI 强制 explicit floating samples + G6，两 mode/backward/replay 实际提交通过。functional/custom activations 不支持 |
| I-03 | 彩色/黑白、单双栏、真实尺寸与出版场景，§17.2 M2、§13.2、§18.1 | **partial**。已现场生成 36 份三 fixture、全部可恢复层级、彩色/黑白×85/180 mm SVG/PNG 并审看，见 `visual-gold-audit.md` / `evidence/visual-golds`。小尺寸最终字号不足，细节页/选区、完整配置与固定浏览器截图/研究者审看未完成 |
| I-04 | 总览、原位多级展开与完整视觉编辑，§17.3 | 实际三 fixture core 多级展开 anchor/pin/折返几何独立通过；Residual CNN 父 growth 缓存缺陷已修，真实源码反例 Node14/14 通过。pin 同轴冲突有明确 warning，不能称无冲突；完整 browser task/性能认证仍缺 |
| I-05 | 共同 Skill + 三宿主按能力打开同一 Studio，§17.2 M1、§17.3 | 本机只有 Codex CLI 0.160.0 可发现；Codex Desktop 实际 Studio 打开已有证据。Claude Code / dsh / deepseek 不在 PATH，实际 discovery/open 未验收。按 §17.4 据实降级，不以官方文档替代宿主认证 |

M4 当前有界 holdout 与 telemetry 实现另记于 [m4-completion.md](m4-completion.md)：独立 PatchVisionEncoder/opaque Conv1d 2/2 通过，但真实运行泛化、固定性能 p95、3–5 位研究者任务完成率、完整视觉出版审看仍 partial/未完成。M5 的全面三宿主 E2E、安装/升级/回滚与 90 秒 Beta 演示仍是后续阶段目标。它们不冒充 M3 的运行隔离/多输入/回放/state report，也不因 M4 holdout 通过而自动完成。

## 独立多输入 oracle

验收自行编写 `/tmp` 模型：`q` 为 `[2,3,8]` float32，`memory` 为 `[2,5,8]` float32，`mask` 为 `[3,5]` bool；`alternative = nn.ReLU(memory)`，`attention(q, memory, memory, attn_mask=mask, need_weights=False)`。只把该调用的 `key` 对应 `memory` Name 改为 `alternative`；`query`、`value`、mask、序列长度语义及第二输出槽 `None` 均不改。MHA `batch_first=True`，头数 2，dropout 明确冻结。

人工预期 source bytes 只改指定 key span；完整静态关系只有该 named key 绑定改变。真实 runtime profile 要记录前后调用角色、shape/dtype、输入 artifact 与种子/模式，在 sampled execution 中核对 key producer 从 memory Input 变为 ReLU output。intent 改变计算行为，不要求与旧 attention 输出逐元素相同；成功 forward/梯度/结构 replay 仅说明声明样本与 profile。

拒绝反例至少包括 K/V length 不一致、query feature 不匹配、错误 dtype/mask shape、目标 port 错选、after-target/不同作用域 producer、未声明输入与环境、不能隔离的 runtime、取消/超时/异常、staged 另一端口被改、运行 receipt/profile/input/env 被篡改与重用批准。负例成功时原文件字节保持不变。

## 证据登记规则

每个运行 receipt 必须记录主体、版本、输入、mode/seed/device、命令/adapter、隔离机制、时间、sample coverage 与限制。`passed`、`failed`、`unknown`、`not_applicable`、`not_run` 分开；进程正常退出不等于 binding replay 通过。不得把宿主 subprocess 或 Python monkeypatch 标成 filesystem/network isolation；缺少隔离能力应禁用对应 profile。

静态事实、sample runtime observations、模型状态、source commit 和视觉导出分别验收。当前总状态：**完整 M3 passed（Linux x86-64 CPU、声明样本与已登记范围内）**。I-03 出版金标准与 I-05 三宿主认证保持 partial/未认证。
