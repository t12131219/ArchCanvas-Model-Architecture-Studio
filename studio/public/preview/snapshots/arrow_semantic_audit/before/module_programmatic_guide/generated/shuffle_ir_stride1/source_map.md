# ShuffleNetV2 split/retain：源码与图框对应

来源：`pytorch/vision`，固定提交 `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E005 | [torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py](sources/torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py) · `channel_shuffle` | 21–34 | — |
| E001 | [torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py](sources/torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py) · `InvertedResidual` | 37–96 | — |
| E002 | [torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py](sources/torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py) · `InvertedResidual.__init__` | 38–74 | — |
| E003 | [torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py](sources/torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py) · `InvertedResidual.depthwise_conv` | 77–85 | — |
| E004 | [torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py](sources/torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py) · `InvertedResidual.forward` | 87–96 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| shuffle_ir_stride1.root | ShuffleNetV2 split/retain / module | [B,24,16,16] | E002,E004 | — |
| shuffle_ir_stride1.input | Module input | [B,24,16,16] | E002,E004 | — |
| shuffle_ir_stride1.module | ShuffleNetV2 InvertedResidual | [B,24,16,16] | E002,E004 | — |
| shuffle_ir_stride1.chunk | Chunk channel dim1 into2 | 2 tensors [B,12,16,16] | E002,E004 | — |
| shuffle_ir_stride1.branches | Dispatch x1 / x2 | x1 + transformed x2 | E002,E004 | — |
| shuffle_ir_stride1.retained | Retain x1 / no learned branch1 | [B,12,16,16] | E002,E004 | — |
| shuffle_ir_stride1.branch2 | Learned branch2 | [B,12,16,16] | E002,E004,E003 | — |
| shuffle_ir_stride1.b2.conv1 | Conv 1 / 12→12 | [B,12,16,16] | E002,E004,E003 | branch2.0; instance=shuffle_ir_stride1.branch2.0 |
| shuffle_ir_stride1.b2.bn1 | BatchNorm | [B,12,16,16] | E002,E004 | branch2.1; instance=shuffle_ir_stride1.branch2.1 |
| shuffle_ir_stride1.b2.relu1 | ReLU | [B,12,16,16] | E002,E004 | — |
| shuffle_ir_stride1.b2.dw | Depthwise Conv3 / C=12 | [B,12,16,16] | E002,E004,E003 | branch2.3; instance=shuffle_ir_stride1.branch2.3 |
| shuffle_ir_stride1.b2.bn2 | BatchNorm | [B,12,16,16] | E002,E004 | branch2.4; instance=shuffle_ir_stride1.branch2.4 |
| shuffle_ir_stride1.b2.project | Conv 1 / 12→12 | [B,12,16,16] | E002,E004,E003 | branch2.5; instance=shuffle_ir_stride1.branch2.5 |
| shuffle_ir_stride1.b2.bn3 | BatchNorm | [B,12,16,16] | E002,E004 | branch2.6; instance=shuffle_ir_stride1.branch2.6 |
| shuffle_ir_stride1.b2.relu2 | ReLU | [B,12,16,16] | E002,E004 | — |
| shuffle_ir_stride1.concat | Concat channel dim=1 | [B,24,16,16] | E002,E004 | — |
| shuffle_ir_stride1.shuffle | channel_shuffle / groups=2 | [B,24,16,16] | E004,E005 | — |
| shuffle_ir_stride1.output | Module output | [B,24,16,16] | E002,E004 | — |

## 与教科书/通用基础图的区别

- This is not MobileNet inverted residual: no residual Add or expansion-ratio skip.
- An empty branch1 constructor at stride1 is never called; retain x1 directly.

## 源码事实与边界

- stride1 splits channels: retained x1 and learned branch2(x2) are distinct operands.
- stride>1 uses two independently learned paths on the same full x; no chunk operation.
- Depthwise groups equal input channels, all Conv biasFalse, BN/ReLU preserve source Sequential indices.
- Channel Concat precedes one groups2 shuffle call; shuffle has no weights and its internals are separately covered.
