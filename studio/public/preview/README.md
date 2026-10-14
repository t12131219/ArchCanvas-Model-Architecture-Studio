# Summary_Merge：语义约束的统一 Edge Router 编辑器

2026-10-13 未知源码适配层：新增标准库 AST 后端和页面“导入模型源码”入口。源码经统一 IR、来源校验和现有递归图/路由器接入；未知调用与动态控制流保留待解析区域，不运行模型。推荐用 `python3 -B source_adapter/serve.py --port 8767` 启动，打开 `http://127.0.0.1:8767/yworks_edge_router_lab/index.html`。已有静态服务可导入 CLI JSON。使用、接口与支持边界见 [适配说明](source_adapter/README.md)，联网参考 FX/export/Netron/torchview 见 [研究记录](source_adapter/RESEARCH.md)，交互证据见 [适配验证](verification/source-adapter/README.md)。现有模型 catalog、snapshots 和复件未改动。

2026-10-13 源码图元与布线修订：明确张量值使用矩阵网格；独立二元加法/逐元素乘法使用真实圆圈 +/×，复合模块与 tuple/list 保持原语义。端口按生产者方向分配，文字归属于图元；交叉代价包含落在线段上的折点，多分支干线按所有消费者的合法通道跟随。旧草稿保留手动位移、折点和标签锚点迁移。规则、覆盖、截图与验证见 [专项证据](verification/source-glyphs/README.md)。

2026-10-12 交互模式：右侧“交互模式”可选择“兼容模式”或“实时模式”，选择保存到 `summary-merge:interaction-mode`。兼容模式沿用当前的轻量逐帧预览，松开后由 Worker 从拖动前快照完成权威路由和完整校验；实时模式每一帧从同一快照执行权威 `move()`，因此箭头端点、分支/合并干线、容器接口和跟随文字会立即更新。两种模式共用 IR、source binding、parent、Memory 和边界约束，非法最终位置会恢复到拖动前或上一合法状态。当前模式也写入画布的 `data-interaction-mode`，便于浏览器验证。

两种模式的浏览器和源码证据见 [`verification/interaction-modes.json`](verification/interaction-modes.json)。

2026-10-12 连线文字与边框修订：源适配器为文字登记 canonical route / IR 绑定，236 个标签沿实际路径跟随并可单独拖动吸附；统一路由按笔画宽度避让容器边框，共享分叉与角落接口随安全通道调整。全部当前视图已扫描，详见 [证据与截图](verification/route-labels/README.md)。

2026-10-12 交汇点跟随：分支圆点通过源码张量与注册连线确定归属，按实际共享路径计算位置；移动、Apply、撤销和重做使用同一关系。旧 SVG 中误挂在其他模块里的静态圆点会迁移，普通交叉不会成为语义分支。

2026-10-12 短路径与容器接口跟随：语义字段和物理连接位置分离，普通图元自动选择合法连接侧；短间距优先直线，移动后也优化仍然合法的绕行路径。LayerNorm 等内部算子的原始直通出口可随所属端口移动，保留容器边、层级与穿越次序。Memory 上入下出、分支干线和多字段插槽继续受保护。共享路由器已同步，全部当前示例由 Summary_Merge 的 index 展示。实现、浏览器截图和验证见 [专项证据](verification/shortest-routing/README.md)。

2026-10-12 拖动修订：移动时立即修正相关连接的直角路径，检查端口方向、箭头末段、障碍与已记录的容器接口；无法合法连接的位置会整体回退。Q/K/V 名称与形状跟随张量图元，模块标题跟随模块，容器携带子图元及各自附件；文字本身也可拖动所属图元。原生生成器、导入元数据及运行时校验均保存明确归属。截图、DOM、撤销/重做与跨模型结果见 [专项证据](verification/drag-follow/README.md)。

