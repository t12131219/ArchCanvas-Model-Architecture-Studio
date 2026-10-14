# LU invertible 1x1 convolution：源码与图框对应

来源：`rosinality/glow-pytorch`，固定提交 `97081ff115a694cf04aeedbd58447f33d242c879`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [glow-modules/model.py](sources/glow-modules/model.py) · `InvConv2dLU.__init__` | 89–112 | — |
| E003 | [glow-modules/model.py](sources/glow-modules/model.py) · `InvConv2dLU.forward` | 114–122 | — |
| E002 | [glow-modules/model.py](sources/glow-modules/model.py) · `InvConv2dLU.calc_weight` | 124–131 | — |
| E004 | [glow-modules/model.py](sources/glow-modules/model.py) · `InvConv2dLU.reverse` | 133–136 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| glow_invconv_lu.root | LU invertible 1x1 convolution |  | E001,E003,E004,E002 | — |
| glow_invconv_lu.x | Input x | [B,8,8,8] | E003 | — |
| glow_invconv_lu.p | Weight state | C=8 | E001 | — |
| glow_invconv_lu.body | LU invertible 1x1 convolution module | [B,8,8,8] | E001,E003,E004,E002 | — |
| glow_invconv_lu.weight | Weight materialization |  | E003 | — |
| glow_invconv_lu.factors | Read L/U/logdiag + fixed buffers | [8,8] | E001 | — |
| glow_invconv_lu.reconstruct | P @ L @ U; unsqueeze | [8,8,1,1] | E002 | — |
| glow_invconv_lu.conv | Channel mixing |  | E003 | — |
| glow_invconv_lu.convop | F.conv2d / 1x1 | [B,8,8,8] | E003 | — |
| glow_invconv_lu.det | Determinant branch |  | E003 | — |
| glow_invconv_lu.detop | H*W * sum(logdiag) | scalar | E003 | — |
| glow_invconv_lu.y | Convolved y | [B,8,8,8] | E003 | — |
| glow_invconv_lu.ld | Log determinant | scalar | E003 | — |

## 与教科书/通用基础图的区别

- No attention, spatial kernel3 or extra bias is present.
- Do not count fixed LU buffers as learned parameters.

## 源码事实与边界

- The 1x1 weight is square and mixes channels at each pixel; determinant scales by H*W.
- LU source learns strict-triangular factors and log absolute diagonal; permutation, masks, signs and identity are buffers.
- Reverse uses an explicit matrix inverse, outside the selected forward view.
