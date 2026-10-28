# Summary 原生编辑与 Studio 面板接入

日期：2026-10-28。此阶段继续执行 Summary 优先替换，范围是原生组装编辑；不是整体迁移完成声明。

## 当前替换与入口

原生语义模型的“编辑”现在建立 Summary 编辑副本，使用原版
`semantic_studio/authoring-model.js`；不再默认把完整 v2 IR 转成 Studio 的旧 `AuthoredDraft`。
新建空白模型也进入这条路径。原有正式源码生成器通过模型菜单的“新建正式源码模型”、
“正式源码工作副本”继续提供 managed-copy、源码解析、独立检查和审查能力。
旧 catalog / legacy 图尚未获得原生 IR 时，编辑仍使用原正式入口。

首次创建编辑副本会按 Summary 编辑器的详细切面重新投影；显示名、样式、图例和页面带入新稿。
原切面、手动路线与相机继续保存在原始案例，当前不保证新副本逐点复用原案例几何。

没有复制 `authoring.html`、`authoring-app.js` 或旧画布 renderer。主菜单、左右面板、
层级树、工具栏、对象/图例/页面标签、导出窗口与同一个 iframe 均来自正式 Studio。
`SummaryAuthoringPanel.tsx` 在右侧对象面板中提供折叠区，命令进入当前 iframe，
由 `studio-authoring.js` 调用 Summary 原版模型，再由现有 Worker 重建、布线和校验。
React 只保留表单草稿，不持有第二份可写节点/边模型。

## 功能与面板衔接

| 入口/折叠区 | 当前行为 | 底层与身份 |
| --- | --- | --- |
| 模型 → 新建空白模型 | 创建独立组装文档 | `SemanticAuthoring.empty`，新的 workspace UUID |
| 顶部编辑/视图 | 原生模型首次进入时创建副本；返回视图保留 iframe；再次编辑复用该副本 | 原始 source case 继续保留；F0/F1 只改变当前语义切面 |
| 模型名称、编辑层级 | 改模型标题；进入任意真实 composite、返回父级 | 当前 doc 的 `title`、`editorScope`、`open` |
| 原子与模块库 | 16 个原版预设，共 113 个源码单位；可搜索和添加 | 原文件 `data/semantic/authoring-presets.json`，未重新手写算子或 glyph |
| 添加输入/输出 | 在当前编辑层级增加真实接口节点 | 原版 `addInterface` |
| 原始源码构件 | 提取 baseline 中原子或完整子树并插入 | 原版 `fragment/add`，内部引用和边槽位重映射 |
| 节点与结构编辑 | 名称与 constructor/arguments JSON 声明；复制、删除、多选组合 | 原版 `editNode/template/add/erase/group` |
| 我的组合模块 | 将选中子树、内部边与组件元数据保存到当前编辑文档的库；再次插入 | 原版 `template`；每次插入分配新身份 |
| 精确槽位连接 | 显示当前层级实际端点身份及 slot；显式连线、替换、重接与删除 | 原版 `ports/portIndex/connect`，不按图形位置猜槽位 |
| 顶部撤销/重做 | 语义编辑和现有视觉编辑使用同一预览图历史 | 每次语义提交只产生一个历史项；失败不改变图或历史 |
| 对象样式、图例、页面 | 沿用 Studio 原表单；语义重建保留 visual overlay | `studioPresentation`；不写 Python |
| 保存、编辑 JSON | 浏览器自动保存与顶部保存；完整 JSON 可在新浏览器恢复 | 当前声明、稳定 workspace 身份、摘要与视图一起保存 |
| 正式源码编辑 | 有原始案例时先返回原始 source case，再进入既有源码工作副本流程 | 不把组装声明当作修改后的 Python；原稿另行保留 |

端口字段明确携带实际 `node + port`。复合构件的端口可指向内部接口或真实边界端点。
连接前必须在当前文档中找到端点和对应方向的槽位。输入已有驱动时默认拒绝；勾选
“明确替换输入已有连接”后才移除旧驱动。重接在临时副本中先验证两个新端点，失败后
原连接与历史都保留。组合仅接受同级节点，删除递归移除后代和相关边。
画布原有连接工具仍创建明确的视觉草稿；模型依赖编辑使用“精确槽位连接”折叠区。

## 文档、来源和事务边界

新记录 `archcanvas-summary-authoring/1` 使用稳定 `summary-authoring-<UUID>`，
包含最新 `semantic-authoring/1` 文档、内容 SHA256 和仅作来源的 origin。
原导入记录 `archcanvas-summary-import/1` 继续是不可变原始文档，不能借编辑入口跳过
`D.matches`。进入编辑是显式创建新副本，不改原始案例和适配包。

