# QANet context-query attention：源码与图框对应

来源：`hengruo/QANet-pytorch`，固定提交 `04605e21172b3a5e8b0e2b7a869f2e55ef02e8fb`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [qanet-attention-sequence/config.py](sources/qanet-attention-sequence/config.py) · `__module__` | 1–67 | — |
| E004 | [qanet-attention-sequence/models.py](sources/qanet-attention-sequence/models.py) · `mask_logits` | 21–22 | — |
| E002 | [qanet-attention-sequence/models.py](sources/qanet-attention-sequence/models.py) · `CQAttention.__init__` | 212–217 | — |
| E003 | [qanet-attention-sequence/models.py](sources/qanet-attention-sequence/models.py) · `CQAttention.forward` | 219–238 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| qanet_context_query_attention.root | QANet context-query attention |  | E002,E004,E003 | — |
| cq.input_c | Context C / channels-first | [B,96,8] | E003 | — |
| cq.input_q | Query Q / channels-first | [B,96,5] | E003 | — |
| cq.input_cm | Context padding mask / 0 or1 | [B,8] | E003 | — |
| cq.input_qm | Query padding mask / 0 or1 | [B,5] | E003 | — |
| cq.body | Tri-linear bidirectional interaction | [B,384,8] | E002,E003,E004 | — |
| cq.c | Transpose context to length,features | [B,8,96] | E003 | — |
| cq.q | Transpose query to length,features | [B,5,96] | E003 | — |
| cq.ct | Context expand over queries | [B,8,5,96] | E003 | — |
| cq.qt | Query expand over context | [B,8,5,96] | E003 | — |
| cq.cq | Ct * Qt / pairwise products | [B,8,5,96] | E003 | — |
| cq.features | Concat [Ct,Qt,Ct*Qt] | [B,8,5,288] | E003 | — |
| cq.score | Pair features @ learned w | [B,8,5] | E002,E003 | — |
| cq.s1 | Query-normalized attention S1 | [B,8,5] | E003,E004 | — |
| cq.qmask | Apply query mask / -1e30 | [B,8,5] | E003,E004 | — |
| cq.softmax1 | Softmax along query positions | [B,8,5] | E003 | — |
| cq.s2 | Context-normalized attention S2 | [B,8,5] | E003,E004 | — |
| cq.cmask | Apply context mask / -1e30 | [B,8,5] | E003,E004 | — |
| cq.softmax2 | Softmax along context positions | [B,8,5] | E003 | — |
| cq.a | A = S1 @ Q | [B,8,96] | E003 | — |
| cq.cross | S1 @ transpose(S2) | [B,8,8] | E003 | — |
| cq.b | B = cross-attention @ C | [B,8,96] | E003 | — |
| cq.ca | C * A | [B,8,96] | E003 | — |
| cq.cb | C * B | [B,8,96] | E003 | — |
| cq.fuse | Concat [C,A,C*A,C*B] | [B,8,384] | E003 | — |
| cq.tail | Dropout and restore channels-first | [B,384,8] | E003 | — |
| cq.drop | Dropout p=.1 / eval identity | [B,8,384] | E003 | — |
| cq.transpose | Transpose feature and context axes | [B,384,8] | E003 | — |
| cq.output | Context-query interaction output | [B,384,8] | E003 | — |

## 与教科书/通用基础图的区别

- Do not replace S2 with a max-reduced query-to-context attention from another BiDAF implementation.
- Do not use the same mask or same normalization axis twice; do not insert QKV projections.

## 源码事实与边界

- Frozen config.py supplies d_model96 and dropout.1; context8/query5 are explicit module example lengths, not claimed full-model limits.
- One learned vector w has3D entries and no bias; pair features concatenate C,Q,C*Q before the dot with w.
- The same raw S scores take different masks and normalize over query axis2(S1) versus context axis1(S2).
- A=S1@Q; B=(S1@S2.T)@C; the final four-part feature concat is C,A,C*A,C*B.
- Mask helper uses arithmetic with finite-1e30, not masked_fill(-inf). Only out is returned; attention matrices are internal.
