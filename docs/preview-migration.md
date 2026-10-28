# Summary_Merge 预览迁入正式 Studio

> **视觉验收修正（2026-10-28）**：用户指出旧混合图存在阶段缺失与连线错乱，先前账本测试与截图不足以证明视觉衔接。已修复展示容器误删、聚焦预算、返回附属及槽位衔接，并加入原版结构对照和浏览器放大检查。当前结果以[残缺问题修复与视觉复核](summary-mixed-presentation-fix-20261028.md)为准；本文件保留历史实现范围。

## 2026-10-28：全案例混合语义前沿

当前 43 个原生案例及 3 个登记预览案例已接入右侧 **Summary → Summary 语义切面 → 模块语义深度**。同图中的模块可独立选择 F0/F1、原生中间切面或任意源码层数；嵌套子模块覆盖父模块。完整实现、登记图的能力边界、编辑/保存衔接和逐案例验证见 [混合语义前沿说明](summary-mixed-frontier-integration-20261028.md)。大图原子事实展开与全部物理布线完成分别验收，pending/failed 保留真实状态。

源码级职责对比、F0/F1 接入计划、视图/编辑双模式边界和正式面板折叠方案见 [源码对比与移植说明（2026-10-27）](summary-merge-to-studio-comparison-20261027.md)。本文继续作为首次复制、桥接契约和历史验证记录；2026-10-28 的原生语义接管和验证见本文对应小节。

**当前验收（2026-10-28）：本次约定范围的迁入及接入验收完成。** 包括新 CPU 显式观察、43 项目录及三大图；实际入口、当前测试及保留限制见[最终功能审计](summary-migration-feature-audit-20261028.md)和文末最终验收。其余分阶段描述保留历史范围。

**当前裁决（2026-10-27）：Summary_Merge 是预览视图与交互的唯一运行时权威。** 递归 frontier、F0/F1、节点/边/端口、正交路由、拖动/框选/连接、相机、撤销重做、源码证据和 preview visual draft 均由 `studio/public/preview/yworks_edge_router_lab` 的 Summary 副本计算并通过 bridge 发布。正式 Studio 的 React 层保留顶部菜单、左侧层级树、右侧对象/图例/页面面板、模式切换、Authoring/事务、保存和正式导出；这些面板只发送 bridge 命令并投影 child snapshot，不再实现第二套 graph/frontier/router/selection。两边重叠时，以 Summary 的视图结果为准；只有正式源码编辑、参数/激活/重绑定、CAS 保存和 publication 导出仍由 Studio 的正式工作流负责。

2026-10-14，按用户要求将独立原型 `prototype/Summary_Merge` 的预览技术复制到正式项目。中心画布使用递归图、源码适配、连接编辑与路由引擎；正式 Studio 的顶部工具、左侧模型层级、右侧对象/图例/页面面板和基于图例的模型编辑继续使用。完整案例目录放在“模型 → 示例与模块库”，自动布线入口在右侧折叠菜单中。

这次来源是 `Summary_Merge`，不同于此前拒绝使用的 `ArchCanvas_Model Architecture Studio_Temp`。前端资源、模型材料和证据在正式项目内独立保存，运行时不回退到任一原型服务。

## 启动和文件位置

Python 3.11+，前端建议 Node 24+。已有依赖时：

```bash
cd ~/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio
npm run build
cd ..
PYTHONPATH=src .venv/bin/python -B -m archcanvas_cli capabilities
PYTHONPATH=src .venv/bin/python -B -m archcanvas_cli serve --host 127.0.0.1 --port 8765
```

