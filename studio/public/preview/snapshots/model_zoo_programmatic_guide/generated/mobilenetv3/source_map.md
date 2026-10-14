# MobileNetV3-Large (CIFAR-10)：源码与图框对应

来源：`https://github.com/rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。


本图联合取证以下独立快照：

- `deeplearning-models-batch4`：`https://github.com/rasbt/deeplearning-models` @ `59beda3aa25337e576564f1c18c6edd26f9f30e3`。
- `torchvision-v0.9.0-mobilev3`：`pytorch/vision` @ `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-mobilenet-v3-large-cifar10.py](sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-mobilenet-v3-large-cifar10.py) · `__module__` | 1–149 | [1, 4, 5, 7, 8, 9, 10, 12, 13, 14, 15, 16] |
| E003 | [torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv2.py](sources/torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv2.py) · `_make_divisible` | 15–28 | — |
| E002 | [torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv2.py](sources/torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv2.py) · `ConvBNActivation.__init__` | 32–54 | — |
| E012 | [torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py](sources/torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py) · `SqueezeExcitation.__init__` | 23–28 | — |
| E013 | [torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py](sources/torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py) · `SqueezeExcitation._scale` | 30–35 | — |
| E014 | [torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py](sources/torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py) · `SqueezeExcitation.forward` | 37–39 | — |
| E006 | [torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py](sources/torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py) · `InvertedResidualConfig.__init__` | 44–53 | — |
| E007 | [torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py](sources/torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py) · `InvertedResidualConfig.adjust_channels` | 56–57 | — |
| E004 | [torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py](sources/torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py) · `InvertedResidual.__init__` | 62–92 | — |
| E005 | [torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py](sources/torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py) · `InvertedResidual.forward` | 94–98 | — |
| E008 | [torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py](sources/torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py) · `MobileNetV3` | 101–184 | — |
| E009 | [torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py](sources/torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py) · `MobileNetV3.__init__` | 103–171 | — |
| E010 | [torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py](sources/torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py) · `MobileNetV3._forward_impl` | 173–181 | — |
| E011 | [torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py](sources/torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py) · `MobileNetV3.forward` | 183–184 | — |
| E015 | [torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py](sources/torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py) · `_mobilenet_v3_conf` | 187–233 | — |
| E016 | [torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py](sources/torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py) · `_mobilenet_v3_model` | 236–250 | — |
| E017 | [torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py](sources/torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py) · `mobilenet_v3_large` | 253–264 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| m3.model | MobileNetV3-Large / CIFAR-10 | [B,10] | E001,E017,E009 | — |
| m3.input | CIFAR-10 image | [B,3,64,64] | E001,E010 | — |
| m3.stem | Stem / Hardswish | [B,16,32,32] | E002,E009 | — |
| m3.stem.conv | Conv3x3 3 -> 16 | [B,16,32,32] | E002,E009 | features.0.0 |
| m3.stem.bn | BatchNorm2d | [B,16,32,32] | E002,E009 | features.0.1 |
| m3.stem.act | Hardswish | [B,16,32,32] | E002,E009 | instance=features.0.2; no learned parameters |
| m3.stage1 | Stage 1 / IR 1 | [B,16,32,32] | E009,E015 | — |
| m3.block1 | IR 1 / ReLU / skip | [B,16,32,32] | E015,E004,E005 | features.1.block |
| m3.block1.depthwise | Depthwise spatial convolution | [B,16,32,32] | E002,E004 | — |
| m3.block1.depthwise.conv | Conv3x3 16 -> 16 | [B,16,32,32] | E002,E004 | features.1.block.0.0 |
| m3.block1.depthwise.bn | BatchNorm2d | [B,16,32,32] | E002,E009 | features.1.block.0.1 |
| m3.block1.depthwise.act | ReLU | [B,16,32,32] | E002,E004 | instance=features.1.block.0.2; no learned parameters |
| m3.block1.project | Linear pointwise projection | [B,16,32,32] | E002,E004 | — |
| m3.block1.project.conv | Conv1x1 16 -> 16 | [B,16,32,32] | E002,E004 | features.1.block.1.0 |
| m3.block1.project.bn | BatchNorm2d | [B,16,32,32] | E002,E009 | features.1.block.1.1 |
| m3.block1.project.act | Identity | [B,16,32,32] | E002,E004 | instance=features.1.block.1.2; no learned parameters |
| m3.block1.add | Add identity input | [B,16,32,32] | E005 | — |
| m3.stage2 | Stage 2 / IR 2,3 | [B,24,16,16] | E009,E015 | — |
| m3.block2 | IR 2 / ReLU / no skip | [B,24,16,16] | E015,E004,E005 | features.2.block |
| m3.block2.expand | Pointwise expansion | [B,64,32,32] | E002,E004 | — |
| m3.block2.expand.conv | Conv1x1 16 -> 64 | [B,64,32,32] | E002,E004 | features.2.block.0.0 |
| m3.block2.expand.bn | BatchNorm2d | [B,64,32,32] | E002,E009 | features.2.block.0.1 |
| m3.block2.expand.act | ReLU | [B,64,32,32] | E002,E004 | instance=features.2.block.0.2; no learned parameters |
| m3.block2.depthwise | Depthwise spatial convolution | [B,64,16,16] | E002,E004 | — |
| m3.block2.depthwise.conv | Conv3x3 64 -> 64 | [B,64,16,16] | E002,E004 | features.2.block.1.0 |
| m3.block2.depthwise.bn | BatchNorm2d | [B,64,16,16] | E002,E009 | features.2.block.1.1 |
| m3.block2.depthwise.act | ReLU | [B,64,16,16] | E002,E004 | instance=features.2.block.1.2; no learned parameters |
| m3.block2.project | Linear pointwise projection | [B,24,16,16] | E002,E004 | — |
| m3.block2.project.conv | Conv1x1 64 -> 24 | [B,24,16,16] | E002,E004 | features.2.block.2.0 |
| m3.block2.project.bn | BatchNorm2d | [B,24,16,16] | E002,E009 | features.2.block.2.1 |
| m3.block2.project.act | Identity | [B,24,16,16] | E002,E004 | instance=features.2.block.2.2; no learned parameters |
| m3.block3 | IR 3 / ReLU / skip | [B,24,16,16] | E015,E004,E005 | features.3.block |
| m3.block3.expand | Pointwise expansion | [B,72,16,16] | E002,E004 | — |
| m3.block3.expand.conv | Conv1x1 24 -> 72 | [B,72,16,16] | E002,E004 | features.3.block.0.0 |
| m3.block3.expand.bn | BatchNorm2d | [B,72,16,16] | E002,E009 | features.3.block.0.1 |
| m3.block3.expand.act | ReLU | [B,72,16,16] | E002,E004 | instance=features.3.block.0.2; no learned parameters |
| m3.block3.depthwise | Depthwise spatial convolution | [B,72,16,16] | E002,E004 | — |
| m3.block3.depthwise.conv | Conv3x3 72 -> 72 | [B,72,16,16] | E002,E004 | features.3.block.1.0 |
| m3.block3.depthwise.bn | BatchNorm2d | [B,72,16,16] | E002,E009 | features.3.block.1.1 |
| m3.block3.depthwise.act | ReLU | [B,72,16,16] | E002,E004 | instance=features.3.block.1.2; no learned parameters |
| m3.block3.project | Linear pointwise projection | [B,24,16,16] | E002,E004 | — |
| m3.block3.project.conv | Conv1x1 72 -> 24 | [B,24,16,16] | E002,E004 | features.3.block.2.0 |
| m3.block3.project.bn | BatchNorm2d | [B,24,16,16] | E002,E009 | features.3.block.2.1 |
| m3.block3.project.act | Identity | [B,24,16,16] | E002,E004 | instance=features.3.block.2.2; no learned parameters |
| m3.block3.add | Add identity input | [B,24,16,16] | E005 | — |
| m3.stage3 | Stage 3 / IR 4,5,6 | [B,40,8,8] | E009,E015 | — |
| m3.block4 | IR 4 / SE / ReLU / no skip | [B,40,8,8] | E015,E004,E005 | features.4.block |
| m3.block4.expand | Pointwise expansion | [B,72,16,16] | E002,E004 | — |
| m3.block4.expand.conv | Conv1x1 24 -> 72 | [B,72,16,16] | E002,E004 | features.4.block.0.0 |
| m3.block4.expand.bn | BatchNorm2d | [B,72,16,16] | E002,E009 | features.4.block.0.1 |
| m3.block4.expand.act | ReLU | [B,72,16,16] | E002,E004 | instance=features.4.block.0.2; no learned parameters |
| m3.block4.depthwise | Depthwise spatial convolution | [B,72,8,8] | E002,E004 | — |
| m3.block4.depthwise.conv | Conv5x5 72 -> 72 | [B,72,8,8] | E002,E004 | features.4.block.1.0 |
| m3.block4.depthwise.bn | BatchNorm2d | [B,72,8,8] | E002,E009 | features.4.block.1.1 |
| m3.block4.depthwise.act | ReLU | [B,72,8,8] | E002,E004 | instance=features.4.block.1.2; no learned parameters |
| m3.block4.se | Squeeze / excitation | [B,72,8,8] | E012,E013,E014 | features.4.block.2 |
| m3.block4.se.pool | Adaptive average pool 1x1 | [B,72,1,1] | E013 | — |
| m3.block4.se.fc1 | Conv1x1 72 -> 24 | [B,24,1,1] | E012,E013 | features.4.block.2.fc1 |
| m3.block4.se.relu | ReLU | [B,24,1,1] | E012,E013 | — |
| m3.block4.se.fc2 | Conv1x1 24 -> 72 | [B,72,1,1] | E012,E013 | features.4.block.2.fc2 |
| m3.block4.se.gate | Hardsigmoid channel gate | [B,72,1,1] | E013 | — |
| m3.block4.se.multiply | Scale * retained input | [B,72,8,8] | E014 | — |
| m3.block4.project | Linear pointwise projection | [B,40,8,8] | E002,E004 | — |
| m3.block4.project.conv | Conv1x1 72 -> 40 | [B,40,8,8] | E002,E004 | features.4.block.3.0 |
| m3.block4.project.bn | BatchNorm2d | [B,40,8,8] | E002,E009 | features.4.block.3.1 |
| m3.block4.project.act | Identity | [B,40,8,8] | E002,E004 | instance=features.4.block.3.2; no learned parameters |
| m3.block5 | IR 5 / SE / ReLU / skip | [B,40,8,8] | E015,E004,E005 | features.5.block |
| m3.block5.expand | Pointwise expansion | [B,120,8,8] | E002,E004 | — |
| m3.block5.expand.conv | Conv1x1 40 -> 120 | [B,120,8,8] | E002,E004 | features.5.block.0.0 |
| m3.block5.expand.bn | BatchNorm2d | [B,120,8,8] | E002,E009 | features.5.block.0.1 |
| m3.block5.expand.act | ReLU | [B,120,8,8] | E002,E004 | instance=features.5.block.0.2; no learned parameters |
| m3.block5.depthwise | Depthwise spatial convolution | [B,120,8,8] | E002,E004 | — |
| m3.block5.depthwise.conv | Conv5x5 120 -> 120 | [B,120,8,8] | E002,E004 | features.5.block.1.0 |
| m3.block5.depthwise.bn | BatchNorm2d | [B,120,8,8] | E002,E009 | features.5.block.1.1 |
| m3.block5.depthwise.act | ReLU | [B,120,8,8] | E002,E004 | instance=features.5.block.1.2; no learned parameters |
| m3.block5.se | Squeeze / excitation | [B,120,8,8] | E012,E013,E014 | features.5.block.2 |
| m3.block5.se.pool | Adaptive average pool 1x1 | [B,120,1,1] | E013 | — |
| m3.block5.se.fc1 | Conv1x1 120 -> 32 | [B,32,1,1] | E012,E013 | features.5.block.2.fc1 |
| m3.block5.se.relu | ReLU | [B,32,1,1] | E012,E013 | — |
| m3.block5.se.fc2 | Conv1x1 32 -> 120 | [B,120,1,1] | E012,E013 | features.5.block.2.fc2 |
| m3.block5.se.gate | Hardsigmoid channel gate | [B,120,1,1] | E013 | — |
| m3.block5.se.multiply | Scale * retained input | [B,120,8,8] | E014 | — |
| m3.block5.project | Linear pointwise projection | [B,40,8,8] | E002,E004 | — |
| m3.block5.project.conv | Conv1x1 120 -> 40 | [B,40,8,8] | E002,E004 | features.5.block.3.0 |
| m3.block5.project.bn | BatchNorm2d | [B,40,8,8] | E002,E009 | features.5.block.3.1 |
| m3.block5.project.act | Identity | [B,40,8,8] | E002,E004 | instance=features.5.block.3.2; no learned parameters |
| m3.block5.add | Add identity input | [B,40,8,8] | E005 | — |
| m3.block6 | IR 6 / SE / ReLU / skip | [B,40,8,8] | E015,E004,E005 | features.6.block |
| m3.block6.expand | Pointwise expansion | [B,120,8,8] | E002,E004 | — |
| m3.block6.expand.conv | Conv1x1 40 -> 120 | [B,120,8,8] | E002,E004 | features.6.block.0.0 |
| m3.block6.expand.bn | BatchNorm2d | [B,120,8,8] | E002,E009 | features.6.block.0.1 |
| m3.block6.expand.act | ReLU | [B,120,8,8] | E002,E004 | instance=features.6.block.0.2; no learned parameters |
| m3.block6.depthwise | Depthwise spatial convolution | [B,120,8,8] | E002,E004 | — |
| m3.block6.depthwise.conv | Conv5x5 120 -> 120 | [B,120,8,8] | E002,E004 | features.6.block.1.0 |
| m3.block6.depthwise.bn | BatchNorm2d | [B,120,8,8] | E002,E009 | features.6.block.1.1 |
| m3.block6.depthwise.act | ReLU | [B,120,8,8] | E002,E004 | instance=features.6.block.1.2; no learned parameters |
| m3.block6.se | Squeeze / excitation | [B,120,8,8] | E012,E013,E014 | features.6.block.2 |
| m3.block6.se.pool | Adaptive average pool 1x1 | [B,120,1,1] | E013 | — |
| m3.block6.se.fc1 | Conv1x1 120 -> 32 | [B,32,1,1] | E012,E013 | features.6.block.2.fc1 |
| m3.block6.se.relu | ReLU | [B,32,1,1] | E012,E013 | — |
| m3.block6.se.fc2 | Conv1x1 32 -> 120 | [B,120,1,1] | E012,E013 | features.6.block.2.fc2 |
| m3.block6.se.gate | Hardsigmoid channel gate | [B,120,1,1] | E013 | — |
| m3.block6.se.multiply | Scale * retained input | [B,120,8,8] | E014 | — |
| m3.block6.project | Linear pointwise projection | [B,40,8,8] | E002,E004 | — |
| m3.block6.project.conv | Conv1x1 120 -> 40 | [B,40,8,8] | E002,E004 | features.6.block.3.0 |
| m3.block6.project.bn | BatchNorm2d | [B,40,8,8] | E002,E009 | features.6.block.3.1 |
| m3.block6.project.act | Identity | [B,40,8,8] | E002,E004 | instance=features.6.block.3.2; no learned parameters |
| m3.block6.add | Add identity input | [B,40,8,8] | E005 | — |
| m3.stage4 | Stage 4 / IR 7,8,9,10 | [B,80,4,4] | E009,E015 | — |
| m3.block7 | IR 7 / Hardswish / no skip | [B,80,4,4] | E015,E004,E005 | features.7.block |
| m3.block7.expand | Pointwise expansion | [B,240,8,8] | E002,E004 | — |
| m3.block7.expand.conv | Conv1x1 40 -> 240 | [B,240,8,8] | E002,E004 | features.7.block.0.0 |
| m3.block7.expand.bn | BatchNorm2d | [B,240,8,8] | E002,E009 | features.7.block.0.1 |
| m3.block7.expand.act | Hardswish | [B,240,8,8] | E002,E004 | instance=features.7.block.0.2; no learned parameters |
| m3.block7.depthwise | Depthwise spatial convolution | [B,240,4,4] | E002,E004 | — |
| m3.block7.depthwise.conv | Conv3x3 240 -> 240 | [B,240,4,4] | E002,E004 | features.7.block.1.0 |
| m3.block7.depthwise.bn | BatchNorm2d | [B,240,4,4] | E002,E009 | features.7.block.1.1 |
| m3.block7.depthwise.act | Hardswish | [B,240,4,4] | E002,E004 | instance=features.7.block.1.2; no learned parameters |
| m3.block7.project | Linear pointwise projection | [B,80,4,4] | E002,E004 | — |
| m3.block7.project.conv | Conv1x1 240 -> 80 | [B,80,4,4] | E002,E004 | features.7.block.2.0 |
| m3.block7.project.bn | BatchNorm2d | [B,80,4,4] | E002,E009 | features.7.block.2.1 |
| m3.block7.project.act | Identity | [B,80,4,4] | E002,E004 | instance=features.7.block.2.2; no learned parameters |
| m3.block8 | IR 8 / Hardswish / skip | [B,80,4,4] | E015,E004,E005 | features.8.block |
| m3.block8.expand | Pointwise expansion | [B,200,4,4] | E002,E004 | — |
| m3.block8.expand.conv | Conv1x1 80 -> 200 | [B,200,4,4] | E002,E004 | features.8.block.0.0 |
| m3.block8.expand.bn | BatchNorm2d | [B,200,4,4] | E002,E009 | features.8.block.0.1 |
| m3.block8.expand.act | Hardswish | [B,200,4,4] | E002,E004 | instance=features.8.block.0.2; no learned parameters |
| m3.block8.depthwise | Depthwise spatial convolution | [B,200,4,4] | E002,E004 | — |
| m3.block8.depthwise.conv | Conv3x3 200 -> 200 | [B,200,4,4] | E002,E004 | features.8.block.1.0 |
| m3.block8.depthwise.bn | BatchNorm2d | [B,200,4,4] | E002,E009 | features.8.block.1.1 |
| m3.block8.depthwise.act | Hardswish | [B,200,4,4] | E002,E004 | instance=features.8.block.1.2; no learned parameters |
| m3.block8.project | Linear pointwise projection | [B,80,4,4] | E002,E004 | — |
| m3.block8.project.conv | Conv1x1 200 -> 80 | [B,80,4,4] | E002,E004 | features.8.block.2.0 |
| m3.block8.project.bn | BatchNorm2d | [B,80,4,4] | E002,E009 | features.8.block.2.1 |
| m3.block8.project.act | Identity | [B,80,4,4] | E002,E004 | instance=features.8.block.2.2; no learned parameters |
| m3.block8.add | Add identity input | [B,80,4,4] | E005 | — |
| m3.block9 | IR 9 / Hardswish / skip | [B,80,4,4] | E015,E004,E005 | features.9.block |
| m3.block9.expand | Pointwise expansion | [B,184,4,4] | E002,E004 | — |
| m3.block9.expand.conv | Conv1x1 80 -> 184 | [B,184,4,4] | E002,E004 | features.9.block.0.0 |
| m3.block9.expand.bn | BatchNorm2d | [B,184,4,4] | E002,E009 | features.9.block.0.1 |
| m3.block9.expand.act | Hardswish | [B,184,4,4] | E002,E004 | instance=features.9.block.0.2; no learned parameters |
| m3.block9.depthwise | Depthwise spatial convolution | [B,184,4,4] | E002,E004 | — |
| m3.block9.depthwise.conv | Conv3x3 184 -> 184 | [B,184,4,4] | E002,E004 | features.9.block.1.0 |
| m3.block9.depthwise.bn | BatchNorm2d | [B,184,4,4] | E002,E009 | features.9.block.1.1 |
| m3.block9.depthwise.act | Hardswish | [B,184,4,4] | E002,E004 | instance=features.9.block.1.2; no learned parameters |
| m3.block9.project | Linear pointwise projection | [B,80,4,4] | E002,E004 | — |
| m3.block9.project.conv | Conv1x1 184 -> 80 | [B,80,4,4] | E002,E004 | features.9.block.2.0 |
| m3.block9.project.bn | BatchNorm2d | [B,80,4,4] | E002,E009 | features.9.block.2.1 |
| m3.block9.project.act | Identity | [B,80,4,4] | E002,E004 | instance=features.9.block.2.2; no learned parameters |
| m3.block9.add | Add identity input | [B,80,4,4] | E005 | — |
| m3.block10 | IR 10 / Hardswish / skip | [B,80,4,4] | E015,E004,E005 | features.10.block |
| m3.block10.expand | Pointwise expansion | [B,184,4,4] | E002,E004 | — |
| m3.block10.expand.conv | Conv1x1 80 -> 184 | [B,184,4,4] | E002,E004 | features.10.block.0.0 |
| m3.block10.expand.bn | BatchNorm2d | [B,184,4,4] | E002,E009 | features.10.block.0.1 |
| m3.block10.expand.act | Hardswish | [B,184,4,4] | E002,E004 | instance=features.10.block.0.2; no learned parameters |
| m3.block10.depthwise | Depthwise spatial convolution | [B,184,4,4] | E002,E004 | — |
| m3.block10.depthwise.conv | Conv3x3 184 -> 184 | [B,184,4,4] | E002,E004 | features.10.block.1.0 |
| m3.block10.depthwise.bn | BatchNorm2d | [B,184,4,4] | E002,E009 | features.10.block.1.1 |
| m3.block10.depthwise.act | Hardswish | [B,184,4,4] | E002,E004 | instance=features.10.block.1.2; no learned parameters |
| m3.block10.project | Linear pointwise projection | [B,80,4,4] | E002,E004 | — |
| m3.block10.project.conv | Conv1x1 184 -> 80 | [B,80,4,4] | E002,E004 | features.10.block.2.0 |
| m3.block10.project.bn | BatchNorm2d | [B,80,4,4] | E002,E009 | features.10.block.2.1 |
| m3.block10.project.act | Identity | [B,80,4,4] | E002,E004 | instance=features.10.block.2.2; no learned parameters |
| m3.block10.add | Add identity input | [B,80,4,4] | E005 | — |
| m3.stage5 | Stage 5 / IR 11,12 | [B,112,4,4] | E009,E015 | — |
| m3.block11 | IR 11 / SE / Hardswish / no skip | [B,112,4,4] | E015,E004,E005 | features.11.block |
| m3.block11.expand | Pointwise expansion | [B,480,4,4] | E002,E004 | — |
| m3.block11.expand.conv | Conv1x1 80 -> 480 | [B,480,4,4] | E002,E004 | features.11.block.0.0 |
| m3.block11.expand.bn | BatchNorm2d | [B,480,4,4] | E002,E009 | features.11.block.0.1 |
| m3.block11.expand.act | Hardswish | [B,480,4,4] | E002,E004 | instance=features.11.block.0.2; no learned parameters |
| m3.block11.depthwise | Depthwise spatial convolution | [B,480,4,4] | E002,E004 | — |
| m3.block11.depthwise.conv | Conv3x3 480 -> 480 | [B,480,4,4] | E002,E004 | features.11.block.1.0 |
| m3.block11.depthwise.bn | BatchNorm2d | [B,480,4,4] | E002,E009 | features.11.block.1.1 |
| m3.block11.depthwise.act | Hardswish | [B,480,4,4] | E002,E004 | instance=features.11.block.1.2; no learned parameters |
| m3.block11.se | Squeeze / excitation | [B,480,4,4] | E012,E013,E014 | features.11.block.2 |
| m3.block11.se.pool | Adaptive average pool 1x1 | [B,480,1,1] | E013 | — |
| m3.block11.se.fc1 | Conv1x1 480 -> 120 | [B,120,1,1] | E012,E013 | features.11.block.2.fc1 |
| m3.block11.se.relu | ReLU | [B,120,1,1] | E012,E013 | — |
| m3.block11.se.fc2 | Conv1x1 120 -> 480 | [B,480,1,1] | E012,E013 | features.11.block.2.fc2 |
| m3.block11.se.gate | Hardsigmoid channel gate | [B,480,1,1] | E013 | — |
| m3.block11.se.multiply | Scale * retained input | [B,480,4,4] | E014 | — |
| m3.block11.project | Linear pointwise projection | [B,112,4,4] | E002,E004 | — |
| m3.block11.project.conv | Conv1x1 480 -> 112 | [B,112,4,4] | E002,E004 | features.11.block.3.0 |
| m3.block11.project.bn | BatchNorm2d | [B,112,4,4] | E002,E009 | features.11.block.3.1 |
| m3.block11.project.act | Identity | [B,112,4,4] | E002,E004 | instance=features.11.block.3.2; no learned parameters |
| m3.block12 | IR 12 / SE / Hardswish / skip | [B,112,4,4] | E015,E004,E005 | features.12.block |
| m3.block12.expand | Pointwise expansion | [B,672,4,4] | E002,E004 | — |
| m3.block12.expand.conv | Conv1x1 112 -> 672 | [B,672,4,4] | E002,E004 | features.12.block.0.0 |
| m3.block12.expand.bn | BatchNorm2d | [B,672,4,4] | E002,E009 | features.12.block.0.1 |
| m3.block12.expand.act | Hardswish | [B,672,4,4] | E002,E004 | instance=features.12.block.0.2; no learned parameters |
| m3.block12.depthwise | Depthwise spatial convolution | [B,672,4,4] | E002,E004 | — |
| m3.block12.depthwise.conv | Conv3x3 672 -> 672 | [B,672,4,4] | E002,E004 | features.12.block.1.0 |
| m3.block12.depthwise.bn | BatchNorm2d | [B,672,4,4] | E002,E009 | features.12.block.1.1 |
| m3.block12.depthwise.act | Hardswish | [B,672,4,4] | E002,E004 | instance=features.12.block.1.2; no learned parameters |
| m3.block12.se | Squeeze / excitation | [B,672,4,4] | E012,E013,E014 | features.12.block.2 |
| m3.block12.se.pool | Adaptive average pool 1x1 | [B,672,1,1] | E013 | — |
| m3.block12.se.fc1 | Conv1x1 672 -> 168 | [B,168,1,1] | E012,E013 | features.12.block.2.fc1 |
| m3.block12.se.relu | ReLU | [B,168,1,1] | E012,E013 | — |
| m3.block12.se.fc2 | Conv1x1 168 -> 672 | [B,672,1,1] | E012,E013 | features.12.block.2.fc2 |
| m3.block12.se.gate | Hardsigmoid channel gate | [B,672,1,1] | E013 | — |
| m3.block12.se.multiply | Scale * retained input | [B,672,4,4] | E014 | — |
| m3.block12.project | Linear pointwise projection | [B,112,4,4] | E002,E004 | — |
| m3.block12.project.conv | Conv1x1 672 -> 112 | [B,112,4,4] | E002,E004 | features.12.block.3.0 |
| m3.block12.project.bn | BatchNorm2d | [B,112,4,4] | E002,E009 | features.12.block.3.1 |
| m3.block12.project.act | Identity | [B,112,4,4] | E002,E004 | instance=features.12.block.3.2; no learned parameters |
| m3.block12.add | Add identity input | [B,112,4,4] | E005 | — |
| m3.stage6 | Stage 6 / IR 13,14,15 | [B,160,2,2] | E009,E015 | — |
| m3.block13 | IR 13 / SE / Hardswish / no skip | [B,160,2,2] | E015,E004,E005 | features.13.block |
| m3.block13.expand | Pointwise expansion | [B,672,4,4] | E002,E004 | — |
| m3.block13.expand.conv | Conv1x1 112 -> 672 | [B,672,4,4] | E002,E004 | features.13.block.0.0 |
| m3.block13.expand.bn | BatchNorm2d | [B,672,4,4] | E002,E009 | features.13.block.0.1 |
| m3.block13.expand.act | Hardswish | [B,672,4,4] | E002,E004 | instance=features.13.block.0.2; no learned parameters |
| m3.block13.depthwise | Depthwise spatial convolution | [B,672,2,2] | E002,E004 | — |
| m3.block13.depthwise.conv | Conv5x5 672 -> 672 | [B,672,2,2] | E002,E004 | features.13.block.1.0 |
| m3.block13.depthwise.bn | BatchNorm2d | [B,672,2,2] | E002,E009 | features.13.block.1.1 |
| m3.block13.depthwise.act | Hardswish | [B,672,2,2] | E002,E004 | instance=features.13.block.1.2; no learned parameters |
| m3.block13.se | Squeeze / excitation | [B,672,2,2] | E012,E013,E014 | features.13.block.2 |
| m3.block13.se.pool | Adaptive average pool 1x1 | [B,672,1,1] | E013 | — |
| m3.block13.se.fc1 | Conv1x1 672 -> 168 | [B,168,1,1] | E012,E013 | features.13.block.2.fc1 |
| m3.block13.se.relu | ReLU | [B,168,1,1] | E012,E013 | — |
| m3.block13.se.fc2 | Conv1x1 168 -> 672 | [B,672,1,1] | E012,E013 | features.13.block.2.fc2 |
| m3.block13.se.gate | Hardsigmoid channel gate | [B,672,1,1] | E013 | — |
| m3.block13.se.multiply | Scale * retained input | [B,672,2,2] | E014 | — |
| m3.block13.project | Linear pointwise projection | [B,160,2,2] | E002,E004 | — |
| m3.block13.project.conv | Conv1x1 672 -> 160 | [B,160,2,2] | E002,E004 | features.13.block.3.0 |
| m3.block13.project.bn | BatchNorm2d | [B,160,2,2] | E002,E009 | features.13.block.3.1 |
| m3.block13.project.act | Identity | [B,160,2,2] | E002,E004 | instance=features.13.block.3.2; no learned parameters |
| m3.block14 | IR 14 / SE / Hardswish / skip | [B,160,2,2] | E015,E004,E005 | features.14.block |
| m3.block14.expand | Pointwise expansion | [B,960,2,2] | E002,E004 | — |
| m3.block14.expand.conv | Conv1x1 160 -> 960 | [B,960,2,2] | E002,E004 | features.14.block.0.0 |
| m3.block14.expand.bn | BatchNorm2d | [B,960,2,2] | E002,E009 | features.14.block.0.1 |
| m3.block14.expand.act | Hardswish | [B,960,2,2] | E002,E004 | instance=features.14.block.0.2; no learned parameters |
| m3.block14.depthwise | Depthwise spatial convolution | [B,960,2,2] | E002,E004 | — |
| m3.block14.depthwise.conv | Conv5x5 960 -> 960 | [B,960,2,2] | E002,E004 | features.14.block.1.0 |
| m3.block14.depthwise.bn | BatchNorm2d | [B,960,2,2] | E002,E009 | features.14.block.1.1 |
| m3.block14.depthwise.act | Hardswish | [B,960,2,2] | E002,E004 | instance=features.14.block.1.2; no learned parameters |
| m3.block14.se | Squeeze / excitation | [B,960,2,2] | E012,E013,E014 | features.14.block.2 |
| m3.block14.se.pool | Adaptive average pool 1x1 | [B,960,1,1] | E013 | — |
| m3.block14.se.fc1 | Conv1x1 960 -> 240 | [B,240,1,1] | E012,E013 | features.14.block.2.fc1 |
| m3.block14.se.relu | ReLU | [B,240,1,1] | E012,E013 | — |
| m3.block14.se.fc2 | Conv1x1 240 -> 960 | [B,960,1,1] | E012,E013 | features.14.block.2.fc2 |
| m3.block14.se.gate | Hardsigmoid channel gate | [B,960,1,1] | E013 | — |
| m3.block14.se.multiply | Scale * retained input | [B,960,2,2] | E014 | — |
| m3.block14.project | Linear pointwise projection | [B,160,2,2] | E002,E004 | — |
| m3.block14.project.conv | Conv1x1 960 -> 160 | [B,160,2,2] | E002,E004 | features.14.block.3.0 |
| m3.block14.project.bn | BatchNorm2d | [B,160,2,2] | E002,E009 | features.14.block.3.1 |
| m3.block14.project.act | Identity | [B,160,2,2] | E002,E004 | instance=features.14.block.3.2; no learned parameters |
| m3.block14.add | Add identity input | [B,160,2,2] | E005 | — |
| m3.block15 | IR 15 / SE / Hardswish / skip | [B,160,2,2] | E015,E004,E005 | features.15.block |
| m3.block15.expand | Pointwise expansion | [B,960,2,2] | E002,E004 | — |
| m3.block15.expand.conv | Conv1x1 160 -> 960 | [B,960,2,2] | E002,E004 | features.15.block.0.0 |
| m3.block15.expand.bn | BatchNorm2d | [B,960,2,2] | E002,E009 | features.15.block.0.1 |
| m3.block15.expand.act | Hardswish | [B,960,2,2] | E002,E004 | instance=features.15.block.0.2; no learned parameters |
| m3.block15.depthwise | Depthwise spatial convolution | [B,960,2,2] | E002,E004 | — |
| m3.block15.depthwise.conv | Conv5x5 960 -> 960 | [B,960,2,2] | E002,E004 | features.15.block.1.0 |
| m3.block15.depthwise.bn | BatchNorm2d | [B,960,2,2] | E002,E009 | features.15.block.1.1 |
| m3.block15.depthwise.act | Hardswish | [B,960,2,2] | E002,E004 | instance=features.15.block.1.2; no learned parameters |
| m3.block15.se | Squeeze / excitation | [B,960,2,2] | E012,E013,E014 | features.15.block.2 |
| m3.block15.se.pool | Adaptive average pool 1x1 | [B,960,1,1] | E013 | — |
| m3.block15.se.fc1 | Conv1x1 960 -> 240 | [B,240,1,1] | E012,E013 | features.15.block.2.fc1 |
| m3.block15.se.relu | ReLU | [B,240,1,1] | E012,E013 | — |
| m3.block15.se.fc2 | Conv1x1 240 -> 960 | [B,960,1,1] | E012,E013 | features.15.block.2.fc2 |
| m3.block15.se.gate | Hardsigmoid channel gate | [B,960,1,1] | E013 | — |
| m3.block15.se.multiply | Scale * retained input | [B,960,2,2] | E014 | — |
| m3.block15.project | Linear pointwise projection | [B,160,2,2] | E002,E004 | — |
| m3.block15.project.conv | Conv1x1 960 -> 160 | [B,160,2,2] | E002,E004 | features.15.block.3.0 |
| m3.block15.project.bn | BatchNorm2d | [B,160,2,2] | E002,E009 | features.15.block.3.1 |
| m3.block15.project.act | Identity | [B,160,2,2] | E002,E004 | instance=features.15.block.3.2; no learned parameters |
| m3.block15.add | Add identity input | [B,160,2,2] | E005 | — |
| m3.last | Final pointwise / Hardswish | [B,960,2,2] | E002,E009 | — |
| m3.last.conv | Conv1x1 160 -> 960 | [B,960,2,2] | E002,E009 | features.16.0 |
| m3.last.bn | BatchNorm2d | [B,960,2,2] | E002,E009 | features.16.1 |
| m3.last.act | Hardswish | [B,960,2,2] | E002,E009 | instance=features.16.2; no learned parameters |
| m3.head | CIFAR-10 classifier | logits: [B,10] | E009,E010,E001 | — |
| m3.pool | Adaptive average pool 1x1 | [B,960,1,1] | E009,E010 | instance=avgpool; no learned parameters |
| m3.flatten | Flatten from dimension 1 | [B,960] | E010 | — |
| m3.fc1 | Linear 960 -> 1280 | [B,1280] | E009,E010 | classifier.0 |
| m3.head_act | Hardswish | [B,1280] | E009,E010 | instance=classifier.1; no learned parameters |
| m3.dropout | Dropout 0.2 / eval identity | [B,1280] | E009,E010,E001 | instance=classifier.2; no learned parameters |
| m3.fc2 | Replaced Linear 1280 -> 10 | logits: [B,10] | E009,E010,E001 | classifier.3 |
| m3.output | Returned logits | [B,10] | E010,E011 | — |

## 与教科书/通用基础图的区别

- Do not substitute modern torchvision source or MobileNetV2 merely because the checkpoint filename contains v2.
- Do not copy224 input or1000-class output: selected Notebook uses64x64 CIFAR images and a replaced10-class head.
- The final feature width is960, not1280;1280 is the hidden classifier width in this Large configuration.
- SE gate is Hardsigmoid, not Sigmoid/Softmax, and its reduction uses _make_divisible rather than an unrounded C/4.
- Project has Identity rather than ReLU/Hardswish; do not add a projection shortcut to stride2/channel-changing blocks.
- SE multiplication retains depthwise features while the residual Add retains the block input; these two routes refer to different tensors.

## 源码事实与边界

- Notebook cell12 chooses torchvision v0.9.0 Large, pretrained=False, then replaces classifier[-1] with Linear(1280,10); cell14 explicitly selects eval.
- Independent snapshots preserve the Notebook caller and the exact imported library implementation; the caller checkpoint filename mentions v2 but its construction is V3.
- The 15 InvertedResidual configs are [cin,kernel,expanded,cout,se,activation,stride,dilation], with width1, no reduced tail and dilation1.
- Stem is3->16, Hardswish, stride2; logical output-channel stages are16,24,40,80,112,160 with64-crop spatial sizes32,16,8,4,4,2.
- Expansion is omitted only when expanded==cin (IR1); depthwise groups equals expanded channels.
- RE means ReLU; HS means Hardswish. Each project is Conv1x1+BN+Identity, followed by identity Add only for stride1 with equal input/output channels.
- Eight SE blocks use rounded squeeze width, pool->Conv1x1->ReLU->Conv1x1->Hardsigmoid->broadcast scale*retained depthwise features, before projection.
- Ten original-input residual Adds have no following activation; all blocks have independent feature-index parameter scopes.
- Final Conv160->960 precedes pool1, flatten fromdim1, Linear960->1280, Hardswish, Dropout.2 and replacement Linear1280->10; model returns logits only.
- Every block and operator remains in semantic IR. Detailed rendering expands IR1(no expansion), IR4(SE/ReLU/no skip), IR12(SE/Hardswish/skip); other blocks retain exact config and parameter identities in folded boxes.
