# M4 holdout 完整绑定补审

2026-10-05，六个正式 holdout 入口的补充独立静态 oracle 通过 `22/22`，无 skip。它使用从正式工程复制的 `/tmp/archcanvas-independent-r82swyfe/release`、Python `-I -S`，只加入 copied `src` 和 copied tests。模型源码未被导入或执行；产品 frontend 仍为 `ce7f7f733da28cb31ecff80ca029a53094e88f8451bffc3874f8167f80a07d00`。此补审没有改产品源码、Studio 构建、历史 holdout/base-model 报告或旧 seal。

新预期在 `tests/m4_holdout_integrity_oracle.py`，checker 与反例在 `tests/test_m4_holdout_integrity.py`。全部 59 个节点、102 个声明端口和 61 条关系按 fixture 源码及公开 atomic API 合同手写核对，关系沿用已有手写 `m4_holdout_oracle.py`，没有使用 analyzer snapshot 生成期待。精确 `(nodeId, portId)` 查找防止别的节点上的同名端口蒙混过关；端口名称、方向、角色、ordinal、constructor 参数、return path、instance/call 身份、源字节/范围/调用表达式和 producer-to-tensor 双向唯一性均检查。

| 入口 | 节点 | 边 | 声明端口 | 绑定 tensor producer | Call / Instance | opaque |
|---|---:|---:|---:|---:|---:|---:|
| PatchVisionEncoder | 17 | 21 | 35 | 13 | 10 / 10 | 0 |
| UnsupportedVision | 5 | 4 | 6 | 2 | 3 / 3 | 1 |
| TemporalForecaster | 9 | 8 | 14 | 6 | 4 / 3 | 0 |
| SkipSegmentation | 16 | 15 | 26 | 11 | 12 / 12 | 1 |
| GraphForecast | 7 | 8 | 13 | 5 | 3 / 3 | 2 |
| DynamicStateSpace | 5 | 5 | 8 | 3 | 2 / 2 | 2 |

六项完整入口正例之外，16 项主动破坏测试拒绝外来同名端口、共享 producer tensor 拆分、LSTM 多输出槽位 tensor 合并、额外未绑定端口、错角色/ordinal、重复关系、重复 containment、错 parent、repeat 成员顺序交换、伪共享、共享 instance 调用身份合并、unknown 冒充注册语义、opaque 虚构内部节点、unknown 构造实参改变、缺失诊断与错源码 SHA/调用表达式。每项先验证原图通过，再要求相应破坏得到明确拒绝。

custom-root 子项核对完整多重集及 parent，不把 sibling 展示顺序声明成源码执行顺序；Repeat/Sequential 额外按实际源码执行顺序核对子项。MHA 仍声明两个 API 输出端口，其中 `weights` 在 `need_weights=False` 下没有 tensor 绑定；未使用的 API 输出不能制造伪 tensor。opaque 保留可见依赖、实参和 warning，不能因名称或 callable 成功而补出 attention/recurrent/动态区域内部语义。

补审暴露的是历史 checker 的证明范围，而非产品实际输出错误。[四项主动探针](evidence/m4-holdout-integrity-audit/historical-checker-probes.json)实测：原 Temporal 测试接受外来同名 input port 和共享 tensor 拆分，原 ViT 测试接受额外声明 attention port，原 segmentation 测试接受 recovered operation 的错误 parent；新完整 checker 均拒绝。原关系 `set + len` 对当前唯一预期关系已经排除重复边，这里不把它误报成现有 duplicate-edge 漏检。

运行命令：

```bash
.venv/bin/python scripts/check_m4_holdout_integrity.py --project .
```

独立报告、原始套件 stdout、每个模型 architecture/proof、copied oracle/checker/fixture 字节和 package provenance 已逐字保存在 [补审证据目录](evidence/m4-holdout-integrity-audit/process.json)。原始 report 保留 `/tmp` provenance，不重写为新的来源。[报告](evidence/m4-holdout-integrity-audit/m4-holdout-integrity-report.json)分别绑定 oracle、旧手写 relations、checker、发行检查器、frontend、architecture 与 proof SHA。

与旧 v2 seal 的选取核对中，直接绑定的 frontend 和三项发行脚本均保持匹配；该 seal 没有直接列出这次选取的四个旧 oracle/checker 与两个 holdout fixture。`process.json` 明确记录未直接绑定项，不能把“所有已有直接绑定匹配”扩成“所有静态输入直接受该 seal 约束”。新补审用自身独立复制报告 `sourceManifest` 以及保留字节绑定其输入，尚不属于旧 seal，后续 current seal 应另行纳入。

本证据仅覆盖这六个声明 AST 入口。它不证明 arbitrary Python、具体 shape/dtype、数值/forward/backward 等价、每个 parameter origin、浏览器出版/呈现性能、原生活动取消或真人任务，不能据此宣布 M4 完成或继承新构建的旧浏览器矩阵。
