# M4 当前无模板 holdout 与共享/重复/opaque 审计

本目录记录对当前正式工作树的一次新鲜、独立、静态审计。它不改写旧 `m4-holdout-report.json`、`m4-holdout-integrity-audit/` 或任何 seal；审计主结果在 [report.json](report.json)。

当前检查范围是六个手写、无模板入口：`PatchVisionEncoder`、`UnsupportedVision`、`TemporalForecaster`、`SkipSegmentation`、`GraphForecast` 和 `DynamicStateSpace`。分析器与 oracle 在独立 `/tmp` 发行副本中以 `-I -S` 运行，fixture 没有被 import 或执行。结果如下：

- 本地交叉回归：58/58，通过 `local-suite.txt`。
- 新鲜独立 holdout oracle：28/28，通过 `fresh-holdout-report.json`；包括六个 family、输出槽位/反例和 residual bypass 合同。
- 新鲜完整性 oracle：22/22，通过 `fresh-integrity-report.json`；包括六个完整入口和 16 个主动污染拒绝样本。

完整性检查按 `(nodeId, portId)` 精确绑定，并核对声明端口、边的多重集、producer↔tensor 一一对应、containment、source range/digest、instance/call 身份和诊断。当前证据覆盖的语义边界包括：

- `TemporalForecaster` 的共享 projection 保留不同 call 身份；四个嵌套输出保留 `forecast[0]`、`forecast[1]`、`state.hidden`、`state.cell`。
- `SkipSegmentation` 的两个 repeat 成员保持 independent instance、源码顺序和 skip/concat 关系。
- `UnsupportedVision`、`SkipSegmentation`、`GraphForecast`、`DynamicStateSpace` 的未知构造或动态区域保留 source-backed `opaque`，不会因名称被提升为已知算子。

可重跑命令（从本目录的工程根执行）：

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_m4_holdout.py tests/test_m4_holdout_integrity.py \
  tests/test_m4_unknown_boundaries.py tests/test_residual_roles.py

PYTHONPATH=src python scripts/check_m4_holdout.py --project .

PYTHONPATH=scripts:src python \
  docs/evidence/m4-holdout-integrity-audit/check_m4_holdout_integrity.py \
  --project .
```

这些结果只证明声明的静态 AST 合同和保守 unknown 边界。它们不证明具体 shape/dtype、数值或 forward/backward 等价、任意 Python 模型、浏览器渲染/性能、出版尺寸可读性、四向移动后的路由美观、原生取消或 3–5 位真实研究者任务。因此 M4 仍为 partial；本审计不能替代真人与浏览器性能门。
