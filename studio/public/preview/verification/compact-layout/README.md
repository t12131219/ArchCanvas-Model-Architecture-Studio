# 自动收紧布局与边界主干检查

本轮修改位于 `yworks_edge_router_lab/recursive-graph.js`、`styles.css` 和递归专项测试。模型源码、catalog 和导入快照未重新生成。

- 图内展开/收起按钮默认 opacity 0.45，hover/focus-visible 时 0.9，保留键盘操作。
- 可见子节点及其文字决定当前行列尺寸和父框尺寸，隐藏后代不占空间。
- 保留并行分支顺序；某个同级模块展开变宽时，后续同级模块被推开，避免圆圈算子和文字越界。
- 同一个张量的多个输入共享实际 producer 的主干轴，跨多层容器时减少阶梯折线；frame/side/direction 和 canonical binding 仍由源码证据约束。
- presentationVersion 9 会重建旧投影缓存，保留展开树、局部手动偏移、草稿和标签锚点。

## 结果

`transformer-comparison.json` 比较同一个“Attention 展开，SDPA 收起”的前沿：Attention 高度 704 → 450；SDPA 与 Split 的空白间距 278 → 24。Q/V 各 4 个路径点，K 2 个点直达；所有节点、连接、包含关系和分支验证通过。该同一前沿的线路总长 8,430 → 5,736；折点 42 → 22；交叉 5 → 1（统计来自源码与连接约束校验通过的前沿）。

`browser-folded.json` / `browser-after.json` 是实际浏览器中的收起/展开对比。Attention 714 → 450，收起后内部空间释放；再次打开恢复原展开状态。兼容模式和实时模式都实际拖动 PE 加法节点成功，验证信息见 `browser-compat-move.json` / `browser-realtime-move.json`。测试位移已撤销，用户原展开选择与兼容模式已恢复。

- 完整测试：`all-tests-final.log`，75 项通过，0 项失败。
- 目录状态：`catalog-check.json`，114 个活动模型的 339 个初始/一层展开/完全展开状态，0 失败。
- 递归几何：`branch-geometry-check.json`，799 个分支及祖先展开状态，0 源码身份、文字归属或同级模块重叠错误。
- 深层实际布线：`branch-check-summary.json`：799 个独立分支及祖先展开状态，0 失败、0 漏检；逐状态记录见 `branch-all-states.json`。扫描工具是 `check-branches.cjs`。
- IR 一致性：`ir-reference-check.json`，665 份导入图的 IR 摘要与参考目录一致。
- 只读参考目录：`reference-integrity.json`，12,533 文件，0 修改、0 新增。

`*-final.log` 是最终代码上的检查。没有 `final` 的旧日志保留了本轮发现和修正问题的过程，不代表最终结果。`branches-resume.json` 保存已通过的最终版本状态，分片扫描只对剩余状态继续检查。