当前图中 `generic.authoring` 是唯一可写声明，`generic.ir` 必须等于原版
`sourceIR` 的派生结果。`authoringWorkspace` 只保存记录元数据，避免在图中额外保留
一份可写 document。导出时重组记录；导入和恢复时重新读取原始声明、重算摘要、
比较 IR/authoring、再用 Summary 生成器核对 SVG 和几何契约。普通导入文档清理
编辑副本标志；源码适配包拒绝伪装为 workspace 的视图。

未改动或精确重建的原始事实由原版 `sourceIR` 保留；编辑后过期的模块身份、契约、
符号值与运行事实移到 provenance，新的组装明确 `not-verified`、`model_executed:false`。
声明 constructor/arguments 不会改写模块保存的 Python，不能称为重新解析成功。
source adapter、formal source digest、Canvas CAS、prepare/review/approve/commit 的边界保留。
来源 UUID 或 sourceSha256 只是追溯字段，不是本次组装获得了源码认证。

每次图提交携带完整编辑元数据，因此撤销/重做恢复该版本的内容摘要与声明。
自动保存记录和视图不是跨存储原子事务；重开时会独立验证保存图自身携带的声明与摘要，
不会因为编辑导致 IR 摘要变化而静默丢弃合法草稿。编辑历史仍只保留在当前会话，
整页重载或 JSON 搬运恢复当前文档，不恢复整段 undo 栈。顶部保存不提交组装内容到正式
Canvas CAS；仍使用既有 preview-only 浏览器保存，完整搬运应下载编辑 JSON。

## 自主检查发现与修正

1. 接口节点没有自有 constructor 字段，直接投影 `n.constructor` 会带入继承的 Object
   函数，导致 `postMessage` 不能克隆；现只投影自有字段，并增加 structuredClone 检查。
2. 仅使用通用导入的默认 state 会将新增节点全部收在根外框；编辑副本现在按原版
   `authoring-app.viewState` 打开模型根外框、当前层级和祖先，新增子模块保持可选择。
3. 编辑后 IR 摘要变化，旧存档匹配逻辑可能丢弃合法新稿；workspace 恢复现在对保存图
   的独立声明/摘要重新校验，普通导入与源码包仍使用严格不可变绑定。
4. 结构编辑后 Studio 面板不能继续显示旧的 preview-only 节点集合；现在从提交的
   child snapshot 重建不授予事务权限的面板投影。

## 验证与剩余迁移

执行命令、当前字节指纹、结果和截图写入
`docs/evidence/summary-authoring-20261028/validation.json`；逐文件来源与适配见
`docs/summary-authoring-manifest-20261028.json`。本阶段不覆盖前两个阶段的验证材料。

专项覆盖真实的空白编辑、所有 16 预设、精确槽位、占用输入拒绝、显式替换/重接、
组合/层级/模板/删除、来源证据清理、文档篡改拒绝与生成图元检查。
真实浏览器进一步从 Studio 面板操作并检查撤销、F0/F1、保存、重载及全新上下文恢复。

尚未迁完：源码自定义模块的原版静态编译 API、参数重新解析与 `replaceModule` 的完整
UI、recipe 逐构件精确重建及局部组装重认证；完整新版 model catalog；CPU runtime/merged
与正式隔离/receipt 衔接；测量反馈 adaptive-frontier；千级图预算/传输/取消/压力验证；
D0/D1 的旧 renderer 依赖拆分删除。当前仍为 480 节点 / 3600 依赖、16 MB 文档预算。
不能把当前编辑、构建或测试通过表述为图到 Python 的等价或整体迁移已完成。

## 本阶段最终验证结果

- 完整前端：885 项中 884 通过、0 失败、1 项沙箱 Chromium 启动限制跳过；耗时 600.122 秒。
- 专项：69 项通过，包含在全量中；独立副本另执行 69 项并通过。
- 真实浏览器：编辑 12、文档 14、原生源码 16、旧桥接 23，共 65 项；无浏览器错误。
- 构建、独立来源与 10 个编辑运行时/宿主文件字节对照通过；63 个 HTTP 资源与 public/dist 一致。
- 59 个集成静态资产已核对；32 个原生模块仍与 Summary 来源字节相同，原版编辑模型与新增预设文件也保持原样。

浏览器检查包含从 Summary 编辑面板打开原始 Python 的正式工作副本、返回原视图，
再恢复独立组装稿；观察到的正式解析请求均与原适配包 Python 字节一致，
组装图未进入源码事务或运行。源码浏览器与旧桥接回归分别保留自己的证据。
`N.accepts` 允许已明确标记的 pending/failed 路线，本阶段不宣称所有任意组装都已完成严格合法布线。

[当前界面](evidence/summary-authoring-20261028/studio-authoring.png) ·
[最终验证](evidence/summary-authoring-20261028/validation.json) ·
[逐文件清单](summary-authoring-manifest-20261028.json)。
