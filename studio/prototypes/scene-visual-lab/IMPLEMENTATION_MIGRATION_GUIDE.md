# 基于 Scene Visual Lab 副本重建主程序实施指南

> 文档性质：后续实现的规范性方案，不是现有完成状态说明。
>
> 原型基线：`studio/prototypes/scene-visual-lab/`
>
> 新主程序目标目录：`studio/src/scene-studio/`
>
> 旧主程序前端：`studio/src/app/`、`studio/src/main-view/`、`studio/src/visual-kernel/` 等，仅作为功能和协议参考，不再作为新 UI 的实现基座。
>
> 后端基线：`src/archcanvas_studio/`、`src/archcanvas_core/`、`src/archcanvas_python/` 及现有 schemas，继续复用并按本指南扩展。
>
> 代码快照：2026-10-01 当前工作树。

## 1. 最终决策

本轮重建采用以下不可逆转的方向性决策：

1. **主程序前端从最小原型的副本继续生长。** 不再把原型的视觉能力迁入当前臃肿主程序，也不继续维护两套画布和两套视觉状态。
2. **原始最小原型永久保留。** `studio/prototypes/scene-visual-lab/` 是交互基线、视觉回归基线和算法参考，后续功能只能添加到 `studio/src/scene-studio/`。
3. **舍弃的是旧前端实现，不是已验证的后端能力。** 当前 Python 分析、IR、证据、项目、任务、事务和验证服务继续作为新主程序的后端；旧 `StudioApp`、`ArchitectureCanvas`、`visual-kernel` 不作为新画布依赖。
4. **四个 Transformer 场景合并为两份源码。** 当前的“经典横向、经典论文式、Tensor2Tensor 横向、Tensor2Tensor 论文式”必须改成“经典源码、Tensor2Tensor 源码”两个 `SourceProject`；每个项目可以选择标准流程图、论文级视图及其他视图模板。
5. **产品目标是通用的自动源码到多视图链路，不是两个 Transformer 演示器。** analyzer、registry binding、hierarchy、template selection、layout 和 router 必须根据源码事实与声明式契约工作；禁止按项目名、路径、归档摘要或 fixture ID 写分支，也禁止为每个模型手写节点、坐标和连线。
6. **两个 Transformer 是硬性黄金标准，不是产品边界。** 通用化、性能优化、`tier_a` 兼容或代码生成改动之后，两份权威源码生成的标准流程图和论文级视图仍必须与最小原型在视觉展示上、层级、构图、图例、路由、展开交互和性能上几乎一致。
7. **语义只保存一次，视图可以有多份。** 节点、端口、边、参数、父子关系和证据来自同一份 Exact Architecture IR；坐标、展开、颜色、路由和模板属于派生视图。
8. **画布上的增删改和连线可以修改既有源码或生成新的源码项目，但必须经过事务。** 视觉手势先生成语义意图，再根据显式 source strategy 进入既有源码 lowering 或结构化 codegen，完成重新分析、预期/实际 Graph Delta 对比、验证和人工提交；前端不得直接写工作区源码。
9. **先达到功能和交互等价，再切换入口。** 从第一天起停止扩展旧前端，但在新程序通过切换门禁前，不物理删除旧代码，避免失去对照和回滚能力。

“完全保留最小原型的所有交互体验”在本文中不是视觉相似，而是第 3.1 节列出的行为必须逐项通过自动化和浏览器验收。

## 2. 边界与术语

本文使用以下三个目录角色：

| 角色 | 目录 | 规则 |
|---|---|---|
| 原型原件 | `studio/prototypes/scene-visual-lab/` | 只修原型自身缺陷；不得在此接 API、源码事务或主程序壳层 |
| 原型副本/新主程序 | `studio/src/scene-studio/` | 所有新功能的唯一前端落点 |
| 旧主程序前端 | `studio/src/app/`、`main-view/`、`visual-kernel/`、`inspector/`、`shell/` | 只读取功能、协议与测试证据；禁止直接组合回新画布 |

本文中的关键词：

- **Source Project**：一份可分析的源码工程及入口点，不等于一个视图。
- **Exact Architecture IR**：由静态分析和可选运行时证据生成的语义事实层。
- **View Preset**：把同一份 IR 投影为某种阅读目的的规则，例如标准流程图或论文级视图。
- **Scene**：可交给原型 SVG 画布渲染的派生 DTO。
- **Visual Patch**：只改坐标、尺寸、展开、相机、样式和标签展示的操作。
- **Semantic Intent**：希望改变模型结构或参数的用户意图。
- **Source Transaction**：在隔离副本中修改源码并完成重分析、验证、评审和提交的事务。
- **Canonical ID**：语义对象的稳定身份。
- **Lineage ID**：源码修改和重分析前后用于匹配同一对象的身份。
- **Slot ID**：视图模板内部稳定图元或端口槽位的身份。
- **Generic Source-to-View Pipeline**：不识别具体项目身份，只根据 SourceCorpus、Exact IR、registry contract、evidence 和 View Preset 自动生成场景的标准链路。
- **Transformer Golden Baseline**：由两份指定权威归档生成的标准/论文视图及最小原型对应场景，是不可因通用化而放宽的硬回归基准。
- **Tier A Matrix**：`fixtures/tier_a/` 下用于证明通用性的多文件、多输入、多分支、多尺度模型集合；它扩展覆盖面，但不能替代 Transformer Golden Baseline。

## 3. 现有事实基线

### 3.1 最小原型必须完整保留的体验

新主程序必须保留原型的以下行为和反馈节奏：

- 无限画布式平移、滚轮定点缩放、按钮缩放、适合视图；
- 节点选择、边选择、空白取消选择；
- 节点实时拖动预览、释放后提交，允许负坐标和向左拖动；
- 节点尺寸调整；
- 父模块展开/收起、全部展开/全部收起；
- 子模块递归内联展开、拖动、局部连线实时吸附、位置复位；
- `atomic-bottom-up` 原子收束和 `recursive` 逐层路由 A/B 切换；
- `direct`、`orthogonal`、`channel`、`curve`、`adaptive` 五种布线；
- `semantic`、`technical`、`compact` 三种节点视觉；
- `plain`、`plate`、`endpoint` 三种边标签；
- 节点新增、节点删除、连线创建、连线删除；
- 节点和连线检查器；
- 撤销、重做、场景复位；
- 路由质量指标；
- SVG/JSON 方案导出；
- 屏幕渲染与静态导出一致；
- 当前 30 个场景及其 1350 个基础视觉组合继续作为回归语料。

这些交互的输入设备语义、拖动阈值、展开后增量位移、选择反馈和收起后确定性恢复都属于兼容契约。不得以引入新画布框架为由改变。

### 3.2 最小原型当前缺少的能力

原型当前只有内存 `LabScene`，四个 Transformer 场景是手写的。它没有：

- 项目打开、入口点发现和环境选择；
- Python 源码捕获、AST/CST、符号解析和 Exact IR；
- canonical node、named port、tensor、evidence 和 source anchor；
- 源码/模块双导航、统一搜索和诊断；
- 分析任务、取消、进度和 stale generation；
- 参数、结构、自由源码和拓扑草稿事务；
- 验证、Graph Delta、提交、回滚和重分析；
- 模块契约维护和 registry；
- 可编辑源码工作区；
- PNG/PDF 发布导出。

因此，不能通过继续扩充 `LabNode` 和 `LabEdge` 把这些事实塞进原型 DTO。必须在 `LabScene` 之前增加正式语义层。

### 3.3 当前主程序需要保留的功能

以下能力已有源码和测试证据，应迁入新壳层或直接复用后端：

| 能力 | 当前证据 | 新程序处理方式 |
|---|---|---|
| 打开工程、目录浏览、环境和入口选择 | `project-actions.ts`、`project.py`、`server.py` | 保留 API，重做原型风格入口 UI |
| 异步分析、进度、取消、generation 隔离 | `jobs.ts`、`job-actions.ts`、`server.py` | 保留协议和后端，重做轻量状态适配器 |
| 模块/源码双导航 | `navigation.py`、`tree.ts` | 保留数据，作为可折叠辅助面板，不改变画布交互 |
| 搜索 node/tensor/port/evidence/diagnostic | `operations.py`、`/api/search` | 保留 API，结果映射到原型选择状态 |
| 证据、源码定位和诊断 | `StudioState`、`/api/source-excerpt` | 保留，显示在检查器和源码面板 |
| 视觉 patch、批处理、undo/redo | `document.py`、`/api/patch*` | 保留服务端持久化，前端改用原型 reducer 手感 |
| 对齐、分布、固定和布局偏好 | `ArchitectureCanvas.tsx`、`operations.py` | 以原型命令模式重新实现 |
| 参数和有界结构事务 | `bundle.py`、事务 schemas | 原样接入语义命令层 |
| 拓扑草稿、增删节点/边和删除影响预览 | draft/proposal endpoints | 改成画布手势的正式落点 |
| Source Workspace | `SourceWorkspacePanel.tsx`、`bundle.py` | 使用 CodeMirror 6 重做，复用 API |
| 验证配置和结果 | `/api/validation-runs` | 保留后端，压缩成状态栏/抽屉 |
| SVG/PNG/PDF 导出 | 当前主视图和 publication export | 统一从同一派生 scene 导出 |
| Registry、Shape、成本和代码预览 | `module-registry/`、`prototype-graph/`、`codegen/` | 在模型编辑模式按需加载 |
| 模块契约维护 | contract endpoints/dialog | P1 接入；不阻塞最先落地的 P0 纵向切片 |
| 主题、语言、面板大小 | 旧 shell | 只迁用户价值，不复制旧 shell 结构 |

### 3.4 明确舍弃的主程序实现

以下内容不能进入新主程序运行依赖：

- 旧 `StudioApp.tsx` 的单体组件和其大量互相牵连的本地 state；
- 旧 `ArchitectureCanvas.tsx`；
- 旧 `visual-kernel` 作为第二画布内核；
- `FormalStudioState -> KernelDocument -> KernelRenderScene` 的前端专用重复投影链；
- 旧 shell 的固定四面板布局作为页面骨架；
- 通过 label 正则推断模块类型或子模板；
- 通过项目名、路径、归档 digest、fixture ID 或入口类名选择专用场景构造器；
- 为 Autoformer、iTransformer、PatchTST、TimeMixer 或任一测试项目手写节点表、父子关系、坐标和连线；
- 通过数组下标生成可持久化图元 ID；
- 同一 Transformer 为每种画法复制一份语义节点和边；
- 把视觉撤销和源码事务放进同一个历史栈；
- 让前端在没有验证收据时直接写源码。

可以复制小型、纯函数、已测试且没有旧画布类型依赖的代码，但必须迁入新目录并重新命名所有权，不能从旧目录长期 import。

## 4. 技术选型

### 4.1 前端和画布

采用：

- React 18、TypeScript、Vite；
- 原型现有的手写 SVG 渲染；
- 原型现有的 pointer gesture、camera、detail layout、atomic projection 和 adaptive router；
- Lucide 图标；
- CSS variables 管理主题与论文/工程视觉参数。

不采用 React Flow/xyflow 作为新画布。原因不是其能力不足，而是更换画布会改变节点命中、拖动、递归展开、跨层门户、绘制顺序和导出链路，无法满足“完整保留原型交互”的首要约束。

### 4.2 源码分析与改写

采用现有 v2 前端：

```text
ProjectManifest
  -> immutable SourceCorpus
  -> LibCST repository frontend
  -> Python Semantic Graph
  -> registry/port binding
  -> Exact Architecture IR v2
  -> evidence + diagnostics + hierarchy
```

具体约束：

- **LibCST 是 Python 保格式读取和回写的权威。** 官方文档说明它同时保留空白、注释和语义化节点，可从修改后的 CST 重新打印源码。
- **Pyright Type Server 是可选解析证据，不是事实源。** 只用于跨文件类型/符号候选；超时、缺失或 snapshot 不一致时必须降级，不得阻断基础分析。
- **Tree-sitter 只用于可选的编辑器即时语法反馈。** 官方增量解析接口可以在文本编辑后复用旧树，但它不替代 LibCST 的 source anchor、事务改写和最终验证。
- **不得通过 import 用户工程获得静态图。** 运行时 trace 仍是单独、显式授权的隔离能力。
- **Pattern Pack 在 Exact IR 之后执行。** 它只增加 annotation/template binding，不能改变 canonical graph。

### 4.3 源码编辑器

采用 CodeMirror 6，不继续使用 `<textarea>`，也不引入 Monaco。

选择依据：

- CodeMirror 的 document/state 是不可变值，修改通过 transaction 表达，和本项目的 staged buffer/transaction 边界一致；
- 模块化，可只装 Python、diff、search、history 和 diagnostic 所需扩展；
- viewport 渲染适合中大型源码；
- `ChangeSet.mapPos()` 可在本地文本变化时维护 source anchor 装饰；
- 相比 Monaco 体积和 worker 体系更轻，足以满足当前本地 Studio。

CodeMirror 的 undo 只作用于尚未提交的当前 buffer；Source Transaction 的提交、撤销和回滚仍由后端负责，两者不能混为一个历史。

### 4.4 自动布局

默认继续使用原型布局和路由：

- 节点展开和拖动必须走现有增量算法，以保护用户空间记忆；
- paper preset 继续使用确定性的双列/层级规则；
- adaptive router 继续负责最终边路径；
- 用户手工移动后不得被后台自动布局覆盖。

ELK Layered 只作为 P2 的显式“重新布局”命令候选，并放在 Web Worker 中。官方能力覆盖固定端口、正交边、compound graph 和跨层边，适合大型通用 DAG 的一次性排布；它不能在每次 render、展开或拖动时运行，也不能替代原型的递归详情布局和最终路由。

### 4.5 后端通信

继续使用当前本地 HTTP API 和 JSON schema，不在本轮引入 Electron/Tauri、GraphQL 或全局状态框架。新前端建立一层小型 typed client 和一个 reducer/store 即可。

## 5. 目标架构

### 5.1 唯一主链路

```text
源码工程/归档成员
  -> Source Project + immutable SourceCorpus
  -> Python Semantic Graph + Exact Architecture IR
  -> evidence / hierarchy / diagnostics / registry bindings
  -> ViewProjector(IR, ViewPreset, VisualState)
  -> SourceBackedScene
  -> 原型 expansion + detail layout + atomic projection + routing
  -> 同一个 SVG scene renderer
  -> 交互画布 / SVG / PNG / PDF / JSON
```

反向修改链路：

```text
画布手势
  -> SemanticIntent
  -> capability check + named-port validation
  -> preview overlay + expected Graph Delta
  -> isolated Source Transaction
  -> LibCST rewrite
  -> reparse + reanalyze
  -> observed Graph Delta + shape/type/test gates
  -> review
  -> commit
  -> 新 SourceCorpus/IR
  -> 依据 lineage ID 重投影视图
```

空白构图和源码生成链路：

```text
Registry palette + 视图增删改/连线
  -> PrototypeGraphDocument
  -> named-port / Shape / cost / control-region validation
  -> structured PyTorch Code IR + source map
  -> Generated Source Project transaction
  -> compile + 静态重分析 + 可选隔离运行
  -> review + materialize
  -> 作为 Source Project 回到正向读取链路
```

正向读取、既有源码修改和空白构图生成共享 registry、named port、Graph Delta 和 receipt 规则。生成项目物化后必须回到同一 SourceCorpus/Exact IR 链路；不得再创建独立的“原型语义图”和“正式语义图”。

### 5.2 四层状态所有权

