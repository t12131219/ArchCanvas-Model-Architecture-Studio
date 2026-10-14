# Transformer 参考图修订与跨模型验证

2026-10-12。本次结果以此目录链接的报告为准；其他旧截图、专项审查和历史快照保留其生成时的状态。

Memory 现在位于 Encoder 最终输出与 cross-attention 之间。连接进入框的上沿，从下沿继续，在下游分支到 WK、WV；不是把 Memory 作为旁边的标签。框内不叠画连线，以保留文字可读性。它是 `enc.output:out` 的可见值别名，不是新增的计算算子。默认版与 compact 版的概览、模块和详细图都采用此关系。

详细图的真实依赖是 `enc.norm2.layernorm:out → enc.output → Memory → dec.cross.k / dec.cross.v`。Q 绑定 Decoder 当前状态。导入时，同一别名的 K/V 语义记录共享 Memory 物理入口与主干，保留各自的 canonical trace；完整重新布线仍必须经过 Memory。原始 guide 的 SVG、PNG、layout、IR、source evidence 已重新生成，并同步到 Summary_Merge。

同时恢复 FFN hidden 的值快照虚线，区分说明线与张量依赖；显示 cross SDPA 的 memory padding mask；统一当前自有生成图的 shaft 线帽为 `butt`。原始 PyTorch SVG 与历史快照保留原件。[线帽更新记录](linecap-update.json)覆盖 327 个当前生成视图。

浏览器复查还发现说明图层原来位于容器底色之前，导致 hidden 快照虽在 SVG 中却被遮住。现在先画容器、再画说明，使 hidden、形状标签和残差说明实际可见；浏览器证据同时记录了两条值快照说明线及图层顺序。

## 三层验证的作用

1. 原生源码检查：Transformer 适配器静态读取支持的 EncoderLayer/DecoderLayer AST，提取 Q/K/V、mask、residual capture、Post-LN 和 FFN 顺序，与 IR 及源文件摘要比较。其他模型继续使用各自的来源与接口检查。没有执行模型，也不声称能解析任意 Python。
2. 渲染检查：比较 SVG、layout、IR 与源码摘要，验证实际叶接口、张量别名的物理续线、包含关系、完整依赖处置和箭头末段。Memory 绕过可见框、指向错误 owner 或被接到 Q 都是错误。
3. 编辑器导入保护：`semanticBaseline` 独立保存节点 metadata、parent、alias owner、IR digest、canonical trace 和固定端口。重建 routing contract 不能把损坏的语义当作新基准；缺失连接会触发全图错误。显式重接、释放端口和删除仍是可撤销的视觉 draft，保留源绑定。校验失败阻止 Apply。

验证器负责发现并拒绝不一致，修复由有源码依据的适配器重新生成；不会根据节点距离自动猜测模型语义。原始纯 SVG、说明图与历史材料的完整性保护不构成新的模型源码证据。

## 实际结果

| 检查 | 结果 | 记录 |
| --- | --- | --- |
| 原生 source/IR/SVG 与负例 | 7 组通过；模块 76、Model Zoo 25、时序模型 4 | [原生审查](../source-semantic-audit/report.json) |
| Transformer 默认版 | 3 个正例视图；18 个损坏负例全部拒绝；路径数 25 / 41 / 85 | [Transformer 负例](../../snapshots/transformer_programmatic_guide/generated/semantic_negative_checks.json) |
| 其他原生负例 | 模块 399 个；Model Zoo 3 个真实 SVG 损坏；时序 26 个错误操作数，均拒绝 | [原生审查日志](../source-semantic-audit/) |
| 导入 metadata / 端点保护 | 327 个当前视图；1,956 个负例全部拒绝 | [导入负例](../source-contract-negative-checks.json) |
| 当前约束路由 | 328 个视图、5,538 条边；98 个按需目标，92 条重算、6 条合法通道保留；0 失败、0 违规 | [路由报告](../semantic-routing.json) |
| 三种路径显示及包含关系 | 5,538 条边；0 违规、0 对不同张量共线重叠 | [显示检查](../semantic-display-validation.json) |
| 目录完整性 | 8 组输入、5,724 个快照文件、665 个导入视图；SHA、标签及 IR 保留 | [目录检查](../catalog-validation.json) |
| 编辑引擎回归 | 18 项通过；包含六个 Transformer 视图的 Memory 必经与共用主干、重初始化拒绝损坏 | [回归日志](graph-engine-tests.log) |
| 复杂视图全量重布线 | Transformer 85 条、Autoformer 125 条、两张 TimeMixer 145 / 240 条；均 0 失败、0 违规 | [全量重布线](../full-route-representatives.json) |

目录总数为 666 个视图，包含一个内置路由实验。当前 328 个视图包含原始 PyTorch SVG；327 个有导入基准的视图中包含两张说明图。历史视图不套用新的模型正确性结论。

## 图像证据

- [Memory 局部修复效果](memory-after.png)：生成图的真实裁剪，显示上下接口。
- [Memory 到 K/V 的完整路径](memory-full-route.png)：显示最终编码器输出、Memory 以及 cross-attention K/V。
- [修订前图像](transformer-before.png)：本轮开始时的旧图，仅作历史比较。
- 浏览器中的实际图元、重布线路径及检查状态记录在 [browser-checks.json](browser-checks.json)，截图见 [transformer-editor.png](transformer-editor.png)。

可从 [整合入口](../../yworks_edge_router_lab/index.html?case=01093cc06a87b35a&view=detailed)查看详细视图。打开页面后选择“概览 / 内部模块 / 算子详细”可检查同一语义的不同粒度。
