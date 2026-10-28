# Summary_Merge → ArchCanvas Model Architecture Studio：源码对比与移植说明

> **视觉验收修正（2026-10-28）**：用户指出旧混合图存在阶段缺失与连线错乱，先前账本测试与截图不足以证明视觉衔接。已修复展示容器误删、聚焦预算、返回附属及槽位衔接，并加入原版结构对照和浏览器放大检查。当前结果以[残缺问题修复与视觉复核](summary-mixed-presentation-fix-20261028.md)为准；本文件保留历史实现范围。

## 2026-10-28：同图混合切面与所有案例

模块语义深度已作为 Summary 标签页内的折叠区接入，覆盖全部 46 个当前案例。原生 43 例的 877 个源码/运行容器逐个验证原子展开；F0/F1、原生中间切面和任意源码层数可在同一模型组合，子模块有独立优先级。3 个登记预览案例保留原 authority，并提供相同入口中的真实可用层级。面板、编辑、草稿、撤销和 JSON 衔接详见 [本阶段实现与验收边界](summary-mixed-frontier-integration-20261028.md)，具体结果见 [本阶段证据](evidence/summary-mixed-frontier-20261028/validation.json)。

**审计日期：** 2026-10-27；实现更新：2026-10-28  
**源目录：** `/home/fzg/PycharmProjects/ArchCanvas/prototype/Summary_Merge`  
**目标目录：** `/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio`

本文是后续实现的移植基线。它记录两套源码的职责边界、可以复用的功能、正式 Studio 必须保留的面板和事务，以及 F0/F1、视图/编辑双模式、交互细节和源码语义如何接入。本文不是把两个工程目录直接覆盖的复制清单；预览源码语义以迁入的 Summary 实现为主；正式源码写回、事务和文档持久化继续遵守目标工程的契约。

总裁决先固定为：**Summary_Merge 负责视图元素、模块、语义投影、递归前沿、路由和画布交互；正式 Studio 负责前端面板、工作台壳、正式编辑事务、保存和导出入口。** 两边功能重叠时只保留 Summary 的视图/交互 authority，由 Studio 面板发命令并展示结果，不在 React 中复制第二套实现。

## 当前接入状态（2026-10-28）

下方各日期小节保留对应阶段的验证范围；“待迁移”历史描述以此表和最新阶段报告为准。

| 能力 | 当前状态与证据 |
| --- | --- |
| 原生语义、图元、交互、F0/F1 | Summary 接管；[原生视图](summary-native-view-integration-20261028.md)、[D0 旧预览退出](summary-preview-retirement-integration-20261028.md) |
| 视图/组装双模式、源码模块、recipe、局部结构复核 | 已接入 Studio 折叠面板；[组装](summary-authoring-integration-20261028.md)、[源码模块](summary-source-authoring-integration-20261028.md)、[局部复核](summary-local-assembly-integration-20261028.md) |
| 五类文档与完整目录资产 | [文档](summary-documents-integration-20261028.md)已接入；[目录](summary-catalog-integration-20261028.md)43 个条目全部可打开；三大图完整原生/编辑文档接入与限制见[大图阶段](summary-large-operations-integration-20261028.md) |
| 源码/归档 CPU/合并视图 | [证据视图](summary-evidence-views-integration-20261028.md)已接入；当前归档记录没有可唯一核对的调用 regions，合并保留未知边界 |
| 原生测量反馈 adaptive-frontier | [局部细化](summary-adaptive-view-integration-20261028.md)已接入；沿用 Summary 候选/证据规则，使用唯一原生画布的实际文字、端口与路径 |
| Worker 共享语义传输 | [原版传输已接实际通道](summary-worker-transport-integration-20261028.md)；每代隔离、失败恢复；[大图阶段](summary-large-operations-integration-20261028.md)补齐实际取消与三大图 |
| 跨切面来源与自动保存 | [完整来源精确共享](summary-shared-source-integration-20261028.md)；30 次真实切面共用完整 IR，IndexedDB 保存往返通过；大图 30 步真实编辑/撤销/重做另有范围明确的验证 |
| host 快照与浏览器保存恢复 | [完整 IR 引用共享和保存标记恢复](summary-host-source-integration-20261028.md)；便携 JSON 与跨消息传输仍保留完整来源；大图已开放，RSS 限制保留 |
| D1 重复预览模块 | [两旧 helper 和 benchmark 已退出生产](summary-d1-retirement-integration-20261028.md)；正式源码编辑、事务及出版依赖按实际用途保留 |
| 千级图、取消及原生历史 | [三大图实测接入](summary-large-operations-integration-20261028.md)，预算与高 RSS 限制明确保留 |
| 新 CPU 观察、最终功能审计 | [新 CPU 接入](summary-runtime-integration-20261028.md)及[逐项功能审计](summary-migration-feature-audit-20261028.md)已完成本次约定范围的接入验收；资源、文档和样本证明边界明确保留 |

## 1. 结论先行

两边的技术形态不同：

| 层 | `Summary_Merge` 的实际实现 | 正式 Studio 的现有实现 | 移植结论 |
| --- | --- | --- | --- |
| 源码事实 | `semantic_adapter/` 的 21 个 Python 文件，含 AST 抽取、身份/结构/契约校验、运行观察、证据合并和作者模式 | `archcanvas_python/` 生成正式 `Architecture`；`archcanvas_transactions/` 管理参数、激活和输入重绑定 | 预览已切换到迁入的 `archcanvas_summary_semantic`，完整 v2 IR 经 `summary-source-adapter/1` 传递；正式 `Architecture` 仍是源码写回入口，预览不能绕过事务 |
| 语义投影 | `semantic_studio/` 的 45 个 JS/CSS/HTML 文件，`architecture.js`、`publication.js`、角色/路径/契约/值链模块生成可逆展示，`composition-layout.js` 提供 F0/F1 与细化 | React `App.tsx` 显示正式 `CanvasDocument`；递归预览由 `PreviewStudio.tsx` iframe 承载 | 迁入可逆语义和前沿选择；不要把旧 publication 几何直接塞进正式 `Scene` |
| 原生视图和交互 | `yworks_edge_router_lab/` 的 20 个核心文件：递归 authority、物理端口、正交/八方向路由、拖动预览、Worker 事务、撤销/重做、相机、JSON/SVG | `studio/public/preview/yworks_edge_router_lab/` 已有正式副本和同源桥；React 负责外层工具栏与面板 | 以正式副本为运行时来源，不从原型目录加载；桥接命令必须保持来源身份和请求序列 |
| 编辑双模式 | `semantic_studio/index.html` / `authoring.html` 是旧通用画布和独立编辑页；视图可进入原子搭建、组合、参数、端口连接和源码模块 | `WorkspaceModeSwitch` + `AuthoringStudio.tsx`；视图编辑由正式 `CanvasDocument`/视觉历史，模型编辑由 `AuthoredDraft`/受管理源码副本 | 原生模型的编辑和空白组装由 Summary AuthoringModel 接管；保留 Studio 面板和显式正式源码工作副本入口；源码改动仍走正式 transaction |
| 面板 | 原型把模型目录、布线、证据和源码导入放在画布侧栏/抽屉 | 正式 Studio 已有顶部模型菜单、左侧层级树、右侧对象/图例/页面面板和折叠按钮 | 面板以正式 Studio 为壳；Summary 功能放入折叠菜单、右侧 inspector 的新增 section 和预览抽屉 |
| 保存 | 原型递归图使用 IndexedDB/localStorage；旧 IR/canvas/authoring 文档各自兼容 | 正式文档用服务端 CAS/CanvasDocument；预览图仍由 iframe 的浏览器存储负责 | 两种存储继续分离；顶部保存先请求预览保存，再保存正式文档，失败必须分别提示 |
| 导出 | 原型可导出递归 SVG/JSON，旧 publication renderer 另有论文图册 | 正式 `ExportDialog` 使用 publication runtime；预览导出走 `/api/preview/exports` | 预览 SVG 只作为浏览器声明的预览绑定；正式导出收据不伪装成语义重新认证 |

当前目标工程已经包含一轮 Summary 预览迁移和大量未提交的后续 UI/交互改动。本文将“已存在的迁移”与“本轮仍需补齐的产品接入”分开列出，避免把工作树中的实验改动误认为完成的 F0/F1 产品契约。

## 2. 源码阅读范围与基线清单

### 2.1 `Summary_Merge` 的核心源码

以下是本次阅读的运行时源码，不把 `verification/`、`.rollback/`、缓存和生成图片当成实现源：

| 目录 | 数量/规模 | 关键职责 |
| --- | ---: | --- |
| `semantic_adapter/` | 21 个 Python，约 255 KB | `analyzer.py` 读取 Python AST；`schema.py`、`identity.py`、`structure.py`、`contracts.py` 做 IR 守卫；`merge.py`/`observations.py` 合并明确运行证据；`probe.py`/`runtime_worker.py` 是可选 CPU 探针；`authoring.py` 是源码模块和组装认证 |
| `semantic_studio/` | 45 个前端文件，约 969 KB | `architecture.js`、`semantic-engine.js` 生成语义图；`publication.js`、`publication-renderer.js`、`compact-diagrams.js` 负责论文/架构/源码层级投影；`role-*`、`local-*`、`contract-stages.js`、`dimension-paths.js`、`transform-configurations.js` 保留细节语义；`canvas-interaction.js`、`scene-*`、`state-storage.js` 负责旧画布交互和状态 |
| `yworks_edge_router_lab/` | 20 个前端文件，约 408 KB | `app.js` 主循环；`recursive-graph.js` 单一递归 authority 和 frontiers；`graph-engine.js` 图状态；`router.js`、`physical-ports.js`、`route-labels.js`、`semantic-constraints.js` 路由和几何认证；`routing-worker.js` 后台事务；`generic-semantic.js`、`generic-controls.js`、`generic-probe.js` 将通用 IR 接到原生画布；`source-runtime.js`/`source-contracts.js` 管理源码证据 |
| `data/cases/`、`data/semantic/` | 45 个案例文件、48 个语义文件（不含历史验证副本） | 模型目录、源码/运行证据、通用 IR、预设、Transformer 专用案例和展示配置 |
| `tests/`、`tools/`、`docs/` | 回归测试、构建/审计脚本和大量语义边界文档 | 这些是功能边界和复现入口，不能在正式运行时作为隐式依赖加载 |

原型的入口链如下：

```text
index.html
  └─ yworks_edge_router_lab/index.html
       ├─ catalog.js → case/source/IR
       ├─ recursive-graph.js → 当前可见 frontier
       ├─ graph-engine.js + router.js + physical-ports.js
       ├─ routing-worker.js → 展开、路由、完整约束验证、提交/失败恢复
       ├─ generic-semantic.js → 通用 IR → 原生 nodes/edges
       └─ generic-controls.js → F0/F1、语义模式、局部展开、源码/证据入口

semantic_studio/index.html
  ├─ semantic-engine.js → 旧语义投影
  ├─ publication.js / composition-layout.js → 论文/架构切面
  ├─ canvas-interaction.js + scene-worker.js → 旧通用画布
  └─ authoring.html / authoring-model.js → 原子组装和源码模块编辑
```

### 2.2 正式 Studio 的核心源码

| 目录/文件 | 关键职责 |
| --- | --- |
| `src/archcanvas_python/` | 正式源码发现、AST 前端、结构关系、源文件依赖和正式 `Architecture` schema。它是模型事实和源码写回前的正式分析链 |
| `src/archcanvas_preview/analyze.py` | 有界的 Summary 兼容 AST 预览适配器；不 import、不实例化、不执行用户模型；输出 `summary-source-adapter/1` 和 `summary-source-ir/1` |
| `src/archcanvas_cli/server.py` | 单 loopback 服务；提供 `/api/preview/analyze`、`/api/preview/edit-source`、`/api/projects/{id}/preview`、`/api/preview/exports`、Canvas CAS、authoring 和事务 API |
| `studio/src/core/` | `CanvasDocument`、`Architecture`、Scene、端口、正交路由、视觉操作、历史、布局验证、SVG 导出。视觉编辑和 undo/redo 的正式契约在这里 |
| `studio/src/App.tsx` | 正式工作台壳：模型菜单、视图/编辑切换、左树、右侧 inspector、工具栏、保存/导出、正式文档历史、预览桥接和源码/事务入口 |
| `studio/src/PreviewStudio.tsx` | 保持 iframe 常驻，通过 `archcanvas:preview:*` 同源消息调用 Summary 递归画布；负责 ready、请求超时、快照、源码读取、visual 批处理、保存、焦点和通知 |
| `studio/src/previewInterop.ts` | 预览身份与正式节点的来源证据匹配；区分 preview case ID、sourceDigest、irDigest；处理重复实例、分支上下文、父容器、局部坐标和展开回放 |
| `studio/src/previewPresentation.ts`、`previewPanelDocument.ts`、`previewPublication.ts` | 将预览 presentation 投影到正式面板、视觉文档和导出边界；不把预览图元直接当作正式语义节点 |
| `studio/src/AuthoringStudio.tsx` 与 `studio/src/authoring.ts` | 正式从零搭建、源码层级编辑、参数、端口、草稿历史、验证、生成新 managed copy；这是 Python 生成和受管理源码编辑的正式入口；原生组装编辑现由 Summary 面板接管 |
| `studio/public/preview/` | Summary 预览的独立静态副本、案例/源码/snapshot/证据和 `vendor-manifest.json`；运行时不能回溯到 `prototype/Summary_Merge` |

