# 可见宿主能力读数包围的简单控制窗口

本目录封存一次代理操作的简单控制页诊断：20,000.4 ms 内记录 40 个 rAF 时间戳；3 个可信目标输入中 2 个唯一匹配到同一个原生交互，duration 为 1016 ms。宿主能力在窗口之前和之后各返回一次 true。它们是两个离散读数；原始验证器没有摄入该独立文件，保留 `hostPresentation: "unconfirmed"`。

## 原始资料与绑定

- [原始收据](raw.json)：本次浏览器控制页捕获，未修改。
- [离线验证结果](validation.json)：由 [独立控制验证器](../../../scripts/validate_scheduling_control.mjs)生成，未修改；其 `inputBinding` 绑定本目录原始收据。
- [宿主能力观测](host-presentation-observations.json)：浏览器 2 的两个外部能力读数，未修改。
- [封存清单](manifest.json)：绑定以上文件、本 README、验证器、收据声明的当前产品资产及探针源码；同时记录只读冻结核查。SHA256 绑定字节，不能独立证明历史执行过程、参与者身份或截图内容。

本控制页的 [control.mjs](../../../scripts/m4_input_support/control.mjs)没有运行 Studio，也没有导入收据上下文列出的独立 Studio 输入探针。上下文中 3 个产品资产与 6 个探针源码的字节均匹配当前磁盘，验证器和原始收据的绑定亦匹配。该对照只说明当前文件一致，不能作为 Studio 工作负载或历史执行认证。

## 回调时间戳

| 项目 | 本窗口结果 |
|---|---:|
| 窗口 `stoppedAt - startedAt` | 20,000.399999976158 ms |
| rAF 时间戳 / 相邻间隔 | 40 / 39 |
| exact session 回调速率 `40 × 1000 / windowMs` | 1.999960 Hz |
| 首末时间戳间隔 cadence `39 × 1000 / (last-first)` | 2.050915 Hz |
| 间隔 p50 / p95 / p99 / max | 16.7 / 983.4 / 983.4 / 983.4 ms |
| ≤20 ms / >500 ms 间隔 | 20 / 19 |
| >100 ms 间隔 | 19 |
| 完整一秒桶 | 20 桶，每桶 2 个回调 |
| 最后 0.4 ms 尾桶 | 0 个回调 |
| 第一帧距开始 / 末帧距结束 | 981.994 / 2.5 ms |

分位数使用 nearest rank，毫秒舍入到 6 位小数。这些是 rAF **回调**时间戳，不能当作实际呈现帧率、持续 FPS、掉帧数或连续输入到绘制的延迟。验证结果的 `presentedFrameRateHz` 和 `estimatedMissedPresentedFrames` 都为 null。

## 可信目标输入与原生 EventTiming

验证器要求相同 type / target、时间差 ≤8 ms、正 interactionId，并在两个方向都只有一个候选；不会贪心配对或补造缺失事件。

| 捕获事件 | native index | interactionId | duration | queue / processing |
|---|---:|---:|---:|---:|
| pointerdown | null | null | null | null / null |
| pointerup | 11 | 1221 | 1016 ms | 3.6 / 0 ms |
| click | 13 | 1221 | 1016 ms | 3.6 / 0.2 ms |

三条原始输入均为 trusted 且指向 target。pointerup 和 click 共用一个 interactionId，因此只有 **1 个已匹配交互**，不是两次交互。匹配子集的 p95=1016 ms，但单样本不构成代表性 p95、整个页面 INP 或 Studio 性能判断。pointerdown 没有原生条目，不能将其解释为 0 ms、低于阈值或通过；`allCapturedEligibleInputsMatched` 为 false。

原始 PerformanceObserver 条目共 15 个，13 个未匹配目标输入。start 按钮的两条离散原生记录没有对应的 captured start inputs：记录窗口在 start handler 内建立，此前 capture listener 已返回。它们不构成目标交互。`overallPageInpMs` 与 `continuousInputToPaintMs` 保持 null。

## 两种环境证据的范围

页面环境是 Chrome 154 / Linux、1102×905、DPR 1、hardwareConcurrency 16；窗口开始和结束的 document 状态均为 visible/focused，`environmentChanges=[]`，无标记截断。

| 外部读数 / 原始窗口 | UTC 时间 | 相对窗口 |
|---|---|---|
| beforeStart，true | 2026-10-04T17:40:05.851Z | 比开始早 483.9 ms |
| `timeOrigin + startedAt` | 2026-10-04T17:40:06.334900Z | 开始 |
| `timeOrigin + stoppedAt` | 2026-10-04T17:40:26.335300Z | 结束 |
| afterWindow，true | 2026-10-04T17:41:20.899Z | 比结束晚 54,563.7 ms |

这些外部读数包围窗口，未连续追踪宿主呈现；后一个读数不紧接窗口结束。验证文件的 `visibilityInputBinding=null`、`externalVisibility=null`、`hostPresentation="unconfirmed"` 表明该独立观测文件没有作为此次验证器输入，并不否定两次 true。此封存保留两份资料原状，不把它们改写成宿主呈现认证、锁定原生环境或调度恢复的因果证据。

## 探针成本及限制

rAF 40 个局部成本样本总计约 0.100000024 ms；input 3 个总计 0；PerformanceObserver 消费循环 3 个总计约 0.300000072 ms。它们不包含浏览器 observer delivery、成本 append 本身、目标 click handler、rAF rescheduling、计时器、渲染或其他工作。finish 时也调用 consume(takeRecords)，所以 PO 成本样本数不是异步回调次数或条目数。时钟精度下的 0 不等于零开销，`wholeObserverOverheadMs=null`、`schedulingCauseEstablished=false`。

原始收据没有 longTasks 字段，控制模块没有订阅 longtask，不能得出“无长任务”。该窗口不提供固定字体环境、连续宿主呈现或生产性能认证，也不建立可见性请求、窗口大小与调度模式之间的因果关系。

## 冻结与真人门槛

封存时只读核对 [真人试验包清单](../../../.archcanvas/m4-research-trial-zoom-final/manifest.json)：55/55 实现文件、4/4 baseline、5/5 slot envelope 的 SHA256 与字节数全部匹配。清单 SHA256 为 `daeaec0137a0950ca93ca904574987e298f68eb45e6990fd3326d9be37f365b0`；冻结生产 JS 为 `2e77f8616f8408afc985740e77b6a69c7728816f7ec4231f0ee7fe9224752e9f`。

S01–S05 仍 unassigned，每席只有 baseline 文档与 pending review-template；participantCode/reviewer 为 null，没有 assignment、collected、incoming 文件、导出文件、独立 review 或实际 environment.json。storage revision=1、visual revision=0。真人研究者仍 0，researchGate=not_run。此只读库存按 manifest 的检查时刻记录，后续真人输入应重新核查。

本诊断不增加真人结果、独立视觉通过结论或性能通过结论。`humanCertified`、`studioPerformanceCertified`、`presentedFrameRateCertified`、`hostPresentationCertified` 均为 false。本次封存仅新增本 README 与 manifest，没有重跑浏览器、测试、构建或修改原始收据、验证结果、产品与其他证据清单。
