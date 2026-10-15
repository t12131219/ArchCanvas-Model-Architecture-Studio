# 独立路由谓词差分

`reproduce.cjs` 在独立 Node VM 中读取本轮优化前的 router 与当前 router，只导出内部几何谓词进行比较，不执行模型，也不运行图路由矩阵。

确定性种子 `20261015`，包含 30,288 个线段接触例和 60,000 个矩形行列筛选例。覆盖短尺度近平行、旋转、平移、六个尺度及矩形边界/容差附近坐标。撤除线段包围盒剪枝后，最终两类差异均为零；`receipt.json` 绑定脚本与实际 router SHA。

`before-rejected-aabb.json` 记录被撤销方案的 2,900 个差异。原接触判定对短线段使用叉积和距离和容差，允许某些超过固定 EPS 包围盒的近接触，不能用固定 EPS 包围盒提前拒绝。矩形行列筛选仍调用原始精确谓词，这批检查没有发现差异。

这是明确范围的差分样本，不是所有浮点几何的数学证明；完整路线与源码合同检查另见上一级证据。

重现：从正式项目根目录执行 `node docs/evidence/act-source-support-20261015/routing-performance/predicate-audit/reproduce.cjs`。
