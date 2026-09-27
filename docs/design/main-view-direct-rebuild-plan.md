# 主视图基于 Scene Visual Lab 的直接重建计划

状态：Implementation Plan

替代文档：已删除 `docs/design/scene-visual-kernel-integration.md`

适用范围：Studio Web 主视图、主视图视觉内核、主视图交互、主视图导出

不在本次重写范围：模型源码静态解析、运行时证据采集、Exact Architecture IR、源码事务、项目发现与分析任务

决策：先归档当前主视图源码与视觉基线，然后删除当前主视图实现；正式主程序只保留一条新的主视图路径，直接以 Scene Visual Lab 已验证的布局、路由、层级展开、图元、标签和视觉语言为实现基础。正式代码不得导入或运行原型目录中的模块。

最高视觉优先级（P0）：`build/scene-visual-lab` 中已经生成的可交互实例和 1170 组离线 case 是新主视图首先需要学习、靠近并通过对照验收的视觉合同。尤其优先复现其中的各种图例式结构元素、父模块展开后的子模块布局、递归内联展开方式、内部结构图、边界门户与内部连线。不得先用通用矩形网格替代这些能力，再把原型视觉留到最后补做。

## 1. 结论

本计划不再采用“在旧主视图中逐步接入一个新路由内核”的策略，也不再保留 `legacy`、`shadow`、`atomic-v1` 三套运行模式。

新的实施方式是一次明确的主视图换代：

1. 将当前主视图的源码、测试、接口清单、典型状态和截图保存为只读副本。
2. 从 `studio/src/main.tsx` 中抽离并保留项目、分析、源码、证据、事务、验证和任务管理能力。
3. 删除现有中央画布的场景消费、SVG 图元、拖动预览、边端点编辑、布局候选和旧路由接线。
4. 在正式 `studio/src` 下重新建立独立的 `visual-kernel` 与 `main-view` 模块。
5. 将原型的纯算法和视觉语言移植到正式模块，但重新定义正式类型，不引用 `studio/prototypes/scene-visual-lab`。
6. 由现有 `ArchitectureIR + Evidence + PublicationHierarchy + SemanticAnnotationOverlay + CanvasDocument` 驱动新视觉内核。
7. 主视图不再消费后端预先计算的 `VisualScene` 几何；浏览器中的正式视觉内核直接生成布局、路由和渲染场景。
8. 主视图导出与交互画布消费同一个正式内核结果，避免“屏幕一套几何、导出另一套几何”。
9. 在一般画布交互和性能优化之前，先完成 `build/scene-visual-lab` 中图例实例、catalog、父子模块展开与内部实现的正式迁移和视觉对照；这是主视图重建的 P0 交付门。

迁移期间允许使用 Git 提交回退，但不允许在正式运行时保留旧主视图作为隐藏 fallback。归档副本用于审计和人工对照，不参与构建。

## 2. 源码审阅结论

### 2.1 当前正式主视图

当前前端的主要事实如下：

| 文件 | 当前职责 | 重建判断 |
|---|---|---|
| `studio/src/main.tsx` | 3681 行；同时承载 Studio 状态类型、API 调用、项目对话框、树导航、画布状态、相机、选择、拖动、边端点编辑、布局候选、检查器、源码事务和完整页面 JSX | 必须拆分；保留非画布业务，删除画布实现 |
| `studio/src/scene-graphics.tsx` | 当前 `SceneNode` / `SceneEdge` SVG、关系标签、选中态、证明覆盖层 | 删除，由原型视觉语言重建 |
| `studio/src/scene-performance.ts` | SVG 分层索引、标签位置和拖动 transform | 删除，由新内核的 render index 与 gesture session 替代 |
| `studio/src/scene-routing-preview.ts` | 拖动时锁定端口侧和单一走廊的预览路由 | 删除，由原型 `routeScene()` 的同源增量重算替代 |
| `studio/src/drag.ts`、`selection.ts` | 包含约束、多选框和选区计算 | 行为需求保留，代码不作为新画布基础；按新场景模型重写 |
| `studio/src/styles.css` | 671 行，混合了应用壳、主视图、检查器、弹窗和源码编辑器样式 | 拆分；主视图样式删除并按原型重建 |
| `studio/e2e/routing-smoke.spec.ts` | 针对当前 Python 路由与 TS 拖动预览合同 | 删除并换成新主视图端到端测试 |

`main.tsx` 中 `App()` 从约 1124 行开始，中央画布 JSX 从约 2869 行开始。主视图状态和非主视图业务已经高度交织，因此不能只替换 `SceneNodeGraphic` 和 `SceneEdgeGraphic`。必须先拆出应用壳和 API 层，再整体删除中央画布实现。

当前主视图依赖的正式链路是：

```text
ArchitectureIR
  -> PublicationHierarchy / PublicationView
  -> VisualSpec
  -> archcanvas_publication.layout.build_scene()
  -> CanvasDocument materialization
  -> optional legacy/shadow/atomic-v1 routing
  -> StudioState.scenes
  -> React SVG
```

该链路的问题不是只有路由较弱，而是几何权威在 Python、拖动预览在 TypeScript、静态导出又由 Python renderer 完成。现有代码因此同时维护三类相似但不相同的逻辑：

- `src/archcanvas_publication/layout.py` 中的布局、端口偏移和避障。
- `src/archcanvas_publication/routing_*.py` 中的试验性 `atomic-v1` 路由。
- `studio/src/main.tsx` 与 `scene-routing-preview.ts` 中的浏览器交互预览。

新的主视图不继续扩展这组双实现。

### 2.2 当前后端中必须保留的能力

以下能力不是旧主视图实现，必须继续作为正式主程序的一部分：

- `src/archcanvas_python/*`：Python 源码静态分析和模型结构恢复。
- `src/archcanvas_adapters/*`：框架适配、可选运行时能力和环境探测。
- `ArchitectureIR`、`EvidenceRecord`、`SourceSnapshot`：模型事实与证据。
- `PublicationHierarchy`：源码事实到可展开层级的正式组织结果。
- `SemanticAnnotationOverlay` 与 `VisualTemplateBinding`：有证据的语义和视觉模板绑定。
- `CanvasDocument`、`VisualPatch`、`PatchBatch`：视觉修改和撤销/重做历史。
- `DraftGraphDocument`、`SourceTransaction`、`GraphDelta`：结构编辑和源码写回安全边界。
- `src/archcanvas_studio/project.py`、分析任务、搜索、源码工作区、验证任务和服务器安全检查。

`PublicationView` 可以继续作为后端对可见语义前沿的验证结果，但新主视图不再把其中的几何结果当作输入。

### 2.3 Scene Visual Lab 已验证的能力

最小原型位于 `studio/prototypes/scene-visual-lab`。它不是简单的视觉稿，已经包含可移植的实现：

| 文件 | 已验证能力 | 正式迁移方式 |
|---|---|---|
| `src/routing.ts` | 五种路由；自适应端口分散、四侧端口选择、正交搜索、避障、共享线段惩罚、圆角折线、标签角度与九类指标 | 以正式类型重写到 `studio/src/visual-kernel` |
| `src/atomic-hierarchy.ts` | 稳定原子身份、边界门户、门户链、自底向上的出口投影 | 改为消费 canonical node/edge/port，不从绘制图元反推事实 |
| `src/detail-layout.ts` | 递归内联展开、稳定子节点 ID、增量排布、内部路由、子模块拖动和边界约束 | 保留算法结构，移除基于标签猜测结构类型的正式路径 |
| `src/expansion.ts` | 确定性放大父模块、递归内容尺寸和下游增量位移 | 迁为正式纯函数 |
| `src/module-details.ts`、`catalog-details.ts` | 节点图元、39 类结构视觉模板和内部流表达 | 迁为视觉模板库，必须由正式 binding 激活 |
| `src/App.tsx` | 节点/边选择、节点拖动/缩放、内部子模块拖动、多层展开、撤销/重做、导出 | 重建交互控制器，不迁移原型内存事实模型 |
| `src/svg-export.ts` | 与交互图元同视觉语言的 SVG 输出 | 改为消费正式 `KernelRenderScene` |
| `src/scenarios.ts` | 26 类拓扑、五种路由、三种节点样式、三种标签样式，共 1170 组合 | 转为新内核的回归 fixture，不进入用户运行时 |

