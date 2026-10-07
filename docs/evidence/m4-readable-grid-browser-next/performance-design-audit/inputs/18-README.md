# 当前性能条件：独立只读审计

当前 DuFX 两段小图采样均有 2/2 唯一匹配的有效展开/收起，Event Timing 的匹配子集 p95 都为 **40 ms**；rAF 回调时间戳 cadence 都约 **60.002 Hz**。这没有复现 D60 的 1008 ms / 约 2.02 Hz 历史诊断。两份 `*-before.json` 的宿主能力读数实际都为 `false`，页面都报告 `hidden=false`、`visibility="visible"`；因此第二段 `shown-request` 不是成功建立可见条件的 A/B。旧慢样本不被删除，也没有获得原因认证或 300 对象性能通过结论。

审计仅新增本目录，未操作浏览器、服务、产品源代码或测试。独立计算器 [review.py](review.py)、完整分母与计算 [independent-statistics.json](independent-statistics.json)、[输入字节收据](receipt.json) 可复查；34 份输入在读取前后 SHA256/长度一致，归档副本完全相同。输入包括正式 Skill/AGENTS、技术计划、当前采集器及 DuFX JS/CSS、旧原始收据和新 raw；后续 root 的冻结报告不属于本次快照集合。脚本拒绝覆盖归档副本。

## 不同指标的证据范围

正式计划 18.5 将这些列为 beta 目标而非既有数据：300 可见对象 input-to-paint p95 ≤50 ms、交互目标 ≥50 fps；中等子图增量处理 p95 <500 ms；屏幕锚点误差 ≤8 px、无关 pinned 位移 0；固定机器/浏览器/图规模，低配置另报；3–5 名真实研究使用者。真实尺寸 85/180 mm 的人工审看亦单列。

| 样本 | 唯一匹配的有效展开输入 | 匹配子集 duration p95 | rAF 回调 cadence | 间隔 p95 |
|---|---:|---:|---:|---:|
| 历史 D60 | 2/2 | 1008 ms | 2.021358 Hz | 983.4 ms |
| DuFX hidden | 2/2 | 40 ms | 60.002456 Hz | 16.8 ms |
| DuFX shown-request，实际 before=false | 2/2 | 40 ms | 60.002462 Hz | 16.7 ms |

DuFX 每段都只切换 Encoder 的 12→14→12 个可见节点，没有 pin。每段原始 PerformanceObserver 数组各含 83 个条目和 3 个正 interactionId，包含开始/结束等控件事件；采集器仅记录 2 个展开 trial。83 不是 83 个独立交互，2 个 trial 也不是全部原生输入分母。此采集器没有完整 native input log；低于 16 ms 阈值或未交付条目仍未知。它无法给出全页 INP、连续拖动/滚轮 input-to-paint、实际呈现 FPS、300 对象行为或真人结果。

独立计算完整的两侧候选关系后，全部 6 个历史/当前 trial 的存储匹配相等，数量和 p95 相等。规则是 trusted、同名事件、同 canonical target、正 interactionId、时间差 ≤8 ms、合法处理时间和有限非负 duration；双方唯一才匹配。还检查同 document/source/IR、revision 恰好 +1、目标 expanded 状态与操作一致。几何读取边界的“两次 rAF”不是 latency。

## 慢节奏与可见性不能直接归因

D60 的两次 native queue 约 0.2 ms，processing 26.8/17.3 ms，但 duration 均 1008 ms。剩余时间未分解到 compositor、GPU、paint 或宿主调度。新 DuFX processing 为 23.7/17.7 和 16.9/15.1 ms，queue 约 0.1–0.2 ms；不同 build、时间和窗口条件阻止跨样本因果比较。

旧最小控制页没有 React、产品 telemetry、模型或 Studio renderer，仍出现约 16.7/983.3 ms 成对间隔。固定 20 秒 capture 的严格 timestamp+delivery 分母：raf-only idle 40 帧、1.951719 Hz；full click 40/41 原始帧、2.050915 Hz；full idle 40/41 原始帧、2.050926 Hz。点击模式有 4 个 trusted measured inputs、3 个 discrete 匹配、共一个 matched interactionId；27 个原生条目包含 warmup/非目标事件。idle 模式的 5 个原生条目全部开始于 warmup，目标输入为 0。不得用它们补产品样本或减掉“控制耗时”。

另一个旧 20,000.4 ms 最小控制窗口也有 40 回调、约 2.050915 Hz、间隔 p95 983.4 ms。宿主在开始前约 0.484 秒及结束后约 54.564 秒各读 `true`，只证明两个观测时刻，不证明连续呈现。旧 true+慢与新 false+快共同阻止把宿主 boolean 当成已隔离的调度原因。DOM visible/focused 同样不证明宿主窗口、WebContents、遮挡状态或真实显示刷新。该旧控制没有 longtask 订阅，不能说无长任务。

## 采集开销与遗漏

`nativePerformance.ts:69–87` 的 `readScene` 解析 metadata，扫描每个可见 SVG group，读 body/`getScreenCTM` 并转换坐标，再扫描/sort visibleIds。捕获阶段（115–139）还扫描层级、过滤 pins，并在应用 handler 前执行一次 `readScene`、更新 React progress；两次 rAF 后再读一次并更新 progress。DOM/CTM 读可能要求 style/layout，规模随对象数增长，但源码没有围绕这些读的开销计时，因此量化成本未知。主 rAF 链仅存时间戳，没有逐帧全图读取。

telemetry 的 longtask/EventTiming observer 在模块加载时存在，条目各限 200；只有 `visibilitychange` 监听，focus 在起止/visibility 记录中采样，未监听 focus/blur。`snapshot/reset` 不调用 `takeRecords`；native stop 直接快照，无法证明所有延迟交付条目已摄入。两次 rAF proxy、panel 计数 state 更新及固定 overlay 均可扰动诊断窗口。`frames.fps` 字段公式是回调 cadence，本审计从不称其为呈现 FPS。

旧控制直接测得的 frame/input/geometry 自身局部成本最大约 0.1 ms，PO 最大约 0.2 ms；frame 包含内部 geometry，类别重叠不可相加。低成本不证明无扰动，更不能外推正式 `readScene` 在 300 对象的成本；有限时钟精度下的 0 不等于零开销。独立 full 控制具备 capture/final 两次 `takeRecords` 与固定 2 秒 drain，但无法强制浏览器完成条目。

## 下一步诊断的前提

先取得并记录确实改变的宿主条件，固定同一 Studio URL/assets/document/IR/相机、viewport/DPR、同一 observer 和 native 操作，预先确定 warmup/capture/settle/drain，并保留未达到条件、取消和无输入尝试。每条件至少三次并交替顺序，禁止只保留最快窗口、任意延长慢样本或减控制耗时。最小 raf-only 与 full 模式能帮助判断 observer 扰动，实际 Studio 仍要单测。

完整性能门还需要固定字体字节/硬件/电源环境、300 可见对象、全部输入和缺失分母，以及同一 Studio surface 的实际呈现反馈与输入响应关联。BeginFrame、rAF、Paint、提交或 JPG 到达各自不足以证明显示帧。当前 A/B 条件未建立、原因未确定、presented FPS 未认证、真人为 0；M4 保持 partial，M5 不因本报告推进。
