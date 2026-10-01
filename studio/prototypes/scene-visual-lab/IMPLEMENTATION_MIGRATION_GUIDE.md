# Scene Visual Lab 源码实现与主程序迁移指南

> 适用目录：`studio/prototypes/scene-visual-lab/`
> 代码快照：2026-10-01 当前工作树
> 目的：说明最小原型中每类场景、图例、父子展开、层级路由和导出的源码实现，并给出迁移到正式 Studio 的语义边界。

## 1. 先明确：当前原型不是 Python 自动可视化器

当前原型没有 Python AST/运行图解析器，也没有从任意 `.py` 文件自动生成 `LabScene` 的代码。四个 Transformer 场景来自对指定 Python 源码的人工阅读和人工建模；`src/scenarios.ts` 中的节点、边、标签、坐标和 `detail_kind` 都是手写的。

真实链路是：

```text
Python/上游源码
  -> 人工确认模块、调用顺序、张量、mask、共享参数和父子关系
  -> src/scenarios.ts 手写外层 LabScene
  -> src/module-details.ts / src/catalog-details.ts 手写内部 DetailPrimitive
  -> src/expansion.ts 计算父节点展开后的外层布局
  -> src/detail-layout.ts 建立递归详情树并重排/重路由内部图元
  -> src/atomic-hierarchy.ts 将最深原子入口/出口投影到场景边
  -> src/routing.ts 计算外层路由
  -> src/App.tsx 或 src/svg-export.ts 渲染 SVG
```

因此，本文中的“源码对应”表示有证据约束的人工映射，不表示原型已经实现以下能力：

- 自动识别 Python 类、函数、调用图或张量 shape；
- 自动判断某个 `nn.Module` 应使用哪个 `NodeShape`；
- 自动生成父子层级或 `detail_kind`；
- 自动把源码行号、canonical node、evidence ID 绑定到图元；
- 自动证明手写图中的每一条边与任意新版本源码仍一致。

正式主程序迁移时必须以 Source Evidence 和 Exact Architecture IR 为权威，以画布为派生视图。不能反向把本原型的坐标、显示标签或 `LabScene` 当成模型事实。

## 2. 当前快照和实现入口

当前 `SCENARIOS` 共 30 个场景：18 个路由/视觉压力场景、1 个通用父子展开场景、4 个 Transformer 场景、1 个扩展模块目录场景、6 个模型家族目录场景。每个基础场景有：

```text
5 RouteStyle × 3 NodeVisualStyle × 3 EdgeLabelStyle = 45 种组合
30 场景 × 45 = 1350 个基础静态案例
```

展开快照在这 1350 个基础案例之外单独生成。

| 文件 | 责任 | 迁移时的含义 |
|---|---|---|
| [`src/types.ts`](./src/types.ts) | 原型场景、视觉选项、路由结果和 patch 类型 | 仅为原型 DTO，不是正式 IR |
| [`src/scenarios.ts`](./src/scenarios.ts) | 30 个手写场景、视觉组合维度 | 测试 fixture；不要作为模型导入格式 |
| [`src/module-details.ts`](./src/module-details.ts) | Transformer 与九类基础模块的内部图 | 可迁移为有 slot 的视觉模板 |
| [`src/catalog-details.ts`](./src/catalog-details.ts) | 30 个模型家族的内部图 | 可迁移为 schematic 模板，需证据门控 |
| [`src/detail-layout.ts`](./src/detail-layout.ts) | 详情图节点化、递归展开、拖动、局部避障 | 可迁移纯布局算法；ID 机制需更换 |
| [`src/expansion.ts`](./src/expansion.ts) | 外层节点展开和增量位移 | freeform/paper 两种布局策略 |
| [`src/atomic-hierarchy.ts`](./src/atomic-hierarchy.ts) | 原子节点、门户、门户链和边界投影 | 层级连线收束的核心原型 |
| [`src/routing.ts`](./src/routing.ts) | 五种路由、指标与自适应寻路 | 可迁移为正式路由引擎能力 |
| [`src/model.ts`](./src/model.ts) | 内存场景的增删改和边清理 | 仅为 visual patch；不能写模型源码 |
| [`src/App.tsx`](./src/App.tsx) | React 状态、交互、绘制顺序、检查器 | UI 参考；不要迁移原型状态容器 |
| [`src/svg-export.ts`](./src/svg-export.ts) | 无 React 的静态 SVG 和指标导出 | 应与正式渲染 scene 共享语义 |
| [`vite.config.ts`](./vite.config.ts) | 生成案例矩阵和展开快照 | 回归 fixture 生成器 |
| [`references/SOURCE_TRACEABILITY.md`](./references/SOURCE_TRACEABILITY.md) | 基础模块与 Transformer 的源码追溯 | 迁移模板时的证据说明 |
| [`references/MODEL_FAMILY_TRACEABILITY.md`](./references/MODEL_FAMILY_TRACEABILITY.md) | 30 个家族图的上游证据 | schematic 模板的适用/不适用边界 |
| [`BOTTOM_UP_ATOMIC_ROUTING.md`](./BOTTOM_UP_ATOMIC_ROUTING.md) | 原子优先层级路由设计 | 层级路由详细设计补充 |
| [`REGRESSION_TEST_REQUIREMENTS.md`](./REGRESSION_TEST_REQUIREMENTS.md) | 自动化和浏览器视觉门禁 | 迁移后的最低验收基线 |

## 3. 数据模型：语义、视觉和坐标分别放在哪里

### 3.1 `LabScene`

`LabScene` 是一个手写可视化场景：

- `scene_id` 是 fixture ID，不是 architecture ID；
- `nodes`/`edges` 是当前场景的外层图；
- `paper_width`/`paper_height` 只决定 SVG 画布；
- `layout_profile="paper"` 选择论文式展开算法，否则使用 `freeform`；
- 坐标只用于视觉回归，不能证明执行顺序或包含关系。

`src/scenarios.ts` 的 `scene()`、`node()`、`edge()` 是创建普通场景的薄封装；`paperScene()` 和 `paperNode()` 额外设置 `layout_profile`、`layout_lane`、`layout_rank` 与 `paper_tone`。

### 3.2 `LabNode`

节点的字段分成三组：

| 字段 | 含义 | 注意事项 |
|---|---|---|
| `scene_node_id` | 场景内稳定引用 | 仅在手写 fixture 内稳定 |
| `label`、`secondary_label` | 展示名称与简述 | 不是源码符号 ID |
| `shape` | 收起状态的语义图例 | 表达“如何读这个节点”，不是精确类名 |
| `bounds` | 外层位置和尺寸 | 视觉状态，不是架构事实 |
| `detail_kind` | 展开模板选择器 | 决定 `buildModuleDetail()` 的分支 |
| `detail_expanded` | 派生的展开状态 | `expandScene()` 生成，不写回基础 fixture |
| `layout_lane`、`layout_rank` | 论文视图的列和层级 | 只参与 paper 展开布局 |
| `paper_tone` | Encoder/Decoder/Input/Output 色调 | 视觉编码，不改变计算语义 |

### 3.3 为什么使用这 11 种节点图例

`NodeShape` 不是 Python 类型枚举，而是架构阅读语法：

| `NodeShape` | 适用代码结构 | 使用原因 |
|---|---|---|
| `operation` | Linear、Dropout、投影、通用函数/模块 | 单输入输出变换，没有更专用语义 |
| `tensor` | embedding、hidden state、memory、显式张量 | 强调它是数据/表示，而不是执行算子 |
| `convolution` | Conv、feature-map block、pooling 目录节点 | 堆叠特征图最容易表达空间/通道语义 |
| `attention` | self/cross attention、Encoder/Decoder stack | 强调 Q/K/V 关系和可展开注意力结构 |
| `normalization` | LayerNorm/BatchNorm/Add & Norm 外层 | 统计和仿射归一化具有独立视觉语义 |
| `condition` | mask、gate、bias、决策或训练条件 | 输入控制“哪些值可见/哪条路径生效” |
| `merge` | 多路汇聚、加权汇聚、共享调用参数汇聚 | 多条输入进入一个语义边界 |
| `add` | 残差加法或显式 `+` | 与 concat、一般 merge 区分，表示逐元素和 |
| `multiply` | 门控、逐元素乘法、缩放 | 对应 `*`/Hadamard product，而不是普通模块 |
| `concat` | 通道/特征拼接 | 输出维度通常因拼接而变化 |
| `io` | token 输入、最终输出、外部系统边界 | 显示模型图边界，而非内部计算 |

同一个 Python 类在不同层级可能使用不同图例。例如完整 Encoder stack 收起时用 `attention`，展开后的 hidden state 用 `matrix`，内部 LayerNorm 用 `rect/capsule`。这是“层级阅读目的”不同，不是类型冲突。

### 3.4 `LabEdge` 和七种关系

| `EdgeRelation` | 源码语义 | 视觉解释 |
|---|---|---|
| `flow` | 普通返回值/张量传递 | 主数据流 |
| `branch` | 一个值进入多个计算分支 | 扇出 |
| `merge` | 多个值汇入算子 | 汇聚输入 |
| `residual` | identity/skip path | 虚线捷径 |
| `memory` | Encoder memory、cache、共享状态引用 | 跨模块读写，不等价于普通顺序调用 |
| `condition` | mask、attention bias、gate、配置条件 | 控制输入，不当作主张量流 |
| `feedback` | recurrent/cache/environment 更新回路 | 虚线回边 |

`target_port_role` 是比关系颜色更精确的端口约束。当前 paper Transformer 使用 `mask` 和 `memory`，让场景外边进入展开模板的语义端口，而不是默认进入父框左/下边界。

### 3.5 内部图元

`module-details.ts` 与 `catalog-details.ts` 不直接创建 `LabNode`，而是返回 `DetailPrimitive[]`：

- `rect`：算子、模块或语义分组框；
- `matrix`：张量、feature map、权重或中间表示；
- `circle`：`+`、`×`、`Σ`、激活/门等运算点；
- `flow`：内部依赖，`marker:false` 时是无箭头 wire；
- `text`：说明性标注，不参与执行图。

`tone` 只区分通道和视觉层次。蓝/绿/粉/橙/紫不能单独证明任何固定数学语义；真正的语义仍来自 label、channel、target role 和证据绑定。

## 4. 从 Python 源码人工建模为当前视图

### 4.1 建模步骤

当前四个 Transformer 场景实际遵循下列人工步骤：

1. 找到顶层 `forward()` 或框架 body 函数，列出输入、输出和调用顺序。
2. 找到构造函数/配置，确认层数、hidden size、head 数、FFN 宽度、dropout、norm 顺序和权重共享。
3. 找到 mask/bias 的创建位置，区分 padding、causal、encoder-decoder bias。
4. 找到 Encoder/Decoder layer 的边界，把重复层折叠成 `Stack ×N` 父节点。
5. 把函数参数或返回值中的数据依赖建成边；调用本身只有在需要汇聚多个参数时才建成视觉节点。
6. 为可递归解释的父节点设置 `detail_kind`，在 `module-details.ts` 建立内部图。
7. 依据执行语义选 `shape`：张量用 matrix/tensor，控制量用 condition，逐元素运算用 circle/add/multiply，模块调用用 rect/operation/attention。
8. 对不能由当前源码直接证明的部分标为视觉简化，而不是补造事实。

### 4.2 父子模块如何对应

外层父节点与内部模板的绑定是：

```text
LabNode.detail_kind
  -> EXPANDED_DETAIL_SIZES[detail_kind]
  -> buildModuleDetail(detail_kind, bounds)
  -> ModuleDetailDiagram { entryPoint, exitPoint, semanticInputPorts, primitives }
```

以经典 Encoder 为例：

```text
scenarios.ts
  transformer-encoder
  detail_kind = transformer-encoder
      |
      v
module-details.ts
  transformerEncoderDiagram()
  x -> Self-attention -> Dropout -> Add & Norm
    -> Feed-forward -> Dropout -> Add & Norm -> memory
      |
      v
detail-layout.ts
  Self-attention -> attention
  Add & Norm    -> add-norm
  Feed-forward  -> feedforward
```

`inferNestedDetailKind()` 当前根据父模板类型以及内部图元的可见 label/note 推断下一层：Transformer 父模板有显式规则；目录模板还使用正则启发式，例如 label 含 `conv` 推为 `convolution`、含 `pool` 推为 `pooling`。这适合原型，但正式程序不能依赖可翻译文案。应把下一层模板 ID 写进模板 slot 或正式 binding。

### 4.3 内部节点身份和当前限制

`listDetailNodes()` 只把非 frame 的 `rect`、`circle`、`matrix` 变为可选择/拖动的 `DetailNode`。其 ID 由 `detailNodeId(primitiveIndex)` 生成：

```text
detail-node-${primitiveIndex}
```

所以在 `DetailPrimitive[]` 前面插入图元，会改变后续所有子节点 ID，并可能使保存的展开路径和拖动 offset 指向错误节点。这是迁移时必须消除的技术债：正式模板应为每个语义 slot 提供稳定 ID，例如 `encoder.self_attention`、`decoder.cross_attention`、`ffn.expand`，并把它绑定到 canonical/evidence ID。

## 5. 父子展开、内部拖动和原子收束

### 5.1 外层展开

`expandScene()` 总是从基础 `LabScene` 重新派生显示场景，基础坐标不被展开状态覆盖。因此收起后能确定性回到原布局。

普通 `freeform` 场景：

- 按父节点原始 x 排序处理；
- 展开宽度增加多少，就把其右侧节点累计右移多少；
- 递归内容比模板自然高度更高时，位于其下方的节点向下移动；
- 展开父节点以自然高度围绕原中心放置；
- `paper_width/height` 随内容增长。

`paper` 场景：

- 按 `layout_lane` 分 Encoder/Decoder 列；
- 按 `layout_rank` 判断同列上下关系；
- 展开高度全部向上增长，保持底部进入、顶部退出；
- 同 rank 的辅助节点若与展开框重叠，会被推到框的左右；
- 两列之间至少保留 `PAPER_LANE_GAP=72`；
- 全图不足 36 px 边距时整体平移。

### 5.2 递归内联展开

`buildInlineDetailLayout()` 的递归过程是：

1. 以 `buildModuleDetail()` 创建本层自然图；
2. 应用本层拖动/尺寸 override；
3. `listDetailNodes()` 找到可交互子节点；
4. 根据 `DetailExpansionBranch` 找到需要展开的子节点；
5. 为每个子节点递归调用 `buildInlineDetailLayout()`；
6. 用 `automaticExpandedBounds()` 给子树腾出空间；
7. 重算语义分组框、入口/出口、内部 flow 与避障；
8. 返回 `InlineDetailLevel` 树。

`detailLevelKey(rootId, levelPath)` 使用 `rootId/childId/...` 标识每一级。`clampDetailOffsetToBounds()` 限制拖动后的子节点仍位于当前内容边界内。拖动不是修改 `DetailPrimitive` 源模板，而是保存每层的 offset map，再重建布局。

### 5.3 `recursive` 与 `atomic-bottom-up`

两种层级路由模式共享同一详情树：

- `recursive`：每一级父图先接到展开子框的边界，再由子框接到内部节点；便于对照，但会看到中间边界箭头。
- `atomic-bottom-up`：默认模式；先构造最深原子图，再把入口/出口逐层投影到外层，隐藏仅用于穿越父边界的桥接箭头。

`buildAtomicHierarchyProjection()` 为每个详情层建立：

- `AtomicNodeRecord`：未被继续展开的最深可见图元；
- `AtomicEdgeRecord`：内部 flow；
- `BoundaryPortal`：每层 entry/exit；
- `PortalChain`：父模块与展开子模块的门户对应。

`projectedAtomicEntry*()` 和 `projectedAtomicExit*()` 沿唯一的桥接边向下寻找真正原子端点。`buildAtomicHierarchyRoutingPlan()` 再产出：

- `boundaryPorts`：外层边应实际接到的位置；
- `semanticInputs`：`mask`/`memory` 等定向端口；
- `hiddenFlowIds`：已经由外边替代的内部桥接段；
- `foregroundFlowIds`：跨层边，必须画在节点之上。

这样一条外层 `memory -> decoder` 边在 Decoder 展开后能直接接到内部 cross-attention 的 memory 端口，而不会在父边界留下重复箭头。

## 6. 路由、标签、绘制和导出

### 6.1 五种路由

`routeScene()` 提供：

- `direct`：端点直线；
- `orthogonal`：简单正交折线；
- `channel`：按并行边 lane 分槽；
- `curve`：曲线路径；
- `adaptive`：端口选择、分散、避障、路径搜索和圆角折线的组合。

自适应路由的关键实现：

1. `selectSidePair()` 比较四侧候选，避免明显反向出发；
2. 多条边在同一侧由 `assignAdaptivePorts()` 分散，降低端口拥挤；
3. 端口外加 `PORT_STUB=24`，保证箭头离开边框后再转弯；
4. 所有节点障碍膨胀 `NODE_CLEARANCE=14`；
5. `orthogonalSearch()` 以端点和障碍边界建立可见网格；
6. 用 Dijkstra 式搜索最小化长度、折点代价和 `routePenalty()`；
7. 已使用线段进入惩罚，减少交叉和共享线段；
8. `roundedPolylinePath()` 输出圆角 SVG path；
9. 纵向主段的 label angle 为 90 度。

当目标边有 `target_port_role` 时，`adaptiveRoutes()` 优先使用目标详情的 `semanticInputs[role]`，并把该跨层边设置为 foreground；这就是 paper 场景中 mask 和 memory 不落到默认入口的原因。

### 6.2 指标

`measureScene()` 计算：交叉、线段重叠、穿越节点、标签撞节点、净距违规、端口拥挤、反向出发、共享长度、折点数和总路径长度。这些指标用于比较路由方案，不是对模型正确性的证明。

### 6.3 React 绘制顺序

`App.tsx` 的派生顺序是：

