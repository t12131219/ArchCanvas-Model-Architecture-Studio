# 2026-10-14 局部展开浏览器验证

全部浏览器检查使用临时 Chromium context，不读取或写入用户的浏览器 profile。模型来源为隐藏“示例与模块库”中的当前 Transformer 主案例 `01093cc06a87b35a`，不是历史快照。源码仅作文本和来源哈希检查，不执行模型。

最终证据：

- `final-v3/report.json`：12 次逐层细化至 83 个节点 / 85 条边，4 次收起 / 重开，共 16 次切换和 20 项检查。每一步源码 authority SHA256 保持相同；完整边、同级节点、独立值通道校验通过；容器贴边 contact 和降级 constrained 列表为空。Memory 的 K/V 两个消费者分别从记录的底部方向接入。
- `final-transaction/report.json`：第四次构建的 7 项检查，包括 busy 期间四个连接编辑入口不修改图；注入 Worker 拒绝时 visual、expand-all、collapse-all 返回错误且完整图、选区、dirty、undo 和 redo 原样保留。成功 redo 仍能恢复原展开图。Worker 注入仅存在于此测试 context。
- `final-all/report.json`：最终构建在新 context 一次“展开全部”恢复完整原图布局，83 个节点 / 85 条边，零非法边和零贴边降级。
- `bridge-smoke.json`：22 项桥接、保存 / 恢复、原型视觉编辑、原始来源身份和画布操作检查。
- `source-interop/browser-sources.json`：5 个案例 / 14 项来源证据、面板编辑、保存以及正式源码编辑兼容检查。
- `studio-local.png` 和 `studio-full.png`：最终局部及全图，保留主程序左右和顶部面板，关闭模型下拉菜单。

复现脚本为 `studio/scripts/test-preview-expansion.mjs`。`--cross-only --transactions` 验证最终原子操作；`--expand-all-only` 验证一次完整展开；不传这两个参数时执行完整逐层展开和真实工具栏 undo / redo。重复收起指令必须不增加 undo，且不清空既有 redo。

性能记录见 `browser-summary.json`。同口径自动化步骤（包含诊断 snapshot 的准备）中，cross、FFN、Norm2、self 分别从 3972、5096、7004、9247 ms 降至 965、1076、1297、1734 ms。最终 `actionMs` 单独测量点击开始至 UI 完成：首次 cross 为 491 ms、FFN 为 546 ms，完整矩阵为 397–3269 ms；较大子图首次展开和折叠仍需要后台整理。数字是一台机器上的一次本地运行，不是任意模型或设备的性能保证。最后的事务和一次完整展开检查与 CPU 回归并行，其时间仅作为功能诊断，不用于性能比较。

保留的中间记录：`baseline` 是完整单步基线，`baseline-mixed` 有四个有效步骤，最后一步因旧测试未适配视口被 footer 拦截而超时；`final` 的第六步和 `final-v2` 的完整图曾检出额外贴边，已经修复；`final-history-diagnostic` 显式跳过当时已知的两个 contact 断言以提前检查历史功能，不能作为最终布线通过证据。最终严格结果以 `final-v3` / `final-transaction` / `final-all` 为准。

报告内 `servedAssets` 记录实际浏览器获取的 JS SHA256。第三次与第四次构建的几何引擎哈希相同；第四次仅补齐忙碌保护及全展开 / 收起的错误传播。截图和报告不沿用原型目录的历史验证结果。

超过 1 MB 的原始图 JSON / SVG 已保存为 `.json.gz` / `.svg.gz`，解压后的字节保持相同，原始和压缩 SHA256 在 `compressed-artifacts.json`；报告、摘要、日志及 PNG 保持可直接阅读。
