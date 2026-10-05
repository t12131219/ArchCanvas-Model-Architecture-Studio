# AI 模拟新手：从零建模路径审计

当前冻结`Cr_xKW9U` Studio **没有可用的常用模块拖入库或空白模型建模入口**。本轮AI尝试没有搭出Input→Linear→ReLU→Linear→Output；这项能力尚未实现，不能把示例树或视觉图元下拉项当成功的模型库。已有示例的对象选择、显示名/颜色/pin入口可发现；Linear维度显示为只读事实。

本轮先从新的8911服务和tab37只看实际UI，再复核正式源码；子代理起初没有CUA browser capability，实际UI操作由root通过支持的CUA完成，子代理独立读截图/visible DOM。没有代入真人，没有模型执行、语义commit或产品源码修改。

| 尝试 | 观察与结论 | 证据 |
|---|---|---|
| 首屏找空白模型/模块库 | 默认是Transformer，左側是示例选择、源码导入、模型层级；未发现新建空白/模块卡片。 | `initial.png`、`initial-dom.txt` |
| 点击带＋的源码导入 | 实际DOM出现“从Python源码开始”，需单文件源码或架构JSON；空源码时分析打开按钮disabled。这是源码入口，未创建模型草稿。 | `import-dialog-dom.txt`；对应早期PNG像素stale，已排除。 |
| 选择MLP、展开network | 实际DOM出现8个事实对象和Linear1/GELU2/Dropout3/Linear4，表明导航现有模型。 | `mlp-example-dom.txt`、`mlp-expanded-dom.txt` |
| 左侧Linear1拖入空白画布 | root实际拖动[130,354]→[943,366]；before/after完整SVG20922字节完全相同，revision=1、同8个节点identity，未新增模块。 | `tree-drag-before.svg`、`tree-drag-after.svg`、`tree-drag-after-dom.txt`、`tree-drag-after-fresh.png` |
| 点击Linear1找参数/样式 | 当前对象有显示名、图元样式、填充、固定入口；in_features=16/out_features=32位于“模型事实只读”。输入连接需登记运行输入与模式，检查按钮disabled。 | `linear-selected-dom.txt`、`linear-selected.png` |
| 新图端口连接、ReLU创建 | 没有新图/新节点入口，未执行新图连接或创建ReLU；不能用既有MLP的GELU或改接提案填这一步成功。 | 上述实际入口与源旁证。 |

早期`getScreenshot({emit:false})`所得`import-dialog.png`、`mlp-example.png`、`mlp-expanded.png`与各自DOM阶段不符；实际像素观察已保留在[排除记录](excluded-screenshot-observations.json)。更后的fresh native screenshot能显示MLP展开和对象选中。截图尺寸由1280×720变为1102×835，因此不把本链当固定viewport、屏幕连续性或性能证据，不推断调度原因。

UI-only阶段结束后，正式源码旁证确认了缺少的能力：[source-corroboration.json](source-corroboration.json)包含完整源码快照和具体行段。`HierarchyTree`只处理展开/选择，左侧没有palette/draggable，typed视觉operations没有add/remove模型节点或边，`ParameterEditor`只支持Dropout p/MHA dropout，input port拖动只形成受限既有源码改接提案。既有source import/static analysis不等于新建模型authoring。常用模块注册候选及可验收的闭环列在[module-palette-backlog.md](module-palette-backlog.md)，尚未实现。

AI观察可能提示的新手卡点：初次尚未做编辑即出现“有未保存编辑”；左侧熟悉的层名称容易被试作模块库；“页面预设”实际上只切彩色/黑白；Linear看得见构造事实却不能改维度。右侧视觉属性有明确标签，既有示例编辑入口比较可见。这些是AI模拟观察，不是真人意见或评分，也没有3分钟任务或完成率主张。

本轮独立服务的原始启动/能力缺口见[browser-capability-blocker.json](browser-capability-blocker.json)。服务后续留给root同标签的方向连线审计；本报告不宣称8911已关闭、端口空闲或tab已清理。所有截图只覆盖其冻结构建，不能继承到后续代码变更。用户8765与真人五席未触碰，`researchGate=not_run`、`humanSuccessCertified=false`。