2026-10-12 交互性能修订：拖动预览改为 `requestAnimationFrame` 合帧，SVG 节点、边和标签采用稳定图元复用；缩放只更新相机和命中区，路由文字在预览态使用有界候选搜索。松开节点或 Apply 后，复制图在可复用 Worker 中完成完整路由与源码/边界验证，主线程只提交已验证结果；localStorage 写入改为防抖。Transformer、TimeMixer、Model Zoo 和模块代表视图的源基准、浏览器拖动、撤销/重做与 4,002 个语义负例见 [性能证据](verification/performance/benchmark.json) 和 [交互测试](verification/performance/interaction-tests.log)。

2026-10-12 已按 Transformer 参考图同步更新原始 guide、compact 版和合并入口。新增 `semanticBaseline` 与 `source-contracts.js`：从导入数据固定源码身份、包含关系、canonical trace、别名 owner 和端口，防止重新初始化时把语义损坏当作新基准。显式重接、释放端口与删除仍保存为视觉 draft，源码绑定保留。SVG 导出包含节点语义及 draft 操作记录。

当前跨模型源码/IR/SVG 与负例结果见 [修订与验证说明](verification/reference-refinement/README.md)。原生检查结合每个模型自己的 AST/来源规则；运行时基准只防止导入后被改坏，不声称能从任意源码自动推导语义。检测到错误时拒绝并由对应适配器重新生成，不会根据距离猜测新的模型连接。

Memory 已恢复为线路上的最终 Encoder 输出值别名：连接从上沿进入、从下沿继续，再分支到 cross-attention 的 K/V。同一 Memory 值共用物理入口和主干，Q 仍绑定 Decoder 状态。若浏览器缓存与新原图不兼容，先保存到 `summary-merge:archived:<案例>:<视图>:<时间>` 的 localStorage 记录，再显示新原图；已有标签页不会被强制刷新。

入口是 `yworks_edge_router_lab/index.html`，它把八组输入例子合并到同一个可交互的 SVG 编辑器中。启动本地预览后打开 `http://127.0.0.1:8766/index.html`；也可以直接打开本目录的 `index.html` 作为跳转页。

## 这次整合保留了什么

- `yworks_edge_router_lab` 提供节点移动、端点重接、连接创建、折点、Undo/Redo、Orthogonal/Octilinear/Curved 近似、Path As Needed 和障碍物避让。
- 模型图的节点、容器层级、固定端口、原始 SVG 图元、布局 JSON、语义 IR、source map 和源码证据都被复制到 `snapshots/`，编辑器只改当前视觉副本。
- 每条导入边保留 `binding` 和 `semantic_trace`。生产者/消费者端点不能被普通重布线替换；重接和新增连接标为 `draft`，不会伪造模型语义。
- 展开容器按照原始边的 border gate 路由。无关容器是实障碍；相关容器只开放已记录的 gate。子节点移动会被限制在父容器内部，并检查同级模块碰撞。
- `fork_bus` / `collection_bus` 在记录的 junction 处分段，作为 tuple/list 的分支或汇流骨架保留；它们不被解释成求和。只有源图明确存在的 Add/Sum 节点才表示求和。
- 折叠模块的同一视觉入口若对应多个不同 `semantic_trace`，会分配相邻物理槽位。例如 TimeMixer 的 `tm.collect:side:scale` 三个尺度现在分开连接，同时保留其原始 trace。
- 箭头使用原始 SVG 的 user-space marker 参数：`markerWidth=10`、`markerHeight=8`、`refX=9`、`refY=4`。路径到达物理端口，线帽为 `butt`，避免转折处出现多余短线或箭头接缝。

## 如何查看证据

页面中选择任意案例后，`SOURCE CONTEXT` 会列出原始 SVG、布局与接口、语义 IR、源码映射、源码证据和原始案例。右上角“审查与迁移证据”可打开导入覆盖、SHA256 清单和整合验证。

可以直接查看以下证据：

