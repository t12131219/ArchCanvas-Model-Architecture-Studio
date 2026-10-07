# M4 性能下一步：实际能力与宿主条件审计

2026-10-06，本审计新增了实际能力与宿主读数。**当前工具不能取得呈现帧轨迹；下一步应先取得合法呈现测量能力，不能继续把约 1 秒的 rAF 记录采得更多来认证 FPS。** root 正在进行的连线路由工作仍可继续。这里没有操作浏览器、执行模型、安装依赖、修改产品或旧封存证据，也没有新增性能通过项。

[机器收据](receipt.json)保存 20 份输入的字节快照与 SHA256，三份历史简单控制记录独立重算，全部输入审计前后相同。[实际能力](live-capabilities.json)由 root 在 CUA 中读取 browser 2 / tab 60；审计者未连接浏览器。两次 root 记录变量不存在的观察失败在该记录中说明。

这次实际能力列表只有 browser `visibility` / `viewport` 和 tab `pageAssets` / `webmcp`，没有 CDP、trace、连续呈现或录制。磁盘里存在通用 CDP 文档不能补成已提供能力，exec 直接连接 CDP、IPC、socket 或独立浏览器自动化也不能作为替代。

计划 §9.7、§18.1 和 §18.5 要求真实 input-to-paint、长任务与帧率；300 可见对象 p95≤50ms、交互≥50fps 是初始 beta 数值目标。当前原生面板的 Event Timing 只针对 click / pointerdown 展开，且 matching 仍按顺序使用 used-set：跨 trial 可解释同一 entry 时，先者可能取得该 entry。下一离散输入诊断应沿用 full observer 的双向唯一匹配。所有路径的 rAF、几何完成、两帧代理都没有连续 drag / wheel 呈现测量能力，不能填上“paint/FPS通过”。

| 新读取证据 | 改变下一动作的含义 | 证据边界 |
| --- | --- | --- |
| 三个旧 simple control，各 20s 窗口 40 个 timestamp-in-capture 回调 | 间隔只有约 16.7ms / 983ms 两档，连续两段和 999.8–1000.1ms；raf-only 也出现，产品 React 和 full 几何不是该历史低频的必要条件。优先查呈现调度与宿主轨迹。 | 不能定位浏览器、宿主、compositor 或显示器唯一原因；不认证新 Studio。 |
| 两条 full control 的原始 longTasks 均为空 | 没有可用于解释 983ms 间隔的已观测 longtask；不能把这段间隔归因于产品长任务。 | 缺 longtask 不证明系统或测量零扰动。 |
| X11 当前 1920×1080 @60Hz；CPU i5-13400F，GPU RTX2070 / driver535.288.01 | 实际显示模式并非约 1Hz，可排除“这台屏幕配置本身就是1Hz”的简单解释。 | 一次读数不锁定旧窗口、刷新反馈、GPU功耗或实际帧率。 |
| 安装的宿主26.930.31428代码有本地页面 backgroundThrottling 条件分支 | localhost 且宿主内部 visible / active / captured 条件成立时禁用普通后台节流；不能直接断言所有 local IAB 低频来自默认后台节流。 | 只读安装代码；没有读取内部条件、调用方法或证明有效运行值。 |
| 安装代码含 Start / Stop Performance Trace，生成 pftrace | 存在通过实际操作者使用宿主原生界面的合法记录方向，后续可核输入到呈现的轨迹。 | native CUA 已禁用；该入口本轮不可由当前工具操作，也没有执行或上传 trace。 |

[宿主观察](host-readonly-observation.json)保留命令退出码、stdout、stderr。`dpkg-query` 的整体退出1来自部分未安装包，不能当成完整软件发现成功。第一份观察把 Electron 合并在 argv[0] 的 process title 当成单个参数，flags为空；[补充记录](browser-process-flags-supplement-1.json)使用 shlex 解析并仅保存非敏感白名单 flags，原观察保留。[安装代码摘录](host-config-excerpts.json)有 ASAR成员偏移、字节数与 SHA256，没有执行其中逻辑。

字体也只能补环境候选：这次 `fc-match` 的 Noto Sans CJK SC 指向系统 TTC，Inter / Noto Sans 回到 conda 的 DejaVu Sans，Arial 指向 Liberation Sans。它们不是浏览器逐字形 resolved font 证据，不能补写旧“字体已固定”；当前 display / CPU / GPU 也不能回填旧捕获窗口。

当前安全动作已经具体分开：若产品改动后确实需要新的离散输入诊断，root 可继续通过 CUA 使用现有 public-DOM full observer、新 store、固定 workload 和新会话，保留 Event Timing 的16ms阈值、8ms量化、唯一匹配分母与 null；这只补诊断。完整性能门的第一项依赖是出现已支持的呈现轨迹接口，或实际操作者通过原生宿主界面提供本地 trace。本轮没有要求人参与、修改宿主设置或重复慢采样。

取得 trace 后，先做一个短的正式源码 Studio 输入：绑定实际 build/source/document、输入目标和时钟，保留全 trace 与操作记录。必须检查同一 surface / frame sequence 的 renderer 工作接到 compositor presentation feedback；BeginFrame、rAF、Paint、提交给 compositor、截图到达分别都不足。再将真实 input latency flow 接到包含相应视觉响应的首个 presented frame，保留 dropped / unmatched / coalesced 输入，按操作分开 p95；不把 matched 子集叫总体 INP。仅在这种轨迹真正可解析后执行已制定的 A/B 条件与三次重复。300 rendered frontier、300 body与viewport相交、实际同时可读仍须分别记录。

机器状态仍为 M4 partial、M5未开始、真人0。当前 A/B、三次矩阵、连续 input-to-paint、实际 foreground 和 presented FPS 都没有新增认证；这一结论不是把整个项目判为阻塞。