原型当前默认 `atomic-bottom-up`，并保留 `recursive` 用于 A/B。正式主视图只采用 `atomic-bottom-up`。`recursive` 不进入正式运行时。

### 2.4 P0 视觉基准：build/scene-visual-lab

`build/scene-visual-lab` 是当前最小模型已经构建好的可运行成果，也是正式主视图重建的第一视觉基准。它包含：

- 根入口 `build/scene-visual-lab/index.html`，用于实际操作和观察展开行为。
- `cases/manifest.json` 中 26 个场景、1170 个组合，覆盖五种路由、三种节点样式和三种标签样式。
- `cases/semantic-glyph-library`：各种图例式节点元素和结构语法。
- `cases/extended-module-catalog` 以及 traditional ML、neural foundation、vision/sequence、sequence/generative、generative/graph、multimodal/RL/adaptation 六类 catalog：内部结构图、模块图元和内部流表达的实例集合。
- `cases/parent-child-expansion`：父模块展开、子模块内联布局、父边界扩张和外部节点增量位移的直接参照。
- crossing、dense、fan-in/out、residual、feedback、four-side-ports、vertical-label 等路由和标签压力实例。
- 每个 case 的 SVG 与 JSON/metrics，可用于几何、图元、配色、标签和质量指标的离线对照。

这里的“基准”具有以下明确含义：

1. 正式主视图的节点图元、内部图例元素、颜色、线宽、字号、间距、标签板和关系图例首先向这些实例靠近。
2. 父模块展开后，不允许退化成普通节点的均匀网格；必须迁移原型的内容尺寸计算、子模块相对布局、内部路由、递归嵌套表面、入口/出口和下游位移行为。
3. `semantic-glyph-library` 和各 catalog 的图元实现是正式 visual template library 的首批视觉输入，但只可由真实 hierarchy、SemanticAnnotation 或 `VisualTemplateBinding` 激活。
4. 对照验收同时检查“看起来是否接近”和“行为是否相同”，包括展开前后位置变化、子模块顺序、内部流、portal 连续性、折叠恢复和导出结果。
5. `build/scene-visual-lab` 是视觉/行为验收 oracle，不是运行时依赖、模型事实来源或可直接 import 的正式源码。正式实现仍须位于 `studio/src/visual-kernel` 与 `studio/src/main-view`。
6. build 产物与原型源码不一致时，以可运行 build 的用户可见结果确定视觉目标，再回到原型源码定位对应算法；不得根据当前主程序的旧视觉自行折中。

P0 完成之前，不把通用矩形节点、简单网格排布或基础折线路由称为“已经沿用最小原型视觉”。它们最多是接通正式数据的临时骨架。

### 2.5 已存在但不继续采用的保守集成代码

当前仓库已经出现以下试验性模块：

- `src/archcanvas_publication/routing_models.py`
- `routing_graph.py`
- `routing_kernel.py`
- `routing_scene.py`
- `routing_shadow.py`
- `routing_metrics.py`
- `routing_digest.py`
- `src/archcanvas_studio/routing.py`
- 前端的 routing report 类型和 `scene-routing-preview.ts`

这些模块实现了旧方案中的 Python 权威路由、shadow comparison、fallback 和 TS 手势预览。它们证明了稳定 ID、canonical provenance、端口和 portal 元数据可以进入正式合同，但不再作为新主视图的运行基础。

新实现可以参考其测试揭示的合同要求，不继续保留其运行模式、环境变量和 scene fallback。

## 3. 不可破坏的不变量

主视图可以完全重写，但以下约束不得改变：

1. `SourceSnapshot + Evidence + ArchitectureIR` 是模型事实的唯一权威来源。
2. 静态分析不得导入或执行用户项目。
3. 几何、坐标、颜色、图元类型、折叠状态和绘制顺序不得反向写入 Exact IR。
4. canonical identifier 不得由坐标、数组下标、路由点或 SVG DOM 顺序生成。
5. 所有可见节点、端口和边必须能追溯到 canonical ID，或明确标记为纯视觉容器/注释。
6. `VisualPatch` 只能修改 `CanvasDocument`，不能直接修改源码。
7. 新增、删除、重连 canonical 节点或边必须继续进入 draft/proposal/transaction 流程。
8. 原型目录不得被正式源码导入，不得成为运行时依赖，不得成为第二套模型事实。
9. 硬切换不等于降低安全标准。新画布的“删除节点”和“新建连线”必须调用正式 proposal API，不能照搬 `LabPatch` 的直接删除和直接加边。
10. 原型模板只能决定如何画已经被证据证明的结构，不能用图例猜测源码结构。
11. 展开、收起、拖动、改色和重新路由不得改变 `source_digest` 与 Exact IR digest。
12. 不支持的结构必须使用 generic/opaque 视觉，不得用近似模板伪装为 exact。

## 4. 重建边界

### 4.1 保留

- 顶部产品栏中的项目打开、分析、保存、验证、导出入口。
- 左侧正式 module/source 导航树及 canonical 选择联动。
- 右侧 inspect/source/model/evidence 能力。
- 底部 problems/source/diff/validation/jobs/activity 能力。
- 项目对话框、Conda 环境选择、后台任务轮询和 generation 防陈旧覆盖。
- 搜索、Evidence 定位、Source excerpt、源码工作区和事务审查。
- `/api/state`、项目、分析、搜索、源码、验证、proposal、transaction、patch、undo、redo 等非几何 API。

### 4.2 删除并重建

- 中央主视图的 `VisualScene` 消费逻辑。
- 当前节点与边的 React SVG 组件。
- 当前相机、拖动 DOM transform、局部边预览和端点拖动实现。
- 当前 scene render index 和 scene selection 数据模型。
- 当前布局候选面板与 Python 布局候选的主视图接线。
- 当前 relation legend 的 DOM 实现。
- 当前主视图 CSS、深色图元覆写和 semantic zoom 规则。
- Studio 运行时中的 `legacy` / `shadow` / `atomic-v1` 路由选择。
- Studio 对 `StudioState.scenes`、`specs` 和 routing report 的依赖。

### 4.3 暂时保留但退出主视图

`src/archcanvas_publication/layout.py`、`renderers.py`、`VisualSpec` 和 `VisualScene` 仍被 CLI publication、PNG/PDF 和离线 bundle 使用。第一轮主视图重建不应连带破坏这些非 Studio 输出。

它们必须满足两个限制：

1. Studio 主视图不再读取它们的几何。
2. UI 中的“导出当前主视图 SVG”改用新 TypeScript 内核；旧 Python 输出只能标记为 publication export，不能冒充所见即所得的主视图导出。

当后续要求 CLI 与主视图完全同图时，再增加一个调用同一编译后 TypeScript 内核的 headless export 入口。该工作不允许重新引入第二套手写 Python 路由。

## 5. 旧主视图副本

### 5.1 归档目录

实施第一步新增：

```text
docs/archive/main-view-v1/
  README.md
  MANIFEST.json
  SHA256SUMS
  source/
    studio/src/...
    studio/e2e/...
    src/archcanvas_publication/...
    src/archcanvas_studio/...
  fixtures/
    studio-state.json
    canvas-document.json
    architecture.json
  baselines/
    desktop-light.png
    desktop-dark.png
    mobile.png
    expanded-module.png
    selected-edge.png
```

归档源码至少包含：

- `studio/src/main.tsx`
- `studio/src/styles.css`
- `studio/src/scene-graphics.tsx`
- `studio/src/scene-performance.ts` 及测试
- `studio/src/scene-routing-preview.ts` 及测试
- `studio/src/drag.ts`、`selection.ts` 及测试
- `studio/e2e/routing-smoke.spec.ts`
- `src/archcanvas_publication/layout.py`
- `src/archcanvas_publication/renderers.py`
- 全部 `src/archcanvas_publication/routing_*.py`
- `src/archcanvas_studio/routing.py`
- `src/archcanvas_studio/bundle.py`
- 与旧 scene/layout/routing 直接相关的 Python 测试

