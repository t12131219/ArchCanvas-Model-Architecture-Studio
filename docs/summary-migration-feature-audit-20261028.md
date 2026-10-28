# Summary 主导替换：功能与面板逐项审计

日期：2026-10-28。状态：本次约定范围的功能接入与验收完成；不是任意模型支持或性能/出版/训练等价认证。本文件将两份主迁移文档的功能要求映射到正式工程的实际代码与可复核证据；不将某阶段的通过计数当作后续修改的认证。最新阶段的最终字节和范围以各自 `validation.json` 为准。

## 当前功能所有权

Summary 是完整语义 IR、节点/模块/端口图元、F0/F1、局部展开、语义切面、原生布局/路由、画布手势、视觉草稿、组装声明和原生历史的唯一实现。Studio 的 React 面板提供表单、折叠、菜单、选择结果和状态投影。正式 Python 写回、CAS 和 publication 保留自己的独立合同。

原生模型的“编辑”和“新建空白模型”已切换到 Summary AuthoringModel。“正式源码工作副本”和“新建正式源码模型”是显式保留的源码工作流；它们与原生组装声明用途不同。历史对比表中将所有组装入口归于 `AuthoringStudio` 的描述已被此裁决取代。

## 需求 → 实际实现 → 验证入口

下表的“接入”表示已有实际生产调用链；最终验收仍须同时满足当前阶段验证和末尾未关闭项。

| 功能要求 | Studio 面板与实际 authority | 状态及验证入口 |
| --- | --- | --- |
| F0/F1、六档 granularity、frame/read policy | `SummaryViewPanel` → `semantic-view` / `set-frontier` → `studio-semantic` → 原版 SemanticEngine / GenericSemantic | 已接入；`summaryNativeView.test.ts`、原生视图阶段浏览器 |
| 精确角色、阶段、关系、返回/值链切面 | 同一折叠面板提交原始证书身份和请求；完整节点/边账本检查 | 已接入；伪造 role、证书和归属反例，不按名称补证 |
| 递归树、隐藏节点定位、局部展开/收起 | `HierarchyTree` → `focus` / `visual(expand)` → Summary 同一前沿事务 | 已接入；`previewHierarchy.test.ts`、`previewGeneralization.test.ts`、大图实际定位 |
| 模块、未知边界、条件/循环、tuple/共享实例 | 原版 Summary IR、语义投影与图元；Studio 只读事实面板 | 已接入；原生视图、源码语义、分支图元回归，不把 opaque 变成执行证明 |
| 选择/框选/多选、同级选择、固定 | Studio toolbar/树 → `studio-selection` → 原生 selection/presentation | 已接入；原生交互浏览器与 selection 专项 |
| 拖动、端口/折点、连接草稿、对齐/分布 | 原生 app/graph-engine/physical-ports/router/Worker；面板发命令 | 已接入；手势、排列、端口绑定和 invalid draft 反例；不写 Python |
| compat/realtime、正交/八方向、路径/箭头设置 | Studio“布线与箭头设置”打开原生设置抽屉 | 保留 Summary 设置和真正路由校验；未完成路线明确显示并可继续 |
| 中键、缩放、适合画布、V/C/B/F | `view-navigation` 和原生 app；Studio toolbar 同步状态 | 已接入；`previewViewNavigation.test.ts` 和手势浏览器 |
| 当前切面相机、返回、原始图恢复 | Summary 原生快照、最近四个切面相机/布局 | 已接入；相机往返、保存恢复及字段篡改反例 |
| 文字/端口/路径测量驱动局部细化 | `SummaryViewPanel` 策略/开关 → `studio-adaptive` → 原版 adaptive-frontier/5 | 已接入；实际 renderer 测量、采用/拒绝与手动收起证据 |
| 显示名、颜色、边样式、图例、说明、页面 | Studio 对象/图例/页面表单 → `visual` → 原生 studioPresentation | 已接入；host 投影、原生历史、保存/刷新回归；真实编辑保持 dirty |
| 视图/编辑双模式、原始模型副本保留 | Studio 模式按钮 → `studio-authoring` → 原版 authoring-model；iframe 常驻 | 已接入；实际双模式、完整 baseline 与返回恢复 |
| 原子库、源码构件、复制/删除、分组/组合库 | `SummaryAuthoringPanel` 各折叠区 → 原版 empty/fragment/add/erase/group/template | 已接入；16 原版预设、113 源码单位、完整子树及引用重映射回归 |
| 当前编辑层级、精确槽位连接/替换/重接 | Studio 层级及端点表单 → 原版 ports/portIndex/connect | 已接入；单一 producer、显式替换、失败原子性与端点身份回归 |
| 自定义源码模块、参数重解析/替换 | Studio 源码模块折叠区 → 正式有界 HTTP → Summary 静态源码模块解析 | 已接入；真实 HTTP、同名接口保留、失效证书清理与旧回复拒绝 |
| recipe 原始构件重建、局部结构复核 | Studio 折叠区 → 原版 recipe / recognizer；结果绑定 workspace + 声明摘要 | 已接入；事实守恒、证书作用域/深度/篡改及延迟回复反例 |
| 五类文档、完整模型目录 | SourceImportDialog / SummaryCatalogPanel → studio-documents / 原始 IR 资产 | 已接入；目录资产核验和 reader 预算；三大图以最新大图阶段结果为准 |
| 保存/自动保存、JSON 导入导出、浏览器重开 | 顶栏保存 → 原生 IndexedDB flush → 保存标记 / 正式 CAS 合同 | 已接入；缺失 CAS 时只恢复匹配 native graph；异步模型切换不误标已保存 |
| Worker 共用完整来源、取消/迟到回复 | 真正原生 Worker 通道；状态栏/Escape/初次恢复加载层 | 已接入；终止本代，取消不主线程重算，不污染历史，下次 Worker 重新传完整来源 |
| 三大图 F0/F1、30项历史、同会话切换 | 同一 Studio 菜单/折叠面板，无独立实验画布 | 由大图阶段单独验收；RSS 合计仍高，不承诺任意同规模模型延迟 |
| 源码 / 已有 CPU / 合并证据视图 | SummaryViewPanel 证据模式与 run 选择 → 原版观察/合并投影 | 已接入归档记录；无真实 region 的来源保持未知，不把归档 passed 当新执行 |
| 新 CPU 观察 | Studio 新折叠区 → 显式规格与 async job → 正式隔离 → 原版 Summary observer/merge → 显式 native open | 已接入验收；真实手写 ATen/producer/call/source-stack/双分支/四 region、可选 export、取消/迟到回复、保存与双模式；见[CPU 报告](summary-runtime-integration-20261028.md) |
| 正式参数/激活/重绑定/源码区域/受管理副本 | 原 Studio Authoring、RuntimeProfile、Review、事务服务 | 保留；视觉草稿及组装声明不能取得写回权 |
| 预览 SVG/JSON 与正式 publication | 顶栏导出分别使用原生预览收据和正式 publication 收据 | 保留来源区别；浏览器声明不能伪装为服务端重新认证 |
| D0/D1/D2 重叠实现清理 | AST authority 审计覆盖生产 importer graph、Worker、动态入口 | D0 与两个旧 move/recovery helper 已退出；正式编辑/事务/出版仍依赖的 core 按用途保留 |

