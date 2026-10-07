# 新构建两次原生 toggle：独立只读回读

本审计没有操作浏览器/服务、修改产品/build、重跑 Studio suite、执行模型或安装依赖。读取后冻结 18 份输入字节并复读，全部稳定；当前独立 native validator 重新执行 exit 0，Python 审计另外从完整候选关系计算双向唯一，无产品 matcher 导入。详情见 [`report.json`](report.json)。

实际记录来自 root 通过 CUA 操作的 Transformer encoder 展开/收起：**2 captured / 2 trusted / 2 valid / 2 bilateral matches**，前沿 `12→14→12`，revision `0→1→2`，目标与 source/document/IR 绑定保持，目标屏幕锚点位移均 0。两项匹配 duration 各 **1008 ms**，匹配子集 p95=1008ms；没有 pin，不能称无关 pin 漂移通过。

原始 snapshot 有 67 条 Event Timing entries，其中 9 条 positive-interaction entries、3 个 interaction ID。启动采样按钮贡献 target=null 的 pointerdown/up/click，duration3008ms；encoder 两次各有 pointerdown/up/click，duration1008ms。此面板仅捕获识别到的 toggle click/pointerdown 两项 trial，并非完整原生输入日志；不能把 2/2 写成全部输入覆盖、全页 INP 或代表性 p95。

本轮完整 Studio 314/314、0 fail/skip 和 strict TypeScript/Vite build exit0 的已有日志已回读，checks-final 所列当前源码与三个 build bytes 均精确一致。local build 为 `index-D60-bDcz.js`（SHA256 `c4de08e37f8ece504350d8a4d7b1d0a0ec0b26aa13ab31f4b9ca77c90634ee72`）/`index-QPVAzYp6.css`。单列 `assets.public.json` 是 collector 将实际采样前公开 DOM URL 观察转录并保存，后续同 tab 无 benchmark 页重新读取 URL 也一致；审计未 fetch 浏览器 asset bytes，不把本地 build hash 当作已证明内部 browser cache bytes。

已实际查看 1280×720 的 completed JPEG：收起的 Transformer 总览为54%，树中 encoder 收起，采样面板显示记录已生成。面板遮挡部分 source embedding/encoder 侧画布，因此此图只证明采样 UI 状态，不是完整无挡论文图审看。DOM 的 readonly receipt JSON 与保存 raw 解析对象完整相等。

96 个 rAF timestamp、95 interval、约2.021 Hz callback cadence、p95 interval983.4ms（整窗约48秒，含准备/等待）仍为回调诊断；longTask observer supported 且 observed array 为空，只能说没有观测到 ≥50ms longTask。DOM visible/focused、`fonts.status=loaded`/empty loaded faces 没有锁定真实 foreground、字体字节/硬件。presented FPS、连续 input-to-paint、A/B×3、物理出版与真人均未认证；性能门 `not_passed`，M4仍partial、真人0。