`MANIFEST.json` 记录原路径、归档路径、Git commit、字节数和 SHA-256。`README.md` 记录启动命令、基线模型、视口、关键操作和已知问题。

归档不包含：

- `node_modules`
- `build/scene-visual-lab`
- `src/archcanvas_studio/static/assets` 中的哈希构建产物
- `.venv`、缓存或用户未跟踪文件

### 5.2 视觉与交互基线

删除前必须保存以下状态：

1. 桌面浅色完整 Studio。
2. 桌面深色完整 Studio。
3. 移动视口。
4. 至少一个展开模块。
5. 选中节点、选中边、拖动中和框选后的状态。
6. 右侧 Evidence/Source/Visual/Model tab。
7. 底部 Problems/Validation/Jobs tab。
8. SVG 导出与当前 `StudioState` fixture。

归档只用于回答“旧版曾经如何工作”和辅助回归定位，不作为新实现的像素目标。新主视图的视觉目标是 Scene Visual Lab，而不是旧主视图。

## 6. 目标架构

```text
SourceSnapshot + Evidence + ArchitectureIR
                    |
                    v
      PublicationHierarchy / SemanticOverlay
                    |
                    v
         Studio formal-state adapter
         (no geometry, no LabScene)
                    |
                    v
             KernelDocument
      atoms / ports / edges / modules
                    |
        +-----------+-----------+
        |                       |
        v                       v
 hierarchy projection      visual state
 expanded frontier         CanvasDocument
        |                       |
        +-----------+-----------+
                    v
              layout kernel
                    v
      bottom-up portals + route kernel
                    v
            KernelRenderScene
        +-----------+-----------+
        |                       |
        v                       v
 React SVG main view       SVG export
```

边界说明：

- 后端继续回答“模型是什么、证据在哪里、哪些层级与关系成立”。
- 正式 TypeScript 视觉内核回答“这些事实在当前展开和视觉状态下如何布局与绘制”。
- React 组件只绘制 `KernelRenderScene` 并转发交互意图，不拥有路由算法。
- `CanvasDocument` 只保存用户视觉选择，不保存新的模型语义。

## 7. 正式目录设计

建议将当前单文件 App 拆为：

```text
studio/src/
  main.tsx                         # 只负责 React bootstrap
  app/
    StudioApp.tsx                  # 页面壳和面板编排
    studio-types.ts                # /api/state 正式前端类型
    studio-state.ts                # generation/model identity/state acceptance
  api/
    studio-client.ts               # GET/POST、nonce、错误标准化
    jobs.ts
  shell/
    TopBar.tsx
    NavigationPanel.tsx
    InspectorPanel.tsx
    BottomPanel.tsx
    ProjectDialog.tsx
    SourceWorkspace.tsx
  visual-kernel/
    types.ts                       # KernelDocument/KernelRenderScene
    normalize.ts                   # 稳定排序、ID 与输入校验
    hierarchy.ts                   # visible representative 与原子投影
    layout.ts                      # 原型 expansion/layout 的正式版本
    detail-layout.ts               # 递归内联详情
    portals.ts                     # 边界门户与 portal chain
    routing.ts                     # adaptive/direct/orthogonal/channel/curve
    metrics.ts                     # 质量指标
    visual-language.ts             # 节点/边/标签/颜色/图例 token
    svg-geometry.ts                # path、圆角、label placement
    svg-export.ts                  # 从 KernelRenderScene 输出 SVG
  main-view/
    ArchitectureCanvas.tsx
    CanvasToolbar.tsx
    CanvasViewport.tsx
    SceneSvg.tsx
    NodeGraphic.tsx
    EdgeGraphic.tsx
    DetailGraphic.tsx
    RelationLegend.tsx
    CanvasInspector.tsx
    formal-state-adapter.ts
    canvas-controller.ts
    gesture-controller.ts
    selection.ts
    camera.ts
    main-view.css
```

强制依赖方向：

```text
shell -> main-view -> visual-kernel
                 -> api

visual-kernel -X-> React
visual-kernel -X-> api
visual-kernel -X-> studio/prototypes
```

`visual-kernel` 必须保持纯 TypeScript、无 DOM、无 React、无 fetch。这样交互画布、单元测试、fixture 生成和 SVG 导出可复用同一结果。

## 8. 正式视觉内核数据模型

原型的 `LabScene`、`LabNode`、`LabEdge` 和 `LabPatch` 不进入正式代码。新内核至少定义：

```ts
interface KernelDocument {
  documentId: string;
  architectureId: string;
  sourceDigest: string;
  nodes: KernelNode[];
  ports: KernelPort[];
  edges: KernelEdge[];
  modules: KernelModule[];
  templateBindings: KernelTemplateBinding[];
}

interface KernelNode {
  nodeId: string;                  // canonical node ID
  parentModuleId?: string;
  canonicalNodeIds: string[];
  label: string;
  secondaryLabel?: string;
  semanticKind: string;
  shape: KernelNodeShape;
  inputPortIds: string[];
  outputPortIds: string[];
  evidenceIds: string[];
  templateBindingId?: string;
}

interface KernelPort {
  portId: string;                  // canonical port ID
  ownerNodeId: string;
  direction: "input" | "output";
  role: string;
  evidenceIds: string[];
}

interface KernelEdge {
  edgeId: string;                  // stable projected identity
  canonicalEdgeIds: string[];
  sourcePortId: string;
  targetPortId: string;
  relation: KernelRelation;
  semanticChannel: string;
  tensorIds: string[];
  label: string;
  evidenceIds: string[];
}

interface KernelVisualState {
  expandedModuleIds: string[];
  nodePositions: Record<string, Point>;
  nodeSizes: Record<string, Size>;
  detailOffsets: Record<string, Point>;
  pinnedNodeIds: string[];
  routeHints: Record<string, Point[]>;
  routeStyle: RouteStyle;
  nodeStyle: NodeVisualStyle;
  labelStyle: EdgeLabelStyle;
  camera: CameraState;
}
```

`KernelRenderScene` 是可丢弃的计算结果，包含 bounds、route points、path、label point、portal chain 和 render order。它不写入 Architecture IR，也不成为新的持久化事实层。

### 8.1 稳定身份规则

- 原子节点使用 canonical node ID。
- 原子端口使用 canonical port ID。
- 原子边使用 canonical edge ID。
- 可见聚合节点 ID 由 hierarchy/view ID 派生。
- 可见聚合边 ID 由排序后的 canonical edge IDs、可见起终点、relation 和 semantic channel 生成摘要。
- detail visual primitive 若没有 canonical 实体，只能使用 `binding_id + slot_id`，并标为 visual-only。
- 任何 ID 都不得包含坐标、数组位置、当前缩放或路由点。

### 8.2 正式状态适配

`formal-state-adapter.ts` 只读取：

- `architecture.nodes/edges/tensors/repeats/fanouts`
- `hierarchy.nodes`
- `views[active_projection_id]` 的可见语义信息
- `semantic_overlay.annotations/template_bindings`
- `evidence`
- `document` 与 `view_state`

它明确不读取：

- `StudioState.scenes`
- `VisualScene.points`
- 旧 routing report
- 原型 `SCENARIOS`
- `module-details.ts` 中的标签猜测结果

## 9. 源码解析与视觉模板的连接

### 9.1 保留现有解析

模型源码到 Architecture IR 的分析流程不改。新主视图不得增加第二套 AST 解析器，也不得在浏览器中重新解析 Python。

### 9.2 模板激活规则

原型中的内部结构图不能仅凭节点名称出现。正式激活次序是：

1. `VisualTemplateBinding.fidelity == exact`：按 canonical node/edge/port/tensor slot 绘制完整内部图。
2. `opaque`：显示原型风格的模块外框和已证明的入口/出口，不绘制未证明内部关系。
3. `schematic`：只在 UI 明确标记“示意”时显示，不绑定 canonical 实体，不参与 exact edge 路由。
4. 无 binding：使用 generic operation/container/tensor 图元。

当前仓库已有 `attention.qkv-v1` 模板与 binding 校验，可作为第一个 exact 模板。其余原型家族只有在 Pattern Pack 或分析器提供正式 binding 后才能进入 exact 展开。

