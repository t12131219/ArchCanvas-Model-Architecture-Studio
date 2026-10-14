# 紧凑混合方向版：上次的箭头优化结果

本目录保存统一自底向上之前的最终版本，供与当前默认版并列选择。

- 整体流程向上，Attention 内部向下；SDPA 与 FFN 横向展开。
- Linear→Q/K/V 张量横向连接，投影分支保持并列。
- 固定 9px 箭头，末段至少 18px，不沿模块边框走线。
- 图3为 1600×2308，比最初 1600×2562 版缩高约 9.9%；九类检查通过。

[三图预览](generated/index.html) · [图3 SVG](generated/figure3_detailed.svg) · [图3 PNG](generated/figure3_detailed.png) · [当时的完整说明](源码到Transformer三层架构图_对应关系与程序化布局.md) · [返回版本选择](../../版本选择.md)

脚本、SVG、PNG 与布局记录直接取自 `snapshots/before_bottom_up/`。本目录另含源码及证据副本，生成脚本可独立运行。在本目录执行：

```bash
python3 draw_transformer.py
```

输出只写入本目录的 `generated/`。当时的 Markdown 内容保留，内嵌图已指向本目录的旧版图片。文件摘要见 [preservation_manifest.json](preservation_manifest.json)；生成后可用 [check_svg_routes.py](check_svg_routes.py) 重新核对箭头、边框和端点。
