# Summary_Merge 主导替换：2026-10-28 语义后端阶段报告

后续原生认证视图替换见 [原生视图阶段报告](summary-native-view-integration-20261028.md)。
以下“尚未接入”及 851 项计数记录该阶段时点；当前实现状态以原生视图报告为准。

本轮在已有递归画布迁入的基础上，把 Studio 新建预览的源码语义默认路径切换为
Summary_Merge 原生静态语义。目标工作树已有的未提交 UI、路由和桥接修改全部保留。
当前构建可用，但完整迁移仍未结束，下面明确列出已替换内容和剩余能力。

## 已实施的替换

| 职责 | 当前实现 | 被替代或保留的实现 |
| --- | --- | --- |
| 新建预览源码分析 | `archcanvas_summary_semantic`：复制 Summary `semantic_adapter` 的 21 个 Python 文件；19 个原样、2 个有记录的适配 | `archcanvas_preview/analyze.py` 不再是 Studio 新请求的默认路径，暂留给旧 API、存档和 rule/authoring 的兼容依赖 |
| 语义传输 | `archcanvas_preview/semantic_bridge.py`：保留完整 `archcanvas-source-semantic/2`，派生兼容 `summary-source-ir/1` | 不把原生 IR 当作正式 Architecture，不根据视图反推源码 |
| 分支、循环、资源、操作数、身份 | 原生节点/边和契约保存在 `ir.semantic_ir`；兼容节点/边保留 `.semantic`；原始 source/target port 不变 | 没有把循环回边删成 DAG；SCC 仅用于布局排序 |
| 图元、frontier、路由、物理端口、手势和历史 | 已迁入的 Summary `yworks_edge_router_lab` 副本 | React 主画布继续使用 `PreviewStudio`；面板只读取 snapshot、发送命令 |
| 语义详情入口 | Studio 右侧对象 tab 的“Summary 源码语义”折叠区 | 保留 Studio 的 section、表单、按钮和折叠形式，不嵌入旧语义工作台侧栏 |
| 源码证据和原生 IR 下载 | child 证据抽屉；下载使用 Python 原始 canonical JSON | 不经 JS 重写浮点和大整数，避免下载后 native digest / certificate 失效 |
| 工程与编辑 | Studio 原有菜单、左树、对象/图例/页面、Authoring、CAS、事务和 publication | 参数、激活、重绑定、源码 region 与生成仍走正式受管理副本工作流 |

新增包只使用正式目录内的相对包导入，没有 `prototype`、旧 Temp 项目或原型服务的运行时
依赖。可选 runtime/probe 模块虽随包保留，但静态预览入口不会调用它们，也不会导入、
实例化或执行用户模型。正式 runtime 的显式隔离/receipt 流程保持现有边界。

## 从源码到面板的实际链路

1. Studio 的单文件导入、正式 Architecture → 预览、managed preview 请求都显式携带
   请求顶层 `semanticMode: "summary"`。`config` 只包含模型构造参数，名为
   `semanticMode` 的模型参数也不会被桥接层挪用。旧 API 客户端省略模式时仍用 legacy；
   当前 Studio 自己始终明确选择 Summary。
2. 服务验证相对路径、文件数、总字节和构造参数，按唯一的 `module:Class` 选择入口，
   在新临时目录中调用迁入的静态分析器。跨文件 helper 仍只读取 AST。
3. 临时绝对路径重定位为提交时的相对路径，重新推导受来源身份约束的语义证书并封存
   IR。原生 `end_line` / `end_column` 保持原 schema；兼容 evidence 根据 AST 的
   UTF-8 byte span 从原文重新切片，不用 `ast.unparse` 冒充原始文本。
4. 原生 v2 文档保存在 portable bundle 中。Registry 可增加明确的语法检查补充对象，
   但原始节点、边、父级、操作数端口必须全部保留；补充结构不能冒充 native facts。
5. 浏览器验证 portable/native digest、source manifest 和精确证据片段后才安装图。
   `canonicalSemanticIR` 保留 Python JSON 原文；可视前沿、路由或选择不能修改它。
6. F0/F1 和左树动作经过现有 bridge/Worker；child 发布提交后的 snapshot。
   Studio 右侧显示 schema、执行标志、覆盖、选中节点的类型/来源/未知原因、迭代与重复
   契约、语义契约及结构模式。契约定位其 node，非容器 motif 定位真实 member。
7. 进入编辑时保持 iframe 挂载，使用同一源码建立正式编辑副本。未编辑返回时保留原生
   bundle 和源码字节；生成或事务提交产生新源码后重新进入 Summary 分析路径。
8. 顶部保存协调 child IndexedDB 与正式 CAS；两者仍是独立存储。刷新时按正式文档和
   preview identity 恢复。SVG 使用当前 child 图；原生语义下载使用 canonical 原文。

