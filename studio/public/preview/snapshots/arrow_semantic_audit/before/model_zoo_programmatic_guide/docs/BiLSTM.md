# BiLSTM：两层双向、最后层状态与真实分类头

本适配器对应固定 `rasbt/deeplearning-models` 提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3` 的 `pytorch_ipynb/rnn/rnn_bi_multilayer_lstm_own_csv_agnews.ipynb`。模型入口是 `RNN.forward(text, text_length)`。图像选择 `compute_accuracy` 中一个 batch 的预测片段，采用 `model.eval()`；最后的 `[B]` 类标签用于函数随后进行准确率累积，图不包含其最终返回的准确率百分比。

[原 Notebook](../sources/deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_bi_multilayer_lstm_own_csv_agnews.ipynb) · [派生 Python](../sources/deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_bi_multilayer_lstm_own_csv_agnews.py) · [适配器](../adapters/bilstm.py) · [固定来源与 cell 映射](../source_manifest.json)

原 cell 5 设置配置，cell 21 定义 Field，cell 27 构建词表，cell 31 设置 BucketIterator；cell 35 定义模型类，cell 36 实例化，cell 38 批量评估，cell 39 训练 loop，cell 42 单句预测。cell 索引从 0 起；每个派生源码片段保留原 cell/行映射。绘图只读源码文本和 AST，不运行 AGNews CSV、torchtext、spaCy 或模型。

## 固定配置和 shape

`EMBEDDING_DIM=128`、`HIDDEN_DIM=256`、`NUM_LAYERS=2`、`BIDIRECTIONAL=True`、`OUTPUT_DIM=4`、`DROPOUT=.5`。模型读取新闻 `content` 字段；`text:[T,B]` 与 `text_length:[B]` 来自 `batch_data.content`。序列优先布局由默认 `batch_first=False` 决定。V 为实际 `len(TEXT.vocab)`，`max_size=5000` 仅是构建设置，B 和 T 仍保留运行时符号。

主要形状如下：

| 操作 | 输出 |
| --- | --- |
| Embedding / 外部 Dropout | `[T,B,128]` |
| pack_padded_sequence | PackedSequence，有效数据 `[sum(lengths),128]` |
| 两层双向 LSTM | `packed_output, (h_n,c_n)`；两种状态均为 `[4,B,256]` |
| `hidden[-2,:,:]` / `hidden[-1,:,:]` | 各 `[B,256]` |
| 按特征轴 Concat / 外部 Dropout | `[B,512]` |
| Linear1 / 外部 Dropout | `[B,64]` |
| Linear2 / forward 返回 | `[B,4]` logits |
| caller `torch.max(logits,1)` 的 indices | `[B]` 类标签 |

`sort_within_batch=True` 与 `sort_key=lambda x:len(x.content)` 给打包提供按内容长度排列的 batch。打包调用没有传 `enforce_sorted=False`、`batch_first=True` 或额外 `.cpu()`。保留原代码契约，不把可能的旧版库兼容问题伪装成已修复执行路径。

## 为什么只画最后层的两个方向

PyTorch 双向 LSTM 的 h_n 第一轴依次为 layer0-forward、layer0-reverse、layer1-forward、layer1-reverse。所以 `hidden[-2,:,:]` 和 `hidden[-1,:,:]` 是**最后一层的 forward 与 reverse 最终 hidden**。第二个不是“整段序列最后 token 的逆向输出”；h_n 与 dense output 最后位置的含义不同。

图在 `Select hidden h_n` 之后设置并列的两个有类型 operand，各自读取同一个 hidden 生产者并执行真实索引切片。`torch.cat((..., ...), dim=1)` 按 forward 然后 reverse 的顺序收集它们，特征宽度为 `256+256=512`。这里是实际的切片 tuple/Concat，不是方向相加，也不是将所有四个 layer-direction 状态 flatten 成 1024。

`packed_output` 与 `cell` 都没有参与分类；`pad_packed_sequence` 只出现在注释中，不应画成执行节点。两层和两个方向的内部递推归于一个实际 `self.rnn` 库模块；Notebook 没有定义四门实现，也没有独立构造四个 `nn.LSTM`。详细图不会把内部方向标识误画成四个源码类实例。

## fc1 的源码表达式不能悄悄改写

源码确实构造：

```python
self.fc1 = nn.Linear(hidden_dim * num_layers, 64)
# ... forward ...
hidden = self.dropout(torch.cat((hidden[-2,:,:], hidden[-1,:,:]), dim=1))
hidden = self.fc1(hidden)
hidden = self.dropout(hidden)
hidden = self.fc2(hidden)
return hidden
```

这份 profile 中 `hidden_dim*num_layers=256*2=512`，恰好等于两个方向的 Concat 宽度。两个公式的语义不同：Concat 宽度来自两个方向，源码 Linear 输入宽度写成了层数。不能据此声称只改 `NUM_LAYERS` 就仍然正确，也不能把图中证据写成源码实际用了 `hidden_dim*2` 或 `hidden_dim*num_directions`。适配器同时保存真实表达式和固定数值，并说明这一限制。

fc1 与 fc2 之间只有 Dropout，**没有 ReLU、Tanh 或其他激活**。eval 下 Dropout 为恒等运算，所以这两层是连续 affine 映射；图仍保留两个独立 Linear 参数身份，不擅自合并源码节点。forward 没有 Softmax。

## Dropout：一个外部实例、三次调用与内部层间机制

`self.dropout=nn.Dropout(.5)` 被三个位置调用：Embedding 后、hidden Concat 后、fc1 后。三张图记录三个调用节点与相同 `instance_identity=self.dropout`，因为执行位置不同，不能只画一次。Dropout 没有学习参数，相同实例也不代表训练中共享同一随机 mask；每次调用产生自己的随机丢弃。

此外 `nn.LSTM(..., dropout=.5)` 在训练时应用层间 dropout，位于 layer0 输出进入 layer1 的库内部路径。这是库参数，不是 Notebook 定义的一个门，也不等于对最终 h_n 再作一次外部 Dropout。当前 caller 先 `model.eval()`，这两类 dropout 都不启用；模块仍保留在图中，IR 的 `active=False` 与说明注明模式。训练 loop 的 `model.train()` 会启用它们，这是另一种执行模式，未混入当前 eval 架构。

## 参数身份、GloVe 与调用方边界

LSTM 有四个独立 layer-direction 参数族，每族包括 `weight_ih`、`weight_hh`、`bias_ih` 和 `bias_hh`，共 16 个 API 参数 tensor。`_l0` 与 `_l1` 表示层，`_reverse` 表示逆向族。第一层的 input-weight 宽度为 128；第二层接收下层两个方向拼接，宽度为 512；每族 hidden-weight 宽度为 256。每一族随有效时间步复用参数，层间/方向间不共享。参数名和 shape 来自 `nn.LSTM` API 契约，内部 gate 运算仍是未冻结的库边界。

`TEXT.build_vocab(..., vectors='glove.6B.100d')` 给词表保存 100 维向量，但源码从未把 `TEXT.vocab.vectors` 复制到模型 128 维的 Embedding。图中的 Embedding 使用构造器默认初始化，并传入真实 `padding_idx=PAD_IDX`。不能仅因为词表构建提到 GloVe，就画“GloVe100→projection128”或预训练 Embedding。

批量 `compute_accuracy` 直接取 `torch.max(logits,1)` 的索引，没有 Softmax；训练使用外部 `cross_entropy`。`predict_class` 在单句路径中另行应用 Softmax，再取最大概率和类别，同时添加最短长度 padding。这是不同 caller，未并入所选 batch 图。

## 程序化排布与核验

源码先后依赖决定自底向上的主链：Embedding/Dropout → Packing → LSTM/h_n → 两个最后层方向切片 → Concat/Dropout → 两层 Linear/Dropout → logits → caller max。切片并列表示两个 operand，没有执行时间先后关系；左右顺序保留 source tuple 的 forward、reverse 顺序。模块等宽对齐，长度侧端口进入 Packing；层次、间距和箭头由共享布局引擎测量和路由。

源码注册的模型属性是 `embedding`、`rnn`、`fc1`、`fc2` 与 `dropout`。Packing、Last-layer Concat、Classifier 等阶段边框是适配器对同一 forward 中相邻语句的说明分组，源码没有额外的阶段类或 Sequential；折叠不新增参数或计算。

概览折叠 forward 与 caller；模块视图显示五个真实阶段；详细视图展开两方向切片、Concat 和各 Dropout/Linear 调用。橙色标识递推库边界、黄色标识 Concat、紫色标识 Linear、粉色标识输入/Embedding，沿用 Transformer 字体、深边框与颜色对比。不同节点配色不用于推断参数是否共享。

适配器 `validate_ir()` 核验 last-layer 索引、ordered Concat、16 个参数身份、Dropout 实例/调用数和 eval 状态、fc1 原始表达式、Embedding 来源、Packing 长度依赖、caller 边界。固定源码哈希、AST/Notebook provenance 与布局检查是另外的验证层；当前工作没有执行模型，也没有验证旧 Notebook 在当前 Python/torchtext/spaCy 环境中的运行结果。
