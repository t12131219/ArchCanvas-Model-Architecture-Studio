# ZeroConv2d conditioner：源码与图框对应

来源：`rosinality/glow-pytorch`，固定提交 `97081ff115a694cf04aeedbd58447f33d242c879`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [glow-modules/model.py](sources/glow-modules/model.py) · `ZeroConv2d.__init__` | 140–146 | — |
| E002 | [glow-modules/model.py](sources/glow-modules/model.py) · `ZeroConv2d.forward` | 148–153 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| zero_conv.root | ZeroConv2d conditioner |  | E001,E002 | — |
| zero_conv.x | Input features | [B,16,8,8] | E002 | — |
| zero_conv.body | ZeroConv2d module | [B,8,8,8] | E001,E002 | — |
| zero_conv.pad | Explicit boundary padding |  | E002 | — |
| zero_conv.padop | F.pad / constant value 1 | [B,16,10,10] | E002 | — |
| zero_conv.conv | Zero-initialized Conv3x3 |  | E002 | — |
| zero_conv.convop | Conv 16 -> 8; padding0 | [B,8,8,8] | E001,E002 | — |
| zero_conv.scale | Learned output scaling |  | E002 | — |
| zero_conv.scaleop | out * exp(scale * 3) | [B,8,8,8] | E002 | — |
| zero_conv.y | Conditioner output | [B,8,8,8] | E002 | — |

## 与教科书/通用基础图的区别

- Do not substitute standard zero padding or permanently frozen convolution.

## 源码事实与边界

- The argument named padding in the constructor is unused; actual forward pads all four sides with value 1.
- Conv weight and bias start at zero but remain learnable; exp(scale*3) starts at 1.
