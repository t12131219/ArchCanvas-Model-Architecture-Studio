# Scene Visual Lab 技术内核受控集成方案

状态：Proposed

目标版本：未定

适用范围：`archcanvas_publication`、`archcanvas_studio`、Studio Web 前端

决策结论：抽取并重接技术内核，不整体移植 Scene Visual Lab

## 1. 背景与目标

Scene Visual Lab 已验证多层展开、自底向上的原子门户投影、正交路由、端口分配、避障、语义图元和压力场景生成。它可以作为正式视觉/路由内核的实现来源，但不能成为新的事实层或编辑协议。

本方案的目标是：

1. 将原型中已验证的路由、门户投影、视觉图元和质量度量接入正式 Studio。
2. 让所有路由输入来自 `ArchitectureIR`、Evidence 和 `PublicationView`，不再从图形几何反推模型语义。
3. 保持 `VisualPatch` 与 `SourceTransaction` 的安全边界不变。
4. 让交互画布和 SVG/PNG/PDF 导出消费同一份权威场景几何。
5. 通过 feature flag、shadow comparison 和逐步放量替换旧路由，任何阶段均可回退。

非目标：

- 不把 `LabScene`、`LabPatch` 或原型内存状态升级为正式协议。
- 不让视觉层创建、删除或修改 Exact IR 的执行节点、端口和边。
- 不把原型中的模块模板当作用户源码的真实内部结构。
- 不在本次迁移中同时重写整个 `studio/src/main.tsx`。
- 不执行用户项目来补足静态分析无法证明的关系。

## 2. 不可破坏的不变量

迁移后的实现必须持续满足以下条件：

1. `SourceSnapshot + Evidence + ArchitectureIR` 是模型事实的唯一权威来源。
2. canonical identifier 不得由坐标、渲染顺序、折线路径或展开状态生成。
3. `PublicationView` 决定当前可见前沿；路由器只对该前沿做投影和几何计算。
4. 视觉 patch 不得改变 `source_digest`、Exact IR 或 Evidence。
5. 节点/边结构修改必须进入 proposal 或 `SourceTransaction`，并经过 prepare、verify、review、commit。
6. 一条可见边必须可追溯到至少一条 canonical edge；无法证明来源时不得伪造执行语义。
7. 折叠、展开和重新布局不得改变 canonical node/edge/port 身份。
8. 静态导出只能渲染正式 `VisualScene`，不得在导出时重新猜测端点或重新路由。
9. 不支持、跳过或回退的路由能力必须产生结构化诊断，不得报告为通过。

## 3. 当前系统与替换边界

正式链路当前为：

```text
ArchitectureIR
  -> PublicationHierarchy / PublicationView
  -> VisualSpec
  -> archcanvas_publication.layout.build_scene()
  -> VisualScene
  -> React SVG / publication renderers
```

`build_scene()` 和 `_relayout_compound_scene()` 同时承担节点布局、容器整理、端口偏移和边路由。前端已有 memo 化的 `SceneNodeGraphic`、`SceneEdgeGraphic`，并在拖动时通过 DOM transform 与局部 edge preview 避免每个 pointer move 重渲染整个场景。视觉修改通过 `/api/patch` 或 `/api/patch-batch` 写入 `CanvasDocument`。

目标不是替换整条流水线，而是在 `PublicationView -> VisualScene` 之间引入有明确合同的路由阶段：

```text
SourceSnapshot + Evidence + ArchitectureIR
                    |
                    v
          PublicationHierarchy
                    |
        expanded_node_ids / frontier
                    |
                    v
             PublicationView
                    |
                    v
       RoutingGraphAdapter (Python)
                    |
                    v
        EvidenceBackedRoutingGraph
                    |
          +---------+---------+
          |                   |
          v                   v
 Visible Projection      Style Resolver
 / Portal Chains              |
          +---------+---------+
                    v
              Route Kernel
                    |
                    v
        RoutedScene / VisualScene
          |                   |
          v                   v
 React scene primitives   SVG/PNG/PDF renderer
```

Python 负责权威场景生成；TypeScript 只负责交互期间的同构乐观预览。pointer up 后必须以 Python 返回的新 `VisualScene` 覆盖预览。

## 4. 原型资产的处理方式

| 原型资产 | 正式处理 | 原因 |
|---|---|---|
| `routing.ts` | 抽取算法规范，分别实现 Python 权威版本与 TS 预览版本 | 路由和度量可复用，但正式提交必须由后端裁决 |
| `atomic-hierarchy.ts` | 保留投影思想，基于 Exact IR 重写 | 当前实现从详情图元和坐标反推原子关系，不满足事实合同 |
| `detail-layout.ts` | 抽取容器约束、端口稳定和递归布局规则 | 不能继续依赖硬编码详情树作为模型事实 |
| `module-details.ts`、`catalog-details.ts` | 迁为可选 Pattern Pack/视觉模板 | 可提供视觉建议，不得声称是用户模型真实结构 |
| `svg-export.ts` | 保留视觉参数与测试夹具，不迁移独立路由 | 正式导出必须直接消费 `VisualScene` |
| `scenarios.ts` | 转为正式 route fixtures 与视觉回归资产 | 26 类压力拓扑适合做算法回归 |
| `App.tsx`、`model.ts`、`LabPatch` | 不迁移 | 原型编辑模型会绕过正式 API 与事务边界 |
| `types.ts` 的 `LabScene` | 不迁移 | 正式模型必须继续使用 core schema |

原型目录在 Phase 0 后冻结为参考实现。后续修复优先进入正式内核；只有用于对比的案例和 fixture 可继续回灌原型。

## 5. 正式路由数据合同

### 5.1 内部模型

新增 `src/archcanvas_publication/routing_models.py`。这些模型是 publication 内部合同，不是第二套 Architecture IR。

```python
@dataclass(frozen=True)
class RoutingNode:
    routing_node_id: str
    scene_node_id: str
    view_node_id: str
    canonical_node_ids: tuple[str, ...]
    parent_routing_node_id: str | None
    bounds: RoutingRect
    semantic_kind: str
    collapsed: bool
    evidence_ids: tuple[str, ...]
    candidate_port_ids: tuple[str, ...]

@dataclass(frozen=True)
class RoutingPort:
    routing_port_id: str
    owner_routing_node_id: str
    canonical_port_ids: tuple[str, ...]
    direction: Literal["input", "output"]
    semantic_role: str
    semantic_channel: str | None
    allowed_sides: tuple[PortSide, ...]
    preferred_side: PortSide | None
    evidence_ids: tuple[str, ...]

@dataclass(frozen=True)
class RoutingEdge:
    routing_edge_id: str
    view_edge_id: str
    canonical_edge_ids: tuple[str, ...]
    source_port_id: str
    target_port_id: str
    tensor_ids: tuple[str, ...]
    semantic_channel: str | None
    visual_relation: str
    evidence_ids: tuple[str, ...]

@dataclass(frozen=True)
class BoundaryPortal:
    portal_id: str
    owner_routing_node_id: str
    child_routing_node_id: str
    side: PortSide
    point: RoutingPoint
    canonical_edge_ids: tuple[str, ...]

@dataclass(frozen=True)
class PortalChain:
    routing_edge_id: str
    source_port_id: str
    portal_ids: tuple[str, ...]
    target_port_id: str

@dataclass(frozen=True)
class RouteGeometry:
    routing_edge_id: str
    points: tuple[RoutingPoint, ...]
    source_port_id: str
    target_port_id: str
    portal_ids: tuple[str, ...]
    fallback_reason: str | None
```

