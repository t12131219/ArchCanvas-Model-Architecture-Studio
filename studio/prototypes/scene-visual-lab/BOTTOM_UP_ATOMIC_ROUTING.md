# 备用方案：原子图优先的自底向上折叠路由

## 状态

- 状态：已在 Scene Visual Lab 落地，默认启用；保留逐层模式用于 A/B 回退。
- 适用范围：Scene Visual Lab 的父子模块展开、折叠、端口与箭头投影。
- 保持不变：现有图例、模块内部语义、`VisualPatch` / `SourceTransaction` 边界和当前默认路由实现。
- 启用方式：工具栏“层级”选择 `原子收束` / `逐层`；URL 可用 `?hierarchy=recursive` 固定旧模式。

## 结论

该方案可行，而且比逐层独立生成内部图与箭头更适合多级模块。

核心变化是把最深层原子节点和原子边作为唯一事实来源。系统先完成最详细视图的节点布局、端口分配和连线，再根据当前折叠状态把原子图投影为可见图。父模块不再拥有另一套与内部数据流无关的入口线和出口线，而是复用原子边穿过层级边界时产生的同一组稳定门户。

这会把“展开后重新猜测父层箭头应连接哪里”改成“同一条原子边在不同可见层级下的几何投影”，从数据模型上减少边界断点、重复竖线、累积折点和错误吸附。

## 当前瑕疵对应的结构原因

当前实现同时维护两类几何：

1. `LabScene.edges` 负责一级模块之间的外部连线。
2. `ModuleDetailDiagram.primitives` 负责每一级父模块内部的折线。

两者只通过父框的 `entryPoint` / `exitPoint` 约定衔接，并不知道彼此是否来自同一条语义数据流。递归展开时，每一级又独立生成自己的边界入口、母线和分支，所以容易出现：

- 外部箭头结束于一级父框边界，内部箭头却从二级父框的另一坐标开始。
- 多级父框各自产生一条长边界母线，视觉上形成重复竖线和多余折点。
- 一个子模块放大后，父层只能根据旧折线端点反推目标，误差会随层级累积。
- 箭头虽然在数值上接近边界，但并不属于同一个连接对象，遮挡或绘制顺序会重新暴露视觉断点。

截图中的长竖线和两段彼此独立的水平箭头正是这种“逐层拥有独立几何”的表现。

## 目标不变量

备用实现必须满足以下不变量：

1. 每条真实数据流只有一个稳定的 `atomicEdgeId`。
2. 任意展开状态下，每条原子边要么完全隐藏在同一个折叠模块内，要么恰好属于一条可见投影边。
3. 一条边跨越父子边界时，边界内外共享同一个 `portalId` 和完全相同的坐标。
4. 展开或折叠只改变可见代表节点和投影边，不改变原子节点、原子边和已确认的最深层布局。
5. 同一展开状态重复计算必须得到相同节点位置、门户顺序和路由。
6. 圆形运算节点的最终端口必须位于水平或垂直中轴线。

## 建议的数据模型

当前 `DetailPrimitive.flow.points` 只有绘制几何，没有稳定的来源、目标和层级身份。自底向上投影需要先增加一层与渲染无关的逻辑图：

```ts
interface AtomicNode {
  atomId: string;
  parentModuleId: string;
  bounds: Bounds;
  semanticKind: string;
  inputPorts: AtomicPort[];
  outputPorts: AtomicPort[];
}

interface ModuleNode {
  moduleId: string;
  parentModuleId?: string;
  childModuleIds: string[];
  atomIds: string[];
}

interface AtomicEdge {
  atomicEdgeId: string;
  sourcePortId: string;
  targetPortId: string;
  relation: EdgeRelation;
  semanticChannel?: string;
}

interface BoundaryPortal {
  portalId: string;
  moduleId: string;
  side: PortSide;
  slot: number;
  point: Point;
  atomicEdgeIds: string[];
}

interface ProjectedEdge {
  projectedEdgeId: string;
  sourceVisibleId: string;
  targetVisibleId: string;
  relation: EdgeRelation;
  atomicEdgeIds: string[];
  portalChain: string[];
}
```

`semanticChannel` 用于防止不应合并的数据流被错误收束。例如 Q、K、V，残差、条件、状态和普通前向流即使可见起点和终点相同，也应保留不同通道。

## 自底向上的生成流程

### 1. 归一化为原子图

所有模块构造器只声明：

- 原子节点及其父模块。
- 稳定输入、输出端口。
- 原子边的来源、目标、关系和语义通道。
- 模块层级树。

矩形、矩阵、圆形、文字和折线仍可由现有图例渲染器产生，但折线不再是逻辑关系的事实来源。

### 2. 布局最深层节点

先在各个最小父模块的局部坐标系中排布原子节点。随后从叶模块向根模块计算包围盒：

```text
module bounds = union(child module bounds, direct atom bounds) + header + padding
```

父模块只负责容纳子内容，不重新创造一套与内部节点脱离的拓扑。

### 3. 为原子边建立层级门户链

对每条原子边：

1. 找到来源原子与目标原子的最低公共祖先模块。
2. 从来源向上经过每个父模块时建立出口门户。
3. 从公共祖先向目标向下经过每个父模块时建立入口门户。
4. 相邻层级共享同一个门户坐标，形成连续的 `portalChain`。

门户坐标首先来自最深层已确认的原子路由，再按边界侧、语义通道和目标方向分槽。这样父层与子层不会各自计算一份入口点。

### 4. 按展开状态投影可见节点

定义 `visibleRepresentative(node, expansionState)`：

- 原子节点的所有祖先都展开时，代表节点是原子节点本身。
- 遇到第一个折叠祖先时，代表节点是该父模块。

