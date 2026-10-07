# M4 可读画布与草稿交互收敛

本阶段使用正式工程构建 `index-thbum3BQ.js` / `index-QPVAzYp6.css`。画布文字在总览缩放时做有界补偿，长中文与宽 Latin 标题按卡片宽度省略并保留完整 `title`，端口提示框根据节点障碍物选择候选位置；删除连线后会明确要求重新检查。Studio 专项测试 300/300 通过，strict TypeScript/Vite 构建退出 0，独立源码复核见 [report.json](evidence/m4-readable-canvas-work/independent-source/report.json)。

浏览器样本见 [browser manifest](evidence/m4-readable-canvas-work/browser-final/manifest.json)。样本包括 58%/100% MLP 总览与提示、四向 16 单位节点移动及撤销、长标题、保存重开、删边反馈、双输入 Add 的横向/纵向端口末端点击、预算内长形状静态检查、AdaptiveAvgPool2d 长类型和 1100×720 响应式视口。所有样本由 AI 操作，真人参与者仍为 0；它们只支持清楚列出的局部行为。

已知边界：Add 双输入标签在低缩放下仍偏小；提示框不避让连线/marker，密集且无空位时可能覆盖节点；本批次没有认证全部 17 模块、任意分支的全局连线美观、出版尺寸、呈现性能或真实研究者任务。旧 BV 模块库动作 JPEG 的独立复核为 `pixelSynchrony=failed`，旧原件和失败报告保留，不从中继承截图认证。
