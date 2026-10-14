# Transformer：源码接口与实际箭头专项审查

本轮修正了默认版和 compact 可选版的源码端点，并重新生成三层 SVG、JSON、PNG。两种阅读方向保留：默认版内部向上，compact 内部保持向下/横向。上游模型源码未修改、导入或执行。

| 活跃产物 | 源码投影的连接数 | 实际 SVG 路径 | 结果 |
| --- | ---: | ---: | --- |
| 默认 overview / modules / detailed | 24 / 40 / 70 | 24 / 40 / 83 | 全通过 |
| compact overview / modules / detailed | 24 / 40 / 70 | 24 / 40 / 83 | 全通过 |
| 两份 mini residual 教学图 | 各 3 条教学关系 | 共 6 条 | 全通过 |

六张主图共 **294 条实际路径**，另有 mini 的 6 条。详细图有 13 个张量别名，穿过网格的同一连接被拆成前后两段，所以物理路径数大于源码投影连接数。独立审计包含 **66 个源码断言**、**20 个主图错误注入**；mini 另有 **8 个实际 SVG / layout 错误注入**。所有负例均被拒绝。

[独立主图审计 JSON](actual_transformer_audit.json) · [实际 SVG 检查器](audit.py) · [mini 审计](mini/actual_mini_residual_audit.json) · [历史完整性与已知端点局限](history_integrity.json) · [原型总审查](../箭头语义审查报告.md)

## 修正的源码对应

| 关系 | 旧记录的问题 | 当前实际箭头 |
| --- | --- | --- |
| PE | PE 矩形身份被用于独立 Add 圆圈的输出 | `embedding.out → pe.add.x`；`pe.buffer.out → pe.add.pe`；后续从 `pe.add.out` 出发 |
| residual | `sublayer:input_tap` 只是一处几何分叉，未追到真实 producer | 第一层来自 PE Add；后续来自前一层 LayerNorm；详细图进入真正的 Add `x` 端口 |
| Encoder memory | 外部箭头只到 cross-attention 的外框接口 | 从 Encoder 最终 LayerNorm 分别进入 `dec.cross.k:in` / `dec.cross.v:in`；Q 来自 Decoder 当前 LayerNorm |
| 展开的 FFN / Add & Norm | 箭头可能结束或开始于展开外框，内部续线是匿名路径 | 输入到 `linear1.in`，输出来自 `linear2.out`；Add 的输出真正进入 LayerNorm，后续从 LayerNorm 出发 |
| Q/K/V 与 FFN X/Z 网格 | 网格只有颜色和位置，没有可核对的 producer | 每个网格注册值别名身份、owner 与实际 in/out；不得绕入其他张量网格 |
| 模块粒度 Attention 摘要行 | 描述性矩形没有源身份；compact 未完整连接行内部 | 显式 `projection_summary` / `sdpa` / `output_summary`，保存 source members、Q/K/V 命名端口及实际续线 |

源码接口由 `semantic_routes.source_contracts()` 明确声明，`canonical_terminals()` 递归解析到当前可见的叶算子。折叠的 summary 是声明成员的源码范围，而不是新增 Python 算子。源码决定生产者、消费者及字段；原有布局通道仅提供可走的几何路径。程序会先删除旧匿名绘图路径，再按完整源码投影重新输出实际箭头。

SVG 每条路径具有 `data-src` / `data-dst`、`data-canonical-src` / `data-canonical-dst` 及 `data-semantic-edges`。layout 逐条保存全部 **134 条 IR 边**的处置：声明接口别名、实际连接或同一可见源码范围内折叠。详细图处置为 47 条接口别名、81 条被实际 trace 覆盖的源边、6 条折叠于 cross SDPA 内部的依赖；dropout / NaN guard 等透明步骤保留在 trace 中。不能靠“有一个合法 edge ID”证明任意端点，也不能把缺线假称为折叠。

## 验证与复跑

从 `prototype/` 目录运行：

```bash
python3 -B transformer_programmatic_guide/draw_transformer.py
python3 -B transformer_programmatic_guide/variants/compact_mixed_flow/draw_transformer.py
python3 -B transformer_programmatic_guide/check_svg_routes.py \
  transformer_programmatic_guide/generated \
  transformer_programmatic_guide/variants/compact_mixed_flow/generated \
  --border 0.1 --summary --strict
python3 -B arrow_semantic_audit/transformer/audit.py
python3 -B arrow_semantic_audit/transformer/mini/audit.py
```

重新生成 SVG 后，应先用 `rsvg-convert` 更新同名 PNG，主图独立审计才会接受当前 SVG 的栅格预览。审计读取实际 XML，与 layout 逐点核对几何、箭头、实际端口、canonical 字段与 source trace，再与独立写自 supplied forward 的 24 / 40 / 70 条预期关系清单比较。代码不导入绘图器或上游模型；它也核对原源码 SHA256 和证据行范围。

20 个主图负例覆盖：memory 错接 Q、residual 来自处理后输出、PE buffer 替代 Add、Q/K 操作数互换、端点停在展开外框、FFN 跳过 ReLU、仅修改实际 SVG 落点、实际路径缺失、无身份实际路径、网格 alias owner 错配。两种方向各运行一组，拒绝结果保存在审计 JSON。

本轮从**正式目录的最终 SVG**重新渲染六张同名 PNG 及 Attention 局部图。审计 JSON 记录 SVG、PNG、layout、IR、evidence 的 SHA256，并通过“当前 PNG 与重新运行 rsvg-convert 的输出逐字节相同”验证。已查看两套全图 contact sheet 和原尺寸 cross-attention / FFN / PE 局部，确认 memory 实际进入 WK/WV、Q 独立、FFN 主链与网格连续，compact 新增通道避开标题和形状标注。

[默认版全图凭据](current_contact.png) · [compact 全图凭据](compact_contact.png) · [默认 cross-attention](current_cross_attention.png) · [compact cross-attention](compact_cross_attention.png) · [默认 FFN](current_ffn.png) · [compact FFN](compact_ffn.png)

## 保留历史的范围

`snapshots/` 中 **37 个文件、7 张 SVG** 的 SHA256 与审查前清单相同。它们按只读方式检查，并在 `history_integrity.json` 中记录实际路径数、无 source trace 的路径、旧 PE 身份、residual 来源和展开外框端点实例。旧图仍有这些历史端点局限；本轮“通过”仅适用于活跃的六张主图与两份 mini。

`prototype/pytorch_transformer_original/transformer_architecture.svg` 是上游自带参考图，原样保留并单列 SHA256，不当作本原型的已验证生成结果。compact 的 `preservation_manifest.json` 描述最初保存版本；当前活跃目录已修订，应使用本轮审计 JSON 核对当前哈希。旧 `route_diagnostics.json` 在历史目录保留，活跃目录的记录已刷新。

这些证据针对随附实现与手写适配器，不能证明任意源码的数值等价。图中的顶层 Softmax 是明确的虚线解释步骤，cross SDPA 在详细图仍折叠，mask 条件由 caller 决定；没有执行模型，也没有将任意未提供的配置当作运行事实。
