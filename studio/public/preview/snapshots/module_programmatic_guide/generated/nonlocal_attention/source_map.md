# Non-local 2D attention / pooled keys-values：源码与图框对应

来源：`ajbrock/BigGAN-PyTorch`，固定提交 `98459431a5d618d644d54cd1e9fceb1e5045648d`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E003 | [biggan-modules/layers.py](sources/biggan-modules/layers.py) · `SNConv2d.__init__` | 104–109 | — |
| E004 | [biggan-modules/layers.py](sources/biggan-modules/layers.py) · `SNConv2d.forward` | 110–112 | — |
| E001 | [biggan-modules/layers.py](sources/biggan-modules/layers.py) · `Attention.__init__` | 145–155 | — |
| E002 | [biggan-modules/layers.py](sources/biggan-modules/layers.py) · `Attention.forward` | 156–169 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| nonlocal_attention.root | Non-local 2D attention / pooled keys-values |  | E001,E002,E003,E004 | — |
| nonlocal_attention.x | Feature map x | [B,32,8,8] | E002 | — |
| nonlocal_attention.body | Non-local 2D attention module | [B,32,8,8] | E001,E002,E003,E004 | — |
| nonlocal_attention.theta | Full-resolution theta |  | E002 | — |
| nonlocal_attention.theta_conv | SNConv1x1 32 -> 4 | [B,4,8,8] | E001,E002,E004 | instance=theta |
| nonlocal_attention.theta_view | view B,4,64 | [B,4,64] | E002 | — |
| nonlocal_attention.phi | Pooled phi |  | E002 | — |
| nonlocal_attention.phi_conv | SNConv1x1 32 -> 4 | [B,4,8,8] | E001,E002,E004 | instance=phi |
| nonlocal_attention.phi_pool | MaxPool2x2; view B,4,16 | [B,4,16] | E002 | — |
| nonlocal_attention.g | Pooled values g |  | E002 | — |
| nonlocal_attention.g_conv | SNConv1x1 32 -> 16 | [B,16,8,8] | E001,E002,E004 | instance=g |
| nonlocal_attention.g_pool | MaxPool2x2; view B,16,16 | [B,16,16] | E002 | — |
| nonlocal_attention.beta | Spatial similarity |  | E002 | — |
| nonlocal_attention.score | theta.T @ phi | [B,64,16] | E002 | — |
| nonlocal_attention.softmax | Softmax over pooled positions | [B,64,16] | E002 | — |
| nonlocal_attention.aggregate | Attend and restore space |  | E002 | — |
| nonlocal_attention.bmm | g @ beta.T | [B,16,64] | E002 | — |
| nonlocal_attention.view | view B,16,8,8 | [B,16,8,8] | E002 | — |
| nonlocal_attention.o_conv | SNConv1x1 16 -> 32 | [B,32,8,8] | E001,E002,E004 | instance=o |
| nonlocal_attention.residual | Learned residual gain |  | E002 | — |
| nonlocal_attention.gain | gamma * o | [B,32,8,8] | E001,E002 | — |
| nonlocal_attention.add | gamma*o + x | [B,32,8,8] | E002 | — |
| nonlocal_attention.y | Residual attention output | [B,32,8,8] | E002 | — |

## 与教科书/通用基础图的区别

- Do not label this standard full-resolution Transformer Q/K/V attention or permanently zero residual.

## 源码事实与边界

- Theta remains full-resolution; phi and g use max pooling and therefore have four times fewer spatial positions.
- Softmax normalizes the last pooled-position axis. No 1/sqrt(d) scale or positional embedding appears.
- theta,phi,g,o weights are four independent instances; gamma is a learned scalar initialized zero.
- Source y argument is unused. It is not an additional condition input in this attention view.