字段约束：

- `routing_*_id` 必须由稳定的 view/canonical 身份和策略版本生成，不能包含坐标或数组下标。
- `canonical_*_ids` 和 `evidence_ids` 只允许由正式输入复制、聚合，不允许路由器创造。
- `semantic_channel` 用于区分 Q/K/V、残差、条件、状态、训练专用等不能错误合并的流。
- `allowed_sides` 是布局约束，不是模型语义；它可以来自布局族、用户 route hint 或视觉策略。
- 坐标只存在于 routing/scene 层，不写回 Architecture IR。

### 5.2 `SceneEdge` 合同补齐

当前 Python `SceneEdge` 已保存 view/canonical edge 身份，但缺少端口和 Evidence；前端类型还未完整声明已有身份字段。采用向后兼容的增量迁移：

```python
class SceneEdge(StrictModel):
    # existing fields remain
    source_port_id: Identifier | None = None
    target_port_id: Identifier | None = None
    evidence_ids: list[Identifier] = Field(default_factory=list)
    portal_ids: list[Identifier] = Field(default_factory=list)
    route_digest: Sha256 | None = None
```

其中 `source_port_id`/`target_port_id` 是当前可见投影所使用的稳定 routing port；canonical port 集合仍可通过 `view_edge_id -> canonical_edge_ids -> ArchitectureEdge` 追溯。若后续需要直接暴露 canonical port，另加显式 `canonical_source_port_ids`，不要混用两种身份。

`studio/src/scene-graphics.tsx` 的 `SceneEdge` 应同步声明：

- `view_edge_id`
- `canonical_edge_ids`
- `source_port_id` / `target_port_id`
- `evidence_ids`
- `portal_ids`
- `route_digest`

兼容期内这些新增字段可选；切换到 `atomic-v1` 后，除 legacy 场景外必须存在。正式 schema minor version 应递增，读取器在迁移窗口同时接受旧版和新版，`tools/export_schemas.py --check` 必须纳入每个合同 PR。

### 5.3 路由回执

新增内部 `RoutingReceipt`，在构建、shadow comparison、调试下载和测试中使用：

```text
engine                 legacy | atomic-v1
engine_version         算法和权重版本
input_digest           规范化 RoutingGraph + projection + hints 的摘要
route_digest           量化后全部 RouteGeometry 的摘要
node_count / edge_count / portal_count
metrics                RoutingMetrics
fallbacks              edge_id + reason_code
diagnostics            结构化诊断，不包含源码正文
duration_ms             adapter / projection / route / validation 分段耗时
```

回执不进入 Architecture IR。是否持久化为 bundle sidecar 由 Phase 3 决定；至少应在测试与诊断 API 中可获得。

## 6. IR 驱动的自底向上投影

### 6.1 原子图建立

`RoutingGraphAdapter` 输入必须同时包含：

- `ArchitectureIR`
- 对应 Evidence ledger
- `PublicationHierarchy`
- 当前 `PublicationView`
- 已完成节点布局的 scene bounds
- 已验证的 route hints 和布局策略

适配过程：

1. 以 `ArchitectureNode.input_ports/output_ports` 建立原子端口表。
2. 以 `ArchitectureEdge.producer_id/producer_port/consumer_id/consumer_port` 建立原子边。
3. 以 `PublicationHierarchy` 建立任意深度的包含树。
4. 以 `PublicationView.expanded_node_ids` 和可见节点集合计算 visible frontier。
5. 建立 canonical node 到当前可见 routing node 的唯一映射。
6. 对每条原子边生成穿越包含边界的 `PortalChain`。
7. 只在 canonical provenance、方向、relation 和 semantic channel 全部兼容时聚合可见边。

适配器遇到缺失端口或不一致父子关系时应返回结构化错误或 legacy fallback，不得根据矩形相交位置补造端口。

### 6.2 任意层级的出口直连

对每条原子边 `u -> v`，分别求 source 和 target 在当前 frontier 上的最深可见代表：

```text
source_visible = deepest_visible_ancestor(u)
target_visible = deepest_visible_ancestor(v)
```

当父模块展开时，外部边的起点必须继续向内解析到最深可见 source port，而不是固定吸附父框出口。终点同理。因此该规则天然适用于一级、二级及更深层级，不需要按深度编写特例。

门户只用于约束路径穿越容器边界，不作为必须显示的中间箭头：

- 展开：显示最深可见端点之间的一条连续边，路径依次经过 portal chain。
- 折叠：把内部端点投影到折叠父模块的边界端口，并按兼容键收束。
- 部分展开：一端可落在深层子模块，另一端可落在折叠模块，仍由同一原子边投影。
- 无法唯一解析：回退到最近可证明的父级端口，并写入 `fallback_reason`。

### 6.3 边收束键

折叠时只有以下字段相同的原子边可以收束成一条可见边：

```text
(visible_source,
 visible_target,
 edge_type,
 visual_relation,
 semantic_channel,
 direction,
 execution_predicate_class)
```

Q/K/V、残差、状态更新、条件分支、训练专用流不得仅因起止父模块相同而合并。每条收束边保留完整 `canonical_edge_ids`、tensor IDs 和 Evidence 并集。

### 6.4 门户稳定性

门户 ID 使用：

```text
portal:<owner-view-node-id>:<boundary-child-id>:<channel-key>:<direction>
```

同一输入、展开状态和 route hint 下：

- portal ID、side、slot order 必须稳定；
- 折叠再展开后恢复相同的端口顺序；
- 节点平移只改变坐标，不改变 portal/edge 身份；
- 同一容器边界内的 input/output 分槽独立排序；
- 端口中心优先按语义角色和稳定 ID 排序，不依赖当前数组顺序。

## 7. 路由内核设计

新增模块建议：

| 文件 | 职责 |
|---|---|
| `routing_models.py` | 不可变内部模型与枚举 |
| `routing_graph.py` | Exact IR/View 到 `EvidenceBackedRoutingGraph` 的适配与验证 |
| `routing_projection.py` | visible frontier、收束、portal chain、跨层端点解析 |
| `routing_kernel.py` | 候选端口、正交路径、避障、分槽和稳定性策略 |
| `routing_metrics.py` | 几何质量指标、违规检查、评分 |
| `routing_digest.py` | 规范化、坐标量化、input/route digest |
| `routing_fixtures.py` | JSON fixture 读写，仅供测试和调试 |

### 7.1 路由顺序

1. 固定显式 route hint、pin 和用户指定端口约束。
2. 为所有端点生成候选 side/slot。
3. 优先分配具有固定语义的端口，如 Q/K/V、残差、状态反馈。
4. 为普通边按方向、最短距离、拥挤度和稳定 ID 分配端口。
5. 建立 portal chain 并预留容器边界净距。
6. 生成正交候选路径。
7. 依次检查节点穿越、边框贴合、反向出发、急转弯、共享线段和标签空间。
8. 用确定性的词典序评分选择路径。
9. 简化共线点，但不得删除 portal 或语义 junction。
10. 计算 metrics、digest 和 fallback receipt。

### 7.2 评分优先级

不要用一个可互相抵消的总分掩盖正确性错误。候选选择使用词典序：

```text
1. invalid endpoint count
2. forbidden obstacle intersections
3. detached portal count
4. border overlap length
5. semantic channel overlap length
6. arrowhead occlusion count
7. crossings
8. bends
9. reverse departure penalty
10. total length
11. displacement from previous stable route
```

