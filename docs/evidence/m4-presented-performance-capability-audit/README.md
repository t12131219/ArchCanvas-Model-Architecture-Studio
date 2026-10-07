# M4 呈现性能：当前实际能力审计

本轮只读审计没有取得可由当前 Agent 直接执行的 presentation trace 路径。当前 D60 的两次可信 toggle p95=1008ms、rAF≈2.02Hz仍属工程诊断，不能认证性能门。报告和七份输入字节快照见 [`report.json`](report.json)。

`ALL_TOOLS` 按 browser/devtools/profiling/trace/performance/Chrome/CDP 搜索只命中 UI 打开工具，没有 tracing/CDP profiler；直接提供的 `cua_repl` 文档列出 browser visibility/viewport 与 tab pageAssets/webmcp，同样没有 presentation tracing。此审计没有调用共享 CUA 或检查 root 浏览器的私有状态。PATH/dpkg 未发现 Chrome/Chromium、Perfetto/trace_processor；`perf` 存在但它本身没有浏览器 surface 与 presentation-feedback 流。发现范围是 PATH/dpkg，不宣称全盘绝对不存在工具。

安装的 Codex ASAR 仍含原生 **Start Performance Trace / Stop Performance Trace**，调用 Electron contentTracing 并保存 `<system-tmp>/codex-trace-<timestamp>.pftrace`。这次复读 main/package/switch 三份成员与此前 SHA256精确相同；没有执行内部函数、启用 DevTools、接 CDP/socket/IPC、上传轨迹或改配置。代码存在不证明这项 UI 正可操作，也不保证未来 trace 必含相应 surface 的呈现反馈。

具体阻碍是没有可调用工具收集 **同一 Studio surface 的 compositor presentation feedback 与输入响应关联**；native app CUA被禁用，另一个连接到真实 Chrome 的 tracing provider没有被提供。root 服务 handle39008未触碰（未 poll、停止或写入），本审计 sandbox `/proc`只能看到本地 wrapper，不能认证父服务在线状态。

下一项可执行采集是由实际操作者在宿主原生菜单选择 Start Performance Trace，在当前 D60 Studio 完成一个短的 encoder toggle，再 Stop 并保留本地 `.pftrace`，无需上传。先绑定目标/source/document/IR、build、输入时钟、viewport/DPR/UA以及字体/硬件事实；然后解析完整轨迹，确认正确 surface/frame sequence 的 presentation feedback 确实连接到该输入后的首次视觉响应。`BeginFrame`、rAF、Paint、compositor提交或截图到达均不足；先取得这类真实证据，才能继续规定 A/B与三次重复。当前 presented FPS、连续 input-to-paint、固定环境与真人均未认证；M4保持partial。
