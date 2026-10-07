# M4 固定窗口性能控制实验

这是独立测量工具，当前尚未运行浏览器实验。正式产品源码、现有构建与冻结历史证据未由本工具改动。实现从本轮测量合同独立编写，未复用失败原型；旧 `scripts/m4_input_observer.mjs` 仅作为缺口的只读参考。

先固定 [measurement-contract.json](measurement-contract.json)，再实现页面与观察器。主要规则为 **2 秒预热、20 秒采集、2 秒固定 delivery drain**，输入须在采集前 10 秒内结束。实际 timer 迟到、晚输入、无输入、取消、缺失原生 entries 与所有 buffer drops 均保留。不会只给慢试次延长等待，也不会把缺失 entry 写成 0 ms。

## 启动与来源审查

在正式工程目录使用已配置的正式环境；不安装依赖、不运行模型、不构建产品：

```bash
.venv/bin/python docs/evidence/m4-performance-controls-work/serve.py --describe-only
.venv/bin/python docs/evidence/m4-performance-controls-work/serve.py --port 0
```

`--describe-only` 不创建 listener 或 store，仅输出实际解释器、六个正式 package origin、当前 build/helper hashes。启动会创建独占的 `.archcanvas/m4-performance-controls-sessions/<UUID>/documents`，打印实际新端口、来源与文件 bindings；保留完整原始 stdout、失败尝试和 tool session handle。不能从本 README 或 source 的存在声称服务已运行。

页面分别为启动 stdout 中的 `controlUrl` 与 `studioUrl`。前者是顶层简单控制，后者 iframe 同源加载真实未修改的 `/` Studio，所有模型/源分析仍通过真实服务的既有接口。Context 只读请求在会话开始前完成；观察器不请求私有 state、不修改文档、不 dispatch 任何产品事件。

## 用 CUA 采集

1. 打开实际服务返回的页面。固定同一浏览器 surface、前台、未遮挡、DPR、viewport 与字体/硬件记录；原始 tool times 与外部 UI/screenshot 观察由采集者单列。缺少显示、GPU、CPU 固定或真实字形字节证据时保持 unknown。
2. 选择一致的测量区域：`1280×576` 需要至少 `1280×720` 外页，`1280×720` 需要至少 `1280×864` 外页。控制器占 144 px，不覆盖测量区。开启前回到顶部；启动 gate 拒绝被裁切区域。不要把窄窗口或裁切 iframe 报成全可见。
3. 产品页先通过普通操作加载真实模型并设置实际层级、相机与目标。`full` 对目标 ID 的最小几何读取不读产品状态。初始/最终公共 snapshot 记录完整 SVG、metadata、frontier、pins、visible membership；它们是公开观测，不能证明 hidden history。
4. 选择 `raf-only` 或 `full`、标签、操作、目标，点击“开始固定窗口”。预热 2 秒后状态进入“正在采集”。原生 click/drag/pan 等须在采集前 10 秒内完成。保留该 CUA 调用及实际时间；按操作路径/距离比较时需要 native down/up 原始记录，而不是整段 armed/settle 时间。
5. 采集中不读取大 DOM、receipt 或截图，不切页，不 minimize，不调整窗口。一次会话只执行预先声明的一类操作；错误、额外动作与输入迟到都保留。允许取消，取消 receipt 仍保存但不充当完成窗口。
6. 固定 capture 截止读取 `takeRecords`，观察器继续等固定 2 秒；最终再次 `takeRecords` 后 disconnect，再复制/序列化 receipt。结束后通过 **只读公开 textarea** 提取完整 JSON，必要时分块，保存原始字节和前后页面状态。不要在 CUA evaluate 中调用 observer、制造事件、fetch 或读取私有 global。
7. 完整矩阵计划是 control 与四节点/304 rendered Studio，在 raf-only/full、idle/native input 条件下至少三次匹配复现，并交替顺序。先采的有界批次只支持自身实际条件，不代替未完成矩阵。

## 证据边界

`raf-only` 无 native-input 监听、PerformanceObserver 或逐帧 geometry，只保留一条 rAF chain 与环境/lifecycle记录，初/末 snapshot 在采集外。手动操作只能依靠独立 tool 日志，不能将它冒充记录了 gesture。

`full` 记录原生事件、EventTiming（请求 16 ms 阈值）、longtasks 和目标/camera 的公开 DOM 几何。相同 pointer 的 down/up 形成实际 native-duration，pointercancel/orphan/unclosed 另列。EventTiming 匹配必须 type、target token、时间差 ≤2 ms，且 one-to-one。完整原分母保留 matched/missing/ambiguous/invalid 及所有 interaction IDs；最终的匹配索引属于筛选后的 measured-capture entries，另有原始 entry index mapping。

直接 callback 成本按类别记录，geometry 嵌套于 frame，不能相加为独立 CPU。新的 full 是固定合同下的新采集器，不能声称复现旧 full 每项分配，更不能声称消除了 observer、GC 或 layout 影响。`takeRecords` 不强制浏览器完成 pending entry；drain 后未知项仍未知。

**rAF cadence、DOM 响应、focus/visible flags 均不证明真正呈现。** 不从 control 时长相减、不把 matched-subset p95 称为全页 INP、不把 EventTiming remainder 称为 GPU/paint。AI 操作真人记录为 0。此工具本身不通过 M4 性能门槛。
