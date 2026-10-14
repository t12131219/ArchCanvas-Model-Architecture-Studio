# Packed GRU：有效时间步、最终 hidden 与调用方二分类

本适配器取证固定 `rasbt/deeplearning-models` 提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3` 的 `pytorch_ipynb/rnn/rnn_gru_packed_imdb.ipynb`。模型入口为 `RNN.forward(text, text_length)`；图像选择 `compute_binary_accuracy` 中的一个 batch 预测片段，模式为 `eval`。图中最终标签是这个函数的中间结果，其最终累积正确数量与返回准确率百分比不在图内。

[原 Notebook](../sources/deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_gru_packed_imdb.ipynb) · [派生 Python](../sources/deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_gru_packed_imdb.py) · [适配器](../adapters/gru.py) · [固定来源与 cell 映射](../source_manifest.json)

配置位于原 Notebook cell 5；数据 Field、词表、BucketIterator 分别位于 cell 8、10、13；模型类在 cell 17，构造实例在 cell 18，批量评估函数在 cell 20，训练 loop 在 cell 21，单句预测函数在 cell 22。以上索引均从 0 起。派生 Python 的 AST 行号与原 cell/行有独立映射，绘图不执行该 Notebook、torchtext、spaCy、数据下载或模型。

## 固定 profile 与接口

词嵌入宽度为 128，GRU hidden 宽度为 256，输出宽度为 1。源码 `nn.GRU(embedding_dim, hidden_dim)` 没有显式提供 `num_layers`、`bidirectional`、`batch_first`、`bias` 或 `dropout`，对应所用 API 默认契约：一层、单向、sequence-first、有 bias、dropout 为 0。没有初始 hidden 输入，库使用默认零状态。没有额外 `nn.Dropout`。

`text` 是 `[T,B]` token IDs，Embedding 输出 `[T,B,128]`。词表行数为实际 `V=len(TEXT.vocab)`；`max_size=20000` 是词表构建限额，不是可直接替代 V 的确定数值。`batch_size=128` 是 loader 设置，最后一个 batch 或单句输入不一定有 128 个样本。Embedding 未传入 `padding_idx`，也没有预训练权重复制。

## 图例的源码对应

| 图中节点 | 源码事实 | 对应原因 |
| --- | --- | --- |
| Padded token IDs | `forward(text, text_length)`；caller 解包 `batch_data.text` | 模型接收 IDs 与有效长度两个输入，长度不能当作学习特征 |
| Embedding `V→128` | `self.embedding = nn.Embedding(...)` 和 `self.embedding(text)` | 单张 `embedding.weight` 查表得到 sequence-first 特征 |
| External sequence lengths | `Field(include_lengths=True)`；caller 的 `text_lengths` | 作为 Packing 的独立侧输入，形状 `[B]` |
| pack_padded_sequence | `pack_padded_sequence(embedded, text_length)` | 真正输入 GRU 的是 PackedSequence，不是仍含 padding 的 dense 序列 |
| 单层 GRU | `self.rnn = nn.GRU(...)`；`self.rnn(packed)` | 一个真实库模块实例，不是 Notebook 定义的一组 reset/update gate 运算 |
| Select hidden | `packed_output, hidden = ...` | GRU 返回没有 cell 的二元 tuple；分类仅使用 hidden |
| Squeeze layer axis | `hidden.squeeze(0)` | 将 `[1,B,256]` 变为 `[B,256]`，去掉层/方向轴而非时间轴 |
| Linear `256→1` / view | `self.fc(...).view(-1)` | forward 的完整结果是 `[B]` logits，不是概率 |
| Caller Sigmoid / threshold | `(torch.sigmoid(logits) > 0.5).long()` | 图中另一个边框表达批量评估调用方，使用严格大于 0.5 |

`BucketIterator(sort_within_batch=True)` 满足默认打包的排序要求。源码省略 `batch_first` 和 `enforce_sorted`，图中保留 sequence-first 与默认 `enforce_sorted=True`，不自行改写为 False。长度张量交给打包时没有额外 `.cpu()`，兼容性取决于旧 Notebook 和库版本；静态绘图不声称已经验证当前环境可执行。

PackedSequence 的有效值矩阵有 `sum(text_length)` 行。GRU 的 `packed_output` 仍然是打包序列；源码注释中的 dense `[T,B,H]` 形状不能当作此次调用的实际返回类型。该输出未进入分类头，代码没有 unpack、取最后 padded 时间步、mean pooling 或 attention。

## 参数共享与库边界

`rnn.weight_ih_l0`、`rnn.weight_hh_l0`、`rnn.bias_ih_l0` 和 `rnn.bias_hh_l0` 属于一个 GRU 实例，是 PyTorch API 参数契约。该实例在有效时间步上复用权重，并非每个 token 建立一个 GRU。没有层间或方向间的额外参数族。

源 Notebook 没有提供 reset/update gate 的实现，也没有冻结 PyTorch 内核源码，所以详细视图保留 `nn.GRU` 的库边界。门级图若另行教学绘制，需要明确为教材说明；不能说它是从这份 Notebook 提取的源码节点。

## 程序化顺序与三种粒度

适配器依照真实调用顺序组织 `chain.items`：Embedding → Packing → GRU → hidden 选择 → squeeze → Linear → view。共享引擎将链从底向上排布；长度节点放在主链侧方，箭头接入 Packing 的 `lengths` 端口。不同模块采用 Transformer 的深边框、字体与粉/橙/蓝/紫/绿颜色对比，颜色表达绘图角色，参数身份由 IR 字段明确给出。

源码实际注册的模型属性是 `embedding`、`rnn` 和 `fc`。Packing、Recurrent 阶段框与 Binary logit head 是围绕相关调用建立的可折叠说明分组，并非额外 `nn.Sequential` 或新参数实例；每个组内节点仍绑定真实函数片段。

概览折叠 `RNN.forward` 和 caller 边框；模块视图显示 Embedding、Packing、Recurrent、Classifier 四个阶段；详细视图展开上述源码实际操作。内部与主流程均自底向上。Sigmoid 始终留在 caller 边框中，折叠不会改变模型的返回语义。

训练 loop 使用 `binary_cross_entropy_with_logits(logits, labels)`，loss、backward 和优化器不在当前架构范围。单句 `predict_sentiment` 也在模型之外使用 Sigmoid，但包含另一套 tokenization、词表查找和输入组装，未混入所选 batch caller。

`validate_ir()` 独立检查 GRU 返回 tuple、参数族、Packing 默认值和长度依赖、hidden 选择，以及 caller 边界；结合固定哈希、AST、Notebook cell 与布局验证使用。通过这些静态检查不代表完成了模型运行或数值等价测试。
