# 箭头与自动布局优化泛化复查 · 2026-10-17

结论：上一轮优化有可测改善，但不能按用户规范判定全部通过。当前目录案例的被测状态均通过结构检查；历史案例仍有20个失败，陌生嵌套条件图暴露条件箭头省略，TimeMixer等仍存在窄折返，深图总览可读性和紧凑度仍需改进。本轮只新增测试与证据，没有修改产品逻辑。

## 覆盖与可信边界

| 集合 | 案例数 | 所有被测状态结构通过 | UI覆盖 |
|---|---:|---:|---|
| 当前目录 | 115 | 115 | 全部尝试 |
| 历史目录 | 115 | 95 | 全部尝试，失败不算视觉通过 |
| 新陌生源码 | 5 | 5 | 全部打开并截图 |
| Studio原生下拉预设 | 7 | 未纳入离线235案例矩阵 | 全部加载、展开并截图 |
| 环路/自环/并行反向/断开分量 | 4 | 4（纯引擎） | 不作为Studio UI证据 |

离线累计 **1825次状态尝试，1764通过、61失败**。状态包括initial、full、mixed（交替容器展开）、deep（最深祖先链）及成功full之后两轮fold/reopen；失败未阻止其他独立状态。442次重新展开的边绑定比较全部一致，所有输入对象哈希保持不变。成功状态共记录32018条边，包含重复状态，不是独立连接数量。

真实浏览器对全部230个目录案例进行了选择、尝试展开和截图；另外5个陌生模型、7个原生预设。保存253张不同文件名PNG（含初始、细节、稳定总览等；重复采集可覆盖同名文件）。逐案数据见[coverage.json](evidence/visual-generalization-20261017/coverage.json)、[CSV](evidence/visual-generalization-20261017/coverage.csv)；[可搜索图库](evidence/visual-generalization-20261017/gallery.html)提供实际标题、反馈、截图与DOM SVG。

视觉检查包括全部目录截图缩略总览、陌生图/原生预设总览与重点细节。许多大图的总览文字很小，部分截图有菜单或反馈遮挡，**没有对每个案例每条边都做可读比例逐边验收**。加载或展开失败可保留旧画布（例如e09737701fe70f2c、2f8e1e51b7fb194c），不能把其截图当目标图通过。成功场景扣除不单独绘制的junction后，离线节点数与DOM节点数一致；数量一致也不代表视觉质量通过。

## 版本、环境与方法

- 正式开发目录，HEAD `e293d8eb91f56d7800c7135a66049022a2de0d45`，已有未提交改动；具体资产哈希、doctor、脏文件清单见[manifest.json](evidence/visual-generalization-20261017/manifest.json)、[doctor.json](evidence/visual-generalization-20261017/doctor.json)、[worktree-status.txt](evidence/visual-generalization-20261017/worktree-status.txt)。不是已安装Skill发行版本认证。
- 规范SHA256：`a2f565f57915f94a9da673d4e3af6d2562bc8fe06659c9b8b6695188dd704fb7`。测试使用本地正式服务8899，独立状态目录`/tmp/archcanvas-generalization-20261017`，Codex内置浏览器。实际截图尺寸集合见manifest，途中视口变化，不能作为固定视口像素对照。
- AST静态分析，不执行模型，不注册专用适配器；本轮未改ACT原目录，也未对其重新做全文件哈希核验。
- 纯Node VM调用当前公共递归投影、端口、路由、语义与几何校验，另做真实UI检查。耗时为离线构图/布线/校验，不是FPS、绘制延迟或标准硬件性能基准。
- 总览适配应等待命令完成，优先用画布内“返回总览”。早期部分截图在外层异步fit完成前拍摄，不能据此断言裁切或7%最低缩放缺陷；稳定总览能够完整显示。确认的问题是深图缩小后难读及留白较大。

## 陌生案例与受控对照

输入见[inputs/index.json](evidence/visual-generalization-20261017/inputs/index.json)。来源含固定种子生成与已有图结构变换两类；未用于上一轮调参。

- RandomDAG：seed **2026101701**，9个Sequential分支、随机DAG、3个输出。
- TupleCrossing：双输入、两个Fork、tuple拆分、dict返回及交叉消费。
- Level5：六层残差包含。
- NestedCondition：两层条件、两个条件子模块，含源码inspection关系。
- FourBranch：从上一轮Wrapper复制两个MLP分支，并改变else汇合关系，是真实结构变化。

| 全展开模型 | 节点/边（含junction） | 路径总长 | 弯折 | 严格交叉计数 | 离线耗时ms |
|---|---:|---:|---:|---:|---:|
| RandomDAG | 55/49 | 18110.6 | 81 | 7 | 4594 |
| TupleCrossing | 28/23 | 8984.2 | 34 | 2 | 1470 |
| Level5 | 35/33 | 21748 | 44 | 4 | 3688 |
| NestedCondition | 49/35 | 33824 | 102 | 33 | 15009 |
| FourBranch | 57/43 | 21788.93 | 64 | 9 | 5842 |

