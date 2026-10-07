# 17 模块库与新手搭建的只读评估

当前代码有 17 个可点击或拖入的原子模块，分为 11 类：Input、Output、Linear、ReLU、GELU、SiLU、Identity、Dropout、Flatten、Conv2d、MaxPool2d、AdaptiveAvgPool2d、BatchNorm2d、LayerNorm、Embedding、Add、Concat。中英文名称检索、空白画布指引、输入/输出端口拖连或点连、参数编辑、按连接排版、撤销、保存/重开及生成新模型/论文图路径均有代码证据。本次没有操作 palette 浏览器，也未让 AI 充当真人新手。

用户希望“像 DL-Playground 的尽量多的常用预制模块”，当前只能确认上述原子库。代码明确尚不支持 Sigmoid、Tanh、Conv1d、AvgPool2d、BatchNorm1d、MultiheadAttention、LSTM；搜索无结果提示还说明没有组合网络预制。扩充必须先获得参数/形状/source/IR 契约与独立正确性证据，不能只加卡片。

新手缺口主要是：没有可直接拖入的 MLP/卷积块/残差块等组合起点；端口/连线缺少即时展示的声明张量 shape/dtype；大部分参数仍用英文名，只有 Linear 有专门形状示例；首次搭建有文字步骤，但缺少可跟随的小模型进度指导。这些是只读评估后的建议，非当前已实现能力或真人可用性评分。

精确目录、字段默认值、代码 SHA-256 与范围见 palette-novice-readonly-review.json。
