# MobileNetV2 (CIFAR-10)：源码与图框对应

来源：`rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。


本图联合取证以下独立快照：

- `deeplearning-models-batch2`：`rasbt/deeplearning-models` @ `59beda3aa25337e576564f1c18c6edd26f9f30e3`。
- `torchvision-v0.9.0`：`pytorch/vision` @ `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E010 | [torchvision-v0.9.0/torchvision/models/mobilenetv2.py](sources/torchvision-v0.9.0/torchvision/models/mobilenetv2.py) · `_make_divisible` | 15–28 | — |
| E001 | [torchvision-v0.9.0/torchvision/models/mobilenetv2.py](sources/torchvision-v0.9.0/torchvision/models/mobilenetv2.py) · `ConvBNActivation` | 31–54 | — |
| E002 | [torchvision-v0.9.0/torchvision/models/mobilenetv2.py](sources/torchvision-v0.9.0/torchvision/models/mobilenetv2.py) · `ConvBNActivation.__init__` | 32–54 | — |
| E003 | [torchvision-v0.9.0/torchvision/models/mobilenetv2.py](sources/torchvision-v0.9.0/torchvision/models/mobilenetv2.py) · `InvertedResidual` | 61–99 | — |
| E004 | [torchvision-v0.9.0/torchvision/models/mobilenetv2.py](sources/torchvision-v0.9.0/torchvision/models/mobilenetv2.py) · `InvertedResidual.__init__` | 62–93 | — |
| E005 | [torchvision-v0.9.0/torchvision/models/mobilenetv2.py](sources/torchvision-v0.9.0/torchvision/models/mobilenetv2.py) · `InvertedResidual.forward` | 95–99 | — |
| E006 | [torchvision-v0.9.0/torchvision/models/mobilenetv2.py](sources/torchvision-v0.9.0/torchvision/models/mobilenetv2.py) · `MobileNetV2` | 102–198 | — |
| E007 | [torchvision-v0.9.0/torchvision/models/mobilenetv2.py](sources/torchvision-v0.9.0/torchvision/models/mobilenetv2.py) · `MobileNetV2.__init__` | 103–186 | — |
| E008 | [torchvision-v0.9.0/torchvision/models/mobilenetv2.py](sources/torchvision-v0.9.0/torchvision/models/mobilenetv2.py) · `MobileNetV2._forward_impl` | 188–195 | — |
| E009 | [torchvision-v0.9.0/torchvision/models/mobilenetv2.py](sources/torchvision-v0.9.0/torchvision/models/mobilenetv2.py) · `MobileNetV2.forward` | 197–198 | — |
| E011 | [torchvision-v0.9.0/torchvision/models/mobilenetv2.py](sources/torchvision-v0.9.0/torchvision/models/mobilenetv2.py) · `mobilenet_v2` | 201–215 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| mobile.model | MobileNetV2 · CIFAR-10 | logits: [B,10] | E011,E006 | — |
| mobile.input | CIFAR-10 image | [B,3,64,64] | E008 | — |
| mobile.stem | Stem Conv / BN / ReLU6 | [B,32,32,32] | E002,E007 | — |
| mobile.stem.conv | Conv2d 3x3 | [B,32,32,32] | E002,E007 | features.0.0 |
| mobile.stem.bn | BatchNorm2d | [B,32,32,32] | E002 | features.0.1 |
| mobile.stem.relu6 | ReLU6 | [B,32,32,32] | E002 | — |
| mobile.stage1 | Stage 1 · c=16 / n=1 | [B,16,32,32] | E007,E004,E005 | — |
| mobile.stage1.first | IR block · no skip | [B,16,32,32] | E004,E005,E007 | features.1.conv |
| mobile.stage1.first.depthwise | Depthwise spatial convolution | [B,32,32,32] | E002,E004 | — |
| mobile.stage1.first.depthwise.conv | Conv2d 3x3 | [B,32,32,32] | E002,E004 | features.1.conv.0.0 |
| mobile.stage1.first.depthwise.bn | BatchNorm2d | [B,32,32,32] | E002 | features.1.conv.0.1 |
| mobile.stage1.first.depthwise.relu6 | ReLU6 | [B,32,32,32] | E002 | — |
| mobile.stage1.first.project | Linear bottleneck Conv1x1 | [B,16,32,32] | E004 | features.1.conv.1 |
| mobile.stage1.first.project_bn | BatchNorm2d | [B,16,32,32] | E004 | features.1.conv.2 |
| mobile.stage2 | Stage 2 · c=24 / n=2 | [B,24,16,16] | E007,E004,E005 | — |
| mobile.stage2.first | IR block · no skip | [B,24,16,16] | E004,E005,E007 | features.2.conv |
| mobile.stage2.first.expand | Pointwise expansion | [B,96,32,32] | E002,E004 | — |
| mobile.stage2.first.expand.conv | Conv2d 1x1 | [B,96,32,32] | E002,E004 | features.2.conv.0.0 |
| mobile.stage2.first.expand.bn | BatchNorm2d | [B,96,32,32] | E002 | features.2.conv.0.1 |
| mobile.stage2.first.expand.relu6 | ReLU6 | [B,96,32,32] | E002 | — |
| mobile.stage2.first.depthwise | Depthwise spatial convolution | [B,96,16,16] | E002,E004 | — |
| mobile.stage2.first.depthwise.conv | Conv2d 3x3 | [B,96,16,16] | E002,E004 | features.2.conv.1.0 |
| mobile.stage2.first.depthwise.bn | BatchNorm2d | [B,96,16,16] | E002 | features.2.conv.1.1 |
| mobile.stage2.first.depthwise.relu6 | ReLU6 | [B,96,16,16] | E002 | — |
| mobile.stage2.first.project | Linear bottleneck Conv1x1 | [B,24,16,16] | E004 | features.2.conv.2 |
| mobile.stage2.first.project_bn | BatchNorm2d | [B,24,16,16] | E004 | features.2.conv.3 |
| mobile.stage2.repeat | Identity IR block | [B,24,16,16] | E004,E005,E007 | features.3.conv |
| mobile.stage2.repeat.expand | Pointwise expansion | [B,144,16,16] | E002,E004 | — |
| mobile.stage2.repeat.expand.conv | Conv2d 1x1 | [B,144,16,16] | E002,E004 | features.3.conv.0.0 |
| mobile.stage2.repeat.expand.bn | BatchNorm2d | [B,144,16,16] | E002 | features.3.conv.0.1 |
| mobile.stage2.repeat.expand.relu6 | ReLU6 | [B,144,16,16] | E002 | — |
| mobile.stage2.repeat.depthwise | Depthwise spatial convolution | [B,144,16,16] | E002,E004 | — |
| mobile.stage2.repeat.depthwise.conv | Conv2d 3x3 | [B,144,16,16] | E002,E004 | features.3.conv.1.0 |
| mobile.stage2.repeat.depthwise.bn | BatchNorm2d | [B,144,16,16] | E002 | features.3.conv.1.1 |
| mobile.stage2.repeat.depthwise.relu6 | ReLU6 | [B,144,16,16] | E002 | — |
| mobile.stage2.repeat.project | Linear bottleneck Conv1x1 | [B,24,16,16] | E004 | features.3.conv.2 |
| mobile.stage2.repeat.project_bn | BatchNorm2d | [B,24,16,16] | E004 | features.3.conv.3 |
| mobile.stage2.repeat.add | Add identity shortcut | [B,24,16,16] | E005 | — |
| mobile.stage3 | Stage 3 · c=32 / n=3 | [B,32,8,8] | E007,E004,E005 | — |
| mobile.stage3.first | First IR block · no skip | [B,32,8,8] | E004,E005,E007 | features.4.conv; {'count': 1, 'index': 'j', 'independent_parameters': True, 'instance_indices': [4]} |
| mobile.stage3.repeat | Identity IR block x 2 | [B,32,8,8] | E004,E005,E007 | features.{j}.conv; {'count': 2, 'index': 'j', 'independent_parameters': True, 'instance_indices': [5, 6]} |
| mobile.stage4 | Stage 4 · c=64 / n=4 | [B,64,4,4] | E007,E004,E005 | — |
| mobile.stage4.first | First IR block · no skip | [B,64,4,4] | E004,E005,E007 | features.7.conv; {'count': 1, 'index': 'j', 'independent_parameters': True, 'instance_indices': [7]} |
| mobile.stage4.repeat | Identity IR block x 3 | [B,64,4,4] | E004,E005,E007 | features.{j}.conv; {'count': 3, 'index': 'j', 'independent_parameters': True, 'instance_indices': [8, 9, 10]} |
| mobile.stage5 | Stage 5 · c=96 / n=3 | [B,96,4,4] | E007,E004,E005 | — |
| mobile.stage5.first | First IR block · no skip | [B,96,4,4] | E004,E005,E007 | features.11.conv; {'count': 1, 'index': 'j', 'independent_parameters': True, 'instance_indices': [11]} |
| mobile.stage5.repeat | Identity IR block x 2 | [B,96,4,4] | E004,E005,E007 | features.{j}.conv; {'count': 2, 'index': 'j', 'independent_parameters': True, 'instance_indices': [12, 13]} |
| mobile.stage6 | Stage 6 · c=160 / n=3 | [B,160,2,2] | E007,E004,E005 | — |
| mobile.stage6.first | First IR block · no skip | [B,160,2,2] | E004,E005,E007 | features.14.conv; {'count': 1, 'index': 'j', 'independent_parameters': True, 'instance_indices': [14]} |
| mobile.stage6.repeat | Identity IR block x 2 | [B,160,2,2] | E004,E005,E007 | features.{j}.conv; {'count': 2, 'index': 'j', 'independent_parameters': True, 'instance_indices': [15, 16]} |
| mobile.stage7 | Stage 7 · c=320 / n=1 | [B,320,2,2] | E007,E004,E005 | — |
| mobile.stage7.first | First IR block · no skip | [B,320,2,2] | E004,E005,E007 | features.17.conv; {'count': 1, 'index': 'j', 'independent_parameters': True, 'instance_indices': [17]} |
| mobile.last | Final pointwise features | [B,1280,2,2] | E002,E007 | — |
| mobile.last.conv | Conv2d 1x1 | [B,1280,2,2] | E002,E007 | features.18.0 |
| mobile.last.bn | BatchNorm2d | [B,1280,2,2] | E002 | features.18.1 |
| mobile.last.relu6 | ReLU6 | [B,1280,2,2] | E002 | — |
| mobile.head | CIFAR-10 classifier | logits: [B,10] | E007,E008 | — |
| mobile.pool | Adaptive average pool 1x1 | [B,1280,1,1] | E008 | — |
| mobile.reshape | Reshape preserving batch | [B,1280] | E008 | — |
| mobile.dropout | Dropout 0.2 | [B,1280] | E007,E008 | — |
| mobile.fc | Replaced Linear 1280 -> 10 | logits: [B,10] | E007,E008 | classifier.1 |
| mobile.output | Returned logits | [B,10] | E008,E009 | — |

