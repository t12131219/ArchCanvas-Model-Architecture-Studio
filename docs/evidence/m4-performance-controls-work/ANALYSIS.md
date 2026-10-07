# 独立原始收据审查

`analyze.py` 不导入浏览器 helper 或产品实现，只用 Python 标准库、冻结前置 baseline 和实际 raw receipt，按测量合同独立重建时窗、匹配图、手势、分母与分布。这个分析器不能验证工具是否真的以原生方式操作；该部分仍需要实际 CUA tool 记录、服务 launch stdout 和原始浏览器收据来源。

```bash
python3 docs/evidence/m4-performance-controls-work/analyze.py \
  --raw docs/evidence/m4-performance-controls-work/runs/actual-raw.json \
  --output-dir docs/evidence/m4-performance-controls-work/analysis-attempt-1
```

用多个 `--raw` 保留全部尝试。输出目录必须不存在，任何失败都保留原始字节、输入前后 hash、逐收据审查和最终 receipt。退出 0 只表示 raw accounting 与合同一致；环境 confound、late/no-input/cancelled 窗口仍会有 warning，不构成性能通过。退出 2 表示 raw/contract 会计错误或输入改变。

分析器检查固定 deadline/边界迟到、两次实际 drain、buffer attempted/recorded/dropped、phase timestamp算术、每个离散输入的完整分母、loaded Studio asset URL binding、pretrial helper hash、coverage矩形算术和采集时的 renderer membership。它重新计算 one-to-one type/target/time 匹配，missing/ambiguous/invalid 均保留未知；actual same-pointer down/up 区间独立于控制器等待与后续 settle。

同一 attempt 中所有 raw 都分组展示，包含 control/product、raf-only/full、操作、rendered membership 和实际尺寸。至少三次匹配复现及顺序交替仍需采集者证明；分组报告不会把未采条件当作已完成，也不会相减 control 时间或隐藏坏窗口。

分布保留全部值、min/median/nearest-rank p95/max/count；rAF 只代表 callback cadence，EventTiming 的匹配子集 interaction maxima 只代表该子集。真实呈现、全页 INP、实际字形字节与真人验收均保持未认证。
