# 模块箭头语义独立审计

范围：76 个模块 × 3 视图，共 228 个 SVG。
核对 2723 个实际图框、2407 条 SVG 路径、2407 条显式类型依赖。

Independent fixed source hash + AST span references + IR boundary alias traversal + actual SVG XML coordinates; no drawing-engine functions imported.

## 当前结果

通过：True。错误分类：`{}`。

## 待修复的实际端点

| 模块 | 视图 | 路径 | 实际端点与期望 |
|---|---|---|---|

JSON 保留每条显式箭头的源码符号/行号、IR 端口、期望可见节点、实际布局端口和 SVG 坐标。
折叠容器可作为不透明摘要；展开容器必须有真实边界续线或显式接口绑定。布局 rank 不能充当数据依赖。
本检查没有执行模型；叶子命名端口的值身份仍依赖可审查的源码适配合同，不能仅由 SVG 像素证明。