正式前端入口是 `studio/src/main.tsx → App.tsx`，不是原型的静态 `index.html`。正式的模型层级、对象事实、图例、页面和导出面板必须继续由 React 渲染。

## 3. 功能逐项对比

### 3.1 视图模式和 F0/F1

原型中 F0/F1 不是两份独立数据，而是同一份完整 IR 的不同语义前沿：

1. `semantic-engine.js`/`architecture.js` 保留 canonical 节点、边、端口、返回槽位、实例身份和来源证据。
2. `composition-layout.js` 的 frontier/certifiedDetails 选择可见切面；`generic-semantic.js` 将该切面映射为原生递归节点。
3. F1 是中间切面，可以继续进入模块、调用和源码原子层；收起/返回只改变展示前沿，不删除 IR。
4. `publication.js` 的论文/架构/源码模式和 `summary-goals.js` 的覆盖目标是展示策略，不是新的模型事实。

正式副本已有递归 frontier、逐级展开/收起和 `set-frontier` 桥命令；在本轮接入前，产品层尚未显式呈现与原型相同的“F0 架构概览 / F1 架构详图 / 返回概览”语义按钮。此前画布选项只有“展开全部、收起全部、恢复初始视图”，不能让用户区分“架构前沿切换”和“逐个源码容器展开”。

2026-10-28 已进一步用 Summary 原生语义切面替换新导入模型的深度前沿。`App.tsx` 的中央画布菜单和右侧“语义视图”仍发送 `set-frontier({ preset: 'overview' | 'detail' })`，但原生 v2 bundle 由 `studio-semantic.js → generic-semantic.js → composition-layout.js` 处理：F0 使用原生 `frontier`，F1 使用 `certifiedDetails` 的真实角色路径与阶段请求，Worker 完成图元、端口、路由与验证。原生事实、归属账本和切面都保存在唯一的 `graph.generic` 中；`semanticHierarchy` 只是同一切面索引的只读面板投影。旧 catalog / legacy bundle 才继续使用 `recursive.authority` 的深度兼容路径。两条路径按文档类型互斥，React 不维护第二份 authority。child 回报 `frontierPreset`、`semanticView` 和 revision；手动细化为 `custom`，历史和保存恢复该标记。认证 F1 与测量反馈是两项能力；原版 adaptive-frontier/5 现已接入唯一原生画布，见[局部细化报告](summary-adaptive-view-integration-20261028.md)。

同时补齐了右侧“Summary 交互”折叠区：兼容/实时拖动模式、上次路径、安全边界、快照 revision、源码绑定状态，以及布线设置和源码证据入口均通过 bridge 操作。child state 现在发布 `snapshotRevision`、`sourceIdentity`、`interactionMode`、`showGhost` 和 `showObstacles`；这些字段只作为面板状态投影，不构成第二份图模型。

F0/F1 接入要求：

| 要求 | 实现方式 |
| --- | --- |
| F0/F1 由同一 source authority 派生 | 原生文档以 `generic.ir` 和原版语义 projection 为 authority；F1 验证真实契约请求和完整 accounting。旧文档以 `recursive.authority.detail` 保留兼容图 |
| 切换不丢局部展开和布局 | 原生 `generic.layouts` 保留各切面合法位置/路径，`studioCameras` 保留最近四个实际 cut 的相机；旧递归状态继续按原协议恢复 |
| 正式左树同步 | `previewHierarchy.ts` 读取当前 preview display identity；F0/F1 选择后刷新树的 visible/mandatory 集合，不修改正式 Architecture 节点事实 |
| 正式右侧面板可见 | 在现有 inspector 的“视图/层级”折叠 section 中显示当前 frontier、节点/边计数、是否可继续细化、返回概览按钮 |
| 可验证 | 为每个 preset 检查 canonical identity、边界端口、来源证据、布局/路由合法性和回到前沿后的快照稳定性 |

### 3.2 递归展开、折叠和局部编辑

原型的 `recursive-graph.js` 采用一张递归 authority：每个分支可停在不同深度，隐藏内部边投影为最近可见祖先的边界关系，展开时恢复真实后代和端口。`routing-worker.js` 将展开、局部布局、路由和完整验证作为一个事务；失败时 graph、history 和控件一起保持旧状态。

正式副本已经保留这一核心，且 `studio-bridge.js` 暴露 `load`、`snapshot`、`visual`、`set-frontier`、`collapse-all`、`expand-all`、`undo`、`redo`、`focus` 等命令。`PreviewStudio.tsx` 的超时和 `previewInterop.ts` 的请求 gate 防止旧模型回复写入新模型。

必须保持的细节：

- 折叠只影响可见 frontier，不能删除完整源码节点、返回槽位或原始边。
- 展开/收起、手动布局、连接草稿、端口位置和标注分别记录为可撤销的视觉操作。
- 拖动预览只更新受影响子树、连接和标签；释放时才进行完整约束和路由检查。
- 预览图元的世界坐标不能直接当作正式 `CanvasDocument.layout` 的局部坐标，必须经过父容器和来源绑定转换。
- 不能以标签、颜色或距离猜测正式节点；重复调用、共享实例和语法分支必须用来源 span/instance/call identity 匹配。

### 3.3 视图/编辑双模式

原型编辑模式的能力包括：输入/输出、模块库、原子构件、参数、复制/删除、组合为模块、源码自定义模块、精确端口连接、连接替换、保存和往返预览。`authoring-model.js` 以完整递归子树和来源映射为 authority，源码替换会清理过期证书并重新做局部静态认证。

正式 Studio 对应关系：

| Summary 功能 | 正式入口 | 规则 |
| --- | --- | --- |
| 视觉浏览、双击展开、拖动节点、折点/端口、箭头、撤销 | 预览 iframe + 正式顶部 toolbar | 只改 preview presentation；可同步显示名/颜色/图例/页面，但不写 Python |
| 选择源码节点查看证据 | 左侧 `HierarchyTree`、源码抽屉、`ObjectFacts` | 用 `previewInterop.ts` 的来源证据匹配；无唯一匹配时保持 preview-only |
| 参数 `Dropout.p`、激活、输入重绑定 | `ParameterEditor`、`ActivationEditor`、`ConnectionEditor` | 经过正式 prepare/review/approve/commit；需要 managed copy 和规定的 runtime/structural gate |
| 从零搭建、模块组合、原子构件、精确槽位 | `SummaryAuthoringPanel` + 原版 `SemanticAuthoring` | 原生模型默认使用独立声明副本；旧 `AuthoredDraft` 留在显式正式源码菜单；自定义源码模块和参数重解析已接入，见源码模块阶段 |
| 预览连接工具创建的未知连接 | 预览 `connect-tool` | 记录视觉草稿、来源和 invalid route；不能直接生成源码或通过草稿字段绕过身份检查 |

视图/编辑切换必须保留当前预览 iframe，不要销毁 iframe 再重建；否则相机、展开树、路由历史和浏览器存储会丢失。当前 `App.tsx` 已通过 `authoringOpen` 隐藏正式画布而保留 `PreviewStudio`。

### 3.4 路由、物理端口和交互细节

应迁入的原型细节包括：

- 正交、八方向和曲线近似路径；安全距离、交叉/共线重叠代价、保留手动折点、网格候选通道。
- 端口由真实 producer/consumer 和 tuple slot 分配；物理端口位置和 canonical port binding 分离。
- 多输入联合安排、分支边界 gate、容器外框/标题/标签障碍、共享值单通道和独立值分线。
- `compat` 模式按帧预览、`realtime` 模式同步路由；中键平移不改变工具/选择/历史；V/C/B/F 快捷键。
- 错误路径保留 invalid draft 并给出反馈；取消、过期请求或 Worker 失败要恢复完整 gesture baseline。
- 选择、框选、多选、对齐/分布、固定节点和源层级聚焦使用递归图的真实显示 identity。

正式副本的这些能力位于 `router.js`、`graph-engine.js`、`physical-ports.js`、`semantic-constraints.js`、`routing-worker.js`、`studio-selection.js` 和 `view-navigation.js`。正式 React 工具栏已保留选择、连接、折点、端口、对齐/分布、固定、网格、全图和 Apply；布线设置、证据和源码导入作为 Summary 抽屉打开。

### 3.5 源码语义和未知边界

**本段记录 2026-10-27 基线；2026-10-28 已迁入原生静态语义包，当前差异见第 10 节。** `Summary_Merge/semantic_adapter` 比当时正式 `archcanvas_preview` 更宽：它包含合并 runtime receipt、motif/contract 认证、静态符号值、源码结构和 CPU 探针。正式预览适配器目前是有界子集，源码中明确限制为 80 文件、2 MB 源码、480 节点、3600 边、深度 10（具体能力以 `/api/capabilities` 实际返回为准），动态分支、循环、in-place、复杂继承和外部 helper 保留为 opaque/diagnostic。

因此移植规则是：

1. 预览 IR 只证明“源码结构和依赖事实可展示”，不证明张量 shape、dtype、运行路径或新源码等价。
2. 正式 `Architecture` 仍由 `archcanvas_python` 生成，参数/激活/重绑定仍由事务服务复核；不能把 preview IR 直接提交为 source transaction。
3. Summary 的运行探针不作为预览默认路径迁入。若需要运行确认，走正式 `archcanvas_runtime` 的显式输入、隔离 profile 和 receipt。
4. 不支持的来源必须显示具体诊断和源码位置；不能用节点名称或旧 SVG 几何填补事实。

### 3.6 保存、恢复和导出

目标状态必须分成三类：

| 状态 | 存储 | 可否进入源码事务 |
| --- | --- | --- |
| 递归图、frontier、路由、相机、预览草稿、预览撤销栈 | iframe IndexedDB/localStorage；编辑 JSON 可搬运 | 否，视觉状态 |
| 正式 `CanvasDocument`、视觉历史、显示名、样式、图例、注释、页面 | 正式服务 `.archcanvas` CAS | 只保存视觉文档；source binding 不可变 |
| `AuthoredDraft`、managed source、prepare/review/approval/commit journal | 正式 authoring/transaction store | 是，且必须经过正式守卫 |

顶部“保存”应保持以下顺序：

1. 冻结当前 source case、sourceDigest、irDigest 和 preview snapshot。
2. 请求 iframe `save`，确认 IndexedDB 写入完成。
3. 将当前预览 presentation/布局映射到正式视觉文档；若是 preview-only，保存其明确的 preview identity。
4. 以正式 CAS revision 保存 CanvasDocument/history。
5. 任一步失败都保留内存状态，分别提示“预览未保存”或“正式文档未保存”，不能假报全成功。

预览 SVG 导出可以调用 `/api/preview/exports`，但收据必须保持 `browser-declared-preview-binding` 和 `sourceBindingVerified: false`。正式 publication SVG/PDF/PNG 继续使用 `ExportDialog`、`archcanvas_publication` 和正式 renderer；不能把旧 `publication-renderer.js` 的尺寸/排版结果当成正式 Studio 的出版认证。

### 3.7 重叠功能的权威裁决规则（Summary 主视图，Studio 主面板）

本节是移植时的强制优先级。只要两边都实现了同一个用户可见能力，就按以下规则裁决：**视图语义和画布行为以 `Summary_Merge` 为主，前端面板、工作台壳和正式事务以 `ArchCanvas_Model_Architecture_Studio` 为主。**“以 Summary 为主”表示正式 Studio 通过 bridge 调用 Summary 的现有 authority；不表示在 React 中再实现一份相似算法。

#### 3.7.1 什么算“重叠功能”

满足以下任一条件，就视为重叠，不能保留两套并行实现：

1. 两边都能决定同一个视图事实，例如节点是否显示、模块边界、边的端点、端口位置、箭头方向、路由折点、递归深度、F0/F1 前沿或选择 identity。
2. 两边都能响应同一个画布手势，例如展开/收起、拖动、连接、断开、框选、对齐、撤销/重做、相机聚焦或局部布局。
3. 两边都能生成同一个面板字段，例如显示名、颜色、图例、页面、来源 span、证据模式或当前 frontier。
4. 两边都能把同一动作写入可恢复状态，例如布局、frontier、路由、相机、选择和视觉历史。

只有实现层级不同而目标不同的能力才不算重叠。例如，Summary 可以提供“当前递归图的 frontier 计数”，Studio 可以提供“右侧 inspector 的折叠状态”；前者是预览状态，后者是 UI session 状态。判断依据是字段的所有权和恢复范围，而不是按钮文字是否相同。

#### 3.7.2 权威矩阵