| 层 | 权威数据 | 所有者 | 可否直接编辑 |
|---|---|---|---|
| Source | 文件内容、digest、source anchor、项目入口 | Python 后端 | 只能经 Source Transaction |
| Semantic | nodes、ports、edges、tensors、parameters、hierarchy、evidence | Exact Architecture IR | 不可由前端直接改 |
| Visual | preset、位置、尺寸、展开、样式、路由、相机、固定状态 | CanvasDocument/ViewDocument | 可用 Visual Patch |
| Ephemeral UI | hover、框选、拖动 preview、菜单、当前 tab | 浏览器组件 | 可直接改，不持久化 |

必须维持以下不变量：

```text
Visual Patch 不改变 source_digest 或 exact_ir_digest。
Semantic Intent 不携带 SVG 坐标。
切换 View Preset 不生成 Source Transaction。
Source Transaction 提交后必须产生新 source_digest。
重分析后的视觉状态只能按 canonical/lineage ID 迁移，不能按 label 猜测。
```

### 5.3 建议的前端核心类型

```ts
type ViewPresetId =
  | "engineering-flow"
  | "paper-publication"
  | "paper-transformer"
  | "module-hierarchy"
  | "source-call"
  | "tensor-dataflow"
  | "compact-overview";

interface SourceProjectRef {
  projectId: string;
  root: string;
  entrypoint: string;
  framework: "pytorch" | "keras" | "jax" | "onnx" | "auto";
  sourceSnapshotId: string;
  sourceCorpusDigest: string;
  generation: number;
}

interface ViewPreset {
  id: ViewPresetId;
  label: string;
  projection: "architecture" | "module" | "source" | "tensor";
  orientation: "left-to-right" | "top-to-bottom" | "bottom-to-top";
  layout:
    | "incremental-flow"
    | "publication-structural"
    | "paper-dual-lane"
    | "hierarchical"
    | "compact";
  hierarchyDepth: number | "expanded-frontier";
  templateProfile: "engineering" | "paper" | "technical";
  edgePolicy: "semantic" | "all" | "main-flow";
}

interface SourceBackedScene extends LabScene {
  sourceProjectId: string;
  architectureId: string;
  sourceDigest: string;
  exactIrDigest: string;
  presetId: ViewPresetId;
  bindings: Record<string, SceneBinding>;
}

interface SceneBinding {
  sceneId: string;
  canonicalNodeIds: string[];
  canonicalEdgeIds: string[];
  sourceAnchorIds: string[];
  evidenceIds: string[];
  portBindings: Record<string, string>;
  fidelity: "exact" | "schematic" | "opaque";
}
```

`LabNode`、`LabEdge` 仍是渲染输入，不承载完整参数 schema、源码文本或分析规则。`SourceBackedScene.bindings` 是场景对象与正式事实的桥梁。

### 5.4 稳定身份

禁止继续使用 `detail-node-${primitiveIndex}`。目标 ID 规则：

```text
canonical node: 由 Exact IR 生成
source anchor:   corpus digest + file + syntax lineage
view node:       preset id + hierarchy frontier + canonical set digest
template slot:   template id + semantic slot id
render primitive: binding id + slot id
visual override: view node/slot id + property
```

模板插入标题、改变颜色或调整图元顺序后，展开状态、拖动偏移、证据和源码定位必须仍指向原语义对象。

### 5.5 正式 Round-trip 一致性协议

“能够从源码生成图”和“能够从图修改源码”分别成立，不等于双向工程已经闭环。系统必须对三种往返路径生成机器可读的 `RoundTripConformanceReport`：

```text
A(Source S) = Exact IR I
project(I, Preset P, VisualState V) = Scene

apply(Intent E, Source S) = Source S'
delta(A(S), A(S')) == expectedDelta(E)

compile(Draft G) = Generated Source Gs
normalize(A(Gs)) == normalize(G)

NoOp(S) => sourceWrites == [] && digest(S) unchanged
```

其中 `normalize()` 只消除不影响模型语义的差异，例如代码格式、局部变量名、生成器临时 ID 和合法的语句排序；它不得消除节点/端口/边、父子关系、参数共享、Repeat/control region、Shape 约束、调用签名或 evidence-backed unresolved fact。规范化规则必须版本化并进入报告 digest，不能为了让测试通过临时放宽。

建议的报告最小结构为：

```ts
interface RoundTripConformanceReport {
  reportId: string;
  path: "source-view" | "intent-source" | "draft-source";
  baseSourceDigest?: string;
  resultSourceDigest?: string;
  baseExactIrDigest?: string;
  resultExactIrDigest: string;
  draftDigest?: string;
  normalizationRuleDigest: string;
  expectedDeltaDigest?: string;
  observedDeltaDigest?: string;
  semanticIsomorphism: "exact" | "equivalent" | "failed";
  sourceWrites: string[];
  diagnostics: Diagnostic[];
}
```

相同 SourceCorpus、analysis input manifest、adapter、registry、pattern pack 和 schema digest 必须产生相同 Exact IR 和规范化 scene digest。相同 `intentId + baseSourceDigest` 的重试必须返回同一个已存在事务或等价 receipt，不能重复应用修改。生成项目在物化并重新打开后必须到达语义 fixed point；第二次打印不得继续改变源码或 source map。

### 5.6 多证据仲裁和运行语义边界

Exact IR 的事实不能由最后到达的证据覆盖。按以下职责处理各类输入：

| 证据 | 能证明 | 不能证明 |
|---|---|---|
| SourceCorpus/LibCST | 定义、可能控制路径、源码层级、构造和调用位置 | 某个输入实际走过哪条路径 |
| registry/type/Shape rule | 已注册操作的端口和约束 | 未注册自定义操作的真实运行效果 |
| runtime trace/hooks | 固定环境、模式和输入 profile 下实际执行的调用与张量 | 未执行分支、全部动态 Shape、完整源码父子层级 |
| `torch.export`/JAXPR/ONNX graph | 对声明约束成立的规范化计算图和调用签名 | 原始源码模块层级；任意 Python 数据依赖控制流 |
| checkpoint/state | 参数、buffer、optimizer/state tree 的一个版本 | 源码结构与状态天然兼容 |

发生矛盾时必须生成现有 `DiscrepancyRecord`，记录 subject、各方 claim、evidence IDs、输入/环境 profile 和 resolution。runtime/export evidence 只能增加 executed/observed annotation 或把事实标为 conditional/unresolved，不能静默删除源码中未执行的合法分支，也不能把 export 内联后的扁平图反写成源码层级。

每个 runtime receipt 至少绑定：execution mode、构造参数、位置/关键字输入、动态 Shape 约束、dtype/device/backend、seed/PRNG、autocast、参数/state/checkpoint digest、adapter/environment digest 和路径覆盖。涉及 Dropout、BatchNorm、in-place op、tensor alias、hook、共享参数或状态更新时必须显式记录限制。

运行验证按 intent 声明 semantic oracle，而不是统一要求输出相等：

- 纯重构应比较输出容差、输入/参数梯度、buffer 变化和共享参数身份；
- 参数或结构有意变化时，检查 expected delta、输出契约及未受影响区域，不要求变化区域数值相等；
- 无法稳定重放、路径覆盖不足或 alias/mutation 未被 adapter 观测时标为 partial/unsupported，不得显示“完全验证”。

## 6. 通用多视图目标与 Transformer 黄金基准

### 6.1 从四场景改为两项目

当前四个场景：

```text
classic-transformer
paper-classic-transformer
tensor2tensor-transformer
paper-tensor2tensor-transformer
```

目标数据：

```text
source:classic-transformer
  -> preset:engineering-flow
  -> preset:paper-publication
  -> preset:module-hierarchy
  -> preset:source-call
  -> preset:tensor-dataflow

source:tensor2tensor-1.0.14
  -> preset:engineering-flow
  -> preset:paper-publication
  -> preset:module-hierarchy
  -> preset:source-call
  -> preset:tensor-dataflow
```

“场景选择器”在 source-backed 模式下变为两级选择：

1. 源码项目选择；
2. 视图模板选择。

用户切换模板时，source digest、IR digest、canonical selection 和 evidence 不变；只重新生成 scene，并恢复该 preset 自己的 camera、展开和 visual overrides。

### 6.2 两份源码的权威输入

经典 Transformer：

- 权威归档：`/home/fzg/PycharmProjects/ArchCanvas/Constraint relationship of architecture diagram/pytorch_transformer_original.zip`；
- 归档 SHA-256：`7b450cd08737e14b4e9ad33cb240a53be08bf5882986b3d43fa5988d644ae552`；
- 权威入口成员：`pytorch_transformer_original/transformer.py:Transformer`，`example.py` 只提供构造和输入示例；
- `references/SOURCE_TRACEABILITY.md` 必须更新为该归档成员的 member digest 和 source anchors，不能继续把其他同名实现当成权威；
- 自动测试使用仓库内可移植 fixture，例如 `tests/fixtures/frontend_v2/transformer_classic/` 和 `fixtures/tier_a/transformer/`；
- 完整视觉验收必须对权威源码生成不可变 SourceCorpus，不能用手写 `scenarios.ts` 代替。

Tensor2Tensor：

- 权威归档：`/home/fzg/PycharmProjects/ArchCanvas/Constraint relationship of architecture diagram/tensor2tensor-1.0.14.tar.gz`；
- 归档 SHA-256：`83dd1393fdceeeddd77922a36798b7200b979f1c00424b737498438157b8b82f`；
- 权威成员：`tensor2tensor-1.0.14/tensor2tensor/models/transformer.py` 及其静态可达本地依赖；
- 导入时由后端把允许成员物化到内容寻址、只读的 workspace snapshot；
- 记录归档 digest、成员 digest、许可证和 provenance；
- 不允许浏览器直接解包，也不允许静态分析阶段 import/执行该包。

绝对路径只用于当前机器的验收。可提交的示例 manifest 必须使用项目相对路径、归档 digest 或用户选择的项目根，不能把本机绝对路径写进产品配置。

### 6.3 共同语义、不同绑定

两份源码共享 Transformer 视觉语法，但参数和变体由证据决定：

| 语义轴 | Classic | Tensor2Tensor 1.0.14 |
|---|---|---|
| 输入准备 | token embedding + sinusoidal position | modality transform/flatten + timing signal |
| Encoder mask | boolean padding mask | additive attention bias |
| Decoder mask | padding + causal mask | lower-triangle bias |
| FFN | Linear -> activation -> Linear | `conv_hidden_relu` 语义 |
| 条件 | source/target mask | target-space embedding + attention bias |
| 输出共享 | target embedding/projection tying | modality/shared softmax 机制 |
| 顶层 API | 显式 Encoder/Decoder 类 | `prepare_encoder/decoder` + body helpers |

模板只能在证据满足 predicate 时显示对应 slot。无法证明的结构标为 `schematic` 或 `opaque`，不能为了匹配旧图补造 canonical node。

### 6.4 参数化 Transformer 模板

不得维护 `paper-transformer-encoder`、`transformer-encoder` 等两套语义模板。使用一套参数化模板：

```ts
interface TransformerTemplateParameters {
  family: "classic" | "tensor2tensor" | "generic";
  role: "encoder" | "decoder";
  orientation: "horizontal" | "vertical-bottom-up";
  layers: number | "symbolic";
  hiddenSize: number | "symbolic";
  heads: number | "symbolic";
  ffnSize: number | "symbolic";
  ffnKind: "linear" | "conv-hidden-relu" | "gated" | "opaque";
  maskKind: "boolean" | "additive-bias" | "none" | "unknown";
  normOrder: "pre" | "post" | "unknown";
  hasCrossAttention: boolean;
  tiedOutputEmbedding: boolean | "unknown";
}
```

其中只有 `orientation`、色调和展示密度来自 View Preset；其余字段必须来自 IR/evidence。`family` 是有证据的 Transformer 语义变体，不得由归档名、路径或项目 ID 赋值。模板输出稳定 slot：

```text
encoder.input
encoder.self_attention.query
encoder.self_attention.key
encoder.self_attention.value
encoder.self_attention.mask
encoder.residual_1
encoder.norm_1
encoder.ffn.expand
encoder.ffn.activation
encoder.ffn.contract
encoder.residual_2
encoder.norm_2
encoder.output

decoder.input
decoder.self_attention.mask
decoder.cross_attention.query
decoder.cross_attention.memory
decoder.cross_attention.memory_mask
decoder.ffn
decoder.output
```

外部边必须通过 named port/slot 进入 mask、memory 等真实位置，不能连接父框中心后再靠 label 解释。

### 6.5 各视图模板职责

| Preset | 用途 | 默认布局 | 显示内容 |
|---|---|---|---|
| `engineering-flow` | 标准流程图式调试 | 左到右、增量 flow | 调用、张量、mask/bias、端口和主要参数 |
| `paper-publication` | 通用论文级阅读/导出 | 由结构 profile 决定，默认底到顶紧凑层级 | 结构模块、重复层、共享权重、分支/合流和简化辅助调用 |
| `paper-transformer` | 旧原型兼容 alias | 解析到 `paper-publication + encoder-decoder-transformer`，不拥有独立 renderer | 仅供四个旧场景和 golden URL 兼容 |
| `module-hierarchy` | 看父子模块和复用 | 层级/树 | containment、重复实例、共享模块 |
| `source-call` | 从代码理解调用关系 | 上到下 | 文件、类、函数、调用、赋值、返回和源码锚点 |
| `tensor-dataflow` | shape/端口诊断 | 左到右 | tensor、producer/consumer、shape、dtype、mask/state |
| `compact-overview` | 大模型总览 | 压缩分层 | 只显示边界模块和主要流 |

P0 必须完成 `engineering-flow` 和 `paper-publication`；两个 Transformer 在论文级 preset 下必须解析到 encoder/decoder 双列 profile。其余 preset 在 P1 添加，但接口和状态结构从一开始支持任意数量，不能再把 `layout_profile` 限死为 `freeform | paper`。

### 6.6 通用自动化边界：不能把测试案例写进映射层

两个 Transformer 只定义输出质量，不定义实现捷径。正式链路必须对任意受支持 Source Project 执行同一组阶段：

```text
SourceCorpus
  -> Python Semantic Graph
  -> Exact Architecture IR
  -> parent/child + call/value/control evidence
  -> registry binding + optional semantic pattern annotations
  -> structural publication profile
  -> generic View Preset projector
  -> incremental layout + hierarchy/detail routing
  -> SourceBackedScene
```

允许的扩展点只有声明式、可审计的规则：module registry definition、source matcher、port contract、Shape/cost/codegen rule、pattern annotation 和 view-template predicate。它们必须以 symbol、调用、值流、端口、Shape 或 control-region evidence 为输入，输出 canonical annotation 或 template binding。

以下做法一律视为失败：

- `if projectId === "autoformer"`、按目录名/归档 digest/fixture ID 选择构图器；
- 看到类名后直接返回一份预制 `LabScene`；
- 在 pattern pack 中保存节点坐标、完整边表或展开后的详情树；
- 依赖 `SCENARIOS` 才能生成 source-backed view；
- 不认识模型时只显示一个根节点，隐藏已经能从源码证明的子模块和调用关系。

模型家族 pattern pack 可以提高语义名称和论文图例质量，但必须满足：关闭该 pack 后，通用管线仍能生成结构正确、可递归展开的标准流程图和论文级 fallback；pack 只能增加有 evidence 的 annotation/template binding，不能改写 canonical graph。把项目复制到新目录、修改文件名和非语义类名后，规范化结构与视图 digest 必须保持一致，source anchors 可以按新 corpus 正常换代。

