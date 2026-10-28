# 同一模型的混合语义前沿与全案例接入

> **视觉验收修正（2026-10-28）**：用户指出旧混合图存在阶段缺失与连线错乱，先前账本测试与截图不足以证明视觉衔接。已修复展示容器误删、聚焦预算、返回附属及槽位衔接，并加入原版结构对照和浏览器放大检查。当前结果以[残缺问题修复与视觉复核](summary-mixed-presentation-fix-20261028.md)为准；本文件保留历史实现范围。

日期：2026-10-28。接续 `summary-merge-to-studio-comparison-20261027.md` 和 `preview-migration.md`。本次以 Summary 的原始 IR、publication、canonical projector 为权威，Studio 保留面板和正式源码事务流程。

## 覆盖范围与操作

Summary 模型库现有 46 个案例均接入模块深度入口：43 个原生语义案例，另有 3 个登记预览案例。原生目录共 6874 个原始节点、877 个源码及 CPU 容器；其中 7 个案例携带运行记录。完整案例、原始数量与容器数见 [cases.json](evidence/summary-mixed-frontier-20261028/cases.json)。没有按模型名、Transformer ID 或 encoder 路径分支实现功能。

操作入口：右侧 **Summary → Summary 语义切面 → 模块语义深度**。

1. 在画布或层级树选中对象，目标模块会建议其最近的真实源码容器；也可在下拉框直接选择尚未显示的深层容器。根容器表示整个模型。
2. 选择 F0、F1、总览、模块、阶段、语义边界、角色、值链细节或源码原子层，点击“应用到目标模块”。原生中间切面使用 Summary 原有的契约与投影策略；没有契约的案例保持其真实边界，不生成虚构角色认证。
3. 源码原子层可输入 0 到该模块最大层数的任意整数；0 为模块本身，1 为直接子节点，继续增加直到全部后代。也可点击“目标模块展开到全部源码原子”。这不是限于几张预设截图的深度菜单。
4. 再选另一个模块，为它设置不同切面。兄弟模块互不继承；父模块和子模块都有请求时，更具体的子模块覆盖父模块，请求点击顺序不影响结果。
5. 当前切面列表显示每个模块的可见/原始节点数量。点击列表中的名称只更换编辑目标，不裁剪或重新聚焦整个模型。
6. “目标模块恢复全局切面”移除该模块的覆盖请求；其他覆盖继续保留。顶部全局 F0/F1、展开/收起全部会清除所有模块覆盖并统一设置前沿。撤销、重做和返回上个语义切面恢复对应状态。

例如，将 `self.encode` 设为 F1，`self.decode` 设为 F0，再对 encode 下某一个 attention 或 Layer 设定源码深度，其他 Layer 与 decode 保持各自状态。当前原生 Transformer 的**整个模型是 3371 节点、3663 依赖；encode 子树为 1164 节点，decode 子树为 2196 节点**。不能把整个模型的 3371 节点说成 encoder 自身的节点数。

3 个旧登记案例在相同位置提供 F0、F1、任意登记层数及全部登记原子；它们沿用自己的完整 authority，不伪装成原生 v2 的源码/角色契约。源码原子粒度登记图是 83 个可视登记节点，CPU 登记图是 306 个可视登记节点；原文件与原始来源附件仍保留。登记图展开不等于重新解析或执行 Python。

## 数据与投影衔接

原生状态新增 `generic.state.moduleCuts`：

```json
[
  { "id": "真实源码 composite ID", "level": "source", "depth": 2 },
  { "id": "另一个真实源码 composite ID", "level": "f0" }
]
```

`level` 为 `f0/f1/overview/modules/stages/semantic/roles/detailed/source`。`source` 不提供 `depth` 时表示完整后代。局部双击展开/收起会保存该模块自己的 `open`，仍是同一局部切面。模块身份、层级、重复请求、深度和展开引用在投影之前验证，保存的 receipts 不被当成投影权限。

`source-runtime.js` 用 Summary 原版 publication 编译每个请求的局部显示策略，按源码层级和 ID 确定应用顺序。它合并可见前沿、canonical representatives、绑定与附属策略，随后调用**同一个原版 canonical projector**重新处理完整依赖。不是拼接多幅 SVG，也不是用前端层级树重建源码。

隐藏的深层模块需要打开通往自身的真实祖先；祖先之外的兄弟保持原来的切面。局部面板生成的虚拟边界接口不会进入全模型；其输入、输出恢复到原始 canonical binding。无关外部依赖保持原有 bundle、条件、槽位与附属类别。每个原始节点和依赖在全图账本中仍有且只有一项归属。

源码原子层不收缩 alias、parameter、条件、控制、状态等原始单位。完整根展开逐条核对 source、target、source_port、target_port、kind、condition、evidence，而不仅检查节点数量。原始 IR 内容保持不变。

源码、CPU、合并仍是不同证据模式。源码模式不显示 CPU 记录节点；CPU 模式不因一个源码覆盖请求而混入源码树。另一模式的覆盖保存在状态中并暂时不生效。合并模式只在原有输入/槽位/调用匹配通过时展开运行补证区域；无法匹配或未观察的路径继续保留未知边界。切换语义视图不会执行模型。

## 面板、编辑与历史

