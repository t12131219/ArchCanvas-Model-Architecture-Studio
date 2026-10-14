# Direct invertible 1x1 convolution：源码与图框对应

来源：`rosinality/glow-pytorch`，固定提交 `97081ff115a694cf04aeedbd58447f33d242c879`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [glow-modules/model.py](sources/glow-modules/model.py) · `InvConv2d.__init__` | 64–70 | — |
| E002 | [glow-modules/model.py](sources/glow-modules/model.py) · `InvConv2d.forward` | 72–80 | — |
| E003 | [glow-modules/model.py](sources/glow-modules/model.py) · `InvConv2d.reverse` | 82–85 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| glow_invconv.root | Direct invertible 1x1 convolution |  | E001,E002,E003 | — |
| glow_invconv.x | Input x | [B,8,8,8] | E002 | — |
| glow_invconv.p | Weight state | C=8 | E001 | — |
| glow_invconv.body | Direct invertible 1x1 convolution module | [B,8,8,8] | E001,E002,E003 | — |
| glow_invconv.weight | Weight materialization |  | E002 | — |
| glow_invconv.weight_read | Read QR-initialized Parameter W | [8,8,1,1] | E001 | — |
| glow_invconv.conv | Channel mixing |  | E002 | — |
| glow_invconv.convop | F.conv2d / 1x1 | [B,8,8,8] | E002 | — |
| glow_invconv.det | Determinant branch |  | E002 | — |
| glow_invconv.detop | H*W * slogdet(W) | scalar | E002 | — |
| glow_invconv.y | Convolved y | [B,8,8,8] | E002 | — |
| glow_invconv.ld | Log determinant | scalar | E002 | — |

## 与教科书/通用基础图的区别

- No attention, spatial kernel3 or extra bias is present.
- Do not count fixed LU buffers as learned parameters.

## 源码事实与边界

- The 1x1 weight is square and mixes channels at each pixel; determinant scales by H*W.
- The learned weight is initialized with QR once. Forward uses slogdet in float64 then casts the logabsdet to float32.
- Reverse uses an explicit matrix inverse, outside the selected forward view.