父子模块关系按事实恢复：

- `ModuleInstance.parent_instance_id` 表达实例 containment；
- definition、instance 和 call site 分开，同一实例的多次调用不复制参数；
- Python owner scope、attribute assignment、`ModuleList`/容器索引和 control region 提供层级 evidence；
- functional 子图没有 module instance 时，以带 boundary ports 的 semantic group 表达，不能伪造 `nn.Module`；
- 展开节点从 canonical children 投影，父框包含、portal chain、atomic/recursive A/B 和收起恢复继续使用原型算法；
- 无专用 glyph/template 的已知节点使用通用 module/function/operator fallback，仍保留真实名称、端口、Shape、证据和源码定位。

通用论文级视图先从 IR 推导结构 profile，而不是模型名称：

```ts
interface PublicationStructureProfile {
  topology:
    | "encoder-decoder"
    | "single-stack"
    | "multi-branch"
    | "multi-scale"
    | "decomposition-merge"
    | "generic-hierarchy";
  primaryFlow: CanonicalEdgeId[];
  sideInputs: CanonicalPortId[];
  repeatedRegions: ControlRegionId[];
  branchGroups: CanonicalNodeId[][];
  hierarchyRoots: CanonicalNodeId[];
  evidenceIds: string[];
}
```

`encoder-decoder` 才使用 Transformer 的双列构图；encoder-only、分解/合流和多尺度模型不得被补造 Decoder。其他 profile 仍遵循论文级视图的紧凑阅读、稳定父子包含、条件输入侧挂、重复结构折叠、底到顶或明确主流向等共同规则。

### 6.7 `fixtures/tier_a` 通用化验收矩阵

`fixtures/tier_a/` 是通用管线的 P0 兼容集。测试 harness 可以声明入口和输入 Shape，但 production analyzer/projector 不得读取 fixture 名称来决定语义或布局。

| Fixture | 权威入口 | 必须覆盖的通用能力 | 论文级结构预期 |
|---|---|---|---|
| `transformer` | `model.py:Transformer` | 多输入、target mask、self/cross attention、残差 | encoder/decoder 双列 |
| `autoformer` | `models/Autoformer.py:Model` | 四输入、多文件引用、decomposition、AutoCorrelation、encoder/decoder | 分解/合流与 encoder/decoder 主列 |
| `itransformer` | `model/iTransformer.py:Model` | encoder-only、多输入/可选输入、变量维反转、归一化 | 单主栈加侧挂 covariates |
| `patchtst` | `models/PatchTST.py:Model` | patching、RevIN、decomposition 分支、共享 backbone | patch 主链和分解双分支合流 |
| `timemixer` | `models/TimeMixer.py:Model` | 多尺度列表、循环/ModuleList、season/trend 分解与 mixing | 多尺度泳道加分解/合流 |

每个 fixture 必须自动产生：

1. 非空 `engineering-flow` 和 `paper-publication`；
2. 来自同一 Exact IR 的 canonical node/edge/port 集，切换 preset 不改语义 digest；
3. 至少入口模块、一级子模块和一个更深层子模块的可递归展开关系；若源码没有该深度，测试记录 evidence-backed 原因；
4. graph input/output、条件输入、分支/合流、重复区和 opaque boundary 的真实 named ports；
5. 折叠、单模块展开、全部展开、atomic/recursive A/B、拖动、缩放、导出和恢复；
6. source anchor/evidence 定位，以及 partial/opaque 项的显式 diagnostics；
7. 无项目专用 scene builder 的证明，包括重命名目录/文件的 metamorphic test 和生产 bundle 禁止 fixture import 的静态检查。

Tier A 的首次正确输出经人工评审后可以建立各自的视觉 golden，但其作用是防止后续回归，不得反过来把 golden 节点数组写入运行时。两个权威 Transformer 的 golden 等级更高：Tier A 修复导致二者任一标准/论文视图偏离最小原型时，本轮不得合并。

### 6.8 专用 analyzer 退场与无 Pattern Pack holdout

当前 `src/archcanvas_python/analyzer.py` 仍根据 `architecture_profile` 直接分派到 `autoformer.py`、`itransformer.py`、`patchtst.py` 和 `timemixer.py`。这是现状，不是目标架构。迁移必须按以下顺序退场：

1. 为每个专用 analyzer 建立其产生的 canonical fact、annotation、diagnostic 和视觉期望清单；
2. 在关闭 family Pattern Pack 和专用分派的情况下，由通用 LibCST/Semantic Graph frontend 恢复可证明的 definitions、instances、calls、values、ports、control regions 和 hierarchy；
3. 只能把模型家族知识迁入声明式 pattern predicate、semantic annotation、registry matcher 或 view-template predicate；
4. 专用实现不得再创建/删除 canonical node、edge、tensor、port，也不得提供坐标或完整场景；
5. 删除 production `architecture_profile -> analyze_*` 直接返回路径，并以静态 import 检查证明正式 bundle 不依赖这些模块；
6. 启用声明式 pack 时提升论文图语义名称和模板绑定，禁用 pack 时仍生成结构正确、可展开、可定位 evidence 的通用双视图。

除 Tier A 外，必须纳入 `docs/acceptance/stage-8.md` 的七类无 Pattern Pack holdout：CNN/ViT、state-space、GNN、diffusion、MoE、time-series 和 custom hybrid。它们不要求匹配 Transformer golden，但必须通过 source identity、semantic closure、任意深度 hierarchy、canonical coverage、几何和 evidence 门禁。新增模型家族能力时优先扩充此类 holdout，不能通过新增 `architecture_profile` 证明通用性。

## 7. “从源码构建”的正式流程

### 7.1 用户流程

1. 用户点击“从源码构建”。
2. 选择目录或受支持归档、Python 环境、framework、entrypoint 和可选 config。
3. 前端调用项目 discovery，显示候选入口和不可分析原因。
4. 用户确认后启动 v2 analysis job。
5. UI 显示 queued/running/succeeded/failed/cancelled/stale；切换项目会使旧 generation 结果失效。
6. 成功后一次性接收 Source Project、IR、hierarchy、evidence、diagnostics、template bindings 和默认 visual document。
7. 默认打开 `engineering-flow`，适合视图，并选中入口模块。
8. 用户可无损切换 `paper-publication` 等 preset；旧 Transformer golden URL 可以继续使用 `paper-transformer` alias。

### 7.2 后端流水线

```text
discover
  -> resolve manifest/source roots
  -> capture immutable SourceCorpus
  -> parse every selected Python file with LibCST
  -> local import and symbol resolution
  -> optional pinned Pyright query batch
  -> Python Semantic Graph
  -> registry + named-port binding
  -> Exact Architecture IR v2
  -> pattern packs / semantic overlay
  -> hierarchy + evidence + diagnostics
  -> publication/view projection inputs
```

关键门禁：

- 任何文件在捕获期间 digest 变化，整次分析标为 stale；
- 超出文件数、字节数、语法、CFG 或时间预算时返回 partial/opaque，不猜测；
- 源码读取必须限制在 manifest source roots 和显式归档成员；
- 静态分析不执行项目代码；
- sidecar、pattern pack、registry、schema 和 analyzer 的版本/digest 都进入 analysis input manifest；
- 即使没有 family pattern pack，也必须从 canonical hierarchy 和边界端口生成通用标准/论文视图；
- production analyzer/projector 不得 import `fixtures/`、原型 `SCENARIOS` 或按项目身份选择实现；
- 前端只接受 schema version 与 capability report 兼容的结果。

### 7.3 现有 API 的复用

P0 直接复用：

| API | 新 UI 用途 |
|---|---|
| `GET /api/state` | 初始 hydrate 和事务后刷新 |
| `GET /api/projects/recent` | 最近项目 |
| `GET /api/environments/conda` | 环境选择 |
| `GET /api/directories` | 本地目录选择 |
| `POST /api/projects/open` | 建立 project session |
| `GET /api/projects/{id}/discovery` | 入口点与配置发现 |
| `POST /api/analyses` | 启动分析 |
| `GET /api/jobs/{id}` | 任务进度 |
| `POST /api/jobs/{id}/cancel` | 取消任务 |
| `GET /api/search` | 统一搜索 |
| `GET /api/source-excerpt` | 选中对象定位源码 |

前端不得把 `StudioState` 整对象作为组件 props 到处传递。建立 `normalizeStudioState()`，只提取 source、semantic、visual、job 和 transaction 五个 slice。

### 7.4 Framework Adapter 的逐形态能力边界

`SourceProjectRef.framework` 只说明项目框架，不能代表所有能力都可用。每次打开项目和每次 semantic intent 都必须解析现有 `FrameworkAdapterCapability.forms`，按“框架 + 源码形态 + 动作”返回状态：

```ts
type CapabilityStatus = "verified" | "experimental" | "partial" | "unavailable";

interface FrameworkFormCapabilityV2 {
  formId: string;
  framework: "pytorch" | "keras" | "jax" | "onnx" | "python";
  staticAnalysis: CapabilityStatus;
  runtimeEvidence: CapabilityStatus;
  parameterTransaction: CapabilityStatus;
  structuralTransaction: CapabilityStatus;
  codeGeneration: CapabilityStatus;
  artifactCommit: CapabilityStatus;
  supportedTargets: string[];
  verifiedFixtures: string[];
  limitations: string[];
}
```

`FrameworkFormCapability` 下一 schema 版本应增加 `code_generation`，并让 API、UI、命令 handler 和 release support matrix 消费同一行能力。用户选择 Keras subclass、Keras Functional、JAX pure function、Flax Module、ONNX standard graph、ONNX external data 或 custom-domain graph 后，按钮状态和拒绝 receipt 必须来自对应 form，不能回退到框架级布尔值。

本指南 P0 的 greenfield generator 明确只承诺受 registry/codegen rule 覆盖的 PyTorch `nn.Module`。Keras/JAX/ONNX 在对应 form 未达到 verified 前，只开放 capability matrix 允许的分析、运行或有界事务；不得因 Python 静态分析可用就宣称结构生成和提交可用。缺少框架包、provider 或自定义对象时返回 `unavailable`，不自动安装依赖。

### 7.5 分析环境和入口调用的可复现契约

Source snapshot 之外增加 `AnalysisEnvironmentManifest`，至少冻结：

```ts
interface AnalysisEnvironmentManifest {
  pythonImplementation: string;
  pythonVersion: string;
  platform: string;
  frameworkVersions: Record<string, string | null>;
  adapterDigests: Record<string, string>;
  analyzerDigest: string;
  schemaBundleDigest: string;
  registryDigest: string;
  patternPackDigests: string[];
  pyrightVersion?: string;
  lockfileDigests: Record<string, string>;
  environmentVariablesAllowlistDigest: string;
}
```

静态分析结果必须绑定该 manifest；其中影响解析和语义规则的字段变化后缓存立即 stale。runtime 另绑定实际 backend、device/provider、驱动和可选依赖版本。入口调用必须保存 constructor args/kwargs、forward args/kwargs、static args、train/eval 和输入结构；同一个类用不同构造配置得到的是不同 analysis input，不得共享 Exact IR digest。

环境发现只报告已有环境和能力，不执行 `pip/conda` 安装。lockfile 不存在时记录 `unlocked` diagnostic；这不一定阻断纯静态查看，但会降低 runtime/codegen verification 等级，且不能生成可复现声明。

## 8. 从画布直接修改源码

### 8.1 两类命令必须分开

Visual Command：

```text
move-node, resize-node, set-camera, set-style, set-route,
expand, collapse, set-detail-offset, align, distribute, pin
```

它们只生成 Visual Patch，可以立即显示并进入视觉 undo/redo。

Semantic Intent：

```text
create-node, delete-node, set-parameter, replace-operation,
insert-normalization, connect-ports, disconnect-edge,
add-residual, concat-inputs, edit-source-buffer
```

它们不能先改正式 scene；只能生成 preview overlay，并等待后端收据。

### 8.2 统一命令协议

```ts
interface SemanticIntent {
  intentId: string;
  kind:
    | "create-node"
    | "delete-node"
    | "set-parameter"
    | "replace-operation"
    | "insert-normalization"
    | "connect-ports"
    | "disconnect-edge"
    | "add-residual"
    | "concat-inputs"
    | "edit-source-buffer";
  baseSourceDigest: string;
  baseExactIrDigest: string;
  targetCanonicalIds: string[];
  sourceAnchorIds: string[];
  parameters: Record<string, unknown>;
}

interface CapabilityDecision {
  status: "lowerable" | "needs-review" | "proposal-only" | "invalid";
  adapterId?: string;
  expectedDelta?: GraphDelta;
  reasonCodes: string[];
  diagnostics: Diagnostic[];
}
```

`expectedDelta` 由后端选定 lowering adapter 后计算，不能由浏览器声明为事实。同一个用户动作必须有确定结果：可以改、需要评审、只能提案或无效。禁止按钮看似成功但只改了图。

### 8.3 操作到源码策略的映射

| 画布操作 | 语义输入 | 第一批源码 lowering | 不可证明时 |
|---|---|---|---|
| 修改参数 | canonical node + parameter + literal/config anchor | `SemanticParameterPatch` | proposal-only |
| 替换激活 | node + registry definition | `replace_activation` | proposal-only |
| 插入 LayerNorm | edge/port + shape contract | `insert_layer_norm` | proposal-only |
| 新增节点 | registry definition + 参数 + 插入边界 | 拓扑 draft；仅注册模板且有唯一插入点时 lowering | draft 保持 blocked |
| 删除节点 | canonical node + delete impact | 仅无歧义、依赖可闭合的受支持结构 | 显示影响并阻断提交 |
| 新增连线 | source output port + target input port + policy | 注册的 `replace-input`、`fanout`、`add-residual`、`concat` | proposal-only |
| 删除连线 | canonical edge + consumer port | 注册的 disconnect/replace 变换 | proposal-only |
| 手工改源码 | staged files + base digest | `FreeformSourcePatch` | stale/validation failure |

节点 palette 必须由 `module-registry-v1.json` 驱动；创建时生成 definition、参数和 named ports。不能恢复原型当前“新增一个通用 operation 节点”的语义行为。

### 8.4 连线交互

必须保留原型“进入连线模式 -> 选择起点 -> 选择终点”的手感，但命中对象升级为端口：

1. hover 节点时显示兼容 output ports；
2. 选择 source port 后，只高亮类型、shape、relation、cardinality 兼容的 target ports；
3. 拖动或点击 target port 后生成 `connect-ports` intent；
4. UI 显示 policy 选择：`replace-input`、`fanout`、`add-residual`、`concat`；
5. 后端返回 capability 和 expected delta；
6. preview edge 用未提交样式显示；
7. 事务验证成功后进入 diff/review；
8. commit 后重分析，canonical edge 才成为正式边。

不得退化成按边数组顺序决定输入，也不得只保存 source/target node ID。

### 8.5 删除操作

删除前必须调用影响预览，至少列出：

- 被删除 canonical node/edge/tensor；
- 受影响 consumers、shared parameters 和父模块；
- 是否有安全 bypass/rewire；
- 对 shape、输出和 evidence 的影响；
- lowering capability 和阻断原因。

原型的“删除节点并清理关联边”继续用于纯视觉 fixture；source-backed 模式禁止用该函数删除正式模型。

### 8.6 事务状态机

```text
draft
  -> prepared
  -> source-validated
  -> graph-validated
  -> review-ready
  -> committed

任意阶段 -> failed / discarded / stale
```

`verify` 至少执行：

