# 路由可读性只读评估与未采用候选

本评估基于正式工程冻结的 routing-visible Scene 和 C7 实际浏览器公共
SVG 记录。没有修改产品源码、dist、旧原始证据或封印，也没有运行模型或
操作浏览器。Python 几何与路径候选代码从零构造，没有使用失败 prototype。
结果用于定位可安全尝试的工程改进，不代表真人、视觉美观、出版或性能验收。

`metrics.py` 独立解析 M/L/H/V 路径，去除零长与同方向共线顶点，再统计弯折、
反向折返、不同 tensor 的严格正交交叉和共线重合。交叉按“边对＋交点”计数；
同一点的多组边对仍有多条记录。重合按边对计数，并单独给出线段重合长度。
`disjointOwner` 要求两个箭头的 source/target node owner 都不相同，因而比
仅 tensor 不同更保守。共享 tensor 不计入这些冲突。primitive 正反例先验证
严格交叉与端点相接、长重合与仅触边，以及路径归并的区别。

当前实际浏览器证据：

| 实际视图 | 箭头 | 不共享 owner 交叉 | 不共享 owner 重合边对 | 总弯折 |
| --- | ---: | ---: | ---: | ---: |
| Transformer L1 | 29 | 19 | 5 | 76 |
| Transformer L2-preFF 中间态 | 47 | 33 | 14 | 112 |
| Transformer L3 | 59 | 20 | 19 | 124 |
| ResidualCNN L2 | 23 | 0 | 0 | 28 |

MLP 的四方向 before/moved/undo/redo/restored 共 20 个实际 SVG 状态均为
0 交叉、0 不同 tensor 同线重合。左/右移动把总弯折从 8 增为 10；向上移动
把弯折从 8 减为 6，但该位置仍与祖先标题相交。因此弯折少不能单独证明
更好的布局。当前报告已记录标题冲突及可见引导，不重复把它认作新缺陷。

具体反例来自 C7 Transformer L3：`edge:50`（target_mask → self_attention）
与 `edge:57`（memory_mask → cross_attention）在 y=202 的横线及 x=816
的外走廊重合合计 763 SVG 单位。不同 tensor 的源、目标 owner 都不共享。
`edge:13` residual 与 `edge:25`/`edge:29` source_mask 在 x=74 分别重合
350 单位。现有 router 只有 body/header 冲突时才比较候选；这几条路线没有
body 冲突，所以现有最短避障修复会留下同线拥挤。

`experiment.py` 是独立 Python 候选，**没有被正式产品采用**。它只替换临时
Scene 中的路径，保留所有节点、端口及 canonical 关系。候选包含原路径，
使用 6/14/22 单位的引出段，节点边缘和已有走廊的邻近坐标；两轮固定顺序
局部比较。必须无新 body/header 穿越，保留两端坐标及初末进入方向，没有
反向折返，并且目标边与其他不同 tensor 箭头的交叉数及重合边对数都不增加。
先比较冲突总数，再比较重合长度和路径长度／弯折。相同 tensor 可共用 trunk。

| 冻结 CPU 输入 | 不共享 owner 交叉 | 不共享 owner 重合边对 | 总弯折 |
| --- | ---: | ---: | ---: |
| Transformer L0 | 1 → 1 | 6 → 6 | 24 → 20 |
| Transformer L1 | 19 → 10 | 5 → 3 | 76 → 72 |
| Transformer L2 | 20 → 15 | 19 → 13 | 116 → 112 |
| Transformer L3 | 20 → 15 | 19 → 13 | 124 → 120 |

L3 不同 tensor 线段重合总长度为 5754.21 → 3435.01 单位。每个替换保留
端点，0 新 body/header 穿越、0 U-turn。L0 仍有冲突，证实单走廊微调不完备。
Python 耗时只用于控制实验规模；没有研究 TS、DOM 或显示延迟，不能从这些
耗时外推出交互性能。

最小实现建议是保留现有避障器，在存在箭头冲突的少量路线中才评估有预算的
邻近走廊候选。不同 tensor 长同线重合和严格交叉需要进入 cost；共享 source
port 且同 tensor 可保留共享 trunk。原路径始终作为候选，不引入 body/header
穿越、U-turn 或端点方向改变，并保留稳定排序和平局规则。初期候选可限制为
每端 3 个 lead、最近的 8 个走廊、1 次局部 pass；本实验的较大候选集并非已
验证的实时实现。所有四向 preview、commit、undo/redo 和 export 都需要使用
同一个确定性几何过程，再取得新的 CPU 与实际浏览器证据。用户手工布局及
pins 不应因这项改进自动移动。

authored DAG 的初始排布建议：只在尚无手工位置时做最长路径分层，以稳定
插入顺序为 tie-break；支路按上游中心／中位数排列，最多 2–4 次上下游
barycenter 调整。端口的入／出顺序按连接对象的几何位置匹配，避免扇入交叉。
跳层 residual、memory、mask 通道使用外侧不同 lane，正常相邻 data 路线
保持短而直接。移动以后保留手工位置，路由自己避障并报告解决不了的冲突；
不把初始 DAG 排布器用于每次拖动，不通过伪造 Split 节点表示仅作图的 fan-out。

复现命令（正式项目根目录）：

```bash
./.venv/bin/python docs/evidence/m4-ai-usability-next/routing-readability-review/metrics.py
./.venv/bin/python docs/evidence/m4-ai-usability-next/routing-readability-review/experiment.py
```

每份结果绑定读取的原始文件 SHA。`binding.json` 进一步绑定脚本、输出及当前
公共 core 文件，明确这不是新产品构建或新浏览器覆盖。旧封印与原始记录保持
原字节。
