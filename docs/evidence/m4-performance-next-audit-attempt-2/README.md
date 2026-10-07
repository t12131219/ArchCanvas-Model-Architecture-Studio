# M4 当前正式构建性能路径审计（bounded）

本审计于 2026-10-06 对当前正式 `studio/dist` 和性能入口做只读核对。没有操作浏览器、修改产品源、重跑 Studio/build、执行模型或安装依赖。输入、源码与资产哈希以及四个历史 receipt validator 的完整输出见 [`receipt.json`](receipt.json)。

当前正式静态产物是 `index-thbum3BQ.js` / `index-QPVAzYp6.css`，与 [M4 可读性状态](../m4-readable-canvas-status.json) 的 300/300、strict TypeScript/Vite 记录一致。当前 bundle 确实包含 `?benchmark=1` 性能入口、20 组采样、原生输入采样、`two-animation-frame-paint-proxy` 和 `native-event-timing-to-next-paint` 标记。正式运行路径为：

```text
PYTHONPATH=src .venv/bin/python -m archcanvas_cli serve \
  --host 127.0.0.1 --port <port> \
  --data-dir <isolated-/tmp-dir> --studio-dir studio/dist
```

此审计未取得当前页面的浏览器呈现证据。root 可在真实浏览器中打开 `http://127.0.0.1:<port>/?benchmark=1` 以进入现有工程诊断面板（实际页面结果须另取证）。其 synthetic benchmark 使用 DOM tree click，并把两次 `requestAnimationFrame` 明确命名为 paint proxy；native panel 观察 click/pointerdown、Event Timing、long task 和两帧后的公开几何。它没有 compositor presentation feedback，不能给出 presented FPS 或连续 input-to-paint。

四个历史 JSON 均可由独立 validator 重算（Studio 小场景、Studio 300 层、native smoke、native intrusion 均 exit 0），但它们绑定旧 localhost 会话/旧构建，不能认证当前 `thbum3BQ` 产物。保留的结果仍显示约 1 Hz idle/约 1–2 FPS callback cadence 与 996–1955 ms 两帧代理；这些是历史工程诊断，不应被改写成真实呈现帧性能。

下一步需要当前构建的固定环境（viewport/DPR/UA/字体字节/硬件）、完整 trace 与输入时间，并确认同一 surface 的 renderer work 连接到 compositor presentation；可由宿主原生 Performance Trace 入口或等价、实际可解析的 presentation API 提供。获得该能力后再做规定的 A/B 与三次复现。期间可以继续使用 `?benchmark=1` 作为诊断，但应保留 missing/ambiguous Event Timing 为 null，并明确不认证 M4 性能门。当前真人参与者为 0，M4 仍 partial。

历史 `m4-hierarchy-visible-performance` 产品与 control raw 也重新通过当前独立 validators（各 exit 0），但 control 当前字节比较明确指出旧 oI5 产物不存在、index.html 已变化，不能扩展为当前构建认证。其 `visible` 目录名不是真实宿主前台认证。

一次合成的[顺序歧义反例](native-order-counterexample.json)证明当前 native matcher 的 used-set 顺序分配不满足双向唯一：两个同目标 trial 在 0/6ms，一条 entry 在 3ms，两项本应均 null，但产品将其分给首项，独立 validator 接受一项匹配。该结论在本审计后获得修复授权，修复与 focused 测试将另存 `m4-native-matching-work`；原输出保留为修复前失败，不计浏览器测量。

本审计自己的 CUA tab 创建因子 Agent 的 IAB visibility 不支持而失败，未操作页面。42937 的临时服务 session 43839 已按精确 handle 停止，未触碰父 Agent 后续 session 39008。两个 2 秒 timeout 启动无输出，均不充当证据；仅 sandbox server/URL EPERM 与已观察 formal startup 来源分别保留，不声称完整 HTTP/render 验证。