| 功能类别 | 唯一权威 | 正式 Studio 的角色 | 禁止行为 |
| --- | --- | --- | --- |
| 节点、模块、glyph、模块层级 | Summary recursive authority 与 semantic projection | React 面板读取 `preview snapshot`，显示计数、筛选和来源 | 正式 `Scene` 重新推导模块或覆盖 Summary glyph |
| 边、箭头、端口、端口槽位、路由折点 | Summary graph/router/physical-port pipeline | 提供布线设置入口、状态摘要和错误提示 | React 自己计算端点、布线或用标签猜测连接 |
| F0、F1、递归 frontier、局部展开 | Summary frontier authority | 提供 F0/F1/返回/展开/收起按钮，并显示当前前沿 | `HierarchyTree` 自行生成另一套 frontier 或修改 `Architecture` 节点 |
| 展开、收起、局部布局、拖动预览 | Summary worker transaction 与 visual history | 发送命令、显示 pending/invalid/committed 状态 | `App.tsx` 直接改 iframe graph 或绕过 worker 写布局 |
| 选择、框选、多选、聚焦、相机 | Summary selection/view state | 将 preview identity 映射到左树和 inspector | 维护与 child 不一致的第二个 selection state |
| 连接草稿、折点编辑、撤销/重做 | Summary visual draft/history | 提供 toolbar 入口、提交/取消和状态反馈 | 将视觉草稿直接当作源码连接或正式 transaction |
| 显示名、颜色、图例、页面、视图标签 | Summary presentation 是预览显示权威；Studio 面板是编辑入口 | 面板编辑后通过 bridge 提交并刷新 snapshot | 面板本地保存一份与预览不同的显示状态 |
| 来源 span、实例 identity、证据模式 | Summary source evidence + `previewInterop` 映射 | 展示证据、源码抽屉入口和 preview-only 标识 | 以名称、颜色、距离或数组下标匹配对象 |
| 源码事实、正式 `Architecture`、结构关系 | 正式 Studio analyzer/authoring | 提供正式编辑、校验和事务入口 | 从 preview graph 直接生成或写回 Python |
| 参数、激活、输入重绑定、源码 region | 正式 Studio transaction | `prepare → review → approve → commit`，管理 managed copy | Summary 的视觉连接或参数草稿绕过正式守卫 |
| 从零搭建、模块组合、自定义源码模块 | Summary `SemanticAuthoring` / `studio-authoring` | Studio `SummaryAuthoringPanel` 提供折叠表单；正式源码生成保留显式 `AuthoringStudio` 入口 | 嵌入旧 `authoring.html` 形成第二个编辑工作台 |
| 保存、恢复、CAS revision、导出入口 | 正式 Studio 工作台和服务 | 统一顶部按钮，协调 preview 保存与正式 CAS | 保留两套独立“保存成功”状态或覆盖 CAS |
| 预览 IndexedDB/localStorage、递归 snapshot | Summary child storage | 保存前请求 child flush，并记录 snapshot identity | 用 `CanvasDocument` 覆盖 child frontier/layout 状态 |

表中的“唯一权威”是运行时决策点。代码可以在正式 Studio 中有一个薄适配器或按钮 handler，但该适配器不得复制 authority 的数据结构、算法或第二份持久化字段。

#### 3.7.3 正式运行时消息流

两边的职责应通过单向命令和带 revision 的快照连接，推荐消息流如下：

```text
Studio App / toolbar / panel
  ├─ command: set-frontier | expand | collapse | visual | focus | undo | redo | save
  └─ transaction request: parameter | activation | rebind | authoring | commit
          │
          ▼
PreviewStudio + previewInterop
  ├─ 校验 modelId、sourceDigest、irDigest、requestId、previewIdentity
  ├─ 将 Studio 面板命令转换为 archcanvas:preview:* bridge 消息
  └─ 丢弃过期响应，不把旧模型结果写入当前面板
          │
          ▼
Summary preview child
  ├─ recursive authority / semantic projection / router / worker
  ├─ 产生新的 snapshot、selection、frontier、layout、history revision
  └─ 返回 source evidence、display identity、计数和诊断
          │
          ▼
Studio presentation adapters
  ├─ 更新 iframe、HierarchyTree、ObjectFacts、图例/页面和状态栏
  └─ 仅把允许的 presentation 字段映射到 CanvasDocument
```

正式源码事务走另一条路径：`Studio panel → formal API prepare/review/approve/commit → analyzer/transaction store → 新 sourceDigest → 重新分析并加载新的 Summary preview`。预览 child 的 `visual` 命令永远不能跳过这条路径。所有命令都应带 `requestId` 和当前 source identity；响应必须带 `snapshotRevision`，以便面板判断是否仍可应用。

#### 3.7.4 状态同步方向和字段边界

| 字段/状态 | 来源 | 同步方向 | 说明 |
| --- | --- | --- | --- |
| `frontier`、`open`、`folded`、`layouts`、路由和相机 | Summary child | child → Studio 展示；Studio → child 命令 | Studio 不直接改值，只发命令 |
| 预览选择和显示 identity | Summary child | child → Studio | Studio 可请求 `focus`，不能自行选中另一个 identity |
| 显示名、颜色、图例、页面 | Studio 面板编辑意图；Summary presentation 落地 | Studio → child 命令，child → Studio snapshot | 以 child 返回值作为最终显示结果 |
| 来源 span、实例/call identity、证据和诊断 | Summary source adapter/child | child → Studio | 面板只读；无法唯一匹配时保持 preview-only |
| 参数、激活、输入重绑定、源码文本 | 正式 transaction store | Studio → formal API；新 sourceDigest → child | 不通过 preview visual snapshot 写回 |
| `CanvasDocument` 视觉文档与 CAS revision | 正式 Studio | Studio → CAS；恢复时 Studio → child 命令 | 只能保存已允许的 presentation 映射 |
| 面板折叠、选中的 inspector section、临时菜单 | Studio UI session | Studio 内部 | 不写入 child frontier/layout/localStorage |

同步应以完整 snapshot 或带 revision 的增量为准；禁止通过 DOM 读取 iframe 内部节点、复制旧全局变量或依赖按钮文字推断状态。对于重复实例、共享节点和条件分支，映射必须携带来源 span、instance/call identity、父容器和局部坐标上下文。

#### 3.7.5 冲突和失败处理

- Summary snapshot 与 Studio 面板缓存不一致时，以 Summary 最新 `snapshotRevision` 为准，面板重新渲染并清除过期本地草稿。
- Studio 发出命令后若 child 返回 `stale-request`、`source-mismatch` 或超时，保留上一个合法 snapshot；不能把 optimistic 面板状态当成已提交。
- 正式 transaction 成功但新 sourceDigest 尚未加载时，界面显示“已提交，预览重建中”，不能继续编辑旧 preview identity。
- 预览路由或布局失败时保留 invalid draft 和诊断，恢复到最后一个合法 visual history；不得静默改成另一条路由。
- CAS 保存冲突、浏览器存储不可用或导出失败时分别提示对应层级；不能显示统一的“全部已保存”。
- 任一映射无法证明唯一来源时，降级为 preview-only，并在 inspector 显示源码位置和原因；不能猜测或自动绑定正式节点。

#### 3.7.6 面板接入的验收要求

每个 Summary 功能接入正式面板后，至少要证明以下行为：

1. **F0/F1**：从 F0 进入 F1，再返回 F0，节点/边/端口 identity 不变，局部展开、布局和相机按前沿恢复；左树和右 inspector 显示同一 `snapshotRevision`。
2. **模块与视图元素**：模块边界、glyph、箭头、端口和路由来自 Summary；调整面板折叠或切换页面不会改变画布结果。
3. **交互**：拖动、连接、折点、框选、对齐、固定、撤销/重做经由 child worker 完成；过期响应不会污染新模型。
4. **双模式**：视图模式的任何 visual 操作都不会改变源码 digest；编辑模式的参数/激活/重绑定经过正式 transaction，返回视图使用新的 digest。
5. **面板保留**：模型菜单、层级树、对象、图例、页面、保存和导出仍从正式 Studio 入口可达；Summary 功能位于折叠 section，不新增第二套主侧栏。
6. **没有双 authority**：代码审查和运行时检查都不能发现第二个 renderer、router、frontier authority、selection store 或独立的“保存成功”状态。

迁移完成的判定不是“按钮存在”，而是同一个操作无论从画布 toolbar、左树还是右 inspector 发起，都最终调用同一个 Summary authority，并由正式 Studio 统一呈现状态和承担事务边界。

## 4. 目标 UI 结构：保留主程序面板，折叠接入 Summary 功能

正式 Studio 的 UI 骨架应保持如下结构：

```text
顶部：模型菜单 | 视图 / 编辑 | 保存 | 导出 | 保存状态
左侧：模型层级树 | 源码证据抽屉
中部：Summary 递归画布（iframe）
      选择/连接/折点/端口/撤销/重做/对齐/固定/网格/全图/Apply
右侧：对象 | 图例 | 页面
      ├─ 对象：显示、排列与层级、连接点、正式参数/激活/重绑定、事实、来源
      ├─ 语义视图（新增折叠区）：证据模式、F0/F1、展开/返回、源码细节入口
      ├─ Summary 交互（新增折叠区）：上次路径、安全边界、端口、路由/箭头抽屉入口
      └─ 预览连接：预览边样式、草稿/正式关系标识和来源说明
底部：统一状态、当前 revision、RECURSIVE PREVIEW
```

具体接入建议：

- **模型菜单**：保留现有“新建空白模型、导入 Python、查看源码、内置示例、示例与模块库、原型来源与审查记录”。不要把原型目录列表再渲染一份到 React。
- **画布选项折叠菜单**：保留“布线与箭头设置、展开全部、收起全部、恢复初始视图”；新增“架构概览（F0）”“架构详图（F1）”“返回当前前沿/源码层级”。
- **右侧 inspector**：只显示当前选中对象的局部语义摘要、来源 span、证据模式和可用细化动作；完整源码仍走左侧源码抽屉，完整证据仍走 iframe 审查对话框。
- **编辑模式**：沿用 `AuthoringStudio` 的模块库、草稿画布、参数/端口检查、源码 region 编辑、验证、生成和返回视图，不嵌入原型的 `authoring.html`。
- **折叠状态**：面板折叠属于 Studio UI session；F0/F1/frontier 和画布布局属于预览 presentation；二者不能共用一个 localStorage key。

### 4.1 功能与面板的衔接总原则

正式 Studio 的面板是 Summary 预览的 **命令壳和状态投影层**。面板不读取 iframe DOM，不复制 `graph`，不自行计算路由或 frontier；它只通过 `PreviewStudio` 暴露的 `load`、`snapshot`、`source`、`visual`、`focus`、`save` 和 `command` 调用 child，并根据 child 返回的 `state`、`selection`、`notice`、`error` 重绘。

每次衔接都要保留四个身份字段：`caseId`、`sourceDigest`、`irDigest`、`previewIdentity`。此外，变更请求使用 `requestId`，状态使用 child 的 `snapshotRevision`/`revision`。面板可以显示 optimistic 的“处理中”，但只有收到新的 child snapshot 后才能显示“已应用”或更新正式文档。面板折叠、当前 tab、搜索文字和临时菜单属于 Studio session，不写入 Summary graph。

衔接的基本生命周期如下：

```text
1. PreviewStudio hello
   → ready(capabilities) → load(bundle)
   → loaded/state(document)
2. Summary child 用户操作
   → selection/state/notice/error
   → PreviewStudio 回调 App
   → previewInterop 映射 preview identity
   → HierarchyTree/ObjectFacts/状态栏刷新
3. Studio 面板操作
   → 校验当前 caseId/sourceDigest/selected identity
   → command 或 visual(operation batch)
   → child worker/graph authority 提交
   → applied/state(snapshotRevision)
4. Studio 保存
   → child save（IndexedDB flush）
   → presentation 映射到 CanvasDocument
   → 正式 CAS 保存
```

如果 child 忙于加载、拖动或 Worker 事务，所有改变 graph 的面板按钮应禁用；只读的源码、snapshot 和 ping 可以按 bridge 契约读取。超时、`source-mismatch`、`stale-request` 或 `error` 只能回到上一个合法 snapshot，不能用面板缓存覆盖 child。

`PreviewStudio.command()` 也必须遵守握手和顺序：React 工具栏可以使用
fire-and-forget 调用，但 bridge 会在 iframe `ready` 后再发送，并串行投递连续
命令。这样首次加载期间点击 F0/F1、工具、抽屉或辅助显示不会静默丢失；命令失败仍通过
`onError` 回到 Studio，而不是伪造已应用状态。

### 4.2 顶部菜单、模式切换和统一入口

