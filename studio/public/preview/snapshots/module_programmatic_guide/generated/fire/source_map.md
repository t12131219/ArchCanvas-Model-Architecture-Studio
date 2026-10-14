# Fire squeeze/expand：源码与图框对应

来源：`pytorch/vision`，固定提交 `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [torchvision-v0.9.0-vision-extended/torchvision/models/squeezenet.py](sources/torchvision-v0.9.0-vision-extended/torchvision/models/squeezenet.py) · `Fire` | 15–40 | — |
| E002 | [torchvision-v0.9.0-vision-extended/torchvision/models/squeezenet.py](sources/torchvision-v0.9.0-vision-extended/torchvision/models/squeezenet.py) · `Fire.__init__` | 17–33 | — |
| E003 | [torchvision-v0.9.0-vision-extended/torchvision/models/squeezenet.py](sources/torchvision-v0.9.0-vision-extended/torchvision/models/squeezenet.py) · `Fire.forward` | 35–40 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| fire.root | Fire squeeze/expand / module | [B,128,32,32] | E002,E003 | — |
| fire.input | Module input | [B,64,32,32] | E002,E003 | — |
| fire.module | Fire | [B,128,32,32] | E002,E003 | — |
| fire.squeeze | Squeeze 1x1 | [B,16,32,32] | E002,E003 | — |
| fire.squeeze.conv | Conv 1 / 64→16 | [B,16,32,32] | E002,E003 | squeeze; instance=fire.squeeze |
| fire.squeeze.relu | ReLU | [B,16,32,32] | E002,E003 | — |
| fire.expand | Two independent expansions | 2 x [B,64,32,32] | E002,E003 | — |
| fire.expand1x1 | expand1x1 | [B,64,32,32] | E002,E003 | — |
| fire.expand1x1.conv | Conv 1 / 16→64 | [B,64,32,32] | E002,E003 | expand1x1; instance=fire.expand1x1 |
| fire.expand1x1.relu | ReLU | [B,64,32,32] | E002,E003 | — |
| fire.expand3x3 | expand3x3 | [B,64,32,32] | E002,E003 | — |
| fire.expand3x3.conv | Conv 3 / 16→64 | [B,64,32,32] | E002,E003 | expand3x3; instance=fire.expand3x3 |
| fire.expand3x3.relu | ReLU | [B,64,32,32] | E002,E003 | — |
| fire.concat | Concat channel dim=1 | [B,128,32,32] | E002,E003 | — |
| fire.output | Module output | [B,128,32,32] | E002,E003 | — |

## 与教科书/通用基础图的区别

- The expand paths consume squeezed x, not raw64-channel x.
- Same16->64 channel change is not shared weights.

## 源码事实与边界

- Squeeze Conv/ReLU runs before both independent expand paths.
- All three Conv use bias=True; no BN, pooling or residual.
- Two expanded tensors concatenate in 1x1 then3x3 order;128 channels.