```text
editor.scene + expandedNodeIds
  -> expandScene() 得到 displayScene
  -> buildInlineDetailLayout() 得到 detailTrees
  -> buildAtomicHierarchyRoutingPlan() 得到边界端口/隐藏段/前景段
  -> routeScene() 得到 routed edges
  -> 背景边
  -> NodeGraphic（含递归详情）
  -> 前景跨层边
```

背景边先画、节点后画、语义端口边最后画，是为了让普通长边被节点遮挡，而进入内部原子节点的跨层边保持可见。

### 6.4 静态导出

`renderSceneSvg()` 重复同一派生链，但不依赖 React。`vite.config.ts` 的 `generateBundle()`：

- 为每个场景生成 45 个基础 SVG/JSON；
- 为每个可展开父节点生成单独展开快照；
- 为该场景生成“全部展开到原子级”快照；
- 生成每场景索引、总索引和 `manifest.json`。

交互导出的 JSON 还包含 visual options、展开 ID、递归 expansion tree、拖动 offsets、层级路由模式、指标和内嵌 SVG。

## 7. 30 个场景逐项实现

### 7.1 18 个路由和视觉压力场景

这些场景是路由/图例回归 fixture，不是从某个真实模型源码恢复出的执行图。

| 场景 ID | 手写拓扑和图例 | 验证的实现 |
|---|---|---|
| `linear-chain` | IO -> tensor embedding -> attention -> normalization -> projection | 最短主链、均匀端口、短标签的基线 |
| `fan-out` | shared tensor 扇出 Q/K/V 和 gate，再汇入 attention | 一源多边端口分散、branch/condition/merge 颜色和标签 |
| `fan-in` | 四个 expert 汇入 weighted merge，再接 norm/head | 多源进入同目标时的端口拥挤和终段净距 |
| `residual-skip` | attention/dropout 主链与 input residual 在 Add 汇合 | 长跳连、虚线 residual、主链避让 |
| `feedback-loop` | recurrent cell 产生 emission 和 continue 条件，条件回写 state | feedback 回边、循环拓扑和条件出口 |
| `dense-bipartite` | 左 3 节点到右 3 节点全连接 | 9 条边集中交叉时的分槽、标签碰撞和共享线段惩罚 |
| `shared-hub` | producer/consumer/cache 环绕 shared memory | 高度数中心节点、读写方向和环状端口选择 |
| `crossing-pressure` | 左右各四节点按逆序连接 | 不可避免交叉下的路径分流与确定性 |
| `parallel-relations` | 相同 source/target 同时有 flow、memory、residual，另有 mask/cache | 同端点多语义边的 lane 分离、关系颜色和回边 |
| `long-labels` | 三个超宽节点、长副标题和长边标签，另有跨越 residual | 文本不溢出、标签底板、标签避让和宽节点锚点 |
| `asymmetric-sizes` | 标量、高窄 condition、超宽 operation、方形 merge 混排 | 四侧选择面对非均匀尺寸时的稳定性 |
| `vertical-dag` | 上到下分支、跨层 memory、skip 和 concat | 非默认纵向 DAG、top/bottom 端口及多层汇聚 |
| `nearest-side-regression` | source 在 target 右侧，中间有大障碍 | 不能从错误侧反向离开；验证最近侧与绕障选择 |
| `terminal-fan-in` | 六个上下分布的 source 进入一个高 target | 同目标端口分散、箭头末段长度、箭头头部遮挡 |
| `four-side-ports` | 左右上下八个节点进入中心 Add | 四侧入射、角点净距、目标侧容量 |
| `vertical-edge-labels` | 两列纵向链和横向交叉连接 | 长纵向段的标签旋转 90 度及标签/节点净距 |
| `semantic-glyph-library` | tensor、conv、attention、norm、add、multiply、concat 等图例共存 | `NodeShape` 的 SVG 语法、颜色和混合关系可读性 |
| `dense-channel-separation` | 五对平行边、五条逆序交叉边和中心障碍 tensor | 高密度通道搜索、共享线段惩罚和顺序稳定性 |

### 7.2 `parent-child-expansion`

该场景串联 `tensor-transform`、`convolution`、`attention`、`add-norm`、`feedforward` 五种父模板。它的目的不是表达一个权威模型，而是覆盖完整展开契约：

- 所有父模块收起时仍是普通 `LabNode`；
- 展开后入口与原外边连续、出口与下游边连续；
- attention 内部 Q/K/V、Add & Norm 的残差、FFN 的两层投影都可选择；
- Transformer 类子图可继续钻取下一层；
- 父节点变宽后，下游节点由 `expandScene()` 增量右移；
- 内部拖动只改变 detail offsets，相关内部 flow 重新吸附并避让。

### 7.3 `extended-module-catalog`

该场景串联四个有独立内部图的基础模块：

| 父节点 | 展开实现 | 为什么使用该图例 |
|---|---|---|
| Embedding | `embeddingDiagram()`：token/position 两路 lookup、加法、可选 norm、dropout | token/position 是张量，lookup 是操作，加法用 `+` |
| LSTM cell | `recurrentDiagram()`：`x_t/h_{t-1}/c_{t-1}`、四门、乘加、`c_t/h_t` | gate 是条件，状态是 matrix，逐元素乘加用圆形运算符 |
| Sparse MoE | `mixtureOfExpertsDiagram()`：router、top-k、多个 expert、加权 `Σ` | router 决定分支，expert 是并行 FFN，`Σ` 表示加权汇聚 |
| Pooling | `poolingDiagram()`：feature map、window、reduction、pooled map | 特征图使用堆叠 matrix，窗口是参数/观察区域而非新张量 |

### 7.4 六个模型家族目录场景

`detailCatalogScene()` 为每个目录自动建立 `Input -> 五个模块 -> Output` 的外层线性链；这条链仅用于逐个展开和比较图例，不表示五类模型会在一次推理中串行执行。真正的内部图由 `buildCatalogDetail()` 分发。

| 目录场景 | 五个 `detail_kind` | 内部结构重点与图例理由 |
|---|---|---|
| `traditional-ml-catalog` | `linear-model`、`kernel-machine`、`decision-tree`、`ensemble`、`clustering` | 线性 score/link；核映射和 margin；阈值二叉路径；并行 learner 汇聚；assign/update 迭代。条件节点用于决策，merge 用于投票/聚合 |
| `neural-foundation-catalog` | `decomposition`、`mlp`、`normalization`、`residual-block`、`dense-connection` | 矩阵基与投影；升维-激活-降维；统计量与仿射；identity skip 加法；跨层 concat。分别使用 tensor、operation、normalization、add、concat |
| `vision-sequence-catalog` | `inception`、`depthwise-convolution`、`unet`、`vision-transformer`、`gru` | 多尺度卷积分支、DW/PW 分离、U-Net 跳连、patch token + Transformer、GRU 门控；使用卷积堆栈、concat、attention 和乘加符号 |
| `sequence-generative-catalog` | `bidirectional-recurrent`、`seq2seq`、`state-space`、`autoencoder`、`variational-autoencoder` | 正反向状态 merge；encoder-context-attention-decoder；selective scan；latent bottleneck；μ/logσ² 与重参数采样。state/tensor 与 condition 分开显示 |
| `generative-graph-catalog` | `gan`、`diffusion`、`normalizing-flow`、`graph-message-passing`、`time-series-forecast` | 对抗双路径；加噪/去噪时间条件；可逆链与 log-det；message/aggregate/update；trend/seasonal 汇合。回路、条件与 merge 按训练/数据依赖区分 |
| `multimodal-rl-adaptation-catalog` | `dual-encoder`、`dqn`、`actor-critic`、`distillation`、`adapter-lora` | 图文双塔相似度；Q/target/replay 闭环；actor/critic/advantage；teacher/student loss；冻结主干与低秩增量相加。merge、feedback、add 分别表达对齐、更新和参数增量 |

目录内部图是“家族结构模板”，不是每个具体模型的精确执行图。例如 `ensemble` 同时概括 bagging 的并行投票和 boosting 的残差序列；`normalization` 同时概括 Batch/Layer/Group/RMSNorm。正式程序只有在 predicate 证明具体变体后才能标为 `exact`，否则应保留为 `schematic` 或 `opaque`。

## 8. 四个 Transformer：共同语义和两种构图语法

四个场景不是四份无关模型：

| 模型语义 | 横向工程视图 | 双列论文视图 |
|---|---|---|
| 本地教学版经典 Encoder-Decoder Transformer | `classic-transformer` | `paper-classic-transformer` |
| Tensor2Tensor 1.0.14 Transformer | `tensor2tensor-transformer` | `paper-tensor2tensor-transformer` |

横向视图把数据和调用参数从左到右摊开，适合调试、端口和路由验证；论文视图把 Encoder/Decoder 分成两列，自下向上流动，适合与论文架构图对照。两种视图应该共享同一语义 IR，差别只应存在于 layout profile、模板 orientation 和显示层级。

## 9. 经典 Transformer 的 Python 证据

权威本地文件：

```text
/home/fzg/PycharmProjects/ArchCanvas/Article/classic_transformer.py
```

同一 `Article/` 目录下的
`/home/fzg/PycharmProjects/ArchCanvas/Article/Transformer.py` 与它的 SHA-256 完全相同：

```text
49c31f68d36406e5990d3761c9a6d23ba38b5ed7d8d622e0999b1e9b415a48b7
```

关键源码范围：

| 源码范围 | 事实 |
|---|---|
| 40-65 | 默认 `d_model=512`、6 层 Encoder、6 层 Decoder、8 heads、`d_ff=2048`、dropout、post-norm 和权重共享开关 |
| 82-129 | 固定 sin/cos positional encoding 与 dropout |
| 132-157 | token lookup 并乘 `sqrt(d_model)` |
| 160-219 | scaled dot-product attention：score、mask、softmax、dropout、乘 V |
| 222-291 | Q/K/V 投影、拆 heads、合 heads、输出投影 |
| 294-316 | 两层 position-wise FFN |
| 319-384 | EncoderLayer 调用次序、dropout、residual 和 LayerNorm |
| 387-484 | DecoderLayer 的 masked self-attn、cross-attn、FFN 和三次 Add & Norm |
| 487-582 | Encoder/Decoder stack 的层循环和最终输出 |
| 670-675 | target embedding 与 output projection 的权重绑定 |
| 677-733 | padding mask、causal mask、target mask 组合 |
| 775-853 | 顶层 `forward()` 的完整数据流 |

### 9.1 `classic-transformer`：横向外层节点映射

| 视图节点/边 | Python 对应 | 为什么这样画 |
|---|---|---|
| `Source tokens [B,S]` | `forward(src_tokens, ...)` 的整数 token 输入 | 模型边界用 `io`；token ID 还不是 hidden tensor |
| `Source embedding` | `src_tok_emb` + `src_pos_enc` | 输出为 `[B,S,D]`，用 `tensor`；设置 `sinusoidal-embedding` 以展开 lookup、PE、加法和 dropout |
| `Source padding mask` | `make_padding_mask()` | 布尔值决定可见 key，不是主 hidden state，使用 `condition` |
| `Encoder call` | 顶层对 encoder 的调用参数汇聚 | `states + src_mask` 汇入一个边界，使用 `merge`；它不是 Python 中新增的一层网络 |
| `Encoder Stack ×6` | `TransformerEncoder` 和六个 `EncoderLayer` | 重复层折叠为父模块，收起用 `attention`，展开用 `transformer-encoder` |
| `Encoder memory` | encoder 返回的 `[B,S,512]` | 是供 decoder cross-attention 读取的张量，使用 `tensor` |
| `Target tokens` | teacher-forcing 下右移的目标 token | 外部输入边界，使用 `io` |
| `Target embedding` | target embedding + position；权重与 projection 共享 | 使用同一 `sinusoidal-embedding` 模板；副标题明确 shared W |
| `Target mask` | padding mask 与 causal mask 的逻辑合取 | 控制 self-attention 可见范围，使用 `condition` |
| `Decoder call` | decoder states、memory、target mask、memory mask 的参数汇聚 | 同样只是视觉汇聚点，不是额外层 |
| `Decoder Stack ×6` | 六个 `DecoderLayer` | 用 `transformer-decoder` 展开 masked self、cross-attn、FFN |
| `Output projection` | `Linear(512, vocab, bias=False)` | 实际算子，用 `operation`；`shared W^T` 写入副标题 |
| `Vocabulary logits [B,T,V]` | 顶层 forward 返回 logits | 模型输出边界，用 `io` |
| memory -> Decoder call | decoder cross-attention 的 K/V | 关系是 `memory`，与普通顺序 flow 区分 |
| src mask -> Decoder call | cross-attention 的 memory mask | 关系是 `condition`，说明它控制 memory keys |

### 9.2 Encoder 父模块内部图

`transformerEncoderDiagram()` 对应单个 `EncoderLayer`，顶部文字 `×6` 表示 stack 重复，不是把六层逐一绘出：

```text
x
 -> Self-attention(Q=K=V=x, source padding mask)
 -> Dropout
 -> Add & Norm(post-LN, residual=x)
 -> Feed-forward(512 -> 2048 -> 512)
 -> Dropout
 -> Add & Norm(post-LN)
 -> memory
```

图中两条弧形/正交 residual channel 分别绕过 attention 子层和 FFN 子层。使用 `Add & Norm` 矩形而不是一个普通 operation，是因为源码明确有逐元素残差相加和 LayerNorm 两个语义步骤，且它们还可以继续展开成 `F(x)`、`x`、`+`、LayerNorm。

### 9.3 Decoder 父模块内部图

`transformerDecoderDiagram()` 对应：

```text
y
 -> Masked self-attention(target padding + causal mask)
 -> Dropout -> Add & Norm
 -> Cross-attention(Q=decoder, K/V=encoder memory, source padding mask)
 -> Dropout -> Add & Norm
 -> Feed-forward -> Dropout -> Add & Norm
 -> decoded
```

这里必须区分三类输入：

- `y` 是主数据入口；
- target mask 控制 masked self-attention；
- encoder memory 和 source mask 控制 cross-attention。

横向模板目前把 target mask/source mask 画在父模块内部；paper 模板则通过显式 `semanticInputPorts` 接收外层 mask/memory，体现了迁移时应采用的更精确端口模型。

### 9.4 Attention 的下一层展开

`attentionDiagram()` 把 `MultiHeadAttention.forward()` 映射为：

```text
输入
 -> Q/K/V 三路 Linear
 -> h × Q/K/V
 -> Q × K^T
 -> scale by 1/sqrt(d_k)
 -> Softmax（源码中 mask 在 Softmax 前应用）
 -> attention weights × V
 -> context
 -> Concat heads
 -> W^O
 -> output
```

Q/K/V 使用不同颜色 matrix，是因为它们是不同投影后的张量通道；`×` 用圆形图例，因为对应矩阵乘；Softmax/Linear 用矩形，因为是算子；weights/context/output 用 matrix，因为是中间张量。当前通用 attention 详情没有单独画 mask 输入，mask 在 Encoder/Decoder 上一层表达。

### 9.5 Sinusoidal embedding 的下一层展开

`sinusoidalEmbeddingDiagram()` 映射为 token ID -> TokenEmbedding -> 乘 `sqrt(d_model)`，以及 position -> 固定 sin/cos PE，两路在 `+` 汇合，再经 dropout 输出 `[B,L,D]`。固定 PE 使用橙色 operation 而不是参数 matrix，是为了强调它由公式/注册 buffer 生成、没有可训练权重。

## 10. Tensor2Tensor 1.0.14 的 Python 证据

权威本地包：

```text
/home/fzg/PycharmProjects/ArchCanvas/Constraint relationship of architecture diagram/tensor2tensor-1.0.14.tar.gz
```

包内文件：

```text
tensor2tensor-1.0.14/tensor2tensor/models/transformer.py
```

关键源码范围：

| 源码范围 | 事实 |
|---|---|
| 44-75 | `model_fn_body()`：prepare encoder/decoder、调用 stacks、返回 decoder output |
| 78-106 | `transformer_prepare_encoder()`：`flatten4d3d`、padding bias、target-space embedding、timing signal |
| 109-126 | `transformer_prepare_decoder()`：shift-left、decoder self-attention bias、timing signal |
| 129-167 | Encoder stack：self-attention、dropout、residual/norm、FFN |
| 170-226 | Decoder stack：masked self-attention、encoder-decoder attention、FFN |
| 229-265 | `transformer_ffn_layer()` / `conv_hidden_relu` |
| 269-306 | base 参数：hidden 512、6 层、8 heads、filter 2048、共享 embedding/softmax |

### 10.1 `tensor2tensor-transformer`：横向外层节点映射

| 视图节点/边 | Tensor2Tensor 对应 | 为什么这样画 |
|---|---|---|
| `Inputs` | `features["inputs"]` 后的 `flatten4d3d` | 框架输入通常带额外 4D 维度，节点副标题保留 flatten 事实 |
| `Target space id` | `features["target_space_id"]` 的 32 维 learned embedding | 它条件化 encoder input，不是主 token 流，所以用 `condition` |
| `Encoder prepare` | flatten + target-space embedding + timing signal | 多个张量操作汇成 encoder states，用 `tensor` + `tensor-transform` 详情 |
| `Encoder attention bias` | `attention_bias_ignore_padding()` | 以大负数加到 logits，不是 bool mask，仍属于 `condition` |
| `Encoder call` | encoder states + bias 参数汇聚 | 视觉汇聚点，不是源码额外层 |
| `Encoder Stack ×6` | `transformer_encoder()` | `tensor2tensor-encoder` 模板标出 bias 与 `conv_hidden_relu` |
| `Encoder output` | encoder 返回的 memory | decoder cross-attention 的 K/V，使用 `tensor` |
| `Targets` | `features["targets"]` teacher-forcing 输入 | 模型边界 `io` |
| `Decoder prepare` | shift-left + timing signal | 使用 `tensor-transform` 表示 shape/position 预处理 |
| `Decoder self-attention bias` | lower-triangle bias | causal 约束以负 bias 实现，使用 `condition` |
| `Decoder call` | states + encoder output + 两类 bias | 参数汇聚，不是新层 |
| `Decoder Stack ×6` | `transformer_decoder()` | 展开 masked self、cross attention、conv FFN |
| `Shared softmax` | `shared_embedding_and_softmax_weights=True` 及 T2T modality 输出层 | 表达 tied weights；实际 projection/softmax 由 modality/runtime 层完成，不是 `model_fn_body()` 内直接调用 |
| `Target logits` | 框架输出 logits | 模型边界 `io` |

