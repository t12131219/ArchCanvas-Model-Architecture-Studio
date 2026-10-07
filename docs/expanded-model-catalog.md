# 模型搭建模块库扩展

本次开发将正式模块库从 17 个原子扩为 **74 个原子、13 个分类**，将网络起点从 3 个扩为 **23 个透明图块**。这是当前源码中的功能，已冻结的 Beta.2 发布包不因这次开发自动改变。

所有公开部件均有实际参数表、端口、静态形状检查、Python 生成和生成后独立 AST 重分析。没有用禁用卡片充当新增功能。DL-Playground 只提供模块类别与发现方式参考，没有采用其实现，也没有导入旧工程 runtime。

| 分类 | 数量 | 覆盖范围 |
| --- | ---: | --- |
| 输入与输出 | 2 | 显式 shape / dtype 输入、命名输出 |
| 全连接 | 1 | Linear / FC |
| 激活 | 16 | ReLU、GELU、SiLU、Sigmoid、Tanh、ReLU6、LeakyReLU、ELU、SELU、Softplus、Softsign、Hardsigmoid、Hardswish、PReLU、Softmax、LogSoftmax |
| 基础算子 | 4 | Identity、MatMul、Mean、Sum |
| 随机失活 | 6 | Dropout、1d/2d/3d、AlphaDropout、FeatureAlphaDropout |
| 形状变换 | 8 | Flatten、Unflatten、Reshape、Transpose、Permute、Unsqueeze、Squeeze、Upsample |
| 卷积 | 6 | Conv1d/2d/3d、ConvTranspose1d/2d/3d；包括分组、深度和逐点配置 |
| 池化 | 12 | 1d/2d/3d 的 MaxPool、AvgPool、AdaptiveMaxPool、AdaptiveAvgPool |
| 归一化 | 9 | 1d/2d/3d 的 BatchNorm 与 InstanceNorm、LayerNorm、RMSNorm、GroupNorm |
| 嵌入 | 1 | Embedding |
| 合并与分支 | 5 | Add、Subtract、Multiply、Divide、Concat |
| 循环与序列 | 3 | RNN、GRU、LSTM |
| 注意力 | 1 | MultiheadAttention |

23 个起点：最小 MLP、小型 CNN、残差 MLP、Transformer 前馈层、一维时序 CNN、三维体数据 CNN、卷积归一化激活、深度可分离卷积、卷积瓶颈、词嵌入与前馈、GRU 序列分类、LSTM 序列分类、双向 RNN、卷积上采样解码、全连接自编码器、图像 Patch 嵌入、自注意力、卷积残差块、门控 MLP、跨注意力、U-Net 单级跳连、带投影残差块、Transformer 编码器块。每个组合的组成、输入与输出都公开，插入后仍是可编辑、可连线的普通节点，整体插入只占一次撤销历史。U-Net、MobileNet 风格图块和 Transformer 块只是声明的具体组成，不冒充完整标准模型。

搜索基于活跃 runtime 的模块和实际起点组成。FC、Swish、GAP、LN、GN、MHA 等精确别名映射到真实模块；完整 `nn.Tanh`、`AvgPool2d`、`Squeeze` 等名字采用精确查询，不会误匹配其他模块的说明或子串。

## 静态边界

输入尺寸与类型是用户声明，静态成功不证明实际数据、显存、数值或训练效果；生成流程不导入或执行用户模型。带参数模块显式生成 float32 参数，接受匹配的 float32 输入；无参数浮点算子支持 float32 / float64。Embedding 仅接受 int64 索引，实际索引上下界需要数据验证。

RNN / GRU / LSTM 目前支持批次三维序列、默认零初态与可选双向多层配置，真实输出端口为 `output`、`h_n`，LSTM 还有 `c_n`。不能将三者压成一个张量；`portTensors` 提供每条输出的声明尺寸。单层循环模块的层间 dropout 必须为 0，PackedSequence、显式初态和 LSTM 投影尚未提供。

