# Squeeze / space-to-channel：源码与图框对应

来源：`rosinality/glow-pytorch`，固定提交 `97081ff115a694cf04aeedbd58447f33d242c879`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [glow-modules/model.py](sources/glow-modules/model.py) · `Block.forward` | 271–296 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| glow_squeeze.root | Squeeze / space-to-channel |  | E001 | — |
| glow_squeeze.x | Input x | [B,2,8,8] | E001 | — |
| glow_squeeze.body | Squeeze module | [B,8,4,4] | E001 | — |
| glow_squeeze.factor | Factor spatial offsets |  | E001 | — |
| glow_squeeze.view1 | view B,C,H/2,2,W/2,2 | [B,2,4,2,4,2] | E001 | — |
| glow_squeeze.permute | Move 2x2 offsets to channels |  | E001 | — |
| glow_squeeze.perm | permute(0,1,3,5,2,4) | [B,2,2,2,4,4] | E001 | — |
| glow_squeeze.merge | Materialize and merge |  | E001 | — |
| glow_squeeze.contig | contiguous() | [B,2,2,2,4,4] | E001 | — |
| glow_squeeze.view2 | view B,4C,H/2,W/2 | [B,8,4,4] | E001 | — |
| glow_squeeze.y | Squeezed features | [B,8,4,4] | E001 | — |

## 与教科书/通用基础图的区别

- Do not add pooling, learned convolution or drop spatial entries.

## 源码事实与边界

- This is a parameter-free bijective rearrangement of 2x2 offsets into channels.
- H and W must be even for this selected profile. It is the space-to-channel direction, opposite to PixelShuffle.