| 正式面板控件 | Summary 功能衔接 | 面板收到的状态 | 具体规则 |
| --- | --- | --- | --- |
| “模型 → 内置示例” | Studio 选择正式示例后调用 `load(bundle)`；示例与模块库按钮调用 `show-library` | `loaded`、`state.caseInfo`、`sourceAvailable` | 切换前保存或明确丢弃当前 preview dirty 状态；旧 `caseId` 的 selection、source 和 snapshot 不得带入新模型 |
| “模型 → 示例与模块库” | `command('show-library')` 打开 child 原有目录/抽屉 | child `notice`、当前 case | 目录内容仍由 Summary catalog 提供；React 不再复制一份案例列表 |
| “模型 → 原型来源与审查记录” | `command('show-evidence')` | child dialog 状态和 source evidence | 这是查看来源的入口，不改变正式 `Architecture` 或源码绑定 |
| “导入 Python 源码” | 正式 `SourceImportDialog` 负责文件大小、entry 和 API 分析；通过 `show-import` 可打开 Summary 导入抽屉 | `edit-source`、`source`、diagnostics | 解析结果先是 preview-only；只有进入正式编辑/managed copy 后才允许参数或源码事务 |
| `WorkspaceModeSwitch：视图` | 保持 iframe 常驻，所有视图操作走 Summary | `tool`、`busy`、`dirty`、`canUndo`、`canRedo` | 视图模式只产生 presentation/visual draft，不改变 Python source digest |
| `WorkspaceModeSwitch：编辑` | 先 `snapshot`/`save`，确认 source evidence，再打开 `AuthoringStudio` 或正式 source editor | `sourceAvailable`、`caseId`、`sourceDigest` | 不能把 preview graph 直接当作 formal `Architecture`；进入编辑后使用 managed copy 和正式 transaction |
| 顶部“保存” | 先调用 child `save`，再映射 `studioPresentation` 到 `CanvasDocument` 并走 CAS | child `saved` + formal revision | 必须分别展示“预览已保存”和“正式文档已保存”；任一失败都保留内存状态 |
| 顶部“导出” | 预览选择使用 child `svg`/`export-svg` 或 `/api/preview/exports`；正式文档使用 `ExportDialog` | preview receipt 或 publication receipt | 两种 receipt 必须标明来源；预览导出不能伪装成正式 publication 认证 |

### 4.3 左侧模型层级面板的衔接

`HierarchyTree` 不是第二个模型解析器。它从 `previewHierarchy(snapshot)` 取得 Summary 的真实 display identity、parent、children、repeat 和 mandatory root 信息，再把用户动作转成 child 命令：

| 左树动作 | 调用 | Summary 处理 | 返回后的面板动作 |
| --- | --- | --- | --- |
| 搜索模块 | 本地过滤 display identity 和来源路径 | 不改变 graph；匹配隐藏节点时只准备祖先路径 | 显示匹配路径，不能创建新的 formal node |
| 点击节点 | `focus({ nodeId })` 或 additive focus | child 展开必要祖先并更新真实 selection | child `selection` 回流后同步左树、iframe 和右侧 inspector |
| 展开/收起三角 | `set-frontier({ locations/sourceLocations, expanded })` 或 `visual([{type:'expand'}])` | recursive authority 事务化更新 frontier、路由和历史 | 等待 `state`；失败时树恢复原状态并显示诊断 |
| 选择同级/全部/清空 | `select-nodes({scope:'siblings'|'all'|'clear'})` | child 根据可见节点和 junction 规则选择 | 只使用 child 返回的 `selectedNodes`，不由 React 猜测选区 |
| 固定节点 | `pin-selection({pinned})` | Summary 保存 pinned presentation 并限制直接拖动 | 左树只显示锁定状态，位置仍由 child 控制 |
| 选中 preview-only 节点 | `focus` + source location | child 返回 evidence/opaque/source-unavailable | 右侧只显示视觉事实和源码位置，不显示可提交的 formal 参数编辑器 |

左树的 `expandedIds`、`mandatoryIds`、`pinnedObjects` 如果来自 formal `CanvasDocument`，只能用于正式文档兼容；当前预览树应优先使用 child snapshot 中的 `recursive.authority` 和 `studioPresentation`。同一节点在不同调用、共享实例或不同分支中的 identity 不能用 label 或数组下标合并。

### 4.4 中央 toolbar、iframe 和 Summary 功能的逐项对应

中央区域分成两部分：React toolbar 只发命令，iframe 负责图元、端口、路由和手势。对应关系如下：

| Toolbar/画布功能 | 命令或回调 | Summary authority | React 端允许做的事 |
| --- | --- | --- | --- |
| 选择、框选、多选 | `select-tool`、`select-nodes`；child 发布 `selection` | `studio-selection.js` | 更新按钮高亮、选中数量和 inspector；不维护第二套 selected node 集合 |
| 创建连接 | `connect-tool`；child 记录 `sourceDraftOperations` | `graph-engine.js` + source contracts | 显示“视觉草稿连接”标签和 Apply 状态；不能直接调用 formal rebind |
| 编辑折点 | `bend-tool` + child pointer gesture | `router.js`/`routing-worker.js` | 显示 pending/invalid；不能把宿主坐标写入 `CanvasDocument.layout` |
| 显示端口、拖动 S/T 端点 | `show-ports`、child `visual` 的 `portLayout` | `physical-ports.js` + semantic constraints | 显示端口状态和错误；canonical producer/consumer 由 child 保持 |
| 撤销/重做 | `undo`、`redo` | child history | 更新 `canUndo`/`canRedo`；正式 Canvas history 只保存允许的 presentation 映射 |
| 对齐/分布 | `arrange-selection({kind, scope})` | child 对可见 sibling 做原子布局事务 | 发送所选范围和 disabled 状态，不自行算坐标 |
| 固定/解锁 | `pin-selection({pinned})` | child presentation state | 显示锁图标；固定不等于正式源码属性 |
| 优化连线 | `apply-layout` | router worker、完整 route/layout validation | 等待 `busy=false` 和新 snapshot；失败保留 invalid draft |
| 网格、适合画布、缩放 | `grid`、`fit`、`zoom` | child `view-navigation.js` 和 camera | 只同步按钮状态；camera 不写 formal source |
| 布线与箭头设置 | `show-routing` | child routing drawer 和当前 options | React 不复制 clearance、crossing、overlap、port side 等设置 |
| 展开全部/收起全部 | `expand-all`、`collapse-all` | recursive authority 事务 | 等待新 frontier 后刷新左树和计数 |
| 恢复初始视图 | `reset` | child original graph + undo history | 提示“可撤销”；不能重建一份新的 React graph |
| F0/F1/源码层级 | `set-frontier` 支持 `overview`/`detail` 命名 preset，并保留 `locations/sourceLocations` 兼容入口 | Summary frontier/semantic authority | F0/F1 按钮只发送 preset；右侧显示 current frontier、可继续细化和返回入口 |

iframe 必须保持挂载。切换到源码抽屉、右侧 inspector 或 `AuthoringStudio` 时只隐藏画布，不销毁 child，否则 camera、展开树、Worker history 和浏览器存储会丢失。child 自己产生的 selection、notice 和 state 是面板刷新唯一依据。

### 4.5 右侧 inspector 的字段和操作分层

右侧 inspector 需要把“Summary 视觉事实”和“正式源码事实”明确分区，避免用户把同一控件理解为源码编辑：

| Inspector 区域 | 数据来源 | 可执行操作 | 是否进入源码事务 |
| --- | --- | --- | --- |
| 预览选区摘要 | child `selection`、`state.selectedNodes` | 清空、聚焦、查看选中名称 | 否 |
| 视觉对象“显示” | child `studioPresentation.nodes` | `visual` 的 `alias`、`nodeStyle` | 否；保存到 preview presentation/CAS 视觉文档 |
| “排列与层级” | child node x/y、expanded、pinned、frontier | `focus`、`set-frontier`、`visual(move/expand/pin)` | 否 |
| “连接点/连线样式” | child physical port、edge route、binding/evidence | `show-ports`、`visual(portLayout/edgeStyle)`、打开布线抽屉 | 否；视觉草稿保留 source binding 和 invalid 状态 |
| 源码证据 | child `sourcePath`、`line`、`span`、evidence | 打开左侧源码 drawer、定位源码行 | 只读；不能从名称反推正式节点 |
| 正式参数 | formal `ArchitectureNode.parameters` + `Capabilities` | `ParameterEditor` → prepare/review/approve/commit | 是；需要正式 source binding 和 managed copy |
| 激活/输入重绑定 | formal transaction API + runtime profile | `ActivationEditor`、`ConnectionEditor` | 是；需要 runtime/structural gate，预览 connection 只能生成提案 |
| 图例 | child presentation 与 Studio 当前页面 | `visual(legend)` 或 `syncPresentation` | 否；可随正式 CanvasDocument 保存 |
| 页面/说明文字 | child/Studio page presentation | `visual(page/annotation)`、预览导出或正式 publication 导出 | 视觉说明可保存；不改变源码语义 |

当选中节点只有 preview identity 而没有唯一 formal binding 时，inspector 应显示“源码检查 · 视觉对象”，只开放显示名、颜色、展开和源码查看；参数、激活、重绑定按钮必须禁用并说明原因。只有 `previewInterop.ts` 证明唯一来源 span/instance/call identity 后，才显示正式编辑器。

### 4.6 F0/F1、源码证据和编辑模式的跨面板流程

一次完整的 F0/F1 操作应按以下顺序衔接：

1. 用户在中央 toolbar 或右侧“语义视图”点击 F0/F1；Studio 根据当前 `caseId` 发送 `set-frontier` 命名 preset，源码定位仍使用 locations 兼容入口。
2. child 保存当前 open/folded/layout/presentation，Worker 计算新的 frontier、端口和路由；成功后发布 `state`，失败则发布 `error` 并恢复旧 snapshot。
3. `previewHierarchy` 用新的 display identity 重建左树；右侧显示当前 frontier、可细化对象数、节点/边计数和 source evidence；中央 iframe 保留 camera/selection 能力。
4. 用户点击源码证据时，Studio 调用 `focus({sourcePath,line})`；child 展开必要祖先并返回 selection/span；源码 drawer 只显示对应文件和行范围。
5. 用户点击“进入编辑”时，Studio 先保存 preview snapshot，再验证 sourceAvailable 和 formal binding；进入 `AuthoringStudio` 使用 managed source copy。
6. 编辑提交后产生新的 `sourceDigest`/`irDigest`，Studio 丢弃旧 preview identity，重新加载新的 Summary bundle；旧 preview 的视觉草稿不能自动复活。

F0/F1 按钮、层级树展开、画布双击和源码行聚焦都必须最终改变同一个 child frontier。验收时要从四个入口分别触发同一节点的展开，再比较 `snapshotRevision`、display identity、路由、端口和 undo 栈，不能只比较按钮是否变成 active。

### 4.7 保存、通知和错误状态在面板中的显示

| 状态 | 中央画布 | 左树/右侧 | 顶部/底部 |
| --- | --- | --- | --- |
| `ready/loading` | iframe 显示 loading，禁用改变 graph 的按钮 | 保留上一个树或显示载入中 | 显示“正在载入模型图与布线引擎…” |
| `busy/dragging` | child 保持当前 gesture，禁止并发 mutation | 只允许只读源码和状态查看 | 显示处理中，不把临时几何写入正式文档 |
| `dirty` | 显示视觉草稿/未提交路线 | inspector 标注 preview-only/draft | 顶部“有未保存编辑” |
| `applied` | 显示新 route/frontier/layout | 以新 snapshot 刷新树和事实 | 显示操作成功和新的 revision |
| `invalid draft` | 保留红色/无效草稿和诊断 | 显示端口、来源或障碍原因 | 显示错误，但不自动换路 |
| `source-unavailable` | 仍可浏览和视觉编辑 | 隐藏正式参数/源码事务按钮 | 说明当前仅为预览 |
| `save` 部分成功 | 保留 child 状态 | 显示 preview/CAS 各自保存结果 | 禁止显示统一“全部已保存” |
| `source-mismatch/stale` | 回到最后合法 child snapshot | 清理过期面板草稿 | 要求重新聚焦或重新载入 |

通知必须携带操作名和层级（preview、formal transaction、CAS、export）。`onNotice` 用于用户可恢复反馈，`onError` 用于命令失败或身份错误；两者都不能把 source writeback 描述成普通视觉编辑。

## 5. 文件映射与实现责任

