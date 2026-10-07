# 下一轮真实性能门：能力与合同审计

结论：现有受支持工具能取得真实 **离散输入的 Event Timing → next paint**，可关闭预先声明的点击/键盘交互子项；不能取得连续 pointermove/wheel 的呈现延迟、持续 presented FPS，或在鼠标仍按下时发出 Escape/blur 的取消样本。继续采相同 rAF/DOM proxy 不会关闭后三项门。本轮只读源码、文档、工具元数据和主机事实，未操作共享浏览器、运行模型、重建、安装或改冻结文件。

## 必须保留的目标

正式计划 §9.7、§18.1 要真实 input-to-paint、长任务、帧率和屏幕锚点。§18.5 的 Beta 目标是 **300 可见对象 p95≤50ms、≥50fps**，中等展开 p95<500ms、屏幕锚点≤8px、无关 pin 位移0；不是100ms。100ms可以另报诊断比较，不能替换50ms，也不能把 Beta 数值重新编成原计划没有的 M4 硬门。`docs/m4-input-observation.md` 首段仍绑定历史 Cr_x 构建，不能当作 ChS 性能证据。

| 门/事实 | 本环境真正可取得的证据 | 当前缺口与下一行动 |
| --- | --- | --- |
| 离散 Event Timing | 受支持 native click/pressKey 的可信事件；独立 v2 observer 收原始 entry、interactionId、目标 token、时钟；validator 双侧唯一匹配并按 interaction 最大 duration 去重 | ChS 尚无本轮 trial。应在已经展开的304对象场景测预声明离散操作；4→304 toggle只能证明展开子项。所有预声明试次必须有实际 scene 变化与唯一匹配，缺失保持null，不能只挑较快子集关总体门 |
| 完整应用采样缓冲 | v2 每个实际写入 list 有limit/dropped，stop drains `takeRecords()` | `completeBuffers`仅表示所列应用 list 无drop。当前validator允许漏报部分/全部buffers，并不证明浏览器内部PO无丢失。下节给出具体新协议补丁候选 |
| 环境身份 | 独立 support 页可把当前同一IAB的UA、DPR、viewport、supportedEntryTypes显示为公开DOM，并与正式页当前bundle/时间关联；host CPU/内存/OS/字体文件可只读登记 | 同一UA不是浏览器二进制版本锁定；support页不是正式iframe即时viewport。UA、外页与iframe各自采值。未取得浏览器实际glyph字体、GPU呈现路径或刷新率 |
| 长任务 | `PerformanceObserver('longtask')`原始≥50ms任务/attribution，能力标志和同操作窗口过滤 | unsupported必须null；0条只说明未观察到该类任务，不说明系统无停顿。PO内部drop情况另列 |
| 屏幕连续性 | 真实操作前后SVG端点/CTM、viewport、camera、target与至少一个无关可见pin；完整SVG/保存链 | 终点几何不能替代paint。pins为空或离屏不能计pin0。外页滚动与iframe screen坐标要分别记录 |
| 持续 presented FPS | 当前 API 无 compositor/presented trace | 官方CUA只有完整drag/scroll/click/pressKey；Tab.dev只有logs，capabilities仅visibility/viewport/pageAssets/WebMCP。无trace/profiler。rAF回调频率、截图间隔、视频文件FPS都不是呈现帧计数。需要受支持的浏览器原生trace或真人在已声明浏览器的DevTools Performance录制，再离线核trace；不得绕过CUA接CDP/private API |
| held-pointer取消 | 产品有Escape/blur/pointercancel/lostcapture代码路径，v2能记录取消事件与同pointer facts | 当前CUA drag是完整手势，没有独立down/move/up；不能在hold期间插Escape。两条工具调用并发不构成可审计held状态。需受支持held输入能力或真人按住→移动→Escape→释放，保留原生事件顺序和前后文档/相机/历史事实 |

CUA能力清单来自主代理本轮读取的官方API文档摘要；本代理未重置或选择共享浏览器来再次探测。`functions.exec`可调用工具元数据检索没有trace/profiler/heldpointer接口，`open_in_codex`仅展示面板。这是已公开API范围，不能据此声称机器不存在任何浏览器诊断功能。

## 优先代码候选：完整性协议，而非新proxy

保持既有 v2 observer/validator及失败raw原字节不变；若实施，应新建协议/文件或新版本快照，并重新核其独立反例，不把旧v2 receipt重新标成新协议通过。以下是关闭完整性缺口所需的最小改变：