原型 `detail-layout.ts` 中通过标签推断 `nestedKind` 的逻辑，不得用于真实模型。正式嵌套类型只能来自：

- hierarchy 中的真实子节点；
- `SemanticAnnotation.semantic_role/glyph`；
- `VisualTemplateBinding`；
- 明确的 visual-only schematic 用户选择。

### 9.3 未知结构的显示

未知或证据不足时：

- 保留节点和真实边。
- 节点显示 generic/opaque 视觉。
- 检查器显示 unresolved 原因和 Evidence。
- 允许用户拖动、调色和折叠。
- 禁止自动补出 Q/K/V、残差、门控或张量变换。

## 10. 原型视觉语言的正式化

### 10.1 节点图元

正式主视图沿用原型的图元语法：

- tensor：矩阵或堆叠平面。
- convolution：特征图堆栈与网格。
- attention：Q/K/V 汇入节点。
- normalization：圆角条带与统计符号。
- condition：六边形。
- merge：菱形。
- add / multiply / concat：圆形运算符。
- io：胶囊形。
- operation：克制的算子块。

正式 relation 集合仍保留现有 `VisualRelation` 的完整语义。视觉映射以原型七类颜色为基础：

| 正式关系 | 原型视觉族 | 基准颜色/线型 |
|---|---|---|
| `sequence` | flow | `#39444d` 实线 |
| `parallel-branch` | branch | `#266d66` 实线 |
| `merge` | merge | `#725b19` 实线 |
| `residual` | residual | `#b33d5a` 虚线 |
| `memory-reference` | memory | `#7756a2` 实线或短虚线 |
| `condition` | condition | `#a35416` 实线 |
| `state-update` | feedback | `#2467a5` 虚线 |
| `shape-transform` | transform 扩展 | 使用原型 violet 家族 |
| `routing` | routing 扩展 | 使用原型 orange/neutral 家族 |
| `parameter-share` | shared 扩展 | 使用原型 pink 家族 |
| `training-only` | muted 扩展 | 灰色虚线 |

节点的原型配色、1.35px 基准描边、5 至 6px 圆角、13px 主标签、10px 副标签、纸张背景、20px 网格和非缩放描边作为默认视觉 token。正式主视图可通过主题 token 适配深色模式，但不得改变各语义族之间的可辨识性。

### 10.2 三种节点和标签样式

保留原型控制项：

- 节点：`semantic`、`technical`、`compact`。
- 标签：`plain`、`plate`、`endpoint`。
- 路由：`adaptive` 为默认；`direct`、`orthogonal`、`channel`、`curve` 作为用户视觉选项。

这些选项写入 `CanvasDocument`，不会触发重新分析，也不会改变 canonical graph。

### 10.3 图例

新 `RelationLegend` 直接读取当前可见 `KernelEdge`：

- 每种关系只显示一次。
- 线段颜色、粗细和虚线必须与边完全相同。
- 使用原型的小字号、紧凑间距和纸张色背景。
- 默认左上；允许四角或隐藏。
- 展开/折叠后图例按实际可见关系更新。
- 图例不遮挡节点时才覆盖在画布内，否则移动到画布工具栏末端。

内部模板中的 Q/K/V、Add、Multiply、Concat 等“图例式图元”保持原型风格，并通过 tooltip/检查器显示 canonical slot 与 Evidence。

### 10.4 图例实例与展开视觉的 P0 迁移顺序

图例不只指左上角的关系颜色列表，还包括最小模型中用来表达模块内部实现的视觉实例。正式迁移按以下顺序执行：

1. 迁移 `semantic-glyph-library` 的基础图元和精确尺寸/token，建立可单独渲染的 production glyph fixture。
2. 迁移 `module-details.ts` / `catalog-details.ts` 的 primitive 集合、内部 flow、矩阵/张量、运算符、frame、annotation 和 tone，不先用普通矩形占位。
3. 迁移 `extended-module-catalog` 及六类 catalog 的完整实例，逐项建立 template ID、slot ID、fidelity 和 Evidence 映射。
4. 迁移 `parent-child-expansion` 的父容器扩张、子模块布局、递归嵌套表面、内部入口/出口、兄弟节点避让和下游增量移动。
5. 迁移 atomic bottom-up portal 投影，使外部边、父边界、内部图和继续展开后的子图使用连续的入口/出口。
6. 最后才把这些视觉能力接到通用真实模型；缺少 exact binding 的节点仍显示 opaque，但其外框、端口和已证明的内部子节点也应使用同一视觉语言。

每完成一类图元或展开行为，都必须与 `build/scene-visual-lab` 对应页面并排截图，并记录以下差异：bounds、内部 primitive 数量、相对位置、route points/path、label placement、portal、字体、颜色和展开前后位移。未记录的主观“相似”不算验收。

## 11. 层级展开与自底向上投影

正式主视图只实现原型默认的 `atomic-bottom-up`：

1. 从 Architecture IR 建立最深层原子节点、端口和边。
2. 从 PublicationHierarchy 建立模块包含树。
3. 布局最深层真实节点或 exact template slot。
4. 自叶向根计算模块包围盒。
5. 为跨层原子边计算最低公共祖先和 portal chain。
6. 根据当前 expanded module set 计算 visible representative。
7. 以 `(sourceVisibleId, targetVisibleId, relation, semanticChannel)` 聚合可见边。
8. 在稳定门户之间执行路由。

必须满足：

- 每条 canonical edge 在任一展开状态下恰好隐藏或属于一条可见投影边。
- 展开/折叠不改变 canonical ID、原子布局和端口顺序。
- 相邻层级共享完全相同的 portal 坐标。
- Q/K/V、残差、条件、状态和普通流不能因为可见端点相同而被错误合并。
- 父模块移动时整体平移子树；子模块拖动只修改该层 detail offset。
- 收起再展开必须确定性恢复此前内部布局。

左侧导航树仍可控制 module/source 层级，但画布展开不再等待 Python 重新生成 `VisualScene`。展开状态先在本地立即生效，再通过正式 view-state/patch API 持久化。

## 12. 路由内核

### 12.1 默认流程

`adaptive` 路由按以下顺序工作：

1. 根据节点相对位置、已有障碍和语义方向选择端口侧。
2. 同一节点同一侧的端口按对端坐标稳定排序并分散。
3. 注入 portal chain 的硬约束点。
4. 建立包含节点边界、净距线、端口 stub 和已用走廊的正交搜索图。
5. 以硬错误优先的评分寻找路径。
6. 压缩重复点和共线点。
7. 生成圆角 SVG path。
8. 在最长合适线段上放置标签，必要时旋转纵向标签。

### 12.2 评分顺序

候选路径使用词典序，而不是一个难解释的总分：

```text
1. invalid endpoint count
2. node intersection count
3. clearance violation count
4. reverse departure count
5. crossing count
6. shared segment length
7. bend count
8. route length
9. stable route key
```

前四项为硬质量门。存在硬错误时显示结构化诊断，不静默换回旧路由。

### 12.3 拖动中的路由

拖动开始时建立 `GestureSession`，记录：

- 受影响节点和子树。
- 关联边。
- 已分配端口侧和顺序。
- 当前 portal chain。
- 未受影响的占用走廊。

每个 pointer move 只重新计算受影响边。允许用 `requestAnimationFrame` 合并事件，但预览和 pointer up 后的最终路线必须调用同一个路由函数，不能再维护一套简化 preview 算法。

## 13. 主视图交互

### 13.1 选择与相机

- 单击节点或边选择。
- 空白处拖动框选。
- Shift 扩展选择。
- 空白处平移，滚轮/触控缩放。
- Fit、Focus selection 和相机持久化保留。
- 选择身份存 canonical/view ID，不存 DOM element 或数组下标。

### 13.2 节点和内部子模块拖动

- 拖动顶层节点产生本地预览，pointer up 后提交一个 `PatchBatch`。
- 拖动容器时整体移动其当前可见子树。
- 拖动内部 exact detail node 写入独立 detail offset，不改变 canonical 拓扑。
- 约束函数保证子节点留在父模块内容区域。
- 多选移动、对齐和分布由前端计算 patch batch，不再请求 Python layout endpoint。

