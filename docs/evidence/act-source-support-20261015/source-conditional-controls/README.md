# 源码条件的独立展示关联

`SourceConditional → 直接 SourceBranch` 使用独立的棕色虚线、空心箭头与条件判定菱形。`条件成立 · true` / `否则 · false` 和统一图例明确标为“条件分支 · 非张量”。它只表达 AST 包含关系；不会把 if/else 串为执行顺序，也不会声称某条运行路径已确定。

关联不进入 canonical `graph.edges`、tensor/value IR 或源码审查 receipt。直接父子关系、sourceKind 与相同源码 evidence 是生成条件。几何借用现有 `SummaryEngine.routeOne`、`SummaryConstraints.validate` 和 `SummaryRouteLabels.place`；实际节点、标题、容器墙、已记录路线、动态路线标签、随 owner 移动的附件、说明文字与分叉标记参与避让。空间不足时不画非法箭头，在预留的判定菱形显示 `!`，hover 可读诊断。

计算仅发生在已完成的 frontier/route/move/validate 事务及已提交的文字/视觉编辑。`render` / 图例读取不会调用路由器。缓存覆盖当前可见对象、真实坐标与路线、文字/附件等几何；拖动中缓存过期时暂时隐藏关联，正常提交后重新生成。单色预设只改绘制颜色，保留虚线语法。

## ACT 真实输入

以最终 `final-arrow-support/ACTPolicy-preview.json`（181 个详细对象、139 条源码边）为输入。三种局部 frontier 均得到两条条件关联、零诊断，canonical source/layout/每条边全部通过，额外 `refresh` 前后 canonical 内容 hash 相同：

| Frontier | 可见对象 | canonical 边 | 条件关联 |
| --- | ---: | ---: | ---: |
| 条件展开、分支收起 | 15 | 10 | 2 |
| 训练分支展开 | 27 | 18 | 2 |
| 两分支展开 | 29 | 19 | 2 |

运行 `node docs/evidence/act-source-support-20261015/source-conditional-controls/reproduce.mjs` 重建 [act-frontiers.json](act-frontiers.json)。receipt 包含输入和引擎 hash、节点与边计数、完整关联路线和标签框、canonical 不变 hash 及约束结果。`timing` 是该次 Node 事务的局部测量，不是浏览器帧率或普适性能承诺。

`studio/tests/previewSourceControls.test.ts` 覆盖直接包含、反例、不同比例/独立嵌套展开、不修改 canonical、缓存失效与渲染不布线、无合法空间、Worker/fallback 一致、单色与导出 scope、可移动文字/附件障碍。
