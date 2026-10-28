# Summary 大图状态精简：层级投影与原生历史

日期：2026-10-28。本阶段处理实际大图探查中发现的重复状态；保持 Summary 为语义/视图 authority，Studio 继续提供原面板。不抬高 480 节点 / 3600 依赖 / 16 MB 导入预算，不宣称千级交互已验收。

## 重复来源与替换

原 `studio-semantic.decorate` 将 `N.nodes(graph)` 的全部原始语义、派生摘要与部分可见 HTML 再存入 `semanticHierarchy`。3371 节点 Transformer 在 F0 只有 30 个可见节点，导航层却另携带约 12.35 MB；`graph.generic.ir` 本来已经包含完整原始事实。

现在导航行保留精确 ID/父级、显示名、位置尺寸和展开标记。与同一图 canonical IR 的源码匹配字段完全一致时，行用 `semanticRef:true`；宿主 `previewDetailGraph` 通过 Map 按该行的精确 ID 读取已有 IR 对象。没有按名称、序号、路径子串或任意外来 reference 猜测对象。未命中或不合法标记不解析为另一个节点。旧完整导航行继续可读。

派生图元保留必要的 kind、源码证据、表达式、实例与模块身份、SourceBranch 条件和 callSites。`presentation_only:true` 已足以拒绝正式源码绑定，因此其导航行不重复庞大 canonical_members 数组；完整成员过程仍在 Summary 原生投影、可见图元证据与归属账本中。非 presentation_only 对象的多成员排除规则完整保留。该调整不删除 IR 节点、依赖、未知边界或运行记录，不引入第二套面板语义。

| 大图 | 原导航层字节 | 当前导航层字节 | 原始 canonical 节点 / 边 |
| --- | ---: | ---: | ---: |
| Transformer · 语义架构 | 12,351,809 | 1,501,516 | 3371 / 3663 |
| ForeignComposition | 982,982 | 118,311 | 604 / 585 |
| Transformer · CPU 运行证据 | 2,989,845 | 396,142 | 1194 / 1145 |

这是相同 F0、300 ms 路由预算、关闭可选细化时的组件大小诊断；路由 pending/failed 仍明确存在，不把单次构建时间或克隆时间当作帧率、固定 p95 或大图验收。

## 历史与面板衔接

原生 `save`、undo、redo、会话内缓存及 reset/original 副本改为 `N.snapshot → SummaryNativeSemantic.cloneGeometry`。它先递归冻结同一 cut 的 IR/state/receipts/navigation/authoring/migration 及原生 node.semantic、edge.binding，再共享这些不可变对象。WeakSet 只记住已递归冻结的对象，重复快照不再遍历全部语义。

位置、路由、可编辑端口、视觉草线、样式/别名/图例/页面、注释及切面布局缓存仍由原版 cloneGeometry 独立复制。30 份同切面快照共享一份 IR 和 receipts，同时拥有 30 份独立节点数组。正式源码、CAS 与事务历史不受这套引用优化替代；legacy 图仍沿用独立 JSON 克隆。

冻结不是来源认证，也不写入可序列化 trusted 标志。导入、保存恢复与 Worker 的语义/几何验证继续执行；篡改导出的 binding 仍会被拒绝。IndexedDB 和 JSON 的数据合同不变，本阶段尚未压缩持久化与 iframe 消息中的全部重复副本。

Studio 层级树、对象面板、源码定位、显示样式与展开状态都经原有 previewDetailGraph 入口读取；完整树行数与排序不变。原生图元和交互仍由 Summary 提供，保留 32 个原版模块的字节一致性。

## 自主测试与发现

新增专项比较全部 43 模型精简前后的真实 hierarchy 和 opaque panel document；多文件、同一实例两次调用和 tuple 输出在正式 AST 架构上逐对象比较绑定、源码跨度与歧义。另核对聚合排除、分支条件/callSites、精确引用反例、30 快照共享/隔离、冻结后的反篡改与真实 save/undo/redo handler 的 30 项历史上限。

首轮只筛字段时，长表达式与派生成员仍造成大幅重复，故改为同一 IR 的精确引用，而非删减语义。测试最初误用只有 legacy IR 的旧 fixture；现由其真实源码重新静态生成 Summary bundle，并与原独立正式 AST 架构对照。sandbox 中同步 Python 子进程的 stdin/管道行为导致测试停等/EPERM，已使用项目现有异步 execFile 模式并设 30 秒超时，不执行 fixture 中的 Python 模型。

最终验证另记 [validation](evidence/summary-compact-state-20261028/validation.json)。此前阶段冻结文件不重写；完整大图开放仍需剩余传输、持久化、跨切面历史、取消及压力验证。新 CPU 执行、测量反馈 adaptive-frontier 与 D1 继续在整体迁移范围内。

一次组装浏览器回归在刷新时撞上本任务并行重建清空 dist 的短暂窗口，实际页面返回 Studio build is not present。失败截图和记录已保留；这属于验证编排错误，改为构建完成后稳定服务再完整重跑，不放宽功能断言。


本阶段最终验证：完整前端 934 项（933 通过、0 失败、1 沙箱 Chromium 跳过）；最终新增专项 8 项通过。较宽专项 152 项通过（在最后一项精确引用反例添加前执行），独立副本以最终文件执行 153 项通过。真实 Chromium：手势 5、原生 16、证据视图 9、组装 12，共 42 项通过。主/独立构建、109 HTTP 资源、32 原版 JS 与 45 目录来源核验通过。复用正式独立副本并同步比较 131 项当前集成输入，重新确认 8 个模块实际来源、69 个 Python 文件当前字节一致及 5 个纯静态 fixture 分析；不声称干净安装或新 CPU 执行。详见[本阶段验证](evidence/summary-compact-state-20261028/validation.json)。大图完整开放及整体移植仍未完成。
