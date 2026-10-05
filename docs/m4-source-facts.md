# M4 共享实例、重复和未知边界的显示与身份链

静态分析已保留的事实需要在图与对象检查器中可见。此前 TemporalForecaster 的两个 `projection` 都显示为 Linear，参数相同却没有可见的共享说明；四个 Output 仅显示序号。当前对象来源面板显示同一实例的不同调用、可选择的同实例调用列表、完整返回槽位、证据类型、源码位置和可展开的稳定身份。别名、颜色、图元样式不参与实例分组，也不能提升 evidence。

图内采用紧凑文字：共享实例显示 `shared instance · 2 calls`，返回槽位显示 `return.forecast[0]`、`return.state.hidden` 等。完整的括号形式 `return["forecast"][0]` 保留在检查器、SVG title 与 metadata。过长槽位只缩略图内 subtitle，保持既有对象宽度，metadata 的 key/index 不截断。repeat 明确标记 independent/shared **instances**，避免把没有参数的共享模块也称为共享权重。opaque 优先显示 unresolved boundary，并保留虚线；视觉改名为 Attention 或使用 attention 图元仍保留原始 opaque fact。

SVG metadata 增加 `sourceFactScope=whole-source-architecture` 和完整节点事实清单，包括当前 frontier 隐藏的对象；`renderedNodes` 单独列出本页实际对象与 canonical identity，详情边界另标 `boundary=true`，避免把外部来源或隐藏事实误当本页可见节点。`renderedBindings` 保留每条绘制关系对应的 canonical edge IDs、producer/consumer ports、tensor identity 与 role。此信息来自当前 CanvasDocument 的 architecture，不从显示别名、论文模板或旧版本补造。

新增 [source-facts 独立报告](evidence/source-facts/report.json) 与 [五项源码反例测试](evidence/source-facts/independent-suite.txt)。`scripts/check_source_facts.py` 从正式工程复制到 `/tmp/archcanvas-independent-17p23s4x/release`，Python 用 `-I -S` 仅加入复制的正式 src，Node 使用复制的 core。它对三个源码入口独立分析、创建画布、修改别名/样式/pin、通过 DocumentStore 保存并重开，再生成正式 Scene 与实际 publication SVG，核对其来源事实、绑定、文档/视觉/storage revision、input/output digest。所有 artifacts 保留在 [source-facts 目录](evidence/source-facts/)。

| 源码入口 | 本次核对事实 |
|---|---|
| TemporalForecaster | 同一 Linear instance 的两个不同 call；forecast 两个 tuple index、state hidden/cell 四个完整路径；视觉编辑和重开后的身份不变 |
| SkipSegmentation | 两个不同 ConvRefinement instance；repeat 为 independent；详情外部边界仍指向原 canonical 对象；ConvTranspose2d 保留 opaque |
| GraphForecast | GraphAttentionKernel 与动态 ConditionalRegion 保留 opaque；任意 attention 显示别名/图元不改变事实或凭空产生 MHA |

反例还覆盖相同 label 的独立 instance、重复 callId 不被计为不同调用、Scene fact 修改不反写 Canvas，以及很长且含 XML 特殊字符的输出 key。专项测试 5/5 与 TypeScript noEmit 通过；生产构建和实际浏览器操作由本轮统一验证另行记录。

这项改动不改变 Architecture/CanvasDocument JSON schema 或 source/IR digest。Scene JSON 和 SVG 字节会因新增来源 metadata/title 与紧凑说明改变；旧导出证据保留历史状态，不能用新渲染覆盖后声称旧工件已获证。工程身份链没有导入、构造或执行模型，不证明张量形状、数值等价、浏览器手势、真人研究任务、出版最终尺寸可读性或 PDF 保留 metadata。
