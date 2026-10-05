# 从零建模的模块库：待实现验收清单

本清单来自本轮8911的真实UI尝试与其后的正式源码复核，是新增产品能力的要求草稿，**尚未实现**。它不把既有示例树、彩色/黑白页预设或 imported 模型视觉编辑包装成模块库，也不改变 M4 真人门。参考 DL-Playground 的交互意图；不复制无明确许可的参考代码，不使用失败旧 prototype 作为底座。

当前可复核缺口：新标签默认打开 Transformer；左侧是示例/源码导入/模型层级。将实际 Linear 树行拖入空白画布，完整SVG字节没有变化。选择 Linear 的右侧有视觉显示名/填充/pin，in_features/out_features 为只读。当前 typed visual operations 没有模型节点/边增删；受限端口拖动形成既有源码的改接提案。

## 用户闭环与优先级

| 优先级 | 用户看到的能力 | 可接受证据 |
|---|---|---|
| P0 | 明确的“新建模型”入口，打开真正的空白模型文档；可返回示例/导入。 | 新的隔离浏览器session仅靠可见控件创建空白模型；没有自动塞入默认Transformer或要求手工JSON。 |
| P0 | 左侧“模块库”与“模型层级”分开，按用途分组，提供搜索；卡片显示名称、用途、必需参数、输入/输出。 | Input、Output、Linear、ReLU等实际可拖入；鼠标和键盘都有可见反馈。没有只做卡片、点击后仅加说明或画一个假框的stub。 |
| P0 | 拖入创建独立实例，同类块可重复添加；选择后编辑真实参数。 | 连续放两个Linear得到不同instance/call identity；设置16→32、32→4在文档、端口合同、自动生成源码和重新分析结果一致。参数无效时解释错误并保留上一个合法图。 |
| P0 | 从输出端口连到兼容输入，直观连接/断开；支持修改刚建图的计算关系。 | UI独立搭建Input→Linear→ReLU→Linear→Output；不存在关系的节点不能靠绘制箭头宣称已连接；反向/重复输入/悬空/环路按声明合同拒绝或标明不完整。 |
| P0 | 新建草稿有模型名称、输入名、输出名、参数与接口；未完成状态明确。 | 空图、缺输入/输出、未连接参数节点不能伪称完整nn.Module、proven architecture或可训练网络。 |
| P0 | 撤销/重做覆盖新增、参数、连接、删除及视觉样式；保存刷新保留同一文档。 | 完整操作链逐字段核对；重新打开仍保留稳定身份、端口绑定、参数、位置、图例与visual history的声明边界。 |
| P0 | 图上构建完成后自动产生受管理的新模型源码预览；无需用户手写代码。 | 独立手写oracle对图→源码→正式静态分析的全部节点/参数/ports/producer关系复核。源码文件有明确路径、来源和digest；不靠模板补不存在的内部结构，不覆盖原导入项目。 |
| P0 | 屏幕、保存Canvas和当前SVG/PDF导出共享正式Scene，保留用户的视觉编辑。 | from-zero模型的节点数、连线、参数字幕与实际导出逐项一致；保存后改图再导出不拿旧revision。模型编译/执行状态与图渲染成功分开。 |
| P1 | 常用块分组和有意义的初始参数足够覆盖MLP、CNN、Attention小模型；不只支持5块demo。 | 下表每个已启用条目都有完整registry合同、真实拖入/参数/连线/生成源码/重分析验收；未支持项明确标注，不展示可拖入的空实现。 |
| P1 | 预设区分“模型起始结构”与“论文呈现”，模型预设仍可拆解和编辑。 | 从MLP/CNN等模型预设打开的图，与拖块从零创建消费同一draft/registry/operations；paper/monochrome不会改变图结构或参数。 |
| P1 | 独立使用者只看界面能找到模块、参数与连接，遇错知道如何修。 | 保留AI模拟卡点作工程反馈；另招3–5位真实模型制图使用者做完整任务，记录失败/放弃/时间与工件，不用代理数量代替真人样本。 |

## 模块注册候选

正式静态前端当前有15类atomic constructor合同。它们只是现有解析依据，**不证明已实现任何authoring/generation合同**。候选模块库应逐条新增独立合同与验收，避免把analyzer的只读支持直接宣传为可创建/可修改。

| 分组 | 候选块 | 每个块的最少独立合同 |
|---|---|---|
| 接口 | Input、Output | 稳定接口名、形状/类型声明或显式unknown；输出关联一个明确producer，不把图例当接口。 |
| 全连接 | Linear、Identity | in/out_features、bias与明确单输入输出；Identity保留同一张量合同。 |
| 激活/正则 | ReLU、GELU、SiLU、Dropout | 参数合法范围、inplace/approximate/概率说明；默认无inplace，保留实际创建值，不复用visual glyph作为操作类型。 |
| 卷积/池化 | Conv2d、MaxPool2d、AdaptiveAvgPool2d、Flatten | channels/kernel/stride/padding/output_size/start/end dim参数、形状约束与不确定项；无未经证实的runtime shape主张。 |
| 归一化 | LayerNorm、BatchNorm2d | normalized_shape/num_features/eps/momentum等字段，必要的shape/dtype与train/eval状态边界。 |
| 序列 | Embedding、MultiheadAttention、LSTM | attention明确query/key/value/mask命名端口、weights等多输出合同；LSTM明确output/h_n/c_n。调用与共享实例身份分开。 |
| 组合/后续 | Add、Concat、局部模块封装、repeat/shared | 真实多输入、轴/输出合同、实例/调用份数与封装接口；不把框内包含当新增执行。独立合同完成前标未实现。 |

## 实现边界与复核

新建模型需一个具有类型/参数/端口/绑定合同的 authored draft；其编辑是模型草稿编辑。来自既有Python的Architecture/Canvas继续按source binding消费事实，alias、颜色、排版不改源码。不能在现有source-bound Canvas里直接塞节点并伪造源码位置或digest；也不能为新建模式引入旧runtime回退。

初期可以采用有界DAG与明确的PyTorch构造/forward生成子集，自动生成的新文件通过正式静态前端重分析。注册边界外的结构保留不完整/unsupported，不生成偷偷替换为Identity的网络。执行/训练仍为另一个显式隔离workflow，图形成功不触发模型运行，不声称运行语义或数值等价。

任何authoring构建都需要新版本的browser scope、独立oracle与研究包；本轮旧`Cr_xKW9U`截图/39-case矩阵不能认证新功能。该清单尚无代码变更、测试通过或交付时间承诺。
