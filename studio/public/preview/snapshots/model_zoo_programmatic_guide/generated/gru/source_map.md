# GRU (packed IMDb classifier)：源码与图框对应

来源：`https://github.com/rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_gru_packed_imdb.py](sources/deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_gru_packed_imdb.py) · `RNN` | 76–97 | [17] |
| E002 | [deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_gru_packed_imdb.py](sources/deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_gru_packed_imdb.py) · `RNN.__init__` | 77–83 | [17] |
| E003 | [deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_gru_packed_imdb.py](sources/deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_gru_packed_imdb.py) · `RNN.forward` | 85–97 | [17] |
| E004 | [deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_gru_packed_imdb.py](sources/deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_gru_packed_imdb.py) · `compute_binary_accuracy` | 108–118 | [20] |
| E005 | [deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_gru_packed_imdb.py](sources/deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_gru_packed_imdb.py) · `predict_sentiment` | 160–172 | [22] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| gru.root | Packed GRU: IMDb sentiment | per-batch labels: [B] | E003,E004 | — |
| gru.input | Padded token IDs | text: [T,B] | E003,E004 | — |
| gru.forward | RNN.forward: packed GRU classifier | logits: [B] | E003 | — |
| gru.embedding | Token embedding | [T,B,128] | E002,E003 | — |
| gru.lookup | Embedding V -> 128 | [T,B,128] | E002,E003 | embedding.weight |
| gru.packing | Pack valid time steps | PackedSequence | E003 | — |
| gru.pack | pack_padded_sequence | PackedSequence | E003 | — |
| gru.recurrent | Single-layer GRU | [B,256] | E002,E003 | rnn |
| gru.core | nn.GRU 128 -> 256 | (packed_output,h_n) | E002,E003 | rnn |
| gru.select_hidden | Select hidden h_n | [1,B,256] | E003 | — |
| gru.squeeze | Squeeze layer axis 0 | [B,256] | E003 | — |
| gru.classifier | Binary logit head | logits: [B] | E002,E003 | — |
| gru.fc | Linear 256 -> 1 | [B,1] | E002,E003 | fc |
| gru.flatten | view(-1) | logits: [B] | E003 | — |
| gru.caller | Caller: per-batch binary decisions | binary labels: [B] | E004 | — |
| gru.sigmoid | Sigmoid | p(positive): [B] | E004 | — |
| gru.threshold | Threshold p > 0.5 | labels: [B] | E004 | — |
| gru.lengths | External sequence lengths | text_length: [B] | E003,E004 | — |

## 与教科书/通用基础图的区别

- Do not substitute an LSTM tuple or add a cell state, bidirectional branch, stacked layer, or dropout.
- Do not replace packing/final hidden with dense padding, last padded output, mean pooling, or pad_packed_sequence.
- Do not put Sigmoid inside RNN.forward or claim vocabulary_max_size is the realized embedding row count.
- Reset/update gates are not source-extracted operators; the real nn.GRU runtime boundary remains explicit.

## 源码事实与边界

- The selected constructor is Embedding(V,128), GRU(128,256), Linear(256,1); V is len(TEXT.vocab).
- The API defaults used by the source are one layer, unidirectional, sequence-first, bias=True and dropout=0.
- Field(include_lengths=True) and BucketIterator(sort_within_batch=True) supply valid lengths and sorted batches.
- pack_padded_sequence omits batch_first and enforce_sorted arguments; do not silently change their defaults.
- GRU returns (packed_output,hidden), without an LSTM cell; only hidden.squeeze(0) enters the classifier.
- RNN.forward returns fc(...).view(-1), a [B] logit vector; the caller applies sigmoid and threshold.
- The diagram ends at per-batch predictions inside compute_binary_accuracy, not the function's accumulated accuracy percentage.
- Training uses binary_cross_entropy_with_logits outside forward; predict_sentiment is a separate single-sentence caller.
- The same recurrent instance reuses weights across time; gate implementation is external PyTorch code, not notebook AST.
- Old torchtext/spaCy and length-device compatibility are not tested: source and model are never executed.
