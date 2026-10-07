# 首批实际控制结果

这两份原始收据由 root 通过 IAB 2 的 tab 59 原生 CUA 点击采集；本分析 Agent 没有操作浏览器。工具日志记录创建时 `visible:false`，后续 DOM 记录 visible/focused。**实际外部呈现与窗口遮挡仍未知**，不能把 DOM flags 当作前台呈现认证。

页面是顶层最小控制，没有 React、SVG 模型、产品遥测或模型执行。实际测量矩形为 `1280×576`，位于 `x0,y144`，外页 `1280×720`。Context 指向尚未重建的 `Dzp9we5t/B6WbMowt` 资产；控制页没有加载这些产品资产，这些是服务当时的资产绑定。后续新 build 的 product 记录须独立分组。

| 实际条件 | raw / 严格采集内 rAF 数 | 采集内 callback cadence | 离散输入候选 / matched | 原生指针 down→up |
| --- | --- | --- | --- | --- |
| `control-raf-idle-r1` | 40 / 40 | 1.951719 次/秒 | native 未观测 | native 未观测 |
| `control-full-click-r1` | 41 / 40 | 2.050915 次/秒 | 3 / 3 | 0.700000048 ms |

严格采集内 rAF 同时要求 callback timestamp 与 observedAt 均在预定 20 秒窗口。前者 39 个间隔中 20 个 ≥950 ms、19 个 <25 ms；后者 39 个间隔中 19 个 ≥950 ms、20 个 <25 ms，均没有 25–950 ms 中间间隔。快速的成对 callback 不代表持续高帧率；全体 cadence 仍约每秒两次。

`full` 收据包含 4 个 trusted measured-surface 原生事件：pointermove、pointerdown、pointerup、click 各一次。27 个全部 EventTiming 中 5 个 start 在 warmup、22 个在 capture；14 个 measured-capture entries 中只有与 3 个候选一对一匹配的 3 个 entries，另外 11 个明确保留 unmatched。匹配的 down/up/click 共属于 interaction 4279，各原生 duration 为 **1024 ms**。这只是一个匹配 interaction 的实际报告，不能称为全页 INP 或总体 p95性能。

最后原生输入后、预定 capture 截止前保留约 19011.3 ms；两次固定 drain均存在，buffer drops、observer errors、longtasks为0。直接 callback 成本小、类别嵌套且部分采集外 snapshot 单列；没有 isolate observer、GC、layout、CPU/GPU 或 browser delivery。`raf-idle` 与 `full-click` 操作不同且各只有一次，不能据此估算完整观察器开销。

独立 [analysis-attempt-2/receipt.json](analysis-attempt-2/receipt.json) 为 2/2 raw accounting passed、exit0、4 inputs前后 unchanged；SHA256 `0c66d14aaadf93f3c6fb32001eb677f849828310daf6929354c894f330fb2290`。其前置 attempt1完整保留；attempt2新增了按完整资产集和DPR分组，没有改变 measurement helper。

当前分析器的 [analyzer-negative-attempt-2/receipt.json](analyzer-negative-attempt-2/receipt.json) 证明 12/12实际 raw 的损坏副本被独立拒绝，missing/ambiguous 时长保持 null；SHA256 `55ea045478352173cd66f589135f9b9d9ddbf11e0111c6040f04d97a4135eb92`。这些是证据完整性负例，不是新浏览器试次或产品性能测试。

首批结果支持继续排查浏览器 surface/环境调度：极小控制也有慢 callback 与 1024 ms 原生 duration。它未定位命名的后台策略、未证明产品快慢、未完成计划的三次匹配复现，也未认证真实呈现、字体环境、性能门槛或真人体验。M4 仍 partial。