MultiheadAttention 提供 `query` / `key` / `value` 输入及 `output` / `weights` 输出。默认真实返回按头平均权重，检查 Q/K/V 特征宽度、批次、K/V 长度与头数整除关系；自注意力三路同源，跨注意力 K/V 的 IR 角色保留 memory。掩码、KV 缓存、独立 kdim/vdim 与因果模式尚未提供。

张量合并采用完全相同形状与类型，Concat 仅允许拼接轴不同；MatMul 支持二维及批次矩阵，批次轴严格一致，不承诺隐式广播。Reshape 最多允许一个 -1，生成时根据声明尺寸显式推导；Transpose / Permute / Squeeze / Unsqueeze 和约简检查轴与元素数。合法约简和 Squeeze 可产生零维标量。ConvTranspose 检查 output_padding；池化正确排除 ceil_mode 中起点落入右侧填充的窗口。RMSNorm 需要包含该 API 的 PyTorch 版本；调研及合同采用版本固定的 PyTorch 2.9 文档。

训练损失、优化器、动态控制流、数据加载与自定义 Python 执行没有被新增为可生成模块。保存不完整草稿仍可用；生成要求所有输入已连接、无环，且每个节点最终参与命名输出。

## 来源与许可证

检索日期为 **2026-10-07（Asia/Shanghai）**。实际联网收据和快照见 [network-receipt.json](evidence/catalog-research-v1/network-receipt.json)。

- [DL-Playground](https://github.com/dsgiitr/DL-Playground)，本地 checkout `c07a79b60bcb67be0bec2276002bd21f92a616de` 的 README、`frontend/src/nodes/registry.ts`：参照公开功能类别；本地 Git 跟踪文件没有 LICENSE，**没有复制代码或资源**。网络取得公共仓库页面并保存摘要。
- [PyTorch 2.9 nn](https://pytorch.org/docs/2.9/nn.html)、[functional](https://pytorch.org/docs/2.9/nn.functional.html)：实际取得完整文档页面。新版 docs.pytorch.org 请求返回 403；pytorch.org 的 stable 地址只返回跳转页面，收据明确记录，未将其当作已读 API 内容。
- [PyTorch v2.9.0 官方源码文档](https://github.com/pytorch/pytorch/tree/v2.9.0/torch/nn/modules)：取得 activation、rnn、conv、pooling、normalization、transformer 和 functional 源码中的 API 文档，核对参数和形状；只依据公开 API 独立实现合同。官方 LICENSE 快照包含 BSD 风格授权及第三方声明。
- [torchvision ResNet](https://github.com/pytorch/vision/blob/main/torchvision/models/resnet.py) 与 [MobileNet V2](https://github.com/pytorch/vision/blob/main/torchvision/models/mobilenetv2.py)：核对残差投影、瓶颈与深度/逐点卷积结构。仓库 BSD 3-Clause LICENSE 已保存，没有移植模型代码。main 地址是调研时快照，不声明固定版本。

原 M4 fixture 和历史证据没有改写。Conv1d 与 ConvTranspose2d 获得新的公开合同后，当前 holdout 测试明确验证这些新增支持；仍未知的反例使用独立 `holdout_catalog_boundaries` 中真实但尚未注册的 `nn.LocalResponseNorm`。M4 真人与性能认证状态不因模块库扩展改变。

## 验证

[tests/test_authoring_catalog_expanded.py](../tests/test_authoring_catalog_expanded.py) 为全部 74 原子实际生成并重分析，另有独立手算卷积/转置卷积/池化/形状变换、双向循环末态、跨注意力权重、次输出接入下游与损坏端口/参数拒绝案例。

[studio/tests/authoring-presets.test.ts](../studio/tests/authoring-presets.test.ts) 将全部 23 起点通过真实插入函数生成草稿、保持稳定身份与一次撤销，并交给正式 backend 验证完整源码及每个声明输出。搜索测试验证现有目录、类别、实际组成和误匹配边界。最终运行证据见 [catalog-contract-receipt.json](evidence/catalog-research-v1/catalog-contract-receipt.json)。
