# ArchCanvas Scene Visual Lab

独立的 React、TypeScript 和 SVG 最小验证原型，用于比较节点视觉、连线标签与路由策略。原型只维护内存中的 `LabScene`，不会访问 Studio API、正式 workspace 或模型源码。

## 使用

从 `studio/` 目录运行：

```bash
npm run prototype:build
npm run prototype:serve
```

- 编辑器：<http://127.0.0.1:4312/>
- 案例矩阵：<http://127.0.0.1:4312/cases/index.html>
- 独立输出：`../build/scene-visual-lab/`

开发时可运行 `npm run prototype:dev`。修改案例或导出逻辑后重新执行 `prototype:build`，以刷新静态案例矩阵。

## 结构

- `src/types.ts`：与 Studio Scene 命名对齐的最小场景与 typed visual patch 类型。
- `src/model.ts`：节点和连线的增删改，以及节点删除时的关联连线清理。
- `src/routing.ts`：五种路由策略；自适应方案包含分散端口、节点净距、正交避障、共享线段惩罚、圆角折线和纵向标签。
- `src/scenarios.ts`：26 类压力拓扑和 1170 个路由/节点/标签穷举组合的维度定义。
- `src/module-details.ts`：原有九类模块的共享内部图元与新增家族的统一分发入口。
- `src/catalog-details.ts`：传统 ML、CNN/ViT、序列、生成、图网络、强化学习与参数适配等 30 类结构家族的内部图。
- `src/model-family-catalog.ts`：300 余个检索别名、结构家族归并和真实 IR 必须检查的差异轴。
- `src/detail-layout.ts`：父模块内子节点的稳定 ID、递归内联展开、同级增量排布、拖动边界、共享门户吸附和正交避让。
- `src/atomic-hierarchy.ts`：由最深层详情树生成稳定原子节点/边、边界门户和自底向上的层级投影。
- `src/expansion.ts`：确定性的父模块展开布局；接受递归内容尺寸，保留左侧位置并增量平移下游节点。
- `src/svg-export.ts`：交互编辑器和静态案例共享的 SVG 视觉语言，并输出各模块单独展开与全展开快照。
- `src/App.tsx`：编辑器、拖动预览、尺寸调整、检查器和方案导出。
- `vite.config.ts`：构建时生成每个组合的 SVG、JSON、分类页和总索引。

## 扩展方案

新增布线方案时，在 `RouteStyle`、`ROUTE_STYLES` 和 `routePoints()` 中添加同名分支。新增节点或标签视觉时，在对应样式联合类型、组合数组、React 渲染和 `svg-export.ts` 中添加实现。新增压力拓扑只需向 `SCENARIOS` 添加 `LabScene`。

当前语义图元包括张量矩阵/长方体、卷积特征图堆栈、Q/K/V 注意力、归一化条带、Add、Multiply 和 Concat。指标额外覆盖节点边框净距、端口拥挤、反向出发和共享线段长度。

## 备用层级路由方案

当前默认启用[原子图优先的自底向上折叠路由方案](./BOTTOM_UP_ATOMIC_ROUTING.md)：先建立最深层详情树和稳定原子身份，再把子层真实门户自底向上投影到父层与外部边，并收束层级边界的中间箭头。工具栏“层级”可切回“逐层”作为 A/B 基线；该实现不改变现有图例和交互数据。

所有带内部图的场景都可用右上角按钮显示或隐藏内部数据流。每个内部图使用同一契约：外部输入与父模块左侧中心端口重合，内部宏观流向从左到右，最后节点连接父模块右侧中心端口，再由外部边继续进入下一模块。展开状态不会修改基础 `LabScene` 坐标，而是从基础场景重新派生放大尺寸、下游位移和外部路由，因此收起后会确定性恢复原布局。构建产物为每个模块输出单独展开和全部展开的 SVG/JSON 快照。

父模块展开后，其中的矩形、矩阵和运算圆均是独立子节点：点击可在检查器查看坐标，拖动时相关内部箭头会实时重新吸附并绕开无关子节点。带圆形 `+` 控件的子节点可继续钻取下一层结构；展开内容会内联替换该子节点，同级未展开子节点和汇合节点继续保留，后续同列节点向下移动、右侧节点向右移动，父框按内容递归增长。每一级的输入与输出都吸附展开框左右边界，内部首尾数据流与同级数据流保持连续。相同规则可递归到更深层，任意层子节点仍可选择、拖动、收起和复位；导出的 JSON 和 SVG 会保留展开树与各层内部布局。

视觉回归可使用只读 URL 参数直接打开指定状态：`?scene=<scene-id>&expand=<detail-kind>` 展开目标父模块，追加 `&drilldown=<child-label>` 可直接打开匹配的二级结构。例如：

```text
/?scene=sequence-generative-catalog&expand=bidirectional-recurrent&drilldown=rnn
```

## 设计依据

- [JointJS Links and routing](https://docs.jointjs.com/learn/features/diagram-basics/links/#routing)：锚点、边界连接点、Manhattan 避障路由和圆角连接器的职责分离。
- [ELK Layered](https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html)：端口约束、端口顺序、边节点间距、共享路径惩罚和标签间距。
- [yFiles Edge Router](https://docs.yworks.com/yfiles-html/search/?q=edge%20router)：端口候选、节点边距、最小角点距离、单调路径和交叉成本。
- [yFiles Incremental Diagram Layout](https://www.yworks.com/pages/incremental-diagram-layout)：展开时只插入必要空间、轻微移动既有节点并保持相对顺序，以保护用户的空间记忆。
- [TensorBoard Graphs](https://www.tensorflow.org/tensorboard/graphs)：将父节点作为内部节点容器，通过展开/收起在概念图与算子细节之间切换。
- [PyTorch Embedding](https://docs.pytorch.org/docs/stable/generated/torch.nn.Embedding.html)：索引输入、词表查找和嵌入向量输出的形状语义。
- [PyTorch LSTM](https://docs.pytorch.org/docs/stable/generated/torch.nn.LSTM.html)：输入门、遗忘门、候选状态、输出门以及 `c_t` / `h_t` 更新关系。
- [PyTorch MaxPool2d](https://docs.pytorch.org/docs/stable/generated/torch.nn.MaxPool2d.html)：池化窗口与空间降采样语义。
- [Hugging Face Mixture of Experts](https://huggingface.co/blog/moe)：router、top-k 专家选择、并行 FFN 与加权汇聚结构。
- [NN-SVG](https://alexlenail.me/NN-SVG/) 与 [PlotNeuralNet](https://github.com/HarisIqbal88/PlotNeuralNet)：卷积特征图堆栈、三维张量和求和图元。
- 本地 `Constraint relationship of architecture diagram/`：矩阵、Q/K/V、Add/Multiply、残差和张量长方体的论文图表达。

离线固定版本源码、许可证、网页视觉核对记录，以及 39 类父模块中每个图例和箭头的源码对应关系，见 [`references/README.md`](./references/README.md)、[`references/SOURCE_TRACEABILITY.md`](./references/SOURCE_TRACEABILITY.md) 和 [`references/MODEL_FAMILY_TRACEABILITY.md`](./references/MODEL_FAMILY_TRACEABILITY.md)。这些参考文件不参与原型构建，也不会被 Studio 导入执行。

决定回灌正式 Studio 后，优先迁移纯函数与样式参数，不迁移原型编辑状态：

1. 路由候选与度量进入 Studio 的路由模块。
2. 节点、连线和标签渲染进入 `scene-graphics.tsx`。
3. 保持正式程序的 `VisualPatch` 与 `SourceTransaction` 边界不变。