- base source/corpus digest 新鲜度；
- LibCST parse 和 anchor 唯一性；
- 静态 import/symbol resolution；
- 重分析 Exact IR；
- expected/observed Graph Delta 精确匹配；
- named port、shape、dtype 和 cardinality；
- Python compile check；
- 请求中声明的 targeted tests；
- hierarchy 的 collapsed/full projection；
- 目标 preset 的 scene 构建和几何验证。

只有 `review-ready` 可以显示提交按钮。提交成功后必须重新 hydrate，而不是把 preview scene 当成新事实。

### 8.7 视觉状态重放

源码提交后：

1. 用 lineage ID 匹配新旧 canonical objects；
2. 保留仍存在对象的位置、尺寸、展开和 slot offset；
3. 新对象放在受影响局部邻域，不全图重排；
4. 删除对象的 visual override 进入可审计 tombstone 后再清理；
5. 当前选择映射到新对象或清空，并给出原因；
6. 每个 preset 分别迁移自己的 VisualState。

### 8.8 当前缺口：代码预览不等于源码能力

当前主程序已经具备一部分底座，但不能把这些底座误报为“画布已经可以生成或修改源码”：

| 已有能力 | 当前边界 | 本次迁移必须补齐 |
|---|---|---|
| `studio/src/module-registry/` | 有版本化 definition、参数 schema、named port 和 registry digest | 让 palette、检查器、Shape、成本、codegen 和源码 lowering 真正消费同一 definition |
| `studio/src/prototype-graph/` | 可物化端口并做部分 Shape、关系、基数和成本分析 | 建立可编辑但不可直接提交的正式 Graph Draft，并补齐控制流、复合模块和提交门槛 |
| `studio/src/codegen/` | 可生成带 span 的 PyTorch 草稿预览 | 把预览升级为可验证、可评审、可物化并可重新打开的 Source Project |
| draft/proposal API | 可以记录 synthetic node/edge 和意图 | `create-node`、`connect-ports`、`delete-node` 的通用写回仍缺少 adapter，当前必须保持 blocked/proposal-only |
| Source Workspace | 已有单文件/事务基础 | staged 多文件编辑、生成项目评审和图/源码双向选择尚未形成完整产品链路 |
| runtime trace | 面向冻结的源码入口和显式验证任务 | 不能验证刚生成的源码，也没有生成代码专用的隔离、限额和确定性重放协议 |

因此要实现的是两种不同的源码结果，而不是继续给代码预览增加“下载”按钮：

```text
既有源码模式：
SemanticIntent -> adapter lowering -> LibCST Source Transaction -> 重分析

空白构图模式：
PrototypeGraphDocument -> 静态验证 -> PyTorch Code IR -> 确定性打印
  -> Generated Source Project draft -> 编译/静态分析 -> 可选隔离运行
  -> 评审 -> 物化 -> 作为新的 Source Project 重新打开
```

两种模式必须在 project/session 中显式标识，不得在 lowering 失败时偷偷从“修改既有源码”切换成“重生成整个文件”。浏览器也不得直接写用户目录。

### 8.9 Registry 驱动的节点创建和参数编辑

DL-Playground 中最值得保留的思想，是一个 layer definition 同时驱动节点创建、参数 UI、Shape、成本和代码生成。实现时复用当前 `module-registry`，但不要复制其源码或把 React 组件塞回 definition。

每个已批准定义至少固定以下契约：

```ts
interface RegisteredModuleDefinition {
  ref: {
    definitionId: string;
    version: string;
    digest: string;
  };
  categoryId: string;
  canonicalKind: string;
  parameterSchema: ParameterSchema[];
  ports: PortContract[];
  shapeRuleId?: string;
  costRuleId?: string;
  codegenRuleId?: string;
  sourceMatchers: SourceMatcher[];
  glyphId: string;
  detailTemplateId?: string;
  editPolicy: EditPolicy;
}
```

`ref` 必须固定 ID、版本和 digest。草稿节点只保存 definition ref、实例参数、父级和实例级端口，不复制 definition；已批准 definition 不能原地修改。

创建节点的完整调用链为：

1. palette 从 registry 构建搜索和分类，不维护第二份节点类型列表；
2. 用户选择 definition 后，由 registry 物化 schema 默认值和精确 named ports；
3. `CreateNode` command 携带 draft digest 和 definition ref 进入 command handler；
4. command handler 产生新 `PrototypeGraphDocument`、audit event 和 diagnostics；
5. Shape/成本分析产生只读 `AnalysisSnapshot`；
6. `projectToScene()` 把节点投影到原型画布，并使用 definition 的 glyph/template；
7. 用户确认源码策略前，节点始终是带明确状态的 synthetic draft，不能伪装成 canonical node。

右侧参数检查器同样由 schema 驱动：数字使用带范围的输入/步进器，布尔值使用开关，枚举使用选择器，Shape/tuple 使用结构化编辑器。每次修改发出 `SetInstanceParameter`，先校验类型、约束和动态端口变化，再重新分析；节点卡片只显示高价值摘要，不复制一套完整表单。

参数导致端口集合变化时，registry 必须返回端口迁移结果。仍可对应的端口保留稳定实例 ID；被移除且已有连接的端口产生 blocking diagnostic，由用户显式断开或迁移，不能静默删边。

### 8.10 严格命名端口与 Graph Draft

Graph Draft 是语义编辑的权威暂存层，React 状态、`LabScene` 和 SVG handle 都不是图事实。建议复用现有 `PrototypeGraphDocument` 并保证最小结构包含：

```ts
interface PrototypeGraphDocument {
  draftId: string;
  baseSourceDigest?: string;
  baseExactIrDigest?: string;
  baseRegistryDigest: string;
  sourceStrategy: "rewrite-existing" | "generate-project";
  nodes: PrototypeNode[];
  edges: PrototypeEdge[];
  inputs: GraphInput[];
  outputs: GraphOutput[];
  controlRegions: ControlRegion[];
  digest: string;
}

interface PrototypeEdge {
  edgeId: string;
  source: { nodeId: string; portId: string };
  target: { nodeId: string; portId: string; ordinal?: number };
  relation: "tensor" | "mask" | "state" | "control" | "parameter";
  policy: "replace-input" | "fanout" | "add-residual" | "concat";
}
```

在 `rewrite-existing` 中，draft 以 Exact IR binding 为只读基线：canonical nodes/edges 不被就地改写，新增对象使用 synthetic ID，修改和删除用 intent overlay 表达，并保留 source anchors。`generate-project` 没有既有 canonical/source anchor，全部对象都是 draft 身份，直到物化后重新分析才获得 canonical ID。两类身份不得混合或用 scene ID 代替。

端口不是绘图锚点。每个实例端口必须保留 direction、required、min/max connections、ordered/variadic、accepted relations、tensor contract 和 definition port ID。SVG 中的坐标和边侧只是该端口在当前 preset 下的投影。

Graph Draft 允许暂时不完整：用户可以先放节点、再连线，也可以在重构中暂时移除必需输入；但每个 command 后都要立即给出 blocking/non-blocking diagnostics。正式提交前固定运行：

```text
schema/default validation
  -> port existence + direction
  -> cardinality + ordered ordinal
  -> relation compatibility
  -> required input completeness
  -> tensor rank/dtype/layout
  -> cycle/control-region validation
  -> symbolic Shape propagation
  -> cost analysis
  -> source strategy feasibility
  -> zero blocking diagnostics
```

所有语义命令返回新文档、diagnostics、digest 和审计事件。禁止把现有 `applyVisualPatch()`、节点数组 patch 或“删节点并顺便删边”的 fixture helper 用在 Graph Draft 上。

### 8.11 Shape、成本、诊断和提交门槛

分析器按依赖关系调度节点，并按 **目标 port ID 和 ordinal** 组装输入；绝不能依赖 edges 数组顺序。Shape 值至少区分：

```text
Known(具体维度)
Symbolic(B、T、D 等带约束符号)
Unknown(证据不足，可继续部分分析)
Error(契约冲突，阻断提交)
```

规则结果必须记录 definition/rule 的版本和 digest、输入假设、输出 Shape、diagnostics 与受影响对象。某节点无法分析时，只阻断依赖它且需要该事实的下游；无关分支仍产生部分结果，不能因单个 unknown 清空全图结果。

成本分析必须区分 module instance、call site 和 parameter group：共享 embedding/输出投影只计算一次参数，同一共享模块被调用多次则分别计算 FLOPs；符号维度产生带公式和假设的范围，不伪造具体数字。

源码提交门槛按策略分开：

| 校验 | 修改既有源码 | 生成新项目 |
|---|---|---|
| 端口/Shape/控制结构 | 必须 | 必须 |
| lowering adapter 可用 | 必须 | 不适用 |
| 精确 source anchor | 必须 | 不适用 |
| codegen rule 全覆盖 | 仅涉及重生成片段时 | 必须 |
| Python compile | 必须 | 必须 |
| 重分析后的 Graph Delta | 必须 | 必须与整个 draft 对应 |
| 可选 runtime replay | 可选且显式授权 | 可选且显式授权 |

静态验证通过只能进入 `review-ready`，不能自动提交。任何 unknown 是否阻断由具体 rule 和输出契约声明，UI 不得自行降级 severity。

### 8.12 两种源码结果必须独立实现

#### 8.12.1 修改既有 Source Project

既有源码模式以当前 SourceCorpus、Exact IR、source anchors 和 lineage 为 base：

```text
SemanticIntent
  -> capability adapter selection
  -> expected Graph Delta
  -> LibCST transform plan
  -> 临时 workspace 应用变更
  -> parse/compile/import-resolution 静态检查
  -> 重新分析 Exact IR
  -> observed Graph Delta 精确比较
  -> diff/review/commit
```

adapter 必须声明支持的框架、源码形态、必需 anchors、前置条件和预期 delta。例如 `insert-sequential-module@1` 只能处理已证明的顺序调用边界；`add-residual@1` 必须知道 add 的插入位置、两路值和后续 consumer。没有唯一 lowering 时保持 proposal-only，不尝试字符串拼接或正则替换。

该模式只改必要的 CST 节点并保留其他格式、注释和导入。它不得把整个类替换成 codegen 输出，也不得因为画布图可生成 PyTorch 就覆盖用户手写控制流。

#### 8.12.2 从 Graph Draft 生成新的 Source Project

空白构图模式不要求 source anchor，但要求所有节点、端口、控制区和输出都可由固定版本的 codegen rule 表达：

```text
PrototypeGraphDocument
  -> validateGraph()
  -> compileToPyTorchCodeIR()
  -> deterministic printer + source map
  -> GeneratedProjectManifest + candidate files
  -> 后端临时 workspace
  -> compile + 静态重分析 + expected/observed graph comparison
  -> review
  -> 用户选择的新目录中原子物化
  -> 作为 Source Project 打开
```

生成结果至少包含模型源码、项目 manifest、入口声明和 generation receipt。依赖版本、Python/PyTorch 约束、输入规格、seed 和 generator digest 必须写入 manifest；可选测试文件只能由已注册模板生成。

前端代码预览可以即时产生，但正式 candidate bundle 必须由后端使用固定版本 generator 重新产生，或由后端对浏览器提交的 Code IR/文件逐项重建 digest 并完成全套静态重分析。浏览器提供的字符串永远不直接写入目标目录。

### 8.13 结构化 PyTorch Code IR 与双向 source map

Codegen rule 只能构造结构化节点，不能返回拼接后的 Python 字符串。Code IR 至少表达：

- import、class、`__init__` field、`forward` 参数和 return；
- module call、functional call、attribute/index、keyword argument 和安全 Python literal；
- 单值、tuple、嵌套 tuple、可选输出和丢弃值；
- shared module field 与多个 call site；
- `ModuleList`、Repeat、显式 loop 和受限条件区；
- graph input/output 与 named port value binding。

编译顺序以依赖图和 control region 为准。拓扑排序只适用于普通 DAG 区域，不能把 Repeat 或条件分支拍平成无条件节点列表。MHA、LSTM 等多输出规则必须完整表达 tuple pattern，不能生成 `${output}, _ = ...` 后丢失画布已声明的输出。

printer 负责确定性命名、导入去重、缩进、换行和 literal 编码。同一 graph digest、registry digest、generator version 和配置必须得到字节完全相同的文件；用户 label 不直接成为变量名，字符串、路径、dtype 和可选值必须通过安全 printer 编码。

每个输出 span 至少可以回到以下一种来源：

```ts
type GeneratedSourceOrigin =
  | { kind: "node"; nodeId: string }
  | { kind: "port"; nodeId: string; portId: string }
  | { kind: "edge"; edgeId: string }
  | { kind: "parameter"; nodeId: string; parameterId: string }
  | { kind: "control-region"; regionId: string };
```

source map 同时建立 origin -> spans 和 file/range -> origins 索引。选择画布对象时高亮所有相关源码；选择源码时只在映射唯一或用户从候选中确认后选择图对象。生成源码 map 和既有源码的 LibCST SourceAnchor 是两套证据，不能混用：前者来自 printer，后者来自冻结 SourceCorpus。

### 8.14 Generated Source Project 生命周期

生成项目是正式领域对象，不是下载弹窗中的临时文本：

```text
graph-draft
  -> generated-source-draft
  -> statically-validated
  -> runtime-validated（可选）
  -> review-ready
  -> materialized
  -> opened-and-reanalyzed

任意阶段 -> failed / discarded / stale
```

建议新增后端能力，具体 URL 可按现有 API 命名约定调整：

```text
POST /api/generated-projects/prepare
POST /api/generated-projects/{id}/validate
POST /api/generated-projects/{id}/runtime-validate
POST /api/generated-projects/{id}/materialize
POST /api/generated-projects/{id}/discard
```

`prepare` 请求至少携带 graph digest、registry digest、generator version、目标框架、class/entrypoint 配置和输入规格；返回文件清单、每文件 digest、source map、diagnostics 和 receipt。服务端在临时目录中工作，`materialize` 之前不触碰目标目录。

物化前必须再次校验 receipt、目标目录是否为空或符合显式覆盖策略、路径 confined、文件 digest 和 stale generation。默认只允许新建空目录；覆盖已有文件需要单独逐文件授权和 diff，不能借“生成项目”绕过 Source Transaction。

物化后立即走第 7 节的“从源码构建”流程。只有新 SourceCorpus 能重新产生与 draft 对应的 Exact IR、入口可发现且 source map/lineage 可建立，状态才是 `opened-and-reanalyzed`；否则物化 receipt 标记失败或部分失败，不能把浏览器 draft 当成正式项目继续编辑。

### 8.15 复合模块、Repeat 和 ModuleRef

自定义模块不能只保存在浏览器 `localStorage`。从选区创建模块时必须：

1. 捕获选中节点、内部边和 control regions；
2. 按跨边界的 named ports 推导模块输入/输出，要求用户解决歧义并命名；
3. 识别可提升参数、内部常量、共享 parameter groups 和 Shape 约束；
4. 生成 `DefinitionDraft` 和嵌套 Graph IR；
5. 运行 schema、port、Shape、codegen 和 migration fixture 校验；
6. 经 contract review 后发布不可变 definition version；
7. 外部图只通过固定 digest 的 `ModuleRef` 引用它。

definition 生命周期为：

```text
approved@vN -> definition-draft -> validating -> review-ready
  -> approved@vN+1 / rejected
```

版本判断同时比较参数 schema、端口、Shape/cost/codegen rule、source matcher 和视觉 metadata。端口删除、语义变化或 rule digest 变化必须按 breaking change 处理，并提供引用实例的迁移结果。

Repeat 是显式 control region，不是为了画面方便复制 N 个无关节点：