### 13.3 展开与收起

- 父模块右上角使用原型的 `+` / `-` 控件。
- 双击模块也可展开。
- 展开后内联替换父级占位，不打开独立页面。
- 任意深度继续使用相同规则。
- 展开状态写入 CanvasDocument view state。

### 13.4 新建、删除与重连

原型的 UI 手势可以保留，提交语义必须改造：

| 用户动作 | 正式结果 |
|---|---|
| 删除 visual-only annotation | `VisualPatch` |
| 删除 draft node/edge | draft API |
| 删除 canonical node | delete impact preview + typed intent |
| 新建 canonical-looking node | draft node，不进入 Exact IR |
| 新建或重连边 | proposed connection / draft edge |
| 改变位置、尺寸、颜色、标签换行 | `VisualPatch` / `PatchBatch` |

任何情况下都不允许在浏览器 reducer 中直接改写 canonical graph。

### 13.5 撤销与重做

原型本地 `past/future` 只用于理解交互，不进入正式实现。正式主视图继续调用服务器的 `/api/undo` 和 `/api/redo`，保证刷新后历史仍然一致。

## 14. CanvasDocument 扩展

现有操作继续保留，并新增或明确以下视觉操作：

- `set-kernel-options`：route/node/label style。
- `set-detail-expansion`：某一模块的递归展开树。
- `set-detail-offset`：模板/真实子节点在父模块中的视觉偏移。
- `set-node-shape-override`：仅视觉 glyph override。
- `set-legend-placement`：沿用现有操作。

每个 patch 必须包含适用的 architecture/source digest 或由服务端在提交时校验当前 document binding。对旧 scene ID 的依赖逐步移除，target 使用 stable node/edge/module ID。

迁移旧 CanvasDocument 时：

- `set-position`、`set-size`、`set-pin`、`set-label-wrap`、palette、font、line、caption、annotation、camera 可转换。
- 旧 `set-route-hint` 只有在 canonical edge 集和端点身份唯一匹配时转换。
- 旧 scene ID 无法映射时产生 migration diagnostic，不猜测。
- layout mode 转成新的 kernel options；不存在对应项时使用 `adaptive + semantic + plain`。

## 15. 主视图导出

主视图工具栏的导出流程改为：

```text
KernelDocument + KernelVisualState
  -> buildKernelRenderScene()
  -> renderKernelSceneSvg()
  -> browser Blob download
```

导出必须复用：

- 同一节点图元函数或同一 render description。
- 同一 route points/path。
- 同一 label point/angle。
- 同一 relation token 和 legend。
- 同一展开状态与 detail offsets。

SVG 中保留：

- canonical node/edge/port IDs。
- evidence IDs。
- template binding ID 与 fidelity。
- portal IDs。
- source digest 与 kernel version。

主视图导出不得重新路由。PNG/PDF 若从主视图发起，应从这份 SVG 派生。

## 16. 实施步骤

### Phase 0：归档并冻结旧主视图

实施状态（2026-09-27）：已完成。旧主视图源码、离线状态 fixture、完整交互截图与 SVG 基线已归档到 `docs/archive/main-view-v1`；70 项 checksum 全部通过，并以独立提交 `74611f2` 冻结。

交付：

- `docs/archive/main-view-v1` 源码副本、manifest、checksums 和截图。
- 一组可离线加载的 StudioState/CanvasDocument fixture。
- 旧主视图行为清单。
- 单独的归档提交。

退出条件：归档能定位每个原文件，checksum 校验通过，视觉基线可查看。

### Phase 1：拆出非画布应用壳

实施状态（2026-09-27）：已完成本阶段的运行边界拆分。`main.tsx` 只负责 bootstrap，`StudioShell`、正式类型、状态接收和 API client 已形成边界；源码工作区与事务审查已提取到 `studio/src/inspector/SourceWorkspacePanel.tsx`、`TransactionReview.tsx`，Inspector 的概览、源码、模型、视觉和边关系面板已提取到 `studio/src/inspector/InspectorPanels.tsx`，项目启动、文件夹选择、草稿节点/边和删除影响对话框已提取到 `studio/src/inspector/ProjectDialogs.tsx`。patch、kernel batch、事务参数/结构准备、连接提议和源码事务提交由 `studio/src/app/studio-actions.ts` 负责；项目/目录/搜索/验证/分析请求集中在 `studio/src/app/project-actions.ts`，导航序列化在 `navigation-actions.ts`，任务轮询和取消在 `job-actions.ts`。`StudioApp.tsx` 不再直接调用项目、搜索、验证或分析 API，只负责编排状态和渲染；所有请求继续通过 `studio-client` 保持 nonce、状态接收、导航恢复和 activity log 行为一致。

工作：

- 将 `main.tsx` 缩减为 bootstrap。
- 提取 `StudioApp`、API client、状态接收、项目、导航、检查器、底部面板和对话框。
- 为抽出的非画布模块补充行为测试。
- 暂时使用一个明确的 `ArchitectureCanvasPlaceholder` 保持构建可运行。

这一步不是保留旧主视图，而是保护仍需继续使用的正式程序能力。

退出条件：项目分析、导航、证据、源码、事务和任务 UI 在没有旧画布代码时仍可运行。

### Phase 2：删除旧主视图运行路径

实施状态（2026-09-27）：已完成。旧 `scene-graphics`、`scene-performance`、`scene-routing-preview` 及对应测试已删除；前端 runtime 不再依赖 `StudioState.scenes/specs/routing`、旧 layout/route/align API 或 fallback 画布，中央区域只有 `ArchitectureCanvas`。

删除或清空：

- `scene-graphics.tsx`
- `scene-performance.ts` 及测试
- `scene-routing-preview.ts` 及测试
- 旧画布相关的 `main.tsx` 代码和 CSS
- 旧 routing smoke e2e
- Studio runtime routing mode、shadow report 和环境变量
- `StudioState.scenes/specs/routing` 的前端依赖
- layout candidate、route、align 等旧主视图 API 接线

退出条件：代码库中不存在旧 React SVG 画布和运行时 fallback；应用只显示新主视图挂载点。

### Phase 3：建立正式纯视觉内核

实施状态（2026-09-27）：已完成。正式内核已覆盖 26 个 topology × 45 个视觉组合、39 类 catalog/detail、adaptive routing/metrics、父子展开五状态、portal、递归 detail 与同源 SVG export。prototype vocabulary 扫描实际读取 `build/scene-visual-lab/cases` 的 1170 个 SVG，锁定 `scene-node/scene-edge`、矩阵/操作 glyph、detail-shape/detail-flow、五类 tone 以及正式输出中的同名结构类；P0 结构报告 14/14 解析并通过，静态 12 组 PNG 对照通过，内部拖拽和递归交互态另有明确的 interaction-only 像素差报告。正式内核不依赖 React、DOM、API 或 prototype/build 目录。

本阶段内部采用 P0 顺序，不以“基础节点已经能显示”作为完成信号：

- 正式 types 与输入校验。
- 首先迁移 `build/scene-visual-lab/cases/semantic-glyph-library` 对应的 visual language token 和图元。
- 随后迁移全部 catalog detail primitive、内部 flow 和 template layout。
- 完整迁移 `parent-child-expansion` 对应的 expansion 和 recursive detail layout。
- 迁移 route styles、rounded path、label geometry、adaptive routing 与 metrics，确保内部/外部线路同源。
- atomic hierarchy、portal 和 visible projection。
- SVG export。

同时把原型测试迁移为正式 kernel 测试，增加禁止原型/build import 的扫描测试，并为上述 P0 case 建立 production render digest 与并排截图。

退出条件：1170 组合 fixture 可由正式内核独立生成；semantic glyph、catalog detail、父子展开和递归内部图达到视觉/行为对照门；无 React、DOM、API 或 build 目录依赖。

### Phase 4：连接正式模型数据