导入现在拒绝在载入或图事务忙碌时提交，防止旧模型处理和新导入相撞。错误保留当前
源码与图，不把失败的分析响应描述成已完成载入。当前模型证据已接入可见的证据对话框，
原先仅放在嵌入模式隐藏区域中的下载按钮不再是唯一入口。

## 当前仍需迁入的能力

| 能力 | 本轮状态 | 后续衔接要求 |
| --- | --- | --- |
| 原型认证 F0/F1、角色/阶段/路径/值链切面 | 后续原生视图阶段已接入 | 见原生视图报告；measured adaptive-frontier 反馈算法仍未接入 |
| runtime / merged 证据切换与 CPU 补证 UI | 未接入默认预览 | 使用正式显式隔离 profile 和 receipt；不得在静态导入时运行模型 |
| 千级原生图与分批继续布线 | 未接入 | 当前仍为 80 文件、2 MB、480 节点、3600 边、深度 10；需扩展预算、取消、pending route 和完整恢复契约 |
| 原型通用模型目录和原生文档格式 | 未完整接入 | 现有预览 catalog 保持可用；不能将其数量当作原型最新通用语义目录迁入完成 |
| 原型 `AuthoringModel` 的全部语义编辑操作 | 未逐项迁入 | 保留 Studio 编辑壳与受管理源码流程，为精确槽位、共享实例、组合/替换逐项建立适配与回归 |
| D0 / D1 旧实现删除 | 本轮未批量删除 | 按对比文档第 8 节拆分导入关系；仍供正式编辑/导出使用的 core 文件不能整组移除 |

保留原生 IR、能够全展开少量控制流样本，以及具有 F0/F1 按钮，均不表示上表已经完成。
原型自身的旧验证报告不作为当前 Studio 的通过证据。

## 本轮验证与自查

机器可读结果及日志位于 [evidence/summary-semantic-20261028](evidence/summary-semantic-20261028/validation.json)。

- Python 定向回归：97 项，5 项因沙箱禁止监听端口而跳过；允许 loopback 的环境中单独
  重新运行完整 HTTP preview 套件，14 项全部通过，包含新 Summary 上传/managed refresh、
  stale 409、legacy 兼容、预览导出，以及正式参数 review/approve/commit 后
  Summary 重新读取新参数、新来源摘要且保留原始文件。
- 7 项新原生语义前端验证覆盖 residual、branch、loop、opaque、UTF-8、浮点、构造参数、
  source/native digest、伪造投影拒绝与原生文档下载；下载后用 Python `validate_ir`
  独立验证浮点、大整数、摘要和证书。
- AST 多文件证据因入口包变化需要更新。保留历史报告，新证据写入本日目录；对应
  generalization 与 Summary 桥接的 15 项复测已通过，随后补了下载精度和忙碌状态保护回归。
  App 回调提取 harness 也已补齐新增的 busy 状态依赖；最终相关 33 项全部通过。
- 最终前端全量回归：851 项，850 项通过、0 失败、1 项跳过，耗时约 540 秒。
  跳过项为沙箱 Chromium DOM 检查；另有实际 Chromium 的桥接及主工作台验证。
  全量成功日志保存在 `frontend-full-current.log`，不以定向测试替代全量结果。
- 5 组现有正式 fixture 静态分析通过：MLP、ResidualCNN、Transformer、ViT 和时间序列；
  这些结果证明各自样本可解析，不代表任意 PyTorch 模型可完整 lowering。
- 实际 Chromium 检查分为既有桥接的 23 项和主工作台的 7 项，后者覆盖真实源码导入、
  折叠语义面板、F0→F1→F0、视图→编辑→视图、保存刷新、SVG 与原生 IR 下载。
- 包独立性：在 `/tmp` 的 `-I -S` 独立源码副本中解析模型；离线 wheel 含完整 21 个
  语义 Python 文件，在解包 wheel、无 site-packages 条件下可直接分析，未导入 torch。
  项目 `.venv` 缺少 `bdist_wheel`，该次构建失败有日志；系统 Python 的已有构建工具
  离线构建与独立解包检查成功，未安装新依赖。

全量前端最终计数、构建指纹、浏览器结果与记录时点以本目录 `validation.json` 为准。
首次全量 849 项中唯一失败为旧 AST 证据指纹，第二次全量的两项失败为回调 harness
缺少新增 busy 状态依赖；均已修复，并在最终全量中通过。每次运行的日志均独立保留，
没有将失败报告改写为成功。最终新增下载修复另有专项和真实浏览器验证。
最终核对的 23 个预览适配资源与构建产物逐字节一致，21 个迁入 Python 模块及
8 个集成文件均匹配来源清单中的摘要。

当前测试服务仅使用 `/tmp` 中的临时数据目录。没有修改原型源码、删除正式 core、提交、
推送或部署工程。新模块来源指纹见 [语义迁入清单](summary-semantic-manifest-20261028.json)，
预览适配资源指纹见 `studio/public/preview/integration-manifest.json`。
