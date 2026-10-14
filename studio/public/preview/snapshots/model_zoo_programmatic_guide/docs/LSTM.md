# LSTM：变长序列打包与分类头的源码对应

本适配器对应 `rasbt/deeplearning-models` 的 `pytorch_ipynb/rnn/rnn_lstm_packed_imdb.ipynb`，入口是 `RNN.forward(text, text_length)`。图像范围包括批量评估调用方的 Sigmoid 和阈值，且用独立边框明确区分 `RNN.forward` 与调用方。上游源码只作为文本与 AST 证据，绘图不执行数据下载、torchtext、spaCy 或模型。

[源码副本](../sources/deeplearning-models/pytorch_ipynb/rnn/rnn_lstm_packed_imdb.py) · [原 notebook](../sources/deeplearning-models/pytorch_ipynb/rnn/rnn_lstm_packed_imdb.ipynb) · [适配器](../adapters/lstm.py) · [来源与 cell 映射](../source_manifest.json)

## 所选配置和布局

源码设置 Embedding 宽度 `128`、hidden 宽度 `256`、output 宽度 `1`。构造器只调用 `nn.LSTM(embedding_dim, hidden_dim)`，所以在所用 PyTorch API 的默认契约下是一层、单向、sequence-first 的 LSTM，没有指定初始 hidden/cell，没有内部 dropout。

`text` 是 `[T,B]` 的 token ID 矩阵；`text_length` 是 `[B]` 的有效长度。`B` 与 `T` 是符号化的运行时维度。训练配置 `batch_size=128` 并不保证最后一个 batch 或单句调用也有 128 项。词表矩阵行数是 `V=len(TEXT.vocab)`；`VOCABULARY_SIZE=20000` 用于 `build_vocab(max_size=...)`，不能把它直接当成实际 Embedding 行数，特殊 token 也在实际词表中。

## 图例与源码对应

| 图中结构 | 源码位置 / 参数身份 | 为什么这样对应 |
| --- | --- | --- |
| Padded token IDs | `forward(text, text_length)`；`compute_binary_accuracy` 解包 `batch_data.text` | 真实模型输入是 token IDs，不是已嵌入特征；时间轴在第一维 |
| Embedding `V→128` | `__init__.embedding`，`forward` 的 `self.embedding(text)` | 单张词表权重按 token ID 查表；输出 `[T,B,128]` |
| External sequence lengths | `text_length` 参数；torchtext `Field(include_lengths=True)` | 长度是调用方提供的控制信息，通过侧端口参与打包，不是新学习的 embedding |
| pack_padded_sequence | `forward` 的 `torch.nn.utils.rnn.pack_padded_sequence(embedded, text_length)` | 真实输入 LSTM 的是 PackedSequence；不能画成全部 padding 都参与递推的普通 dense 序列 |
| 单层 LSTM `128→256` | `__init__.rnn`，`forward` 的 `self.rnn(packed)` | 是真实的 `nn.LSTM` 库模块，参数身份属于同一个 `rnn` 实例 |
| Select hidden h_n | `packed_output, (hidden, cell) = ...` 与 `self.fc(hidden.squeeze(0))` | 代码只使用 hidden；packed_output 与 cell 没有进入分类头 |
| Squeeze layer axis | `hidden.squeeze(0)` | hidden `[1,B,256]` 去掉的是 layer/direction 轴，不是时间轴 |
| Linear `256→1` | `__init__.fc`，`forward` 的 `self.fc(...)` | 真实分类层只产生一个 logit，独立参数为 `fc` |
| view(-1) | `return ... .view(-1)` | `[B,1]` 展平为 `[B]`；这是模型 forward 的完整返回值 |
| 调用方 Sigmoid / `p>0.5` | `compute_binary_accuracy` | 概率和二分类标签来自评估函数，不属于模型内部 |

`BucketIterator(sort_within_batch=True)` 的数据准备满足打包默认要求；图中不凭空增加 `enforce_sorted=False`。Packing 后的 `.data` 有 `sum(text_length)` 行，其他 PackedSequence 元数据由 PyTorch 保存；LSTM 返回的 `packed_output` 仍是打包序列。源码注释中的 dense output shape 不能替代这次实际打包调用的返回类型。

## nn.LSTM 内部为什么不展开四个门

当前 notebook 只定义了 LSTM 的构造和调用，**并没有定义 input/forget/output/candidate 四门运算源码**。因此详细图仍把 `nn.LSTM` 画为有明确输入、输出、参数身份与运行时依赖的库模块边界。教材四门图可以作为另一个说明面板，但不能把它伪装成从这份 notebook AST 中提取的节点。

`weight_ih_l0`、`weight_hh_l0`、`bias_ih_l0` 和 `bias_hh_l0` 是 `nn.LSTM` API 的默认参数身份；图中记录了这个库依赖层次。若将来要真正展开内部实现，需要再冻结并取证匹配版本的 PyTorch 源码，同时注明 fused/backend 的实现分支。当前原型没有冻结 PyTorch runtime，所以不宣称展开了内核。

同一个 LSTM 实例在有效时间步上复用同一组递推参数。它不是为每个 token 新建一套权重。该模型没有 bidirectional、堆叠层、attention、sequence mean pooling、将所有 hidden 拼接的 Flatten，也没有 `pad_packed_sequence`。这些结构不能因为“常见 LSTM 架构”而补进图中。

## 顺序、侧输入和颜色如何程序化确定

主链的源码顺序是 Embedding → Packing → LSTM → hidden 选择 → squeeze → Linear → view。适配器按此顺序写 `chain.items`；共享引擎从底向上布置矩形。Embedding、Packing、Recurrent、Classifier 四个主要模块用等宽对齐，长度节点位于侧方，连接 Packing 的 `lengths` 端口。

LSTM 的 hidden/cell/packed_output 是 tuple 结果。图中显式选择 hidden，不能画三个输出相加后进入 FC。接口文字给出未使用字段，分类主链只携带被实际使用的 hidden。

配色沿用 Transformer 的字体、深边框与图例对比：Embedding 粉色、Linear 紫色、主要 feature group 蓝色、Sigmoid 绿色、张量 reshape/选择中性浅色；递推模块拥有独立图例角色。相同颜色编码相同绘图角色，参数共享由 `parameter_scope` 与 `temporal_parameter_sharing` 字段说明。

概览折叠整个模型 forward；模块视图展示四个实际阶段以及单独的调用方评估阶段；详细视图展示 tuple 选择、squeeze、view 等真正出现在源码中的细节。所有视图保持模型边界，Sigmoid 不能随着折叠混进 `RNN.forward` 的真实返回语义。

## Sigmoid、训练损失和单句预测的边界

训练循环直接把模型 logits 交给 `F.binary_cross_entropy_with_logits`，没有先调用 Sigmoid。评估函数为 `torch.sigmoid(logits)>0.5`，Sigmoid 在调用方。`predict_sentiment` 也在调用模型后应用 Sigmoid，但它额外使用 spaCy tokenization、词表 lookup 和单句输入组装；它与所选 batch evaluation 路径不同，当前图没有把两种调用方混为一个执行路径。

源码副本、逐 cell/逐行映射、AST 符号证据用于追溯；模型配置和上游 API 默认值通过审阅记录。图像是明确范围的静态结构说明，不验证原 notebook 在当前环境的 torchtext/spaCy 兼容性，也没有执行该 notebook。
