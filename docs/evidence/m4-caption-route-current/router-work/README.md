# 通用正交路径安全捷径实现

本目录记录 `studio/src/core/orthogonalRouter.ts` 的独立新增实现；没有采用失败原型代码，没有修改历史 gold、文档入口或最终构建产物。通用规则只在 `batch()` 的旧 generic/family/collapsed-residual 路由完成后执行，单条障碍修复入口的既有契约保持。

此前 generic 仅在路径之间有冲突压力时评估候选，清晰但多余的折线常保留。新 final shortcut pass 对任意角色的路径提出局部子路径拼接及有限正交走廊，保留所有端点与方向；长度、弯数均不增加且至少一项严格改善。不是源事实推断，也不合并 tensor、branch、role 或 style。

新规则禁止反向 U-turn，保留原有至少 6 世界单位的端点逃逸（原有逃逸不足 6 时保留原值）。所有端点正文、Repeat 两块背板、无关正文和祖先标题都作为障碍；新中段与相关边界保持 6 世界单位间隙。端点逃逸只可穿自己的 padding，不能穿正文。新规则自身碰撞与关系容差为 `1e-7`，不会改变旧路由器的全局 `0.01` 容差。

每个候选与当前完整 batch 的其他路径逐对比较具体几何集合：不能新增 crossing 点、perpendicular/bend/collinear contact，重叠区间必须是旧占据区间的子集；同 tensor 与不同 tensor 都受保护。既有同 tensor trunk 的身份不能授权新增共享几何。删除旧交点不允许换取另一个位置的新交点。不是只比总体数量，更不是全局交点或弯数最少证明。

`ROUTE_SHORTCUT_BUDGET` 独立于旧 refinement 的资源预算：节点最多 1024、路由 512、点总数 4096、每条点数 64；每条候选最多保留 256 个、详细评估 32 个；全局 512 个候选、接受 32 条路径、32768 pair checks、250000 segment checks、100000 obstacle checks。达到任何保护边界即保留上次验证过的结果，不把未检查候选当成功。候选生成循环也由最多 64 点、1024 节点和最多 64 个坐标通道限制。预算是操作次数上界，不是时间或 FPS 认证。

[新独立测试](../../../../studio/tests/route-shortcut-independent.test.ts) 使用完整封存的旧 router 作为 before 观察；端点、方向、U-turn、pair contacts/crossings/union-overlap 由另写的几何 oracle 核对，未调用生产统计助手。最终 focused **16/16**，严格 TypeScript exit 0；旧 router 替代重放 **16 中 13 通过、3 项预期失败**，分别暴露一般清晰路径、CNN L2、Transformer L1 原先缺少的缩短行为。所有失败和修正原因见 [尝试记录](attempts.md)。本子任务没有运行最终 Vite 构建或浏览器。

[独立量化](source-frontier-measurement.json) 覆盖 3 个源模型的 **9 个不同层级、198 次路由出现**，实际改变 3 次：CNN L2 residual `edge:18` 长度 849.4→831.4，Transformer L1 residual `edge:31` 长度 197.2→54.2 / 弯 4→2，Transformer L1 memory `edge:55`（保留 canonical 55/56）长度 434 保持 / 弯 4→2。累计减少 161 世界单位、4 个弯。跨层级出现不是新的独特 tensor，不能与重复宽度/配色矩阵次数累加。

引用的 `historical-document-current-geometry.json` 实际包含 **21** 个候选，未补造“第 22 个”。清单原有候选只要求 pair 数量不劣化及名义矩形安全，其中一些会移动既有交点或接触位置，新规则会保守拒绝。当前 Transformer L0 均保留原有路径；没有宣称把 21 个候选全部落实。

源码、节点、端口、pins 和输入 Scene 不被修改；布局与 branch/canonical/source 仍由同一 CanvasDocument 产生。派生标签锚点可能随路径改变，它们的正确关联与浏览器像素需要另外验收。当前 pass 逐对保护其他路由，未单独证明所有可构造路径的自身非相邻 segment 交点没有新增；`validDirections` 的 U-turn 禁止不能替代这种全域证明。全局最佳路由、任意复杂层级、实际帧率、实体出版与真人任务仍不在此报告范围内。
