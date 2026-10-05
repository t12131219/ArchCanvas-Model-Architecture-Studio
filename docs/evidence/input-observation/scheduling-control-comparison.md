# 简单页面调度对照的独立离线校验

两份 20 秒原始窗口均存在约一秒的 rAF 间隔和一次长 EventTiming 目标交互；第二份后六秒的回调节奏加快。这说明同一浏览器环境的简单页面也出现了调度异常，不能将 Studio 中的类似现象直接归因于 React、SVG 或模型代码。它同样不能证明宿主已经可见、可见性请求造成恢复、或 Studio 已满足性能目标。

输入是 [background 原始收据](simple-control-background.json)、[visibility-request 原始收据](simple-control-visibility-request.json) 和[外部可见性操作收据](browser-visibility-observation.json)。输出是 [background validation](simple-control-background-validation.json)、[visibility-request validation](simple-control-visibility-request-validation.json)。[独立验证器](../../../scripts/validate_scheduling_control.mjs)只读取 JSON 和声明文件字节，不导入 control、observer、Studio 或浏览器；本次没有重新测量、生产构建或运行工程回归。

## rAF 全窗口与差分

百分位采用 nearest rank，排序后取 `ceil(n×p)-1`，展示到六位小数。相邻 rAF 时间戳反映回调节奏，不是 presented frame rate；完整窗口回调率和首末时间戳差分率使用不同分母，两者都不能替代显示帧率。

| 指标 | background | visibility-request |
| --- | ---: | ---: |
| session 时长 ms | 20000.4 | 20000.2 |
| 原始 rAF 时间戳数 | 40 | 384 |
| 相邻差分数 | 39 | 383 |
| 差分 min / mean ms | 16.6 / 512.371949 | 16.5 / 52.130026 |
| 差分 p50 / p95 / p99 ms | 983.2 / 983.4 / 983.4 | 16.7 / 16.8 / 983.3 |
| 最大间隔 ms | 983.4 | 1000 |
| 大于 100 ms 的间隔 | 20 | 14 |
| 全 session 回调数 / 秒 | 1.999960 | 19.199808 |
| 相邻回调差分率 / 秒 | 1.951707 | 19.182803 |

从 `startedAt` 起算，20 个完整一秒桶的回调数为：

```text
background:
[2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2]

visibility-request:
[2,2,1,2,2,2,2,2,2,2,2,2,2,2,59,58,60,60,60,60]
```

末尾不足一秒的桶分别仅 0.4 / 0.2 ms，均为 0 回调，validation 明确标为 partial，不能混入完整秒桶分布。第二份前 14 个完整秒桶有 27 回调，后六桶有 357；全窗的 p95 16.8 ms 会掩盖前段停顿，不能称为持续 60 FPS。validation 保留每个大于 100 ms 间隔的原始起止及索引，没有估算“丢失呈现帧”。

## 可信目标输入与原生 EventTiming

仅匹配 raw 中 `trusted=true`、`targetId=target` 的 pointerdown/pointerup/click。候选须同类型、同目标、startTime 与原始 at 相差不超过 8 ms，且是正 interactionId。只有候选唯一、该候选也只被一个 captured raw 输入竞争时才接受；不使用先到先得匹配。当前六个匹配的 startTime 差实际均为 0。缺失、多个候选、多个 raw 竞争、unsupported 或截断均保留 null，不将缺失解释成 0 ms 或低于阈值。

| 目标输入 | background | visibility-request |
| --- | ---: | ---: |
| raw 可信 down / up / click | 1 / 1 / 1 | 1 / 1 / 1 |
| 唯一匹配 | 3 / 3 | 3 / 3 |
| 观测到的 interactionId | 5238 | 5259 |
| 每项原生 duration ms | 1000 | 2016 |
| native input queue ms（down/up/click） | 0.1 / 0.2 / 0.2 | 0.3 / 0.2 / 0.2 |
| native processing ms（down/up/click） | 0.1 / 0 / 0.2 | 0 / 0 / 0.2 |
| PO 总条目 | 19 | 67 |
| 不关联目标 raw 的 PO 条目 | 16 | 64 |