### 10.2 T2T 内部图如何复用经典模板

`tensor2tensorEncoderDiagram()` 和 `tensor2tensorDecoderDiagram()` 不重新画一套坐标，而是先调用经典 `transformerEncoderDiagram()`/`transformerDecoderDiagram()`，再遍历 primitives 替换：

- 层标题中的参数名称；
- `Feed-forward` note 为 `conv_hidden_relu · filter=2048`；
- source padding mask 为 encoder attention bias；
- target mask 为 lower-triangle decoder bias；
- source memory mask 为 encoder-decoder bias；
- 底部解释文字。

这种复用是合理的，因为两个实现共有 self-attention、cross-attention、residual、norm 和两阶段 FFN 的宏观拓扑；差异主要是条件量表示和 FFN 实现。但正式模板不应通过可见 label 搜索后替换，应让一个参数化 Transformer 模板接收 `mask_mode`、`ffn_kind`、`norm_order`、`activation` 等配置。

### 10.3 当前 T2T 场景的一个语义偏差

横向和 paper T2T 场景目前都把 `Target space` 条件边接到 `Inputs`，而源码实际在 `transformer_prepare_encoder()` 内把 target-space embedding 加到 encoder input。迁移时应把它绑定到 `Encoder Prepare` 的 `condition:target-space` slot，不能照搬当前边的 target node。

## 11. 两个论文式 Transformer 场景

### 11.1 公共布局语法

paper 场景使用：

- `layout_profile="paper"`：选择向上增长的展开算法；
- `layout_lane="encoder" | "decoder"`：保持双列；
- `layout_rank`：维护同列的上下顺序；
- `paper_tone`：区分 encoder、decoder、input、output、neutral；
- 主数据流从节点底部进入、顶部退出；
- mask 从侧边进入，memory 从 Encoder 列横向进入 Decoder cross-attention。

`paperVerticalBoundary()` 用于把原本左入右出的 attention/FFN/Add-Norm/embedding/tensor-transform 详情转换成底入顶出：它只改触及水平父边界的首尾 flow，内部拓扑保持不变。

`paperTransformerEncoderDiagram()` 和 `paperTransformerDecoderDiagram()` 则原生按纵向坐标绘制大层：底部 input、向上经过 attention/Add & Norm/FFN、顶部 output。它们为 `mask`/`memory` 创建显式 `semanticInputFlow()`。

### 11.2 `paper-classic-transformer`

Encoder 列从下到上：

```text
Inputs -> Input Embedding
      + Positional Encoding -> +
      -> Encoder N× -> Encoder memory
```

Decoder 列从下到上：

```text
shifted Outputs -> Output Embedding
              + Positional Encoding -> +
              -> Decoder N×
              -> Linear -> Softmax -> Output Probabilities
```

source mask 以 `target_port_role="mask"` 进入 Encoder 内部 self-attention；target mask 进入 Decoder masked self-attention；Encoder memory 以 `target_port_role="memory"` 进入 Decoder cross-attention。使用侧入端口而不是接到父框底部，是因为它们不是 decoder 主 hidden stream。

已知重复风险：外层已经有单独的 `Positional Encoding + Add`，但 `Input/Output Embedding` 的 `paper-sinusoidal-embedding` 详情内部又包含 PE 和加法。收起时读图正确，展开时会把 PE 表达两次。正式迁移应二选一：

- 把 embedding 详情拆成 `token-embedding`，外层保留 `position-encoding` 与 `position-add`；或
- 外层合并成 `token+position embedding` 一个父节点，内部再展示两路与加法。

推荐第一种，因为它能让 Python/IR 中的 token lookup、position function、add、dropout 分别绑定 evidence 和 canonical IDs。

### 11.3 `paper-tensor2tensor-transformer`

Encoder 列：

```text
Inputs -> Encoder Prepare(target-space + timing)
       -> Encoder N×(attention bias, conv FFN)
       -> Encoder Output
```

Decoder 列：

```text
Targets -> Decoder Prepare(shift-left + timing)
        -> Decoder N×(causal bias + encoder output/bias)
        -> Shared Softmax -> Target Logits
```

它与 paper classic 共享双列和向上流动语法，但刻意显示 T2T 的四个差异：target-space embedding、attention bias、timing signal、`conv_hidden_relu`/shared softmax。

`paper-tensor2tensor-encoder/decoder` 复用 `paperTransformer*Diagram(bounds, true)`，通过布尔参数替换标题、bias 文案和 FFN note。迁移到正式程序时，应把该布尔值改为结构化模板参数，避免以后为更多变体继续增加布尔组合。

### 11.4 `target_port_role` 的完整链路

paper 场景的语义边通过以下链路落到内部端口：

```text
LabEdge.target_port_role = "mask" / "memory"
  -> buildModuleDetail().semanticInputPorts
  -> buildAtomicHierarchyRoutingPlan().boundaryPorts[node].semanticInputs
  -> adaptiveRoutes() 选择 semantic target point/side
  -> route.foreground = true
  -> App/svg-export 在节点之后绘制该边
```

这套机制是四个 Transformer 中最值得迁入主程序的部分之一，但正式类型应允许一个节点有多个命名 input port，而不是用一个可选字符串绕过通用端口模型。

## 12. 图例选择和源码结构之间的判定规则

后续把新 Python 模型迁入正式程序时，可用以下规则，但判定必须来自 IR/evidence，而不是源码文本正则：

| 源码结构 | 父节点/内部图例 | 判定理由 |
|---|---|---|
| `nn.Module`/函数对输入做单一变换 | `operation` / `rect` | 强调执行单元 |
| 变量被多个后续算子读取 | `tensor` / `matrix` 加多条出边 | 这是共享数据，不应复制成多个模块 |
| `x + f(x)` | `residual` 边 + `add`/`+` | 显式保留 identity 与变换支路 |
| `torch.cat` | `concat` | 与逐元素 add 的 shape 语义不同 |
| `a * b`、gate | `multiply`/`×` | 表示逐元素或矩阵乘时应在 note/channel 中进一步区分 |
| bool mask 或 large-negative bias | `condition` 输入 | 控制 attention logits，不是 hidden flow |
| Q/K/V 投影和 attention | `attention` 父节点；matrix + multiply + softmax 内图 | 使 query/key/value 与概率权重可追踪 |
| 重复 `ModuleList`/layer loop | 可展开 stack 父节点 + `×N` | 避免平铺 N 份，同时保留数量证据 |
| weight tying | `parameter-share`（正式 IR）或清晰标注 | 不能只靠两个节点同名；应绑定同一参数 canonical ID |
| reshape/permute/flatten | `shape-transform`（正式 relation）或 tensor-transform 模板 | 这是 shape/布局变化，不一定包含可训练参数 |
| dropout/train-only 分支 | `training-only`（正式 relation） | 推理时可能不生效，应与主计算区分 |
| cache/recurrent state | `memory-reference`/`state-update` | 跨时间或跨调用生命周期，不是普通 sequence |

当前原型的 `EdgeRelation` 只有 7 类；正式 `KernelRelation` 已包含 `shape-transform`、`routing`、`parameter-share`、`training-only` 等更精确关系。迁移时应向正式类型靠拢，不要为了兼容原型而降级正式语义。

## 13. 正式 Studio 的现状和正确迁移落点

正式程序已经有如下链路：

```text
FormalStudioState / Exact Architecture IR
  -> studio/src/main-view/formal-state-adapter.ts
  -> KernelDocument
  -> studio/src/visual-kernel/layout.ts
  -> KernelRenderScene
  -> ArchitectureCanvas.tsx / visual-kernel/export.ts
```

`formal-state-adapter.ts` 已把 hierarchy/canonical nodes/template bindings/evidence 转换为：

- `KernelNode.canonicalNodeIds` 与 `containedCanonicalNodeIds`；
- `KernelPort`；
- `KernelEdge.canonicalEdgeIds`、`tensorIds`、`evidenceIds`；
- `KernelTemplateBinding` 的 node/edge/port/tensor slots；
- `KernelVisualState` 中的位置、尺寸、展开和路由偏好。

正式 `visual-kernel` 已经存在：

- `catalog-details.ts`；
- `module-details.ts`；
- `template-details.ts`；
- `routing-engine.ts`；
- `detail-layout.ts`、`layout.ts` 与 `export.ts`。

但当前正式 `NodeDetailKind` 尚不包含 Transformer stack、paper orientation、sinusoidal embedding 专用种类；`layout.ts` 的 detail boundary 目前固定左入右出；门户链也没有原型当前完整的递归原子收束能力。

### 13.1 不应迁移的内容

- 不把 `LabScene` 变成正式模型格式；
- 不把 `scene_node_id` 当 canonical ID；
- 不把 label 正则推断当模板绑定；
- 不把 `bounds`、lane、rank 写入 Exact Architecture IR；
- 不把 `App.tsx` 的本地 undo/redo 状态替换正式 workspace state；
- 不让 visual patch 修改 Python 源码；
- 不因模板“看起来像”就把 fidelity 标为 exact。

### 13.2 应迁移的内容

- `DetailPrimitive` 的视觉词汇和 SVG 渲染参数；
- 参数化 Transformer 模板及命名 semantic slots；
- freeform/paper 的 orientation 和增量展开算法；
- 递归详情布局中的避障、拖动约束和父框增长；
- atomic projection、portal chain、语义端口和绘制层级；
- 自适应路由候选、净距、stub、Dijkstra、惩罚和指标；
- 静态导出与交互渲染共享同一 `KernelRenderScene` 的原则；
- 场景矩阵和展开快照作为 production visual-kernel 回归 fixture。

## 14. 推荐迁移方案

### 阶段 1：先定义正式 Transformer 语义模板

不要直接增加十几个显示专用 `NodeDetailKind`。建议建立一个参数化模板，例如：

```ts
interface TransformerTemplateParameters {
  orientation: "horizontal" | "bottom-up";
  role: "encoder" | "decoder";
  layers: number;
  hiddenSize: number;
  heads: number;
  ffnSize: number;
  attentionMaskMode: "boolean-mask" | "additive-bias";
  ffnKind: "linear" | "conv-hidden-relu" | "gated";
  normOrder: "pre" | "post";
  hasCrossAttention: boolean;
  tiedOutputEmbedding: boolean;
}
```

这些参数必须由 predicate/evidence 证明，并进入 `KernelTemplateBinding.bindingDigest`。orientation 属于 visual state/template rendering，不属于模型事实。

### 阶段 2：使用稳定 slot ID

为模板图元建立稳定 slot，例如：

```text
encoder.input
encoder.self_attention
encoder.self_attention.mask
encoder.residual_1
encoder.norm_1
encoder.ffn.expand
encoder.ffn.activation
encoder.ffn.contract
encoder.residual_2
encoder.output

decoder.self_attention
decoder.cross_attention.query
decoder.cross_attention.memory
decoder.cross_attention.memory_mask
decoder.ffn
decoder.output
```

`RenderDetailPrimitive.primitiveId` 应由 `bindingId + slotId` 构造，不能由数组下标构造。每个 slot 通过 `nodeSlots/edgeSlots/portSlots/tensorSlots` 绑定 canonical IDs，并保留 `evidenceIds`。

### 阶段 3：补齐正式命名端口

将原型的 `target_port_role` 提升为正式端口：

```text
decoder.hidden.input
decoder.self_attention.mask
decoder.cross_attention.memory
decoder.cross_attention.memory_mask
decoder.hidden.output
```

路由只读取 `KernelEdge.sourcePortId/targetPortId`，不读取 label。展开模板负责把 port slot 映射到具体内部图元的位置。

### 阶段 4：统一横向和论文式视图

同一个 `KernelDocument` 应能选择两种 view preset：

- engineering：左到右，显式 prepare/call/mask 参数；
- paper：Encoder/Decoder 双列、底到顶、隐藏部分调用细节。

两者共享 canonical nodes、edges 和 evidence；只更换 layout profile、orientation、折叠粒度和 tone。这样才能避免维护四份手写语义图。

### 阶段 5：迁移原子层级路由

把 `AtomicHierarchyProjection` 的思路改写为基于正式 `KernelNode/KernelPort/KernelModule`：

1. 从已展开模块的真实子节点和模板 slots 建原子图；
2. 为每级 module 建 entry/exit/semantic portals；
3. 根据 canonical edge 和 port slot 建 portal chain；
4. 自底向上选择最深可见端点；
5. 隐藏仅用于父边界桥接的重复段；
6. 将跨层 edge 放入 foreground layer。

### 阶段 6：把当前 30 场景改为正式 fixture

- 18 个压力场景可转成 `KernelDocument` 视觉 fixture；
- 目录场景保留为 schematic template gallery；
- 经典/T2T 各维护一份语义 fixture，再分别应用 engineering/paper visual preset；
- 每个 fixture 同时断言 canonical IDs、ports、template binding、route metrics 和 SVG snapshot；
- 构建矩阵继续覆盖 5×3×3，但把“视觉比较”和“语义正确性”测试分开。

## 15. 已知简化和迁移风险

| 风险 | 当前状态 | 迁移要求 |
|---|---|---|
| Python 到视图不是自动链路 | 完全手写 | 接入正式 static analysis -> Exact Architecture IR；禁止通过导入/执行用户项目取图 |
| 子节点 ID 依赖 primitive index | 插入图元会漂移 | 使用稳定 slot/binding ID |
| 下一层类型依赖可见 label 正则 | 翻译/改名会失效 | 在模板定义中显式声明 nested template |
| paper classic 重复 PE | 外层和 embedding 详情都画 PE | 拆 `token-embedding`/`position-add` 或只保留一个层级 |
| T2T target-space 边目标不准 | 当前接到 `Inputs` | 接到 Encoder Prepare 的 condition slot |
| T2T Shared Softmax 是框架层抽象 | body 中无直接 softmax 调用 | 绑定 modality/runtime evidence，不能伪装成 body 内显式节点 |
| Transformer 参数写死 | 512/6/8/2048、post-LN | 从 IR/template parameters 渲染 |
| Attention 模板省略 mask/dropout/cache/GQA | 只画通用 MHA 核心 | 按变体 predicates 增减 slots |
| 目录图是家族并集 | 不代表任一具体模型全部步骤 | 默认 schematic，满足 exact predicate 后再升级 |
| 原型 visual patch 无来源事务 | 只改内存 `LabScene` | 正式语义编辑必须走 prepare/verify/review/commit |
| paper 属性混在节点上 | lane/rank/tone 和语义节点同对象 | 迁到 `KernelVisualState` 或 layout preset |
| 横向详情部分 mask 是内部装饰 | 与外部 edge 不完全统一 | 全部改为正式命名 port 与 canonical edge |

## 16. 测试与验收清单

迁移或修改原型时至少验证：

1. TypeScript 编译通过：

   ```bash
   npx tsc -p prototypes/scene-visual-lab/tsconfig.json
   ```

2. 原型单元测试通过：

   ```bash
   npx vitest run prototypes/scene-visual-lab/src
   ```

3. 完整静态构建生成 30×45=1350 个基础案例，并生成所有单独展开和全部展开快照。
4. `classic-transformer` 与 `tensor2tensor-transformer` 的 Encoder/Decoder 能展开到 attention、Add & Norm、FFN。
5. 两个 paper 场景保持双列、底入顶出；展开后辅助 mask/bias/PE 节点不与父框重叠。
6. paper Decoder 的 `mask` 和 `memory` 边命中各自内部语义端口。
7. `atomic-bottom-up` 下没有父边界重复箭头；切到 `recursive` 时仍可作为 A/B 基线。
8. 任意内部节点拖动后，父框包含、内部边重吸附、无关节点避让、展开树不丢失。
9. 收起所有详情后基础 `LabScene` 坐标确定性恢复。
10. 负坐标、向左拖动、缩放/平移、导出 SVG/JSON 按 [`REGRESSION_TEST_REQUIREMENTS.md`](./REGRESSION_TEST_REQUIREMENTS.md) 完整检查。
11. 正式程序中每个 exact 图元能追到 canonical IDs、slot IDs 和 evidence IDs；缺证据时必须降级或产生 diagnostic。
12. Source Evidence/IR 与视觉布局冲突时，以 Source Evidence/IR 为准。

## 17. 迁移完成后的目标链路

最终不应保留“四个手写 Transformer 语义场景”，而应形成：

```text
Python 静态分析证据
  -> Exact Architecture IR
  -> hierarchy + canonical nodes/edges/tensors/parameters
  -> predicate-verified KernelTemplateBinding
  -> 一个 Transformer 语义模板 + 参数
  -> engineering 或 paper 视图 preset
  -> recursive detail layout
  -> atomic portal projection
  -> adaptive routing
  -> ArchitectureCanvas / SVG export
```

这样，Python 源码中的父子模块、参数共享、mask/bias、张量通道和执行关系都有正式 ID；当前原型验证过的图例、布局、路由和交互则作为纯视觉层复用。两者的边界清楚后，后续模型变体可以新增证据和模板参数，而不需要再复制一整份场景坐标。

## 18. 注册表驱动的原子节点与受保护模块契约

本节说明如何借鉴 DL-Playground 的节点注册、自动表单、Shape 推导和代码生成机制，在 Scene Visual Lab 内建立第一版“创建节点”能力，并为后续迁入正式 Studio 预留严格的端口契约、版本审核和源码事务边界。