- `verification/catalog-validation.json`：665 个导入视图、源标签、IR 和源布局绑定的完整性检查。
- `verification/semantic-routing.json`：328 个当前视图的约束路由检查；逐视图计数保存在报告中；0 条失败、0 条违规。
- `verification/semantic-display-validation.json`：5,538 条当前连接的正交、八方向、曲线显示检查，以及包含关系和不同张量共线检查；0 条违规、0 对不同张量共线重叠。
- `verification/source-contract-negative-checks.json`：328 个导入视图、4,002 个破坏源码 metadata、包含关系、端点、trace 或别名的负例全部被拒绝，包括重新初始化后的检查。
- `verification/source-semantic-audit/report.json`：7 组原生源码/IR/SVG 与负例检查通过，Transformer 包括 31 个源码 AST、IR、Memory 续线与 SVG 损坏负例。
- `verification/full-route-representatives.json`：两个 TimeMixer 视图、Autoformer 和 Transformer 详细视图的完整重布线检查；均为 0 失败。
- `verification/arrow-terminal-comparison.html` 与 `.png`：真实 Transformer SVG、旧末端重现和修复后的箭头端点对照。
- `verification/semantic-connection-comparison.html` 与 `.png`：TimeMixer 原始 SVG 与按 `semantic_trace` 分槽后的容器连接对照。
- `verification/summary-merge-editor.png`：统一编辑器的实际浏览器渲染截图。
- `../yworks_edge_router_lab/evidence/verification/overlap-regression.html` 与 `overlap-fixed.png`：用户 13-edge 状态的共线重叠修复证据。
- `verification/input-manifest.json`：八组输入快照的 SHA256；`snapshots/` 是可复核副本。
- `verification/performance/benchmark.json`：5 个代表视图的 9 次热身配对基准；校验约 1.85–4.67×，标签布局约 2.73–18.47×，源级预览移动低于 0.04 ms；浏览器实测 Transformer 预览帧 p50 约 3.2 ms、p95 约 5.7 ms。
- `verification/performance/interaction-tests.log`：文字精确摆放、预览移动的包含/边界约束、Worker 提交和损坏语义拒绝测试。

## 约束和边界

这是独立的浏览器端复刻，不依赖商业 yFiles 运行库，也不会执行模型源码。正交路由、八方向倒角和曲线是本地实现的近似；原图没有合法接口的新增跨容器连接会保持为红色草稿并提示检查端口。历史快照中的视觉推断节点明确标记为 legacy SVG geometry，不被当作新的模型事实。

重新生成导入数据时运行：

```bash
python3 tools/build_catalog.py
node tools/route_catalog.cjs
node tools/verify_semantics.cjs
node tools/check_source_contracts.cjs
python3 tools/audit_source_semantics.py
python3 tests/verify_catalog.py
node tests/graph-engine.test.cjs
```

`build_catalog.py` 只复制和解析已存在的布局/SVG/IR/source evidence；它不会运行任何模型。

2026-10-13 递归展开：编辑器现在只维护一张模型递归图。概览只是默认的可见前沿；双击容器、点击节点右上角的 +/−，或使用检查器可以逐个打开直接子节点。每个分支可以停在不同深度，收起父容器不会丢失后代的展开选择，再次打开会恢复该分支的局部布局。`recursive-graph.js` 保存详细源码树、概览/模块/详细快照的证据来源、前沿边的原始 edge id、canonical binding、端口和 boundary gate；隐藏内部边会投影到最近可见祖先，不会把概括线伪装成新的模型连接。展开、收起、全部展开、撤销/重做、兼容/实时拖动、连线文字和 SVG/JSON 导出共用这一份文档。每个模型的递归状态写入 IndexedDB，旧的三级草稿保持归档。递归专项测试见 `tests/recursive-expansion.test.cjs`、`tools/check_recursive_catalog.cjs` 和 `verification/recursive-expansion/`。

2026-10-13 自动收紧布局：部分展开时，按当前可见模块及其文字占用范围计算行列间距和祖先容器大小；收起内部模块立即释放隐藏内容的空白，并保持并行分支的相对顺序。展开变宽会推开相邻模块，矩阵和算子周围的变量文字也计入容器边界。同一张量进入多层容器时优先沿共同主干穿过接口，减少边界附近的阶梯折线；不同张量仍使用独立通道。旧递归文档升级到 presentationVersion 9 时保留展开选择、手动偏移和标签锚点，仅重建可见前沿缓存。图内 +/− 按钮默认 45% 不透明度，悬停或键盘聚焦时 90%。证据与回归记录见 `verification/compact-layout/`。
