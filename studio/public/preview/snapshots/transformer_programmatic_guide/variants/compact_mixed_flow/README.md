# 紧凑混合方向版

本目录保留统一自底向上之前的版式选择，并已同步本轮源码端点修正。

- 整体向上，Attention 内部向下；SDPA 与 FFN 横向展开。
- Linear→Q/K/V 张量横向连接，投影分支并列；memory 实际进入 K/V，Q 独立接 decoder 状态。
- 固定 9px 箭头，末段至少 18px，不沿模块边框走线。
- 图1/图2/图3为 1600×1218、1600×1606、1600×2308；图3仍比最初 2562px 版缩高约 9.9%。图2为补齐真实摘要行端口和内部续线稍增间距。

[三图预览](generated/index.html) · [图3 SVG](generated/figure3_detailed.svg) · [图3 PNG](generated/figure3_detailed.png) · [Transformer 专项审查](../../../arrow_semantic_audit/transformer/README.md) · [原型总审查](../../../arrow_semantic_audit/箭头语义审查报告.md) · [返回版本选择](../../版本选择.md)

本目录含源码及证据副本，可独立运行：

```bash
python3 draw_transformer.py
python3 check_svg_routes.py generated --border 0.1 --summary --strict
```

输出只写入本目录 `generated/`。本轮 `semantic_routes.py` 按明确源码接口投影到可见叶端点，真实 SVG 中的 `data-src/dst`、`data-canonical-src/dst`、`data-semantic-edges` 可与 layout/IR 逐项核对；每条 IR 边有处置记录。Q/K/V、FFN X/Z 是保留 producer 身份的张量别名，不能靠几何邻近换值。教学 mini 新增真实 Input x，残差从输入分叉而非 F 输出。

`preservation_manifest.json` 是最初保存可选版时的历史摘要，不能作为本轮活跃文件的哈希证明。原始脚本、图片、旧 `route_diagnostics.json` 与 Markdown 保存在 `../../snapshots/before_bottom_up/` 及审查前备份，未改动。活跃 `generated/route_diagnostics.json` 已刷新；本轮实际 SVG/PNG/layout/IR 哈希及渲染一致性见 [专项审计 JSON](../../../arrow_semantic_audit/transformer/actual_transformer_audit.json)。完整长文中的旧示例计数属于历史叙述，以本 README 与专项审查为准。