## 自省中发现的具体问题

- 完整语义共享必须同时覆盖 Worker、原生历史、host snapshot 和实际视觉编辑处理函数，单独优化某个 clone helper 不够。大图 30 次编辑发现的遗漏已在真实 `studioVisual` 路径修复。
- 大图恢复需要可见进度、取消和有界握手；非当前存档不能在启动阶段全部提前布线。延后构建后仍在真正打开时执行完整 reader / 原生图校验。
- 原生文档恢复必须保留 `semanticRevision`；没有源码转换时不能将已存版本重置。
- 原生图与已存完整 JSON 相同时，Studio 由别名/图例投影产生的新面板 revision 不应制造未保存状态。正式文档和真实图编辑仍保留各自保存要求；异步核验时同时检查模型代次、case、source/IR 身份及完整 graph。
- 早期失败、停止的压力脚本、诊断与最终验证分开保存。失败文件即使名含 `final` 也不计为成功。

## 最终功能审计与保留边界

两份主迁移文档中的视图/图元、交互、双模式、源码语义、目录文档、面板、保存/导出和重复实现清理要求已映射到上表的实际入口。当前 Summary 原生视图、声明编辑和 CPU 观察是重叠能力的实现；React 面板不构造第二套图。正式 Python 工作副本、源码写回、CAS、运行事务和 publication 按实际独立用途保留。D1 剩余 core 文件仍有这些正式 importer，不能作为重复预览整文件删除。

本次最终整体验收见 [CPU 阶段 validation](evidence/summary-runtime-20261028/validation.json)：当前前端全量、独立专项、后端语义/HTTP/正式运行回归、新 CPU 实际隔离、最终浏览器和资源等价分项列明；不把历史阶段计数叠加成新的全量认证。三大图 30 项历史及最大图保存问题的独立范围仍以[大图 validation](evidence/summary-large-operations-20261028/validation.json)为准；本阶段未重跑或覆盖其证据。

- host 跨消息仍传完整 IR，便携 JSON 仍重复来源。当前引用共享没有解决全部浏览器内存/序列化开销。
- 三大图的资源与时间结论只针对实测资产、浏览器和操作；不承诺任意 4000 节点图的延迟、完整路线或低内存。未完成/失败路线仍有明确状态与继续入口。
- 静态 Python 接口仍为 80 文件/2 MB 及其能力预算；目录/native 文档的 4000 节点/5000 边/64 MB 不扩张正式源码写回范围。
- CPU 只证明声明样例和模式的观察/replay；静态 opaque、未知分支及 coverage 边界保留。模型与工具同进程，不是恶意模型执行的独立认证。
- 独立副本复用已安装 npm 依赖和锁定 CPU venv，验证代码/Worker/资产来源独立；没有声称干净网络安装或跨平台同等执行能力。
- 宿主与原生保存不是跨存储原子事务，刷新不恢复完整 undo 栈；需要搬运完整编辑状态时使用原生 JSON。