这里的结论不是把 DL-Playground 的 React Flow 节点类复制进来，而是提取它已经验证过的注册表思想，再按 ArchCanvas 的 Source Evidence、Exact Architecture IR 和 visual-kernel 分层重新实现。最重要的约束是：**`LabScene` 仍然只是视觉投影，不能成为模块语义、端口或 Shape 的事实来源。**

### 18.1 DL-Playground 中可复用的设计证据

DL-Playground 已经形成一条浏览器内构图链路，相关源码职责如下：

| 源码 | 当前行为 | ArchCanvas 可复用的思想 | 不应直接照搬的部分 |
|---|---|---|---|
| [`registry.ts:81`](../../../../DL-Playground/frontend/src/nodes/registry.ts) | 按 14 类集中注册节点 | 集中目录、分类检索、从定义生成菜单 | `Record<string, any>` 和模块加载时副作用式组装 |
| [`BaseClass.tsx:18`](../../../../DL-Playground/frontend/src/node_gen/BaseClass.tsx) | `LayerDefinition` 集中声明参数、Shape、成本、代码和组件 | 一个节点类型具有统一的静态能力协议 | 语义定义依赖 React、`any`，并把 `Component` 放进核心协议 |
| [`CreateNodeComponent.tsx:24`](../../../../DL-Playground/frontend/src/node_gen/CreateNodeComponent.tsx) | 从 schema 生成参数表单、Handle、删除和 Shape 预览 | UI 从 schema 投影，不为每个普通节点手写表单 | 组件直接调用 `setNodes/setEdges`，跳过领域命令和审核 |
| [`Conv2dNode.tsx:14`](../../../../DL-Playground/frontend/src/nodes/vision/conv/Conv2dNode.tsx) | 同一节点内实现参数、校验、推导、成本和 PyTorch 字符串 | 原子模块能力完整，可作为首批迁移样例 | 仅支持具体 `number[]`，代码生成是自由字符串拼接 |
| [`graphIR.ts:54`](../../../../DL-Playground/frontend/src/utils/graphIR.ts) | React Flow 图与版本化 GraphIR 互转 | 交互状态与可持久化图模型之间需要适配层 | Handle 是从已存在边反推，缺少预声明的端口语义和基数 |
| [`shape_verifier.ts:23`](../../../../DL-Playground/frontend/src/utils/shape_verifier.ts) | 按依赖就绪顺序传播 Shape | 图级调度应独立于节点 UI | 只按上游节点收集输入，未严格按命名目标端口绑定 |
| [`computeEstimator.ts:26`](../../../../DL-Playground/frontend/src/utils/computeEstimator.ts) | 汇总参数量和 FLOPs | 分析结果可以统一聚合 | 分析结果不应写回 UI 节点的临时字段 |
| [`codeCompile.ts:124`](../../../../DL-Playground/frontend/src/utils/codeCompile.ts) | 调用节点的 init/forward 生成器拼装 Python | 节点定义可选择提供代码生成能力 | 任意字符串难以验证多输出、共享参数、functional op 和控制流 |
| [`RepeatLayer.tsx:20`](../../../../DL-Playground/frontend/src/nodes/control_flow/RepeatLayer.tsx) | 容器节点保存内部节点/边并重复估算 | 复杂节点需要组合语义和专用编辑能力 | 不应把内部 React Flow 数据直接嵌入正式模块定义 |

现有 14 类目录可以原样保留为节点面板的检索分类：

```text
Inputs
Torch Ops
Tensor Shape
Tensor Creation
Activations
Normalization
Regularization
Linear / Dense
Vision Convolution
Vision Pooling
Sequence / Attention
Losses
Metrics
Control Flow
```

这些分类只回答“用户从哪里找到节点”，不表达模型父子关系，也不应成为 IR 的 module hierarchy。父子关系只能来自 `parentId`、组合模块定义或源码分析证据。

#### 18.1.1 DL-Playground 的真实调用链

从源码执行顺序看，DL-Playground 的节点能力不是由一个独立领域模型驱动，而是由 React Flow 状态串起来：

```text
nodes/registry.ts import 各节点 class
  -> NODE_GROUPS 组织侧栏分类
  -> 文件末尾 registerLayer() 填充可变 LAYER_REGISTRY
  -> nodeTypes.ts 读取每个 class.Component，生成 React Flow nodeTypes

useSidebarSystem.filteredGroups
  -> onDragStart() 写 application/reactflow = node type
  -> useGraphInteraction.createNodeFromEvent()
  -> getInitialNodeData() 从 paramSchema 复制默认值
  -> assignParent() 判断 React Flow parentId
  -> setNodes([...nodes, newNode])

React Flow onConnect
  -> addEdge() 直接加入 source/sourceHandle/target/targetHandle
  -> useTraceSystem.useMemo()
  -> verifyShapes(nodes, edges, LAYER_REGISTRY)
  -> 把结果回写到 node.data.__shape
  -> estimateGraphCost() / codeCompile.ts 再读取相同 nodes、edges
```

对应的源码细节如下：

- [`registry.ts:237-244`](../../../../DL-Playground/frontend/src/nodes/registry.ts) 遍历 `NODE_GROUPS`，调用 [`layerRegistry.ts:9`](../../../../DL-Playground/frontend/src/utils/layerRegistry.ts) 的 `registerLayer()` 修改全局 `LAYER_REGISTRY`；导入顺序会影响注册时机，没有重复 ID 和内容 digest 检查。
- [`nodeTypes.ts:7-10`](../../../../DL-Playground/frontend/src/types/nodeTypes.ts) 直接把 `Class.Component` 转为 React Flow component map，说明定义协议和 React UI 仍是耦合的。
- [`useSidebarSystem.ts:29-53`](../../../../DL-Playground/frontend/src/features/editor/hooks/useSidebarSystem.ts) 从 `NODE_GROUPS` 派生搜索结果；[`useSidebarSystem.ts:59-66`](../../../../DL-Playground/frontend/src/features/editor/hooks/useSidebarSystem.ts) 只把 node type 和可选 module metadata 写入拖放 payload。
- [`useGraphInteraction.ts:23-85`](../../../../DL-Playground/frontend/src/features/editor/hooks/useGraphInteraction.ts) 根据四种 `FieldType` 构造初始 data；[`useGraphInteraction.ts:188-233`](../../../../DL-Playground/frontend/src/features/editor/hooks/useGraphInteraction.ts) 生成 React Flow node 后直接 `setNodes`。
- [`useGraphInteraction.ts:160-180`](../../../../DL-Playground/frontend/src/features/editor/hooks/useGraphInteraction.ts) 的连线处理只调用 `addEdge()`，没有检查端口是否必需、连接数是否超限、张量是否兼容，也没有受保护的 command boundary。
- [`useGraphState.ts:18-52`](../../../../DL-Playground/frontend/src/features/editor/hooks/useGraphState.ts) 优先从 `localStorage.graphIR` 恢复，失败后回退到 `nodes/edges`；[`useGraphState.ts:147-171`](../../../../DL-Playground/frontend/src/features/editor/hooks/useGraphState.ts) 每次变化同时保存三份状态，并把 UI 快照加入最多 50 条的 history。
- [`useTraceSystem.ts:30-45`](../../../../DL-Playground/frontend/src/features/editor/hooks/useTraceSystem.ts) 对每次 nodes/edges 变化同步运行 Shape；[`useTraceSystem.ts:106-147`](../../../../DL-Playground/frontend/src/features/editor/hooks/useTraceSystem.ts) 又把派生 Shape 回写到 `data.__shape`。因此持久化输入与分析缓存会相互污染。

#### 18.1.2 Handle 看似命名，实际还不是端口契约

[`BaseClass.tsx:41-45`](../../../../DL-Playground/frontend/src/node_gen/BaseClass.tsx) 的 `HandleSpec` 只有 `targets: string[]` 与 `sources: string[]`。[`CreateNodeComponent.tsx:89-98`](../../../../DL-Playground/frontend/src/node_gen/CreateNodeComponent.tsx) 在节点没有显式声明时生成一个 `in-0` 和一个 `out-0`；[`BaseClass.tsx:190-219`](../../../../DL-Playground/frontend/src/node_gen/BaseClass.tsx) 只是把 target 均匀画在左侧、source 均匀画在右侧。

这套实现能表达“画几个连接点”，但不能表达：

- `query` 必需而 `mask` 可选；
- `Add.operands` 至少两条连接；
- 一个输出可以 fan-out 给多个下游；
- `Concat.inputs` 是有序 variadic，而 Add 的 operands 可视为无序；
- `LSTM.sequence/hn/cn` 是三个不同输出；
- 端口接受的 rank、dtype、layout 和 relation。

更关键的是，[`MultiheadAttentionNode.tsx:16`](../../../../DL-Playground/frontend/src/nodes/sequence/MultiheadAttentionNode.tsx) 虽然声明 `query/key/value/mask`，但 [`shape_verifier.ts:25-37`](../../../../DL-Playground/frontend/src/utils/shape_verifier.ts) 只把每个 target node 的上游 node ID 依边遍历顺序压入数组，[`shape_verifier.ts:87-102`](../../../../DL-Playground/frontend/src/utils/shape_verifier.ts) 再把该数组交给 MHA。它没有按 `targetHandle` 建立 `{query, key, value, mask}` 绑定。于是用户先连接 mask、后连接 query 时，UI Handle 名称正确，`inputShapes[0]` 却未必是 query。

同样，[`graphIR.ts:55-75`](../../../../DL-Playground/frontend/src/utils/graphIR.ts) 从“已经存在的边”反推节点 Handle：一个尚未连线但由定义声明的可选端口不会进入 GraphIR。ArchCanvas 的 `PortContract` 必须先于边存在；边只能引用已物化的端口实例，不能反过来创造端口事实。

另外，[`graphIR.ts:76-106`](../../../../DL-Playground/frontend/src/utils/graphIR.ts) 会原样保存整个 `node.data`，其中可能包含 `__shape` 等派生字段，并在每次 build 时写入新的 `createdAt`。因此它虽然有 `version=2`，却不能直接作为内容寻址的 semantic digest 输入。ArchCanvas 计算 digest 前必须使用明确 schema 的 canonical serializer，排除时间戳、坐标、选择态、分析缓存和 UI 私有字段。

#### 18.1.3 Shape、成本和代码生成的具体能力边界

DL-Playground 当前实现可作为算法原型，但不能直接成为严格审核规则：

| 能力 | 源码行为 | 在 ArchCanvas 中必须补强 |
|---|---|---|
| Shape 调度 | [`shape_verifier.ts:41-115`](../../../../DL-Playground/frontend/src/utils/shape_verifier.ts) 用 `pending` 集合反复寻找上游已完成节点 | 显式拓扑序、循环分类、按命名端口绑定输入、稳定诊断顺序 |
| 多输出 Shape | `shapeCompute()` 返回 object 时，第一项被选为 `defaultShape`，其余放在 `byHandle` | 每条 edge 必须读取自己的 `sourcePortId`，禁止回退到“第一个输出” |
| 未解决节点 | pending 最终统一报告 disconnected edge 或 invalid source | 分开报告缺必需端口、环路、上游 blocking、未知定义和 Shape 不可解 |
| 成本 | [`computeEstimator.ts:21-47`](../../../../DL-Playground/frontend/src/utils/computeEstimator.ts) 再次按 edge 顺序收集默认 Shape 并简单求和 | 按端口取 Shape，记录估算假设；共享参数只计一次，重复调用 FLOPs 分别计数 |
| 拓扑排序 | [`codeCompile.ts:134-165`](../../../../DL-Playground/frontend/src/utils/codeCompile.ts) 使用 Kahn 排序；有环时把剩余节点追加到末尾 | 非显式控制流环必须 blocking；合法循环必须由结构化 Loop IR 表达 |
| 输入/输出变量 | [`codeCompile.ts:181-253`](../../../../DL-Playground/frontend/src/utils/codeCompile.ts) 用 edge label 生成变量名，以 source Handle 猜输出 | 变量来自稳定 value/port ID，显示标签不能参与语义命名 |
| 参数替换 | [`codeCompile.ts:216-226`](../../../../DL-Playground/frontend/src/utils/codeCompile.ts) 用正则替换生成字符串中的关键字参数 | 在 Code IR AST 节点上替换引用，不操作已打印文本 |
| Python literal | [`BaseClass.tsx:224-250`](../../../../DL-Playground/frontend/src/node_gen/BaseClass.tsx) 的 `buildInitString()` 对 text/select 直接插入字符串 | printer 统一处理字符串引号、tuple/list、dtype、None、引用和非法标识符 |
| 动态验证 | [`useTraceSystem.ts:149-172`](../../../../DL-Playground/frontend/src/features/editor/hooks/useTraceSystem.ts) 将 GraphIR、生成代码和输入 Shape 发给 TorchLens | 仅作为显式启用的隔离验证；不得替代默认静态分析或 Source Evidence |

`MultiheadAttentionNode` 目前只输出 context，并在 forward 中用 `${out}, _ = ...` 丢弃 attention weights；`LSTMNode` 只输出 sequence，并丢弃 `hn/cn`。这正说明“PyTorch 调用能返回多个值”和“画布当前只暴露一个 Handle”是两个不同问题。ArchCanvas 注册定义必须完整声明可观察输出，再由参数、availability 或视图 preset 决定哪些端口当前显示。

`RepeatLayerNode` 则展示了另一类边界：它把 `internalNodes/internalEdges` 放入节点 data，验证时构造 `__LOOP_ENTRY__` mock node，再递归调用 `verifyShapes()`；代码生成时重新编译内部 React Flow 图并拼接 `for` 字符串。这种方法适合交互实验，但正式实现应让 Repeat 引用一个版本化 composite graph，并通过显式 carried input/output port 保证循环首尾契约一致。

#### 18.1.4 14 类注册内容与一个实际 ID 冲突

按 [`registry.ts:81-235`](../../../../DL-Playground/frontend/src/nodes/registry.ts) 当前源码，目录内容为：

| 分组 key | 显示名 | 当前注册项 |
|---|---|---|
| `inputs` | Inputs | Input |
| `torch_ops` | Torch Ops | Add、Concat、Sub、Mul、Div、Exp、Log、Sqrt、Pow、Clip、MatMul、Sum、Mean、Prod、Max、Min、ArgMax、ArgMin、tensor Repeat |
| `tensor_shape` | Tensor Shape | Reshape、Transpose、Flatten、Identity/Pass |
| `tensor_create` | Tensor Creation | Zeros、Ones、Rand |
| `activations` | Activations | ReLU、LeakyReLU、GELU、ELU、SELU、Tanh、Sigmoid、Softplus、Softsign、HardSwish、HardSigmoid、Softmax、LogSoftmax |
| `normalization` | Normalization | BatchNorm2d、InstanceNorm2d、GroupNorm、LayerNorm、RMSNorm |
| `regularization` | Regularization | Dropout、SpatialDropout2d、AlphaDropout、StochasticDepth |
| `dense` | Linear / Dense | Linear |
| `vision_conv` | Vision - Convolution | Conv1d/2d/3d、DepthwiseConv2d、PointwiseConv2d、ConvTranspose2d、Upsample、ResidualBlock |
| `vision_pool` | Vision - Pooling | MaxPool1d/2d/3d、AvgPool1d/2d/3d、AdaptiveAvgPool2d、AdaptiveMaxPool2d、GlobalAvgPool2d、GlobalMaxPool2d |
| `sequence` | Sequence / Attention | Embedding、RNN、LSTM、GRU、MultiheadAttention、PositionalEncoding |
| `losses` | Losses | MSELoss、CrossEntropyLoss、BCELoss |
| `metrics` | Metrics | Accuracy |
| `control` | Control Flow | Repeat Layer、ModuleList |

`ModuleRefNode` 在分组循环之后单独注册，因此可被运行时解析，但不属于上述 14 类普通节点。

源码中还有一个需要在迁移前显式消除的冲突：`torch_ops` 的 tensor Repeat 和 `control` 的 Repeat Layer 都使用 registry key `repeat_layer`。文件末尾按分组顺序调用 `registerLayer()`，后注册的 control definition 会覆盖前者；侧栏虽然能显示两个 Repeat 条目，拖放 payload 却是同一个 type key，最终解析到哪个 class 取决于全局 registry 的最后值。

ArchCanvas 的全局 ID 应拆为：

```text
pytorch.tensor.repeat        # torch.Tensor.repeat / torch.repeat_interleave 需再区分语义
archcanvas.control.repeat    # 重复执行一个 composite subgraph
```

`createAtomicNodeRegistry()` 遇到重复 `(id, version)` 必须直接失败，不能采用 last-write-wins。分类 key 也不进入 definition identity：未来把 GELU 从一个目录移动到另一个目录，不应破坏已保存节点。

### 18.2 目标链路与事实来源

原型内建议先建立以下单向链路：

```text
Atomic Node Registry
  -> createPrototypeNode(definitionId, version, params)
  -> PrototypeGraphDocument（节点、命名端口、边、父子关系）
  -> validateGraph + analyzeGraph（Shape、diagnostic、参数量、FLOPs）
  -> projectToLabScene（shape、glyphId、detailTemplateId、坐标）
  -> 现有布局、原子层级路由、SVG 渲染与导出
  -> 可选 PyTorch Code IR -> printer -> Draft Code
```

各层职责必须保持如下边界：

| 层 | 是什么 | 可以持有 | 不能持有或决定 |
|---|---|---|---|
| `AtomicNodeRegistry` | 受版本控制的类型目录 | 参数 schema、端口契约、规则 ID、图例 ID | 实例坐标、当前选中状态 |
| `PrototypeGraphDocument` | 原型语义图 | 节点实例、命名端口、端口级边、父子关系 | SVG path、颜色、纸张坐标 |
| `AnalysisSnapshot` | 对某一图 digest 的派生结果 | Shape、诊断、成本、规则版本 | 实例参数的事实值 |
| `LabScene` | 原型视觉 DTO | bounds、视觉 shape、label、展开模板、路由输入 | 参数 schema、端口合法性、代码生成语义 |
| `KernelDocument` | 正式程序的只读渲染输入 | canonical IDs、evidence、正式 ports/edges/modules | 未审核草稿的直接写入 |

