# BiLSTM (2-layer AGNews classifier)：源码与图框对应

来源：`https://github.com/rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_bi_multilayer_lstm_own_csv_agnews.py](sources/deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_bi_multilayer_lstm_own_csv_agnews.py) · `RNN` | 149–174 | [35] |
| E002 | [deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_bi_multilayer_lstm_own_csv_agnews.py](sources/deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_bi_multilayer_lstm_own_csv_agnews.py) · `RNN.__init__` | 150–162 | [35] |
| E003 | [deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_bi_multilayer_lstm_own_csv_agnews.py](sources/deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_bi_multilayer_lstm_own_csv_agnews.py) · `RNN.forward` | 164–174 | [35] |
| E004 | [deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_bi_multilayer_lstm_own_csv_agnews.py](sources/deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_bi_multilayer_lstm_own_csv_agnews.py) · `compute_accuracy` | 187–197 | [38] |
| E005 | [deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_bi_multilayer_lstm_own_csv_agnews.py](sources/deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_bi_multilayer_lstm_own_csv_agnews.py) · `predict_class` | 248–265 | [42] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| bilstm.root | BiLSTM: AGNews | per-batch labels: [B] | E003,E004 | — |
| bilstm.input | Padded content token IDs | text: [T,B] | E003,E004 | — |
| bilstm.forward | RNN.forward: AGNews classifier | logits: [B,4] | E003 | — |
| bilstm.embedding | Token embedding / dropout | [T,B,128] | E002,E003 | — |
| bilstm.lookup | Embedding V -> 128 | [T,B,128] | E002,E003 | embedding.weight |
| bilstm.embed_dropout | Dropout .5 (eval off) | [T,B,128] | E002,E003 | instance=self.dropout; no learned parameters |
| bilstm.packing | Pack valid time steps | PackedSequence | E003 | — |
| bilstm.pack | pack_padded_sequence | PackedSequence | E003 | — |
| bilstm.recurrent | Two-layer bidirectional LSTM | h_n: [4,B,256] | E002,E003 | rnn |
| bilstm.core | nn.LSTM 128 -> 256 / 2 layers / 2 directions | (packed_output,(h_n,c_n)) | E002,E003 | rnn |
| bilstm.select_hidden | Select hidden h_n | [4,B,256] | E003 | — |
| bilstm.aggregation | Last-layer Concat | [B,512] | E003 | — |
| bilstm.last_layer | Last-layer directional states | two operands [B,256] | E003 | — |
| bilstm.forward_state | Forward state: hidden[-2] | [B,256] | E003 | — |
| bilstm.reverse_state | Reverse state: hidden[-1] | [B,256] | E003 | — |
| bilstm.concat | Concat forward / reverse | [B,512] | E003 | — |
| bilstm.hidden_dropout | Dropout .5 (eval off) | [B,512] | E002,E003 | instance=self.dropout; no learned parameters |
| bilstm.classifier | Two linear layers / logits | logits: [B,4] | E002,E003 | — |
| bilstm.fc1 | Linear 512 -> 64 | [B,64] | E002,E003 | fc1 |
| bilstm.head_dropout | Dropout .5 (eval off) | [B,64] | E002,E003 | instance=self.dropout; no learned parameters |
| bilstm.fc2 | Linear 64 -> 4 | logits: [B,4] | E002,E003 | fc2 |
| bilstm.caller | Caller: per-batch class decisions | class labels: [B] | E004 | — |
| bilstm.argmax | max(logits, dim=1): indices | labels: [B] | E004 | — |
| bilstm.lengths | External sequence lengths | text_length: [B] | E003,E004 | — |

## 与教科书/通用基础图的区别

- Do not draw a generic single-layer LSTM or replace hidden[-2]/[-1] with all-layer flattening or last time output.
- Do not add hidden/cell summation, attention, mean pooling, or the commented-out pad_packed_sequence call.
- Do not rename the actual fc1 expression to a generic direction formula; explain why it works for this fixed profile only.
- Do not invent ReLU between fc1 and fc2 or put the predict_class Softmax into model.forward or compute_accuracy.
- Do not label Embedding as pretrained GloVe or a100-dimensional projection based only on build_vocab vectors metadata.
- Two directions describe the opaque LSTM runtime, not two separately constructed notebook nn.LSTM modules or extracted gate graphs.

## 源码事实与边界

- The fixed constructor uses Embedding(V,128,padding_idx=PAD_IDX), LSTM(128,256,num_layers=2,bidirectional=True,dropout=.5).
- The selected caller sets eval; all three self.dropout calls and recurrent inter-layer dropout are inactive identities in this profile.
- Training recurrent dropout operates between two LSTM layers, not on h_n as a separate source-defined gate.
- The three external dropout call sites reuse one weightless module; training draws fresh masks rather than sharing one mask.
- Packing is sequence-first with default enforce_sorted=True; BucketIterator sorts within batch by content length.
- h_n and c_n have [4,B,256]; forward selects only last-layer forward hidden[-2] and reverse hidden[-1], in that order.
- The 512-wide concat does not combine all four hidden states, time outputs, or cell states.
- fc1 is constructed from hidden_dim*num_layers, which equals512 only for this selected2-layer profile; the concat width depends on2 directions.
- Linear512->64, self.dropout, Linear64->4 contain no ReLU/other activation between the Linear layers; forward returns raw logits.
- compute_accuracy selects max(logits,1) indices without Softmax; predict_class separately applies Softmax and is not the chosen caller.
- build_vocab references GloVe100-dimensional vectors, but the source never copies them to the128-dimensional Embedding.
- Layer and direction families have independent parameters; each family reuses its weights across valid time steps.
- The notebook has no gate implementation; nn.LSTM remains an opaque external library boundary. Models and old torchtext code are never executed.