前四项必须为零才允许进入 `atomic-v1` 正式输出。对于无法满足的边，应记录原因并对该边或整个场景回退，不得输出看似成功但语义不完整的箭头。

### 7.3 端口与拖动稳定性

正式提交时，Python 可以重新选择最优端口。交互预览期间使用 gesture lock：

- pointer down 时冻结 edge identity、semantic port 和 portal chain。
- pointer move 时移动端点并只对受影响子图做局部预览。
- 只有越过明确 hysteresis 阈值时才切换普通边的 side；语义固定端口不切换。
- pointer up 后提交 `PatchBatch`，由后端完整重路由。
- 新 `VisualScene` 到达后移除 preview，若权威路径变化明显可做 100--160 ms 的短过渡，但不得延迟数据更新。

这样既避免端口在四个边之间反复跳动，也不把交互预览误当作持久化结果。

## 8. Python 权威与 TypeScript 预览的一致性

不采用两套独立设计，也暂不引入 WASM。采用“共享规范 + 双实现 + golden fixtures”：

1. Python 是唯一权威实现，负责 scene build、持久化后重建、导出和 route receipt。
2. TypeScript 仅实现 pointer move 所需的局部子集：端点、已冻结门户、正交预览和标签位置。
3. 常量、枚举、side 优先级和量化精度由一份生成的 JSON 配置提供。
4. Python 生成 fixtures，TS 测试消费同一批输入与期望 endpoint/portal signature。
5. TS 不要求与 Python 在每个中间点逐浮点相等，但必须满足：
   - source/target port ID 相同；
   - portal ID 序列相同；
   - 首尾点误差小于 `0.01`；
   - 路径正交且不穿越冻结障碍；
   - pointer up 后以 Python route digest 为准。

建议新增：

- `studio/src/scene-routing-preview.ts`
- `studio/src/scene-routing-preview.test.ts`
- `studio/src/generated/routing-policy.json`
- `tools/export_routing_policy.py`

现有 `scene-performance.ts` 保留 scene index、DOM transform 和 rAF 调度；把 `previewEdgePoints()` 的策略逻辑迁到 `scene-routing-preview.ts`，使性能基础设施与路由规则分离。

## 9. 共享渲染描述

目标不是让 Python 渲染 React，也不是让浏览器负责导出，而是让所有 renderer 消费同一 `VisualScene` 语义：

- 节点形状由 `SceneNode.shape + style fields` 决定。
- 边由 `SceneEdge.points + style fields + label anchor` 决定。
- arrow marker、圆角半径、dash、label rotation 等成为显式 scene/style 字段或统一常量。
- React 不重新路由；publication renderer 不重新选择图元。
- `route_digest` 必须在交互 API 与导出输入中一致。

可以先抽出语言无关的 `scene-style-policy.json`，由 Python renderer 与 TS graphic 共用。待字段稳定后再评估代码生成；不应为了“共享”而把浏览器运行时引入后端。

## 10. 源码驱动的视觉模板集成

原型中的 Attention、CNN、RNN、VAE 等例子不能作为固定图片套在源码分析结果上。正式实现必须把原型拆成“视觉模板 + 语义槽位”，然后用 Exact IR 中已经存在的节点、端口、张量和边填充槽位。

核心分工是：

```text
原型视觉资产决定：真实结构可以怎样清楚地画出来
Exact IR / Evidence 决定：这个项目实际上拥有哪些结构
VisualTemplateBinding 决定：模板槽位绑定到哪些真实 canonical IDs
```

### 10.1 当前能力和缺口

现有正式链路已经具备前半段：

```text
source
  -> static analyzer
  -> ArchitectureIR
  -> Pattern Pack matcher
  -> SemanticAnnotationOverlay
  -> PublicationHierarchy / PublicationView
```

现有 Pattern Pack 已保证应用前后的 Exact IR digest 相同，并支持 matched、generic、ambiguous 和 candidate preview。`compile_hierarchy()` 也会把 `semantic_role`、`group_id`、`glyph`、`layout_family` 等 annotation 信息带入 hierarchy/view attributes。

仍缺少：

```text
SemanticAnnotationOverlay
  -> typed VisualTemplateBinding
  -> template selection
  -> real canonical slot binding
  -> Publication layout constraints
  -> SceneNode / SceneEdge
```

当前 `build_visual_spec()` 主要根据普通 `PublicationNode` 类型选择 glyph，没有系统消费 `semantic_annotations`。现有 `PatternPredicate` 也主要回答“是否存在足够多的某类事实”，不能表达“哪个 Linear 是 Q，哪个是 K，哪个 MatMul 是 score”。因此必须同时补上视觉模板合同和角色绑定合同，不能只增加更多 glyph 名称。

### 10.2 原型资产分层

原型资产分为四层，迁移策略不同：

| 层级 | 正式资产 | 示例 | 是否要求子图匹配 |
|---|---|---|---|
| 原子图元 | `GlyphRecipe` | Add、Multiply、Concat、Linear、Conv、Tensor、Norm | 否 |
| 复合模板 | `VisualTemplateManifest` | Attention、LSTM Cell、VAE Encoder、Transformer Block | 是 |
| 解释示意 | `SceneAnnotation`/解释 overlay | 源码未暴露的标准 Q/K/V 示意 | 否，但必须标记非执行 |
| 原型几何 | 测试参考，不进入产品合同 | 固定坐标、固定折线、图片式内部图 | 不迁移 |

原子图元只改变一个真实节点的表现。复合模板为多个真实节点提供槽位、相对布局和路由偏好。解释示意不能参与执行图、选择身份或源码编辑。原型中的绝对坐标和预画箭头只保留为视觉参考与 fixture。

### 10.3 原子图元解析

新增 `GlyphResolver`，输入只使用已验证的正式事实：

```text
ArchitectureNode.kind
+ attributes.op_type / transform / merge
+ input/output port roles
+ TensorValue.symbolic_shape / semantic_axes
+ ArchitectureEdge.edge_type
+ SemanticAnnotation
 -> GlyphRecipe
```

首批映射：

| IR 事实 | 默认图元 | 说明 |
|---|---|---|
| add/merge-add | 带 `+` 的圆形 | 多输入汇合点，端口按中轴分槽 |
| multiply/elementwise-mul | 带 `x` 的圆形 | 与矩阵乘法区分 |
| matmul | 矩阵乘法节点 | 显示输入 shape 时可使用矩阵片 |
| concat | Concat 汇合图元 | 保留输入顺序和 axis |
| `nn.Conv1d/2d/3d` | 特征图/卷积网格堆栈 | 根据维度选择 1D、2D、3D 表达 |
| `nn.Linear`/projection | 投影梯形或矩阵变换 | 不暗示激活函数 |
| normalization | 归一化条带 | LayerNorm、BatchNorm 等用 secondary label 区分 |
| tensor + two spatial axes | 矩阵或长方体 | 尺寸来自 shape，不由图元反推 |
| sequence/time axis | 序列条带 | 仅在 semantic axes 有证据时启用 |
| repeat | 堆叠图元 + 次数 | 次数来自 `Repeat` |

解析优先级必须稳定：

```text
explicit visual override
  > exact op/transform fact
  > evidence-backed semantic annotation
  > node kind default
  > generic opaque glyph
```

名称只能作为低权重提示，不能覆盖结构事实。

### 10.4 `VisualTemplateManifest` 合同

建议在 `src/archcanvas_publication/templates/` 保存声明式 JSON 模板，并由 `visual_templates.py` 加载。模板文件不得包含 Python、JavaScript、表达式求值或外部资源加载。