实施状态（2026-09-27）：已完成。`formal-state-adapter.ts` 从 Architecture IR、PublicationHierarchy、Semantic Overlay 与 VisualTemplateBinding 确定性地产生 KernelDocument，并输出缺失端口、悬空边、循环包含和 stale binding 诊断。Transformer、Autoformer、iTransformer、PatchTST、TimeMixer 与 generic 六类正式 JSON fixture 的重复适配、稳定 ID 和 digest 测试通过。

工作：

- 实现 `formal-state-adapter.ts`。
- 从 Architecture IR 建立 atomic graph。
- 从 PublicationHierarchy 建立 module tree。
- 接入 SemanticAnnotationOverlay 与 VisualTemplateBinding。
- 建立完整 VisualRelation 到原型视觉族的映射。
- 对缺失端口、悬空边、循环包含和 stale binding 给出结构化诊断。

退出条件：Transformer、Autoformer、iTransformer、PatchTST、TimeMixer 和 generic fixture 均能生成确定性 KernelDocument。

### Phase 5：重建 React 主视图

实施状态（2026-09-27）：已完成。静态 glyph/catalog/parent-child export 与 React 运行时已按原型 token、图例、展开容器和结构报告校验；正式 exact attention 的 Q/K/V 已使用矩阵、线性投影、圆圈 `×`、`h × Q/K/V`、`Output Wᴼ` 与 `1 / √d_k` 原型标记，同时保留 canonical slot 与拖动锚点 contract。运行时与导出态均保留 `node-surface`、`node-grid`、`detail-flow`、`detail-matrix`、`detail-symbol` 等原型兼容结构标识；交互拖动和递归嵌套按 interaction-only 证据单独验收，不把交互中的选择/拖拽状态误报为静态 SVG 差异。`VisualPatch` / `PatchBatch`、刷新恢复和服务器 undo/redo 属于 Phase 6。

工作：

- 以 `build/scene-visual-lab` 为第一屏视觉目标，实现画布 toolbar、viewport、SVG layers、node/edge/detail graphics 和 legend。
- 优先接入已经通过 P0 对照的 glyph、catalog detail 与 parent-child expansion，不允许 React 层另画一套简化内部图。
- 实现选择、相机、框选、拖动、resize、展开和内部子节点交互。
- 接入右侧正式检查器和 Evidence。
- 接入 prototype 风格的节点/边/标签选项。

已交付并验收：

- 正式 `ArchitectureCanvas` 只消费 `ArchitectureIR + PublicationHierarchy + CanvasDocument` 的 adapter 结果，不读取 `VisualScene` 几何，也不引用 prototype/build 目录。
- Scene Visual Lab 风格的 toolbar、viewport、SVG 分层、semantic glyph、关系图例、五种路由、三种节点样式和三种标签样式已进入唯一正式主视图路径。
- 父模块保留式展开、任意层级递归子模块、canonical edge 最深可见投影、portal chain 和 exact `attention.qkv-v1` 内部 46 个 primitive / 23 条 flow 已由正式内核绘制；React 层没有另画简化内部图。
- 鼠标/触控板平移、滚轮与按钮缩放、Fit、Focus Selection、Shift 框选、多选、节点/子树拖动、展开容器与普通节点 resize、exact detail primitive 拖动、边宽命中区和边选中态已经接通。
- 结构容器即使没有自身 canonical node ID，也拥有独立的 render-node 焦点，可直接拖动和 resize；Inspector 仍通过 contained canonical ID 回接正式模型，不把 render identity 写入模型事实。
- 节点、exact detail slot 和边均回接正式选择；边 Inspector 显示关系、源/目标、端口、canonical edge ID 和 Evidence，移动端 Inspector 使用既有覆盖层。
- 单元测试覆盖 exact detail 的 12 个正式交互槽、visual-only 不可选、detail offset/flow 连续性、边命中与选中态、resize handle、Focus Selection 和框选几何。
- Playwright 在 1440×900 与 390×844 完成真实交互验收，覆盖 encoder -> q/k 递归展开、容器 resize、内部节点拖动、节点 resize、框选、多选、边选择、Inspector 和移动端无页面级横向溢出。

退出条件：主视图不读取 VisualScene，却能完整显示并操作真实分析结果；父模块展开后的子模块布局、内部实现和图例式元素通过与 build 实例的并排视觉验收。

### Phase 6：持久化与正式编辑边界

实施状态（2026-09-27）：已完成。主视图的本地状态仅用于手势预览；所有可恢复视觉结果均由服务器 CanvasDocument 派生，结构编辑继续受 draft/proposal/transaction 边界约束。

工作：

- 将视觉操作提交为 VisualPatch/PatchBatch。
- 实现 reload、undo、redo 和 document migration。
- 将新增、删除、重连手势接到 draft/proposal/transaction。
- 验证所有视觉操作前后 source digest 与 Exact IR digest 不变。

已交付并验收：

- `VisualPatch` 正式增加 `set-kernel-options`、`set-detail-expansion`、`set-detail-offset` 和 `set-node-shape-override`；kernel geometry、camera、样式与展开 patch 必须携带当前 `architecture_id`、`source_digest` 和 `kernel_scene_id`。
- 服务端根据 PublicationHierarchy 与 VisualTemplateBinding 建立 stable target 白名单，拒绝 stale architecture/source binding、未知 `view:<hierarchy_id>`、未知展开模块和不属于正式 binding 的 detail target；legacy scene patch 路径继续兼容。
- `derive_view_state()` 现在从服务器历史派生 `node_positions`、`node_sizes`、`detail_offsets`、`module_expansion`、route/node/label style、shape override 与 kernel camera；旧 scene node geometry 和 camera 在 `StudioBundle.state()` 中仅在可唯一映射时迁移到 stable kernel identity，无法映射时输出 migration diagnostic，不猜测目标。
- 节点/容器/多选拖动、左/顶对齐、水平/垂直分布、resize、exact detail primitive 拖动、递归展开、route/node/label 选项、平移、缩放、Fit 与 Focus Selection 均提交正式 `/api/patch-batch`；浏览器本地 state 只保留提交前的 optimistic preview，服务器状态返回、undo、redo 或 reload 后重新同步。
- kernel camera 由前端 180ms 合并提交，但不破坏服务器历史；连续相机变更可由 `/api/undo` 恢复上一视角并由 `/api/redo` 重做。几何多选继续作为单一 PatchBatch 撤销。
- 模块展开不再通过旧 `/api/navigation` 冒充画布历史；画布提交 `set-detail-expansion`，侧栏立即同步，服务器返回及 undo/redo 后从 CanvasDocument 恢复。旧 navigation endpoint 仅保留给导航投影自身。
- 服务器状态公开 source digest 与 Exact IR digest 完整性对；保存视觉文档时再次断言 architecture binding、source digest 和 Exact IR 不变。
- Phase 6 Playwright 在真实 API 上验证样式、detail offset、resize、展开和相机刷新恢复、批次 undo/redo，并验证连接进入 proposal、新建/删除进入 draft，期间 source digest 与 Exact IR digest 始终不变。

退出条件：刷新后布局、展开、样式和相机恢复；结构编辑没有绕过正式安全流程。

### Phase 7：统一主视图导出

实施状态（2026-09-27）：已完成。主视图 SVG、PNG 与 PDF 均由浏览器中的正式 visual kernel 场景生成；旧 Python SVG 明确保留为 publication export，不再作为主视图所见即所得导出。

工作：

- 浏览器 SVG export 使用正式 kernel。
- 从 SVG 派生主视图 PNG/PDF。
- 增加屏幕场景与导出场景 digest 对比。
- 将旧 `/api/export` 重命名或标记为 publication export，避免语义混淆。

已交付并验收：

