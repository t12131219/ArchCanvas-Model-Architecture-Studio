# 混合语义图残缺问题修复与视觉复核

日期：2026-10-28。对应用户提供的完整 Transformer F1 图与残缺混合图。本记录更正此前混合前沿阶段的视觉验收结论：原始节点、依赖账本守恒并不能证明图形完整；旧截图中的阶段缺失、连线错乱及空白不应被验收为可用。

## 已定位的原因

1. `source-runtime.js` 使用 `!n.boundary_ports` 排除局部面板端口。但 Summary 的 Add & Norm、角色路径、重复调用、结构区域也用 `boundary_ports` 保存精确的切边清单。这一判断删除了真正的语义展示容器，子节点随后被提升到错误的父层级，破坏阶段顺序、外框和依赖布局。
2. 原先对每个目标设置 `paperFocus` 后编译。Summary 的聚焦面板会重新分配展开预算、生成临时接口，并采用不同的返回值附属策略。它不是全模型中只改变一个模块深度的等价操作。
3. 最后的统一投影没有合入局部 `edgeAttachments` 和 `metadataKinds`，让原版已正确附属的返回分支重新变成实体连线。绑定恢复还错误覆盖了 policy 中的结果槽位；循环模型的 `0`、`1` 会退化为 `out`。
4. 浏览器持久化可能直接重开旧的残缺几何；仅修改投影不能修复已保存的旧画布。

## 修改后的衔接

- 仅排除真正的临时 `boundary_edge` 端口和 `boundary-interface-group`；保留带切边清单的展示区域及其成员父子关系。
- F0/F1 和各中间切面先在完整模型中按原版 publication 生成，再提取目标子树。只有目标在全局代表前沿中完全不可见时，才回到原版的局部聚焦机制。
- 合并 canonical representatives、绑定、元数据类别、返回分支附属策略。仅在绑定指向局部临时端口时恢复 canonical 边，保留原版已经解析的结果槽位。
- 保留端点、端口均一致的原版连线说明；未触碰区域继续沿用原有依赖。
- renderer 更新为 `native-semantic/16`。旧版混合画布重开时，在 Worker 中重新编译并重新布线，保留原 IR、模块请求、视觉草稿和编辑文档，旧几何存入 `migration.previousNativeLayout`。旧版没有混合切面的画布不触发此次重排。旧版本的撤销快照不跨投影版本复用。
- 旧版混合编辑 JSON 保留原几何作为迁移记录，依据 IR 与状态重新生成当前切面；不继续恢复残缺位置。

没有修改 Summary 原版的 29 个 semantic 模块。本次修正位于正式 Studio 的集成层；没有 Transformer 名称、encoder 路径或模型 ID 专用分支。

## 视觉复核结果

正式主程序 `http://127.0.0.1:8790/`，实际 iframe、Worker、Studio 面板和浏览器持久化：

| 状态 | 实际显示 | 视觉核对 |
| --- | --- | --- |
| encoder F1 + decoder F0 | 51 图元 / 54 边 | encoder 的两段 Add & Norm、Feed-forward 和完整 attention 保留；decoder 的阶段摘要保留，原来的巨大空白与缺失外框消失 |
| encoder F1 + decoder F1 | 82 图元 / 80 边 | 两侧 Layer 1、五段 Add & Norm、三组 attention、两组 Feed-forward 与正常图结构相符 |
| 双侧 F1 放大至 28% | 同一图，无切面替换 | 核对 Q/K/V 路径、attention 输出、残差线和各阶段包含关系 |
| 编辑模式撤销与重做 | decoder F1 → F0 → F1 | 模块独立状态恢复，重新回到视图模式后仍是完整双侧 F1 |
| 旧 v15 混合画布刷新 | 自动升级至当前投影 | 保留两个模块的独立请求，恢复完整阶段，无需清空用户浏览器数据 |

双侧 F1 的 DOM 记录显示 `data-source-constraint-valid=true`、`data-layout-constraint-valid=true`，80 条边的 `data-constraint-valid` 均为 true，五个 Add & Norm 均处于展开状态。截图是视觉证据，DOM 校验是补充证据，二者不能互相替代。

- [修复后的 F1/F0 混合图](evidence/summary-mixed-presentation-fix-20261028/mixed-f1-f0.png)
- [修复后的双侧 F1 全图](evidence/summary-mixed-presentation-fix-20261028/sibling-f1.png)
- [放大的阶段与 attention 细节](evidence/summary-mixed-presentation-fix-20261028/f1-detail.png)
- [浏览器图元和连线校验记录](evidence/summary-mixed-presentation-fix-20261028/browser-f1.json)

## 自动化验收

新增 `summaryMixedPresentation.test.ts`，以原版完整模型投影为对照，逐一核对可见图元、父子关系、原版 paper 描述、阶段定义、展开状态、边身份、两端槽位、条件和 bundle。Transformer 双侧 F1 另逐项比较所有图元的坐标、尺寸、颜色，与原版全局 F1 一致；不再只核对数量或账本。

- 展示结构回归：46 项通过，覆盖 43 个原生案例的 F0/F1，以及 Transformer 兄弟切面、阶段成员、物理布线与旧版迁移。
- 原有混合前沿回归：145 项通过，包括所有原生案例的中间切面、877 个容器的原子展开、源码/CPU/合并模式、草稿、JSON 和编辑继承。
- 原生视图、文档、紧凑状态、作者编辑：40 项通过。
- Worker 传输：15 项与独立 generic-build 1 项分别通过。最初合并运行在结束前被终止，后续分组重跑均正常退出；不把初次未完成的命令计作通过。
- 强化旧残缺画布迁移的定向回归、构建和指纹检查的最终结果见 [validation.json](evidence/summary-mixed-presentation-fix-20261028/validation.json)。

各组存在覆盖交叉，不合并为一次全量测试数。本轮没有重跑整个前端大套件，也没有宣称对全部 46 个案例进行了人工视觉逐图检查；43 个原生案例使用结构对照，人工视觉检查集中于用户报告的 Transformer。三项登记案例的投影代码本轮未改。

任意数千节点的原子视图仍受布线预算约束；原子事实可达与所有物理连线完成继续分别验收。这一限制不能用来接受本次已修复的小型混合视图残缺。