- 记录 repeat count 是具体值还是符号；
- 明确参数是共享、逐层独立还是由 factory 生成；
- 代码生成选择 loop、`ModuleList` 或合法展开；
- 论文视图可以只显示 `x N`，工程视图可以按需展开调用实例；
- 展开/收起只改变 View Preset，不改变 Graph Draft 或生成源码。

`ModuleRef` 的外部端口来自已批准模块契约，进入模块编辑时打开独立嵌套 draft；不能在父图里直接修改其内部 definition。递归引用、未固定版本和边界端口不闭合均阻断 codegen。

### 8.16 三层保护锁与四套历史

编辑模式必须是带 capability、base digest 和过期时间的 session，而不是 UI 中一个 `locked` 布尔值：

| 模式 | 默认状态 | 允许 | 禁止 |
|---|---|---|---|
| 视觉模式 | 开放 | 移动、缩放、展开、样式、路由、preset | 改节点、边、参数、契约 |
| 拓扑草稿模式 | 锁定 | 创建/删除实例、连接/断开端口、改实例参数 | 改 definition、绕过验证提交 |
| 模块契约维护模式 | 强锁定 | 从批准版本创建 definition draft、校验和送审 | 原地修改批准版本、直接影响所有实例 |

权限在 command handler、domain validator 和持久化/API 三层重复检查。每个拒绝返回结构化 receipt；隐藏按钮或 toast 不算权限实现，键盘、导入和测试代码也不能绕过。

历史记录必须分开：

- `VisualHistory`：位置、尺寸、相机、展开、route hint；
- `TopologyDraftHistory`：Create/Delete/Connect/Disconnect/SetParameter 及其反向 command；
- `ContractDraftHistory`：definition manifest 和 migration edits；
- 正式 Source Transaction history：只能通过新的反向事务撤销，不能被浏览器 undo 擦除。

CodeMirror 当前 buffer 还有自己的本地 history，但它只作用于 staged 文本。移动节点不得使 graph/codegen digest 失效，源码提交也不得进入 visual undo 栈。

### 8.17 生成源码的隔离动态验证

动态运行只能补充静态证据，不能成为构图、source anchor 或 Exact IR 的默认来源。用户必须对每次运行或明确范围的会话显式授权；未授权时 UI 不得预加载模型、导入目标工程或自动重试。

每个运行任务使用一次性 workspace 和独立 worker/container，并满足：

- 默认禁网，不挂载宿主 Docker socket；
- 输入文件只读，输出只写临时目录；
- 限制 wall-clock、CPU、内存、PID、打开文件数和文件大小；
- 清理环境变量和 Python path，只使用批准的解释器与锁定依赖；
- 进程超时后终止整个进程组，不能留后台子进程；
- 不在长期服务进程中对用户字符串直接 `exec`；
- stdout/stderr 截断并脱敏，不把源码全文写入日志。

运行请求使用结构化输入规格，支持多个位置/关键字输入、嵌套 tuple/dict 输出、dtype/device、Shape 和可选值域。worker 用固定 seed 构造输入，至少运行两次并记录规范化 replay digest；结果包含模块调用、输入输出 shape/dtype、异常、耗时、资源峰值和环境 manifest。

runtime evidence 与 source/IR 绑定：graph、candidate files、registry、generator、environment 和 input spec 任一 digest 改变后 receipt 立即 stale。两次运行不一致时标记 nondeterministic，不可用于声称生成项目已完全验证。无论运行成功与否，静态端口、source map 和 Graph Delta 门槛都不能被跳过。

### 8.18 第一条构图到源码纵向切片

先用 `Input -> Conv2d -> ReLU` 证明完整链路，不要先追求 palette 中 14 类全部可用：

```text
创建 Input [B,3,224,224]
  -> 创建 Conv2d(in=3,out=16,kernel=3)
  -> 创建 ReLU
  -> 按 named ports 连线
  -> 得到 [B,16,222,222]
  -> 生成结构化 Code IR 和 source map
  -> 后端准备 Generated Source Project
  -> compile + 静态重分析
  -> review/materialize
  -> 从新源码重新打开并得到同构 Exact IR
```

把 `Conv2d.in_channels` 改成 4 后，必须在 `Conv2d.input` 出现 blocking diagnostic；改回 3 后消失。删除 ReLU 后输出应明确改绑到 Conv2d，不能留下孤立 edge；重新加入并连线后 code/source map 必须稳定更新。

同一切片还要准备一个等价的既有源码 fixture，证明 `SetParameter` 和受支持的 `InsertNode` 走 LibCST transaction，而不是重生成文件。两条流程分别验收：

- greenfield：能生成、验证、物化、重新打开；
- existing-source：只改目标 anchor，保留注释/格式并精确匹配 Graph Delta；
- unsupported：无 adapter、端口不兼容或 source anchor 歧义时零源码写入；
- visual parity：全过程继续使用原型的拖动、缩放、连线、展开、选择和导出行为。

该切片通过后，再扩展 Add、MHA、LSTM、共享模块、tuple output、Repeat 和 ModuleRef。简单单输入/单输出链路未闭环前，不得用菜单数量代替完成度。

### 8.19 参数值来源与编辑作用域

参数检查器显示的值不等于源码中一定存在一个可替换 literal。Exact IR 和 registry binding 必须为每个可见参数保存 `ValueOrigin`：

```ts
type ValueOriginKind =
  | "constructor-literal"
  | "module-field"
  | "config-key"
  | "dataclass-field"
  | "function-default"
  | "cli-argument"
  | "registry-default"
  | "factory-result"
  | "computed-expression"
  | "runtime-only";

interface ValueOrigin {
  originId: string;
  kind: ValueOriginKind;
  sourceAnchorIds: string[];
  configPath?: string;
  configKeyPath?: string[];
  confidence: "exact" | "conditional" | "unknown";
  editability: "direct" | "adapter-required" | "readonly";
  evidenceIds: string[];
}

type EditTargetScope =
  | "definition"
  | "module-instance"
  | "call-site"
  | "repeat-template"
  | "config-value"
  | "parameter-sharing-group"
  | "all-shared-uses";
```

`set-parameter` intent 必须携带 `valueOriginId`、`editTargetScope` 和用户确认时显示的 affected canonical IDs/source anchors。后端重新解析 origin 并计算影响范围，不能信任前端上传的集合。以下情况必须要求显式选择或阻断：

- 同一个 config key 构造多个 module instances；
- 同一个 module instance 有多个 call sites；
- Repeat 使用共享模板、独立 `ModuleList` 或 factory 创建不同参数；
- embedding/projection 使用同一 parameter-sharing group；
- 值来自表达式、环境变量、CLI 或 factory，无法唯一改写；
- 修改 constructor definition 会影响项目内其他实例。

检查器应先展示“当前解析值、来源、作用域、受影响对象”，再允许 prepare。禁止把 call-site 展示节点误当成独立 module instance，也禁止通过复制共享参数来实现“只改一个调用”。

### 8.20 模型状态、权重和 checkpoint 迁移

源码结构事务和模型状态迁移是两个独立结果。每个绑定了 checkpoint/state asset 的参数或结构事务都必须生成 `StateMigrationPlan`：

```ts
type StateMigrationAction =
  | "preserve"
  | "rename"
  | "reshape"
  | "initialize"
  | "drop"
  | "block";

interface StateTensorSpec {
  dimensions: Array<number | string>;
  dtype: string;
  device?: string;
}

interface StateMigrationEntry {
  oldStateKey?: string;
  newStateKey?: string;
  action: StateMigrationAction;
  oldTensor?: StateTensorSpec;
  newTensor?: StateTensorSpec;
  parameterGroupId?: string;
  initializerRuleId?: string;
  optimizerSlotKeys: string[];
  evidenceIds: string[];
  diagnostics: Diagnostic[];
}

interface StateMigrationPlan {
  planId: string;
  framework: "pytorch" | "keras" | "jax" | "onnx";
  baseSourceDigest: string;
  resultSourceDigest: string;
  sourceStateDigest: string;
  targetStateSchemaDigest: string;
  entries: StateMigrationEntry[];
  sharedIdentityChecks: string[];
  status: "verified" | "partial" | "blocked" | "not-requested";
}
```

计划至少覆盖 learnable parameters、registered/non-trainable buffers、optimizer state/slots、共享或 tied weights，以及框架特有的 state tree/initializer。参数名相同但 Shape/dtype/共享身份不同不能标记 preserve；`strict=False`、missing/unexpected keys 或按位置复制不能替代逐项计划。

事务 receipt 必须分别报告：

- `source_status`：源码和 Exact IR 是否提交成功；
- `state_compatibility`：现有模型状态是 verified/partial/blocked/not-bound；
- `training_resume_compatibility`：optimizer、scheduler、step/epoch 和随机状态是否可恢复；
- `inference_compatibility`：目标模式下 state load 和最小 replay 是否通过。

用户可以显式选择 `source-only` 提交，但 UI 必须说明原 checkpoint 已解除绑定或兼容性未知，不能继续显示“可直接运行/继续训练”。`source+state` 只有计划 verified、迁移产物 digest 固定、隔离加载通过并经 review 后才能提交。未经信任的 pickle/整模型对象默认不加载；PyTorch 优先 `state_dict`/`weights_only`，Keras 处理 architecture/weights/optimizer/custom object，JAX/Flax 处理 PyTree 结构和 optimizer state，ONNX 处理 initializer/external-data ArtifactSet。

### 8.21 外部变更、多文件原子性和崩溃恢复

stale 事务不得自动做文本 fuzzy merge。用户选择恢复时，系统以原 `SemanticIntent`、旧 expected delta 和新的 SourceCorpus 重新执行 capability/anchor resolution，产生新的 transaction ID；旧 base/current/proposed 三方 diff 只用于理解冲突。重新 prepare 后必须重新运行全部门禁。

多文件事务使用持久化 journal，而不是把内存状态当作原子性：

```text
prepared -> verified -> commit-intent-recorded
  -> replacing-files -> post-commit-validating -> committed
  -> rollback-required -> rolled-back / recovery-failed
```

journal 记录 transaction、base/result corpus digest、每个文件 before/after digest、备份位置、替换进度、fsync/rename 结果和 post-commit gates。服务启动时扫描非终态 journal：能证明所有文件为 before 状态则 discard；能证明所有文件为 after 状态则继续 post-commit validation；混合状态必须从已验证备份回滚并生成 recovery receipt。多文件不能宣称底层文件系统提供单原语原子 rename，只能声明“服务级 journal + rollback”。

改写必须保留或显式处理每个文件的 encoding、BOM、LF/CRLF、末尾换行、权限 mode 和逻辑路径。symlink 默认不可写；若未来支持，必须冻结 link 本身和 confined target，不能通过 resolve 越过 project root。无法无损表示的编码、权限变化、备份失败或 rollback proof 不完整均阻断 commit。

## 9. 源码工作区

### 9.1 UI 结构

源码工作区作为底部可拉伸面板或右侧临时全高面板，不改变原型画布中央区域。包含：

- 文件列表和 clean/modified/stale/readonly 状态；
- CodeMirror 6 编辑器；
- 与当前 selection 对应的 source anchor 高亮；
- diagnostics、搜索和 evidence 装饰；
- staged diff；
- 保存到 staged buffer、验证、丢弃、评审、提交；
- transaction active 时只读锁。

选择画布节点、边、内部 slot 或导航项时，源码面板定位到对应 anchor；选择源码区间时，只在映射唯一时同步选择画布对象。

### 9.2 现有 Source Workspace API

继续复用：

```text
POST /api/source-workspace/open
POST /api/source-workspace/save
POST /api/source-workspace/buffer/discard
POST /api/source-workspace/validate
POST /api/source-workspace/discard
POST /api/transaction/commit
POST /api/transaction/discard
```

所有 save 请求必须携带 `base_sha256` 和 `expected_revision`。stale buffer 不自动 merge；显示 working/base/staged 三方差异，由用户重新打开或显式解决。

### 9.3 可选 Tree-sitter 层

如果 P2 添加浏览器端 Tree-sitter：

- 只提供即时 syntax error、折叠和局部结构导航；
- 每次 CodeMirror ChangeSet 同步调用 tree edit，再用旧树增量 reparse；
- 结果标记为 `editor-local`，不得生成 canonical ID 或允许提交；
- 最终验证仍以服务端 LibCST 和 Exact IR 为准；
- 不得把 grammar/WASM 首屏加载变成 P0 阻塞项。

### 9.4 审计、离线交付和协议升级

分析、修改和生成结果可以导出为可验证的 `.archcanvas` bundle。现有 `OfflineBundleManifest` 和 `ArtifactSet` 作为清单边界，至少包含或引用：

- redacted SourceSnapshot/SourceCorpus 摘要和 AnalysisEnvironmentManifest；
- Exact IR、hierarchy、evidence、diagnostics、discrepancy records；
- View Preset、VisualState、折叠/完全展开 scene 及 SVG/HTML/PNG/PDF；
- registry、pattern/template bindings、framework form support matrix；
- RoundTripConformanceReport、transaction/runtime/state migration receipts；
- schema bundle、generator/adapter/analyzer digest 和完整 SHA-256 inventory。

bundle verify 必须拒绝缺失、额外或 digest 不符文件，并检查所有 receipt 是否绑定同一个 source/IR/environment generation。默认不打包用户源码全文、checkpoint 或绝对路径；需要包含时由用户显式选择并在 manifest 标记敏感内容。

所有持久化协议采用 major/minor 兼容策略：未知 major 必须拒绝；additive minor 可在验证后读取；需要重写的旧版本通过固定 digest 的 migration 产生新对象和 receipt，不原地静默升级。至少为 Exact IR、CanvasDocument、DraftGraphDocument、Registry、SourceTransaction、StateMigrationPlan 和离线 bundle 保留向前读取测试及一份前一 major/minor 的迁移 fixture。

落地前先建立或升级以下 schema，Python model、导出副本和 TypeScript generated type 必须由同一源生成：

| Schema | 用途 |
|---|---|
| `round-trip-conformance-report-v1` | 固定三类往返、normalization、delta 和 source writes |
| `state-migration-plan-v1` | 固定状态 key/tensor/optimizer/shared identity 迁移及兼容性 |
| `analysis-environment-manifest-v1` | 固定解析、运行和依赖环境 |
| `transaction-journal-v1` | 固定多文件替换、恢复和 rollback proof |
| `framework-adapter-capability-v2` | 增加 form-level codegen，并统一逐动作状态 |
| `semantic-intent-v2` | 增加 ValueOrigin、EditTargetScope、affected-object review binding |

继续复用 `discrepancy-record-v1`、`artifact-set-v1` 和 `offline-bundle-manifest-v1`，不要建立语义重复的新文档。transaction prepare/verify/commit/reprepare、state migration verify/materialize 和 bundle create/verify 的每个响应都必须返回相应 schema 对象或稳定 ID；只返回字符串提示不构成协议实现。

## 10. 场景投影和渲染

### 10.1 `projectToScene()` 是唯一适配器

```ts
function projectToScene(
  architecture: ExactArchitecture,
  hierarchy: PublicationHierarchy,
  evidence: EvidenceRecord[],
  bindings: VisualTemplateBinding[],
  publicationProfile: PublicationStructureProfile | null,
  preset: ViewPreset,
  visualState: VisualState,
): SourceBackedScene;
```

该函数负责：

- 按 preset 选择 canonical frontier；
- 创建 view node/edge 和 scene binding；
- 选择 glyph、detail template、orientation 和 tone；
- 物化 named ports；
- 应用 visual overrides；
- 为新增对象生成确定性初始位置；
- 输出 fidelity 和 diagnostics。