| Summary 源文件/模块 | 正式目标 | 处理方式 |
| --- | --- | --- |
| `yworks_edge_router_lab/router.js`、`graph-engine.js`、`physical-ports.js`、`recursive-graph.js`、`routing-worker.js` | `studio/public/preview/yworks_edge_router_lab/` 同名文件 | 作为静态 vendor 副本独立运行；允许 Studio 适配补丁，但每项补丁写入 `integration-manifest.json` 并有专项测试 |
| `yworks_edge_router_lab/app.js`、`index.html`、`styles.css` | `studio/public/preview/yworks_edge_router_lab/` | 保留 standalone 能力；`embed=1&surface=canvas` 隐藏重复工具，交由正式 toolbar；抽屉和证据对话框仍由 child 管理 |
| `generic-semantic.js`、`source-runtime.js`、`flow-optimizer.js` | `studio/public/preview/yworks_edge_router_lab/` 同名文件 + `studio-semantic.js` | 原版纯语义/原生图元路径已迁入；Studio 折叠面板代替旧 generic-controls 侧栏，generic-probe 仍待正式隔离接入 |
| `semantic_studio/architecture.js`、`semantic-engine.js`、`publication.js`、`composition-layout.js` | `studio/public/preview/semantic_studio/` 同名纯模块 | 原样迁入语义 projection，`semanticOnly` 不加载旧 renderer；原生 G 生成图元和布局，不把旧 publication 坐标传入正式 Scene |
| `semantic_studio/role-*`、`local-*`、`contract-stages.js`、`dimension-paths.js`、`transform-configurations.js` | Preview child 的 evidence/detail 数据和正式 `ObjectFacts`/源码抽屉 | 先保留为 preview evidence；需要正式显示时通过稳定字段投影，不重建事实 |
| `semantic_studio/authoring-model.js`、`authoring-app.js` | `studio/src/AuthoringStudio.tsx`、`authoring.ts`、`archcanvas_authoring/` | Summary 的原子/槽位/组装语义为迁入目标；保留 Studio 面板与正式受管理源码/事务边界，逐项适配而非另挂旧编辑页 |
| `semantic_adapter/analyzer.py` | `archcanvas_summary_semantic/` + `archcanvas_preview/semantic_bridge.py` | 已复制 21 个 Python 文件；Studio 新请求用原生 v2 语义，旧 `analyze.py` 仅兼容。正式源码写回仍由 formal analyzer 生成，禁止运行时导入 prototype 包 |
| `semantic_adapter/probe.py`、`runtime_worker.py` | `archcanvas_runtime/`、`RuntimeProfileDialog` | 不能直接复制旧 subprocess 逻辑；使用正式隔离 profile、输入规格和 receipt |
| Summary `data/catalog*`、`data/cases`、`snapshots`、source packages | `studio/public/preview/data`、`snapshots`、`sources` | 通过 `vendor-manifest.json`、`catalog-sources.json`、`source-packages.json` 绑定来源；运行时不读取原型绝对路径 |
| Summary `tools/`、`verification/`、旧 browser storage | `docs/evidence/`、正式 tests、迁移 manifest | 只选取可复核证据；不把历史报告或浏览器状态当成当前正式认证 |

当前 vendor 清单登记了 230 个案例（115 active、115 historical）、666 个视图和 5,730 个 snapshot 文件；这代表离线资产保留，不等于所有案例都拥有正式 `Architecture` 绑定。预览源码索引和正式模型目录必须分别显示可解析、preview-only、无源码证据三种状态。

## 6. 分阶段实施计划

### P0：冻结审计基线

- 保留本文和当前 `vendor-manifest.json`/`integration-manifest.json`。
- 记录目标工作树的未提交改动；后续不要用 `git clean` 或复制脚本覆盖它们。
- 用 `/api/capabilities` 读取真实 preview limits、正式 runtime/publication 能力，不从 README 猜测。

### P1：完成契约和身份桥

- 固化 `summary-source-adapter/1`、`summary-source-ir/1`、`previewIdentity`、`CanvasDocument.sourceBindingDigest` 的边界。
- 为同一源码的重复实例、共享实例、条件分支、tuple/list 返回和 preview-only 节点添加 mapping fixtures。
- 验证过期源响应、切换模型、未知来源和伪造 selection 不会污染当前面板。

### P2：完成原生视图行为

- 校验逐级展开/收起、全展开、局部 frontiers、父框/标题/端口/标签障碍、拖动、折点、箭头、连接草稿、撤销/重做、保存重开。
- 检查 compat/realtime、中键平移、V/C/B/F、选区、对齐/分布/固定、Apply 和取消/超时恢复。
- 只在正式 `studio/public/preview` 运行测试；不得从 `prototype/Summary_Merge` 读取 JS。

### P3：接入 F0/F1 和语义折叠面板

- 已完成：child bridge 支持 `overview`/`detail` preset，返回当前 `frontierPreset`；React 由同一 snapshot 计算可用细化和节点/边计数。
- 已完成：`App.tsx` 的画布选项和右 inspector 增加“语义视图”折叠区；按钮只发送命令，不复制图或改 Architecture。
- 已完成：左树、画布和右侧摘要都以同一 preview snapshot 更新；返回当前前沿只做 child focus/fit，不改变 source authority。
- 已完成纯函数、bridge 和完整回归验证；真实 smoke 已覆盖嵌入式 Summary、源码证据、RiverNet 嵌套边、视觉草稿、routing-lab 和 standalone surface。后续新增 vendor 或 bridge 改动仍需在可监听端口的环境重跑浏览器矩阵。

### P4：保留正式编辑工作流

- 视图 → 编辑：保存当前 preview snapshot，建立正式 Architecture/managed project，打开 `AuthoringStudio`。
- 编辑 → 视图：源码生成/修改通过正式 analyzer 重新建立 source binding，再加载新的 preview bundle；旧 preview identity 不复活。
- 参数、激活、重绑定和源码 region 编辑必须经过正式 prepare/review/commit；visual draft 永不自动写回。

### P5：保存、导出和面板验收

- 检查双存储保存顺序、CAS 冲突、浏览器存储不可用、旧 JSON 导入和 source-only 文档恢复。
- 检查预览 SVG/PDF/PNG 与正式 publication 输出的不同 receipt 来源，禁止混淆。
- 逐面板确认折叠/展开、键盘 Escape/Tab、iframe 点击关闭 transient menu、窄屏和大图状态。

### P6：回归和发布门

- Python：预览 adapter、正式 analyzer、HTTP/CAS、authoring、transaction、publication、runtime 隔离测试。
- TypeScript：`npm run build` 和 preview/interop/selection/hierarchy/save/visual regression 测试。
- 浏览器：至少完成模型切换、F0→F1→源码、F1→F0、视图→编辑→视图、连接草稿、撤销/重做、保存重开、导出和面板折叠。
- 发布前执行独立性检查，确保构建产物、Python import、静态资源和文档都不引用 prototype 运行时路径。

本轮实际验证记录：`npm test` 共 843 项，842 项通过、0 项失败、1 项跳过；跳过项是当前沙箱无法启动
Chromium 的 DOM SVG 检查。`npm run build`、48 项定向 preview/interop/frontier/selection/save/source-adapter
测试、预览脚本语法检查、桥接握手/命令顺序测试、`git diff --check` 和 `integration-manifest.json` 指纹检查均通过。
真实 Chromium smoke 的 23 项通过记录见 [preview-bridge-20261027.json](evidence/preview-bridge-20261027.json)，
其中包括 RiverNet `edge-10` 展开、undo/redo、canonical binding 和 caption-safe route；`browserErrors` 为空。
本轮尝试再次启动 Vite 时环境返回 `listen EPERM`，所以没有生成新的监听服务；已有 smoke 证据仍可复核，后续
代码或 vendor 变化必须在允许监听端口的环境重新执行脚本，不能以纯函数和 Worker 测试替代浏览器证据。

### 6.1 当前唯一 authority 裁决

Summary_Merge 的正式副本是预览视图的唯一运行时 authority：新原生文档使用 `generic-semantic.js`
持有完整 native IR 和 certified cuts；旧 catalog/legacy 文档使用 `recursive-graph.js` 的 canonical
authority 和 frontier。两者按文档互斥，`physical-ports.js`/`router.js`/`routing-worker.js` 负责端口、路径和事务，
`studio-selection.js`/`view-navigation.js` 负责选择与相机，`source-adapter.js` 负责源码证据投影。
React `App.tsx`、`HierarchyTree.tsx` 和右侧面板只能通过 `PreviewStudio` bridge 发送命令、读取 snapshot
和显示状态；它们不能重新计算节点、边、路由、frontier 或 preview selection。这样重叠功能由 Summary
替换，Studio 只保留正式面板形态和正式工作流边界。

面板衔接按三层处理：顶部菜单和 toolbar 负责入口与命令，左树负责 display identity 的导航，右 inspector
负责 Summary 视觉事实与正式源码事实的分区展示。F0/F1、展开/收起、连接、端口、布线、相机、撤销/重做和
源码聚焦都回到同一个 child snapshot；显示名、颜色、图例、页面和 annotation 可以作为 visual presentation
保存。从零搭建、组合和源码构件声明使用 Summary 的编辑副本。真正的 Python 参数、激活、输入重绑定、源码区域修改与源码生成则进入明确的正式工作流，遵守各自的源码复核、prepare/review/approve/commit 和 CAS 合同；preview-only 对象不能获得正式写回权限。

## 7. 验收矩阵

| 验收项 | 通过条件 | 失败时的处理 |
| --- | --- | --- |
| 语义完整性 | 原始节点/边/端口/返回槽位/来源证据数量和 identity 稳定；F0/F1 只是可见前沿 | 保留旧 snapshot，显示 source/IR mismatch，不自动修图 |
| 递归图正确性 | 展开/折叠恢复同一 authority；隐藏边只投影边界，不伪造新连接 | 事务回滚，保留上一合法 graph 和 history |
| 路由合法性 | 所有提交路径满足端口、容器、障碍、标签、交叉和 source binding 约束 | 标记 invalid draft，禁止声称已认证 |
| 双模式 | Summary 声明编辑与视觉编辑不改原 Python；正式源码修改经过独立 authoring/transaction；返回新源码视图核对 source digest | 关闭编辑入口或要求重新分析，不覆盖原模型 |
| 面板保留 | 原有模型/层级/对象/图例/页面/导出功能仍可用；Summary 功能在折叠菜单/section 中可达 | 不把原型 sidebar 作为第二套主 UI 发布 |
| 保存恢复 | 预览状态和正式文档分别可恢复；CAS 冲突不覆盖本地编辑 | 分别提示未保存状态，提供 JSON 搬运 |
| 来源安全 | 静态导入不执行；只有显式 CPU 输入/profile 在正式隔离下运行；preview-only/opaque 保持边界；无 prototype runtime import | 拒绝请求并记录诊断 |
| 性能 | 首次复杂展开有明确耗时和取消；Worker/兼容回退结果相同 | 记录样本边界，不能把缓存命中当普遍保证 |

## 8. 正式 Studio 中可以由 Summary_Merge 替代的功能和可删除范围

本节按当前工作树（2026-10-27）核对 `App.tsx`、`PreviewStudio.tsx`、`studio/public/preview/yworks_edge_router_lab/`、`studio/src/core/`、`AuthoringStudio.tsx`、`ExportDialog.tsx` 及其导入关系得出。这里的“可删除”指完成替代、迁移历史状态并通过门禁后可以从正式 Studio 移除；不是建议现在直接执行 `rm -rf`。凡是仍被正式编辑、出版导出或事务流程调用的文件，必须先拆分用途。

### 8.1 删除级别

| 级别 | 含义 | 当前处理 |
| --- | --- | --- |
| D0：可在桥接完成后删除 | 只服务旧的正式预览画布，Summary child 已有一一对应能力；完成调用切换后可删除代码和对应测试 | 优先处理 `App.tsx` 中的旧画布事件/状态和仅用于调试旧 DOM 的面板 |
| D1：可删功能，暂不能删整文件 | 文件同时被 `AuthoringStudio`、正式 publication 或 source editing 使用；先移除 preview 调用，再保留剩余正式用途 | `studio/src/core` 的 Scene/router/port 辅助模块大多属于此级别 |
| D2：只停用旧入口 | 旧页面、旧菜单或兼容缓存仍可能被历史文档引用；替代入口稳定后从 UI/manifest 移除，保留显式导入或归档读取 | standalone preview 控件、旧 storage key、旧 benchmark 页面 |
| R：必须保留 | 不与 Summary 的视图 authority 重叠，或承担正式源码、事务、保存、面板和出版边界 | 正式面板、bridge/interop、CanvasDocument、authoring、transactions、publication/runtime |

### 8.2 D0：Summary 已经直接接管的旧正式预览功能

| 正式 Studio 当前功能/代码 | Summary_Merge 替代 | 删除前置条件 | 完成后的删除范围 |
| --- | --- | --- | --- |
| `App.tsx` 中以 `scene`、`committedScene`、`presentEditorScene`、`paperPosition` 为中心的旧预览几何路径 | child 的 `recursive-graph.js`、`studio-presentation.js` 和 `studio-bridge.js`；iframe 返回完整节点、边、端口、bounds 和 snapshot | 主画布只渲染 `<PreviewStudio>` iframe；所有选择、展开、移动和样式操作都通过 bridge 返回 `snapshotRevision` | 删除旧 preview 场景计算和仅为其服务的 JSX/坐标换算；保留面板所需的 snapshot adapter |
| `App.tsx` 的 `pointerDown`/`pointerMove`/`pointerUp`/`pointerCancelled` 中对 `data-node-id`、`data-edge-id`、`data-port-id`、`data-expand-id` 的 DOM 命中和拖动 | Summary `app.js`、`studio-selection.js`、`interaction-mode.js`、`routing-worker.js` | 浏览器矩阵证明 iframe 内选择、框选、连接、折点、端口、拖动、中键平移和取消/超时恢复均可用 | 删除宿主对旧 SVG/Scene DOM 的命中处理、`Gesture` 的 preview 分支和旧 box-select 计算 |
| `App.tsx` 的 `preview`/`prepareMovePreview`/`previewMoveScene` 视觉拖动预览 | child 的拖动事务、`visual` 命令和 Worker baseline 恢复 | 拖动预览、释放提交、撤销/重做、固定节点和跨 frontier 布局在 child 中产生一致快照 | 删除 `core/movePreview.ts` 在预览路径中的调用；若正式 authoring 仍使用该模块，保留其 authoring 入口 |
| `portLayoutPreview`、`portLayoutOperation`、`nearestPortLayout` 驱动的宿主端口拖动 | `physical-ports.js`、`router.js` 和 bridge `visual` 的 `portLayout` 操作 | 端口位置、producer/consumer、tuple slot、边界 gate 和路由验证全部由 child 返回 | 删除宿主端口几何预览、临时 `CanvasDocument` 端口布局和旧端口 pointer gesture |
| `recoveryPreview`、`layoutRecovery.ts` 在预览画布上的位置修复按钮 | child 的 `apply-layout`、frontier/layout transaction 和 invalid draft 恢复 | 位置修复必须返回 Summary graph 的诊断、路由和新 revision；正式文档位置修复另有明确入口 | 删除只针对旧 formal Scene 的 preview recovery UI；正式 source/authoring recovery 仍保留 |
| `App.tsx` 的预览相机 `camera`、`paperTranslation`、`viewportToWorld`、滚轮/中键处理 | child `view-navigation.js`、`fit`、`zoom` 和 camera snapshot | camera、fit、zoom、焦点切换和 iframe 重挂载恢复均通过 child 验证 | 删除 preview 专用的宿主相机状态和事件；保留 AuthoringStudio 使用的相机工具 |
| 宿主对 preview selection 的重复状态和直接推导 | child `studio-selection.js` + `previewInterop.ts` 的 identity 映射 | 左树、右 inspector、画布和源码证据均由同一 preview identity/snapshot 驱动 | 删除第二套 preview selection store；保留 Studio 的 panel selection 作为展示适配层 |
| 旧宿主“优化自动连接点/改端点”流程中直接改 formal Scene 的部分 | child `physical-ports.js`、`router.js`、`semantic-constraints.js` | 端口显示、端点拖动、路由 Apply 和失败回滚均走 Summary bridge | 删除宿主对预览端点坐标和 Scene port 的计算；正式源码 rebind 流程不删除 |