打开 [Studio](http://127.0.0.1:8765)。一个正式服务同时提供页面、预览解析、编辑、文档和导出 API，不需要启动 `source_adapter/serve.py`。首次安装依赖仍按总 README 的 `npm ci` 和 `requirements.lock` 说明执行。PDF/PNG 需要项目解释器中的 CairoSVG 与系统 Cairo；缺少时 SVG 可用，其他格式由 capabilities 明确返回不可用。

| 正式路径 | 用途 |
| --- | --- |
| `studio/public/preview/yworks_edge_router_lab` | 递归前端、Worker、路由、交互及同源 Studio 桥 |
| `studio/public/preview/data` | 案例目录和源码索引 |
| `studio/public/preview/sources` | 规范命名的预设 Python 源码包和全量历史 Notebook 的 `.py` 转换版，原件已移除，见 [源码整理](preview-sources.md) |
| `studio/public/preview/snapshots`、`verification` | 原始模型材料、离线资源及原型历史证据 |
| `src/archcanvas_preview` | Summary 原生语义桥、legacy 有界 AST 兼容入口及 registry |
| `src/archcanvas_summary_semantic` | 迁入的原生 source semantic IR v2 静态语义包 |
| `studio/src/previewInterop.ts` | 正式编辑与预览之间的源码身份、证据和视觉映射 |
| `studio/public/preview/vendor-manifest.json` | 复制时的逐文件来源、大小、SHA256 清单 |

复制基线为 7,355 个文件、519,531,592 bytes，约 520 MB；该数字来自逐文件 manifest，不使用忽略隐藏/二进制文件的搜索工具计数；最终拷贝完整性另见 [vendor-integrity.json](evidence/preview-migration-20261014/vendor-integrity.json)。登记 115 个当前案例、115 个历史案例和 666 个视图，其中 665 个视图有图 JSON。大量快照用于完整离线案例、源码与证据查看，不是运行时 Python 依赖。Vite build 将这些静态资产复制到 `studio/dist/preview`。发布包因此使用 768 MiB、20,000 文件的显式上限。开发用 `studio/scripts/vendor-summary-preview.py` 可以刷新复制材料，正式启动不执行这个脚本。

## 编辑与预览互通

同一组相对路径和 Python 文本分别进入两个明确的契约：

| 用途 | 契约与来源 |
| --- | --- |
| 递归预览 | `summary-source-adapter/1` 包与 `summary-source-ir/1`，由 `archcanvas_preview` 产生 |
| 正式模型编辑与受审查源码变更 | Architecture schemaVersion 1、CanvasDocument、AuthoredDraft，继续使用 `archcanvas_python` 和现有 authoring/transaction 流程 |

两套 manifest 的字段及 IR 不同，因此预览的 `sourceSha256` / `irSha256` 不能当作正式 `sourceDigest` / `irDigest`。桥接用入口、精确源码字节、文件/行证据和实例身份建立对应。切换案例时废弃在途的旧解析，避免上一模型响应写回当前面板；没有对应证据的图元不猜测新的源码绑定。

已有正式模型可进入递归预览；选择源码可映射图元后，可继续使用对象属性、显示名、颜色、图例、说明、页面、布局等面板。进入“编辑”时，从当前源码重新建立正式 Architecture，再使用现有图例/模块搭建与生成流程。生成新源码后重新解析得到新预览，源码变化不通过几何距离推断。

部分旧教学图、路由实验、外部源码或 formal parser 不支持的实现仍可预览，并使用标记为 `preview-only`、证据为 opaque 的面板投影。该投影不赋予语义编辑能力；源码不可取得或没有正式绑定时，不能提交参数或结构写回。原型的既有模型案例也不表示任意新实现都能被完整解析。

新建、重接和删除预览连接记录为视觉草稿操作，保留来源证据；它们不会自动生成模型、改参数或写回源码。现有受支持语义操作继续经过正式 managed-copy、独立检查、具体审查与 guarded commit；不能将预览箭头当作已执行模型关系。

## 解析范围与接口

以下是首次迁入的 legacy adapter 范围；当前 Studio 默认使用下文的 Summary v2 路径。两条解析路径都只用 Python 标准库 AST 读取提供的文本，不 import、不实例化、不执行模型。legacy 支持范围：本地直接 `nn.Module`、跨文件相对导入、直接模块构造、Sequential、别名共享实例、参数签名绑定、静态返回槽位、常见操作和源码值依赖。动态分支/循环、状态和原位修改、外部 helper、复杂继承或未登记调用保留 opaque 区域，不推断运行分支、shape、dtype 或广播规则。

上限保持 80 文件、2 MB 源码、480 节点、3,600 边和深度 10。这里不接入 FX、`torch.export`、ONNX，也不把预览 IR 反向生成为模型。

| POST 接口 | 输入和行为 |
| --- | --- |
| `/api/preview/analyze` | `{files: {relativePath: text}, entry?, config?, semanticMode?: "summary" | "legacy"}` → 预览包；Studio 显式选择 summary，省略模式的旧 API 客户端保留 legacy |
| `/api/source-adapter/analyze` | 上述分析接口的兼容别名 |
| `/api/preview/edit-source` | `{files, entry}` → 从临时有界源码副本生成正式 Architecture，供原编辑流程注册 |
| `/api/projects/{projectId}/preview` | 从已注册工作副本重新解析；可带 `semanticMode`、`config`、`baseSourceDigest`、`baseIrDigest`，旧版本返回 409；包附正式 `studioBinding` |
| `/api/preview/exports` | `{svg, format, dpi, widthMm, binding}` → SVG/PDF/PNG 工件及收据，绑定当前预览 SVG 摘要 |

所有接口沿用正式服务 loopback、Host/Origin 检查。上传文本分析不需要 session token；编辑桥、managed project 和导出需要当前 `X-ArchCanvas-Session`。接口不接受服务器源码目录、解释器或任意文件 URL。

预览导出克隆当前图，经过既有 publication SVG 受限词汇验证并按请求宽度保持 viewBox/纵横比。脚本、HTML、外部图片、CSS 资源 URL、外部 marker、DTD 和事件属性不被接受；不启动浏览器或执行模型转换。收据包含 `inputSvgDigest`、`previewSvgDigest` 和输出摘要；来源身份标记为 `browser-declared-preview-binding`、`sourceBindingVerified: false`，表示浏览器声明，不伪装成服务器已重新验证的 IR。

## 保存与恢复

递归展开、局部布局、手动路由、连接草稿及导入包由预览引擎保存在浏览器 IndexedDB；相关偏好保存在 localStorage。正式 CanvasDocument、managed source、authoring drafts、事务和导出仍保存在正式服务状态目录。`serve --data-dir` 指定完整状态根，默认是正式工程 `.archcanvas`。

## 2026-10-28 Summary 语义底层接管

本轮将 `prototype/Summary_Merge/semantic_adapter` 的完整静态语义包复制到
`src/archcanvas_summary_semantic`。它包含 source semantic IR v2、源码 identity、
contracts、motifs、symbolic values、iteration、structure、source/runtime 证据模型和
有界 probe 代码；Studio 的默认导入只调用 AST 静态路径，绝不会导入、实例化或执行用户
模型。`runtime_worker.py` 等显式运行能力不会从预览入口隐式触发。

`src/archcanvas_preview/semantic_bridge.py` 在临时有界目录中分析提交的源码，将绝对暂存
路径重写为用户提交的相对路径，重新封存 IR 摘要，并把完整
`archcanvas-source-semantic/2` 保存在 `summary-source-ir/1.semantic_ir`。浏览器继续读取
经过现有 `SummarySourceAdapter.validate/verify` 校验的传输包；当前新导入模型随后直接将
原生 v2 IR 交给 `generic-semantic.js`，由原版认证切面生成原生图。旧 catalog/legacy 文档
才继续使用递归深度兼容路径；两者不同时持有当前图。节点的 `semantic` 字段保留
`evidence_status`、operator、module identity、constructor、contracts 所需原始事实；边的
`semantic` 字段保留 source dependency、framework contract、target port 等证据。

Studio 发起的 `architecturePreviewRequest`、源码导入和恢复路径默认带
请求顶层的 `semanticMode: "summary"`（`config` 仅用于模型构造参数）。旧存档仍可显式使用兼容 adapter，但不再是新建视图的
默认 authority。右侧“Summary 源码语义”折叠面板读取同一 bundle 的 schema、coverage、
motif/contract 数和 model-executed 标志；点击“查看 Summary 证据”只发送 bridge 命令，
由 child snapshot 定位源码和 opaque 边界。左侧层级树、F0/F1、对象面板、图例/页面面板
继续使用 Studio 的面板形式，节点和边身份全部来自 Summary child snapshot，不从 iframe DOM
反向猜测。

这条链路仍与正式编辑分开：Summary semantic IR 可以驱动只读源码证据和视觉布局，不能直接
生成 Python diff。参数、激活、重绑定、结构修改和源码写回继续经过 `AuthoringStudio`、
transaction prepare/review/approve/commit；`semantic_ir.runtime` 只是观察证据，不会自动
升级为源码事实。前端 `source-adapter.js` 保留 portable schema 的严格大小、证据切片、
identity、canonical binding 和 digest 校验，避免 richer IR 绕过现有预览安全边界。

顶部保存会先请求子预览保存，随后获取并同步 snapshot，再冻结正式文档与历史并提交正式保存；两种存储不是同一数据库或跨存储原子事务，失败时需要分别核对提示。浏览器数据按 origin 隔离：换端口、清理浏览器数据或换浏览器后，服务端 CanvasDocument 不等于包含所有预览路由细节的备份。迁移复杂预览状态时使用右上“导出 → 编辑 JSON”，通过“导入 Python 源码 → 选择源码目录 / 编辑 JSON / 适配包”恢复。已保存正式文档的可映射显示名、样式、图例、说明和页面在加载时送入新预览；独有的递归几何、草稿连接和路由仍以预览编辑 JSON/IndexedDB 为准。

后续工具入口合并、按住鼠标中键平移及当前构建的验证见 [预览工具整合](preview-toolbar.md)。下方报告记录首次迁移时的构建，后续修改的验证单独存放。

## 早期语义阶段验证（2026-10-28；当前状态见文首及最终审计）

当前实现和新验证见 [Summary 语义接入报告](summary-semantic-integration-20261028.md)，
逐文件来源见 [语义迁入清单](summary-semantic-manifest-20261028.json)。
本轮仍保留 480 节点的桥接上限；已接入原生静态语义、证据面板和原生语义视图，
其中认证语义 F0/F1、角色/阶段/值链切面现已接入，见
[原生语义视图报告](summary-native-view-integration-20261028.md)。runtime/merged、
完整原生 authoring 操作、千级图预算扩展和测量驱动 adaptive-frontier 尚未完成。
五种原生/语义文档格式及可移植编辑 JSON 的导入、浏览器保存和恢复已接入，详见
[文档与面板接入](summary-documents-integration-20261028.md)。导入文档仍是 preview-only 声明证据，
不自动获得 Python 源码绑定；不能把 authoring 格式可导入视为完整编辑模式已经迁完。
原生语义 IR 下载使用 Python canonical JSON 原文，避免 JS 将 `1.0` 和大整数
重新序列化后破坏证书摘要。
补齐新版 Summary router 的搜索裁剪、容器逐段通行约束和优先端口候选后，Transformer
的 F0/F1/source-unit 已通过完整路线回归。默认 8 秒预算仍可能产生显式 pending，
可继续布线；有限预算与完整合法性验收分别记录在原生语义视图报告。

原生视图阶段的完整前端回归为 866 项（865 通过、0 失败、1 项沙箱 Chromium 跳过）；
末次面板计数修正后，65 项专项、19 项原生/Transformer 浏览器检查、构建和独立副本再次通过。
另有共享 router 修复后的 23 项旧案例浏览器检查通过，三组浏览器均无错误。
5 个正式 fixture 共 15 个切面的严格路线检查全部通过；最终 60 个集成 HTTP 资源与 dist
字节一致。准确的执行顺序、范围、指纹和未迁能力见
[当前原生视图验证](evidence/summary-native-view-20261028/validation.json)。

## 文档与面板阶段最终验证（2026-10-28）

五种 Summary 文档格式已接入 Studio 导入窗口，原始文档、authoring 声明、当前切面、
路由、相机和视觉覆盖可随编辑 JSON 恢复。普通文档保持 preview-only 声明证据，
源码适配包继续严格验证；完整原生 authoring 操作仍待适配。生产入口已退出旧
PerfBenchmarkPanel/StudyPanel 的挂载，保留 Studio 原有功能面板。

最终完整前端 879 项中 878 通过、0 失败、1 项沙箱 Chromium 跳过；49 项专项通过，
独立副本另有 42 项通过。真实浏览器共 53 项通过，包含五格式、F0/F1、未绑定编辑拒绝、
保存/重载、下载 JSON 以及全新浏览器上下文恢复。构建、独立运行时来源和 61 个 HTTP
资源字节校验通过。上述计数以本阶段当前代码为范围，不与原生视图历史报告累加。
详见 [文档阶段报告](summary-documents-integration-20261028.md)和
[最终验证记录](evidence/summary-documents-20261028/validation.json)。

## 首次迁移执行的验证（2026-10-14）

本次重新执行了 20 个相关正式后端套件，150 项测试通过、无跳过，覆盖源码泛化、多文件桥接、authoring、来源保护、HTTP/CAS、managed-copy 审查提交、预览重新解析和 SVG/PDF/PNG 导出。另有 4 项 archive 预算与清单测试通过，验证 7,500 资源、精确容量边界、超大成员拒绝，以及迁移文档/证据被纳入新包且不改变历史包必需清单。命令见下方；摘要见 [preview-migration-validation.json](preview-migration-validation.json)，逐测试输出保存在[后端回归日志](evidence/preview-migration-20261014/backend-regression.log)。

正式目录中复制的路由、图引擎、递归展开与交互模式又执行了 4 个完整测试文件，全部通过，总耗时 413.703 秒。原测试定义共 67 项；此环境 Node 隔离运行器只汇报 4 个文件级结果，因此日志中的 tests=4 与源码定义数分开记录。测试在临时 CommonJS harness 中执行，实际 engine、案例和 snapshots 全来自正式 `studio/public/preview`，不使用原型运行时；覆盖逐级展开/收起、局部布局恢复、来源破坏拒绝、Memory/fork 关系、全展开节点移动、容器边界和双交互模式。实际输出见[核心引擎日志](evidence/preview-migration-20261014/engine-regression.log)，源码/运行时摘要与 fixture remap 见[核心引擎报告](evidence/preview-migration-20261014/engine-regression.json)。

上述 4 套核心回归后，`recursive-graph.js` 又修复了视觉草稿来源检查和展开重建。修改前 SHA 保存在核心报告；最终文件另有 6 项正式草稿约束回归全部通过，覆盖伪造 binding/projection/id、丢失 receipt、删除审计组合绕过、合法删除/重接、新草稿以及展开/全展开与 JSON 恢复，见[最终草稿日志](evidence/preview-migration-20261014/draft-constraints-final.log)。没有将此前 67 项结果归属于修改后的递归文件。

收尾兼容门禁修改前的完整 `npm test` 共 620 项，619 通过、0 失败、1 项因当前 sandbox 无法启动 Chromium 而跳过，耗时 256.485 秒，完整输出见[前端回归日志](evidence/preview-migration-20261014/frontend-regression.log)。集成负责人另外通过真实浏览器完成 PDF/PNG 导出，以及将参数改为 `p=0.2` 后“编辑 → 预览 → 保存重开 → 返回编辑”的交互检查；这属于独立浏览器操作记录，不把被跳过的自动测试记为通过。 实际 UI 检查记录及导出收据见 [ui-verification.json](evidence/preview-migration-20261014/ui-verification.json)。

收尾兼容门禁、previewCase 恢复与 snapshot 保存修改后，相关前端套件再次执行 61 项，61 通过、0 失败、0 跳过，见[最终专项日志](evidence/preview-migration-20261014/frontend-final-targeted.log)。最终 `npm run build` 成功，构建日志见[最终构建日志](evidence/preview-migration-20261014/frontend-final-build.log)，主 bundle 为 `index-C4t4SUpH.js`；HTTP 资产报告已绑定该构建及相同 dist/public vendor manifest，摘要记录入口、bundle 和 manifest 的 SHA256。

正式源码副本在 `/tmp` 以 `-I -S`、无 site-packages 执行，7 个 Python 包都解析到独立副本；离线 wheel 构建确认 `archcanvas_preview` 和 `registry.json` 随包发布。正式 `.venv` 下实际验证 SVG、PDF 和 PNG，系统 `python3` 缺少 CairoSVG 的情况不计为 PDF/PNG 成功。

对当时运行的 [127.0.0.1:8891](http://127.0.0.1:8891) 正式服务，逐项读取 2,281 个静态资源，共 160,314,932 bytes，全部 HTTP 200 且响应内容与正式 `dist` 完全一致，缺失或 SPA fallback 伪匹配为 0。逐资源路径、响应类型、大小和 SHA256 保存在 [HTTP 资产报告](evidence/preview-migration-20261014/http-assets.json)。范围包含目录视图、IR、sourceDocs、源码索引资源、前端引擎/Worker/CSS 和主 bundle；它不表示逐像素审核了全部案例。后续构建字节变化需要重新核对对应资产。

```bash
PYTHONPATH=src:tests .venv/bin/python -B -m unittest -v \
  test_authoring test_authoring_catalog_expanded test_authoring_diagnostics_http \
  test_authoring_group_generation test_authoring_http_independent test_canvas_persistence \
  test_custom_modules_http test_large_source_workflow test_output_paths test_publication_export \
  test_rebind_analysis test_residual_roles test_runtime_server test_source_authoring_bridge \
  test_source_dependencies test_source_generality test_source_numeric_roundtrip \
  test_source_region_structure test_stage2_http test_preview_backend
PYTHONPATH=src:tests .venv/bin/python -B -m unittest -v test_preview_bundle_budgets
```

原型旧报告中的 328 视图、5,538 连接显示检查和 4,011 语义破坏负例在本次迁移中没有重新执行，不计为正式新构建的验证结果。本页的测试不证明所有模型视觉等价、任意 Python 完整恢复、图到源码等价、全局路由最优、真实模型运行、外部 checkpoint 兼容或真人出版审看；后续前端构建字节变化由最终资产报告与集成记录绑定。

最终 focus 修复的来源与覆盖边界见 [focus-final-change.json](evidence/preview-migration-20261014/focus-final-change.json)。正式浏览器另外验证了 6 项草稿连接属性与 undo/redo，以及 3 项无源码路由案例保存/整页重载恢复，分别见[草稿连接检查](evidence/preview-migration-20261014/formal-draft-edge-smoke.json)和[路由状态恢复检查](evidence/preview-migration-20261014/formal-routing-persist-smoke.json)；最终 `index-C4t4SUpH.js` 的正式服务桥接检查 18 项通过，见 [preview-bridge-final-dist.json](evidence/preview-migration-20261014/preview-bridge-final-dist.json)，通用报告为 [preview-bridge-smoke.json](evidence/preview-migration-20261014/preview-bridge-smoke.json)。

最终 Studio 界面快照：

![正式 Studio 递归预览与原有工具面板](evidence/preview-migration-20261014/ui-preview.jpg)

## 后续局部展开修复

局部展开的共享分支、残差通道、旧缓存升级和 Worker/Studio 重复计算修复见
[preview-expansion.md](preview-expansion.md)。本次重新验证的运行时摘要、浏览器
展开/收起与撤销记录保存在 `docs/evidence/preview-expansion-20261014/`，
与上面的历史迁移测试记录分开保留。

## 2026-10-27 Summary 优先回归

本轮针对 Summary 运行时替代正式 Studio 重叠预览功能重新执行了构建与回归：`npm run build` 成功；定向 preview/interop/frontier/selection/save/source-adapter 测试 48 项全部通过；完整 `npm test` 共 843 项，842 项通过、0 项失败、1 项因当前沙箱无法启动 Chromium 而跳过。跳过项只影响独立 DOM SVG 浏览器测试，不代表 Summary graph、Worker、bridge 或面板回归失败。

真实 Chromium smoke 的 23 项通过记录固化在 [preview-bridge-smoke-20261027.json](evidence/preview-bridge-20261027.json)。它覆盖：嵌入式 toolbar 单一归属、V/C/B 工具和保存握手、模型目录/布线/源码证据抽屉、源码行聚焦、中键平移、视觉 overlay 与 annotation、物理端口布局、RiverNet 嵌套 `edge-10` 的 canonical binding 与 caption-safe route、展开 undo/redo、SVG、视觉草稿保存恢复、伪造 draft/非法 JSON 拒绝、source-free routing-lab，以及 standalone preview surface。该记录的 `browserErrors` 为空。

本轮 RiverNet 修复位于 Summary 副本的 `source-adapter.js`、`recursive-graph.js` 和 `graph-engine.js`：二元 glyph 的输入/输出物理端口根据真实消费者方向和字幕侧分配；递归展开、移动和局部修复都会把 glyph caption/body 作为障碍候选重新验证；canonical binding、source/body/caption 约束没有放宽。这样 `edge-10` 在展开 `group-27-17-3` 后不会穿过 `multiply` 字幕或 `add` endpoint body，并且折叠再展开、undo/redo 都保留同一路由和 binding。

当前环境尝试重新启动 Vite 时返回 `listen EPERM`，因此本轮没有生成新的监听服务；浏览器结论引用上述已在同一工作树和当前 bridge 脚本上通过的 23 项 smoke 证据。若 vendor 或 bridge 再次变化，必须在允许监听端口的环境重新执行 `studio/scripts/test-preview-bridge.mjs`，不能用纯函数测试替代浏览器证据。

## 2026-10-28 原生组装编辑接入

原生语义模型的“编辑”和默认空白新建现在使用 Summary 的原版 AuthoringModel，
由 Studio 对象面板的折叠区驱动；正式源码编辑改由显式菜单保留。
已接入原子/模块预设、结构编辑、真实槽位连接/替换/重接、组合库、撤销、
浏览器保存与编辑 JSON。原始来源文档保持不可变；编辑副本明确未验证/未执行。
详见 [原生编辑接入](summary-authoring-integration-20261028.md)。源码模块重解析/替换、
recipe、运行补证、大图预算和旧依赖清理仍待继续，整体迁移仍未完成。

编辑阶段最终回归为 885 项（884 通过、0 失败、1 项沙箱 Chromium 跳过）；
69 项专项及独立副本各自通过，真实浏览器 65 项通过，构建与 63 个集成 HTTP
资源字节检查通过。与此前文档阶段、原生视图阶段的报告分开保留，不累加测试数。


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