- 新增纯 TypeScript `renderKernelSceneSvg()` 与稳定 `kernelSceneDigest()`；导出器直接消费画布已经生成的 `KernelRenderScene`，复用节点/关系 token、route path、label point/angle、展开状态、detail primitive、portal 和图例，不触发第二次布局或路由。
- SVG 根节点和 metadata 保留 kernel version、scene/document/architecture identity、source digest 与 render digest；节点、边、端口、Evidence、template binding/fidelity、detail slot 和 portal 均保留稳定 `data-*` provenance。
- 交互画布根节点与 SVG 同时公开同一 `data-kernel-render-digest`；digest 覆盖节点、边、路径、标签几何、展开 detail、portal、关系和视觉样式，但排除相机、选择与 hover 等非导出状态。
- 顶部导出入口改为正式主视图 SVG/PNG/PDF 菜单。PNG 使用同一 SVG 经浏览器 canvas 栅格化，PDF 再由该 SVG 栅格结果封装为单页 PDF；三种格式不读取 Python `VisualScene` 几何。导出 SVG 为图例保留独立栏，不遮挡场景内容。
- 服务端新增 `/api/publication-export`，返回 `X-ArchCanvas-Export-Scope: publication`；兼容 `/api/export` 同样明确 publication scope，并返回 `Deprecation: true` 与 successor `Link`，Studio 主视图不再链接旧入口。
- 纯内核导出测试覆盖 digest 稳定性、既有 path/label geometry 复用、XML escaping、detail/portal/legend 输出和完整 provenance；前端共 21 个测试文件、110 项测试通过，TypeScript 构建检查通过。
- Phase 5、Phase 6 与 Phase 7 Playwright 在干净正式 API fixture 上连续通过。Phase 7 实际下载并解析 SVG，逐项比对屏幕与导出的 digest、节点、边、path、label transform/text、detail slot、portal 和图例，并校验 PNG magic/dimensions、PDF magic 与 publication endpoint headers。
- 浏览器生成的 PDF 经 `pdfinfo` 验证为单页、未加密 PDF 1.4，并经 `pdftoppm` 回渲完成视觉检查；图例、场景和展开内容无裁切或相互遮挡。`tests/test_protocols.py tests/test_studio.py` 同步通过。

退出条件：同一状态下主视图与 SVG 的节点、边、路径、标签、图例和展开内容一致。

退出证据：Phase 7 E2E 对同一次画布状态的屏幕 DOM 与下载 SVG 做结构及 geometry 精确比对并全部通过；PNG/PDF 均从该已比对 SVG 派生，旧 publication renderer 未进入主视图导出链路。

### Phase 8：清理旧后端 Studio 几何路径

实施状态（2026-09-27）：已完成。Studio 启动、state、navigation、kernel patch、undo/redo、持久化与验证路径均不再构建或物化 Python VisualScene；Python publication 编译器只在显式 publication export/CLI publication 工作流中按需运行。

工作：

- 从 Studio state 移除 `scenes/specs/routing`。
- 从 `StudioBundle` 移除仅服务旧主视图的 `base_scenes`、routing mode 和 shadow 状态。
- 删除不再被 CLI publication 使用的 `routing_*.py` 与 `src/archcanvas_studio/routing.py`。
- 删除旧 layout candidate 缓存和 endpoint。
- 重新生成前端静态资产，不手工保留旧哈希文件。

已交付并验收：

- `StudioBundle` 已移除 `specs`、`base_scenes`、routing mode、shadow sample rate 与 shadow report；`recompile_projection()` 只重建正式 `PublicationView`，`state()` 不再公开 `scenes/specs/routing` 或旧 layout/routing capability。
- Studio 初始化不再调用 `build_visual_spec()`、`build_scene()`、`materialize_scene()`、Python layout/routing 或 geometry validation；搜索索引改用 PublicationView binding，Studio validation 明确验证正式 projection，由浏览器 visual kernel 负责交互几何。
- `/api/patch` 与 `/api/patch-batch` 只用 stable kernel target 白名单验证视觉操作，不再接收服务器 scene map；module expansion 只触发 PublicationView 重投影，常规保存不再刷新 routing shadow。
- 删除 `/api/layout-mode`、`/api/layout-candidates`、`/api/layout-candidates/{id}/apply`、`/api/layout`、`/api/route`、`/api/align` 及服务器 candidate cache；Phase 8 API/E2E 均确认这些路径返回 404。
- 删除 `src/archcanvas_studio/routing.py` 以及不参与 CLI publication 的 Python `archcanvas_publication/routing_*.py` shadow/atomic 实验栈、对应 fixture exporter 和测试；正式 publication compiler/layout/renderers 保留。
- 主程序外层选择与 Inspector 索引改为从 formal state 经 TypeScript visual kernel 派生，不读取服务端 VisualScene；canonical selection 直接作为正式画布选择状态，搜索、导航、框选与多选不再依赖旧 `scene_node_id` binding。
- `/api/publication-export` 与兼容 `/api/export` 在显式请求时才临时编译 publication scene；CLI `studio` 启动 gate 改为 formal projection 与 source-invariance，CLI publication SVG/HTML 流程继续通过。
- 新增启动守卫测试：将 Python `build_scene` 替换为立即失败，验证 bundle 初始化、state、kernel patch、保存和 reload 均不触发它，而显式 publication export 会进入该边界。
- Vite 以 `emptyOutDir` 重新生成正式静态资产；旧 `index-4kYngGul.css`、`index-UQZJRoKO.js`、`index-CgEFOZnx.js` 均已移除，当前 HTML 只引用新哈希资产。
- 前端 21 个测试文件、110 项测试通过；完整 Python pytest、ruff、compileall 与 schema check 通过；P0 视觉验收及 Phase 5、6、7、8 Playwright 在同一隔离 Studio fixture 上连续 5/5 通过。

退出条件：Studio 启动和运行不调用 Python scene layout/routing；CLI publication 测试仍通过。

退出证据：Phase 8 Python 守卫覆盖启动与常规运行的禁止调用边界；Phase 8 Playwright 验证正式 state 合同、旧 endpoint 404、TypeScript kernel DOM 与显式 publication export，Phase 5–7 连续回归同时通过。

## 17. 测试计划

### 17.1 纯内核测试

- 原型现有 routing、expansion、detail-layout、atomic-hierarchy、catalog 测试全部迁移。
- `build/scene-visual-lab/cases/manifest.json` 的 26 拓扑 × 45 视觉组合逐项映射为 production fixture，全部生成有限坐标、有限 path 和有限指标。
- semantic glyph library 的 primitive 类型、数量、bounds、tone 和内部 flow 与基准实例逐项核对。
- parent-child expansion 与 recursive nested expansion 的父容器尺寸、子节点相对位置、入口/出口、portal chain 和折叠恢复逐项核对。
- 相同输入重复运行的 RenderScene digest 一致。
- 输入数组重排不改变稳定 ID 和几何 digest。
- 展开再收起再展开恢复原布局。
- 所有跨层边 portal chain 连续。
- 所有圆形运算节点端点位于中轴。
- 关系/semantic channel 不被错误合并。
- 路由不穿过无关节点，净距和反向出发为 0。

### 17.2 正式数据合同测试

- 每个 KernelNode/Edge/Port 的 canonical/evidence provenance 完整。
- exact binding 的所有 slot 满足 cardinality。
- opaque/schematic 不创建 canonical 实体。
- stale binding 被拒绝并退为 generic，不退为伪 exact。
- `formal-state-adapter.ts` 不读取 scene geometry。
- 正式源码中不存在对 `prototypes/scene-visual-lab` 或 `build/scene-visual-lab` 的 import、fetch 或文件读取。

### 17.3 交互测试

- 节点、边、内部子节点选择。
- 框选、多选、容器与子树拖动。
- resize、对齐、分布和 pin。
- 展开任意深度、收起和复位 detail offset。
- 拖动过程中只有受影响边重算。
- undo/redo 以 PatchBatch 为粒度。
- reload 恢复视觉状态。
- canonical 删除、新建和连接进入正式 draft/proposal 流。

### 17.4 端到端测试

至少覆盖：

1. 打开项目并完成静态分析。
2. 主视图首帧非空且包含节点、边和图例。
3. 模块树选择定位到画布。
4. 展开 attention exact template。
5. 拖动节点并刷新，位置保留。
6. 修改 route/node/label style 并刷新。
7. 导出 SVG，核对可见路径和 metadata。
8. 创建 draft connection，确认 Exact IR 不变。
9. 切换源码与 Evidence tab，确认选择身份一致。
10. 手机视口中工具栏、画布和检查器无重叠。

### 17.5 视觉回归

固定以下视口：