因此，当前 [`addNode()`](./src/App.tsx) 创建通用 `operation` 的行为应被替换为“打开节点目录 -> 选择 `definitionId` -> 由 registry 创建 `PrototypeGraphNode` -> 投影成 `LabNode`”。不能只是给 `addNode()` 增加不同的 `shape` 分支，因为 [`LabNode`](./src/types.ts) 本身没有足够的语义字段。

#### 18.2.1 当前最小原型的实际状态流

最小原型目前只有 `LabScene` 这一份可编辑状态。源码调用顺序是：

```text
scenarios.ts 的 node()/paperNode()/edge()
  -> 生成手写 LabScene
  -> App.tsx editorReducer 保存 scene/past/future
  -> applyVisualPatch() 修改 LabScene
  -> expandScene() 按 detail_kind 放大父节点并移动邻居
  -> buildInlineDetailLayout() 生成递归详情树
  -> buildAtomicHierarchyRoutingPlan() 找最深可见原子端点
  -> routeScene() 计算外层边
  -> NodeGraphic 或 renderSceneSvg() 输出 SVG
```

每一步的源码含义是：

1. [`scenarios.ts:14-50`](./src/scenarios.ts) 的 `node()` 与 `edge()` 只填写显示 ID、bounds、`NodeShape`、label、`detail_kind` 和可选 `target_port_role`；没有 definition、params、port 或 Shape。
2. [`scenarios.ts:73-105`](./src/scenarios.ts) 的 `paperNode()` 只是额外写入 `layout_lane/layout_rank/paper_tone`，`paperScene()` 再设置 `layout_profile="paper"`。它没有把普通 Transformer 节点转换成论文视图，而是创建另一份节点数组。
3. [`App.tsx:417-439`](./src/App.tsx) 的 `editorReducer` 对每个 `LabPatch` 保存 `LabScene` 快照，最多 50 条；语义编辑和视觉移动没有分开的 history。
4. [`model.ts:16-55`](./src/model.ts) 的 `applyVisualPatch()` 对加边只检查起点/终点存在且不是自环；没有 direction、port、cardinality、relation 或 tensor contract 校验。
5. [`App.tsx:1207-1220`](./src/App.tsx) 先将拖动 preview 合入 scene，再调用 `expandScene()`；[`App.tsx:1231-1279`](./src/App.tsx) 按展开状态构造并缓存 detail tree。
6. [`App.tsx:1280-1294`](./src/App.tsx) 在 `atomic-bottom-up` 模式构建原子层级投影，再把 `boundaryPorts` 交给 `routeScene()`。这部分是可以继续复用的纯视觉链路。
7. [`NodeGraphic`](./src/App.tsx) 与 [`renderNode()`](./src/svg-export.ts) 各维护一份图例分支；屏幕与导出若只改一处会发生漂移。

当前创建和连线也完全工作在视觉层：

- [`App.tsx:1701-1722`](./src/App.tsx) 的 `addNode()` 生成时间戳 ID、固定 `152×72` bounds 和通用 `operation`，然后直接提交 `LabPatch.add-node`。
- [`App.tsx:1511-1529`](./src/App.tsx) 的连线模式先记 source node ID，再点击 target node；生成的 `LabEdge` 没有 source/target port。
- [`App.tsx:2065-2078`](./src/App.tsx) 的节点检查器只能编辑 label、secondary label、`NodeShape` 和几何；修改 `shape` 实际上是在手工改变图例，而不是改变模块语义。
- [`App.tsx:2080-2091`](./src/App.tsx) 的边检查器可以任意切换 relation、source 和 target；它不会重新验证端口。

这些行为应保留为 visual fixture editor 的能力，但不能承载新建 PyTorch 模块实例。特别是“用户把 shape 下拉框从 `operation` 改成 `attention`”只是一种视觉修改，不能把该节点的 canonical kind、输入端口或 Shape 规则改成 Attention。

#### 18.2.2 现有文件到新层的逐项迁移

| 当前文件/函数 | 当前职责 | 第一阶段改造 | 迁入正式 Studio 后 |
|---|---|---|---|
| `scenarios.ts` | 手写视觉 fixture | 保留；另建 prototype graph fixtures，经 `projectToLabScene()` 生成对照场景 | 仅作为 visual-kernel 回归 fixture |
| `types.ts::LabNode/LabEdge` | 同时承担显示和少量结构信息 | 仅增加投影所需只读引用字段，不加入 params/规则实现 | 由 `KernelRenderScene` 取代 |
| `model.ts::applyVisualPatch()` | 直接增删节点/边 | 继续只处理视觉 patch；禁止接收语义 command | 对应 `CanvasDocument` visual patch |
| `App.tsx::editorReducer` | LabScene undo/redo | 保留视觉历史；新增独立 `PrototypeGraphDraft` history | 由 workspace/transaction state 管理 |
| `App.tsx::addNode()` | 创建通用视觉节点 | 改为打开 registry palette，选择后发 `CreateNode` | 创建 synthetic proposal |
| `App.tsx::beginNode()` edge mode | 节点到节点连线 | 改为选择 source/target `PortInstance`，发 `ConnectPorts` | connection proposal/structural transaction |
| `App.tsx` inspector | 编辑 label/shape/bounds | geometry 仍发 visual patch；参数发 `SetInstanceParameter` | 参数事务与 visual patch 分开 |
| `module-details.ts` | `detail_kind -> DetailPrimitive[]` | detail template registry 消费稳定 slot binding | `KernelTemplateBinding` 驱动 |
| `detail-layout.ts` | 递归布局，并从 label 推断 nested kind | 布局保留；nested kind 改为显式 slot/definition binding | canonical child module binding |
| `atomic-hierarchy.ts` | primitive index 生成 atom/edge ID | 改用稳定 slot ID；portal 读取命名 port binding | 正式 KernelNode/KernelPort 投影 |
| `routing.ts` | 根据 bounds/boundaryPorts 选路 | 基本复用；端点来自 port projection | visual-kernel router |
| `NodeGraphic` / `svg-export.ts` | 两套 SVG 图例实现 | 共同调用 glyph registry 的纯 renderer | ArchitectureCanvas 与 export 共用图元定义 |

#### 18.2.3 父子模块与原子投影的精确替换点

当前展开机制有三处依赖视觉推断：

1. [`module-details.ts:792-853`](./src/module-details.ts) 用 `NodeDetailKind` 选择一组手写 primitives，并以固定坐标声明少量 `semanticInputPorts`；
2. [`detail-layout.ts:164-228`](./src/detail-layout.ts) 读取 primitive label/note，通过正则推断 `nestedKind`，再以 `detail-node-${primitiveIndex}` 生成子节点 ID；
3. [`atomic-hierarchy.ts:89-175`](./src/atomic-hierarchy.ts) 以 `levelKey + primitiveIndex` 生成 atom/flow ID，并通过“点是否落在 bounds 上”推断 flow 端点。

迁移时不删除这些布局算法，而是替换它们的语义输入：

```text
当前：label/note + primitive index + 几何接触
  -> inferNestedDetailKind()
  -> detail-node-N
  -> endpointId(point)

目标：template slot ID + definition/canonical binding + named port binding
  -> nestedDefinitionId / childCanonicalNodeIds
  -> bindingId:slotId
  -> sourcePortId / targetPortId
  -> 几何仅计算端口在屏幕上的 point/side
```

例如 Transformer encoder 模板不再通过 label `Self-Attention` 推断下一层，而是显式声明：

```typescript
{
  slotId: "encoder.self_attention",
  accepts: ["pytorch.nn.multihead_attention", "semantic.attention"],
  nestedDetailTemplateId: "attention",
  inputPortBindings: {
    hidden: "query",
    mask: "mask",
  },
  outputPortBindings: {
    context: "context",
  },
}
```

`primitiveIndex` 仍可作为一次渲染中的数组位置，但不能再进入持久化 ID、review diff 或 evidence binding。这样在模板中插入一个标题或辅助 flow 时，已有展开状态、用户偏移和源码证据不会整体漂移。

### 18.3 建议的核心类型

#### 18.3.1 参数、符号维度和来源

参数 schema 需要覆盖 PyTorch 常见值，并明确参数变化影响哪些派生结果：

```typescript
type ParameterValueKind =
  | "integer"
  | "number"
  | "text"
  | "boolean"
  | "select"
  | "tuple"
  | "list"
  | "dtype"
  | "symbolic-dimension"
  | "node-reference"
  | "parameter-reference";

interface ParameterField<T> {
  id: string;
  kind: ParameterValueKind;
  label: LocalizedLabel;
  required: boolean;
  defaultValue?: T;
  constraints?: {
    min?: number;
    max?: number;
    step?: number;
    enum?: readonly T[];
    tupleLength?: number;
  };
  visibleWhen?: ParameterPredicate;
  defaultWhen?: ParameterDefaultRule<T>;
  conflictsWith?: string[];
  affects: Array<"shape" | "cost" | "code" | "ports" | "visual">;
  editability: "editable" | "source-readonly" | "derived-readonly";
  evidenceIds?: string[];
}

type DimensionValue =
  | { kind: "known"; value: number }
  | { kind: "symbol"; symbol: "B" | "T" | "C" | "H" | "W" | string }
  | { kind: "expression"; expression: DimensionExpression }
  | { kind: "unknown"; reason?: string };

interface ShapeValue {
  dimensions: DimensionValue[];
  dtype?: string;
  layout?: "NCHW" | "NHWC" | "sequence" | "scalar" | "any";
  constraints: ShapeConstraint[];
}
```

相较于 DL-Playground 的 `number[]`，符号维度允许系统保留 `B/T/H/W`，而不是在源码尚未给出具体 batch 或序列长度时伪造数值。`ParameterField` 还要带序列化版本和迁移逻辑；上面省略的 `ParameterSchema<P>` 应包含 `schemaVersion`、`fields` 和 `migrate(oldVersion, value)`。

#### 18.3.2 严格端口契约

“几个入点、几个出点”不能只表达成两个数字。必须同时规定端口身份、方向、端口本身是否存在、每个端口允许多少条边，以及所接受的张量和关系：

```typescript
interface PortContract {
  id: string;
  direction: "input" | "output";
  role: string;
  label: LocalizedLabel;
  required: boolean;
  availability?: ParameterPredicate;
  connections: {
    min: number;
    max: number | "many";
    ordering: "single" | "ordered" | "unordered";
  };
  tensor: {
    ranks?: number[];
    dtypeFamilies?: string[];
    layout?: "NCHW" | "NHWC" | "sequence" | "scalar" | "any";
  };
  acceptedRelations: KernelRelation[];
}
```

这里要严格区分四个概念：

1. `ports.length` 是模块声明了多少个命名连接位；
2. `required/availability` 决定某个端口在当前参数下是否必须或可用；
3. `connections.min/max` 决定一个端口能连接多少条边；
4. `connections.ordering` 决定同一 variadic port 上的多条边是否需要稳定次序。

例如 Add 可以只有一个名为 `operands` 的输入端口，该端口允许 `2..many` 条无序连接；它不是“动态生成很多个无名输入端口”。Concat 也可以只有一个 variadic `inputs`，但其连接必须带稳定 ordinal，因为拼接顺序会改变结果。MultiheadAttention 则应声明语义不同的 `query`、`key`、`value` 和 `mask`，不能用四条都叫 `in-0/in-1/...` 的位置输入代替。

#### 18.3.3 模块定义、节点实例和图文档

```typescript
interface AtomicModuleManifest<P> {
  id: string;
  version: string;
  kind: "atomic" | "composite";
  categoryId: NodeCategoryId;
  label: LocalizedLabel;
  aliases: string[];
  parameters: ParameterSchema<P>;
  ports: PortContract[] | PortContractFactory<P>;
  semantics: {
    canonicalKind: string;
    sourceMatchers: SourceMatcher[];
  };
  visual: {
    shape: NodeShape;
    glyphId: string;
    detailTemplateId?: NodeDetailKind;
  };
  rules: {
    shapeRuleId: string;
    costRuleId?: string;
    codegenRuleId?: string;
  };
  editPolicy: ModuleEditPolicy;
}

interface RegisteredModuleDefinition<P> {
  manifest: Readonly<AtomicModuleManifest<P>>;
  digest: string;
  resolvedRules: {
    shape: ShapeRule;
    cost?: CostRule;
    codegen?: CodegenRule;
  };
  materializePortSpecs(params: P): MaterializedPortSpec[];
}

interface MaterializedPortSpec {
  contractId: string;
  direction: "input" | "output";
  role: string;
  ordinal?: number;
  available: boolean;
}

interface PortInstance {
  portInstanceId: string;
  contractId: string;
  ownerNodeId: string;
  direction: "input" | "output";
  role: string;
  ordinal?: number;
  available: boolean;
}

interface PrototypeGraphNode {
  nodeId: string;
  definitionId: string;
  definitionVersion: string;
  params: Record<string, unknown>;
  origin: "source-derived" | "user-draft" | "template-generated";
  parentId?: string;
}

interface PrototypeGraphEdge {
  edgeId: string;
  sourceNodeId: string;
  sourcePortId: string;
  targetNodeId: string;
  targetPortId: string;
  targetOrdinal?: number;
  relation: KernelRelation;
}

interface PrototypeGraphDocument {
  documentId: string;
  schemaVersion: string;
  registryDigest: string;
  nodes: PrototypeGraphNode[];
  ports: PortInstance[];
  edges: PrototypeGraphEdge[];
}

interface PrototypeGraphVisualState {
  documentId: string;
  nodePositions: Record<string, Point>;
  nodeSizeOverrides: Record<string, Size>;
  expandedNodeIds: string[];
}

interface AnalysisSnapshot {
  documentDigest: string;
  registryDigest: string;
  nodeShapes: Record<string, Record<string, ShapeValue>>;
  diagnostics: GraphDiagnostic[];
  nodeCosts: Record<string, CostEstimate>;
  graphCost: CostEstimate;
}
```

manifest 作者不手写 `digest`。`createAtomicNodeRegistry()` 对规范化 manifest、所引用规则版本和 migration metadata 计算 digest，产出不可变的 `RegisteredModuleDefinition`。这避免作者把旧 digest 误复制到新内容上，也修正了“声明对象尚未注册却要求自己知道最终 digest”的循环依赖。

`definitionVersion` 不能省略。否则同一份已保存图在 registry 更新后会悄悄改变端口、Shape 或代码语义。加载文档时若找不到精确版本，应停止语义分析并给出 blocking diagnostic，而不是自动套用最新版。document 保存物化后的 ports 便于审计和 diff，同时加载时必须根据固定 definition version 重新物化并核对；edge 中保存的是端口实例 ID，分析时还要验证该实例仍能回溯到当前 definition 的 `contractId`。

### 18.4 Registry 的声明和装配方式

普通模块定义应是无 React、无 DOM、无网络和无注册副作用的纯数据：

```typescript
export default defineAtomicModule({
  id: "pytorch.nn.conv2d",
  version: "1.0.0",
  kind: "atomic",
  categoryId: "vision-convolution",
  label: { en: "Conv2d", zh: "二维卷积" },
  aliases: ["torch.nn.Conv2d", "nn.Conv2d"],
  parameters: conv2dParameterSchema,
  ports: [
    inputPort("input", { required: true, rank: 4, layout: "NCHW" }),
    outputPort("output", { rank: 4, layout: "NCHW" }),
  ],
  semantics: {
    canonicalKind: "torch.nn.Conv2d",
    sourceMatchers: [{ matcherId: "python.torch.nn.Conv2d.v1" }],
  },
  visual: {
    shape: "convolution",
    glyphId: "conv2d",
    detailTemplateId: "convolution",
  },
  rules: {
    shapeRuleId: "conv-nd.v1",
    costRuleId: "conv.v1",
    codegenRuleId: "torch.nn.Conv2d.v1",
  },
  editPolicy: { stability: "reviewed", allowInstanceParameterEdit: true },
} satisfies AtomicModuleManifest<Conv2dParameters>);
```

建议使用构建时显式聚合，而不是在每个文件中调用 `registerLayer()`：

```typescript
import conv2d from "./definitions/vision-convolution/conv2d";
import linear from "./definitions/linear-dense/linear";

export const atomicNodeRegistry = createAtomicNodeRegistry([
  conv2d,
  linear,
  // ...
]);
```

`defineAtomicModule()` 只做单文件类型收窄和局部 schema 校验；`createAtomicNodeRegistry()` 才解析跨文件引用、冻结 definition、计算 digest 并建立 `(id, version) -> RegisteredModuleDefinition` 索引。两步分开后，definition 文件仍然是易于 review 的声明式数据，registry 又能执行全局唯一性检查。

`createAtomicNodeRegistry()` 在开发和 CI 中至少执行以下完整性检查：

- `(id, version)`、端口 ID 和参数 ID 在各自作用域内唯一；
- `categoryId`、`shapeRuleId`、`costRuleId`、`codegenRuleId`、`glyphId` 和 `detailTemplateId` 均可解析；
- schema 默认值满足自身约束；
- 所有 predicate 引用的参数存在；
- 输入端口不能接受输出专用关系，端口最小基数不能大于最大基数；
- manifest 可确定性序列化，并由规范化内容计算 digest；
- 同一版本的内容 digest 变化时 CI 失败，强制发布新版本。

`Component` 不进入 `AtomicModuleManifest` 或 `RegisteredModuleDefinition`。节点目录、参数检查器、端口提示、删除命令和 Shape 预览都由统一 UI 读取 schema 生成。只有 `Repeat`、`ModuleRef` 或可视化子图等确实无法由 schema 表达的类型，才通过独立的 `customEditorId` 找 UI 插件；插件也只能发领域命令，不能直接修改图数组。

#### 18.4.1 从点击“节点”到画布出现 Conv2d

