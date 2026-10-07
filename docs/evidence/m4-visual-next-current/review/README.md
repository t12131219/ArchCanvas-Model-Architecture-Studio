# 复杂图的独立几何复核与标签修复

本目录由 AI 审查产生，真人参与者为 0。先绑定 `index-B_XHk-wz.js` 的 100 个 source/test/config 和 3 个 dist 文件，重新静态分析正式 Transformer、MLP、ResidualCNN 源码，再通过正式 core 生成 36 个 SVG/Scene。没有执行模型，没有启用失败旧工程。`fresh-source-core` 的 PNG 是 100 DPI 出版派生图，不是浏览器截图。九个实际 hierarchy frontier 为 Transformer L0–L3、MLP L0–L1、ResidualCNN L0–L2；没有虚构 CNN 第三层。

[`geometry-report.json`](geometry-report.json) 使用独立 Python 路径解析与区间几何，不导入生产 router、intersection、typography 或旧 oracle。8 个控制核对零长度段、严格交叉、中间顶点接触、端点排除、重合区间合并、卡片内部、边界相触与 U-turn。严格交叉只计两个线段内部；“中间顶点接触”另计边在拐点碰到另一条边，不能将它们都命名为可消除交叉。同 tensor 共享主干单列，不能自动判作错误。

| 初始 B_XH 源码 frontier | 不同 tensor 严格交叉对 | 中间接触对 | 重合对 | 独立安全短路候选 |
|---|---:|---:|---:|---:|
| Transformer L0 | 1 | 8 | 7 | 3 |
| Transformer L1 | 19 | 24 | 5 | 5 |
| Transformer L2 | 22 | 39 | 17 | 6 |
| Transformer L3 | 20 | 37 | 17 | 5 |
| MLP L0 / L1 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| ResidualCNN L0 / L1 / L2 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 1 / 1 |

九 frontier 的名义卡片／背板／祖先标题穿越均为 0，U-turn 为 0。22 个候选逐一保持端点及出入法向、所有对象位置，并保护每个全 tensor 边对的严格交叉数、中间接触数及重合长度。其中 Transformer L1 `edge:31` residual 可从 4 弯、197.2 单位缩成 2 弯、54.2 单位；L2/L3 `edge:45` mask 各可减少 2 弯。这是有限搜索给出的可核对提议，不是全局最优，也没有安装进产品；本轮不扩路由 budget。

[`historical-document-binding.json`](historical-document-binding.json) 核对旧 au3 浏览器矩阵九个 paper/180 document 的 54 个封存工件，使用当前 core 重新渲染这些实际 UI 保存的 CanvasDocument。对应 [`historical-document-current-geometry.json`](historical-document-current-geometry.json) 的上述指标相同。旧截图只作为历史定位，不继承为 B_XH 或新标签代码的像素认证。

总览 `memory` 的旧 baseline 为 `(280.5,436.1)`，独立名义文字范围进入 Encoder 重复背板与 Decoder 前板。根 Agent 另在 [`../bxh-browser-before/memory-label-bounds.json`](../bxh-browser-before/memory-label-bounds.json) 保存 B_XH 实际 `getBoundingClientRect`：与两端卡片的 screen 相交宽约 0.2692 / 0.1945 CSS px；root 亲看 100% 原图后记录文字仍可读，不能写成“完全遮蔽”。浏览器 `getBBox` 不支持的失败记录保留。expanded 父容器的背景相交不是卡片障碍。

本次只实现一般连线标签避让，正式源码改动包括 `edgeLabelPlacement.ts`、`scene.ts`、`exportScene.ts`、`types.ts` 与 `layoutWarnings.ts`。helper 使用与 SVG 相同的 9 单位字号，每 codepoint 1 em 加 padding 的确定性名义 envelope；它不是已解析字体量测或印样证明。已有安全位置保持不变；存在卡片／重复背板／标题／其他 route／note／caption 冲突时，只在原锚点附近 64 单位范围内找空白。找不到空间时保留文字和位置，并输出 `layout-edge-label-blocked` 及中文指引。概览和 detail reroute 后都使用这项策略；最终完整标签 envelope 纳入 Scene bounds。没有移动对象、修改路线、改变 canonical binding、重写 source facts 或 persisted manual layout。

源绑定反例与修前字节保存在 [`label-before/manifest.json`](label-before/manifest.json)。[`pre-failure.txt`](label-before/pre-failure.txt) 是 1/1 真正的修前失败：memory nominal body 进入两个卡片。修后首次检查修复了标签，却在 JSON 序列化遗漏 `undefined` 的比较处失败，保存在 `label-after-focused-attempt-1.txt`；改为对称 JSON 比较后继续检查，没有将这次 oracle 错误包装成产品失败。

最终专项 [`label-after-focused-attempt-3.txt`](label-after-focused-attempt-3.txt) **34/34、0 skip**，含 7 个新标签回归、既有 routing/four-direction/history/whole/detail 及导出分区检查；它们不是 34 个新 Studio 测试。[`strict-noemit-attempt-1.txt`](strict-noemit-attempt-1.txt) exit 0，局部 `git diff --check` exit 0。子 Agent 未运行 build/dist 或全套 Studio 测试；根 Agent负责最终统一 build 与真实浏览器跟进。

[`label-after/summary.json`](label-after/summary.json) 是新 source core 的概览／whole／root-detail 结果。概览 memory 变为 `(280.5,388.1)`，原 `M 281 444.1 H 316` 路径、节点、端口、事实与语义摘要保持；名义文字不再碰两端卡片及其他路由。新 helper 不解决本表残留的复杂交叉，也不认证所有字体、所有详细页的浏览器像素、物理出版尺寸、真实呈现性能或研究者任务。M4 不因此完成。