以上 D0 表格描述 2026-10-27 基线；2026-10-28 已删除 App 的旧 pointer/拖动/框选/命中和 Scene 预览分支，当前由唯一 `PreviewStudio` 原生画布提供。D1 又移除了无生产调用的 `movePreview.ts/layoutRecovery.ts`。`ReviewDialog`、source editing 和正式导出仍有明确的 formal Scene 用途，按下表保留，不能整体删除 core。

### 8.3 D1：Summary 替代预览职责后，需拆分再删除的 core 模块

下表以 2026-10-27 依赖基线为起点，2026-10-28 更新已退出模块。预览调用已转向 Summary bridge；仍有正式编辑或出版用途的模块继续保留，不能把整组文件一次性删除。

| 当前文件/功能组 | 可被 Summary 替代的部分 | 当前仍需保留的调用 | 拆分完成后的动作 |
| --- | --- | --- | --- |
| `studio/src/core/scene.ts`、`editorPresentation.ts`、`containerPresentation.ts`、`atomicFrontier.ts` | 预览节点 glyph、容器层级、可见 frontier、父框/标题和边界投影 | `AuthoringStudio` 的草稿辅助、`sourceEditingWorker.ts`、`generatedCanvas.ts`、正式文档兼容/导出 | 移除 preview renderer 分支；保留正式 CanvasDocument/source editing 所需最小 Scene projection，或迁移后单独保留为 formal export adapter |
| `orthogonalRouter.ts`、`readableRouting.ts`、`routeLaneConflicts.ts`、`edgeLabelPlacement.ts` | 预览正交/八方向路由、端口避障、标签间距、交叉和共线约束 | `authoring.ts`、`draftRouting.ts`、`AuthoringStudio.tsx`、正式 `exportScene.ts` | 预览路由全部改为 `router.js`/`routing-worker.js`；仅当 authoring/export 有独立实现后才删除对应函数 |
| `portRouting.ts`、`nodeVisualOutline.ts`、`sourceRelationRoutes.ts` | 预览物理端口、端口 side/fraction、源关系和边界连接 | 正式 AuthoringStudio 的模块端口、草稿连接、源码关系图例和 `generatedWorkspace.ts` | 将 preview port operation 改成 bridge；保留 authoring port geometry，或由 AuthoringStudio 自己的 draft geometry 替代后再删 |
| `document.ts` 中 `effectiveVisibleFrontier`、`expand`、`materialize` 和视觉历史相关函数 | 预览 frontier、展开/收起、布局缓存和 preview undo/redo | 正式 `CanvasDocument`、CAS revision、source editing、formal visual history 和 `previewPanelDocument.ts` | 不删除整个 `document.ts`；仅删除被 child snapshot 取代的 preview projection，并保留正式文档事务模型 |
| `movePreview.ts`、`layoutRecovery.ts` | 旧预览拖动和位置修复 | 无生产调用、无公共 core 导出；九份 live 测试使用历史辅助 | 已退出 `src/core`，必要比较辅助归入 `tests/retired-preview`，旧 benchmark 入口移除；见 [D1 报告](summary-d1-retirement-integration-20261028.md) |
| `memoryContinuity.ts` | 旧预览 memory 连续性与显示端口投影 | `scene.ts`、`exportScene.ts` 的正式编辑/导出投影仍直接导入 | 保留正式用途；Summary 原生画布不使用这条链路 |
| `edgePresentation.ts`、`edgeLegend.ts`、`annotationPlacement.ts`、`typography.ts`、`tokens.ts` | 预览边颜色/箭头/glyph/标签/图例样式 | 正式 CanvasDocument 的图例、页面、publication SVG/PDF/PNG、AuthoringStudio 图例 | Summary presentation 只作为 preview 显示权威；正式出版样式仍保留，避免导出结果依赖 iframe DOM |
| `svg.ts`、`exportScene.ts` | 预览 SVG/JSON 画布导出路径 | 正式 `ExportDialog` 的 CanvasDocument publication receipt 和 `archcanvas_publication` | 预览导出改用 child `export-svg`/`/api/preview/exports`；formal publication export 不删除 |

#### 8.3.1 当前导入关系说明

当前仍不能整文件删除的事实包括：

- `AuthoringStudio.tsx` 直接使用 `core/portRouting.ts`、`core/sourceRelationRoutes.ts`、camera 工具和 draft routing；它是正式编辑模式，不应因 Summary 预览接管而消失。
- `ExportDialog.tsx` 和 `ReviewDialog.tsx` 仍调用 `buildExportScene`、`renderSvg`、`buildScene`；这些属于正式文档/事务审查出口，不是预览 iframe 的重复 renderer。
- `sourceEditingWorker.ts`、`sourceEditingProjection.ts`、`sourcePresentation.ts`、`generatedCanvas.ts`、`generatedWorkspace.ts` 仍需要 `CanvasDocument` 与 formal Scene 做源码编辑和草稿恢复；删除前必须给它们提供新的正式 projection。
- `previewPresentation.ts`、`previewPanelDocument.ts`、`previewInterop.ts`、`previewHierarchy.ts` 是面板与 Summary 的适配层，不能当作重复画布删除。

### 8.4 D2：可以停用或归档的旧入口和诊断功能

这些功能不是 Summary 的核心视图 authority，但会让用户误以为正式 Studio 还有第二套画布。它们适合先停用入口，再决定是否删除文件：

| 入口/文件 | 当前问题 | 替代或处理方式 |
| --- | --- | --- |
| `studio/src/main.tsx` 挂载的 `PerfBenchmarkPanel`、`StudyPanel` 和 `perfBenchmark.ts`/`nativePerformance.ts` | 读取 `.publication-scene`、`data-expand-id` 等旧 formal Scene DOM；当前主画布由 iframe 渲染，指标可能为 0 或失真 | 浏览器性能测试改读 Summary bridge 的 snapshot/worker metrics；完成后从生产入口移除面板，测试文件可归档 |
| `studio/src/StudyPanel.tsx` 的旧 publication DOM 统计 | 与 Summary 的递归节点/边/前沿计数不是同一 authority | 改为读取 `PreviewStudio` 状态；若仅用于研究调试，生产包直接删除挂载 |
| `studio/src/PerfBenchmarkPanel.tsx` 的宿主 benchmark 控件 | 重复测量 formal Scene，不代表 Summary routing worker 性能 | 用 `Summary` 的 `metrics`、route time、worker cancel 数据替代；不再在 App 主界面显示 |
| `App.tsx` 中旧的 `archcanvas.active-document.v1` 兼容键和重复 active canvas 恢复 | 可能恢复已经不再存在的 formal Scene 布局 | 先迁移到 preview snapshot/CAS 映射，保留一次版本化读取；确认无旧文档后删除旧 key 写入 |
| standalone preview 的重复侧栏按钮 | `yworks_edge_router_lab/index.html` 仍有库、布线、源码导入和证据入口，Studio toolbar 也有入口 | `embed=1&surface=canvas` 下隐藏重复主控件；child 对话框/证据仍可由 bridge 打开，不能同时出现两套主菜单 |

### 8.5 R：即使 Summary 功能更完整，也不能删除的 Studio 功能

- 顶部模型菜单、左侧 `HierarchyTree`、右侧对象/图例/页面 inspector、折叠面板和 `WorkspaceModeSwitch`；这些是用户指定保留的正式前端面板。
- `PreviewStudio.tsx`、`previewInterop.ts`、`previewPresentation.ts`、`previewPanelDocument.ts`、`previewPublication.ts` 和 `studio/public/preview/BRIDGE.md`；它们承担 bridge、来源 identity、面板投影和正式保存/导出边界。
- `CanvasDocument`、CAS revision、history、`validateDocument`、正式 `archcanvas_python`、`archcanvas_authoring`、`archcanvas_transactions`、`archcanvas_runtime` 和 HTTP/API；Summary 视觉状态不能代替正式源码事实和事务守卫。
- `AuthoringStudio.tsx`、参数/激活/连接编辑器、`ReviewDialog`、`RuntimeProfileDialog` 和正式 `ExportDialog`；它们分别承担源码编辑、运行参数、事务审核、隔离运行和正式 publication receipt。
- `studio/public/preview/yworks_edge_router_lab` 中的 `recursive-graph.js`、`graph-engine.js`、`router.js`、`physical-ports.js`、`routing-worker.js`、`semantic-constraints.js`、`source-adapter.js`、`studio-bridge.js`、`studio-selection.js` 和 `studio-presentation.js`；这是 Summary 迁入后的唯一预览运行时。

### 8.6 删除执行顺序和硬性检查

1. 先在 `studio/src` 做 importer graph，确认待删函数没有被 `AuthoringStudio`、`ExportDialog`、`ReviewDialog`、source editing 或测试引用；不能只搜索文件名，必须搜索导出的函数名和动态入口。
2. 先切换调用方，再删实现：宿主按钮发 bridge 命令，child 返回 snapshot；连续完成模型切换、F0→F1→F0、拖动、端口、折点、撤销/重做、保存重开和导出。
3. 迁移旧 localStorage/IndexedDB key 和 CanvasDocument 版本；历史文档只能经过显式导入/重新验证，不能静默按旧 formal Scene 恢复。
4. D0 删除后执行 `npm run build`、Studio 测试和浏览器矩阵；D1 每拆出一个模块都执行 authoring、publication、source editing 回归，避免把正式编辑能力误删。
5. 删除生产入口后再清理测试/benchmark；保留一份迁移前 tag 或归档分支，便于恢复旧文档和审计证据。
6. 发布门检查 `rg -n "prototype/Summary_Merge|publication-scene|data-expand-id|buildScene\(" studio/src src`：允许正式 export/authoring 的明确调用，禁止 preview runtime 再出现第二套 renderer/router/frontier/selection authority。

当前可以最先删除的是旧 preview DOM 事件分支和只统计 `.publication-scene` 的生产诊断入口；`studio/src/core` 不能在当前状态整体删除。只有当 D1 的正式编辑与 publication 依赖完成拆分、并且 Summary bridge 覆盖所有预览操作后，才可以逐个 `git rm` 其余重复实现。

## 9. 明确不迁移或不承诺的内容

- 不迁移 `tools/serve_semantic_studio.py` 作为正式服务入口；正式服务统一由 `archcanvas_cli serve` 提供。
- 不将旧 `semantic_studio/publication-renderer.js`、旧 publication 坐标、旧图册分页直接用作正式 `Scene` 或出版认证。
- 不把 Summary 的完整 `semantic_adapter` 当作正式源码写回实现；正式 `archcanvas_python`、authoring 和 transactions 继续独立维护。
- 不把旧浏览器 IndexedDB/localStorage、旧 `semantic-authoring/1` 文档或旧 `summary-merge-recursive/1` 文档直接视为正式 CanvasDocument；只能显式导入并重新验证。
- 不把历史 328/666 视图、旧 SVG 检查、原型测试计数自动继承为当前 Studio 的通过证据；每次 vendor 或桥接改动都要重跑对应正式测试。
- 不承诺任意 Python、任意动态控制流、完整 shape/dtype、checkpoint、训练状态或跨机器字体/出版布局等价。

## 10. 实施状态与文件检查清单

### 2026-10-28：Summary 语义优先接入状态

