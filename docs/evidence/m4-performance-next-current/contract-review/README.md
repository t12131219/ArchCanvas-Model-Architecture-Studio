# M4 性能测量合同与 observer 停止边界

本轮先只读核查正式计划 §9.7、§18.1、§18.5 与当前采集器，再按根 Agent 的限定授权修复已经排队的 PerformanceObserver 条目在快照/reset 边界遗漏或串窗的问题。只改 `studio/src/perf.ts` 和新增 `studio/tests/perf-observer-boundary.test.ts`；未改 native trial 匹配、validator、产品 schema、浏览器、服务、dist 或历史证据。真人仍为 0，M4 性能门仍未通过。

修复前的 19 份输入已逐字节归档，读取后立即复核全部一致，见 [input-receipt.json](input-receipt.json)。它们是审核时的快照，不能在后续并行修改后称为当前源码。正式产品没有使用 Temp runtime 或导入/执行模型；Node 执行测试与 TypeScript 检查，普通 Python 仅作字节/hash/报告记账。

## 已实现的严格限定修复

`snapshot()` 先调用两种 observer 的 `takeRecords()`，然后用 callback 相同的 ingest 路径摄入已经排队的条目。`reset()` 先丢弃当前 queue，再设置新的 monotonic startTime 窗口；晚到 callback 中开始时间早于窗口的条目被丢弃。窗口按条目的开始时间归属，跨 reset 的旧 longtask/event 不计为新窗口输入。仍保留 schemaVersion 1、16 ms Event Timing 阈值、8 ms 量化和最后 200 个交付条目的保留策略。

这修复的是 **已经形成且已排队** 的条目。`takeRecords()` 不会强制浏览器完成尚未绘制、尚未形成或尚未交付的 Event Timing，也没有将当前 2 rAF 空间边界改称 input-to-paint。native session 的同步 `stop()` 仍没有固定异步 settle/drain 协议；本轮不能声称完整停止分母已建立。摄入额外 queued 条目也可能令 snapshot 更慢；没有从原生 duration 中减去任何采集开销。

四个手写 oracle 分别检验：snapshot 摄入 queue 且 callback 后不重复；reset 丢弃旧 queue；reset 后晚到 callback 丢弃旧条目并保留新条目；callback 与 queue 使用一致的最后 200 条保留边界。fake observer 将 queue 与 callback 交付分离，并模拟 canonical target。

| 验证 | 结果 | 原始证据 |
|---|---|---|
| 修复前正式源码上的新四项边界测试 | 0/4，均为断言失败 | [before-test-attempt-2.txt](before-test-attempt-2.txt) |
| 归档旧源码的独立重放 | 0/4，均为相同产品反例 | [before-frozen-reproduction.txt](before-frozen-reproduction.txt)、[before-oracle.test.ts](before-oracle.test.ts) |
| 修复后四项＋原有 perf/native/matching | 24/24，0 skip | [after-focused-tests.txt](after-focused-tests.txt) |
| 严格 TypeScript `--noEmit` | exit 0 | [strict-typescript.txt](strict-typescript.txt) |

初次测试使用了 strip-only 不支持的 TypeScript parameter property，未进入四个产品测试。这个测试构造错误保留在 [before-test-attempt-1-syntax-error.txt](before-test-attempt-1-syntax-error.txt)，纠正后才取得修复前 0/4。专项 24/24 包含新四项，不是额外再加四项；本 Agent 未执行全套或 build/dist。

## 下一步可以实现的测量缺口