1. **预初始化全部缓冲清单。** 固定注册 `events, frames, eventTiming, longTasks, visibility, errors, overhead.sceneReads/inputCallbacks/frameCallbacks/performanceCallbacks`；即使零条也有limit、stored、seen、dropped。核 `seen=stored+dropped`、array.length=stored、完整required key集合；漏项、未知替代项、任一drop都不能得完整。现v2 `completeBuffers`保留原“已报告应用缓冲”含义。
2. **分开应用与浏览器内部完整性。** PO回调若通过实测支持的标准metadata提供 `droppedEntriesCount`，记录原值、能力、累计/增量合同和观察时点。当前回调只收`list.getEntries()`，没有该证据。若API不暴露或无法确定其计数合同，应填`null/unknown`，不能填0；`takeRecords()`仅drain队列，不证明此前无drop。没有内部完整性也可认证全部唯一匹配的**明确试次子集**，不能宣称完整页面/全native latency。
3. **把trial纳入分母。** 预声明操作与304可见对象状态，选定node/control、窗口、target/anchor/pin；结果拒绝no-input、wrong-target、跨document/source/revision、多操作合并、不完整buffer、失败geometry和未匹配/歧义。仅计算有效trial对应的matched interaction；现v2 session-levellatency会汇总窗口内所有eligible离散事件，不能直接充当预声明trial的p95。
4. **停机与能力缺失必须显式。** 在容量阈值前自动停止/分批，而不是满后只留下前段；保存原始停止原因。每批尽量短并保留所有批次，包括失败/慢值。高刷机器20–30秒也可能超过10k回调，不能靠固定秒数保证完整。能力/错误/浏览器内部状态未知时给unknown，而不是强行得到绿色。
5. **认证层与诊断层分开。** 一个新的独立gate核全部预声明试次、buffers完整性、环境绑定、正interactionId、双侧唯一匹配、interaction去重、量化边界、source/scene。纯一致性validator应继续输出engineering，不自动升级整体INP、continuous paint、硬件字体锁定或M4通过。负控至少破坏漏buffer、silenttrim、browserdrop未知/非零、双向歧义、out-of-window事件、300对象不足和no-input试次。

`nativePerformance/1`不是首选：它仅toggle；底层`perf.ts`对Event Timing/longtask/visibility超过200默默trim，没有丢弃计数；native join是逐trial贪心匹配，不能证明双侧唯一；frame只用length==20k标记，独立validator没有拒绝上述silenttrim/截断。独立v2 full更强，但仍需要上述完整性认证层。

Event Timing是16ms阈值、8ms量化数据。missing既可能低于阈值，也可能detached/歧义/截断，不能一律当0或<16ms。临界duration必须按浏览器已证明的量化合同给边界；若只确认8ms粒度而未确认取整规则，可保守留一量化单位余量：观测40ms对50ms目标有余量；48ms不能无条件宣布≤50ms，96ms也不能无条件宣布≤100ms。完全匹配的一组点击/键盘交互可形成真实离散input→paint工程结论；连续drag帧率仍独立开放。

## 本轮主机观察的实际范围

`host-lscpu.json`：Intel i5-13400F，16逻辑CPU；`host-memory.txt`记录约31.2GiB总内存和采样瞬间内存状态，OS/load/governor单列。它们可作为以后固定机器身份和负载的起点，不能证明本轮浏览器持续可见、无竞争、刷新率或GPU路径。报告未把瞬时负载归因给产品。

PATH中的 `fc-match`来自 `/home/fzg/anaconda3/bin`；其Inter/Noto Sans SC匹配到Anaconda DejaVu。`/usr/bin/fc-match`的同名两项也匹配系统DejaVu，`sans-serif:lang=zh-cn`则匹配Noto Sans CJK SC。两个resolver和字体文件SHA单列。正式paper字体stack首先为 `Noto Sans CJK SC`，UI stack首先为Inter/Noto Sans SC；不能把字体加载ready、fontconfig匹配或CSS font-family当作IAB实际glyph使用字体锁定。真正锁定需要浏览器支持的rendered-font检查，或正式产品使用有明确字节/家族/加载绑定的字体资产并独立验证fallback；这属于另一次产品/出版范围，不能在本轮偷偷加字体/重建。

## 下一轮真正能做的动作

当前先做矩阵，不重采性能proxy。随后优先实施并独立验证上面的缓冲/认证层，然后在同一受支持IAB当前ChS上取得当前UA/DPR/各viewport/support标志；在304对象已展开状态采预声明真实离散交互批次，并逐trial匹配、去重与保守阈值判定。20个有效interaction可作为预声明最小工程样本量，不是计划新增硬门；slow/null/失败均留原记录。如果所有指定试次匹配且实际p95达50ms，可关闭该**离散输入子项**，不能合并宣布≥50presentedfps或活动取消通过。若它仍慢，保留native事实并据实际最长事件processing与longtask定下一产品优化，不继续用更快的core/proxy替换。

presented trace和held cancel是明确能力缺口，下一步是受支持浏览器录制或真实参与者动作；不是再收一份rAF报告。`source-bindings.json`冻结本次审阅源码/文档与构建字节，`tool-capability-observation.json`明确能力来源，`evidence-manifest.json`只绑定新目录；旧799封存文件、所有raw/probe原件未改。