结合当前 `App.tsx`，第一条 vertical slice 应明确实现为：

```text
点击 App.tsx 顶栏“节点”
  -> NodePalette 读取 registry.listByCategory()
  -> 用户选择 pytorch.nn.conv2d@1.0.0
  -> parameter schema 产生经过 validate/normalize 的默认参数
  -> materializeNodePorts() 产生 input/output PortInstance
  -> dispatchTopologyCommand(CreateNode)
  -> command handler 检查 TopologyDraft capability 和 expectedDocumentDigest
  -> 返回新 PrototypeGraphDocument + audit event
  -> analyzeGraph() 产生 AnalysisSnapshot
  -> projectToLabScene() 产生 convolution + glyphId=conv2d 的 LabNode
  -> 现有 displayScene/detailTrees/routing/NodeGraphic 链路继续渲染
```

建议 API 不让 React 组件自行拼默认值：

```typescript
interface CreateNodeRequest {
  definition: { id: string; version: string };
  requestedParams?: Record<string, unknown>;
  parentId?: string;
  requestedPlacement?: Point;
}

interface CreateNodeResult {
  document: PrototypeGraphDocument;
  createdNodeId?: string;
  diagnostics: GraphDiagnostic[];
  auditEvent: DraftAuditEvent;
}

function createPrototypeNode(
  registry: AtomicNodeRegistry,
  document: PrototypeGraphDocument,
  request: CreateNodeRequest,
): CreateNodeResult;
```

`createPrototypeNode()` 的固定顺序为：精确解析版本、合并默认值、拒绝未知参数、normalize tuple/list/dtype、运行字段约束、物化端口、检查 parent 是否允许该 child kind、生成稳定实例 ID、追加节点。`requestedPlacement` 由 orchestration 层在创建成功后写入 `PrototypeGraphVisualState`，不参与 semantic document digest。即使参数有 blocking error，也应保存用户明确输入的 draft value 并返回诊断；不能悄悄替换成另一个合法默认值。

UI 与命令边界建议这样接入当前文件：

- `App.tsx::addNode()` 不再构造 `LabNode`，只设置 `nodePaletteOpen=true`；
- `NodePalette` 的选中回调发送 `CreateNode`；
- `PrototypeGraphProvider` 或 reducer 持有 semantic draft；
- `LabScene` 由 memoized selector 投影，不存回 semantic draft；
- 当前 `editorReducer` 只保留手写 fixture/视觉 patch 编辑，或改名为 `visualReducer`，避免与 topology reducer 混淆；
- 投影节点被选中后，检查器用 `prototype_node_id` 找回 semantic node，再按 parameter schema 生成字段。

#### 18.4.2 参数检查器不能照搬节点内表单

DL-Playground 的 [`CreateNodeComponent.tsx:50-64`](../../../../DL-Playground/frontend/src/node_gen/CreateNodeComponent.tsx) 在 `<input onChange>` 中直接 `setNodes()`；这会让每个键入字符都变成未验证的节点 data。Scene Visual Lab 已有右侧检查器，应保留该交互位置，但改成以下过程：

```text
schema field renderer
  -> parse UI text to ParameterDraftValue
  -> field-level diagnostic（允许尚未输入完整）
  -> SetInstanceParameter command
  -> normalize + graph-level invalidation
  -> rematerialize ports（仅 affects 包含 ports 时）
  -> analyzeGraph
  -> projectToLabScene
```

必须区分“输入框中的临时文本”和“已进入语义 draft 的参数值”。例如 tuple 用户输入到一半的 `3,` 不能马上被解析成 `[3]` 并触发错误代码生成；检查器可以持有本地 edit buffer，blur/Enter 或合法 parse 后再发命令。

参数影响域用于精确失效缓存：

| `affects` | 必须失效或重算 |
|---|---|
| `ports` | port instances、相关 edge validity、Shape、cost、code、projection |
| `shape` | 当前节点及下游 Shape/cost/projection overlay |
| `cost` | 当前节点和 graph cost |
| `code` | Code IR 与 printer source map |
| `visual` | `projectToLabScene()`，不必重跑无关 Shape rule |

`in_channels/out_channels/kernel_size` 等数值不能只靠 HTML `step=1`；schema validator 仍要检查 integer、正数和分组整除约束。UI 限制只是辅助，不能作为审核保证。

### 18.5 端口实例与兼容性示例

首批节点的端口契约建议如下：

| 模块 | 输入端口 | 输出端口 | 关键审核条件 |
|---|---|---|---|
| Input | 无 | `output`，`0..many` 下游 | Shape 必须由 schema 或源码证据给出 |
| Conv2d | `input`，恰好 1 条，rank=4、NCHW | `output` | 输入 channel 与 `in_channels` 一致 |
| Linear | `input`，恰好 1 条 | `output` | 最后一维与 `in_features` 一致 |
| Add | `operands`，`2..many` | `sum` | 所有输入 Shape 可广播或严格相同，由 rule variant 决定 |
| Reshape | `input`，恰好 1 条 | `output` | 元素总量约束可符号求解，最多一个推断维度 |
| MultiheadAttention | `query/key/value` 必需，`mask` 可选 | `context` 必需，`weights` 条件可用 | embed dim、head 数、batch layout 和 mask rank 均校验 |
| LSTM | `input` 必需，`h0/c0` 可选 | `sequence/hn/cn` | 层数、方向数和 hidden size 决定多个输出 Shape |
| Transformer Decoder | `hidden/memory` 必需，两个 mask 可选 | `decoded` | self-attention 与 cross-attention 的来源角色不能互换 |
| Loss | `prediction/target` 必需，可选 `weight` | `loss` | target dtype、Shape 和 reduction 决定标量或逐元素输出 |
| Repeat | `loop_input` 和显式 carried ports | `loop_output` | 循环携带值首尾契约一致，重复次数为合法整数 |

端口 ID 一经发布就是序列化协议的一部分。改显示文案不改 ID；删除后的 ID 永不复用；重命名必须通过显式 migration 将旧 edge 的 port ID 转换为新 ID。

对于参数控制的端口，优先定义稳定端口全集，再用 `availability` 控制可用性。例如 `MultiheadAttention.weights` 在 `need_weights=false` 时仍保留稳定定义，并物化为 `available=false` 的可审计端口实例，但 UI 不为它提供可连接 Handle。只有端口数量本身确实由结构参数决定时才使用 `PortContractFactory<P>`，且工厂必须是已审核的纯函数。

连接命令的校验顺序建议固定为：

```text
definition/version 可解析
  -> source/output 与 target/input 方向正确
  -> relation 被双方接受
  -> availability 满足
  -> 单端口 connection cardinality 未超限
  -> tensor rank/dtype/layout 初步兼容
  -> 加边到 draft
  -> 图级 Shape 传播产生最终 diagnostics
```

草稿阶段允许最后两步产生错误，以支持用户逐步构图；发布或提交阶段则不允许存在 blocking diagnostic。

#### 18.5.1 端口物化、连线顺序与孤立端口

端口契约属于 definition，端口实例属于 node instance，edge 只引用端口实例。三者不能合并成一个字符串：

```typescript
function materializeNodePorts<P>(
  definition: RegisteredModuleDefinition<P>,
  nodeId: string,
  params: P,
): PortInstance[] {
  return definition.materializePortSpecs(params).map((port) => ({
    ...port,
    ownerNodeId: nodeId,
    portInstanceId: `${nodeId}:port:${port.contractId}${port.ordinal === undefined ? "" : `:${port.ordinal}`}`,
  }));
}
```

对固定端口，`contractId` 与实例 ID 一一对应。对真正需要多个可见插槽的 variadic port，可以共享 `contractId="inputs"`，以 ordinal 区分 `inputs:0/1/2`。删除中间插槽时不要重排已有 ordinal；否则所有后续 edge ID、diff 和 review target 都会改变。

`ConnectPorts` 至少携带：

```typescript
interface ConnectPortsCommand {
  type: "ConnectPorts";
  source: { nodeId: string; portInstanceId: string };
  target: { nodeId: string; portInstanceId: string };
  targetOrdinal?: number;
  relation: KernelRelation;
  expectedDocumentDigest: string;
}
```

command handler 不能相信 UI 传入的 node ID 与 port ID 是匹配的，必须从当前 document/registry 重新解析 owner、direction 和 availability。这样即使用户在两个点击之间修改了参数、导致可选端口消失，第二次点击也只会返回 stale-port diagnostic，不会产生悬空边。

未连接端口也必须序列化或可由精确 definition version 确定性重建。不能采用 DL-Playground `buildGraphIR()` 的“从边反推 Handle”策略，否则以下状态无法区分：

- definition 原本没有 `mask` 端口；
- definition 有 `mask`，当前没有连接；
- 参数使 `mask` 暂时 unavailable；
- 旧版本曾有 `mask`，新版本迁移失败。

#### 18.5.2 MHA、LSTM 与 Transformer 的端口映射

DL-Playground 的 MHA 使用四个 target Handle，并允许 1–4 个输入；缺失 key/value 时在代码生成中退回 query。这实际上把底层 `nn.MultiheadAttention` 和“自注意力便捷包装”合在了一起。ArchCanvas 应拆成严格原子定义与可选组合定义；PyTorch 原子调用还要区分 batch layout、key padding mask、attention mask 和可选 weights 输出：

```text
pytorch.nn.multihead_attention@1.x
  inputs
    query              required  1..1  sequence
    key                required  1..1  sequence
    value              required  1..1  sequence
    attention_mask     optional  0..1  mask
    key_padding_mask   optional  0..1  mask
  outputs
    context            required  fan-out
    weights            availableWhen(need_weights=true)  fan-out
```

另行定义的 `semantic.self_attention` 可以只暴露一个 `hidden`，再通过组合端口绑定把它连接到内部 MHA 的 query/key/value。这样 fallback 是组合结构的显式证据，不是“数组第二项不存在就取第一项”的偶然行为，也不会让 cross-attention 错把 memory 缺失解释成 self-attention。

LSTM 至少应声明：

```text
inputs:  input(required), h0(optional), c0(optional)
outputs: sequence, hn, cn
```

Transformer Decoder 组合定义则把外部语义端口绑定到内部 slot：

```text
hidden      -> self_attention.query/key/value
self_mask   -> self_attention.attention_mask
memory      -> cross_attention.key/value
memory_mask -> cross_attention.key_padding_mask 或 attention_mask（由源码证据决定）
decoded     <- final_norm/output slot
```

当前最小原型只有 `LabEdge.target_port_role`，并且 [`module-details.ts:821-847`](./src/module-details.ts) 只为若干 attention/paper Transformer 模板手写 `mask`、`memory` 坐标。迁移时它只能作为视觉模板 slot 的过渡输入，不能当作完整端口契约；尤其缺少 source port、owner、required、cardinality 和 tensor constraint。

### 18.6 图例注册与工程/论文视图统一

`NodeShape`、`glyphId` 和 `detailTemplateId` 是三个不同粒度：

- `NodeShape` 决定粗粒度边界和默认端口吸附，如 `convolution`、`attention`、`tensor`；
- `glyphId` 决定原子组件的精确语义图例，如 `conv2d`、`layer-norm`、`matmul`；
- `detailTemplateId` 决定展开后出现的内部结构，如完整 attention 或 Transformer encoder。

DL-Playground 本身不能提供可直接迁移的精确图例注册。它的 [`LayerDefinition`](../../../../DL-Playground/frontend/src/node_gen/BaseClass.tsx) 只有可选 `diagramLabel/diagramFamily`，family 也仅有 `input/output/merge/activation/block/other` 六种；[`diagramProjector.ts:98-110`](../../../../DL-Playground/frontend/src/utils/diagramProjector.ts) 未声明时统一退回 `block`。当前节点定义中基本只有 Input 和 ModuleRef 设置了该 metadata。也就是说，DL-Playground 可以贡献“definition 驱动视觉投影”的思路，但 Conv2d、LayerNorm、MHA 等精确 glyph 仍应由 ArchCanvas 基于现有 Scene Lab 图例重新注册。

建议增加独立图例注册表：

```typescript
interface GlyphDefinition {
  glyphId: string;
  semanticKind: string;
  renderers: {
    engineering: GlyphRendererId;
    paper: GlyphRendererId;
    compact?: GlyphRendererId;
  };
  minSize: Size;
  supportedShapes: NodeShape[];
  accessibilityLabel: LocalizedLabel;
}
```

首批映射可采用：

| 原子组件 | `NodeShape` | `glyphId` | 图例语义 |
|---|---|---|---|
| Conv2d | `convolution` | `conv2d` | feature-map stack + kernel |
| LayerNorm | `normalization` | `layer-norm` | μ/σ 归一化条带 |
| Add | `add` | `add` | 圆形或汇聚点中的 `+` |
| MatMul | `multiply` | `matmul` | 矩阵 `×`，区别于逐元素乘法 |
| Reshape | `tensor` | `reshape` | 轴/维度重排 |
| Transpose | `tensor` | `transpose` | 两轴交换 |
| MultiheadAttention | `attention` | `multihead-attention` | Q/K/V 汇聚与多头输出 |
| Dropout | `operation` | `dropout` | training-only 稀疏点阵 |
| CrossEntropyLoss | `operation` | `cross-entropy-loss` | prediction/target 汇入 loss |
| Repeat | `container` 或扩展后的容器 shape | `repeat` | 循环边界、carried ports 和次数 |

当前 [`NodeShape`](./src/types.ts) 尚无 `container`。实现 Repeat registry 前应先增加该粗粒度 shape，并同时更新颜色、bounds、routing anchor、交互渲染和 SVG 导出；在此之前只能使用 `operation` 作为明确标注的降级显示，不能在类型上假装 `container` 已存在。

#### 为什么当前“论文级 Transformer”和“Transformer”的相同组件没有相同图例

这是当前最小原型的实现路径造成的，不代表两个场景中的组件语义不同。源码中可以精确定位到以下原因：

1. 四个 Transformer 场景在 [`scenarios.ts:512-662`](./src/scenarios.ts) 中是四份独立的 `LabScene`。经典工程场景用 `node()`，论文场景用 `paperNode()`；两者没有共享 node instance、definition ID 或 glyph ID。
2. [`NodeGraphic:937-943`](./src/App.tsx) 在 paper mode 下用 `paper_tone` 取色，并把 `detailed` 定义为 `!paperMode && [tensor, convolution, attention, normalization]...`。因此即使论文节点的 `shape` 仍是 `attention`，Q/K/V glyph 也被明确关闭。
3. [`NodeGraphic:1028-1030`](./src/App.tsx) 对通用 `operation` glyph 同样要求 `!paperMode`。这使论文场景中的 Linear、Softmax 等普通矩形不显示工程图例。
4. `add/multiply/concat` 的 `symbol` 在 [`NodeGraphic:942`](./src/App.tsx) 独立计算，没有 `!paperMode` 条件，所以论文级场景中的 `+` 仍会显示。这说明当前差异不是统一设计规则，而是不同分支的条件不一致。
5. [`svg-export.ts:184-215`](./src/svg-export.ts) 完整复制了相同判断，因此导出结果也会关闭论文 glyph；这不是 React 渲染偶发问题。
6. [`module-details.ts:796-820`](./src/module-details.ts) 为 `attention` 与 `paper-attention`、普通/paper Transformer 分别注册 builder。论文 detail 使用独立 primitives，而不是给同一语义模板应用 paper renderer。
7. [`detail-layout.ts:173-188`](./src/detail-layout.ts) 甚至会把相同文字在普通父模板中推断为 `attention/add-norm/feedforward`，在 paper 父模板中推断为 `paper-attention/paper-add-norm/paper-feedforward`。视觉模式已经进入结构 identity，导致后续无法自然共享图例。

迁移后，相同组件必须先解析为同一个 `(definitionId, version)`，再取得相同 `glyphId`。engineering 与 paper renderer 可以改变尺寸、方向、线宽、配色和信息密度，但不能关闭或改写语义图例。论文视图若要保持经典论文的简洁度，可以使用该 glyph 的 `paper` 变体，而不是退回只靠 label 的普通矩形。

这也意味着“相同 label”不是统一图例的判据；只有相同 canonical semantic kind 或相同受审核 definition 才能共享 glyph。无法证明语义一致的节点应显示通用图例并附 diagnostic，不能为了视觉一致强行合并。

#### 18.6.1 图例渲染器的源码收敛方式

当前交互画布使用 JSX，静态导出使用字符串，两边分别手写矩阵、卷积堆叠、Q/K/V 和 μ/σ。迁移时不要让 `GlyphDefinition` 同时保存两份任意渲染函数；应先生成与运行环境无关的 glyph primitives：

```typescript
type GlyphPrimitive =
  | { kind: "rect"; bounds: Bounds; radius?: number; role: string }
  | { kind: "circle"; center: Point; radius: number; role: string }
  | { kind: "line"; from: Point; to: Point; role: string }
  | { kind: "text"; point: Point; text: string; role: string }
  | { kind: "matrix-grid"; bounds: Bounds; rows: number; columns: number; role: string };

interface GlyphRenderRequest {
  glyphId: string;
  variant: "engineering" | "paper" | "compact";
  bounds: Bounds;
  palette: GlyphPalette;
}

function buildGlyphPrimitives(request: GlyphRenderRequest): GlyphPrimitive[];
```

`NodeGraphic` 把 primitives 映射成 React SVG element，`svg-export.ts` 把同一 primitives 转成 escaped XML。图例几何、显示阈值、paper variant 和 accessibility label 只有一个事实来源。测试同时比较 primitive snapshot 与最终 SVG，避免两个 renderer 再次分叉。

`paper_tone` 继续只决定 palette，不能决定 semantic glyph；`layout_profile` 只选择 glyph variant、布局方向和信息密度。目标判断应从当前的：

```typescript
const detailed = !paperMode && semanticShapes.includes(node.shape);
```

变为：