- 保留 Studio 顶部菜单、全局 F0/F1、模式按钮、层级树、对象/图例/页面以及 Summary 标签。新增的是 Summary 折叠区内的控件，没有引入第二套主面板。
- 对象面板、端口、标签、图例、页面和相机仍通过既有 bridge/presentation 操作当前 graph；语义状态来自 Summary，不从 CanvasDocument 的旧 formal Scene 推断。
- 局部切面关闭自动细化，避免自适应布局覆盖用户指定的模块深度。切面选择仍允许使用原有认证角色和细节入口；已有覆盖请求继续生效。
- `G.operate` 克隆几何后再记忆布局，修复以前记忆布局时写回操作前对象的问题。IR 可继续共享不可变来源，切面状态、草稿和几何分别保存。
- 视觉草稿连接的端点隐藏时，连线保留在 `sourceDraftEdges`；端点重新显示后恢复。视觉删线操作保留在 `sourceDraftOperations`，只有当前投影的精确 binding 相同时才隐藏对应边。两者都不会删除 canonical 事实或产生 Python 修改权限。
- 便携 JSON/nativeLayout 保存隐藏草稿、覆盖请求及布局；再次打开重新编译语义并验证账本，不信任用户携带的 receipts 或 binding。
- 对原连线释放物理端口或重接后产生的同 ID 视觉草稿，只有精确 binding 与新切面一致时重放；不一致时保留为潜在草稿，避免覆盖另一种投影含义。
- 进入 Summary 编辑副本继承仍存在的模块深度；修改、删除或替换模块后，保留/重绑定有效模块，丢弃失效目标及旧的 synthetic `open`。原有源码契约不会自动作为编辑后结构的证明；局部结构复核与正式源码事务仍走各自验证流程。
- 3 个登记预览案例保留单独的 open/folded authority，新增 moduleBase/moduleCuts/moduleManual。对一个模块手动折叠后，再调整兄弟模块不会把手动状态抹掉；全局重置清除这些覆盖。

## 验证与自省

专项测试：`studio/tests/summaryMixedFrontier.test.ts`、`studio/tests/summaryCurrentCases.test.ts`。验证按原子事实、模块、混合前沿、Worker 准备、面板与历史逐级进行。

- 43 个原生案例逐个验证全部 9 种模块切面，带记录的案例同时验证源码/CPU/合并模式；原始 IR 不变，节点与依赖账本完整且不重复。
- 对 877 个原生源码及运行容器逐个完整展开，验证其应显示的全部后代及内部精确端口；源码模式按设计排除运行记录，运行模块另在 CPU 模式验证。
- 原生 Transformer 验证 encoder 的全部中间切面、任意源码层数、嵌套覆盖优先级、兄弟模块独立、无关外部依赖，以及整个模型的全部 3371 节点/3663 依赖。
- JSON 恢复、伪造模块/层数/展开引用、篡改 binding/账本、局部双击、返回、全局重置、操作前对象不变、隐藏草稿恢复及编辑副本继承分别有反例或恢复测试。
- 所有案例分别验证混合前沿的 Worker 准备和布线状态；原生大图采用预算并保留真实 pending/failed。3 个登记案例额外执行原有严格路由与完整 source/layout/edge validator。
- 7 个含 CPU 记录的原生案例分别保存并恢复源码、CPU、合并模式中的混合切面，重新验证 receipts、位置、槽位和完整 IR。
- 浏览器检查使用正式 checkout 的 8790 服务、实际 Worker 和现有 Studio 面板；核心自动化测试不代替真实界面检查。

开发中发现并修复：源码参数被默认资源摘要隐藏；同深度兄弟请求的顺序影响布局；F1 receipt 中已被 lowering 消费的 latent open 被误判；缓存记忆修改历史；切面切换清空视觉草稿及同 ID 连线覆层；模块列表误调用全图 focus；登记案例调整兄弟模块时丢失手动展开；源码和运行覆盖跨证据模式混用。

当前文件指纹见 [本阶段清单](summary-mixed-frontier-manifest-20261028.json)，具体执行结果见 [validation.json](evidence/summary-mixed-frontier-20261028/validation.json)。原版 semantic 模块字节核对另存 [original-modules.json](evidence/summary-mixed-frontier-20261028/original-modules.json)。历史阶段的验证不改写为本次结果。

全量前端执行 1094 项：1093 通过、0 失败、1 项因沙箱无法启动 Chromium 而跳过。后补的全原生混合路由/证据模式 44 项、末轮运行容器 7 项、登记案例及其容器 7 项、运行模式与切面 8 项、含记录案例跨模式恢复 7 项分别通过。末轮草稿修正另跑其受影响的原生视图、文档、状态和共享来源回归，具体数目与日志保存在 validation.json；各组存在交叉，不把它们相加伪装成一次全量运行。

浏览器实际验证包括：全局 F0、encoder F1 + decoder F0、模块撤销/重做、encoder 源码 2 层、encoder 全部 1164 节点、显示未完成布线、显式保存、服务恢复与页面刷新、实际编辑模型名称及撤销、再次保存恢复。最终保留可读混合视图。截图见 [混合前沿](evidence/summary-mixed-frontier-20261028/mixed-frontier.png) 和 [完整 encoder 原子前沿](evidence/summary-mixed-frontier-20261028/encoder-atoms.png)。

## 验收边界

这里的“所有案例”指当前 Summary 模型库的全部 46 项，以及 43 个原生案例中全部 877 个容器；不是宣称任意未来 Python 程序都能得到完整静态展开，也不是穷举 877 个模块之间的所有组合。

原子层可展示全部事实，不代表数千节点的所有物理连线已经全部无冲突。预算结束后仍显示“布线尚未完成”和“继续未完成布线”，不得把 pending 标记为合格 publication。没有对应源码或执行证据的动态边界继续保留。编辑副本中的连线和标签修改也不构成旧/新 Python 等价、数值正确或完整 CPU 覆盖的证明。
