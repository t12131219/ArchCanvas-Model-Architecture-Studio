# TextCNN (IMDb length-masked)：源码与图框对应

来源：`rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py](sources/deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py) · `Config` | 30–44 | [2] |
| E008 | [deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py](sources/deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py) · `tokenize` | 148–150 | [8] |
| E007 | [deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py](sources/deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py) · `make_loaders` | 153–191 | [8] |
| E002 | [deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py](sources/deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py) · `TextCNN` | 197–224 | [11] |
| E003 | [deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py](sources/deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py) · `TextCNN.__init__` | 198–209 | [11] |
| E004 | [deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py](sources/deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py) · `TextCNN.forward` | 211–224 | [11] |
| E005 | [deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py](sources/deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py) · `check_model` | 227–239 | [11] |
| E006 | [deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py](sources/deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py) · `evaluate` | 249–264 | [14] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| textcnn.root | TextCNN / IMDb valid-window pooling | (token_ids,lengths) -> logits [B,2] | E002 | — |
| textcnn.input | Right-padded token IDs | [B,512] | E004,E007 | — |
| textcnn.embedding | Embedding + channel-first layout | [B,200,512] | E003,E004 | — |
| textcnn.lookup | Embedding V -> 200 | [B,L,200] | E003,E004 | embedding.weight |
| textcnn.transpose | Transpose axes 1 and 2 | [B,200,L] | E004 | — |
| textcnn.branches | Three independent convolution widths | 3 tensors [B,128] | E003,E004 | — |
| textcnn.k3 | Conv branch / width k=3 | [B,128] | E003,E004 | convolutions.0 |
| textcnn.k3.conv | Conv1d 200 -> 128 / k=3 | [B,128,510] | E003,E004 | convolutions.0 |
| textcnn.k3.relu | ReLU | [B,128,510] | E004 | — |
| textcnn.k3.operands | Retained features / length mask | features + mask operands | E004 | — |
| textcnn.k3.features_operand | Retain ReLU features | [B,128,510] | E004 | — |
| textcnn.k3.validity | Build valid-window mask | mask: [B,510] | E004 | — |
| textcnn.k3.mask_operands | Allowed count / positions | count + position operands | E004 | — |
| textcnn.k3.valid_count | Count retained windows | valid_windows: [B] | E004 | — |
| textcnn.k3.count | lengths - k + 1 | [B] | E004 | — |
| textcnn.k3.clamp | Clamp count to at least 1 | valid_windows: [B] | E004 | — |
| textcnn.k3.positions | arange feature positions | positions: [510] | E004 | — |
| textcnn.k3.mask | positions >= valid_windows | mask: [B,510] | E004 | — |
| textcnn.k3.masked_fill | Fill excluded windows with dtype min | [B,128,510] | E004 | — |
| textcnn.k3.amax | amax over valid positions | [B,128] | E004 | — |
| textcnn.k4 | Conv branch / width k=4 | [B,128] | E003,E004 | convolutions.1 |
| textcnn.k4.conv | Conv1d 200 -> 128 / k=4 | [B,128,509] | E003,E004 | convolutions.1 |
| textcnn.k4.relu | ReLU | [B,128,509] | E004 | — |
| textcnn.k4.operands | Retained features / length mask | features + mask operands | E004 | — |
| textcnn.k4.features_operand | Retain ReLU features | [B,128,509] | E004 | — |
| textcnn.k4.validity | Build valid-window mask | mask: [B,509] | E004 | — |
| textcnn.k4.mask_operands | Allowed count / positions | count + position operands | E004 | — |
| textcnn.k4.valid_count | Count retained windows | valid_windows: [B] | E004 | — |
| textcnn.k4.count | lengths - k + 1 | [B] | E004 | — |
| textcnn.k4.clamp | Clamp count to at least 1 | valid_windows: [B] | E004 | — |
| textcnn.k4.positions | arange feature positions | positions: [509] | E004 | — |
| textcnn.k4.mask | positions >= valid_windows | mask: [B,509] | E004 | — |
| textcnn.k4.masked_fill | Fill excluded windows with dtype min | [B,128,509] | E004 | — |
| textcnn.k4.amax | amax over valid positions | [B,128] | E004 | — |
| textcnn.k5 | Conv branch / width k=5 | [B,128] | E003,E004 | convolutions.2 |
| textcnn.k5.conv | Conv1d 200 -> 128 / k=5 | [B,128,508] | E003,E004 | convolutions.2 |
| textcnn.k5.relu | ReLU | [B,128,508] | E004 | — |
| textcnn.k5.operands | Retained features / length mask | features + mask operands | E004 | — |
| textcnn.k5.features_operand | Retain ReLU features | [B,128,508] | E004 | — |
| textcnn.k5.validity | Build valid-window mask | mask: [B,508] | E004 | — |
| textcnn.k5.mask_operands | Allowed count / positions | count + position operands | E004 | — |
| textcnn.k5.valid_count | Count retained windows | valid_windows: [B] | E004 | — |
| textcnn.k5.count | lengths - k + 1 | [B] | E004 | — |
| textcnn.k5.clamp | Clamp count to at least 1 | valid_windows: [B] | E004 | — |
| textcnn.k5.positions | arange feature positions | positions: [508] | E004 | — |
| textcnn.k5.mask | positions >= valid_windows | mask: [B,508] | E004 | — |
| textcnn.k5.masked_fill | Fill excluded windows with dtype min | [B,128,508] | E004 | — |
| textcnn.k5.amax | amax over valid positions | [B,128] | E004 | — |
| textcnn.head | Concatenated feature classifier | logits: [B,2] | E003,E004 | — |
| textcnn.concat | Concat pooled branch features | [B,384] | E004 | — |
| textcnn.dropout | Dropout p=0.5 | [B,384] | E003,E004 | — |
| textcnn.classifier | Linear 384 -> 2 | logits: [B,2] | E003,E004 | classifier |
| textcnn.output | Two-class logits | [B,2] | E004 | — |
| textcnn.lengths | External valid lengths | lengths: [B] | E004,E007 | — |

## 与教科书/通用基础图的区别

- This frozen notebook is a newer length-masked implementation, not the older torchtext/TextCNN tutorial structure.
- Use Conv1d with batch-first token IDs followed by transpose, not a made-up Conv2d image or sequence-first input.
- Draw masking before maximum reduction; including every padded convolution window changes this source's semantics.
- Preserve clamp(min=1) for short reviews and torch.finfo(dtype).min; neither all-invalid output nor -infinity is the literal source.
- Draw explicit channel Concat after three branch reductions; branches are not summed and do not share convolution weights.
- Do not add a forward Softmax, positional encoding, attention, LSTM packing or pretrained embeddings.

## 源码事实与边界

- Config defaults are embedding_dim=200,filter_widths=(3,4,5),filters_per_width=128,max_length=512,dropout=0.5.
- The realized embedding row count is len(vocabulary); 30000 is an upper limit including pad/unk, not a guaranteed exact size.
- One shared embedding supplies three independently parameterized Conv1d branches, all with no padding and stride=1.
- For L=512, convolution output positions are 510,509,508; each branch maps 200 embedding channels to 128 filters.
- After ReLU, valid_windows=(lengths-k+1).clamp(min=1); positions>=valid_windows marks excluded windows.
- Internal parallel argument groups are logical operand bundles, not literal source tuples or tuple-field dispatch.
- Typed child bindings give count only the external lengths input, positions only ReLU.shape, and masked_fill the retained ReLU values plus mask.
- Very short reviews retain their first zero-padded window rather than excluding every window.
- Excluded features are filled with the finite minimum of their actual floating dtype, then amax over positions yields [B,128].
- Pooled features concatenate in widths 3,4,5 order to [B,384], pass Dropout(0.5), then Linear(384,2).
- forward returns raw two-class logits only; evaluate applies argmax and cross_entropy outside model forward.
- Lengths are an explicit caller input used by each branch mask; they are not learned embedding or a packed recurrent input.
- Convolution kernels share weights across positions within each branch; different widths have distinct parameter instances.
