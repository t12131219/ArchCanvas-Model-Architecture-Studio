# 残差教学注释图的实际端点核验

当前与 compact_mixed_flow 两份 mini_residual 采用相同注释合同：

- `input_x:out → F:in`：真实输入图元供应变换。
- `F:out → add_norm:in`：变换输出进入复合 Add & Norm。
- `input_x:out → add_norm:skip`：保留输入来自原 x，不能来自 F.out。

图保持自底向上、504×392 的紧凑布局。旁路在输入输出线分叉；F→Norm、Input→F 终段为24px，旁路末段32px，均满足至少18px。

此图是教学注释而非具体模型的运行图；公式与 compound glyph 表示 `z = LN(x + Dropout(F(x)))`，不声称新增模型源码证据。

每条 SVG 路径包含 `data-route-id`、`data-src`、`data-dst` 和 role；独立 `mini_residual_layout.json` 保存 bbox、真实端口、路径与合同。审计直接读取 SVG XML，并用真实矩形重算端口。2个注释图、6条实际SVG箭头通过，8个实际SVG/layout误绑定负例全部拒绝。

[JSON检查记录](actual_mini_residual_audit.json)；复现：

```bash
python3 prototype/arrow_semantic_audit/transformer/mini/audit.py
```

两份最终PNG均已渲染并目视。历史 snapshots 未修改。