```python
class VisualTemplateSlot(StrictModel):
    slot_id: Identifier
    kind: Literal["node", "edge", "port", "tensor"]
    accepts: list[str]
    cardinality: Literal["one", "optional", "one-or-more", "many"]
    semantic_role: str | None = None

class TemplateLayoutConstraint(StrictModel):
    operation: Literal[
        "left-of", "above", "parallel", "align-center",
        "same-rank", "contain", "merge-before", "flow-direction"
    ]
    subjects: list[Identifier]
    strength: Literal["required", "preferred"]
    value: str | float | None = None

class VisualTemplateManifest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    template_id: Identifier
    version: str
    root_role: str
    supported_ir_versions: list[str]
    slots: list[VisualTemplateSlot]
    constraints: list[TemplateLayoutConstraint]
    glyph_overrides: dict[Identifier, str]
    entry_slots: list[Identifier]
    exit_slots: list[Identifier]
    fallback_glyph: str
    test_inventory: list[str]
```

Attention 模板示例：

```json
{
  "template_id": "attention.qkv-v1",
  "version": "1.0.0",
  "root_role": "attention",
  "supported_ir_versions": ["1.0"],
  "slots": [
    {"slot_id": "input", "kind": "tensor", "accepts": ["sequence"], "cardinality": "one"},
    {"slot_id": "q_projection", "kind": "node", "accepts": ["linear"], "cardinality": "one"},
    {"slot_id": "k_projection", "kind": "node", "accepts": ["linear"], "cardinality": "one"},
    {"slot_id": "v_projection", "kind": "node", "accepts": ["linear"], "cardinality": "one"},
    {"slot_id": "score_matmul", "kind": "node", "accepts": ["matmul"], "cardinality": "one"},
    {"slot_id": "softmax", "kind": "node", "accepts": ["softmax"], "cardinality": "one"},
    {"slot_id": "value_matmul", "kind": "node", "accepts": ["matmul"], "cardinality": "one"},
    {"slot_id": "output_projection", "kind": "node", "accepts": ["linear"], "cardinality": "one"}
  ],
  "constraints": [
    {"operation": "flow-direction", "subjects": ["input", "output_projection"], "strength": "required", "value": "left-to-right"},
    {"operation": "parallel", "subjects": ["q_projection", "k_projection", "v_projection"], "strength": "required"},
    {"operation": "merge-before", "subjects": ["value_matmul", "output_projection"], "strength": "preferred"}
  ],
  "glyph_overrides": {
    "q_projection": "projection",
    "k_projection": "projection",
    "v_projection": "projection",
    "score_matmul": "multiply",
    "softmax": "normalization"
  },
  "entry_slots": ["input"],
  "exit_slots": ["output_projection"],
  "fallback_glyph": "attention",
  "test_inventory": ["attention-self", "attention-cross", "attention-negative"]
}
```

模板只能表达相对布局和图元偏好，不能包含 canonical IDs、绝对源码路径或最终折线路径。模板的 edge slot 只能绑定真实 `ArchitectureEdge`，不能创建执行边。

### 10.5 Pattern Pack 角色捕获

在 `PatternPackManifest` 中新增强类型的 capture 和 relation constraint，而不是依赖名称或列表位置：

```python
class PatternCapture(StrictModel):
    capture_id: Identifier
    entity: Literal["node", "edge", "port", "tensor"]
    selector: PatternPredicate
    cardinality: Literal["one", "optional", "one-or-more", "many"]

class PatternRelationConstraint(StrictModel):
    relation_id: Identifier
    source_capture: Identifier
    target_capture: Identifier
    relation: Literal[
        "produces", "consumes", "connects", "contains",
        "shares-input", "shares-parameter", "precedes"
    ]
    edge_type: str | None = None
    port_role: str | None = None
    required: bool = True

class PatternTemplateRule(StrictModel):
    rule_id: Identifier
    template_id: Identifier
    root_capture: Identifier
    captures: list[PatternCapture]
    relations: list[PatternRelationConstraint]
```

匹配分为五步：

1. 依据 node kind、op type、transform 等强结构事实生成候选。
2. 依据真实 producer/consumer port 和 edge 验证数据流关系。
3. 依据 shape/semantic axes 排除不兼容候选。
4. 依据 repeat、sharing、execution predicate 验证控制和共享关系。
5. 最后才使用 weak name 给已通过硬约束的候选排序。

`PatternPredicate` 的全局 count 匹配继续用于识别模型家族；`PatternCapture` 负责为具体模板建立一一可追溯的角色绑定。两者不能混为同一结果。

当多个 capture assignment 同分且无法用结构事实消歧时，结果必须是 ambiguous，不得按源码顺序、坐标或 ID 字典序随意选择一个并宣称 exact。

### 10.6 `VisualTemplateBinding` 合同

`SemanticAnnotationOverlay` 增加默认空列表 `template_bindings`，保持 Pattern Pack 仍只输出 overlay 的现有安全边界：

```python
class VisualTemplateBinding(StrictModel):
    binding_id: Identifier
    template_id: Identifier
    template_version: str
    root_canonical_node_ids: list[Identifier]
    node_slots: dict[Identifier, list[Identifier]]
    edge_slots: dict[Identifier, list[Identifier]]
    port_slots: dict[Identifier, list[Identifier]]
    tensor_slots: dict[Identifier, list[Identifier]]
    evidence_ids: list[Identifier]
    predicate_ids: list[Identifier]
    fidelity: Literal["exact", "opaque", "schematic"]
    binding_digest: Sha256
```

约束：

- `exact` 的所有 required slots 必须满足 cardinality。
- node/edge/port/tensor ID 必须存在于同一 Architecture IR。
- edge slot 的端点必须与已绑定 node/port slot 一致。
- `evidence_ids` 是所有绑定实体 Evidence 的稳定并集。
- `binding_digest` 由 template version、Exact IR digest 和规范化 slot mapping 生成。
- overlay 应用前后 Exact IR digest 必须相同。
- stale、ambiguous 或 template version 不兼容的 binding 不得进入 PublicationView。

Attention exact binding 示例：

```json
{
  "binding_id": "binding:attention:block-3",
  "template_id": "attention.qkv-v1",
  "template_version": "1.0.0",
  "root_canonical_node_ids": ["node:block-3.attention"],
  "node_slots": {
    "q_projection": ["node:block-3.q-proj"],
    "k_projection": ["node:block-3.k-proj"],
    "v_projection": ["node:block-3.v-proj"],
    "score_matmul": ["node:block-3.qk-matmul"],
    "softmax": ["node:block-3.softmax"],
    "value_matmul": ["node:block-3.av-matmul"],
    "output_projection": ["node:block-3.out-proj"]
  },
  "edge_slots": {
    "q_to_score": ["edge:block-3.q-score"],
    "k_to_score": ["edge:block-3.k-score"],
    "weights_to_value": ["edge:block-3.weights-value"]
  },
  "port_slots": {},
  "tensor_slots": {},
  "evidence_ids": ["evidence:attention-source"],
  "predicate_ids": ["linear-projections", "qk-score-route", "softmax-route"],
  "fidelity": "exact",
  "binding_digest": "..."
}
```

### 10.7 三档可信度

#### Exact

源码和 IR 已提供完整内部节点、端口和数据流。可以实例化交互式内部图：

- 每个图元绑定 canonical node/tensor。
- 每条箭头绑定 canonical edge 和 port。
- Inspector 可以定位源码 Evidence。
- 子模块可以继续展开。
- 视觉移动只产生 VisualPatch。

