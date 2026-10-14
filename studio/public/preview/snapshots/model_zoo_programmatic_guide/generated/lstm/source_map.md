# LSTM (packed IMDB classifier)：源码与图框对应

来源：`rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [deeplearning-models/pytorch_ipynb/rnn/rnn_lstm_packed_imdb.py](sources/deeplearning-models/pytorch_ipynb/rnn/rnn_lstm_packed_imdb.py) · `RNN` | 76–97 | [17] |
| E002 | [deeplearning-models/pytorch_ipynb/rnn/rnn_lstm_packed_imdb.py](sources/deeplearning-models/pytorch_ipynb/rnn/rnn_lstm_packed_imdb.py) · `RNN.__init__` | 77–83 | [17] |
| E003 | [deeplearning-models/pytorch_ipynb/rnn/rnn_lstm_packed_imdb.py](sources/deeplearning-models/pytorch_ipynb/rnn/rnn_lstm_packed_imdb.py) · `RNN.forward` | 85–97 | [17] |
| E004 | [deeplearning-models/pytorch_ipynb/rnn/rnn_lstm_packed_imdb.py](sources/deeplearning-models/pytorch_ipynb/rnn/rnn_lstm_packed_imdb.py) · `compute_binary_accuracy` | 108–118 | [20] |
| E005 | [deeplearning-models/pytorch_ipynb/rnn/rnn_lstm_packed_imdb.py](sources/deeplearning-models/pytorch_ipynb/rnn/rnn_lstm_packed_imdb.py) · `predict_sentiment` | 160–172 | [22] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| lstm.root | Packed LSTM: IMDB sentiment | binary labels: [B] | E003,E004 | — |
| lstm.input | Padded token IDs | text: [T,B] | E003,E004 | — |
| lstm.forward | RNN.forward: packed LSTM classifier | logits: [B] | E003 | — |
| lstm.embedding | Token embedding | [T,B,128] | E002,E003 | embedding |
| lstm.lookup | Embedding V -> 128 | [T,B,128] | E002,E003 | embedding.weight |
| lstm.packing | Pack valid time steps | PackedSequence | E003 | — |
| lstm.pack | pack_padded_sequence | PackedSequence; data [sum(lengths),128] | E003 | — |
| lstm.recurrent | Single-layer LSTM | [B,256] | E002,E003 | rnn |
| lstm.core | nn.LSTM 128 -> 256 | (packed_output, (h_n,c_n)) | E002,E003 | rnn |
| lstm.select_hidden | Select hidden h_n | [1,B,256] | E003 | — |
| lstm.squeeze | Squeeze layer axis 0 | [B,256] | E003 | — |
| lstm.classifier | Binary logit head | logits: [B] | E002,E003 | fc |
| lstm.fc | Linear 256 -> 1 | [B,1] | E002,E003 | fc |
| lstm.flatten | view(-1) | logits: [B] | E003 | — |
| lstm.caller | Caller: binary accuracy decision | binary labels: [B] | E004 | — |
| lstm.sigmoid | Sigmoid | p(positive): [B] | E004 | — |
| lstm.threshold | Threshold p > 0.5 | predicted labels: [B] | E004 | — |
| lstm.lengths | External sequence lengths | text_length: [B] | E003,E004 | — |

## 与教科书/通用基础图的区别

- A generic LSTM figure cannot replace the actual pack_padded_sequence call with a dense padded sequence or averaging head.
- The head consumes the final hidden state; this source does not unpack/concatenate all time outputs.
- No bidirectional, stacked LSTM, attention, or dropout module is added to this selected constructor.
- The common four-gate textbook drawing is not presented as extracted notebook code; the nn.LSTM boundary remains explicit.
- Sigmoid is shown above the model boundary as caller evaluation; model.forward returns logits.
- The vocabulary row count remains V rather than asserting max_size is exactly the realized len(TEXT.vocab).

## 源码事实与边界

- The notebook constructor is nn.Embedding(input_dim,128), nn.LSTM(128,256), nn.Linear(256,1).
- The recurrent module is one-layer, unidirectional, sequence-first by the PyTorch API defaults used here.
- input_dim is len(TEXT.vocab); max_size=20000 is a vocabulary construction limit, not an exact embedding row count.
- pack_padded_sequence consumes embedded tokens and their external valid lengths.
- BucketIterator(sort_within_batch=True) provides sorted minibatches for default packing behavior.
- Only hidden.squeeze(0) feeds fc; packed_output and cell are not used by this classifier.
- RNN.forward returns flattened logits; sigmoid and threshold belong to compute_binary_accuracy.
- predict_sentiment also applies sigmoid externally, but its tokenization/single-sentence path is not the selected batch diagram.
- binary_cross_entropy_with_logits is in the training loop, outside model forward; it must not be preceded by a model sigmoid.
- Gate equations and the nn.LSTM implementation are external library behavior, not notebook-defined source nodes.
- Within one nn.LSTM instance recurrent weights are reused across time; it is not a fresh Linear per token.
