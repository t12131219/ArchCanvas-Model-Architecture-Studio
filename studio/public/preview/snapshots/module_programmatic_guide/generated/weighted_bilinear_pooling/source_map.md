# Weighted bilinear pooling：源码与图框对应

来源：`jnhwkim/ban-vqa`，固定提交 `ef4cc36d63f6b31344301ac1bd91afd807d132e5`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [ban-modules/bc.py](sources/ban-modules/bc.py) · `BCNet.__init__` | 19–39 | — |
| E002 | [ban-modules/bc.py](sources/ban-modules/bc.py) · `BCNet.forward_with_weights` | 64–71 | — |
| E003 | [ban-modules/fc.py](sources/ban-modules/fc.py) · `FCNet.__init__` | 13–31 | — |
| E004 | [ban-modules/fc.py](sources/ban-modules/fc.py) · `FCNet.forward` | 33–34 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| weighted_bilinear_pooling.root | Weighted bilinear pooling / module only | [B,4] | E002 | — |
| weighted_bilinear_pooling.v | Visual features V | [B,5,8] | E002 | — |
| weighted_bilinear_pooling.q | Language features Q | [B,3,6] | E002 | — |
| weighted_bilinear_pooling.w | External pair weights w | [B,5,3] | E002 | — |
| weighted_bilinear_pooling.module | Weighted bilinear pooling / operators | [B,4] | E002 | — |
| weighted_bilinear_pooling.vproject | V projection | [B,5,12] | E002,E004 | — |
| weighted_bilinear_pooling.vproject.drop | Dropout .2 | [B,5,8] | E003,E004 | — |
| weighted_bilinear_pooling.vproject.linear | WeightNorm Linear 8 -> 12 | [B,5,12] | E003 | v_net.main.1 |
| weighted_bilinear_pooling.vproject.relu | ReLU | [B,5,12] | E003,E004 | — |
| weighted_bilinear_pooling.qproject | Q projection | [B,3,12] | E002,E004 | — |
| weighted_bilinear_pooling.qproject.drop | Dropout .2 | [B,3,6] | E003,E004 | — |
| weighted_bilinear_pooling.qproject.linear | WeightNorm Linear 6 -> 12 | [B,3,12] | E003 | q_net.main.1 |
| weighted_bilinear_pooling.qproject.relu | ReLU | [B,3,12] | E003,E004 | — |
| weighted_bilinear_pooling.einsum | Weighted bilinear contraction | [B,12] | E002 | — |
| weighted_bilinear_pooling.pool | Group k3 factors / sum | [B,4] | E002 | — |
| weighted_bilinear_pooling.pool.unsqueeze | Insert pool channel axis | [B,1,12] | E002 | — |
| weighted_bilinear_pooling.pool.avg | AvgPool1d k3 / stride3 | [B,1,4] | E002 | — |
| weighted_bilinear_pooling.pool.sum | Squeeze + multiply by k | [B,4] | E002 | — |
| weighted_bilinear_pooling.output | Selected module output | [B,4] | E002 | — |

## 与教科书/通用基础图的区别

- Do not add Softmax, concatenate modalities, or insert the attention-only extra visual Dropout.5.
- Do not label the output as average pooling: source multiplies pooled values by k.

## 源码事实与边界

- Two FCNet projections are separate owned parameter families; external w is a two-axis pair weight input, not a learned module parameter.
- einsum contracts both visual and question positions; k3 feature factors then pool by AvgPool1d and multiplication by3, which implements sum-pooling.
- This method does not use BCNet.dropout(.5), h_mat or h_bias; attention-generation and pooling examples do not imply shared instances.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