每条原子边 `(u, v)` 被映射为：

```text
a = visibleRepresentative(u)
b = visibleRepresentative(v)

if a == b:
    隐藏为折叠模块内部关系
else:
    加入可见候选边 (a, b)
```

### 5. 自底向上收束箭头

候选边按以下键分组：

```text
(sourceVisibleId, targetVisibleId, relation, semanticChannel)
```

同组原子边收束为一条 `ProjectedEdge`，并保留完整的 `atomicEdgeIds`。不能只按可见起点和终点合并，否则会错误吞掉 Q/K/V、残差或条件支路。

折叠后箭头数量减少；重新展开时，投影边可无损恢复为原来的分支。必要时可在折叠边标签中展示数量，但第一版不必增加新的视觉元素。

### 6. 路由可见投影边

最终路由以稳定门户为硬约束：

- 第一段必须从来源端口或来源出口门户出发。
- 最后一段必须到达目标入口门户或目标端口。
- 中间必须按 `portalChain` 依次穿过层级边界。
- 路由器只能优化门户之间的走廊，不能移动门户造成层级断裂。

## 对截图问题的预期改善

对于 `Input → Dual encoder → Image encoder → Linear` 这类多级路径，系统只维护一条原子数据流及其门户链：

```text
Input output
→ Dual encoder portal
→ Image encoder portal
→ Linear portal
→ token / position atoms
```

当 `Linear` 折叠时，末端原子边被投影到 `Linear`；当 `Image encoder` 也折叠时，同一批边继续收束到 `Image encoder`。截图中的多条独立竖向母线不再由每层单独生成，边界两侧也不会存在不同的起点坐标。

## 与交互编辑的关系

- 拖动原子节点：只重算关联原子边及受影响门户。
- 拖动展开父模块：整体平移其子树和门户，不改变子树内部路由。
- 折叠父模块：只重算可见代表、边分组和模块外部走廊。
- 展开父模块：复用缓存的原子布局与门户链，避免重新猜测内部连接。
- 手动调整父框大小：改变包围盒和门户的边界投影，但不修改原子拓扑。

建议分别缓存：

```text
atomic layout cache  = hash(atom graph + manual atom offsets)
portal cache         = hash(atomic layout + hierarchy)
projection cache     = hash(expansion state + semantic grouping policy)
route cache          = hash(projected graph + visible bounds + route options)
```

## 原型接入状态

### 已完成：并行逻辑模型

- 新增 `atomic-hierarchy.ts`，从当前详情树生成稳定原子节点、原子边、边界门户与门户链。
- 保留 `module-details.ts` / `catalog-details.ts` 的图元构造器作为兼容输入，不改变已有图例。
- 无法绑定节点的折线端点以稳定 junction 身份保留，不伪造成模块节点。

### 已完成：运行时投影器

- `buildAtomicHierarchyProjection()` 是无副作用纯函数，交互画布与静态 SVG 共用。
- 根模块外部路由读取投影门户，父子层边界复用子层真实入口/出口。
- 展开边界的父层入边、子层出边和外部入边收束中间箭头。

### 已完成：最小原型 A/B

- 已增加 `recursive` / `atomic-bottom-up` 工具栏开关。
- 节点和图例渲染继续复用当前实现，只切换连线和层级投影来源。
- `atomic-bottom-up` 为默认，`recursive` 保留为回退和视觉基线。

### 阶段 D：评估是否回灌正式 Studio

- 仅迁移纯图投影、门户分配和路由函数。
- 保持正式 Studio 的 IR、Evidence、VisualPatch 和 SourceTransaction 约束不变。
- 原子边必须能追溯到 Architecture IR 或分析证据，不能从视觉几何反向伪造语义关系。

## 验收标准

### 结构测试

- 每个 `AtomicEdge` 在任意展开状态下覆盖次数恰好为 1：隐藏或属于一条投影边。
- 每条跨层边的相邻门户坐标差小于 `0.01`。
- 折叠再展开后，原子节点坐标、端口顺序和原子边身份不变。
- 不同 `relation` 或 `semanticChannel` 的边不会错误合并。
- 所有圆形节点连接均落在水平或垂直中轴线。

### 穷举状态

- 每个父模块：全部折叠、仅父层展开、逐层单支展开、允许的最大深度展开。
- 每条多分支结构：单分支、全部分支、残差、反馈、汇聚和 Q/K/V。
- 每个状态同时验证交互 SVG 和静态导出 SVG。

### 视觉指标

- 跨层边界断点为 0。
- 同一门户的重复短线为 0。
- 非语义需要的重叠竖向母线为 0。
- 展开前后未涉及节点的位移应最小化。
- 箭头尖端不遮挡目标图例或其他箭头主干。

## 风险与限制

- 完整原子图可能很大，应保留模块局部坐标和分层缓存，不应每次交互都展开为一个巨大 SVG。
- 边收束会隐藏多重关系，因此必须保留 `atomicEdgeIds`，不能只保存聚合数量。
- 用户手工移动折叠父模块与移动内部原子节点是两类变换，需要分别存储。
- 含循环、跨层残差和共享权重的模型不能只靠树结构；模块归属是树，数据流本身仍是一般有向图。
- 当前构造器以绘制图元为主，完成原子语义适配会比修补单个箭头的工作量大，但长期可显著减少多层特例。

## 采用判断

建议将本方案保留为下一代层级路由候选，而不是立即替换当前实现。若后续仍频繁出现“修复一层、另一层产生新断点”的情况，应优先进入阶段 A/B；这类问题说明逐层几何修补已经接近其维护上限。