1. **完整原生输入账本。** 当前 `nativePerformance.ts` 仅捕获展开 click/pointerdown，至多 100 个 trial；它不是所有输入分母。应在 opt-in 诊断窗口内记录预先列明的 trusted discrete/continuous 事件（pointer down/up/cancel/move、click、键盘、wheel 等），保留 sequence、原始/归一化 timeStamp、pointer/key 身份、目标 canonical ID/控件类别、phase、capturedAt。同一次 pointer gesture 的 down/up/click 与 interactionId 要分组，不能分别当三个研究者操作；连续 move/wheel 与离散 Event Timing 分开。无 native timing 的输入保持 missing/unsupported，不能记成 0 ms 或 below-threshold 成功。记录 total、retained、overflow/dropped，截断时完整性为 false；禁止由最后 200 条倒推出全输入数量。
2. **固定停止协议。** 明确 capture start/end、settle/drain 时长和实际边界。请求停止时移除 capture listeners、记录 captureEndedAt；observer 保持订阅至 drainEndedAt。开始/结束各 drain，最终 drain 后才封存。每条 raw timing 保留 deliveryAt/phase，按 startAt 决定 capture 归属；warmup、结束按钮与窗口后输入单列，而不是混入性能分母。延迟几何未完成、取消、缺失条目、超时与 overflow 必须保存。固定等待不会保证所有未来条目，receipt 必须据实标记；每次不能任意延长直到最快样本出现。
3. **readScene/React 测量开销。** 当前捕获阶段在产品 handler 前扫描全部 SVG、metadata 与层级，读每个 body 的 `getScreenCTM`；两次 rAF 后再次全图读取，进度回调触发 React 更新。分别用 `performance.now()` 记录 scene read、capture 总耗时、pending callback/ingest/progress 调用耗时，注明重叠项不可相加，有限时钟精度的 0 不是零成本。不从原生 Event Timing 减开销。可将性能窗口的 before binding/visible IDs 缓存到已提交场景版本，将 anchor 读取限定到目标和无关 pins；完整起止 scene/counted viewport snapshot 单独取。优化后仍需验证 revision、source/IR、屏幕锚点与 pin 几何，不得从 DOM 读取退化成预期 JSON 自证。
4. **300 可见对象的严格场景。** 当前 `visibleIds` 只是 SVG DOM frontier `[data-canonical-id]` 的节点数，没有 viewport 相交、边/图例/注释类别或遮挡证据。建立 source-backed、无专用模板的固定 workload，保留来源/静态事实与 CanvasDocument 的 digest。预定义 object 类别，分别报告 rendered canonical nodes、tensor edges、legend/annotations 和 viewport-intersecting bodies；避免 port 子元素的 `data-node-id` 重复计数。至少有 300 个实际 viewport 内对象的样本才能支撑这项门；root 应先明确计数定义，不能让 12→14→12 或页面外 DOM 节点数冒充。记录实际 viewport rect、相机/缩放、DPR、字体状态/字节和截图；适配画布将 300 对象缩到不可读亦应保留为体验失败。
5. **实际呈现帧。** 当前 `frames.fps` 公式是 rAF callback cadence；Event Timing 给离散事件到下一次浏览器 paint 的 duration，但不认证连续 pointermove/wheel 或显示器实际呈现 FPS。可以增加明确名 `callbackCadenceHz` 并保留原字段兼容，`presentedFps` 保持 null/unsupported，禁止以 Paint/BeginFrame/提交/截图代替 presentation。已有 capability audit 未取得可调用 trace/CDP 采集能力；有实际操作者 trace 后，先验证同一 Studio surface 的 frame-sequence presentation feedback 与输入响应 flow，才扩大试次。
6. **固定环境、重复与真实研究者。** 同一 build/source/IR/document、viewport/相机、字体字节、硬件/电源与原生操作矩阵先固定，至少三次并保留全部尝试及失败。AI `isTrusted=true` 不证明真人；3–5 研究者、180 秒任务、85/180 mm 真人审美/连线审看仍需独立记录，不能由本报告或 24 项测试替代。

## 现有独立 validator 的范围

`validate_native_performance.mjs` 独立重建 trial↔entry 双向唯一候选关系，检查 scene/source/IR/revision、展开状态、anchors/pins 坐标空间与 rAF 公式。这些合同保持原样。它只证明 receipt 的内部一致性，未读取完整输入账本、固定 stop/drain、observer overflow、采集开销、viewport 300 对象或真正 presentation stream。下一版协议需要独立增加这些 raw/summary 反例；不能在现有 schema1 上新增一个宽松 `passed` 布尔值解决。

DuFX 两段 2/2 native 展开样本、匹配子集 p95 40 ms、rAF 约 60 Hz 是历史小场景诊断。两段宿主 getVisible 都为 false，`set(true)` 请求没有建立新的 A/B 条件。本 Agent 没有重做这个失败的可见性实验，未操作浏览器或系统设置，旧 D60 1008 ms/约 2 Hz 失败保持原样。

重放旧源码：`node --experimental-strip-types --test --test-isolation=none docs/evidence/m4-performance-next-current/contract-review/before-oracle.test.ts`。修复后专项：在 `studio` 运行 `node --experimental-strip-types --test --test-isolation=none tests/perf-observer-boundary.test.ts tests/perf.test.ts tests/native-performance.test.ts tests/native-matching-independent.test.ts`。
