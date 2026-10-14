# 通用端口、短路径与交汇点跟随

入口：`../../yworks_edge_router_lab/index.html?case=01093cc06a87b35a&view=detailed`。

本次规则用于全部 115 个当前案例：328 个导入模型视图、5,538 条连接。历史素材保留原始证据；编辑器使用同一套运行时。

## 端口与路径

源码/IR 的 canonical 字段决定张量身份、生产者、消费者、层级、别名和字段插槽；可变的 physical ports 只决定画布上的连接侧和位置。原始 fixed ports 和绑定记录继续作为证据。普通叶图元可选择合法边，圆形图元仅用边中点，容器端口只沿登记的边移动，别名和共享输出插槽受保护。

候选路线按长度、折点、交叉和不同张量重叠代价选择。短间距尝试直线与少折点路线，复杂障碍使用可见性图。移动后也重新考虑仍合法但绕远的路径。该实现没有证明任意障碍下的数学全局最短，也不等同商业 yFiles 求解器。

原 SVG 首/末直线穿过的祖先容器接口可跟随对应端点；接口所属容器、边、方向和穿越次序仍被校验。Memory 保持上入下出；同一张量的共享干线保留，不同张量不得合并。

## 交汇点

用户截图中的圆点原先被 SVG 顺序分配给了另一个模块。适配器现在依据源张量身份、注册路径与至少三条入射方向建立 `junctionMarkers`。圆点不再存放于模块静态 HTML；运行时从实际分支路径计算坐标。旧草稿删除登记的旧圆点片段、补齐归属，同时保留节点位置和路径。

普通交叉不生成连接点。多个不同物理端口的几何交叉也不自动生成分支。移动操作在所有相关分支更新后验证拓扑；Apply 在整批路由结束后验证，失败则整批回退。源码基准保护圆点的张量身份、归属和路径引用。

## 验证覆盖

- 328 个当前模型视图、5,538 条连接。
- 8,370 个可变端点、5,332 个登记接口跟随关系、939 条受保护共享干线。
- 514 个 source fork 均位于实际共享路径；5 个集合的实际移动检查通过。
- 33 个编辑器回归、13 个独立路由回归、3,714 个导入保护负例通过。
- 原生 Transformer 27 个源码/IR/layout/SVG 损坏负例通过。

## 实际证据

- `browser-pe-after.json`：PE 移到右侧后使用 PE 左边 → 圈加右边；canonical 字段未改。
- `browser-layernorm.json`、`browser-layernorm-after.png`：原始直通接口随 LayerNorm 移动。
- `browser-junction-after.json`：分支点 x=382 → 430.278，位于两条同源连接上，85 条连接无违规。
- `browser-junction-history.json`：撤销恢复 x=382，重做恢复 x=430.278。
- `junction-final.png`、`browser-junction-final.json`：最新运行时实际移动和 Apply 后的截图与 DOM。
- `policy-coverage.json`：全量端口/接口/分支元数据覆盖与静态检查。
- `junction-motion.json`：5 类模型集合的移动检查，源绑定保持一致。
- `graph-engine-tests.log`：通用编辑器回归，包括两版 Transformer 的三个视图、水平/垂直/反向分支、旧草稿迁移及拓扑负例。
- `../source-contract-negative-checks.json`：完整性与篡改负例。
- `../source-semantic-audit/report.json`：7 组原生源码、IR、layout、实际 SVG 检查，没有执行模型。
- `../semantic-routing.json`、`../semantic-display-validation.json`、`../full-route-representatives.json`：全量与复杂图路由验证。

生成器同步：`prototype/transformer_programmatic_guide/semantic_routes.py` 及 compact 变体把 source fork 写入渲染元数据，原生验证器检查标记坐标与源码身份；适配器用相同关系导入 Summary_Merge。原生 Transformer 检查包含 27 个损坏负例。
