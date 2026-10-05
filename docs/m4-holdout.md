# M4 无模板模型泛化：多家族 holdouts

本阶段加入一个独立于已有 Transformer、MLP 与 Residual CNN 样例的手写 vision holdout：`fixtures/holdout_vit/model.py` 的 `PatchVisionEncoder`。它由 patch `Conv2d`、token `flatten/transpose`、`LayerNorm`、`MultiheadAttention`、两次残差、`Sequential` MLP、`mean` 池化和分类 `Linear` 组成；源码没有依赖旧 prototype，也没有模板快照或预先生成的图。

同一文件保留 `UnsupportedVision` 负例。它通过 `OpaqueTokenMixer` 使用注册表之外的 `nn.Conv1d`。分析器报告一个 source-backed `opaque` 节点和 warning，不把名称推断成 `Conv2d`、attention 或可编辑的已知层。这个边界用于确认新增 holdout 不以牺牲 unknown safety 换取覆盖率。

`fixtures/holdout_families/model.py` 加入另外四个独立入口：`TemporalForecaster` 的 LSTM 返回 sequence、`h_n` 与 `c_n`，共享 projection 在两个不同调用中使用，最终返回嵌套 dict/tuple 的四个 tensor 输出；`SkipSegmentation` 保留两个独立 `ConvRefinement` repeat、skip 与上采样结果的 concat，未知 `ConvTranspose2d` 保留 opaque；`GraphForecast` 的自定义 `GraphAttentionKernel` 名称不获 attention 合同，依赖数据的 if 合并为 opaque `ConditionalRegion`；`DynamicStateSpace` 的自定义 `StateSpaceScan` 和依赖输入 shape 的 loop 均保留 opaque，循环内部 projection 不伪报为无条件执行。

独立手写 oracle 在 `tests/m4_holdout_oracle.py`，测试在 `tests/test_m4_holdout.py`。测试冻结全部节点种类、category/evidence、端口关系与关键 constructor 参数，核对共享 instance 和不同 call identity、repeat 的 independent 成员、嵌套输出、MHA 三具名端口、残差/skip concat、以及未知 constructor 和动态区域诊断。oracle 不导入或执行 fixture。

从正式目录生成独立 `/tmp` 副本并用 `-I -S` 运行的命令是：

```bash
PYTHONPATH=src python scripts/check_m4_holdout.py --project .
```

本次证据为 [m4-holdout-report.json](evidence/m4-holdout-report.json) 和 [m4-holdout-independent-suite.txt](evidence/m4-holdout-independent-suite.txt)：独立 `/tmp/archcanvas-independent-4lgexvos/release` 的 Python 28/28（六个 family holdouts＋十个输出槽位合同/反例＋十二个 bypass 合同/反例）通过，正式 Studio 的 [输出路径独立测试](evidence/output-path-studio-independent-suite.txt) 3/3 通过。各入口实际计数为：

| 入口 | 节点 | 边 | opaque 节点 |
|---|---:|---:|---:|
| PatchVisionEncoder | 17 | 21 | 0 |
| UnsupportedVision | 5 | 4 | 1 |
| TemporalForecaster | 9 | 8 | 0 |
| SkipSegmentation | 16 | 15 | 1 |
| GraphForecast | 7 | 8 | 2 |
| DynamicStateSpace | 5 | 5 | 2 |

`check_independence.py` 的独立发行检查还会分析 `holdout_vit` 的 `PatchVisionEncoder` 与 `holdout_families` 的 `TemporalForecaster`。

多输出修复前的六项测试只核对了四个 tensor producer 与编号 Output，dict key/tuple index 缺失；这个历史 partial 状态和原报告保留在 [before-output-path](evidence/before-output-path/m4-holdout-report.json)，不改写历史浏览器收据。当前每个 Output 增加 `outputPath` key/index 证据，TemporalForecaster 的手写预期分别为 `forecast[0]`、`forecast[1]`、`state.hidden` 与 `state.cell`。同一 tensor 在多个位置返回时保留多个 Output 身份；None 槽位不制造 tensor，但后续 index 不移动。动态 key、dict unpack 与不能无损序列化的 key 将整个字典保留为 `OpaqueDictionary`，绑定可見 key/value 依赖，不给未知内部槽位猜路径。

`outputPath` 纳入 IR digest。当前 TemporalForecaster 的 source digest 为 `3a6976a808974cfbb911cf2bab8c44b7d302c20c0e28046e1a9e7002fe51b667`，IR digest 为 `0e60a72fa479c1a84b69ca3cffe7d2efba27727c2e0b7f4c6b653066f8c1a189`；各模型完整绑定见当前报告。Python 保存校验、JSON Schema 和 TypeScript 校验接受可序列化的已知槽位并拒绝 malformed 路径；槽位改变后不继承旧编号 Output 的显示别名。

完整 CNN source oracle 又发现 `x + residual` 的 skip 位于右侧，旧分析器把 Add 的左输入硬编码为 residual。当前只在两个不同 tensor producer 间存在由已恢复的非 opaque 节点组成的严格依赖路径时，把祖先 tensor 所在输入标为 residual；Add 的 category 也仅在这种 bypass 获证时为 residual。`tests/test_residual_roles.py` 使用独立手写源码验证左右交换、误导变量名、并行分支、无关输入、opaque 中间/端点、同 tensor、LSTM 同 producer 多输出槽位与 sibling-output 路径，以及 AugAssign。缺少 recoverable return 的 custom forward 现在与诊断一致地标记为 opaque，不能建立 bypass 证据。修复前 16＋3 的报告保留在 [before-residual](evidence/before-residual/m4-holdout-report.json)；ViT 与 Transformer 既有 bypass 事实保持成立。

该证据只覆盖声明的静态 AST 子集和 source-backed unknown 边界。它不声称任意模型、动态区域内部语义、Conv1d/ConvTranspose2d/GNN/SSM kernel 合同、具体 tensor shape、运行时数值等价或三宿主支持。publication 字号、性能与研究者任务仍属于后续 M4/M5 工作。