它不能解析源码、执行 pattern matching、修改 IR、读取项目路径/fixture ID 或调用 React。`publicationProfile` 必须由上游根据 IR/evidence 推导；projector 只应用通用布局语法。

### 10.2 详情模板

将 `module-details.ts` 和 `catalog-details.ts` 改为 registry：

```ts
interface DetailTemplate {
  templateId: string;
  version: string;
  applicableKinds: string[];
  slots: DetailSlot[];
  nestedTemplates: Record<string, string>;
  render(context: DetailRenderContext): DetailDiagram;
}
```

每个 slot 明确绑定 node/edge/port/tensor/evidence。禁止 `inferNestedDetailKind()` 根据可见 label 推断。

30 个家族目录模板默认是 `schematic`。只有 predicate 和证据完整时才能升级为 `exact`；无法识别的组合显示 `opaque` 父框和真实边界端口。

### 10.3 层级路由

继续复用原型的：

- recursive detail tree；
- boundary portal；
- portal chain；
- projected atomic entry/exit；
- hidden/foreground flow 分层；
- semantic input port。

替换三项输入：

```text
primitive index -> stable slot ID
label regex      -> explicit nested template binding
point touching   -> named source/target port binding
```

几何只负责把端口投影到 point/side，不负责发现语义。

### 10.4 屏幕和导出必须共用渲染树

当前原型 `NodeGraphic` 与 `svg-export.ts` 有重复图例分支。新程序应抽出：

```text
scene-graphics.ts
  -> create render primitives
  -> React SVG renderer
  -> string/SVG serializer
```

交互画布与 SVG/PNG/PDF 导出必须使用同一 `RoutedScene` 和图元定义。导出只能关闭 hover/selection/control overlay，不能重新计算另一套布局。

### 10.5 父子视图和大场景性能

通用化不能以每次交互重跑全链路为代价。缓存和失效边界固定为：

| 产物 | 缓存键 | 失效条件 |
|---|---|---|
| Semantic Graph / Exact IR | source corpus + analyzer/registry/config digest | 源码或分析输入变化 |
| Publication profile | exact IR + profile rule digest | 语义图或 profile rule 变化 |
| canonical hierarchy/detail descriptor | IR + template binding digest | hierarchy/template 变化 |
| preset scene projection | IR + preset + frontier + binding digest | preset/frontier/semantic binding 变化 |
| expanded detail subtree | canonical node + detail template + expansion state | 该节点事实、模板或本分支展开变化 |
| routed local region | affected bounds/ports + route policy | 受影响节点、端口或障碍变化 |

实现约束：

- camera pan/zoom 只更新 SVG transform 和点阵呈现，不重建 IR、scene、详情树或路由；
- 高频拖动每动画帧最多提交一次局部 preview，未受影响根模块和兄弟详情树保持引用稳定；
- 展开只物化目标 canonical subtree，并只重算从目标到根的祖先链、受影响邻居和相关边；
- 收起直接删除派生子树，不排队执行全场景布局；
- source/Graph Delta 提交后按 changed canonical/lineage set 做局部失效，不能默认清空所有 preset cache；
- 大型首次布局和显式全图重排可进 Worker，但 pointer move、camera 和单分支展开不能等待 Worker 全图结果；
- 渲染层可按 viewport 降低非关键 label/detail 的绘制成本，但不能改变 scene 语义、命中对象或导出内容；
- 开发构建记录 projector、detail build、layout、routing 的调用次数和耗时，用测试断言未受影响分支没有重建。

性能验收直接采用 `REGRESSION_TEST_REQUIREMENTS.md` 第 1.8、3.7 节：完全展开后拖动预览在 `1 s` 内可见，松手后最终几何在 `2 s` 内提交；相机连续操作不触发布局重算。经典 Transformer、Tensor2Tensor 和 Tier A 中展开节点最多的案例都必须执行，不能只在小 fixture 上测量。

## 11. 新前端状态与组件边界

### 11.1 Store 分片

建议使用 React reducer + context，先不引入第三方全局 store：

```text
projectSlice      SourceProject、discovery、generation
semanticSlice     IR、hierarchy、evidence、diagnostics、registry
viewSlice         preset、SourceBackedScene、VisualState、selection
interactionSlice  gesture、hover、connect mode、camera preview
jobSlice          analysis/validation job
transactionSlice  intent、proposal、transaction、diff、receipt
sourceSlice       file list、buffers、editor selection
```

派生数据用纯 selector；不要把完整 state 复制到多个 `useState`。

### 11.2 模式

保留三个清晰模式，但使用同一个画布：

| 模式 | 允许操作 |
|---|---|
| 浏览 | 选择、导航、展开、搜索、证据、视图切换 |
| 布局 | 拖动、缩放、尺寸、对齐、路由、视觉样式、导出 |
| 模型 | palette、参数、增删、端口连线、源码事务 |

模式只改变可用命令和 overlay，不切换画布实现。

### 11.3 组件建议

```text
SceneStudioApp
  AppToolbar
  SourceProjectDialog
  NavigationDrawer
  ViewPresetSwitcher
  SceneCanvas                 # 由原型 App 拆出
    RoutedEdges
    SceneNode
    InlineDetailTree
    SemanticPorts
    GestureOverlay
  InspectorDrawer
    InspectPanel
    VisualPanel
    ModelEditPanel
    EvidencePanel
  SourceWorkspace
  TransactionReview
  ProblemsAndJobs
```

桌面默认保留原型的工具栏、场景列表和检查器比例；新增能力优先使用抽屉、tab 和菜单，不能把画布压缩成旧主程序的四栏工作台。

## 12. 建议目录

`scene-studio` 只新增 UI 编排和适配层；现有 `studio/src/module-registry/`、`studio/src/prototype-graph/`、`studio/src/codegen/` 是共享领域模块，应补齐后直接复用，禁止在新目录复制第二份 registry、Graph IR 或 printer。

```text
studio/src/scene-studio/
  SceneStudioApp.tsx
  main.tsx
  styles.css

  state/
    store.tsx
    actions.ts
    selectors.ts
    normalize-studio-state.ts

  api/
    client.ts
    project-api.ts
    source-api.ts
    transaction-api.ts
    generated-project-api.ts
    runtime-validation-api.ts

  domain/
    ids.ts
    source-project.ts
    semantic-intent.ts
    view-preset.ts
    source-backed-scene.ts
    generated-project.ts

  projection/
    project-to-scene.ts
    frontier.ts
    derive-publication-profile.ts
    transformer-binding.ts
    visual-state-replay.ts

  presets/
    engineering-flow.ts
    paper-publication.ts
    paper-transformer.ts
    module-hierarchy.ts
    source-call.ts
    tensor-dataflow.ts

  templates/
    registry.ts
    generic-module.ts
    generic-functional-group.ts
    transformer.ts
    attention.ts
    feedforward.ts
    add-norm.ts
    catalog.ts

  canvas/
    SceneCanvas.tsx
    scene-graphics.tsx
    gestures.ts
    canvas-viewport.ts
    expansion.ts
    detail-layout.ts
    atomic-hierarchy.ts
    routing.ts
    export.ts

  commands/
    visual-commands.ts
    semantic-commands.ts
    capability.ts
    transaction-controller.ts
    graph-draft-controller.ts
    generated-project-controller.ts

  source/
    SourceWorkspace.tsx
    codemirror.ts
    source-selection.ts
    GeneratedProjectReview.tsx
    generated-source-map.ts

  panels/
    Inspector.tsx
    Navigation.tsx
    TransactionReview.tsx
    ProblemsAndJobs.tsx
    RuntimeValidation.tsx

  fixtures/
    visual/
    source-projects/

  tests/
    tier-a/
```

开始迁移时可先保留原型文件名，待第一阶段测试全部通过后再拆目录。禁止一次性改名和改行为，避免无法定位交互回归。

## 13. 分阶段实施

### 阶段 0：冻结基线并建立副本

任务：

- 对原型执行 TypeScript、Vitest、静态构建和 Playwright 基线；
- 保存关键桌面/移动截图和路由指标；
- 建立原型源码清单与 digest；
- 审计当前 `studio/src/scene-studio/` 是否是原型等价副本；
- 只把副本接到独立开发入口，不切换正式 `main.tsx`；
- 给旧主程序标记 feature freeze。

出口：副本在没有 API 数据时与原型行为一致，原型目录零改动。

### 阶段 1：单画布壳层和状态边界

任务：

- 从 `App.tsx` 拆出 `SceneCanvas`，不改变 gesture 和渲染；
- 建立七个 store slice；
- 接入现有 `/api/state`，只显示项目元数据；
- 视觉 fixture 和 source-backed scene 共用画布；
- 抽出共享屏幕/导出图元。

出口：原型 30 场景和 1350 组合无回归；不存在第二个 canvas renderer。

### 阶段 2：“从源码构建”纵向切片

任务：

- 项目选择、discovery、入口、环境和 config；
- analysis job 启动、轮询、取消和 stale generation；
- `AnalysisEnvironmentManifest`、入口调用配置和 framework form capability hydrate；
- `normalizeStudioState()`；
- Exact IR -> `SourceBackedScene` 最小投影；
- 选择节点后显示 source excerpt/evidence；
- 默认 `engineering-flow`。

出口：`tests/fixtures/frontend_v2/transformer_classic/` 可以完全从源码打开，不依赖 `SCENARIOS`。

### 阶段 3：Transformer 二源多视图

任务：

- 从第 6.2 节两个权威归档建立固定 digest 的 Source Project manifest；
- 完成参数化 Transformer template 和稳定 slots；
- 完成 `engineering-flow`、`paper-publication` 和旧 `paper-transformer` alias；
- 将四个手写场景降为视觉 golden，不再是运行时数据；
- named mask/memory/target-space ports；
- preset 独立 VisualState 和 camera；
- 对折叠、单模块展开、全部展开和论文双列执行结构/截图/路由/性能 golden。

出口：每份源码的 IR digest 在切换视图前后不变；两个 preset 都能递归展开到 attention/FFN/Add & Norm，并与最小原型达到第 15.2 节定义的硬基准。

### 阶段 4：Tier A 通用化和性能门禁

任务：

- 用同一 SourceCorpus -> IR -> projector 链分析 `fixtures/tier_a` 五个项目；
- 为每个项目生成 `engineering-flow` 和 `paper-publication`，不增加项目专用 scene builder；
- 恢复 module instance 父子关系、functional semantic group、named boundary ports 和重复/控制区；
- 完成结构 profile 推导及 generic glyph/detail fallback；
- 增加目录/文件/非语义类名重命名的 metamorphic tests；
- 增加 production bundle 禁止 import fixture/SCENARIOS 和 fixture ID 分支的静态门禁；
- 关闭 `architecture_profile -> analyze_*` 专用分派，以声明式 Pattern Pack/annotation 取代 family canonical graph builder；
- 加入 `stage-8.md` 七类关闭 Pattern Packs 的 holdout，并要求 generic 双视图、层级和 evidence 成立；
- 实现 canonical hierarchy、detail subtree、preset projection 和局部路由缓存；
- 按 `REGRESSION_TEST_REQUIREMENTS.md` 第 1.8、1.9、3.7、3.9 节执行标准/论文视图和完全展开性能测试；
- 每次 Tier A 修复后重新执行两份 Transformer golden，不允许更新基准来掩盖退化。

出口：五个 Tier A 项目均从源码自动生成非空、可展开、可定位证据的标准流程图和论文级视图；两个 Transformer 的结构、视觉、交互和性能 golden 零回退。

### 阶段 5：视觉编辑与持久化

任务：

- 将原型 visual patch 映射到 `/api/patch` 和 `/api/patch-batch`；
- 服务端 visual undo/redo；
- 对齐、分布、固定、样式、相机和展开持久化；
- lineage-based visual replay；
- 统一 SVG/PNG/PDF/JSON 导出。

出口：刷新浏览器后视觉状态恢复，且 exact IR digest 不变。

### 阶段 6：视图增删改和连线回写源码

任务：

- registry palette 和 named port overlay；
- `PrototypeGraphDocument`、拓扑草稿 session 和独立 draft history；
- schema 参数检查器、符号 Shape、成本和 blocking diagnostics；
- parameter、replace activation、insert norm；
- create/delete/connect/disconnect intent；
- capability decision、preview overlay、impact preview；
- `ValueOrigin`、`EditTargetScope` 和共享实例/调用/Repeat 影响范围确认；
- 第一批 LibCST lowering adapter，明确 adapter 的源码形态和 anchor 前置条件；
- transaction prepare/verify/review/commit/discard；
- observed delta 和 targeted tests；
- `RoundTripConformanceReport`、intent 重试幂等和 no-op 零写入；
- 静态/runtime/export 冲突进入 `DiscrepancyRecord`，不覆盖 canonical facts；
- commit 后重分析和局部布局保持。

出口：至少完成第 15.5 节既有源码端到端事务用例；任意新增、删除或连线如果没有受支持 adapter，都明确阻断且不改源码；提交后两个 Transformer 和受影响 Tier A 视图通过视觉门禁。

### 阶段 7：源码生成、源码工作区和高级能力

任务：

- CodeMirror 6 staged buffer；
- anchor/evidence/diagnostic 双向定位；
- freeform source transaction；
- 结构化 PyTorch Code IR、确定性 printer 和双向 source map；
- Generated Source Project prepare/validate/review/materialize 生命周期；
- `Input -> Conv2d -> ReLU` 构图、生成、物化和重新分析纵向切片；
- DefinitionDraft、ModuleRef、Repeat 和复合模块边界；
- module/source 双导航和统一搜索；
- 受限 worker、验证配置、runtime receipt 和确定性 replay；
- train/eval、动态 Shape、PRNG、alias/mutation、梯度、buffer 和共享身份的 semantic oracle；
- checkpoint/state asset 绑定、`StateMigrationPlan` 和 source-only/source+state 双结果；
- 多文件 transaction journal、外部变更 re-prepare、崩溃恢复和 rollback receipt；
- encoding/newline/file mode/symlink 策略；
- `.archcanvas` 离线 bundle、support matrix、环境/产物 digest inventory 和协议迁移 fixture；
- pattern overlay；
- module contract maintenance；
- 其余 View Preset。

出口：生成项目能在临时目录通过编译和静态重分析，经评审后物化为新 Source Project，并对重新打开的标准/论文视图执行视觉门禁；旧主程序功能清单逐项标为“已迁移”或“明确取消并有理由”。

### 阶段 8：正式切换和删除旧前端

任务：

- 让 `studio/src/main.tsx` 只渲染 `SceneStudioApp`；
- 更新 Vite build、Python static bundle 和启动脚本；
- 运行完整 Python/TypeScript/Playwright/视觉验收；
- 对 Round-trip、state compatibility、无 Pattern Pack holdout、事务崩溃恢复和 bundle verify 执行发布门禁；
- 在一个发布周期内保留旧前端 tag/branch 和 bundle 回滚点；
- 验收后删除旧 `app/main-view/visual-kernel/shell/inspector` 中不再被使用的实现；
- 删除前以 `rg` 和 TypeScript 构建证明零引用。

出口：生产入口只有原型派生画布；旧前端不再打包；原始最小原型仍可独立运行。

## 14. 功能优先级

### P0：切换前必须有