交叉计数是不同wire的正交线段严格内部相交次数，不包含共线重叠、端点相交，也不直接等同于视觉违规数。叶子面积利用率为叶节点面积之和/节点外包围矩形面积，不能单独作为布局评分。弯折与小段先经过公共simplify处理。

受控A/B使用上一轮冻结的graph-engine、recursive-graph、source-adapter、source-controls四个旧资产，其余依赖保持当前值；是模块级对照，**不是完整旧版重放**，见[controlled-before/results.json](evidence/visual-generalization-20261017/controlled-before/results.json)。

| 结构 | before → 当前 |
|---|---|
| TupleCrossing full | 路径9180.2→8984.2；弯折38→34 |
| NestedCondition | full/deep失败→结构通过；mixed路径11281.18→10347.52、弯折64→57；条件图层仍有省略 |
| FourBranch | full/mixed/deep失败→结构通过 |
| RandomDAG、Level5 | 路径/弯折指标一致，未观察到这些指标退化 |

无法据此证明全部拓扑、交互及文本条件都没有退化。

## 未解决缺陷与工程任务

### P1：历史层级图在部分状态无法合法投影/展开

- 状态：待修复；本轮复现，未关闭。
- 影响版本：上述开发资产。来源：历史案例，共20个、61个失败状态。
- 根因分类：可见图投影、边界端口、共享主干、路由。诊断包括独立tensor lane重叠、非正交canonical route、未声明跨容器边界、junction越过owner、源码包含关系变化。它们发生在不同模型和展开状态，并非单一模型名称问题；具体根因仍需逐类定位。
- 复现：运行audit.mjs；按下表选择对应ID和状态。UI在库中包含历史快照后打开并展开；initial即失败时可能仍显示旧图。
- 预期：跨层接口与共享tensor身份保持、全部可见边合法，失败不得静默显示为已展开。
- 修复任务：在公共可见投影与lane/gate约束阶段分别处理这些结构；不得放松语义校验或添加ID特例。自动化失败现场与完整诊断见[failures.json](evidence/visual-generalization-20261017/failures.json)。截图在图库按ID检索。

| ID | 模型 | 失败状态 |
|---|---|---|
| 147d4d87577504a7 | bilstm | mixed |
| 212b86d4ecb9b22e | textcnn | deep |
| 72e2e4bb9c070870 | bilinear attention | full, mixed, deep |
| af2846b3f4addccd | capsule routing | full, mixed, deep |
| 805e8f1514111aba | compact bilinear pooling | full |
| 2b5880a89b55ee74 | ggnn step | full, mixed, deep |
| bf07c02af1d1d13e | graph attention | full, deep |
| 5bb1f4b08b2787aa | graphsage mean | full, deep |
| 0d433bb4bed081d9 | graphwavelet sparse | full, deep |
| ca50ee1364140aad | weighted bilinear pooling | full, mixed, deep |
| 33d364ad0ea2d8b4 | autoformer | full, mixed |
| 2af474b50b586c7c | timemixer | full, mixed |
| e09737701fe70f2c | Transformer | initial, mixed, deep, fold1 |
| de3a41a1f4dd2b3f | Transformer | mixed, deep |
| 17c406223f35fcb5 | Transformer | initial, full, mixed, deep |
| 2f8e1e51b7fb194c | Transformer · compact | initial, full, mixed, deep |
| f0584cf4142849ee | Transformer | mixed, deep |
| c50cf81bd22bac48 | Transformer | initial, full, mixed, deep |
| e9bf3b44f3f2ff25 | 残差小例 · 历史 SVG | initial, full, mixed, deep, fold1, reopen1, fold2, reopen2 |
| d74eaca95e31e59a | 残差小例 · 历史 SVG | initial, full, mixed, deep, fold1, reopen1, fold2, reopen2 |

其中bilstm `147d4d87577504a7` mixed、textcnn `212b86d4ecb9b22e` deep、Transformer `de3a41a1f4dd2b3f`与`f0584cf4142849ee` mixed/deep是本次增加状态覆盖后新发现的4个案例；其余16个已在前次记录。**覆盖扩大导致发现更多，不能直接认定是本轮修复引入回归。**

### P1：陌生嵌套条件图省略条件分支箭头

- 状态：待修复，真实UI与离线均确认。
- 复现：静态打开`inputs/nested_condition.py:NestedCondition`，展开全部，聚焦`if secondary`；完整场景49节点/35边（计数不含条件overlay），层级与分支并存。
- 实际：full有4条条件箭头诊断，两个条件owner各true/false均省略；mixed有2条。诊断为“条件分支标签没有安全空间；关联箭头未绘制”。不要把重复状态中的诊断相加当独立箭头数量。
- 环境：细节图1088×835，100%聚焦；完整SVG的`#sourceControlLayer`诊断计数为4，源码/张量几何校验仍为true。
- 根因分类：条件关系图层的文字避障/路由与验收门槛脱节。结构通过不能掩盖条件关系未绘制；这是带标签的嵌套分支类问题。
- 修复任务：为条件标签与箭头共同分配安全空间，冲突时触发局部布局扩容/重排；将省略诊断纳入完整视图验收，不得靠隐藏箭头消除冲突。
- 回归：本轮NestedCondition full/mixed/reopen；见[局部截图](evidence/visual-generalization-20261017/screenshots/holdout-nested_condition--ui-missing-control-detail.png)与同名SVG。

