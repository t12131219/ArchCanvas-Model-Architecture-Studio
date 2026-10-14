# Structured hop attention：源码与图框对应

来源：`kaushalshetty/Structured-Self-Attention`，固定提交 `84ed64f9cee75f84a5d871a46508a308182e4a6d`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [structured-self-attention-sequence/attention/model.py](sources/structured-self-attention-sequence/attention/model.py) · `StructuredSelfAttention.__init__` | 13–51 | — |
| E003 | [structured-self-attention-sequence/attention/model.py](sources/structured-self-attention-sequence/attention/model.py) · `StructuredSelfAttention.softmax` | 73–93 | — |
| E002 | [structured-self-attention-sequence/attention/model.py](sources/structured-self-attention-sequence/attention/model.py) · `StructuredSelfAttention.forward` | 100–115 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| structured_attention.root | Structured hop attention |  | E001,E003,E002 | — |
| struct.input | Precomputed LSTM outputs H | [B,8,16] | E002 | — |
| struct.body | Structured sentence attention subgraph | A:[B,3,8]; mean:[B,16] | E001,E002,E003 | — |
| struct.scorer | Two-layer hop scorer | [B,8,3] | E001,E002 | — |
| struct.first | Linear H16 -> d_a12 | [B,8,12] | E001 | linear_first |
| struct.tanh | Tanh | [B,8,12] | E002 | — |
| struct.second | Linear d_a12 -> hops3 | [B,8,3] | E001 | linear_second |
| struct.softmax | Normalize time / helper | [B,8,3] | E002,E003 | — |
| struct.swap | Transpose time to last axis | [B,3,8] | E003 | — |
| struct.flat | Contiguous + view2D | [B*3,8] | E003 | — |
| struct.normalize | F.softmax / dim omitted | [B*3,8] | E003 | — |
| struct.restore | View original transposed size | [B,3,8] | E003 | — |
| struct.swapback | Transpose back to time,hops | [B,8,3] | E003 | — |
| struct.attention | Transpose to hop attention A | [B,3,8] | E002 | — |
| struct.pool | A @ original LSTM outputs | [B,3,16] | E002 | — |
| struct.avg | Sum hop embeddings / r=3 | [B,16] | E002 | — |
| struct.output | Boundary: mean embedding and A | [B,16]; [B,3,8] | E002 | — |

## 与教科书/通用基础图的区别

- Do not invent padding-mask arrows or a bidirectional LSTM based on the paper.
- Do not normalize across hops or replace source mean-hop fusion with flatten/concatenation.

## 源码事实与边界

- Two independent biased Linear layers score three hops; constructor zeroes both biases but keeps them learnable.
- The actual source LSTM is unidirectional with width lstm_hid_dim, not twice that dimension.
- The helper moves axis1 to the final axis, makes a2D view, calls F.softmax with omitted dim, restores and transposes back.
- Hop attention multiplies the same original outputs used for scores; hop embeddings are averaged by sum/r, not concatenated.
- No padding mask, packed sequence, attention Dropout, or orthogonality loss is executed inside this selected subgraph; l2_matrix_norm is a separate helper.
- Top boundary variables are not a return tuple of a standalone method; full forward returns classifier output and attention.