`semantic_adapter` 已迁为正式 `src/archcanvas_summary_semantic` 包；
`src/archcanvas_preview/semantic_bridge.py` 负责把原生 `archcanvas-source-semantic/2`
完整保留并投影到递归浏览器的 `summary-source-ir/1`，而不复制一套前端 graph authority。
Studio 新导入路径默认使用 请求顶层的 `semanticMode: "summary"`（`config` 保留模型构造参数），旧 adapter 作为显式兼容
路径保留。此处的替换范围是预览源码语义，不替代 `archcanvas_python` 的正式事务事实。

面板衔接补充：

| Studio 面板 | Summary 数据/命令 | 处理原则 |
| --- | --- | --- |
| 左侧模型层级 | child graph 的节点、parent、expanded 和 frontier snapshot | 只投影，不重新计算 Summary hierarchy/可见图 |
| F0/F1、展开/收起 | `set-frontier`、`expand-all`、`collapse-all` | 同一 Summary graph authority；保留现有按钮和折叠菜单 |
| 对象显示属性 | bridge visual operation + snapshot | 显示名/颜色/图例/页面等仍用 Studio 表单，结果写入 Summary visual history |
| Summary 源码语义 | bundle `semantic` 与完整 `ir.semantic_ir` | 显示 schema、coverage、motif/contract 数；只读，不授予写回权限 |
| 源码证据 | 相对文件路径、精确 UTF-8 AST span、`show-evidence` | 证据片段按提交源码重新切片；浏览器验证 digest 和 byte span |
| 正式模型编辑 | 同源文本重新进入正式 Architecture/Authoring | 参数、激活、重绑定、源码修改仍 prepare/review/approve/commit |

可直接由 Summary 替代的旧源码 preview AST 默认入口已退出 Studio 新请求路径；旧的
`archcanvas_preview/analyze.py` 暂保留给兼容存档、rule adapter 和已有验证入口，待 importer
graph 审计后拆分删除。`semantic_studio` 的历史独立 renderer、publication renderer 与
authoring HTML 不作为第二个画布挂入 Studio；其语义事实通过迁入的 Python IR 进入现有
Summary runtime，避免双选区、双 frontier 和双路由。残差、分支、循环回边与 opaque 的小型独立样本已经通过原生递归引擎验证，
包括全部展开/收起和 canonical 端口守恒。角色/路径/值链、模块/阶段/语义边界六档切面和 `certifiedDetails` 的认证 F0/F1 已通过
原生 pipeline 接入；右侧新增“Summary 语义切面”折叠区，包含重复结构、绑定、来源外框策略、
认证角色路径、关系详图、返回切面和原始对象归属。未完成布线显式计数并可继续处理，
保存的未完成视觉状态不能伪装成合法路由。
自主测试进一步发现并补齐了新版 Summary 原生投影所依赖、旧 router 尚未实现的选项：
搜索范围/冗余障碍裁剪、容器通行坐标、逐段通行约束，以及优先当前端口和合法简单候选。
Transformer 三档的完整合法性测试现已通过，原先源码单位层的 11 条失败有修复前后证据。
默认 8 秒预算与严格 fixture 路由验收预算分开，不把仍在排队的路线标成已完成。
五种 Summary 原生/语义文档格式已通过原版读取器接入 Studio 导入窗口，保留原始文档、
authoring 声明、当前切面和视觉编辑；来源按未验证的文档证据处理。详见
[文档与面板接入](summary-documents-integration-20261028.md)。生产入口也已移除旧性能/研究
面板的挂载（D2），其源码保留归档。完整原生 authoring 操作、runtime/merged CPU 补证、
千级图预算扩展和基于 renderer 测量反馈的 adaptive-frontier 仍待接入；旧 catalog/legacy
文档的 F0/F1 继续是深度兼容前沿。
480 节点上限仍有效；完整 Transformer 原生 IR 的千级源码图仍不在当前桥接范围内。

开始真正改代码前，按以下顺序确认：

1. `git status --short`，确认目标工作树的未提交文件已被记录。
2. 读取 `AGENTS.md`、本文、`docs/preview-migration.md`、`studio/public/preview/BRIDGE.md` 和两个 manifest。
3. 读取 `/api/capabilities`，保存 preview limits、source adapter、publication/runtime 的实际响应。
4. 运行 `npm run build` 和目标测试的基线；失败项写入独立日志，不修改历史报告。
5. 实现 F0/F1 面板和 bridge 后，先跑纯函数/Worker/Interop 测试，再做浏览器操作。
6. 将每个新增 vendor 或适配文件的来源、sha256、用途和测试写进 manifest/文档。

### 当前实现和验收证据

实现明细、替换清单、当前未迁功能及本轮测试记录见
[2026-10-28 实施报告](summary-semantic-integration-20261028.md)。迁入的 21 个 Python
文件有 19 个保持来源字节，2 个有明确适配；逐文件指纹见
[语义迁入清单](summary-semantic-manifest-20261028.json)。该报告与本节覆盖当前状态，
前文 2026-10-27 的测试计数和能力范围仅作为历史基线。原生视图替换及新增验证单独记录在
[原生语义视图接入报告](summary-native-view-integration-20261028.md)，不要将先前测试计数当作新 JS 的验证。

原生视图阶段已完成的当前验证：完整前端 866 项中 865 通过、1 项沙箱 Chromium 跳过；
末次空选区面板计数修正后 65 项专项通过，原生/Transformer 浏览器 19 项再次通过，
共享 router 补齐后旧案例浏览器 23 项通过。5 个正式 fixture 的 15 个原生切面均检查完整
来源/归属/几何/路由，Transformer 不再豁免路线失败。构建、独立副本与 60 个当前 HTTP
资源字节校验通过；完整日志和本轮未迁能力见
[原生视图验证记录](evidence/summary-native-view-20261028/validation.json)。

### 相关现有文档

- `docs/preview-migration.md`：首次 Summary 预览复制、HTTP/静态资源、正式桥接和历史验证边界。
- `docs/preview-expansion.md`：局部展开、路由和交互性能修复。
- `docs/preview-toolbar.md`：预览工具如何并入正式 Studio toolbar。
- `studio/public/preview/BRIDGE.md`：iframe 消息、视觉操作、选择、frontier 和保存契约。
- `prototype/Summary_Merge/docs/generic-native-host-migration.md`：原型侧原生递归 host 的设计、F0/F1 和排除项。
- `prototype/Summary_Merge/docs/generic-authoring.md`：原型侧视图/编辑双模式、源码模块和组装认证。
- `prototype/Summary_Merge/docs/generic-canvas-interaction.md`：原型侧 Worker、路由、拖动、缓存和 IndexedDB 交互边界。

### 2026-10-28：文档入口、来源面板和 D2 执行补充

当前多格式文档接入取代 Studio 将这些 JSON 交给正式 Architecture parser 的旧分支。
模型菜单中的“工程目录 / 已有文档”新增直接 JSON 选择；五种格式全部使用 Summary 的
`G.read`、AuthoringModel 与原生投影，不从旧 Studio 几何重建图元。左右面板继续用 Studio
形式；F0/F1、层级、对象样式、图例、页面、说明与相机读取同一 child snapshot。

`nativeDocument` 保存原始文档和内容身份，`importedDocument` 标记未验证的证据来源。
普通文档不会获得 adapter 或源码事务权限；顶部保存使用 preview-only 浏览器保存，
编辑 JSON 包含原始文档与当前图，支持跨 origin 搬运。完整 authoring 操作仍待迁移。

D2 已执行范围：生产 `main.tsx` 退出 `perfBenchmark`、`PerfBenchmarkPanel` 和 `StudyPanel`
的 import/挂载。保留相应研究源码；没有删掉 Studio 的功能面板或正式 core。
当前验证与功能自省见 [文档阶段报告](summary-documents-integration-20261028.md)和
[本阶段证据](evidence/summary-documents-20261028/validation.json)。

文档阶段最终验证：完整前端 879 项，878 通过、0 失败、1 项沙箱 Chromium 跳过；
49 项专项、独立副本 42 项和真实浏览器 53 项通过。源码原生 pipeline 的五个 fixture、
15 个切面均通过完整路线检查；61 个 HTTP 集成资源与当前构建字节一致。
这些结果对应本阶段当前代码，原生 authoring 操作、CPU 补证、千级预算及 D0/D1 清理
仍未完成，不能据此将整体迁移标记为完成。

### 2026-10-28：Summary 组装编辑开始替换重叠编辑功能

原生模型的“编辑”、默认空白新建已切换为 Summary 编辑副本，保留 Studio 的主菜单、
左树、对象/图例/页面和同一 iframe。新增右侧“原子与模块库”“节点与结构编辑”
“精确槽位连接”折叠区，使用原版 AuthoringModel、16 个预设/113 个源码单位、
真实槽位、组合、模板、复制/删除和同一历史。原正式 `AuthoredDraft` 仍通过明确的
源码菜单保留，并用于 Python 工作副本生成/审查。

编辑副本是 `archcanvas-summary-authoring/1`，UUID 稳定、内容摘要随提交变化。原导入
文档保持不可变；编辑不获得 verified Python binding，不绕过正式 transaction。
当前源码模块重编译/替换、recipe、runtime/merged、千级预算及 D0/D1 清理仍待继续。
详细面板映射、持久化/undo 边界、自主检查和验证见
[Summary 编辑阶段报告](summary-authoring-integration-20261028.md)。上面的文档阶段计数
继续对应历史代码，不能用来证明本阶段新增编辑逻辑。

编辑阶段最终验证：完整前端 885 项中 884 通过、0 失败、1 项沙箱 Chromium 跳过；
专项及独立副本各 69 项通过；真实浏览器编辑/文档/原生/旧桥接共 65 项通过。
构建、独立运行时来源和 63 个 HTTP 资源字节检查通过。完整范围和剩余能力见
[编辑阶段验证](evidence/summary-authoring-20261028/validation.json)。


### 2026-10-28：源码模块重解析与原始构件精确重建

Summary 的原版 `compile_module`、`replaceModule` 与 `recipe` 已进入正式 Studio。
右侧新增“源码模块与参数重解析”“原始构件精确重建”折叠区：源码全文与构造参数
静态提取后加入当前层级，兼容替换保留同名接口的精确槽位和对象样式；删除已连接
输入则保留原图、历史与输入源码。参考重建可按模块或源码原子逐个恢复原身份、
父级和跨构件依赖，独立比较完整节点/边后才显示精确重建。

正式 API `/api/preview/authoring/module` 使用有界独立 AST 进程，要求 session/同源；
不执行模型，不写回 Python。回复同时检查案例加载序列、workspace 和声明摘要，
避免在解析期间切模型或改稿后错误提交。保存/JSON 恢复继续验证当前组装声明，
不会隐式重新编译。详见 [源码模块阶段报告](summary-source-authoring-integration-20261028.md)。
局部结构重认证、完整新 catalog、CPU runtime/merged、测量反馈、千级预算及 D0/D1
仍待继续；上面的历史阶段计数不代表新增能力的验证。

源码模块阶段最终验证：完整前端 889 项中 888 通过、0 失败、1 项沙箱 Chromium 跳过；后端 29 项，真实浏览器 71 项通过。独立副本重新构建，另有前端专项 73、多文件 9、后端 29 项通过；63 个 HTTP 资源字节一致。详见[源码模块阶段验证](evidence/summary-source-authoring-20261028/validation.json)。这些结果不代表剩余迁移项已完成。


### 2026-10-28：Summary 组装局部结构复核

原版 `certify_assembly` 已通过正式有界静态进程接入右侧“组装局部结构复核”折叠区。
复核只更新严格绑定当前声明的局部契约，不改变节点、依赖、槽位或源码事实；声明编辑
后清理结果，现有 undo/redo、原生 F0/F1 和保存/编辑 JSON 一起恢复对应版本。
恢复仍先派生 `sourceIR`，逐字段比较完整事实，不允许用新结果替换当前稿的语义。
局部结果是文档声明，不是服务端签名、模型执行或 Python 写回许可。
实现、自主发现与本阶段独立证据见[局部结构复核报告](summary-local-assembly-integration-20261028.md)。
完整新 catalog、CPU runtime/merged、测量反馈、千级预算和 D0/D1 仍在后续范围。

局部结构阶段最终结果：完整前端 892 项（891 通过、0 失败、1 沙箱 Chromium 跳过）；最后解析后预算 guard 另由最终及独立副本各 85 项与真实浏览器复核 5 项验证。后端各 33 项，真实浏览器共 37 项；63 HTTP 资源一致。执行范围详见[局部复核验证](evidence/summary-local-assembly-20261028/validation.json)。


### 2026-10-28：D0 旧预览职责由 Summary 替换

App 中旧 pointer/拖动/框选/端口命中、formal Scene 预览、位置提案、宿主预览相机和缓存已移除。保留 Studio 面板，“优化当前布线”和自动连接点恢复改为 Summary bridge/Worker 事务，原生取消回滚 graph/history/selection/pan camera。正式源码编辑、事务与 publication 依赖继续保留，未整体删除 core。具体替换、面板衔接、测试归档及本阶段验证见[旧预览职责清理](summary-preview-retirement-integration-20261028.md)。

D0 最终验证：完整前端 872 项（871 通过、0 失败、1 沙箱 Chromium 跳过）；主专项与独立副本各 124 项、真实 Chromium 共 56 项通过。25 项旧宿主实现用例退出，新增 5 项原生用例。来源和执行范围详见 [D0 验证](evidence/summary-preview-retirement-20261028/validation.json)。整体迁移仍在进行。

