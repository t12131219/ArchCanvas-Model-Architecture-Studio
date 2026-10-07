# M4 源码压力场景：300 层普通 Sequential

Studio 示例 `Dense 300-layer stress` 对应 `fixtures/stress_300/model.py` 的 `model:DenseStress300`。源码逐行显式声明 150 对 `nn.Linear(16, 16)` / `nn.ReLU()`，共 300 个不同 module instance；没有源码构造循环、forward 循环、外部 graph 模板或人工注入 IR。fixture authoring 可以生成这些文本行，但正式分析只读取静态声明，不导入或执行模型。

正式 analyzer 实际产生 304 个 canonical nodes 和 304 个 canonical edges。`createDocument` 默认展开根模块，仅非根 `network` Sequential 容器收起。该初始 scene 为 4 nodes / 2 edges；展开 network 后为 304 canonical nodes / 302 scene edges，其中 300 个是实际 Linear/ReLU 层对象。收起后恢复 4 nodes / 2 edges。

302 条 scene edges 包含 input→network 的容器输入边、input→第一层、299 条层间连接和最后层→Output。根输入 adapter 和 network result adapter 在 projection 中隐藏；scene 节点与连接都来自同一 analyzer 事实图。

运行独立证据命令：

```bash
PYTHONPATH=src python scripts/check_m4_stress.py --project .
```

该命令将正式源码复制到 `/tmp`，用 `-I -S` 运行 source contract，再用复制的正式 `createDocument` / `applyVisualBatch` / `buildScene` 取得 counts。证据在 [m4-stress-report.json](evidence/m4-stress-report.json) 与 [m4-stress-scene-receipt.json](evidence/m4-stress-scene-receipt.json)。Python source contract 和 Node core 场景检查均通过。

浏览器性能采样应先选此示例并保留 network 收起，再执行既有 non-root expand/collapse/fit benchmark；其唯一目标是 network。此文档和 core receipt 仅证明压力数据规模与 canonical 来源，不声明 latency、FPS、模型运行正确性或长链图的出版排版质量。