例如源码明确包含 `q_proj`、`k_proj`、`v_proj`、QK MatMul、Softmax 和 AV MatMul，才能显示 exact Q/K/V 数据流。

#### Opaque

源码只暴露一个模块调用或分析器无法证明内部结构，例如单个 `nn.MultiheadAttention` 调用。此时只显示：

- Attention 专用父模块 glyph。
- 源码中真实存在的输入、输出端口。
- 可证明的参数、shape 和 Evidence。
- `implementation hidden/unresolved` 的解析状态。

不得产生可选择的虚构 Q/K/V canonical nodes，也不得从 opaque 内部发起 SourceTransaction。

#### Schematic

产品需要显示“该类模块通常如何工作”时，可将原型内部图作为解释 overlay：

- 使用独立 annotation layer 和明确的示意视觉状态。
- 不产生 canonical node/edge/port ID。
- 不参与 routing graph 的执行边覆盖率。
- 不参与选择、搜索、GraphDelta 或 SourceTransaction。
- 默认可关闭，导出时必须标记为 schematic。
- Inspector 明确说明它不是当前源码的解析结果。

`schematic` 不能自动升级为 `exact`。只有重新分析产生了完整 IR 并通过 binding validation 后，才能切换可信度。

### 10.8 模板实例化到 Publication 和 Scene

完整链路为：

```text
ArchitectureIR
  -> apply_pattern_packs()
  -> SemanticAnnotationOverlay.template_bindings
  -> compile_hierarchy()
  -> project_hierarchy(expanded_node_ids)
  -> PublicationNode.visual_binding_ids
  -> build_visual_spec()
  -> GlyphResolver / VisualTemplateRegistry
  -> template layout constraints
  -> SceneNode / SceneEdge
  -> RoutingGraphAdapter
  -> authoritative route kernel
```

职责划分：

- `apply_pattern_packs()` 只匹配和绑定 canonical entities。
- `compile_hierarchy()` 验证 binding digest，并把 binding identity 传播到对应 hierarchy node。
- `project_hierarchy()` 只保留当前 frontier 能完整或部分表示的绑定。
- `build_visual_spec()` 根据 glyph precedence 和 binding fidelity 选择表现。
- scene builder 将 template constraint 降低为普通节点 bounds、container membership 和 route hints。
- routing kernel 仍以正式端口和边为输入，模板不能提供替代箭头。

建议为 `PublicationNode` 增加显式 `visual_binding_ids`，而不是长期把强类型绑定塞在自由形态的 `attributes` 中。`VisualSpec` 可增加 `template_instances`，每个 instance 保存 template/binding ID、fidelity、可见 slot 与布局约束，不复制 Exact IR 实体。

### 10.9 展开、折叠和交互

父模块展开后，模板不能渲染为一张图片。exact template 必须实例化为普通 Scene 节点：

```text
Attention parent SceneNode
  |- q_projection SceneNode -> canonical q projection
  |- k_projection SceneNode -> canonical k projection
  |- v_projection SceneNode -> canonical v projection
  |- score_matmul SceneNode  -> canonical score op
  |- softmax SceneNode       -> canonical softmax op
  |- value_matmul SceneNode  -> canonical value op
  `- output_projection SceneNode -> canonical output projection
```

所有实例化节点继续携带：

- `view_node_id`
- `canonical_node_ids`
- `parent_scene_node_id`
- `evidence_ids`
- stable routing ports
- `template_instance_id` 和 `slot_id`

因此节点可以选择、移动、查看 Evidence 和继续展开。模板只提供首次布局；用户位置 patch、pin、route hint 具有更高优先级。

折叠时不保存一套独立模板边。正式 atomic projection 按当前 visible frontier 收束同一批 canonical edges。再次展开时根据 stable binding/slot identity 恢复节点和端口，而不是重新依赖几何猜测角色。

### 10.10 模板选择和冲突规则

同一节点或子图可能同时命中原子 glyph、多个 Pattern Pack 和用户视觉覆盖。统一优先级：

```text
user visual override
  > exact template binding
  > exact atomic glyph
  > opaque specialized glyph
  > schematic annotation (separate layer)
  > generic glyph
```

冲突处理：

- 两个 exact binding 覆盖相同 canonical edge 且角色不一致：标记 ambiguous，全部回退 generic。
- workspace pack 与 builtin pack 冲突：workspace 只有在约束更具体且 digest lock 有效时才可覆盖。
- binding 只满足 optional slot：仍可 exact，但缺失槽位不得虚构；模板必须声明允许缺失。
- required slot 缺失：降为 opaque 或 generic。
- template version 不支持当前 IR：generic，并写 receipt。
- 用户视觉 override 只能改变图元和布局，不能改变 slot 的 canonical binding。

### 10.11 失败回退矩阵

```text
完整角色绑定且 Evidence 有效
  -> exact interactive template

父模块可识别但内部结构不可证明
  -> opaque specialized glyph

用户显式开启概念说明
  -> separate schematic overlay

Pattern Pack 冲突、binding stale 或 required slot 缺失
  -> generic node/container + structured diagnostic

只有名称相似
  -> generic；name hint 不得单独激活模板
