# 源码图元与多分支布线修订

只细化明确的张量值与二元加法/逐元素乘法。普通 Linear、Conv、Norm、复合计算、拼接及 tuple/list 汇流保留模块图框。矩阵网格是符号，不表示运行时数值或实际矩阵行列数。

共享实现为 `prototype/source_glyphs.py`；原生 Model Zoo、模块和时序生成器使用同一规则。`source_glyph_validation.py` 独立检查源码合同、真实 SVG 圆圈/矩阵、符号、外部名称/shape/证据归属、包含关系和物理端口。105 份核心 semantic IR 与修改前逐字节相同。时序细化表达式须与冻结源码的 AST 子表达式匹配，不能根据节点名称猜运算。

原图中两个输入曾按端口名字固定分配至下方、左侧，造成右侧分支逆向绕行。现在按两个真实生产者位置共同分配独立输入端口；输出仍保存 canonical producer/consumer 和 tensor field。输入横向通道避开标题、shape 和证据行。矩阵名称、shape、运算符说明嵌套于同一个图元 owner，随图元移动。

编辑器的通用路由同时考虑长度、折点、交叉和通道间距。折点落在另一条独立线段上也计入交叉代价；候选通道包括独立线端点附近的绕行通道。惩罚交叉时使用 450 的代价。共享干线的分叉点位于所有消费者均能到达的合法区域；某个消费者的容器出口不能将其他内部线路牵引进边框。源码声明的相同张量可共用主干；不同参数/张量不因几何交点合并；tuple/list 不解释为 Add。

`refine_model_wires.cjs` 对当前含新图元的交叉线路做有界优化，只有零语义/边界错误、交叉不增加且综合代价下降才提交。受拓扑、容器接口和手动折点限制，复杂图不保证所有交叉都能消除。

旧草稿迁移先验证旧源码基准，再比较新旧 canonical 关系，保留手动位移、折点、视觉重接/删除记录与标签锚点。新增圆圈/矩阵的几何端口更新至真实边界；有冲突的路径重新布线。已损坏的源码绑定不能通过迁移被覆盖为有效数据。来源 IR 变化的旧草稿归档到 localStorage；不静默删除。

证据：

- `coverage.json`：各类模型和图元覆盖、逐算子证据与子表达式。
- `refresh.json`：319 个当前视图更新、canonical 连接身份检查。
- `wire-refinement.json`：逐视图交叉、折点、长度对比及受约束保留情况。
- `browser-checks.json`：兼容/实时模式拖动与代表视图检查。
- `validation.json`：最终原生审查、整合验证与回归结果。
- `../source-semantic-audit/report.json`：7 组原生源码/IR/SVG 与负例审查。
- `../semantic-routing.json`：328 个当前视图布线检查。
- `../semantic-display-validation.json`：正交、八方向与曲线显示的边界/共线检查。
- `before/`：修改前的 Highway、多分支 MixHop 数据。

生成与检查不导入或运行上游模型。

最终布线证据（2026-10-13）： 211 个含独立交叉的视图中 201 个接受了有界改进，交叉总数从 1,670 降至 583；全量 328 个当前视图共 5,538 条边，失败 0、边界违规 0、独立张量共线/重叠 0。代表性 SVG 为 `highway-after.svg`、`mixhop-layer-after.svg` 和 `mixhop-dense-after.svg`；交互证据在 `browser-checks.json`。
