# 历史比较边界

本阶段的历史 Scene／SVG 金样及其 manifest 未改。原先当前测试要求“所有纸图路径完全不变”和“只有 collapsed residual 能缩短”；新一般几何优化有意扩展了这一范围。

`studio/tests/monochrome-role-independent.test.ts` 现在仅在比较历史金样前归一化派生路径、标签坐标、引导线、页面边界及新增 caption diagnostics，其余完整 Scene 仍精确比较，归一化后的出版／交互 SVG 仍与原字节比较。实际路径另外检查端点、首尾方向、长度／弯折不增加、无新正文侵入、无新相交位置或重叠；独立 caption 和 shortcut 测试验证未经归一化的新表现、工作上限与几何保护。

`studio/tests/collapsed-residual-independent.test.ts` 保留独立 `assertRefinement` 对节点、固定对象、端口、角色、样式、canonical branches、sourceFacts 和输入不变的检查；允许其他角色及可见端点采用经过几何核验的缩短路径。缺少 canonical identity 不会许可合并或改写绑定；几何 pass 不依赖这些事实。

初始受影响的十项旧断言失败原样保存在 [router 记录](../router-work/existing-focused-attempt-2.txt)，不能改成先前通过。调整后的 [专项 attempt-1](attempt-1.txt) 55/55、零跳过；它不是最终统一检查，也不加到其产品测试总数上。正式变更前测试字节在 [126 项档案](../before-change/manifest.json) 中。当前入口历史正文和失败记录均另行保留。
