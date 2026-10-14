# Pyramid pooling / PSPModule：源码与图框对应

来源：`Lextal/pspnet-pytorch`，固定提交 `4eb6ab61287e837f5e2d8c1ae09fadeaa0e31e37`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [pspnet-vision-extended/pspnet.py](sources/pspnet-vision-extended/pspnet.py) · `PSPModule` | 8–25 | — |
| E002 | [pspnet-vision-extended/pspnet.py](sources/pspnet-vision-extended/pspnet.py) · `PSPModule.__init__` | 9–14 | — |
| E003 | [pspnet-vision-extended/pspnet.py](sources/pspnet-vision-extended/pspnet.py) · `PSPModule._make_stage` | 16–19 | — |
| E004 | [pspnet-vision-extended/pspnet.py](sources/pspnet-vision-extended/pspnet.py) · `PSPModule.forward` | 21–25 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| pyramid_pooling.root | Pyramid pooling / PSPModule / module | [B,128,24,24] | E002,E004 | — |
| pyramid_pooling.input | Module input | [B,64,24,24] | E002,E004 | — |
| pyramid_pooling.module | PSPModule | [B,128,24,24] | E002,E004 | — |
| pyramid_pooling.branches | Four pyramid bins + original feats | 5 x 64 channels | E002,E004 | — |
| pyramid_pooling.bin1 | Pool bins 1x1 | [B,64,24,24] | E002,E004,E003 | — |
| pyramid_pooling.pool0 | AdaptiveAvgPool 1x1 | [B,64,1,1] | E002,E004,E003 | — |
| pyramid_pooling.conv0 | Conv 1 / 64→64 | [B,64,1,1] | E002,E004,E003 | stages.0.1; instance=pyramid_pooling.stages.0.1 |
| pyramid_pooling.resize0 | Bilinear upsample to H,W | [B,64,24,24] | E002,E004 | — |
| pyramid_pooling.bin2 | Pool bins 2x2 | [B,64,24,24] | E002,E004,E003 | — |
| pyramid_pooling.pool1 | AdaptiveAvgPool 2x2 | [B,64,2,2] | E002,E004,E003 | — |
| pyramid_pooling.conv1 | Conv 1 / 64→64 | [B,64,2,2] | E002,E004,E003 | stages.1.1; instance=pyramid_pooling.stages.1.1 |
| pyramid_pooling.resize1 | Bilinear upsample to H,W | [B,64,24,24] | E002,E004 | — |
| pyramid_pooling.bin3 | Pool bins 3x3 | [B,64,24,24] | E002,E004,E003 | — |
| pyramid_pooling.pool2 | AdaptiveAvgPool 3x3 | [B,64,3,3] | E002,E004,E003 | — |
| pyramid_pooling.conv2 | Conv 1 / 64→64 | [B,64,3,3] | E002,E004,E003 | stages.2.1; instance=pyramid_pooling.stages.2.1 |
| pyramid_pooling.resize2 | Bilinear upsample to H,W | [B,64,24,24] | E002,E004 | — |
| pyramid_pooling.bin6 | Pool bins 6x6 | [B,64,24,24] | E002,E004,E003 | — |
| pyramid_pooling.pool3 | AdaptiveAvgPool 6x6 | [B,64,6,6] | E002,E004,E003 | — |
| pyramid_pooling.conv3 | Conv 1 / 64→64 | [B,64,6,6] | E002,E004,E003 | stages.3.1; instance=pyramid_pooling.stages.3.1 |
| pyramid_pooling.resize3 | Bilinear upsample to H,W | [B,64,24,24] | E002,E004 | — |
| pyramid_pooling.retained | Retain original feats | [B,64,24,24] | E002,E004 | — |
| pyramid_pooling.concat | Concat priors then original | [B,320,24,24] | E002,E004 | — |
| pyramid_pooling.bottleneck | Conv 1 / 320→128 | [B,128,24,24] | E002,E004 | bottleneck; instance=pyramid_pooling.bottleneck |
| pyramid_pooling.relu | ReLU | [B,128,24,24] | E002,E004 | — |
| pyramid_pooling.output | Module output | [B,128,24,24] | E002,E004 | — |

## 与教科书/通用基础图的区别

- This literal implementation retainsC channels per bin rather than C/4.
- Original feats is the last list entry, not the first.
- Do not use ASPP dilation rates or add absent BN.

## 源码事实与边界

- Four adaptive pools independently project64->64, resize to24x24, then concatenate before original feats.
- Stage Conv biasFalse; bottleneck bias defaultsTrue; no BN inside this PSPModule.
- F.upsample has omitted align_corners; no API default is invented.
- Upstream repository contains no LICENSE file; its absence is explicitly retained in provenance.