- 原型全部交互；
- 从源码构建；
- 两份 Transformer 源码；
- 通用自动 Source-to-View pipeline，不含按项目/fixture 身份分支；
- production analyzer 不再通过 `architecture_profile` 返回专用 family canonical graph；
- Tier A 五个项目的标准流程图和论文级视图；
- 七类关闭 Pattern Packs 的 holdout 可生成通用双视图；
- 两份 Transformer 标准/论文视图与最小原型的硬 golden；
- 父子模块递归展开和完全展开交互性能门禁；
- source/evidence 定位；
- visual persistence/undo/redo；
- Registry 驱动创建、严格 named ports、Shape 和 blocking diagnostics；
- 参数修改、节点增删、端口连线的事务入口，且至少一组既有源码 adapter 可以正式提交；
- 参数 `ValueOrigin`、`EditTargetScope` 和受影响共享对象必须可审查；
- `Input -> Conv2d -> ReLU` 可以生成、验证、物化并从新源码重新打开；
- 三类 `RoundTripConformanceReport`、no-op 零写入和 intent 重试幂等；
- framework/form/action 能力矩阵；未验证能力明确 unavailable/partial；
- 绑定 checkpoint 的事务必须产生状态兼容性结论，不能把源码成功误报为训练资产兼容；
- 多文件提交具备 journal、rollback proof 和崩溃恢复；
- diff/review/commit/discard；
- SVG/JSON 导出；
- 快速静态验证。

### P1：切换发布必须有

- module/source 导航；
- 搜索、诊断、任务和取消；
- PNG/PDF；
- Source Workspace；
- 其余 view presets；
- 对齐、分布、固定和主题；
- 扩展的 topology draft/codegen rule 和双向 source map；
- 复合模块、Repeat、ModuleRef 和模块版本迁移；
- runtime receipt/trace 的显示与显式授权入口；
- `AnalysisEnvironmentManifest`、lockfile/adapter/analyzer/schema digest 和可复现等级；
- 已支持有界变换的 `StateMigrationPlan` 物化与隔离验证；
- `.archcanvas` 离线审计 bundle 和完整 inventory verify；
- 持久化协议 major/minor 兼容、拒绝和迁移 receipt；
- module contract maintenance。

### P2：可在新基座上继续

- 可选 Tree-sitter 即时语法；
- ELK 显式重新布局；
- 跨框架高级 lowering；
- 大图虚拟化和 Worker 路由。

P2 不得成为继续使用旧前端的理由。

## 15. 测试与验收

### 15.1 原型零回归

每轮涉及 canvas、analyzer、registry、pattern/template binding、source-to-view mapping、hierarchy、layout、routing、detail、源码事务、codegen 或 export 的修改都必须执行本节。源码修改提交后和生成源码物化后，必须重新分析结果源码并对新视图执行同一门禁，不能以“只改后端/只改生成器”为理由跳过视觉检查。

从 `studio/` 目录执行 `REGRESSION_TEST_REQUIREMENTS.md` 第 2 节的完整命令，而不是只运行新增测试：

```bash
npx vitest run --exclude 'e2e/**' --exclude 'tools/export-p0-acceptance.test.ts'
npx tsc -p prototypes/scene-visual-lab/tsconfig.json --noEmit
npm run prototype:build
git diff --check
```

并遵循 `REGRESSION_TEST_REQUIREMENTS.md`：

- 负坐标、向左拖动和无限画布；
- atomic/recursive A/B；
- 父框包含和同级避让；
- 端口吸附、最短合法路径和 foreground edge；
- 展开/收起确定性；
- 屏幕/导出一致；
- 第 1.9、3.9 节论文级视图的列顺序、底边锚定、侧挂条件输入和递归层级；
- 第 1.8、3.7 节完全展开交互性能；
- 30 场景和完整组合矩阵。

自动化通过后还必须执行第 3 节真实浏览器截图检查，并记录场景、preset、展开层级、拖动方向、路由指标和性能结果。新程序不能只跑旧主程序测试、静态 SVG 或 DOM 数值后宣布通过。

### 15.2 Transformer 硬性黄金基准

对第 6.2 节两个权威归档分别断言：

- 一个 Source Project、一个 source digest、一个 Exact IR digest；
- 标准流程图和论文级视图均由源码自动生成，运行时不读取四个手写场景；
- 切换 preset 不改变 canonical node/edge/tensor/port 集；
- view node 可以不同，但 binding 必须回到同一 canonical IDs；
- Encoder/Decoder、mask/bias、memory、FFN 和输出共享按源码证据出现；
- paper 视图双列、底入顶出，展开后 mask/memory 连接内部 slot；
- engineering 视图左到右，保留调用和条件输入；
- 展开到 attention 后 Q/K/V、score、scale、mask、softmax、V、concat 和 output projection 的 slot 稳定；
- 父子模块、直接父级包含、portal chain、atomic/recursive A/B 与最小原型一致；
- 折叠、单独展开 Encoder/Decoder、递归全展开、收起恢复、拖动和导出行为与最小原型一致；
- 节点相对顺序、论文双列、主流向、条件节点侧挂、图例种类和语义端口属于结构 hard assertions；
- deterministic desktop/narrow screenshots 使用最小原型 golden；任何未审核像素差异、遮挡、重叠、断线、路由指标增加或性能回退都失败；
- 缺失证据的 slot 不得伪装 exact。

黄金文件只能在明确的视觉设计变更评审中更新，不能因 Tier A 修复、缓存优化、analyzer 改写、源码事务或 codegen 改动自动重录。若通用结果和 Transformer golden 冲突，先修复通用算法或声明式规则，禁止增加项目身份分支。

### 15.3 Tier A 自动多视图矩阵

对 `fixtures/tier_a/{transformer,autoformer,itransformer,patchtst,timemixer}` 逐项运行：

1. 从 config/test manifest 选择入口和输入规格，捕获多文件 SourceCorpus；
2. 生成非空 `engineering-flow` 与 `paper-publication`；
3. 校验两个 preset 共享 source/exact IR digest 和 canonical 对象；
4. 校验入口到子模块、深层子模块或 evidence-backed boundary 的父子层级；
5. 校验输入、条件端口、分支/合流、重复区、Shape 和 opaque diagnostics；
6. 对折叠、单模块展开、全部展开、atomic/recursive、拖动、缩放、窄视口和 SVG 导出截图；
7. 运行目录/文件/非语义类名重命名测试，规范化语义和视图结构不变；
8. 禁用可选 family pattern pack，仍可通过 generic hierarchy/glyph 生成两种可用视图；
9. 静态检查 production bundle 不引用 `fixtures/tier_a`、`SCENARIOS` 或 fixture-specific scene builder；
10. 每个案例完成后立即重跑第 15.2 节两个 Transformer golden。

Tier A 论文级视图应用 `REGRESSION_TEST_REQUIREMENTS.md` 第 1.9、3.9 节的共同视觉原则，但按真实结构 profile 调整：只有 evidence 证明 encoder/decoder 时才要求双列；single-stack、multi-scale 和 decomposition-merge 分别使用紧凑单栈、多泳道和稳定分支/合流，不能为满足截图补造模块。

### 15.4 交互契约

Playwright 至少覆盖：

- 画布 pan/zoom/fit；
- 节点拖动/resize 和释放提交；
- 父子递归展开、子节点拖动、复位；
- 选择在画布、导航、源码和检查器之间同步；
- preset 切换后 selection 保持；
- 连接模式的端口过滤和取消；
- visual undo/redo 不影响源码；
- transaction active 时编辑锁；
- 桌面和移动视口无重叠、文本不溢出。

所有画布 E2E 需要截图和 canvas/SVG 非空像素检查。

### 15.5 源码事务端到端用例

切换前至少通过：

1. 在 Classic Transformer 修改 `num_heads` 或另一个有精确 anchor 的参数：源码格式/注释保留，observed delta 精确，commit 后视图更新。
2. 将一个受支持 activation 替换为另一个 registry activation：shape 不变，源码和 IR 同步。
3. 在受支持顺序边插入 LayerNorm：节点、端口、边和源码调用均出现，undo 不能误当成视觉 undo。
4. 从兼容 output port 向 input port 建立受支持连接：policy 明确，预期/实际 delta 一致。
5. 尝试不兼容端口、歧义 source anchor 或未知控制流：操作被阻断，源码零变化。
6. transaction 准备后外部修改源文件：commit 以 stale 失败，不能 fuzzy merge；使用原 semantic intent 在新 snapshot 上 re-prepare，重新解析 anchor、生成 diff 并执行全部门禁。
7. 自由源码 buffer 修改：staged -> validate -> review -> commit -> reanalyze 完整闭环。
8. 同一 `intentId + baseSourceDigest` 重试：不得重复应用，返回原事务或等价 receipt。
9. literal、config key、共享 module、多 call site 和 Repeat template 的参数修改：作用域和 affected objects 与 review 一致。

每个成功事务都要在 commit/reanalyze 后生成标准和论文视图，运行第 15.1 节视觉门禁，并断言 Graph Delta 外未受影响的 canonical subtree、preset VisualState 和布局保持稳定。涉及两份 Transformer 时必须额外通过第 15.2 节；涉及 Tier A 时必须通过对应第 15.3 节行。

### 15.6 构图、代码生成和运行验证

新增领域测试至少覆盖：

1. registry definition ID 唯一、ref/digest 固定、默认参数可序列化，重复或缺失 rule 引用启动即失败；
2. named port 的方向、required、cardinality、relation、ordered ordinal 和 tensor contract 正反例；
3. Known/Symbolic/Unknown/Error Shape 的传播、局部阻断和诊断对象定位；
4. 共享 parameter group 只计一次参数，同一实例的多个 call site 分别计 FLOPs；
5. printer 对 tuple、嵌套 tuple、多输出、共享 module、functional op、loop 和安全 Python literal 的 golden tests；
6. graph/node/port/edge/parameter 与 generated source span 的双向选择，歧义选择不得静默猜测；
7. 既有源码 rewrite 和 greenfield project generation 使用不同 command/receipt，失败时不能互相降级；
8. generated project 在 materialize 前完成 Python compile、导入静态解析、入口发现和 Exact IR 重分析；
9. graph/registry/generator/input 任一 digest 变化后 generated/runtime receipt stale；
10. runtime worker 的禁网、只读输入、CPU/内存/PID/文件大小/超时和进程组终止；
11. 多输入、多输出、固定 seed、两次 replay digest 和 nondeterministic 结果；
12. unsupported graph edit、codegen rule 缺失、目标目录冲突和未授权 runtime 均产生零源码写入。
13. train/eval、Dropout、BatchNorm buffer、in-place op、tensor alias、hook 和参数共享的 observation/limitation；
14. preserve-semantics 事务的输出容差、梯度、buffer 和共享身份 oracle，以及行为变化事务的未影响区域 oracle；
15. 同一 SourceCorpus 与 analysis input manifest 重跑得到相同规范化 IR/scene digest；
16. 各 framework form 对 static/runtime/parameter/structural/codegen/commit 分别返回 verified/partial/experimental/unavailable。

端到端必须包含第 8.18 节的 `Input -> Conv2d -> ReLU` 两条用例：greenfield 生成后重新打开得到同构图；existing-source 只修改精确 anchors 并保留无关格式和注释。之后再增加 Add、MHA、LSTM、Repeat 和 ModuleRef，不能以单输入节点通过代替多输入/多输出测试。

每个 materialized generated project 都必须作为全新 Source Project 重新打开，生成 `engineering-flow` 和 `paper-publication`，再执行第 15.1 节的自动化与浏览器视觉检查。比较 Graph Draft 与重分析 IR 的节点、端口、边、父子关系和 source map；不能只证明 Python 可编译而不检查生成源码对应的视图。

### 15.7 Digest 和权限不变量

自动测试必须证明：

- Visual Patch 前后 source/exact IR digest 不变；
- View Preset 切换前后 source/exact IR digest 不变；
- failed/discarded/proposal-only intent 不产生 source write；
- commit receipt 列出的 source writes 与真实修改文件完全一致；
- analysis 不 import/execute 目标工程；
- runtime trace 未授权时不能由 UI 暗中启动；
- generated source preview 不能直接写入用户目录；
- generated project 的 materialize receipt 与真实文件清单和 digest 完全一致；
- RoundTrip report 绑定 source、IR、draft、normalization rule 和 expected/observed delta digest；
- 相同 intent 重试不产生第二次 source write，no-op intent 不创建伪修改事务；
- runtime/export/checkpoint evidence 不静默删除或改写 SourceCorpus 可证明的 canonical facts；
- 缺失框架包/provider/自定义对象时只返回 unavailable，不触发联网安装；
- 目录/文件/非语义类名变化不改变规范化架构和视图结构 digest；
- production code 不读取 fixture ID、权威归档 digest 或手写 scene 来决定投影；
- 归档导入不能路径穿越或写到 workspace 外。

### 15.8 性能预算

初始预算：

| 操作 | 目标 |
|---|---|
| 拖动 preview | 常规场景保持 60 fps 感知，无网络请求 |
| 单次 pointer move | 不重建 IR，不执行全图布局 |
| preset 切换 | 已有 IR 下 300 ms 内出现首个 scene |
| 展开/收起 | 只重算受影响 detail/layout/routing |
| 完全展开拖动 preview | `1 s` 内可见，且未受影响根/兄弟不重建 |
| 完全展开松手提交 | `2 s` 内完成最终几何和指标刷新 |
| source selection -> anchor | 100 ms 内本地定位，缺 buffer 时再请求 |
| 大型自动布局 | Worker 中运行，可取消，结果显式应用 |

性能不达标时先做 selector memoization、局部重算和 Worker；不要引入第二画布。

### 15.9 Round-trip 和编辑作用域验收

建立独立 conformance suite，不能用普通单元测试名称中的 `round_trip` 代替系统级报告。至少覆盖：

1. 同一 Source Project 连续分析两次，Exact IR、hierarchy、bindings 和每个 preset 的规范化 scene digest 一致；
2. `SetParameter`、`ReplaceActivation`、`InsertLayerNorm` 各自产生 expected/observed delta 精确匹配的报告；
3. Graph Draft 生成源码、物化、重新打开后，节点、named ports、边、父子关系、Repeat/control region、参数共享和 Shape 约束规范化同构；
4. 对 generated source 再次执行 printer 不产生新的源码变化，source map 仍绑定同一 canonical/value identity；
5. no-op、失败、discarded、proposal-only 和重复 intent 均为零新增 source write；
6. 修改 config key 时报告所有受影响实例，选择 module instance/call site 但源码只有共享定义时必须阻断或要求改 scope；
7. 共享 embedding/projection、同一 module 多 call site、共享 Repeat template 和独立 `ModuleList` 的作用域不能混淆；
8. Graph Delta 外的 canonical subtree、evidence、其他 preset VisualState 和未受影响源码字节保持不变。

每份报告必须由后端根据实际产物计算，前端不得提交 `semanticIsomorphism=exact`。报告失败时事务不能进入 review-ready；`equivalent` 只能由版本化 normalization rule 产生，并在 review 中列出被忽略的全部差异。

### 15.10 状态、证据、恢复和交付验收

发布前至少覆盖以下矩阵：

