# 正式搭建模块库与 DL-Playground 行为对标

正式 `module_catalog()` 当前有17个条目、11类；包括Input/Output两个界面节点和15个计算/变换模块。AuthoringStudio左侧已提供分类、中文/英文搜索、点击添加和拖入画布；接口/源码静态检查不是新浏览器使用记录。小白已经可以全靠视图搭建受支持的无环网络，尚需自己组合基础层和连接，没有可直接插入的MLP/CNN/残差组合预制。

| 正式分类 | 当前条目 |
| --- | --- |
| 输入与输出 | Input、Output |
| 全连接 | Linear |
| 激活函数 | ReLU、GELU、SiLU |
| 基础算子 | Identity |
| 正则化 | Dropout |
| 形状变换 | Flatten |
| 卷积 | Conv2d |
| 池化 | MaxPool2d、AdaptiveAvgPool2d |
| 归一化 | BatchNorm2d、LayerNorm |
| 嵌入 | Embedding |
| 合并与分支 | Add、Concat |

当前明确unsupported列表包括Sigmoid、Tanh、Conv1d、AvgPool2d、BatchNorm1d、MultiheadAttention、LSTM；列表不是全量缺失枚举。任意Python、动态形状、共享实例、普通计算环、隐式Add广播、三路以上Concat、组合网络预制和自动训练也没有支持。静态分析器能识别某模块不代表作者ing端已有构造/shape/source round-trip契约。

本地DL-Playground的 `frontend/src/nodes/registry.ts` 声明14个palette groups、80个group entries；其中 `repeat_layer` 在Torch Ops与Control Flow重复，只有79个不同group key，另有module_ref专用注册。这只是读到的目录声明，不是80个正确生成/运行模块的证据，也不是ArchCanvas覆盖率分母。Losses/metrics/control/创建随机tensor等部分超出当前制图与安全建模的首期范围。

| 使用者会感到的覆盖差异 | 本地DL-Playground目录/侧栏证据 | 正式当前范围和建议 |
| --- | --- | --- |
| 基础层数量 | 13种activation菜单项，更多tensor操作/reshape/transpose/normalization | 正式3种activation及有限shape操作；后续可优先Sigmoid、Tanh、LeakyReLU、Softmax/LogSoftmax、Reshape、Transpose，每项独立合同和反例，不只加按钮。 |
| 卷积、池化、分割网络 | Conv1d/3d/transpose2d/Upsample、1d/3d/Avg/AdaptiveMax/Global pooling | 正式Conv2d + MaxPool2d/AdaptiveAvgPool2d；group/dilation已存在，可组合depthwise/pointwise参数，但没有专用预制卡。优先补AvgPool2d/Conv1d，再逐项Upsample/ConvTranspose2d及对应边界。 |
| NLP/序列 | Embedding、RNN、LSTM、GRU、MultiheadAttention、PositionalEncoding | 正式Embedding/LayerNorm可用；Attention/sequence需要多输入/多输出/返回tuple、mask/不同Q/K长度的独立合同，不能借参考项目存在类名就直接启用。 |
| 组合网络和可复用模块 | ResidualBlock菜单、ModuleList/RepeatLayer、SavedModule搜索与拖入/module editor | 正式没有组合预制、模块封装、模块编辑栈。先用已支持层提供透明展开的有限MLP/CNN/Residual presets，后续独立设计versioned reusable subgraph/ports/参数映射。 |
| 训练 | Losses、Accuracy、runner/worker接口 | 正式生成/注册仅静态核对，不执行训练；不为扩大palette而自动加入执行路径。 |

参考计划书§2.3已经指出其shape verifier端口传播、cross-attention shape、首输入tracing和stub GraphModel问题，并说明项目自身许可证未确认。因此这里只借鉴可见行为/模块分类，不复制代码、不采用失败原型、不把参考项目自测或worker成功当正式独立证据。

最实用的下一产品改动是 **左侧增加经过独立验证的组合预制**，使用现有17模块即可降低新手接线负担，且不会扩大生成语义子集：

1. MLP分类：Input `[1,16]` → Linear16→32 → ReLU → Linear32→8 → Output，显式float32与输出维度。
2. 小型CNN：Input `[1,3,32,32]` → Conv2d3→16/k3/pad1 → BatchNorm2d16 → ReLU → MaxPool2d2 → AdaptiveAvgPool2d1×1 → Flatten → Linear16→10 → Output。
3. 残差MLP：Input `[1,16]` 分支到两个Linear16→16的主链和Add跳接，保持同shape；把每个模块与真实连线完整展开供修改，禁止用一个无法生成的新“Residual”图标代替。

预制插入应创建新stable IDs、明确输入声明/参数、在一次草稿历史命令内加入整组nodes/edges并适合画布；可预览后插入，用户能撤销一次恢复原草稿。对手算张量shape、生成AST/IR全部端口/producer-consumer与保存重开进行独立检查，并由真实新手从空白完成任务。模板是作者ing草稿对象，不向已有source-bound CanvasDocument塞伪造模型节点，也不自动执行模型。

其次逐批扩基础模块，优先易于定义语义但当前缺失的activation/shape/pooling，再做有界Attention/序列。每批沿用参数/typed ports/静态tensor推导/独立source round-trip/中文诊断，与新手任务和出版图一起验收。上述全部是建议，当前没有启用这些功能。