## 与教科书/通用基础图的区别

- Do not infer architecture solely from the notebook's torch.hub call; bind the exact torchvision v0.9.0 source implementation.
- Do not copy the original ImageNet 1000-class head or 224x224 shapes into this 64x64 CIFAR-10 replacement-head profile.
- Depthwise grouping is an attribute of a single Conv2d, not hundreds of separately instantiated branches.
- Do not add a projection shortcut to changed-channel or stride2 blocks; this implementation simply omits the identity Add.
- The linear bottleneck is a pointwise Conv2d without activation, not an nn.Linear layer or a ReLU6 block.
- Do not insert Softmax in model.forward or use squeeze that removes the B=1 batch dimension.

## 源码事实与边界

- The notebook pins torch.hub to pytorch/vision:v0.9.0, pretrained=False; its actual implementation is independently frozen as source.
- The caller crops resized CIFAR-10 to 64x64 and replaces classifier[-1] with Linear(1280,10).
- Default width_mult=1 and round_nearest=8 preserve the seven [t,c,n,s] settings and 17 independently constructed InvertedResidual blocks.
- The stem maps 3->32 with stride2; stage channels are 16,24,32,64,96,160,320 and spatial sizes are 32,16,8,4,4,2,2.
- Expansion uses hidden_dim=round(inp*t); t=1 stage1 omits expansion completely and depthwise-convolves 32 channels before projecting to16.
- Depthwise Conv2d uses groups=hidden_dim; the subsequent pointwise bottleneck is Conv2d+BN without ReLU6.
- Identity Add executes only when stride=1 and inp==oup. There are 10 identity additions, no learned projection shortcuts and no post-Add activation.
- Final Conv1x1 maps320->1280, then adaptive average pooling and batch-preserving reshape feed Dropout0.2 and the replaced Linear1280->10.
- Dropout is an eval identity; BatchNorm still uses running statistics; forward returns logits without Softmax.
- Later blocks are folded operator summaries with real feature indices and parameter members; representative t1, t6/no-skip and t6/identity blocks expand.
