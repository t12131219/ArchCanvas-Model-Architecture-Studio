# 时间序列原型：源码、IR 与真实箭头端点审计

本次修正覆盖 `timeseries_programmatic_guide` 的四个已有适配器与共享绘图引擎，保留 Transformer 字体、色板、自底向上主链、三粒度折叠规则及正式视图尺寸。上游模型代码没有导入或运行；只读取 ZIP、复制证据文件、解析 AST，并执行本项目的绘图与验证程序。

## 修正的真实操作数

| 模型 | 修正前的不足 | 当前绑定 |
|---|---|---|
| Autoformer | 侧线按可见外层组投影，展开后可能仍从组边界出发；trend 没有独立生产者接口 | `series_decomp` 的 `trend` 输出绑定 Moving average，而主输出是 `x - mean`。展开时 trend 箭头从 Moving average 出发；折叠时由分解边界代表该命名字段 |
| Autoformer | memory 只到 cross 模块边界，没有独立的 K/V 目标 | memory 真实 IR 边到 cross Q/K/V projection 的 `memory_KV`，声明仅供 K、V；主链供 Q。完全展开时物理终点为投影算子，图中同时注明 `Q: decoder; K,V: memory` |
| iTransformer | 统计旁路源端口被写成普通 `out` | 反归一化读取保存的 `mean_std`，而非归一化后的张量值 |
| PatchTST | 跨层分数字段不够明确 | 第 1 层 raw scores 的 `scores` 进入第 2 层 raw scores 的 `prev`。展开后箭头仍进入 Softmax 前分数节点，而不是 Attention 外框、Softmax 或 A@V |
| TimeMixer | 只画最后递推状态进入返回列表，未显式表示已保留的中间尺度 | 每个 season/trend 路径增加三个 `retained_scale` 输入，最后尺度由主链输入；trend 恢复尺度顺序 0..3。原始分量以 `season[i]` / `trend[i]` 命名，接入对应尺度 Add 的 `original_scale` |

这些字段与来源均有源码片段支持，例如 `self.cross_attention(x, cross, cross, ...)`、`return res, moving_mean`、`attn_scores + prev`、`out_season_list.append(...)`、`out_trend_list.reverse()`。AST 检查针对这些实际表达式，不以文件名或图中标签代替操作数核对。

## 端点和折叠规则

1. 适配器显式声明源码对应结构，再生成完整 IR。`port_bindings` 由真实 `boundary` / `output_binding` 边物化，不按节点 rank、绘制先后或列表首末位置猜测接口。
2. 模块展开时，命名输出追到实际内部生产算子，命名输入追到实际消费算子；遇到展开的子模块继续递归。Dropout 等 inline fold 只能沿真实单路径 IR 边穿透。
3. 整个模块折叠时，由最近可见祖先代表它的字段。一个已展示的内部算子不能被主链收缩跳过。
4. 每条实际 SVG 路径都有 `data-semantic-trace` 和 `data-representation`，包含主链、残差、tuple/list 分支、汇流总线及辅助旁路。汇流总线代表字段收集，不暗示加法。
5. 辅助边两端都折叠进同一边界时，登记 `suppressed_edges` 与理由；不能无记录漏掉真实操作数。
6. 独立检查器从真实 IR 边重建展开接口，不信任 renderer 给出的 `projected_src` / `projected_dst`。实际 SVG/XML 路径、矩形和 JSON 的几何登记也逐项比较。

## 保存与验证

修改前两目录共 388 个文件已按字节备份，清单为 [before_manifest.json](before_manifest.json)。其中时间序列目录 113 个文件均核对备份摘要；25 个上游源码副本完全未变。[timeseries_before_after.json](timeseries_before_after.json) 列出修改前后摘要和每视图路径数。备份在 `../before/`，原始 ZIP 仍只读，验收器检查已审阅 ZIP 摘要与其成员字节。

| 范围 | 结果 |
|---|---|
| 正式 12 个 SVG/PNG 视图 | 全部通过；608 条真实路径均有 IR trace；画布尺寸与修改前相同 |
| 4 个完全展开审计 SVG/PNG | 全部通过；659 条真实路径均有 IR trace，用于覆盖正式版折叠掉的内部端点 |
| 26 个错误注入负例 | 全部被拒绝，包括错误源码操作数/返回次序、错误元组字段、漏掉保留尺度、错误来源/目标算子 |
| 16 个节点列表与 rank 扰动 | 全部通过，端点绑定不依赖 IR 节点排列顺序 |
| 几何与导出 | 三视图的真实 SVG 路径和布局登记一致；末段至少 18px、不沿边框、不穿叶框、主链向上；PNG 尺寸一致 |

六个正式负例和四个完全展开负例同时修改实际 SVG 路径与布局端点登记，使几何坐标仍正确指向一个已注册的错误图框；独立检查器仍能拒绝。因此检查不限于“端点坐标等于自己登记的端口”。

机器结果见 [timeseries_arrow_checks.json](timeseries_arrow_checks.json) 和 [正式导出验收](../../timeseries_programmatic_guide/generated/export_checks.json)。视觉核验已查看 [正式 12 图总览](visual/formal_contact.png)、[完全展开 4 图总览](visual/expanded_contact.png)，以及 Moving average、cross K/V 投影、TimeMixer 尺度回收、PatchTST raw scores、iTransformer 统计来源的局部 PNG。完全展开图仅用于审计覆盖，不代替较紧凑的正式预览。

从 `timeseries_programmatic_guide` 运行：

```bash
python3 generate.py --png
python3 verify.py generated --png
python3 check_arrow_semantics.py generated --report ../arrow_semantic_audit/timeseries_transformer/timeseries_arrow_checks.json
```

这些检查证明指定静态适配器中的已审阅操作数、展开/折叠端点和实际导出的对应关系。它们不证明模型运行时数值等价、任意新配置的控制流、任意源码自动语义恢复或所有文字与连线之间的全局最优排布。复合算子内未拆出的字段仍明确保留在接口；没有凭参考 PNG 补造内部计算。

Transformer 当前版、可选版与 mini 的专项结果由另一个审计文件记录；其历史 snapshots 保留原字节。本页的通过结论不追溯认证未更新的历史图像。