```typescript
const variant = paperMode ? "paper" : visualStyle === "compact" ? "compact" : "engineering";
const glyph = glyphRegistry.resolve(node.glyph_id, variant);
```

如果 paper variant 尚未实现，registry 完整性检查应要求显式 fallback 到 engineering/compact renderer并产生开发期 warning，而不是静默不画。

### 18.7 Shape、诊断和成本分析

`analyzeGraph()` 应在 UI 之外按下列阶段执行：

```text
resolve exact definition versions
  -> materialize parameter-dependent port instances
  -> validate edge endpoints/cardinality/direction/relation
  -> build dependency graph by node + named target port
  -> topological schedule / cycle classification
  -> invoke audited shape rules
  -> solve symbolic constraints
  -> invoke cost rules
  -> return immutable AnalysisSnapshot
```

与 DL-Playground 不同，不能把 Shape 写入 `node.data.__shape`。这样做会把事实数据和派生缓存混在一起，也无法说明结果由哪个 registry/rule 版本产生。`AnalysisSnapshot` 必须同时记录 `documentDigest`、`registryDigest` 和规则版本；任一输入变化即废弃旧快照。

规则实现与 module manifest 分离：

```typescript
interface ShapeRule {
  id: string;
  version: string;
  verify(context: ShapeRuleContext): GraphDiagnostic[];
  infer(context: ShapeRuleContext): Record<string, ShapeValue>;
}

interface CostRule {
  id: string;
  version: string;
  estimate(context: CostRuleContext): CostEstimate;
}
```

manifest 只引用 rule ID，不能内嵌任意闭包。这样审核者可以单独证明 `conv-nd.v1` 是纯函数、无 I/O、无随机性，并让 Conv1d/2d/3d 在有意的参数化范围内复用它。

诊断至少包含 `code`、`severity`、`messageKey`、`targetIds`、`relatedPortIds`、`evidenceIds` 和可选修复建议。严重度继续使用正式 kernel 已有的 `info/warning/blocking`；只有 blocking 为零时才允许发布拓扑草稿。

#### 18.7.1 分析器必须按端口构造输入，而不是按边顺序构造数组

建议在拓扑调度前构造显式 binding table：

```typescript
interface NodeInputBindings {
  nodeId: string;
  byPort: Record<string, Array<{
    edgeId: string;
    sourceNodeId: string;
    sourcePortId: string;
    targetOrdinal?: number;
  }>>;
}

interface ShapeRuleContext<P = Record<string, unknown>> {
  nodeId: string;
  params: P;
  inputs: Record<string, ShapeValue[]>;
  outputContracts: PortContract[];
  constraints: SymbolicConstraintStore;
}
```

构造过程必须先按 `targetPortId` 分组；对 `ordering="ordered"` 的端口按 `targetOrdinal` 排序并检查 ordinal 重复/缺口，对 `unordered` 端口则用 edge ID 排序以保证 diagnostics 与 digest 确定。Shape rule 只能读取 `context.inputs.query`、`context.inputs.mask` 等命名值，不能读取“第 0 个输入碰巧是 query”。

输出同样按 port ID 返回：

```typescript
interface ShapeRuleResult {
  outputs: Record<string, ShapeValue>;
  constraints: ShapeConstraint[];
  diagnostics: GraphDiagnostic[];
}
```

下游 edge 从 `outputs[edge.sourcePortId]` 获取 Shape。缺少该 key 是规则实现错误或 definition/rule 不匹配，必须 blocking；禁止像 DL-Playground 那样回退到 object 第一项的 `defaultShape`。

#### 18.7.2 blocking 传播与部分分析

草稿图经常不完整，分析器不能因为一个节点失败就丢弃全图结果。建议对每个输出保存状态：

```typescript
type AnalyzedValue =
  | { status: "known"; shape: ShapeValue }
  | { status: "unknown"; constraints: ShapeConstraint[]; reason: string }
  | { status: "blocked"; causedByDiagnosticIds: string[] };
```

处理规则为：

- 缺少 required port：当前节点相应输出为 blocked；
- 输入 Shape unknown 但 rank/dtype 约束仍可推导：继续运行支持 partial inference 的 rule；
- 上游 blocking：生成一条简短的 dependent diagnostic，引用原始 diagnostic ID，不复制长错误；
- 图中独立分支继续分析并给出 Shape/cost；
- cost 中涉及 unknown dimension 时返回 symbolic expression 或 confidence/assumptions，不伪造 0；
- 共享 parameter group 由 canonical parameter ID 去重，module call FLOPs 按每次调用累计。

这样右侧检查器既能显示局部成果，也能明确说明为什么某个端口暂时没有 Shape。

### 18.8 使用结构化 PyTorch Code IR

DL-Playground 的 `getInitCode()` 和 `getForwardCode()` 足够支持演示型顺序网络，但 ArchCanvas 需要覆盖：

- `torch.add`、`reshape` 等 functional op；
- tuple/dict 多输出和解包；
- 同一 module/parameter 的多次调用与权重共享；
- 可选参数、关键字参数和 dtype/device；
- Repeat、ModuleList、条件和显式循环；
- 生成代码片段与 Source Evidence/CodeSpan 的对应。

因此 `codegenRuleId` 应产生结构化 IR，而不是直接返回 Python 字符串：

```typescript
type PyTorchStatement =
  | ModuleInitStatement
  | ModuleCallStatement
  | FunctionCallStatement
  | TensorMethodStatement
  | TupleUnpackStatement
  | AssignmentStatement
  | ForStatement;

interface PyTorchDraft {
  imports: ImportSpec[];
  fields: ModuleInitStatement[];
  forward: PyTorchStatement[];
  sourceMap: Record<string, { nodeId: string; portIds: string[] }>;
}
```

printer 负责安全编码 Python literal、标识符去重、格式化和 CodeSpan；rule 只能构造受限 AST。首期代码生成应标为“Draft/Proposal”，不自动覆盖用户 `.py` 文件。迁入正式 Studio 后，任何源码变化仍必须走 prepare/verify/review/commit。

#### 18.8.1 从 Graph 到 Code IR 的具体步骤

代码生成前不再复用“Shape 的拓扑数组”，而是建立 value graph：

```text
PrototypeGraphEdge(sourcePortId, targetPortId)
  -> ValueId = `${sourceNodeId}:${sourcePortId}`
  -> 按 target port 绑定 call arguments
  -> 为 parameter-sharing group 分配一个 ModuleFieldId
  -> 对 node 调用 codegen rule，产生 statements + output ValueIds
  -> printer 分配合法且不冲突的 Python identifiers
  -> sourceMap 记录 statement/span -> node/port/evidence
```

至少区分三种节点：

| 节点种类 | `__init__` | `forward` | 示例 |
|---|---|---|---|
| module definition | 产生 `ModuleInitStatement` | 产生 `ModuleCallStatement` | Conv2d、Linear、LayerNorm |
| functional op | 无 field | 产生 `FunctionCallStatement` 或 tensor method | Add、MatMul、Reshape |
| composite/control | 引用子图或受限控制结构 | 产生嵌套 block | Repeat、ModuleRef |

MHA 应产生 tuple value，再根据端口使用情况决定是否保留 weights：

```typescript
const call = moduleCall(fieldId, argsByPort);
return tupleBind(call, {
  context: valueId(nodeId, "context"),
  weights: params.need_weights ? valueId(nodeId, "weights") : discardValue(),
});
```

LSTM 则将 PyTorch 的 `(sequence, (hn, cn))` 表达为嵌套 tuple pattern。不能继续使用 `${outputVar}, _ = ...`，否则画布声明 `hn/cn` 后 printer 仍会丢失它们。

代码生成 gate 至少验证：graph 无非控制流环、每个必需 codegen port 已绑定、所有引用定义版本可解析、参数可编码、共享 field 的构造参数一致、所有被下游使用的 output port 都由 rule 产生。失败时返回结构化 diagnostics，不生成“尽量可运行”的残缺代码。

### 18.9 三层保护锁

保护锁必须区分实例拓扑和模块定义，不能只做一个全局“可编辑”按钮：

| 模式 | 默认状态 | 允许的操作 | 禁止的操作 |
|---|---|---|---|
| 视觉模式 | 开放 | 移动、缩放、展开/收起、切换图例和视图 preset | 修改节点、边、参数和契约 |
| 拓扑草稿模式 | 锁定 | 创建/删除实例、连接/断开端口、修改可编辑实例参数 | 改模块定义、直接提交正式 IR |
| 模块契约维护模式 | 强锁定 | 基于已批准版本创建 definition draft | 原地修改已批准版本、绕过评审发布 |

UI 上的锁只负责表达状态和避免误触，真正的权限检查要在三处重复执行：

1. command handler 拒绝当前模式无权执行的命令；
2. domain validator 检查目标定义的 `editPolicy`、版本和 digest；
3. 持久化/API 层再次检查 session capability、base digest 和 review receipt。

不能让调用者通过直接构造 `LabPatch` 绕开保护锁。`LabPatch` 只适合视觉实验；语义操作应使用显式命令：

```typescript
type PrototypeGraphCommand = {
  commandId: string;
  expectedDocumentDigest: string;
} & (
  | { type: "CreateNode"; definitionId: string; version: string; params: unknown }
  | { type: "DeleteNode"; nodeId: string }
  | { type: "ConnectPorts"; source: PortRef; target: PortRef; relation: KernelRelation }
  | { type: "DisconnectEdge"; edgeId: string }
  | { type: "SetInstanceParameter"; nodeId: string; parameterId: string; value: unknown }
);
```

所有 command 返回新的 draft、diagnostics 和 audit event。视觉投影收到新文档后再产生 `LabPatch` 或完整 `LabScene`；反向由 `LabScene` 猜测语义是禁止的。

#### 18.9.1 锁不能实现成 `const [locked, setLocked]`

当前 `App.tsx` 顶栏的新增、连线、删除按钮始终可用，`patch()` 又只是 `dispatch({type: "patch"})`。若只在按钮外包一层 `disabled={locked}`，键盘命令、测试代码、导入文档或未来 API 仍能直接发 patch。

建议把编辑会话建模为带 capability 的判别联合：

```typescript
type EditSession =
  | {
      mode: "visual";
      documentId: string;
    }
  | {
      mode: "topology-draft";
      draftId: string;
      baseDocumentDigest: string;
      capability: TopologyDraftCapability;
      expiresAt: string;
    }
  | {
      mode: "contract-maintenance";
      draftId: string;
      baseDefinition: { id: string; version: string; digest: string };
      capability: ContractMaintenanceCapability;
      expiresAt: string;
    };
```

解锁拓扑的含义是 `beginTopologyDraft(baseDocumentDigest)`，不是把 boolean 改为 false；关闭锁的含义是放弃 draft 或提交 review，不是直接把当前状态视为 approved。capability 至少绑定用户/session、允许的操作集合、base digest 和过期时间。

command handler 入口统一检查：

```typescript
function dispatchGraphCommand(
  session: EditSession,
  current: PrototypeGraphDocument,
  command: PrototypeGraphCommand,
): CommandReceipt {
  if (session.mode !== "topology-draft") {
    return rejected("EDIT_MODE_REQUIRED", command);
  }
  if (!allows(session.capability, command.type)) {
    return rejected("CAPABILITY_DENIED", command);
  }
  if (command.expectedDocumentDigest !== digest(current)) {
    return rejected("STALE_DRAFT", command);
  }
  return executeValidatedCommand(current, command);
}
```

所有拒绝都返回非零、结构化 receipt；不能只 toast 一句然后当作命令成功。UI 根据 receipt 更新提示，但领域层决定是否执行。

#### 18.9.2 历史记录也必须分层

当前 `editorReducer` 把移动、改 label、加边和删节点都放进同一 `past/future`。引入语义图后应拆成：

- `VisualHistory`：bounds、camera、展开、detail offset、route hint；undo 不触发定义版本变化；
- `TopologyDraftHistory`：Create/Delete/Connect/Disconnect/SetParameter command 及反向 command；每步重算 digest/diagnostics；
- `ContractDraftHistory`：manifest diff 与 migration edits；只能在 contract-maintenance session 内存在；
- 正式 commit history：不可由前端 undo 擦除，只能通过新的反向事务处理。

移动节点后不应让 `PrototypeGraphDocument` digest 变化，除非产品明确把布局纳入语义文档。推荐把 position 存在独立 prototype visual state，使 Shape/codegen cache 不因拖动失效。

### 18.10 契约草稿、评审和版本状态机

已批准定义不可原地修改。解锁“模块契约维护模式”实际执行的是：

```text
approved
  -> create DefinitionDraft(baseId, baseVersion, baseDigest)
  -> draft
  -> validating
  -> review-ready
  -> approved 或 rejected
```

建议的审核对象为：

```typescript
interface DefinitionDraft {
  draftId: string;
  base: { id: string; version: string; digest: string };
  candidate: AtomicModuleManifest<unknown>;
  author: string;
  createdAt: string;
}

interface ContractDiff {
  parameterChanges: SchemaChange[];
  portChanges: PortChange[];
  ruleChanges: RuleReferenceChange[];
  visualChanges: VisualContractChange[];
  compatibility: "breaking" | "backward-compatible" | "visual-only";
  requiredVersionBump: "major" | "minor" | "patch";
}

interface ReviewReceipt {
  draftId: string;
  candidateDigest: string;
  validationRunId: string;
  reviewer: string;
  decision: "approved" | "rejected";
  decidedAt: string;
}
```

版本判定至少遵守：

- 删除/重命名端口、新增必需端口、改变连接基数下限、改变 Shape 或代码语义：major；
- 新增向后兼容的可选端口或可选参数：minor；
- 文案、非语义视觉样式或不改变含义的 glyph renderer 修复：patch；
- `glyphId` 从一种语义换到另一种语义不能伪装成 patch；
- 端口或参数重命名必须提供可测试的 graph migration；
- 发布物包含规范化 manifest、规则版本、测试摘要和 digest；receipt 必须绑定 candidate digest，修改后旧 receipt 自动失效。

契约代码审核规则至少包括：

- 禁止 `any`、随机数、时间依赖、网络、DOM、文件 I/O 和执行用户源码；
- definition ID、port ID、parameter ID 稳定且可确定性序列化；
- Shape/cost/port factory 为纯函数，只能引用批准的 rule library；
- Python 代码只经结构化 IR 和受审核 printer 输出；
- source matcher 明确支持的全限定名、参数绑定和 evidence 策略；
- 每个端口都有合法、非法、缺失、超额连接测试；
- 每个 Shape 规则都有边界值、符号维度、未知维度和错误输入测试；
- engineering/paper 必须解析到相同 `glyphId`；
- breaking change 必须带已有实例迁移和无法迁移时的 blocking diagnostic。

#### 18.10.1 为什么不能直接采用 DL-Playground 的自定义模块版本

DL-Playground 已有 `SavedModule`，但它解决的是浏览器本地复用，不是受审核契约：

- [`moduleRegistry.ts:17-30`](../../../../DL-Playground/frontend/src/utils/moduleRegistry.ts) 保存 GraphIR、Handle 名称数组、内部 React Flow nodes/edges 和可选 variable map；没有 definition digest、review receipt 或兼容性级别。
- [`moduleRegistry.ts:32-37`](../../../../DL-Playground/frontend/src/utils/moduleRegistry.ts) 用第一个数字简单生成 `v2/v3`，不区分 major/minor/patch。
- [`moduleRegistry.ts:112-137`](../../../../DL-Playground/frontend/src/utils/moduleRegistry.ts) 按相同 ID 覆盖 `localStorage` 中的对象，没有不可变历史版本。
- [`moduleRegistry.ts:140-161`](../../../../DL-Playground/frontend/src/utils/moduleRegistry.ts) 保存已有模块时沿用相同 ID、提高显示 version，并批量改 module-ref data；旧实例无法继续固定在旧契约。
- [`useModuleSystem.ts:382-400`](../../../../DL-Playground/frontend/src/features/editor/hooks/useModuleSystem.ts) 导入模块时也可按 ID 覆盖本地记录。

ArchCanvas 必须把逻辑 identity 与版本 identity 分开：

```text
definitionId = pytorch.nn.conv2d       # 跨版本稳定的家族 ID
version      = 2.1.0                   # 语义版本
digest       = sha256(canonical bundle) # 精确内容身份
```

registry 可同时保存多个 version；graph instance 固定引用一个 version。升级实例是显式 `MigrateNodeDefinition` command，输入旧/新 definition、migration ID 和 expected graph digest，输出参数变换、port remap、edge remap 与 diagnostics。绝不在发布新 definition 时批量静默改写所有实例。

#### 18.10.2 ContractDiff 的判定顺序

diff 工具不能只做 JSON 文本比较，建议按语义层计算：

1. 规范化旧/新 manifest，忽略字段顺序和非语义格式；
2. 以稳定 parameter ID 比较类型、required/default/constraints/affects；
3. 以稳定 port contract ID 比较 direction、availability、cardinality、ordering、tensor 和 relations；
4. 比较 shape/cost/codegen rule 的 `(id, version, digest)`；
5. 比较 source matcher、canonical kind 和 evidence policy；
6. 最后比较 label、glyph/template 和非语义视觉 metadata；
7. 取所有变化要求的最高版本级别，并检查用户声明的 next version 是否足够；
8. 对 breaking change 执行 migration fixtures，生成可迁移/需人工处理/不可迁移统计。

如果只改 label，但 source matcher 或 shape rule digest 同时变化，整体仍按后者判定，不能被 visual-only 标签掩盖。

### 18.11 拓扑草稿的提交门槛

拓扑解锁后，用户可以暂时删除必需输入或只搭一半子图。这类中间状态保存在 `PrototypeGraphDocument` draft 中，不应在每次点击时都被强行阻止；但系统必须立即显示 blocking diagnostic。

正式提交前固定运行：

