# 浏览器截图绘制滞后诊断

2026-10-04，实际 CUA 截图与已更新的 DOM/source/revision 绑定出现不同步。按 `captures-index-observed.json` 的当时记录，AI 操作员打开真实截图并检查可见页头宽度、PAPER COLOR/MONOCHROME 与 inspector active 按钮；`report.json` 绑定被检查的原截图 SHA-256。报告中的24张错图包含上一个宽度/配色状态，以及两张尚未消失的导出模态框。原始工件保留，后续完整重拍以新 caseId 单列；不能覆盖或把本诊断拼图算作浏览器采集。

页头匹配仍不代表完整视觉验收。若干展开长页的底部被 viewport 裁去；字体的真实尺寸、路由质量、留白与六维人工评分仍待独立审看。这里的 AI 像素观察不是研究者或真人评审，`humanAcceptanceCertified=false`。

两份 `archcanvas-painted-status-full-*.jpg` 是页头和控制按钮的诊断裁图；两份 `archcanvas-painted-frontier-*.jpg` 是页头正确的十个早期样本的完整窗口缩略图。它们由真实截图派生，不能冒充新浏览器截图。最后一份 `residual_cnn-level2-monochrome-85` 采用切换状态、取得 AX 状态、先丢弃一次截图、再在独立 tool call 保存第二次截图，页头85 mm/黑白和两层ResidualBlock展开均与声明一致；后续仍需逐图验证稳态画面。

旧采集增长到37 records（36基础、1份MLP编辑后）后，另从只读副本临时stamp实际hash并执行正式collect，`old-dom-file-consistency-manifest.json`证明这些Canvas/frontier/page、interactive DOM与重新生成的实际publication bytes一致。完整临时副本留在 `/tmp/archcanvas-current37-filebindings-8glg3e0y`。这项通过恰好说明机器绑定验证无法识别上述真实paint错图；`old-dom-file-consistency-summary.json`明确把图像内容仍登记为 rejected/pending，不把旧37份工件用于最终有效截图数量。
