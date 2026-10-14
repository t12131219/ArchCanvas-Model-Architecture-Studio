# PSP resize/convolution upsample：源码与图框对应

来源：`Lextal/pspnet-pytorch`，固定提交 `4eb6ab61287e837f5e2d8c1ae09fadeaa0e31e37`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [pspnet-vision-extended/pspnet.py](sources/pspnet-vision-extended/pspnet.py) · `PSPUpsample` | 28–40 | — |
| E002 | [pspnet-vision-extended/pspnet.py](sources/pspnet-vision-extended/pspnet.py) · `PSPUpsample.__init__` | 29–35 | — |
| E003 | [pspnet-vision-extended/pspnet.py](sources/pspnet-vision-extended/pspnet.py) · `PSPUpsample.forward` | 37–40 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| psp_upsample.root | PSP resize/convolution upsample / module | [B,32,16,16] | E002,E003 | — |
| psp_upsample.input | Module input | [B,64,8,8] | E002,E003 | — |
| psp_upsample.module | PSPUpsample | [B,32,16,16] | E002,E003 | — |
| psp_upsample.resize | Bilinear resize / 2x H,W | [B,64,16,16] | E002,E003 | — |
| psp_upsample.conv | Conv3 + BN + PReLU | [B,32,16,16] | E002,E003 | — |
| psp_upsample.conv_op | Conv 3 / 64→32 | [B,32,16,16] | E002,E003 | conv.0; instance=psp_upsample.conv.0 |
| psp_upsample.bn | BatchNorm | [B,32,16,16] | E002,E003 | conv.1; instance=psp_upsample.conv.1 |
| psp_upsample.prelu | PReLU / one learned slope | [B,32,16,16] | E002,E003 | conv.2; instance=psp_upsample.conv.2 |
| psp_upsample.output | Module output | [B,32,16,16] | E002,E003 | — |

## 与教科书/通用基础图的区别

- Do not replace bilinear upsample with ConvTranspose or PixelShuffle.
- The PReLU parameter is separate from Conv/BN parameter paths and does not have32 independent slopes.

## 源码事实与边界

- Bilinear F.upsample doubles input H and W before the convolution, rather than applying pixel channel rearrangement.
- Conv3 padding1 retains enlarged16x16 and has default biasTrue; BN32 follows it.
- nn.PReLU() owns exactly one learned slope initialized0.25, shared across all32 channels; it is not a fixed ReLU.
- align_corners is omitted in this historical API call; drawing does not invent a default or execute the library.