```

模板失败不能阻止基础模型图生成。回执至少记录 template ID、binding ID、fidelity、matched predicate IDs、rejection reason 和 fallback glyph。

### 10.12 模板版本、缓存与安全

- 模板 manifest 使用内容 digest 和显式 version。
- scene/cache key 加入 template digest 和 binding digest。
- 模板升级不能改变 canonical identity，只能改变视觉约束和默认图元。
- workspace template 必须使用 digest lock；session candidate 只能 preview。
- 模板 loader 拒绝可执行 matcher、脚本、远程 URL 和越界资源路径。
- 模板选择不执行用户代码，也不导入用户框架。
- 导出 artifact 应记录使用过的 template ID/version/digest。

### 10.13 代码落点

建议新增或修改：

| 文件 | 改动 |
|---|---|
| `src/archcanvas_core/models.py` | `VisualTemplateBinding`、capture/relation 合同、overlay 新字段 |
| `src/archcanvas_patterns/matcher.py` | 子图 capture、关系约束、ambiguity 和 binding digest |
| `src/archcanvas_patterns/builtin/*/pattern.json` | 从家族识别扩展到可验证角色绑定 |
| `src/archcanvas_publication/visual_templates.py` | 模板 registry、digest、compatibility validation |
| `src/archcanvas_publication/templates/*.json` | 声明式 glyph/compound template |
| `src/archcanvas_publication/compiler.py` | 传播 binding identity 和 fidelity |
| `src/archcanvas_publication/layout.py` | `GlyphResolver`、template constraint lowering |
| `src/archcanvas_core/schemas/` | 导出的增量协议 schema |
| `studio/src/scene-graphics.tsx` | 通用 glyph primitive 和 template instance 渲染 |
| `tests/test_visual_templates.py` | manifest、binding、fallback、digest、holdout 测试 |

禁止把模板构造继续塞入 `studio/src/main.tsx`。React 只渲染后端已经选择并实例化的 scene primitive。

### 10.14 首批迁移目录

按证据需求和风险分批：

1. **原子图元**：Add、Multiply、Concat、Tensor、Conv、Linear、Norm、Activation、Repeat。
2. **首个 exact 复合模板**：Multi-head Attention，用于打通 capture、binding、展开和跨层路由。
3. **状态型模板**：RNN/LSTM/GRU，重点验证 state-update 和循环边。
4. **编码生成模板**：VAE Encoder/Sampling/Decoder，重点验证多输出、随机变量和 opaque 降级。
5. **分支专家模板**：MoE、router、top-k、expert merge，重点验证条件/路由语义。
6. **视觉骨干模板**：CNN block、residual block、ViT patch embedding。
7. **时序模型模板**：Autoformer、PatchTST、iTransformer、TimeMixer，复用现有 acceptance fixtures。

每个模板必须同时提供 positive、negative、mutation、ambiguity、digest invariance、collapsed/expanded 和 holdout 测试。只有原型截图而没有可绑定 IR fixture 的模板保持 schematic，不进入 exact registry。

禁止：

- 仅因模块名包含 `attention` 就创建 Q/K/V canonical nodes。
- 用模板边替换 `ArchitectureEdge`。
- 把示意性的矩阵、加号、乘号当作已从源码证明的运算。
- 让模板编辑直接生成或删除源码结构。
- 以原型坐标、节点数组顺序或截图位置作为匹配依据。

Pattern Pack 的匹配、拒绝和 Evidence 必须继续写入 receipt/review 流程。视觉模板缺失时回退为普通 glyph，不影响 Exact IR、PublicationView 或基础场景生成。

## 11. 正式交互流程

### 11.1 节点拖动

```text
pointerdown
  -> capture scene revision + affected edge IDs + port/portal locks
pointermove
  -> requestAnimationFrame
  -> DOM node transform
  -> TS local route preview for affected edges only
pointerup
  -> VisualPatch(set-position) inside PatchBatch
  -> POST /api/patch-batch
  -> CanvasDocument validation (source_digest unchanged)
  -> Python atomic-v1 rebuild
  -> return authoritative VisualScene + RoutingReceipt summary
  -> replace preview and update history
```

若 scene revision 已变化，前端丢弃旧 gesture 并从最新 scene 重试或提示冲突，不提交基于旧坐标的 patch。

### 11.2 展开与收起

```text
set-collapse patch
  -> compile expanded_node_ids
  -> rebuild PublicationView/frontier
  -> rebuild RoutingGraph projection
  -> retain canonical selection identity
  -> route deepest visible endpoints at every depth
  -> return VisualScene
```

展开状态只改变 view/frontier，不改变 Architecture IR。历史中的 undo/redo 以整个 `PatchBatch` 为单位。

### 11.3 路由手工调整

`set-route-hint` 只能表达视觉约束，例如 preferred side、waypoint、corridor、locked segment。它不能改变 source/target canonical port，也不能把一条边连接到新的模型节点。

### 11.4 结构编辑

增加、删除或重连模型边仍执行：

```text
EditIntent / ProposedConnection
  -> compatibility proof
  -> SourceTransaction prepare
  -> isolated verification
  -> GraphDelta review
  -> explicit commit
  -> re-analysis
  -> new IR/View/Scene
```

路由器只消费新 IR，不参与源码写入。

## 12. Feature Flag 与运行模式

新增明确的服务端配置，而不是只在前端隐藏 UI：

```text
ARCHCANVAS_ROUTING_ENGINE=legacy|shadow|atomic-v1
ARCHCANVAS_ROUTING_SHADOW_SAMPLE_RATE=0.0..1.0
```

模式语义：

| 模式 | 用户可见输出 | 新内核行为 |
|---|---|---|
| `legacy` | 旧路由 | 不运行，最低风险回退 |
| `shadow` | 旧路由 | 后台生成新 route、比较 metrics/digest，不改变 scene |
| `atomic-v1` | 新路由 | 新内核失败时按策略回退并产生诊断 |

服务端在 workspace/session capability 中返回实际模式和 engine version。前端不得通过 query string 在生产环境越权切换；开发构建可提供诊断开关。

回退粒度：

- **edge fallback**：单边缺少足够端口信息，但其余场景仍可安全使用新路由。
- **scene fallback**：投影不完整、存在 orphan edge、digest 失败或核心正确性指标非零。
- **deployment rollback**：将环境配置切回 `legacy`，无需迁移或丢弃 `CanvasDocument`。

回退不得吞掉合同错误。IR/View 身份不一致应作为失败暴露；只有已登记、可解释的不支持场景可以回退。

## 13. 分阶段实现计划

路由内核和视觉模板是两条并行工作流。路由阶段继续使用 Phase 0--7；视觉模板使用 Track V0--V4，并在 Phase 4/5 汇合：

| 视觉阶段 | 工作内容 | 依赖 | 汇合点 |
|---|---|---|---|
| V0 | 清点原型图例，拆分 atomic/compound/schematic，建立来源与测试 inventory | Phase 0 | baseline manifest |
| V1 | 实现 `GlyphResolver` 和首批原子图元，不改变结构 | 无 | 可独立接入 legacy scene |
| V2 | 增加 template/capture/binding schema 和 matcher，不实例化 UI | 正式 IR/Evidence | Phase 2 schema/provenance |
| V3 | 以 Attention 打通 exact/opaque/schematic、展开和路由 | V2 + Phase 2/3 | Phase 4 前端交互 |
| V4 | 迁移其余模板、共享渲染策略与导出 provenance | V3 | Phase 5/6 验收 |

V1 可以先行，因为原子 glyph 不创建结构。V2 之后的复合模板必须等待 IR 驱动投影合同稳定。任何视觉阶段均不得用硬编码详情图绕开 Phase 2 的 canonical edge/port provenance。

### Phase 0：冻结基线与资产清点

代码变化：

- 冻结 `studio/prototypes/scene-visual-lab` 的算法版本和案例清单。
- 给 26 类拓扑、展开状态和已知缺陷截图建立稳定 fixture ID。
- 将原型图例标记为 atomic、compound 或 schematic，并记录对应的 IR fixture 能力。
- 输出 legacy 与原型的 route metrics、SVG 和 JSON baseline。
- 在 CI 中补跑 `npm run prototype:build`，直到正式 fixtures 完成迁移。

交付物：baseline manifest、fixture inventory、算法版本、已知差异列表。

退出条件：

- 同一 commit 可重复生成相同案例清单与 digest。
- 记录所有测试命令和未运行门禁。
- 原型生产代码不再承担正式功能开发。

### Phase 1：建立纯 Python 路由内核

代码变化：

- 新增 `routing_models.py`、`routing_kernel.py`、`routing_metrics.py`、`routing_digest.py`。
- 将原型的端口候选、避障、正交简化、共享线段惩罚和指标转写为无 UI 依赖的纯函数。
- 暂不接入 `build_scene()`；使用手写 `RoutingGraph` fixture 测试。

测试：

- 路径正交、端点在节点边界、障碍净距、圆形中轴吸附。
- fanout/fanin、残差、反馈、反向边、密集端口、相邻容器。
- 输入顺序随机化后的确定性 property test。
- 非法值、重复 ID、缺失端口和不可路由场景的结构化失败。

退出条件：所有正确性硬指标为零；相同输入的 route digest 完全一致；尚未改变正式 Studio 输出。

### Phase 2：实现 IR/View 适配与自底向上投影

代码变化：

- 新增 `routing_graph.py` 和 `routing_projection.py`。
- 从 `ArchitectureIR`、Evidence、Hierarchy、View 构建 routing graph。
- 补充 `SceneEdge` 的端口、Evidence、portal 和 digest 字段。
- 增加 `VisualTemplateBinding`、capture/relation constraint 和 binding digest schema，但保持模板输出不可执行。
- 更新 schema exporter、协议测试和 TS 类型。

测试：

- 每条 visible edge 的 canonical/evidence provenance 完整。
- 每条 atomic edge 在任意展开状态下恰好被隐藏或投影一次。
- 任意深度展开后，外部边连接到最深可见真实端点。
- 折叠再展开不改变原子身份、portal order 和 source digest。
- Q/K/V 等不同 semantic channel 不错误收束。
- exact binding 的全部 node/edge/port slot 可追溯且不会改变 Exact IR digest。

退出条件：不读取 `DetailPrimitive.flow` 或矩形几何来推断语义；所有 adapter 输出都能追溯到正式 IR。

### Phase 3：Shadow 接入正式 scene build

代码变化：

- 在 `layout.build_scene()` 的边路由阶段接入 `RoutingEngine` facade。
- `legacy` 维持原路径；`shadow` 同时计算 atomic-v1，但只返回旧 scene。
- 在开发诊断 API/日志中输出 `RoutingReceipt` 和逐指标差异。
- `_relayout_compound_scene()` 也通过同一 facade 路由，避免候选布局绕过新内核。

比较维度：

- orphan/detached endpoint
- obstacle/border intersection
- crossing/bend/length
- semantic overlap
- build time 和内存
- canonical/evidence/source digest invariance

退出条件：真实模型 corpus 中无 provenance 丢失或硬错误；性能未超过预算；任何异常均可定位到 edge + reason code。

### Phase 4：正式前端预览接入

代码变化：

- 新增 `scene-routing-preview.ts`，接管 `previewEdgePoints()` 的策略部分。
- 在 pointer down 建立 gesture route lock；pointer move 只更新受影响节点和边 DOM。
- `scene-graphics.tsx` 补全正式 `SceneEdge` 字段。
- 接入通用 atomic glyph 和 Attention template instance；不在 React 中重新匹配模板。
- `main.tsx` 只负责协调 gesture、patch 和 scene replacement，逐步把 canvas 交互移到独立 hook/component。

测试：

- Playwright 覆盖拖动、连续拖动、取消、展开、收起、undo/redo、reload。
- TS/Python fixture 的端口和 portal signature 一致。
- 拖动期间无无意义箭头、端点脱离、整图 React commit 或端口抽搐。
- pointer up 后 preview 被权威 scene 替换。
- exact 模板内部节点可选择、移动、展开并查看 canonical/Evidence；opaque/schematic 不冒充 exact。

退出条件：`atomic-v1` 可在开发和测试环境交互使用；关闭 flag 后行为恢复 legacy。

### Phase 5：统一交互与导出几何

代码变化：

- publication renderer 只使用 `SceneEdge.points`、label anchor 和样式字段。
- React graphic 同样只使用 scene primitive，不再含独立的最终路由逻辑。
- 增加 interactive scene 与导出输入的 `route_digest` 对比。
- 把 glyph、marker、label 和 palette 常量收敛到共享 policy。
- 导出记录 template ID/version/digest、binding ID 和 fidelity；schematic 图层保持可辨识。

退出条件：同一 scene 的 React 与 SVG 导出端点、portal、折线和标签语义一致；导出不调用 route kernel。

### Phase 6：真实模型验收与逐步放量

至少覆盖：

- Autoformer
- PatchTST
- iTransformer
- TimeMixer
- 一个未参与内核开发的 holdout 模型
- 包含多级容器、fanout/fanin、残差、反馈、共享参数和条件流的合成模型

放量顺序：本地开发 -> CI fixtures -> opt-in workspace -> 默认新建 workspace -> 全量默认。每一步保留至少一个稳定观察窗口和一键 `legacy` 回退。

退出条件：正确性、视觉、交互、性能门禁全部通过；无未解释 fallback；用户文档和诊断信息完整。

### Phase 7：删除旧路由

只有满足以下条件才删除 legacy：

- `atomic-v1` 已跨至少两个发布周期稳定运行。
- 所有正式 acceptance fixture 已迁移。
- 无活跃 workspace 依赖 legacy 专有 route hint。
- rollback 演练完成，旧 `CanvasDocument` 可无损重建。
- 维护者明确批准删除 PR。

删除前不复用 `legacy` 名称承载新算法，避免配置含义漂移。

## 14. 测试矩阵与 CI 门禁

### 14.1 单元与属性测试

- adapter：canonical/view/scene/port 身份映射。
- projection：每条 atomic edge 覆盖一次，任意深度 frontier。
- portal：跨层连续、稳定排序、收束可逆。
- router：正交、避障、净距、端口容量、标签锚点。
- digest：输入顺序无关、浮点量化稳定、策略版本敏感。
- metrics：每个违规都由最小 fixture 单独触发。

### 14.2 合同测试

- `source_digest` 在所有 VisualPatch 后不变。
- Scene 新字段 schema round-trip。
- 旧 scene/document 可读，新 scene 写出新 minor version。
- route hint 不能更改 canonical source/target。
- 缺失 Evidence/port 不会被几何推断补齐。

### 14.3 集成测试

- `PublicationView -> RoutingGraph -> VisualScene -> SVG` 全链路。
- collapsed、fully expanded、单支展开、混合深度展开。
- force-directed、radial、orthogonal 等正式 layout candidate 重新路由。
- PatchBatch、undo/redo、reload persistence。
- 路由失败时 scene/edge fallback 和 receipt。

### 14.4 浏览器与视觉回归

Playwright 截图至少使用 desktop 和窄 viewport，检查：

- 箭头与节点边框不重合。
- arrowhead 不遮蔽末端线段或汇合语义。
- 多分支在汇聚前保持可辨识通道。
- 标签横向/纵向策略符合边方向且不遮挡节点。
- 深层子模块出口直接连接外部目标。
- 移动、展开和缩放期间无重叠 UI 或空白画布。

像素回归只作为视觉漂移告警；端点、provenance、障碍相交等结构断言才是正确性门禁。

### 14.5 视觉模板测试

每个 `VisualTemplateManifest` 都必须通过：

- positive：完整 fixture 产生预期 template/binding/fidelity。
- negative：结构相近但关键数据流不同的模型不得误匹配。
- mutation：删除或替换一个 required node/edge/port 后必须降级或拒绝。
- ambiguity：存在多个等价 assignment 时不得随意选择。
- digest invariance：匹配和实例化前后 Exact IR/source digest 不变。
- slot coverage：required slot cardinality 和 edge endpoint 一致。
- collapsed/expanded：折叠、部分展开、完全展开不丢失 binding identity。
- opaque：单一框架模块调用不产生虚构内部 canonical nodes。
- schematic：解释图层不进入 routing edge coverage、GraphDelta 和搜索身份。
- holdout：未参与模板开发的模型保持 generic 且 publication/geometry 仍通过。
- renderer parity：交互场景和导出记录相同 template/binding digest。

### 14.6 CI 调整

目标 CI 增加：

```text
python -m pytest tests/test_routing_*.py tests/test_visual_templates.py tests/test_publication.py tests/test_studio.py
python tools/export_schemas.py --check
python tools/export_routing_policy.py --check
npm test
npm run build
npm run prototype:build      # Phase 0--2 临时保留
playwright routing smoke     # Phase 4 起
```

任何未安装或未运行的可选视觉门禁必须标记为 skipped/unsupported，不能显示 passed。

## 15. 性能预算

以下为初始工程预算，Phase 0 基准后可调整，但调整必须附基准数据：

| 场景 | 初始预算 |
|---|---|
| 典型场景 pointer preview | P95 < 16 ms/frame |
| 1,000 节点后端权威重路由 | P95 < 250 ms |
| 5,000 节点后端权威重路由 | P95 < 1 s，允许 LOD |
| 10,000 节点 overview | 必须启用 LOD、标签抑制和可见区域裁剪 |
| 无输入变化重复构建 | route digest 100% 相同 |
| pointer move React 更新 | 不超过受影响子图；节点移动优先 DOM preview |

基准必须分别记录 adapter、projection、route、validation、serialization 和 browser paint，不能只记录总耗时。压力测试要包含高 fanout、深层嵌套和密集双向边，不能只使用均匀 DAG。

## 16. 可观测性与诊断

开发诊断面板或下载包应提供：

- engine/version/mode
- input/route digest
- scene、node、edge、portal 数量
- route 分段耗时
- 硬错误与 fallback reason code
- metrics 汇总及最差的若干 edge ID
- shadow 模式中新旧算法差值

建议 reason code：

```text
missing-canonical-port
ambiguous-visible-endpoint
invalid-containment-chain
no-obstacle-free-route
route-hint-conflict
portal-capacity-exceeded
unsupported-edge-relation
non-deterministic-output
```

诊断只记录标识符、指标和有限上下文，不记录用户源码正文。正常生产日志不输出完整 scene JSON。

## 17. 数据迁移与兼容性

1. 新增 scene 字段采用 additive minor schema 迁移。
2. `CanvasDocument` 不持久化自动生成的 points，因此旧文档可用新引擎重新构建。
3. 已有 `set-route-hint` 在 adapter 中转换；无法转换的 hint 明确诊断并回退，不能静默丢弃。
4. undo/redo 继续存 patch batch，不存整个路由图。
5. route digest 包含 engine version，算法升级不会与旧结果误判相同。
6. 缓存键至少包含 architecture/view/spec/frontier/canvas patch/engine policy digest。
7. 切换回 legacy 不删除新字段和历史；legacy renderer 忽略它不认识的可选元数据。

## 18. 风险与控制

| 风险 | 影响 | 控制措施 |
|---|---|---|
| Python 与 TS 路由漂移 | 拖动结束后路径跳变 | Python 权威、共享 fixtures、gesture lock、短过渡 |
| IR 端口信息不足 | 无法直连真实子模块 | 明确 fallback，不用几何伪造；推动 analyzer 补证据 |
| 深层展开导致组合爆炸 | 路由耗时和 DOM 增长 | frontier 增量、受影响子图、LOD、缓存 |
| 收束错误合并语义边 | Q/K/V 或条件流含义丢失 | 严格 aggregation key、canonical edge coverage test |
| 新算法改变用户空间记忆 | 展开/拖动体验不稳定 | 稳定 IDs、增量布局、previous-route displacement penalty |
| 两套 renderer 视觉漂移 | 导出与画布不同 | 同一 VisualScene、共享 style policy、route digest |
| `main.tsx` 继续膨胀 | 后续维护困难 | Phase 4 只抽 canvas interaction hook/component，避免大爆炸重写 |
| fallback 掩盖合同错误 | 长期带病运行 | 区分 unsupported 与 invalid；invalid 阻断并告警 |
| 模板名称误匹配 | 展示不存在的模型内部结构 | 名称只作弱提示；required capture 必须由结构和数据流证明 |
| 模板 required slot 不完整 | 图例语义看似完整但实际缺边 | cardinality/endpoint validation；降级 opaque/generic |
| schematic 被误认为 exact | 用户错误理解或错误编辑源码 | 独立 annotation layer、显式 fidelity、禁止进入事务和搜索身份 |
| 模板升级导致缓存错配 | 旧布局套用新槽位 | template/binding digest 进入 scene cache key 和导出 provenance |

## 19. PR 切分建议

每个 PR 保持可独立回滚：

1. `routing-fixtures-baseline`：基线、manifest、CI 原型构建。
2. `visual-asset-inventory`：atomic/compound/schematic 分类和 IR fixture 能力清单。
3. `routing-models-metrics`：内部模型、digest、metrics，无产品接入。
4. `routing-kernel-python`：纯函数 Python router 和压力 fixtures。
5. `routing-ir-adapter`：IR/View adapter、projection、portal chain。
6. `visual-atomic-glyphs`：`GlyphResolver` 和原子图元，不改变场景结构。
7. `visual-template-contract-v1`：template、capture、binding schema 和 digest。
8. `pattern-role-binding`：确定性子图 capture、关系约束、ambiguity 和 receipt。
9. `scene-edge-contract-v1.1`：core schema、TS type、schema export。
10. `routing-shadow-mode`：facade、配置、receipt、比较报告。
11. `visual-template-attention`：首个 exact/opaque/schematic 端到端模板。
12. `routing-preview-ts`：前端局部预览与 cross-language fixtures。
13. `routing-playwright-visual`：交互、模板展开和像素回归。
14. `routing-atomic-opt-in`：opt-in 正式输出。
15. `scene-render-policy`：画布与导出视觉描述收敛。
16. `visual-template-catalog`：VAE、RNN、MoE、CNN 和时序模型模板。
17. `routing-default-on`：真实模型验收后改默认值。
18. `routing-legacy-removal`：稳定窗口后单独删除。

合同 PR 与算法 PR 分开，以便 schema review 不被大量几何实现掩盖。

## 20. Definition of Done

受控集成完成必须同时满足：

- 正式路由完全由 Exact IR/Evidence/View 驱动，无几何反推语义。
- 任意层级展开时，外部边连接最深可见真实子模块；折叠时可确定性收束。
- 每条可见边能追溯到 canonical edge、port 和 Evidence。
- exact template 的每个 required slot 都绑定真实 canonical entity，模板不创建执行语义。
- opaque 和 schematic 在 UI、导出与 Inspector 中均不会被表达为 exact。
- 原子 glyph、复合模板和用户视觉 override 遵循统一且确定的优先级。
- template/binding digest 进入缓存、导出 provenance 和 stale validation。
- 所有视觉修改保持 `source_digest` 不变，结构编辑仍走 SourceTransaction。
- Python 权威路由、TS 预览和导出通过共同 fixtures。
- 26 类压力拓扑、真实四类时序模型和 holdout 模型通过结构、视觉、交互测试。
- 性能预算有实际基准数据并进入 CI/发布门禁。
- shadow comparison 无未解释的正确性回归。
- feature flag、scene fallback 和部署回滚均完成演练。
- 连续两个发布周期稳定后，才允许删除 legacy 路由。

## 21. 推荐的首个实施里程碑

第一个里程碑应止于 Phase 2，不触碰用户可见行为：

1. 固化原型 fixture 和 baseline。
2. 建立 Python `RoutingGraph`、route kernel、metrics 和 digest。
3. 完成 `ArchitectureIR + PublicationView -> RoutingGraph` 适配。
4. 建立 `VisualTemplateManifest`、capture 和 `VisualTemplateBinding` 合同，但暂不启用产品模板。
5. 用正式 IR fixture 证明任意层级的原子出口直连、折叠收束和 provenance 完整。
6. 用 Attention fixture 证明 exact binding、opaque fallback 和 ambiguity rejection。
7. 形成 shadow mode 所需的输入输出合同。

这个边界可以先证明“算法已脱离原型数据模型，并遵守 ArchCanvas 事实合同”，再承担正式 UI 和持久化风险。未达到该里程碑前，不应把 `atomic-bottom-up` 设为正式 Studio 默认路由。
