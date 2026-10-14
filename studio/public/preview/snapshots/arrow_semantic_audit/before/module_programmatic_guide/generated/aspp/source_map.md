# ASPP atrous context：源码与图框对应

来源：`pytorch/vision`，固定提交 `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E004 | [torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py](sources/torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py) · `ASPPConv.__init__` | 41–47 | — |
| E005 | [torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py](sources/torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py) · `ASPPPooling.__init__` | 51–56 | — |
| E006 | [torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py](sources/torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py) · `ASPPPooling.forward` | 58–62 | — |
| E001 | [torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py](sources/torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py) · `ASPP` | 65–93 | — |
| E002 | [torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py](sources/torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py) · `ASPP.__init__` | 66–86 | — |
| E003 | [torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py](sources/torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py) · `ASPP.forward` | 88–93 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| aspp.root | ASPP atrous context / module | [B,64,32,32] | E002,E003 | — |
| aspp.input | Module input | [B,256,32,32] | E002,E003 | — |
| aspp.module | ASPP | [B,64,32,32] | E002,E003 | — |
| aspp.branches | Pointwise / rates / global context | 5 x 64 channels | E002,E003 | — |
| aspp.pointwise | Pointwise Conv1 + BN + ReLU | [B,64,32,32] | E002,E003 | convs.0 |
| aspp.pointwise.conv | Conv 1 / 256→64 | [B,64,32,32] | E002,E003 | convs.0.0; instance=aspp.convs.0.0 |
| aspp.pointwise.bn | BatchNorm | [B,64,32,32] | E002,E003 | convs.0.1; instance=aspp.convs.0.1 |
| aspp.pointwise.relu | ReLU | [B,64,32,32] | E002,E003 | — |
| aspp.rate6 | Atrous Conv3 / rate=6 | [B,64,32,32] | E002,E003,E004 | convs.1 |
| aspp.rate6.conv | Conv 3 / 256→64 | [B,64,32,32] | E002,E003,E004 | convs.1.0; instance=aspp.convs.1.0 |
| aspp.rate6.bn | BatchNorm | [B,64,32,32] | E002,E003,E004 | convs.1.1; instance=aspp.convs.1.1 |
| aspp.rate6.relu | ReLU | [B,64,32,32] | E002,E003,E004 | — |
| aspp.rate12 | Atrous Conv3 / rate=12 | [B,64,32,32] | E002,E003,E004 | convs.2 |
| aspp.rate12.conv | Conv 3 / 256→64 | [B,64,32,32] | E002,E003,E004 | convs.2.0; instance=aspp.convs.2.0 |
| aspp.rate12.bn | BatchNorm | [B,64,32,32] | E002,E003,E004 | convs.2.1; instance=aspp.convs.2.1 |
| aspp.rate12.relu | ReLU | [B,64,32,32] | E002,E003,E004 | — |
| aspp.rate18 | Atrous Conv3 / rate=18 | [B,64,32,32] | E002,E003,E004 | convs.3 |
| aspp.rate18.conv | Conv 3 / 256→64 | [B,64,32,32] | E002,E003,E004 | convs.3.0; instance=aspp.convs.3.0 |
| aspp.rate18.bn | BatchNorm | [B,64,32,32] | E002,E003,E004 | convs.3.1; instance=aspp.convs.3.1 |
| aspp.rate18.relu | ReLU | [B,64,32,32] | E002,E003,E004 | — |
| aspp.pool_path | Global pool + project + resize | [B,64,32,32] | E002,E003,E005,E006 | — |
| aspp.pool | Adaptive average pool1 | [B,256,1,1] | E002,E003,E005 | — |
| aspp.pool_conv | Conv 1 / 256→64 | [B,64,1,1] | E002,E003,E005 | convs.4.1; instance=aspp.convs.4.1 |
| aspp.pool_bn | BatchNorm | [B,64,1,1] | E002,E003,E005 | convs.4.2; instance=aspp.convs.4.2 |
| aspp.pool_relu | ReLU | [B,64,1,1] | E002,E003,E005 | — |
| aspp.resize | Bilinear resize to input H,W | [B,64,32,32] | E002,E003,E006 | — |
| aspp.concat | Concat all5 paths | [B,320,32,32] | E002,E003 | — |
| aspp.project | Project + BN + ReLU + Dropout | [B,64,32,32] | E002,E003 | — |
| aspp.project.conv | Conv 1 / 320→64 | [B,64,32,32] | E002,E003 | project.0; instance=aspp.project.0 |
| aspp.project.bn | BatchNorm | [B,64,32,32] | E002,E003 | project.1; instance=aspp.project.1 |
| aspp.project.relu | ReLU | [B,64,32,32] | E002,E003 | — |
| aspp.dropout | Dropout p=0.5 | [B,64,32,32] | E002,E003 | — |
| aspp.output | Module output | [B,64,32,32] | E002,E003 | — |

## 与教科书/通用基础图的区别

- Rates6/12/18 and width64 are explicitly chosen; DeepLabHead uses12/24/36 and default width256.
- A global-pool path is not a fourth dilated convolution.

## 源码事实与边界

- Five paths receive the same feature input; three3x3 paths have distinct rates and independent parameters.
- Global pooling path records adaptive pool1 and bilinear resize with align_corners=False.
- Concat320 precedes Conv1x1/BN/ReLU/Dropout.5; caller mode controls BN/Dropout.
