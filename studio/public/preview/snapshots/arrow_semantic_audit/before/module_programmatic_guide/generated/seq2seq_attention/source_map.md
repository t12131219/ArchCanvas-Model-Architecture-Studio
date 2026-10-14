# Seq2seq dot attention / context fusion：源码与图框对应

来源：`IBM/pytorch-seq2seq`，固定提交 `f146087a9a271e9b50f46561e090324764b081fb`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [ibm-seq2seq-attention/seq2seq/models/attention.py](sources/ibm-seq2seq-attention/seq2seq/models/attention.py) · `Attention.__init__` | 40–43 | — |
| E003 | [ibm-seq2seq-attention/seq2seq/models/attention.py](sources/ibm-seq2seq-attention/seq2seq/models/attention.py) · `Attention.set_mask` | 45–52 | — |
| E002 | [ibm-seq2seq-attention/seq2seq/models/attention.py](sources/ibm-seq2seq-attention/seq2seq/models/attention.py) · `Attention.forward` | 54–72 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| seq2seq_attention.root | Seq2seq dot attention / context fusion |  | E001,E003,E002 | — |
| ibm.query | Decoder output / query | [B,3,16] | E002 | — |
| ibm.context | Encoder context / keys and values | [B,8,16] | E002 | — |
| ibm.external_mask | Mask set by caller / optional branch | [B,3,8] | E003 | — |
| ibm.body | Dot attention + decoder fusion | [B,3,16] | E001,E002 | — |
| ibm.score | bmm(output, context^T) | [B,3,8] | E002 | — |
| ibm.mask | masked_fill_ / True -> -inf | [B,3,8] | E002,E003 | — |
| ibm.softmax | View2D + Softmax input positions | [B,3,8] | E002 | — |
| ibm.mix | bmm(attn, same context) | [B,3,16] | E002 | — |
| ibm.concat | Concat [mix, original output] | [B,3,32] | E002 | — |
| ibm.fusion | Output fusion / source view wrappers | [B,3,16] | E001,E002 | — |
| ibm.flat | View2D / width32 | [B*3,32] | E002 | — |
| ibm.linear | Linear32 -> 16 | [B*3,16] | E001 | linear_out |
| ibm.tanh | Tanh + restore sequence view | [B,3,16] | E002 | — |
| ibm.output | Return fused output, attention | [B,3,16]; [B,3,8] | E002 | — |

## 与教科书/通用基础图的区别

- Do not insert sqrt(D) scaling, QKV linears or an additive scorer.
- Do not swap concat order; do not feed the newly fused output into its own scoring path.

## 源码事实与边界

- Query is the decoder output, while context supplies both keys and values without learned QKV projections.
- The source computes an unscaled dot product, optionally masks attn.data in place with-inf, then normalizes context positions.
- mask startsNone; this example selects the real set_mask branch, and caller supplies the full broadcast-compatible score mask.
- The context mixture is concatenated before original decoder output, passed through one biased linear_out and Tanh.
- forward returns fused output and the same normalized attention weights; no attention Dropout is present.