## 2026-10-28：完整 generic 目录与 Studio 折叠入口

Summary 的 43 模型目录、43 IR 与 1 展示配置均已原样迁入。新增“模型 → Summary 模型库”和右侧折叠面板，沿用原生导入、F0/F1、层级、双模式编辑与保存。40 个预算内模型开放；3 个大图明确禁用，完整数据保留。实测大型 Transformer 的总览 graph 已达约 28.4 MB，尚需大图传输、保存、历史内存和取消验证，不能仅提高节点上限。详情见 [模型目录接入报告](summary-catalog-integration-20261028.md)。整体迁移仍在进行。

目录阶段最终验证：完整前端 917 项（916 通过、0 失败、1 沙箱 Chromium 跳过）；主专项和独立副本各 45 项，真实 Chromium 35 项；109 HTTP 资源、45 原样目录资产和 32 原样原生 JS 均通过。43 目录条目中 40 可打开、3 个大图保留数据并明确限制，详见[目录阶段验证](evidence/summary-catalog-20261028/validation.json)。


## 2026-10-28：源码 / CPU 轨迹 / 合并证据视图

Summary 原生证据 mode 与样例选择已接入 Studio 的“Summary 语义切面”折叠区。完整 IR 与归属账本保留，层级定位可按精确身份跨源码/CPU 视图并返回；撤销、保存刷新、编辑 JSON 与从 CPU 切面建立完整组装稿沿用原生历史。静态模型禁用 CPU 选项。当前归档记录缺少可唯一核对的源码调用 regions，合并保持源码未知边界，不能将归档 passed 或相似名称当新执行认证。实现、面板衔接、自省与本阶段验证见 [证据视图报告](summary-evidence-views-integration-20261028.md)。新 CPU 执行、3 个大图、测量反馈及 D1 仍待继续。


本阶段最终验证：完整前端 926 项（925 通过、0 失败、1 沙箱 Chromium 跳过）；主专项和独立副本各 100 项，真实 Chromium 37 项通过。主构建与独立副本构建、8 个最终运行/测试文件的独立字节对照、109 HTTP 资源核验通过。32 原生 JS 与 45 目录资产保持来源一致。详见 [证据视图验证](evidence/summary-evidence-views-20261028/validation.json)。本阶段没有后端执行改动，不挪用旧后端计数；整体移植仍在进行。


## 2026-10-28：大图状态精简基础

层级投影按精确 ID 引用同图完整 IR；Transformer 导航层从约 12.35 MB 降到 1.50 MB，树、源码映射与完整事实保留。原生会话历史改用冻结语义共享与独立几何快照，Studio 面板及正式事务边界继续保留。详见[状态精简报告](summary-compact-state-integration-20261028.md)。3 个大图的传输/保存/压力仍未完成，本阶段不提高导入预算或开放受限模型。


本阶段最终验证：完整前端 934 项（933 通过、0 失败、1 沙箱 Chromium 跳过）；最终新增专项 8 项通过。较宽专项 152 项通过（在最后一项精确引用反例添加前执行），独立副本以最终文件执行 153 项通过。真实 Chromium：手势 5、原生 16、证据视图 9、组装 12，共 42 项通过。主/独立构建、109 HTTP 资源、32 原版 JS 与 45 目录来源核验通过。复用正式独立副本并同步比较 131 项当前集成输入，重新确认 8 个模块实际来源、69 个 Python 文件当前字节一致及 5 个纯静态 fixture 分析；不声称干净安装或新 CPU 执行。详见[本阶段验证](evidence/summary-compact-state-20261028/validation.json)。大图完整开放及整体移植仍未完成。


## 原生测量驱动局部细化（2026-10-28）

Summary 的原版 adaptive-frontier/5 现由 studio-adaptive.js 接到唯一原生画布；候选比较使用实际图元文字、精确操作数绑定和成功的物理路径。Studio 保留右侧折叠面板，增加开关、策略、采用/拒绝回执和手动收起入口。保存有效请求与开启前基线；关闭恢复原请求，重开独立校验已保存布局。详细范围、来源及验证见 [局部细化报告](summary-adaptive-view-integration-20261028.md)。新 CPU、大图完整压力与 D1 仍未完成。


本阶段最终验证：完整前端 946 项（945 通过、0 失败、1 沙箱 Chromium 跳过）；最终专项 41 项（含新增自适应 12 项）和独立副本专项 94 项通过。真实 Chromium：自适应 8、手势 5、原生 16、证据 9、组装 12，共 50 项通过；实际 36 处文字按 CTM 换算世界坐标检查包含。主/独立构建、110 HTTP 资源、32 原版模块及 45 目录资产逐字节核验通过。独立副本核对当前生产字节、69 个 Python 文件、8 个实际模块来源及 5 个纯静态 fixture。详见[本阶段验证](evidence/summary-adaptive-view-20261028/validation.json)。新 CPU、大图完整压力和 D1 仍待继续，整体移植未完成。


## 原生 Worker 共享语义传输（2026-10-28）

Summary 原版 `G.transport()` 已接入实际主线程/Worker 通道，同切面几何操作复用完整冻结语义；每代 Worker 单独缓存，发送失败、错误和缓存过期均清空通道后以完整输入独立重算。Studio 面板、原生 validator、历史和正式事务边界保留。三大图诊断的后续消息减少约 85.6%–90.9%，但仍未通过完整路由/保存/压力验收，限制不提高。来源、异常恢复、自省和本阶段证据见 [Worker 传输报告](summary-worker-transport-integration-20261028.md)。整体移植继续进行。


本阶段最终验证：完整前端 958 项（957 通过、0 失败、1 沙箱 Chromium 跳过）；新增传输专项 12 项（含真实 Worker 线程）、独立副本专项 145 项通过。真实 Chromium：传输/故障恢复 6、手势 5、原生 16、证据 9、组装 12、自适应 8，共 56 项通过。主/独立构建、111 HTTP 资源、32 原版模块与 45 目录资产字节核验通过；独立副本同步 141 项输入、核对 69 个 Python 文件、8 个模块来源及 5 个静态 fixture。详见[本阶段验证](evidence/summary-worker-transport-20261028/validation.json)。整体迁移仍未完成。


## 跨切面完整来源共享与自动保存快照（2026-10-28）

Summary 原版防御性构建复制保持，适配边界按完整内容精确比较后复用冻结 IR；30 次真实切面历史保留独立 state/几何而共用一份来源，自动保存用原生快照并由实际 IndexedDB 往返校验。来源 digest 不作为认证依据。详见[来源共享报告](summary-shared-source-integration-20261028.md)。host/便携 JSON 与大图压力仍未全部完成，当前预算保留。


本阶段最终验证：完整前端 964 项（963 通过、0 失败、1 沙箱 Chromium 跳过）；专项 38 项（含新增来源共享 6 项）、独立副本专项 151 项通过。真实 Chromium：共享/保存/故障 8、手势 5、原生 16、证据 9、组装 12、自适应 8，共 58 项通过。主/独立构建、112 HTTP 资源、32 原版模块和 45 目录资产字节核验通过；独立副本同步 146 项输入、核对 69 个 Python 文件、8 个模块来源及 5 个静态 fixture。详见[本阶段验证](evidence/summary-shared-source-20261028/validation.json)。大图完整压力、新 CPU 与 D1 仍待继续，整体迁移未完成。


## D1：重复预览移动与位置修复退出生产（2026-10-28）

删除生产 `movePreview.ts`、`layoutRecovery.ts` 及旧 benchmark 入口。历史反例移到测试专用目录；Summary 唯一负责实际预览拖动、位置修复、端口与取消恢复。正式源码 Worker、编辑、事务审查与 publication 的 Scene/路由依赖继续保留，AST 门禁包含 Worker URL 和 type import，防止旧实现重新进入生产。详见[D1 报告](summary-d1-retirement-integration-20261028.md)。


D1 本阶段最终验证：完整前端 967 项（966 通过、0 失败、1 沙箱 Chromium 跳过）；核心专项 70 项、最终审计专项 3 项、独立副本最终专项 118 项通过。真实 Chromium 手势 5、原生 16，共 21 项通过。主/独立构建与依赖审计通过，112 HTTP 资源及上一阶段运行资源逐字节一致；32 原版模块、45 目录资产原样。独立副本核对 172 项输入、69 个 Python 文件、8 个模块来源及 5 个静态 fixture。首次独立测试因缺少约定解释器启动失败，一次修复目录有误；两份失败日志保留，正确根目录最小环境下最终通过。详见[本阶段验证](evidence/summary-d1-retirement-20261028/validation.json)。大图、新 CPU 与最终逐项审计仍未完成。


## host 快照来源共享与浏览器保存恢复（2026-10-28）

同一完整 IR 在原生 graph、adapter、编辑 baseline 和导入文档之间按完整内容共享冻结引用，几何/相机/编辑状态独立复制；Studio 面板继续投影 Summary 的唯一图。显式保存直接使用原生快照。同时修复仅存浏览器的预览重开后错误显示未保存的问题，并检查异步切换模型。便携 JSON 仍为完整原格式，每条消息仍传完整来源。详见[本阶段报告](summary-host-source-integration-20261028.md)。


本阶段验证：较早完整前端 972 项（971 通过、0 失败、1 沙箱 Chromium 跳过）；最后完整 IR 识别、快照局部别名与浏览器保存恢复改动由最终专项 46 项、独立副本 111 项及真实 Chromium 35 项验证，不把较早全量计为最后改动的全量验证。主/独立构建与 112 HTTP 资源核验通过，32 原版模块和 45 目录资产原样；179 项当前输入、69 个 Python 文件、8 个模块来源及 5 个静态 fixture 核对通过。三大图诊断中引用表示体积减少约 29%–36%，首次构建更慢；不代表浏览器 IPC、完整路由、RSS 或大图开放。详见[本阶段验证](evidence/summary-host-source-20261028/validation.json)。整体迁移继续进行。


## 三大图、取消、原生历史与保存恢复（2026-10-28）

当前 43 项目录全部开放，三份原受限模型使用完整 IR：Transformer 语义架构 3371/3663、ForeignComposition 604/585、Transformer CPU 记录 1194/1145（节点/边）。Studio 保留面板和双模式；取消由实际 Worker 待处理状态驱动，终止本代且不触发主线程重算。三图 F0/F1、隐藏节点定位、保存刷新、实际完整 JSON 往返、完整组装副本和同会话切换通过。另保留最大图 30 次真实编辑、30 次撤销、30 次重做的成功范围证据。完整报告见[大图接入](summary-large-operations-integration-20261028.md)。


本阶段验证：最后保存镜像修复之前完整前端 983 项（982 通过、0 失败、1 沙箱 Chromium 跳过）；最后改动专项 30 项、独立副本 131 项通过，最终三图浏览器 10 项、最终取消 4 项及最大图别名保存恢复专项通过。较早且原生代码未再改变的大图取消 4 项、三图完整编辑文档 3 项按各自范围单列。主/独立构建和 112 资源等价通过，187 项当前输入、69 Python 文件、8 模块来源及 5 静态 fixture 核对通过。未把旧阶段计数累加为当前全量。RSS 仍高，便携 JSON 与跨消息传输仍有完整来源；新 CPU 执行与最终审计继续进行。详见[本阶段验证](evidence/summary-large-operations-20261028/validation.json)和[逐项审计](summary-migration-feature-audit-20261028.md)。


## 最终接入验收（2026-10-28）

本次按两份主迁移文档约定的功能迁入及接入验收完成。Summary 主导视图/图元、交互、静态语义和声明编辑；Studio 保留面板形式与正式 Python/事务/CAS/publication 合同。新增 CPU 观察已进入“对象 → 新 CPU 观察”折叠区，明确规格、正式隔离、原版 ATen/producer/source-stack/分支/replay、独立结果打开、取消和保存/双模式均验收通过。详情见[CPU 报告](summary-runtime-integration-20261028.md)、[最终功能审计](summary-migration-feature-audit-20261028.md)与[本阶段 validation](evidence/summary-runtime-20261028/validation.json)。

本阶段完整前端 993 项：992 通过、0 失败、1 Chromium 沙箱跳过；该跳过项随后在允许启动 Chromium 的环境单独通过。独立前端专项 187 项、独立 CPU 7 项通过；主 CPU 核心 7 项、HTTP/正式运行 10 项、语义/组装/HTTP 33 项通过，按范围单列。最终真实浏览器 CPU 6、原生 16、手势 23 项通过；主/独立构建与依赖审计通过，112 个 HTTP/独立构建资源、32 原版 JS、45 目录资产和原版 Python observer 核验一致，261 项当前输入与70个 Python文件核对通过。各历史阶段通过数不累加为当前全量。

仍保留高 RSS、host 完整 IR 跨消息传输、便携 JSON 来源重复、明确文档/源码预算及 CPU 样本证明边界；这些限制不等于已经完成性能或任意模型支持认证。三大图历史压力范围仍按原阶段证据读取，未覆盖其封存文件。下方/上方旧阶段“未完成”描述只适用于各自当时版本，以文首状态和本节为准。