### P2：固定侧口汇入仍有1.57–2单位窄折返

- 状态：待修复；TimeMixer已真实UI放大并核对DOM路径，TransformerXL为离线路径确认，未补做其局部UI放大。
- 结构：同一汇合节点侧边多路输入、窄通道及固定端口约束。TimeMixer full/mixed/reopen均可复现；TransformerXL initial/fold复现。
- 最小可执行复现输入：`scenes/39ca17212a8004c5--full.json`内`route-0118-117`，`tm.pool2 → tm.collect`；需保留邻居障碍物/端口，直接删去上下文不是等价复现。
- TimeMixer路径：`(1511,4544.5)→(1517,4544.5)→(1517,4324.5)→(1520.6,4324.5)→(1520.6,4322.5)→(1511,4322.5)`。两个水平反向段仅隔2单位，接近箭头尖端。
- 同类：当前`b4e7f02ce4dce8d4` full `route-0199-198`也是2单位；TransformerXL `d7b7d45929e95090` initial `route-0008-7`为1.57单位。
- 预期：正确端口下消除可避免窄回头，端口不足时明确扩容/重新分配，保留边身份。实际路径通过现有几何校验，却不符合可读性优化目标。
- 根因分类：端口分配/路由后处理；完整根因待定位，不可不经复验直接删掉折点。
- 修复任务：在公共路径简化/端口空间分配阶段增加最小回头宽度与合法替代路线搜索，将此类指标纳入回归。
- [100%局部UI截图](evidence/visual-generalization-20261017/screenshots/39ca17212a8004c5--ui-hairpin-detail.png)；同名DOM SVG包含与离线一致的实际路径。箭头样式为原案例scale辅助虚线，不能将其误称为源码条件overlay。

### P2：深层展开耗时与稀疏布局影响阅读

- 状态：待优化。Level5与NestedCondition全展开叶子面积比约0.07/0.06；多层祖先边框和路由通道使布局很高。两者不是仅改标签的案例。
- NestedCondition首次full离线15009ms，RandomDAG4594ms，FourBranch5842ms；相应缓存reopen约100–313ms。性能瓶颈需进一步profile，不能据此声称UI卡顿FPS或单一确定根因。
- Studio原生DenseStress300成功展开306个DOM节点，总览约2%，只能看清整体方向；树聚焦支持局部阅读。六层残差稳定总览约14%，也不能阅读全部标签。不存在已证实的总览裁切。
- 修复任务：profile层级构建/候选路由和重复校验，评估局部重算；对单子容器链、嵌套内边距、通道预留做公共紧凑布局，保护端口与手动布局。保留导航，不能以导航替代布局质量。
- [深残差稳定总览](evidence/visual-generalization-20261017/screenshots/holdout-deep_residual--ui-overview-settled.png)、[300层总览](evidence/visual-generalization-20261017/screenshots/studio-preset-stress_300--ui-full.png)。

## 可重复运行

从正式项目目录：

```bash
node docs/evidence/visual-generalization-20261017/audit.mjs
node docs/evidence/visual-generalization-20261017/topologies.mjs
node docs/evidence/visual-generalization-20261017/verify-results.mjs --strict
```

audit.mjs按案例顺序保存结果与完整场景；正常退出只代表诊断执行完毕。严格检查当前应退出2，因为存在结构失败、条件overlay省略和窄折返。可按`AUDIT_FILTER=holdout`重跑陌生集合；`AUDIT_BASELINE=1 AUDIT_FILTER=holdout`重做受控模块A/B。重新运行会覆盖本目录同名证据，需保留本轮快照时先复制输出目录。Node需要支持toSorted（本轮v24.19.0）。输入bundle已生成，离线脚本不执行Python模型。

UI复查：通过模型菜单→示例与模块库选择案例，需要时勾历史→展开全部/按失败状态展开→等待完成→画布内返回总览→树中聚焦问题节点→检查可读比例截图及实际图层诊断。陌生模型的打开URL记录在[opened.json](evidence/visual-generalization-20261017/opened.json)，依赖本轮临时服务状态。

## 尚未覆盖的规范项目

本轮没有全量覆盖每个案例的手动移动/锁定、新增删除重连、撤销重做、字体尺寸变化、最小视口和全部缩放，也没有全量逐箭头尖端/标签碰撞人工检查。四个拓扑用例是纯引擎证据，未逐一在Studio里交互。DOM SVG采集不等于产品实际导出，本轮没有重做全量实际SVG导出；前轮Transformer/VAE导出结果不能充当本轮重新测试。没有运行产品全测试集，因为本轮未改产品代码。

因此本报告提供完整目录尝试、组合状态结构回归、陌生模型泛化证据与可执行缺陷单，不宣称已满足规范的全部验收门槛。下一轮应先处理条件关系丢失和历史展开失败，再处理窄折返、耗时与紧凑度，并扩展交互/最小视口矩阵。