```text
schema/default validation
  -> port existence + direction
  -> per-port cardinality
  -> relation compatibility
  -> tensor rank/dtype/layout
  -> required input completeness
  -> cycle/control-flow validation
  -> symbolic Shape propagation
  -> cost analysis
  -> codegen feasibility（仅请求生成代码时）
  -> zero blocking diagnostics
  -> review/commit
```

这一区分使“编辑过程可不完整”和“发布结果必须严格有效”同时成立。保护锁负责进入草稿，validator 负责能否离开草稿；两者不能互相替代。

### 18.12 `projectToLabScene()` 的具体映射

投影函数建议只读取语义图、独立视觉状态和分析快照，并输出当前渲染器已经理解的 DTO：

```typescript
function projectToLabScene(input: {
  graph: PrototypeGraphDocument;
  visual: PrototypeGraphVisualState;
  analysis: AnalysisSnapshot;
  registry: AtomicNodeRegistry;
  glyphs: GlyphRegistry;
  viewPreset: "engineering" | "paper";
}): LabSceneProjection;
```

投影必须是确定性纯函数。它可以返回 `LabScene` 以及 `prototypeNodeBySceneNodeId`、`prototypeEdgeBySceneEdgeId` 等索引，但不能修改 graph、analysis 或 registry。

| `PrototypeGraph` 来源 | `LabScene` 目标 | 规则 |
|---|---|---|
| `node.nodeId` | `scene_node_id` | 直接使用稳定实例 ID，不用数组下标 |
| definition `visual.shape` | `shape` | 粗粒度轮廓 |
| definition `visual.glyphId` | 新增的 `glyph_id` | 精确图例，不从 label 推断 |
| definition `detailTemplateId` | `detail_kind` | 仅在 template predicate 满足时设置 |
| definition label + params | `label/secondary_label` | 经过统一 formatter，不能反向解析 |
| `node.parentId` | 层级投影输入 | 进入现有展开和 portal 构建，不塞入 label |
| edge 两端 port ID | `target_port_role` 及后续正式 port refs | 过渡期可映射 role，最终直接使用命名端口 |
| `AnalysisSnapshot` | Shape/cost/diagnostic overlay | 只读覆盖层，不回写语义节点 |
| `visual.nodePositions[nodeId]` | `bounds.x/y` | 不进入语义 digest；尺寸由 glyph/template 的约束计算 |

为了兼容当前原型，可以先给 `LabNode` 增加可选的 `glyph_id` 和 `prototype_node_id`，给 `LabEdge` 增加可选的 `source_port_id/target_port_id`；但这些字段仍是投影结果。正式语义对象必须存在于单独的 prototype graph 模块中。

建议投影结果显式携带来源索引，而不是让 UI 拼 ID：

```typescript
interface LabSceneProjection {
  scene: LabScene;
  sourceIndex: {
    nodeBySceneId: Record<string, { prototypeNodeId: string; definitionDigest: string }>;
    edgeBySceneId: Record<string, { prototypeEdgeId: string }>;
    detailSlotByPrimitiveId: Record<string, { bindingId: string; slotId: string }>;
  };
}
```

当 definition 没有 glyph 或 detail template 时，投影器输出明确 fallback 和 diagnostic。它不能从 label 正则猜测；label 正则只保留在旧 fixture compatibility adapter 中，并应有删除期限。

### 18.13 建议源码目录

首期可在 `scene-visual-lab/src` 下新增：

```text
prototype-graph/
  types.ts                     # PrototypeGraphDocument、node、edge、draft
  visual-state.ts              # position/size/expanded，不进入语义 digest
  commands.ts                  # 创建/删除/连线/参数修改命令
  command-handler.ts           # 模式、权限和 base digest 检查
  validate-graph.ts            # 端口、拓扑和提交门槛
  analyze-graph.ts             # 调度 Shape/cost rules
  project-to-lab-scene.ts      # 唯一的语义图 -> LabScene 适配器
  digest.ts                    # 确定性规范化与摘要

atomic-registry/
  types.ts                     # AtomicModuleManifest、PortContract、ParameterSchema
  define-module.ts             # defineAtomicModule 与静态约束
  registry.ts                  # 显式聚合和完整性验证
  categories.ts                # 14 个检索分类
  definitions/
    inputs/
    torch-ops/
    tensor-shape/
    tensor-creation/
    activations/
    normalization/
    regularization/
    linear-dense/
    vision-convolution/
    vision-pooling/
    sequence-attention/
    losses/
    metrics/
    control-flow/

analysis-rules/
  shape/
  cost/
  diagnostics.ts
  symbolic-dimensions.ts

glyph-registry/
  registry.ts
  definitions.ts
  renderers/

codegen/
  pytorch-ir.ts
  rule-registry.ts
  printer.ts
  source-map.ts

contract-review/
  types.ts
  diff.ts
  validate-definition.ts
  version-policy.ts
  migrations.ts

ui/
  NodePalette.tsx              # 搜索与 14 类目录，只发 CreateNode
  ParameterInspector.tsx       # schema 驱动的右侧参数编辑
  PortOverlay.tsx              # 命名端口命中区与连线预览
  EditModeControl.tsx          # visual/topology/contract 会话入口
```

这些模块不依赖 React。`App.tsx` 只负责调用 command handler、保存当前 draft/analysis、把投影结果交给现有 SVG 画布，并在检查器中渲染 schema。这样将来迁入正式 Studio 时，registry、规则和测试可以整体移动，不必携带原型的 UI 状态容器。

### 18.14 分阶段实施顺序

#### 阶段 A：语义底座

1. 建立纯 TypeScript 的 registry、parameter、port、symbolic Shape、diagnostic 类型；
2. 完成 registry 完整性、digest 和版本测试；
3. 建立 `PrototypeGraphDocument`，不改现有场景数据；
4. 实现 `projectToLabScene()`，用测试证明投影不反向污染语义图。

#### 阶段 B：首批原子节点和创建 UI

1. 先注册 Input、Linear、Conv2d、MaxPool2d、ReLU、GELU、Add、LayerNorm、Dropout、Reshape、Transpose、Embedding、MultiheadAttention；
2. 将“新建节点”改为带搜索和 14 类分组的命令菜单；
3. 参数在右侧检查器统一编辑，不在节点卡片中塞完整表单；
4. 加入命名端口和端口级连线，保留当前 SVG、布局和路由系统。

#### 阶段 C：静态分析和图例统一

1. 实现拓扑调度、端口基数校验、符号 Shape 传播和成本汇总；
2. 引入 `AnalysisSnapshot`，删除对 UI node 私有字段的依赖；
3. 注册稳定 glyph，并让 engineering/paper 使用同一 `glyphId`；
4. 用四个 Transformer 场景验证 MHA、Add、LayerNorm、FFN 等共享定义投影一致。

#### 阶段 D：草稿代码和复杂结构

1. 实现 PyTorch Code IR、printer 和 source map；
2. 输出“生成源码提案”，不自动写用户文件；
3. 增加 Repeat、ModuleRef、ModuleList、多输出和显式循环；
4. 将 contract diff、版本判断、review receipt 和 migration 接入 CI/本地审核界面。

#### 阶段 E：迁入正式 Studio

1. 将 registry 定义映射到 Exact Architecture IR 的 canonical semantic kind；
2. 扩展正式 `KernelPort` 的 optional、cardinality、tensor contract 等信息；
3. 把原型 draft 转换为 synthetic proposal；
4. 通过 [`prepareStructural()`](../../src/app/studio-actions.ts) 进入正式 prepare/verify/review/commit；
5. 源码重新静态分析后，用带 canonical/evidence IDs 的正式节点替换 synthetic 节点。

动态执行验证放在最后，并且必须显式启用、禁网、限制 CPU/内存/PID/运行时间。默认路径继续是静态分析，不得通过 import 用户工程来获得模型图。

#### 18.14.1 推荐的第一个端到端切片：Input -> Conv2d -> ReLU

第一轮不要先把 14 类全部搬进菜单。应先用三个节点证明语义链路完整：

1. `atomic-registry/definitions/inputs/tensor-input.ts`：声明无输入、一个 `output`、符号/具体 Shape 参数；
2. `atomic-registry/definitions/vision-convolution/conv2d.ts`：声明 `input/output`、Conv 参数与三个 rule ID；
3. `atomic-registry/definitions/activations/relu.ts`：声明一进一出和 Shape-preserving rule；
4. `analysis-rules/shape/input.ts`、`conv-nd.ts`、`identity.ts`：先支持 known/symbolic `B,C,H,W`；
5. `prototype-graph/commands.ts`：支持 CreateNode、ConnectPorts、SetInstanceParameter；
6. `project-to-lab-scene.ts`：映射为 `io -> convolution -> operation`，其中 Conv 使用 `glyph_id=conv2d`；
7. `NodePalette.tsx` 替换当前顶栏 `addNode()` 的直接 patch；
8. `ParameterInspector.tsx` 在当前检查器位置显示 Conv 字段、端口和 Shape diagnostics；
9. `PortOverlay.tsx` 让边从 source output 命中 target input，并把端口点投影给现有 router；
10. 使用现有 `NodeGraphic`、`routeScene()` 和导出链路显示结果。

该切片完成时必须能证明：

```text
Input.output [B,3,224,224]
  -> Conv2d.input
  -> Conv2d.output [B,16,222,222]
  -> ReLU.input
  -> ReLU.output [B,16,222,222]
```

把 Conv2d `in_channels` 改成 4 后，应出现绑定到 `Conv2d.input` 的 blocking diagnostic；改回 3 后诊断消失。锁定拓扑后 Connect/Delete/SetParameter command 被拒绝，但节点移动、缩放、展开和视图切换仍可用。interactive SVG 与导出 SVG 必须显示同一个 `conv2d` glyph。

只有该链路通过后再扩展 Add、MHA、LSTM 等多输入/多输出节点，否则会在简单 one-in/one-out 尚未稳定时同时调试 variadic、optional 和 tuple output。

### 18.15 与正式 Studio 的事务边界

当前正式 [`KernelPort`](../../src/visual-kernel/types.ts) 已包含 `portId/ownerNodeId/direction/role/evidenceIds`，后续可以增加或关联以下契约信息：

```typescript
interface KernelPortContractProjection {
  required: boolean;
  minConnections: number;
  maxConnections: number | "many";
  tensorContract?: TensorContract;
  acceptedRelations: KernelRelation[];
  definitionId: string;
  definitionVersion: string;
}
```

这些字段应来自批准的 module manifest 与源码证据的结合，而不是 renderer 临时生成。正式链路为：

```text
approved RegisteredModuleDefinition
  -> 用户创建 ModuleInstance draft
  -> port/Shape/cost/compatibility validation
  -> LabScene 或 KernelRenderScene 投影
  -> prepareStructural / verify / review / commit
  -> Python 源码重新静态分析
  -> canonical node + evidence 取代 draft node
```

不得直接修改 [`KernelDocument`](../../src/visual-kernel/types.ts)。拓扑草稿最终调用结构事务；参数变化调用参数事务；模块定义本身的变化走独立 registry transaction。定义审核不能伪装成 visual patch，visual patch 也不能改变 port contract。

正式提交还要防止过期草稿：prepare 时提交 base source digest、registry digest 和 definition versions；verify 或 commit 发现任一 digest 已变化时，要求 rebase 并重新分析。

#### 18.15.1 原型命令到现有 Studio action 的映射

正式前端已经有三条不同入口，迁移时不要全部塞进 `prepareStructural()`：

| 原型意图 | 现有正式入口 | 说明 |
|---|---|---|
| 修改普通实例参数 | [`prepareParameter()`](../../src/app/studio-actions.ts) | 请求 `/api/transaction/prepare`，必须绑定 canonical target node 和源码参数 |
| 创建/删除/替换模块实例等结构变化 | [`prepareStructural()`](../../src/app/studio-actions.ts) | 请求 `/api/transaction/prepare-structural`；prototype node 先作为 synthetic proposal |
| 连接两个正式端口 | [`proposeConnection()`](../../src/app/studio-actions.ts) | 当前请求 `/api/proposal/connection`，已经携带 source/target port ID；后续仍需 verify/review/commit 闭环 |
| 移动、缩放、展开、route hint | visual/navigation persistence | 不生成 Python 源码事务，不改变 `KernelDocument` 语义 |
| 修改模块契约/manifest | 当前无对应 action | 必须新增独立 registry transaction；不能借用参数或 visual patch |

`prepareStructural()` 当前 payload 包含 `patch_id/operation/target_node_id/parameters`，因此从原型迁移时需要一个显式 adapter：

```typescript
function toStructuralProposal(
  command: PrototypeGraphCommand,
  bindings: DraftCanonicalBindings,
): StructuralProposal | UnsupportedReceipt;
```

adapter 只有在 draft node/port 已能绑定源码位置或明确的插入位置时才产生 proposal。纯画布 ID、label 或坐标不足以构造正式源码修改；无法绑定时返回 unsupported receipt，而不是把 `scene_node_id` 冒充 `target_node_id`。

提交后的回收流程也要写成代码路径：

```text
commit receipt(sourceDigestAfter)
  -> 触发 Python 静态重新分析
  -> 得到新的 Exact Architecture IR
  -> 重建 KernelDocument
  -> 用 proposal correlation ID 匹配 canonical node/port/evidence
  -> 移除已兑现 synthetic node
  -> 无法匹配则保留 diagnostic，不能声称迁移成功
```

definition registry transaction 与 model source transaction 是两套并行版本空间。前者批准“Conv2d 这个模块类型如何定义”，后者批准“某个项目源码中增加一个 Conv2d 实例”；review receipt、digest 和权限不能混用。

### 18.16 测试与验收要求

除第 16 节已有的视觉回归外，注册表和契约系统至少增加：

1. 每个 definition 的 schema 默认值、序列化 round-trip 和版本 migration 测试；
2. 每个端口的合法方向、错误方向、缺失必需连接、连接超额和非法 relation 测试；
3. Conv2d/Linear/Add/Reshape/MHA 的具体 Shape、符号 Shape、未知维度和错误 Shape 测试；
4. 参数变化触发 ports/shape/cost/code 缓存失效的测试；
5. 同一文档和 registry 输入产生相同 digest、AnalysisSnapshot 和投影的确定性测试；
6. engineering/paper 对同一 definition 解析到相同 `glyphId` 的测试；
7. 未解锁时所有拓扑命令被 command/API 层拒绝的测试；
8. 已批准 definition 不能原地修改、receipt 与 candidate digest 严格绑定的测试；
9. breaking contract 未提供 migration 时无法发布的测试；
10. topology draft 可暂存不完整图，但 blocking diagnostic 未清零时无法提交的测试；
11. PyTorch printer 对 tuple、多输出、共享 module、特殊字符串和值的安全编码测试；
12. synthetic proposal 经正式事务和源码重分析后被 canonical/evidence node 替换的集成测试。

首批迁移完成的判据不是“菜单中能看到 14 类”，而是至少一组代表性节点从 registry 创建、经命名端口连接、完成 Shape/成本分析、投影到现有画布，并能在锁定/草稿/审核状态之间保持同一组稳定 ID。

#### 18.16.1 与现有测试的衔接

现有测试已经覆盖视觉层，新增测试应在其上补语义层，而不是替换：

| 现有测试 | 已验证 | 新增断言 |
|---|---|---|
| [`model.test.ts`](./src/model.test.ts) | visual patch、clone、bounds | semantic command 不可由 `applyVisualPatch()` 触发；projection 不修改 graph |
| [`transformer-scene.test.ts`](./src/transformer-scene.test.ts) | 经典/T2T 展开、递归 detail、路由 | 相同原子 definition 的 engineering/paper `glyphId` 相同 |
| [`paper-transformer-scene.test.ts`](./src/paper-transformer-scene.test.ts) | 双列布局、底入顶出、semantic port | paper glyph 不为空；mask/memory slot 绑定到正式 port contract |
| [`atomic-hierarchy.test.ts`](./src/atomic-hierarchy.test.ts) | portal chain、最深端点、隐藏桥接边 | 插入无关 primitive 后 slot-based atom ID 不变 |
| [`routing.test.ts`](./src/routing.test.ts) | 选路和度量 | 端口投影 point/side 改变时 edge 仍引用同一 port ID |
| [`expansion.test.ts`](./src/expansion.test.ts) | 父节点放大、邻居平移 | topology digest 不因展开、拖动或 offset 改变 |

建议新增测试文件及职责：

```text
atomic-registry/registry.test.ts          # 唯一性、引用解析、digest、版本固定
atomic-registry/definitions.test.ts       # 每个 definition 的 schema/port contract
prototype-graph/commands.test.ts          # capability、stale digest、command receipt
prototype-graph/validate-graph.test.ts    # cardinality/relation/tensor/cycle
prototype-graph/project.test.ts           # 纯函数、稳定 ID、两种 preset
analysis-rules/shape/*.test.ts            # known/symbolic/unknown/boundary
analysis-rules/cost/*.test.ts             # shared params、重复调用、假设
glyph-registry/glyphs.test.ts             # paper/engineering primitive parity
codegen/printer.test.ts                   # AST、安全 literal、多输出和 source map
contract-review/diff.test.ts              # major/minor/patch 与 migration gate
```

其中 registry definitions 适合做数据驱动的通用契约测试：遍历每个已注册 definition，验证所有 input/output port 至少有一个合法 fixture 和一个非法 fixture；但不能只靠通用测试，Conv、MHA、LSTM、Repeat 等规则仍需专门的语义测试。

### 18.17 源码复用与许可证前置条件

当前 DL-Playground checkout 根目录未发现 `LICENSE`、`COPYING` 或 `NOTICE`。在版权许可或项目授权明确前，只应复用架构思想、行为观察和公开接口形态，并按本节契约重新实现；不要直接复制其 TypeScript/TSX 源码、样式或测试夹具。

实施时应保留一份来源记录，说明哪些能力是根据行为重新设计、哪些术语属于 PyTorch/React Flow 通用概念，以及是否有经授权的代码片段。若后续确认许可证，再由维护者决定是否保留 clean-room 实现或引入带 attribution 的依赖。
