# BAN bilinear attention：源码与图框对应

来源：`jnhwkim/ban-vqa`，固定提交 `ef4cc36d63f6b31344301ac1bd91afd807d132e5`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [ban-modules/attention.py](sources/ban-modules/attention.py) · `BiAttention.__init__` | 16–21 | — |
| E002 | [ban-modules/attention.py](sources/ban-modules/attention.py) · `BiAttention.forward_all` | 31–44 | — |
| E003 | [ban-modules/bc.py](sources/ban-modules/bc.py) · `BCNet.__init__` | 19–39 | — |
| E004 | [ban-modules/bc.py](sources/ban-modules/bc.py) · `BCNet.forward` | 41–62 | — |
| E005 | [ban-modules/fc.py](sources/ban-modules/fc.py) · `FCNet.__init__` | 13–31 | — |
| E006 | [ban-modules/fc.py](sources/ban-modules/fc.py) · `FCNet.forward` | 33–34 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| bilinear_attention.root | BAN bilinear attention / module only | p, logits: 2 x [B,2,5,3] | E002 | — |
| bilinear_attention.v | Visual features V | [B,5,8] | E002 | — |
| bilinear_attention.q | Language features Q | [B,3,6] | E002 | — |
| bilinear_attention.scoreparams | Owned h_mat(g,v), h_bias | h[1,2,1,12]; b[1,2,1,1] | E001,E003 | — |
| bilinear_attention.module | BAN bilinear attention / operators | p, logits: 2 x [B,2,5,3] | E002 | — |
| bilinear_attention.vproject | V projection | [B,5,12] | E004,E006 | — |
| bilinear_attention.vproject.drop | Dropout .2 | [B,5,8] | E005,E006 | — |
| bilinear_attention.vproject.linear | WeightNorm Linear 8 -> 12 | [B,5,12] | E005 | v_net.main.1 |
| bilinear_attention.vproject.relu | ReLU | [B,5,12] | E005,E006 | — |
| bilinear_attention.vproject.extra | Extra attention Dropout .5 | [B,5,12] | E003,E004 | — |
| bilinear_attention.qproject | Q projection | [B,3,12] | E004,E006 | — |
| bilinear_attention.qproject.drop | Dropout .2 | [B,3,6] | E005,E006 | — |
| bilinear_attention.qproject.linear | WeightNorm Linear 6 -> 12 | [B,3,12] | E005 | q_net.main.1 |
| bilinear_attention.qproject.relu | ReLU | [B,3,12] | E005,E006 | — |
| bilinear_attention.score | Low-rank bilinear scores + bias | [B,2,5,3] | E004 | logits.h_mat_{g,v} and logits.h_bias |
| bilinear_attention.mask | Mask zero visual rows / -inf | [B,2,5,3] | E002 | — |
| bilinear_attention.normalize | Normalize all V,Q pairs | [B,2,5,3] | E002 | — |
| bilinear_attention.normalize.flat | View V*Q positions | [B,2,15] | E002 | — |
| bilinear_attention.normalize.softmax | Softmax dim=2 | [B,2,15] | E002 | — |
| bilinear_attention.normalize.view | Restore V,Q axes | [B,2,5,3] | E002 | — |
| bilinear_attention.output | Selected module output | p, logits: 2 x [B,2,5,3] | E002 | — |

## 与教科书/通用基础图的区别

- Do not substitute Transformer QK^T/sqrt(d): BAN uses a learned three-operand low-rank bilinear einsum.
- Do not normalize only over question tokens or mask zero question rows.
- Do not silently replace the source data mutation with a different autograd implementation.

## 源码事实与边界

- h_out2<=32 selects the real low-rank einsum branch with k3 factors. h_mat is weight_norm reparameterized by BiAttention; it is not a plain final Parameter named h_mat.
- FCNet includes Dropout.2 before WeightNorm Linear and ReLU; only the visual path gets the extra attention Dropout.5.
- Zero visual rows are detected from original v; source mutates logits.data with -inf, then Softmax normalizes flattened V*Q jointly for each glimpse.
- forward_all returns p and masked logits; logit=True alternate raw-only path is outside this selected profile.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