每份是一次 interaction 的三种事件，不是三个独立试验。阈值为 16 ms，duration 按 8 ms 网格记录；这一次匹配子集既不是整页 INP，也不是连续拖拽 input-to-paint 测量。validation 将这些未测量指标保留 null。

每份都有三个 start 按钮的离散 PO 事件，但 raw start 输入为 0。control 的捕获监听器在 start handler 建立 session 前返回；同一 task 内随后创建的 observer 仍可能收到该 task 的 start PO 条目。因此验证器只从真实 captured target raw 建立匹配，未用 PO 补造 start 或其他操作。

## callback 成本与环境

| 内部成本样本 | background：n / sum / max ms | visibility-request：n / sum / max ms |
| --- | ---: | ---: |
| rAF | 40 / 0.1 / 0.1 | 384 / 1.1 / 0.1 |
| input capture | 3 / 0.1 / 0.1 | 3 / 0 / 0 |
| performance consume | 3 / 0 / 0 | 6 / 0.1 / 0.1 |

这些只量到源代码中的 append/consume 区段：不包含成本记录本身、rAF 重约、浏览器 observer delivery、目标 click handler、定时器、样式/布局/绘制或整页 CPU。零值可能受时钟分辨率影响，不证明零开销。finish 还调用 `consume(takeRecords())`，样本数不能等同异步 PO delivery 次数，也不能用小样本成本确定一秒调度间隔的原因。

两份文档 begin/end 均为 visible/focused，没有环境变化或截断。viewport 为 1280×720 / 1102×905，DPR 均 1，hardwareConcurrency=16、timeOrigin 相同；这不构成完整硬件、浏览器或字体锁定。外部 capability 在 `set(true)` 前后都返回 false，且收据不是连续同步的宿主呈现跟踪。内部 visible/focused 不证明宿主可见，目录名 background/visibility-request 也不能作为实测宿主状态。

validation 逐项比较了 receipt 声明与当前文件：三份 production dist、harness、control.html、control.mjs 共六项 hash/bytes 相符。context 另列的 `scripts/m4_input_observer.mjs` 是 15711 bytes / `007bcb667be4f2cdfed5f56d79bbe5ba27a5a03cf641e00230531bc6afd57c1a`；核查时当前文件为 15723 bytes / `fb409d86902457647f7506028623343492a7e6f4d39de346ed9a3906cb84c9af`，因此 `allDeclaredFilesMatchCurrent=false`。control 本身不导入该独立 Studio observer；保留该旧上下文绑定，不将所有来源声称为当前 unchanged，也不将无关 observer 变化推定为 control raw 失效。原始收据和冻结 production 文件未改写。

## 验证与范围

```bash
node --test --test-isolation=none tests/test_scheduling_control.mjs
node scripts/validate_scheduling_control.mjs \
  docs/evidence/input-observation/simple-control-background.json \
  --visibility docs/evidence/input-observation/browser-visibility-observation.json
node scripts/validate_scheduling_control.mjs \
  docs/evidence/input-observation/simple-control-visibility-request.json \
  --visibility docs/evidence/input-observation/browser-visibility-observation.json
```

11 项独立测试通过，覆盖双向匹配歧义、缺失/unsupported、start 无 raw、错误目标/类型/时间/interaction、synthetic input、截断、时钟与成本计数、部分窗口以及宿主可见性不被认证。另一 agent 从 raw 独立计算的秒桶、百分位、目标交互、成本与来源与两份 validation 相符。

本对照只能记录这两个窗口的简单页面调度节奏、一次可信目标交互及有限探针区段成本。不能从两次非随机窗口确立 visibility/viewport 因果关系，不能认证 Studio native 输入性能、持续呈现帧率、真人任务、字体环境或人工视觉验收。
