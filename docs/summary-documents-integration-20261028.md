# Summary 文档导入与 Studio 面板接入（2026-10-28）

本阶段继续以 Summary 为语义、图元、切面、交互和路由的实现主体。
Studio 保留模型菜单、导入窗口、层级树、对象/图例/页面面板、保存按钮和正式源码事务。
原先只能导入源码适配包与旧递归 JSON 的入口，现已接入 Summary 原版多格式读取器。
所有格式共享当前原生渲染器；读取后的 IR、state、authoring、migration 和布局交给
`SummaryNativeSemantic` / `ArchCanvasSemanticView`，并由同一个 Worker 与当前画布持有。

## 格式与替换关系

| 输入 | 读取方式 | 当前画布与保留内容 |
| --- | --- | --- |
| `archcanvas-native-semantic/1` | 原版 `G.read`，按 renderer 版本迁移 | 原生 IR、切面、authoring、migration、布局缓存与 nativeLayout；当前版本布局验证后恢复，旧版本几何保留在迁移证据中 |
| `semantic-canvas/1` | 原版 `G.read` | IR/state/authoring 进入原生投影；旧几何作为 provenance 保留，不充当新画布坐标权威 |
| `archcanvas-architecture-document/1` | 原版 `G.read` | 同上；此格式不能误送入 Studio 正式 Architecture parser |
| `semantic-authoring/1` | 原版 `SemanticAuthoring.validate/sourceIR` | 原始模块、库、源码声明、baseline/recipe 和 authoring 文档保留；本阶段支持显示与视觉编辑，尚未接入完整原生 authoring 操作面板 |
| `archcanvas-source-semantic/2` | 原版 IR 校验与原生投影 | 完整导入的语义对象、依赖、槽位和声明证据；默认原生 F0 |
| `summary-merge-recursive/1` + `nativeDocument` | 重新读取原文并验证内容身份，再验证编辑图 | 可移植的原始文档记录、当前切面、布局/路由、相机和 Studio 视觉覆盖；不从 wrapper 的声明恢复源码权限 |
| `summary-source-adapter/1` / 带 `adapter` 的编辑 JSON | 保持 `SummarySourceAdapter.verify` 优先 | 精确源码与证据包保持原有验证路径，不退化为普通文档导入 |

`studio-documents.js` 是正式 Studio 的薄适配层，没有复制或改写 Summary 的多格式
语义读取规则。32 个原生 vendor 模块仍与 Summary 来源字节一致。
本阶段逐文件来源、适配用途和指纹见 [文档接入清单](summary-documents-manifest-20261028.json)。

## 面板与功能衔接

1. **模型菜单 → 导入 Python 源码 → 工程目录 / 已有文档 → 选择 Summary / 编辑 JSON**。
   Studio 自己的导入窗口直接选择 JSON；源码目录/多个文件继续打开原有工程导入窗口。
   单文件入口选择 `.json` 时也走同一个文档分发器，不调用正式 Architecture parser。
2. child 调用原版读取器，先检查文档规模、语义层级和依赖，再用原生 Worker 构建视图。
   只有预检通过后才注册新的文档案例。案例归入“Summary 文档”，identity 来自原始文档
   stable JSON 的 SHA256，避免不同导入内容复用同一图的保存键。
3. 提交后的 snapshot 同时包含 `importedDocument`、`nativeDocument`、`semanticView` 和
   当前 graph。左侧层级树、右侧对象属性、F0/F1、语义切面与归属计数均读取该 snapshot。
   宿主不重算 Summary 的 frontier、glyph、router 或选区。
4. 对象显示名、颜色、说明、图例和页面等继续使用 Studio 面板，命令写入 child 的视觉
   history。切面、返回、撤销/重做与相机仍由 Summary 负责；原始 IR 和 authoring 声明不变。
5. “Summary 交互”中的源码状态对这类输入显示“文档证据”；“Summary 语义切面”折叠区
   明示其未绑定 Python 文本、未由本次导入执行模型。读取源码返回清楚的 unavailable 信息，
   不让宿主先发起一次必然失败的源码绑定。
6. “源码与证据”中的当前文档来源可下载原始 Summary 文档；“导出 → 编辑 JSON”保留
   原始文档记录和当前视图。JSON 不只是当前可见节点的截图或旧 Studio Scene。

## 保存、重开与权限边界

原始文档按 `summary-document:v1:<id>` 保存于 child 既有 IndexedDB，索引为
`summary-document:index:v1`；编辑 graph 继续使用既有 `<caseId>:unified` 保存契约。
启动时重新读取并验证原始文档，再恢复经过原生检查的 graph，不信任旧的 verified 标志。
`N.decorate` 在 F0/F1、语义细化和历史操作间保留 `importedDocument`。

