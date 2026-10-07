# M4 语义边界独立复核：2026-10-07

本次从当前正式工作树重新运行 M4 静态 holdout 与身份链，保留前一版 `../report.json` 原字节。结果见 [receipt.json](receipt.json)，封存字节摘要见 [process.json](process.json)。产品 frontend 未改；未导入、构造或执行 fixture/model，未借用失败原型 runtime。

| 收据 | 结果 | 实际证明范围 |
|---|---:|---|
| 当前本地交叉回归 | 59/59 | 六个 holdout、完整性 checker、未知边界源码探针和 residual 关系 |
| 独立发行 holdout | 28/28 | 六入口，输出槽位和 bypass 合同/反例 |
| 独立完整性 oracle | 22/22 | 六个完整入口及 16 个主动污染反例 |
| 独立 unknown suite | 19/19 | 对源码字面量进行静态 AST 分析的保守边界探针 |
| 当前 source-facts 身份链 | 5/5 | 三个源码入口的视觉编辑、DocumentStore 保存/重开及实际 SVG metadata |

这些套件有重叠，不相加成为产品覆盖数。三个独立发行副本分别由正式 `check_independence.py` 生成；Python 使用 `-I -S -B`，只添加 copied `src`/oracle tests。原 provenance JSON 以确定性 gzip 保留全部原字节，原始大小/SHA、包来源和输入子集记录于主收据；解压即可校验，不改写原 `/tmp` 来源。

新增源码级反例为 `tests/test_m4_unknown_boundaries.py::test_unresolved_registered_name_stays_opaque_with_shared_call_identity`：源码 `from plugin import Linear` 刻意与注册算子同名且有共享别名。分析结果保留 `kind=Linear/category=opaque/evidence=opaque`、未知构造 warning、同 `instanceId` 的两个独立 `callId` 和空 children；没有注册 Linear 合同。它补足已有“图上把 unknown 改成 contract”污染测试之外的真实源码解析边界。

语义 gate 仍为 `bounded_pass`。正式计划 §18.2 的 holdout 要求是“可恢复部分准确，未知不造假”；当前六个声明入口及静态反例支持这一有限范围。§18.3 的 shared/repeat 身份、repeat 顺序/计数通过完整 oracle；其中 TemporalForecaster、SkipSegmentation、GraphForecast 的编辑/重开/实际 SVG metadata 保留来源事实。没有新家族模板，没有因 unknown 名称赋予已知语义。

本复核不证明任意 Python、每个参数 origin、具体 shape/dtype、forward/backward 数值等价、未知 kernel 内部语义、真实浏览器折叠/展开操作、呈现性能、四向移动美观、85/180 mm 真人出版审看或研究者任务。这些边界解释了 `bounded_pass`，不能改写为 M4 全量完成。按用户最新指示可继续 M5；本收据不改变 M4 `partial` 或真人 0。

可重跑：

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_m4_holdout.py tests/test_m4_holdout_integrity.py \
  tests/test_m4_unknown_boundaries.py tests/test_residual_roles.py

PYTHONPATH=src python scripts/check_m4_holdout.py --project .
PYTHONPATH=scripts:src python scripts/check_m4_holdout_integrity.py --project .
PYTHONPATH=scripts:src python scripts/check_source_facts.py --project .
```
