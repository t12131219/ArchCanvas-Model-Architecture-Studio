# Bahdanau attention / query-key-value roles：源码与图框对应

来源：`eladhoffer/seq2seq.pytorch`，固定提交 `769c9995594ea0059075280f49a86ac4dace28bd`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [seq2seq-additive-sequence/seq2seq/models/modules/attention.py](sources/seq2seq-additive-sequence/seq2seq/models/modules/attention.py) · `AttentionLayer.__init__` | 18–48 | — |
| E004 | [seq2seq-additive-sequence/seq2seq/models/modules/attention.py](sources/seq2seq-additive-sequence/seq2seq/models/modules/attention.py) · `AttentionLayer.set_mask` | 50–54 | — |
| E002 | [seq2seq-additive-sequence/seq2seq/models/modules/attention.py](sources/seq2seq-additive-sequence/seq2seq/models/modules/attention.py) · `AttentionLayer.calc_score` | 56–75 | — |
| E003 | [seq2seq-additive-sequence/seq2seq/models/modules/attention.py](sources/seq2seq-additive-sequence/seq2seq/models/modules/attention.py) · `AttentionLayer.forward` | 77–129 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| seq2seq_additive_attention.root | Bahdanau attention / query-key-value roles |  | E001,E004,E002,E003 | — |
| addatt.input_q | Query / original width12 | [B,3,12] | E003 | — |
| addatt.input_k | Keys / width16 | [B,8,16] | E003 | — |
| addatt.input_v | Explicit values / width20 | [B,8,20] | E003 | — |
| addatt.input_mask | Key mask / selected | [B,8] | E004 | — |
| addatt.body | Additive scoring / explicit values | [B,3,12] | E001,E003,E002 | — |
| addatt.query | Query Linear12 -> key width16 | [B,3,16] | E001,E003 | linear_q |
| addatt.qexpand | Unsqueeze + expand query over keys | [B,3,8,16] | E002 | — |
| addatt.kexpand | Unsqueeze + expand keys over queries | [B,3,8,16] | E002 | — |
| addatt.add | Projected query + key | [B,3,8,16] | E002 | — |
| addatt.scoring | Bahdanau scalar scorer | [B,3,8] | E001,E002 | — |
| addatt.flat | View paired query-key rows | [B*3*8,16] | E002 | — |
| addatt.tanh | Tanh pair sum | [B*3*8,16] | E002 | — |
| addatt.linear | Score Linear16 -> 1 | [B*3*8,1] | E001,E002 | linear_att |
| addatt.reshape | View scores B,query,key | [B,3,8] | E002 | — |
| addatt.mask | Expand key mask / fill -1e12 | [B,3,8] | E003,E004 | — |
| addatt.softmax | Softmax over key positions | [B,3,8] | E003 | — |
| addatt.drop | Attention Dropout p=.1 / eval | [B,3,8] | E001,E003 | — |
| addatt.context | bmm(post-drop weights, values) | [B,3,20] | E003 | — |
| addatt.concat | Concat [original query, context] | [B,3,32] | E003 | — |
| addatt.fusion | Output fusion | [B,3,12] | E001,E003 | — |
| addatt.outlinear | Output Linear32 -> 12 | [B,3,12] | E001 | linear_out |
| addatt.outtanh | Tanh output | [B,3,12] | E003 | — |
| addatt.output | Return context, post-drop weights | [B,3,12]; [B,3,8] | E003 | — |

## 与教科书/通用基础图的区别

- Do not replace additive scoring with dot or add K/V projections absent from this branch.
- Do not silently use keys as explicit values; do not return pre-dropout weights or swap concat operands.

## 源码事实与边界

- linear_q projects queries to key width; keys are not projected by a separate K Linear in this selected source branch.
- Query/key tensors expand to all pairs, add, Tanh, and linear_att produce scalar additive scores.
- normalize=False and weight_norm=False explicitly select ordinary biased score/output linears.
- A supplied key mask expands over queries and uses finite-1e12, then Softmax(dim2) and attention Dropout.
- Values are explicitly distinct inputs; when values=None the source alternatively reuses keys.
- Output fusion concatenates original query before weighted context; returned weights come after Dropout, even though selected eval makes it identity.