| 测试域 | 必须证明 |
|---|---|
| 状态 preserve/rename | 参数、buffer、optimizer slot 和共享身份逐项映射，before/after digest 可复核 |
| Shape 改变 | 无批准 reshape/initializer rule 时为 blocked；不得借 `strict=False` 静默丢权重 |
| source-only | 源码可提交，但旧 checkpoint 明确 detached/unknown，UI 不显示可继续训练 |
| source+state | 隔离迁移、严格加载、最小 replay、review 和产物 commit 全部通过 |
| 不可信状态 | pickle/整模型默认不执行；只允许受限 metadata/weights-only 路径或明确阻断 |
| 证据冲突 | static/runtime/export/checkpoint 差异生成 `DiscrepancyRecord`，未执行分支不从 IR 消失 |
| 动态运行 | mode、input profile、动态 Shape、seed/PRNG、backend/device、路径覆盖和限制全部进入 receipt |
| stale re-prepare | 旧事务保持 stale；新事务从 semantic intent 重新解析，不继承旧 anchor 成功状态 |
| 中途崩溃 | 在每个文件替换点注入故障，重启后只能得到完整 after 或已证明的完整 before 状态 |
| 文件保真 | UTF-8/非 UTF-8 Python encoding、BOM、LF/CRLF、末尾换行和 mode 按策略保留；symlink 越界被拒绝 |
| 环境可复现 | 环境、lockfile、adapter/analyzer/schema digest 变化使相关缓存和 receipt stale |
| 离线 bundle | inventory 对 missing/extra/modified file 均失败；绝对路径和未授权源码/checkpoint 不泄漏 |
| 协议迁移 | 未知 major 被拒绝，支持的旧 minor/major 通过固定 migration 和 receipt 读取 |

PyTorch 首批状态 fixture 至少包括 Linear 参数重命名、BatchNorm buffer、tied embedding/output projection、增加无权重 ReLU、插入有权重 LayerNorm 和改变 Linear 输出维度。Keras/JAX/ONNX 只执行 support matrix 对应 form 已声明的单元格；未验证单元格必须测试 unavailable，而不是跳过后仍显示 supported。

## 16. 切换门禁

只有同时满足以下条件，才允许把旧主程序从构建中移除：

- 原始原型仍可单独构建和运行；
- 新程序通过原型全部交互回归；
- 两份 Transformer 都从第 6.2 节固定摘要的权威归档生成，而不是从手写场景或替代源码生成；
- 两份 Transformer 的标准/论文视图通过第 15.2 节结构、截图、交互、路由和性能硬基准；
- Tier A 五个项目都由同一通用链路生成标准流程图和论文级视图，并通过第 15.3 节；
- `stage-8.md` 七类 holdout 在关闭 Pattern Packs 后仍通过通用结构、层级、evidence 和双视图门禁；
- production analyzer/projector 不按项目名、路径、归档 digest、fixture ID 或入口类名选择专用构图器；
- production analyzer 不再通过 `architecture_profile` 直接调用 Autoformer/iTransformer/PatchTST/TimeMixer canonical graph builder；
- 父子模块、functional semantic group、boundary ports 和递归展开来自源码证据；
- 第 15.5 节既有源码事务和第 15.6 节构图/代码生成用例通过，所有负例零写入；
- `Input -> Conv2d -> ReLU` 生成项目可以物化、重新打开并恢复同构 Exact IR；
- Source-to-View、Intent-to-Source 和 Draft-to-Source 三类 RoundTrip report 全部通过，no-op 和 intent 重试满足幂等；
- create/delete/connect 不再以“前端能画出 draft”冒充完成：支持项有正式 receipt，不支持项明确阻断；
- 参数编辑显示 ValueOrigin、EditTargetScope 和全部受影响实例/调用/共享组；
- 项目打开、分析任务、搜索、证据、诊断、验证、源码工作区和导出可用；
- runtime receipt/trace 具备显式授权和隔离限额，module contract maintenance 已完成迁移；
- framework/form/action support matrix 与实际 adapter 门禁一致，不存在框架级过度声明；
- 绑定状态资产的事务具有独立 state/training/inference compatibility 结论，source-only 不冒充 checkpoint 兼容；
- 多文件事务通过故障注入、journal 恢复和 rollback proof，且文件 encoding/newline/mode 策略通过；
- AnalysisEnvironmentManifest、离线 bundle inventory 和支持的协议迁移 fixture 可验证；
- 源码事务和生成源码在重新分析后都执行 `REGRESSION_TEST_REQUIREMENTS.md` 的标准/论文视觉检查；
- 完全展开的相机、拖动、收起和局部重算通过第 15.8 节性能预算；
- 屏幕和导出使用同一 scene；
- 当前主程序功能清单有逐项迁移记录；
- TypeScript、Python、schema、Playwright 和视觉测试全部通过；
- 新入口 bundle 不引用旧 `StudioApp`、`ArchitectureCanvas` 或 `visual-kernel`；
- 有已验证的回滚构建。

“代码已经复制到 `studio/src/scene-studio/`”不构成完成；“页面看起来像原型”也不构成完成。

## 17. 风险与处理

| 风险 | 处理 |
|---|---|
| 把四个 Transformer 继续维护成四份图 | 强制 Source Project 与 View Preset 分离；测试 IR digest 不变 |
| 为通过 Transformer golden 把产品写成专项演示器 | 两份 Transformer 只作输出 hard baseline；Tier A、重命名 metamorphic test 和 bundle 静态门禁证明通用性 |
| 为每个 Tier A 模型增加手写 mapper | 只允许 evidence-driven registry/pattern/template predicate；generic fallback 必须独立生成两种视图 |
| 继续用 `architecture_profile` 分派专用 analyzer | 用无 Pattern Pack holdout 建立通用恢复门禁；family 知识只进入声明式 annotation/template binding |
| 把所有论文视图强制画成 Transformer 双列 | 先推导结构 profile；只对真实 encoder/decoder 使用双列，其他结构使用单栈、多尺度或分解/合流布局 |
| 通过重录 golden 掩盖通用化回归 | golden 更新需独立视觉设计评审；普通修复、缓存和 analyzer/codegen 改动禁止自动更新 |
| 为兼容原型把正式语义降级为 node-to-node edge | scene binding 物化 named ports；语义命令只接受 port ID |
| 新 UI 再次变成单体 | store slice、command controller 和纯 projector 分层；组件不得直接调用全部 API |
| 旧 visual-kernel 又被引入 | 构建 lint/`rg` 门禁禁止从新目录 import 旧内核 |
| 视觉手势误改源码 | VisualCommand/SemanticIntent 使用不相交联合类型和不同 endpoint |
| 重分析后用户布局丢失 | canonical/lineage/slot ID 重放，禁止 label 匹配 |
| 图、源码各自可用但往返后语义漂移 | 三类 RoundTripConformanceReport、版本化 normalization 和 fixed-point/no-op 门禁 |
| 修改一个展示节点意外影响全部共享实例 | ValueOrigin + EditTargetScope + affected object review；共享定义无法拆分时阻断 |
| 自动布局破坏空间记忆 | 默认增量布局；ELK 只在用户显式命令时应用 |
| 通用父子展开导致交互卡顿 | 按 IR/preset/subtree/local route 分层缓存，camera 不重建，按第 1.8/3.7 节测调用次数与 `1 s/2 s` 门槛 |
| LibCST 不能证明复杂动态 Python | opaque/proposal-only；不进行猜测式写回 |
| lowering 失败后用全文件生成结果覆盖手写源码 | source strategy 固定；rewrite-existing 和 generate-project 使用不同 command、receipt 和目标目录策略 |
| 代码预览被误当成可提交项目 | Generated Source Project 必须经过后端临时 workspace、compile、重分析、review 和 materialize |
| 生成源码在主服务中直接执行 | 一次性受限 worker、禁网和资源上限；未授权不运行，runtime evidence 不替代静态事实 |
| 单次 runtime/export 图覆盖未执行源码分支 | 证据分层、路径覆盖和 DiscrepancyRecord；动态证据只增加 observation/condition |
| 源码提交成功但 checkpoint 已失效 | 独立 StateMigrationPlan 与 source/state/training/inference 四类结果；未知兼容性不显示成功 |
| 使用 `strict=False` 或按位置复制掩盖权重丢失 | 每个 parameter/buffer/optimizer slot 明确 preserve/rename/reshape/initialize/drop/block |
| 框架级 supported 掩盖某种源码形态不可编辑 | framework form/action matrix 驱动 UI、API 和 release support，未验证单元格为 unavailable |
| 多文件提交中途崩溃留下混合版本 | 持久化 journal、逐文件 digest、启动恢复、备份和 rollback proof，不声称文件系统级原子 rename |
| 环境变化后复用过期分析或运行结论 | AnalysisEnvironmentManifest 和 lockfile/adapter/analyzer/schema digest 参与 stale 判断 |
| 复合模块只存在浏览器 localStorage | DefinitionDraft 经评审发布固定版本，ModuleRef 绑定 definition digest |
| T2T 依赖面过大 | SourceCorpus 预算、静态可达闭包、partial diagnostics、固定归档 digest |
| 源码编辑器和画布历史混淆 | buffer undo、visual undo、source transaction 三套边界分别呈现 |
| 当前未提交 `scene-studio` 修改被覆盖 | 实施阶段先审计和 diff；不得重新复制覆盖用户工作 |
| 过早删除旧主程序失去对照 | feature freeze 立即生效，物理删除延迟到切换门禁之后 |

## 18. 联网核对结论与来源

本指南在 2026-10-01 重新核对了下列官方资料，并结合仓库现有实现作出选型：

- [LibCST: Why LibCST](https://libcst.readthedocs.io/en/latest/why_libcst.html)：LibCST 是可重新打印的 lossless CST，同时提供接近 AST 的语义节点；因此用于正式 Python source anchor 和保格式改写。
- [Tree-sitter: Advanced Parsing / Editing](https://tree-sitter.github.io/tree-sitter/using-parsers/3-advanced-parsing.html#editing)：编辑后可先更新旧树位置，再将旧树传入 parser 进行结构共享的增量解析；因此仅适合作为编辑器即时反馈层。
- [CodeMirror System Guide](https://codemirror.net/docs/guide/)：编辑器 state/document 不可变，修改通过 transaction/ChangeSet，支持位置映射和 viewport 渲染；与 staged source buffer 模型一致。
- [ELK Layered](https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html)：支持分层方向、端口约束、正交路由、compound graph 和跨层边；因此适合显式批量重排，不适合替代原型实时交互。
- [TensorBoard Graphs](https://www.tensorflow.org/tensorboard/graphs)：父节点展开/收起用于在概念层和算子层之间切换，支持继续保留原型的层级阅读模式。
- [PyTorch MultiheadAttention](https://docs.pytorch.org/docs/stable/generated/torch.nn.MultiheadAttention.html)：用于核对 Q/K/V、mask 和输出端口语义。
- [PyTorch `torch.export`](https://docs.pytorch.org/docs/2.14/user_guide/torch_compiler/export.html)：导出图提供 sound/normalized 计算 IR、调用签名和动态 Shape 约束，但会内联子模块；训练 IR 可能包含 mutation/alias，数据依赖控制流仍有边界。因此它是运行语义 sidecar，不替代源码层级。
- [PyTorch Saving and Loading Models](https://docs.pytorch.org/tutorials/beginner/saving_loading_models.html)：`state_dict` 同时包含参数和 registered buffers，optimizer state 独立；整模型 pickle 与类路径绑定，结构重构后脆弱。用于确定 StateMigrationPlan 和默认不加载不可信整模型对象。
- [Keras Serialization and Saving](https://keras.io/guides/serialization_and_saving/)：模型资产包含 architecture/config、weights、optimizer、loss/metrics，自定义对象需要 config/注册机制；因此“可重建架构”不能代表训练状态兼容。
- [Flax Save and Load Checkpoints](https://flax.readthedocs.io/en/latest/guides/checkpointing.html)：checkpoint 通常是参数、其他 state 和 optimizer state 的 PyTree，结构变化需要显式 checkpoint surgery/transform；用于 JAX/Flax 状态迁移边界。
- [ONNX Shape Inference](https://onnx.ai/onnx/repo-docs/ShapeInference.html)：Shape inference 不保证完整，动态 Reshape、自定义算子和符号算术会产生 unknown；不得把 partial 推导伪装成 exact。

本地 `DL-Playground/` 只作为行为和架构研究样本：Registry 驱动节点、Graph IR、依赖调度 Shape、代码 span、复合模块和运行 trace 是可重新设计的思路；弱语义 handle、按边顺序取输入、字符串/正则 codegen、长期进程 `exec` 和不完整隔离不进入目标方案。当前 checkout 根目录未发现明确许可证文件，因此禁止直接复制其 TypeScript/TSX、样式和测试夹具。

仓库内事实优先级高于通用网页建议：

1. 当前源码和测试；
2. schemas 与 transaction receipts；
3. 固定上游源码及其 digest/许可证；
4. 官方文档；
5. 其他设计参考。

## 19. 现有资料的继续使用方式

原指南中有价值但不再适合放在主实施链路中的细节，继续由以下文件承载：

- `references/SOURCE_TRACEABILITY.md`：基础模块、Classic Transformer、Tensor2Tensor 的源码证据；
- `references/MODEL_FAMILY_TRACEABILITY.md`：模型家族模板的证据和 schematic 边界；
- `references/UPSTREAM_SOURCES.sha256` 与 `NEW_UPSTREAM_SOURCES.sha256`：固定上游摘要；
- `BOTTOM_UP_ATOMIC_ROUTING.md`：原子收束算法；
- `REGRESSION_TEST_REQUIREMENTS.md`：画布和视觉门禁；
- 根目录 `README.md`、`PRODUCT.md`、`DESIGN.md`、`docs/contracts/protocols.md`、`docs/support-matrix.md`：当前正式后端能力和协议。

实现人员不应从本文复制旧场景坐标或源码行号。源码更新后，证据与 anchor 必须由 analyzer 重新生成；视觉模板只消费稳定 binding。

## 20. 第一条实施切片

推荐先完成一个可以真实证明架构方向的切片，而不是先搭完整 shell：

```text
复制的 Scene Visual Lab
  -> 点击“从源码构建”
  -> 打开 pytorch_transformer_original.zip
  -> 选择 pytorch_transformer_original/transformer.py:Transformer
  -> 固定 AnalysisEnvironmentManifest、入口调用和 framework form capability
  -> v2 静态分析
  -> projectToScene(engineering-flow)
  -> 原型画布显示并可递归展开
  -> 切换 paper-publication
  -> 选择 attention 定位源码/evidence
  -> 修改一个有精确 anchor 的参数
  -> prepare/verify/review/commit
  -> 重分析
  -> expected/observed delta 与 RoundTripConformanceReport 通过
  -> 若绑定 checkpoint，显示独立 StateMigrationPlan/compatibility 结果
  -> 两个 preset 同步更新且原布局按 lineage 保持
```

后续顺序固定为：

1. 对 Tensor2Tensor 权威归档完成同样链路，冻结两个 Transformer hard golden；
2. 在不增加项目身份分支的前提下跑通 Tier A 五项目和结构 profile；
3. 删除 `architecture_profile -> analyze_*` canonical graph 分派，跑通七类关闭 Pattern Packs 的 holdout；
4. 完成父子递归展开、局部缓存及完全展开性能门禁，并重跑 Transformer golden；
5. 完成第 8.18 节 `Input -> Conv2d -> ReLU` 的 greenfield 生成与 existing-source 改写双链路；
6. 为 literal/config/shared/Repeat 参数作用域、no-op/重试幂等和生成源码 fixed point 生成 RoundTrip report；
7. 完成至少一组 checkpoint preserve/rename/block、事务崩溃恢复和离线 bundle verify；
8. 对修改后源码和生成后源码重新执行 Tier A/Transformer 适用的标准与论文视觉检查。

若任一链路依赖 `SCENARIOS` 中的节点数组、fixture/project ID、旧 `ArchitectureCanvas`、旧 `visual-kernel`，或只能显示 code preview 而不能得到验证后的源码和视图结果，说明重建方向尚未真正落地。