- 1440 × 900
- 1280 × 800
- 1024 × 768
- 390 × 844

固定以下场景：

- linear chain
- fan-in / fan-out
- residual skip
- crossing pressure
- dense bipartite
- parent-child expansion
- attention exact template
- recursive nested expansion
- long labels
- dark theme

P0 视觉回归还必须覆盖：

- `semantic-glyph-library` 中每一类图例式元素。
- `extended-module-catalog` 与六类 catalog 的内部图实现。
- `parent-child-expansion` 展开前、展开后、继续展开、拖动内部子模块和再次收起五个状态。
- Q/K/V、Add、Multiply、Concat、矩阵/张量、frame、nested inline surface 和内部 flow。
- 外部边进入父模块、穿过 portal、连接内部真实节点以及从内部出口继续到下游节点的完整连续路径。

每个 P0 场景保存 build 基准图、production 图和结构化差异报告。截图验收不仅比较像素，还检查 canvas 非空、SVG bounds、primitive 数量、相对布局、文本溢出、图例遮挡、边穿节点、portal 连续性和交互命中区域。

### 17.6 仓库验证

每个阶段至少运行：

```bash
cd studio && npm test
cd studio && npm run build
python -m pytest
python -m compileall -q src tools tests
python tools/export_schemas.py --check
```

完成主视图后运行 Playwright 桌面和移动端截图检查。

## 18. 性能预算

基准环境和 fixture 固定后执行以下预算：

| 场景 | 目标 |
|---|---|
| 200 节点 / 300 边首次生成 | 交互可用前不超过 300 ms |
| 单节点拖动 | 每帧内核与 DOM 更新合计不超过 16.7 ms 的目标帧预算 |
| 展开一个中型模块 | 不超过 120 ms |
| 无关节点重渲染 | 0 |
| 同输入缓存命中 | 不重新运行全图路由 |
| SVG 导出 | 与当前 RenderScene 线性相关，不重新布局 |

优化顺序：

1. 以 node/edge/module digest 做分层缓存。
2. 只重算 gesture affected set。
3. React 只消费稳定 render records。
4. 需要时对屏幕外 detail 层做裁剪，但不能改变导出。
5. 在确认 profile 后再引入 worker，不预先增加并发复杂度。

## 19. 风险与处理

### 风险 1：原型模板看起来正确但没有源码证据

处理：模板只能由 VisualTemplateBinding 激活；未知结构使用 generic/opaque。

### 风险 2：一次删除旧主视图导致非画布能力丢失

处理：Phase 1 先拆应用壳；归档和非画布行为测试必须在删除前完成。

### 风险 3：浏览器主视图与 CLI publication 暂时不同

处理：明确区分 main-view export 与 publication export；主视图先保证同源，后续再让 headless publication 调用同一 TS 内核。

### 风险 4：大图路由阻塞 UI

处理：纯函数缓存、局部 affected set、稳定端口复用和按需 worker。不得用旧 Python scene fallback 掩盖性能问题。

### 风险 5：旧 CanvasDocument patch 指向 scene ID

处理：实现显式 migration report；只能在唯一映射时转换，不能模糊匹配。

### 风险 6：层级不是纯树状数据流

处理：模块归属使用树，数据流继续使用一般有向图；循环、残差、共享参数和跨层边由 edge relation 与 portal chain 表达。

### 风险 7：原型自身存在重复或临时代码

处理：迁移行为和测试，不逐文件复制。正式模块重新定义 API、去除原型 editor state、URL fixture 参数和 scenario runtime。

## 20. 删除清单

完成重建后，以下旧主视图符号不得继续出现在正式运行路径：

- `SceneNodeGraphic`
- `SceneEdgeGraphic`
- `buildSceneRenderIndex`
- `previewNodeTransform`
- `createGestureRouteLock`
- `previewEdgePoints`
- `RoutingShadowReport`
- `AtomicRoutingReport`
- `ARCHCANVAS_ROUTING_ENGINE`
- `ARCHCANVAS_ROUTING_SHADOW_SAMPLE_RATE`
- Studio runtime 的 `legacy` / `shadow` / `atomic-v1`
- `StudioState.scenes` 作为主视图输入
- 原型的 `LabPatch`、`LabScene` 和 scenario selector

允许继续存在但不得被主视图调用：

- CLI publication 的 `VisualScene`
- Python SVG/PNG/PDF renderer
- release bundle 的 publication artifacts

## 21. Definition of Done

只有同时满足以下条件才算完成：

1. 旧 `scene-visual-kernel-integration.md` 已删除。
2. 旧主视图源码、状态 fixture 和截图已有可校验副本。
3. 当前主视图实现和试验性 shadow/fallback 路径已从 Studio runtime 删除。
4. 正式主视图没有任何对原型目录的 import 或运行时文件读取。
5. 主视图由现有 Architecture IR、Evidence、Hierarchy 和 Semantic Overlay 驱动。
6. `build/scene-visual-lab` 的 semantic glyph、全部 catalog、parent-child expansion 和 recursive internal detail 已作为 P0 完成并有并排截图与结构化差异报告。
7. 父模块展开后的子模块布局、内部结构实现、内部 flow、入口/出口和递归嵌套方式没有退化成通用矩形网格或占位图。
8. 主视图完整沿用原型的节点图元、内部结构图、层级展开、路由、标签和紧凑图例视觉语言。
9. exact、opaque、schematic 在 UI 与数据中可区分。
10. 节点拖动、内部子模块拖动、resize、选择、框选、相机、展开、撤销、重做均可用。
11. 新建、删除和重连没有绕过 draft/proposal/transaction。
12. 所有视觉编辑前后 source digest 和 Exact IR digest 不变。
13. 主视图 SVG 导出与屏幕 RenderScene 同源且 digest 可比。
14. 原型测试矩阵、正式模型 fixture、浏览器交互和移动端视觉测试全部通过。
15. `npm test`、`npm run build`、Python tests、compileall 和 schema check 全部通过。
16. 生成静态资产中只保留当前构建引用的哈希文件。

实施验收（2026-09-27）：以上 16 项的自动化验收门均已具备通过证据。当前证据为：前端 24 个测试文件、117 项测试通过；P0 结构 14/14 通过；静态 PNG 视觉门 12/12 通过，另外 2 个交互/递归案例生成明确的 interaction-only 像素差报告；Playwright 主视图与 Phase 5–8 5/5 通过；完整 Python pytest、ruff、compileall 和 schema check 通过；prototype vocabulary 扫描覆盖 1170 个原型 SVG，并为 39 个正式 detail kind 逐一绑定到本地原型标签。正式 SVG 与 React 运行时均输出原型兼容的节点/边/详情结构类，exact attention 的 Q/K/V formal slot contract、矩阵、乘法圆圈和中性 K^T 路由注释已与原型对齐，catalog expanded container 的语义配色已修正；exact/opaque/schematic 在数据、DOM 属性、徽标和边框样式中明确区分。构建和静态资产引用检查均通过。`StudioApp` 的项目、导航和任务 controller 已形成独立 action 模块；后续只需在新增业务边界时保持这些模块化测试，不再把旧主视图路径引回正式 runtime。

## 22. 推荐提交顺序

建议按以下提交组织实施，保持每个提交意图单一：

1. `archive current Studio main view`
2. `extract Studio shell and API client`
3. `remove legacy main-view renderer and routing modes`
4. `add production visual-kernel contracts and fixtures`
5. `port lab glyph catalog detail and parent expansion visuals`
6. `port lab routing hierarchy portals and metrics`
7. `adapt ArchitectureIR and hierarchy to visual kernel`
8. `build prototype-style React main view`
9. `persist visual interactions through CanvasDocument`
10. `connect structural gestures to proposal transactions`
11. `unify main-view SVG export`
12. `remove obsolete Studio geometry APIs and tests`
13. `complete browser visual and performance acceptance`

上述顺序是工程提交边界，不是旧/新主视图并行放量方案。从第 3 个提交开始，正式 Studio 只有新主视图挂载点；第 5 个提交先兑现 build 中最关键的图例、catalog 和父子展开视觉；从第 8 个提交开始，只有新视觉内核负责主视图展示。