顶部保存沿用 Studio 的 **preview-only 保存分支**：等待 child 保存与 snapshot，同步面板
并记录保存标记。成功后清除先前的操作错误提示。原始文档与视图保存在当前浏览器 origin，
不声称它们已经进入正式工程 CAS；跨浏览器、端口和机器迁移使用编辑 JSON。
若正式文档中已有对应 preview-only identity，恢复面板时也不请求 Python 源码。

可移植编辑 JSON 重新导入时验证：原始文档 schema/预算与摘要、case identity、IR、authoring、
节点归属、canonical 依赖/槽位、几何和路由。原生图元必须与 Summary 生成器产生的 SVG 一致；
外带 definitions、extras、附件或 route-label SVG 不能随此新入口执行或显示。旧语义画布里的
几何仍可留在原始 provenance 中。Studio 视觉覆盖通过现有结构化 presentation 保留。

原始文档中的源码路径、IR digest、证书、runtime/merged 数据都是**导入的声明证据**。
导入不会 import/实例化 Python 模型，不重新认证源码，不运行 CPU 补证，不生成 Python diff。
graph 上伪造的 `sourceAdapter` 会被移除；`sourceAvailable` 保持 false。
正式参数/结构编辑仍需原始 Python 或已验证的适配包，并进入正式审查事务。

JSON 上限为 16 MB，语义图上限仍为 480 节点 / 3600 依赖，另有深度 128、20 万对象的
结构预算。此阶段没有提升千级图能力；作者文档转换后也受同一 IR 预算约束。

## 退出的旧生产入口

`main.tsx` 不再导入 `perfBenchmark` 或挂载 `PerfBenchmarkPanel`、`StudyPanel`。
它们读取旧 `.publication-scene` DOM，无法代表当前 Summary iframe 的性能或可见图。
本次移除生产挂载，保留源码与既有研究测试材料；未删除 Studio 的对象、图例、页面、
层级、导入、正式编辑和导出功能，也未整体删除正式 `core`。

## 验证与尚未完成的迁移

当前字节的命令、结果、指纹和浏览器证据统一记录在
[本阶段验证](evidence/summary-documents-20261028/validation.json)，不覆盖原生视图阶段的历史证据。
新增单元/宿主回归为 `summaryDocuments.test.ts` 与 `previewApp.test.ts`；真实浏览器脚本为
`studio/scripts/test-summary-documents.mjs`，从 Studio 导入窗口操作五种格式并检查 F0/F1、
证据与源码状态、visual overlay、相机、顶层保存、真实整页重载、下载 JSON 再导入和 SVG。下载 JSON 还在全新浏览器
上下文验证，确认恢复不依赖之前的 IndexedDB、文档索引或源码包。

功能自省：**导入 authoring 文档不等于已迁完 Summary 的编辑模式**。原生 AuthoringModel
的原子节点、精确输入/输出槽位、替换/重接、共享身份、模板、源码模块和组装 recipe
仍需适配到保留的 Studio 面板及正式事务。完整新 catalog、CPU runtime/merged 补证、
测量驱动 adaptive-frontier、千级预算/取消/压力验证及 D0/D1 依赖清理仍是后续工作。
不能把本阶段可显示的历史 runtime 证据计作本机执行成功，或将当前进度写成全部移植完成。

## 本阶段最终验证结果

- 完整前端：879 项，878 通过、0 失败、1 项因沙箱 Chromium 启动受限跳过；当前全量为修正后的完整复跑。
- 专项：49 项全部通过，已包含在全量计数中；独立副本另执行 42 项文档/宿主检查并全部通过。
- 真实浏览器：文档 14 项、原生源码包交互 16 项、旧案例桥接 23 项，共 53 项，无浏览器错误。
- 五个正式 fixture 的 F0/F1/source-unit 共 15 个切面全部来源、归属和路线检查通过。
- 当前构建、独立副本和 61 个 HTTP 资源字节检查通过；57 个集成静态资产与 dist 一致，32 个原生模块与 Summary 来源字节一致。

浏览器验证包含真实导入窗口、未绑定编辑拒绝、源码抽屉、视觉编辑、相机、保存、整页重载、
JSON 下载/再导入、全新浏览器上下文恢复与 SVG。当前界面见
[文档与 Studio 面板截图](evidence/summary-documents-20261028/studio-documents.png)。
源码和测试指纹见 [本阶段清单](summary-documents-manifest-20261028.json)，
完整命令范围、初次失败及修复经过见 [验证记录](evidence/summary-documents-20261028/validation.json)。
