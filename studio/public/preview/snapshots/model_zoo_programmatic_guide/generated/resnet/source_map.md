# ResNet18：源码与图框对应

来源：`rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E009 | [deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py](sources/deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py) · `conv3x3` | 99–102 | [15] |
| E001 | [deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py](sources/deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py) · `BasicBlock` | 105–134 | [15] |
| E002 | [deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py](sources/deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py) · `BasicBlock.__init__` | 108–116 | [15] |
| E003 | [deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py](sources/deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py) · `BasicBlock.forward` | 118–134 | [15] |
| E004 | [deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py](sources/deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py) · `ResNet` | 139–202 | [15] |
| E005 | [deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py](sources/deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py) · `ResNet.__init__` | 141–166 | [15] |
| E006 | [deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py](sources/deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py) · `ResNet._make_layer` | 168–183 | [15] |
| E007 | [deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py](sources/deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py) · `ResNet.forward` | 185–202 | [15] |
| E010 | [deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py](sources/deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py) · `resnet18` | 206–212 | [15] |
| E008 | [deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py](sources/deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py) · `compute_accuracy` | 223–234 | [18] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| resnet.model | ResNet18 · MNIST | 2 x [B,10] | E010,E004 | — |
| resnet.input | MNIST image | [B,1,28,28] | E007 | — |
| resnet.stem | Convolutional stem | [B,64,7,7] | E005,E007 | — |
| resnet.stem.conv | Conv2d 1 -> 64 | [B,64,14,14] | E005,E007 | conv1 |
| resnet.stem.bn | BatchNorm2d | [B,64,14,14] | E005,E007 | bn1 |
| resnet.stem.relu | ReLU | [B,64,14,14] | E007 | — |
| resnet.stem.pool | MaxPool2d | [B,64,7,7] | E005,E007 | — |
| resnet.stage1 | Stage 1 · 64 channels | [B,64,7,7] | E005,E006,E007 | — |
| resnet.stage1.identity | Identity block x 2 | [B,64,7,7] | E006,E002,E003 | layer1.{i}; {'count': 2, 'index': 'i', 'independent_parameters': True} |
| resnet.stage1.identity.residual | Two convolutions + identity | [B,64,7,7] | E003 | — |
| resnet.stage1.identity.conv1 | Conv2d 3x3 | [B,64,7,7] | E009,E002,E003 | layer1.{i}.conv1 |
| resnet.stage1.identity.bn1 | BatchNorm2d | [B,64,7,7] | E002,E003 | layer1.{i}.bn1 |
| resnet.stage1.identity.relu1 | ReLU | [B,64,7,7] | E003 | — |
| resnet.stage1.identity.conv2 | Conv2d 3x3 | [B,64,7,7] | E009,E002,E003 | layer1.{i}.conv2 |
| resnet.stage1.identity.bn2 | BatchNorm2d | [B,64,7,7] | E002,E003 | layer1.{i}.bn2 |
| resnet.stage1.identity.add | Add identity | [B,64,7,7] | E003 | — |
| resnet.stage1.identity.relu2 | ReLU after Add | [B,64,7,7] | E003 | — |
| resnet.stage2 | Stage 2 · 128 channels | [B,128,4,4] | E005,E006,E007 | — |
| resnet.stage2.downsample | Downsampling block | [B,128,4,4] | E006,E002,E003 | layer2.0 |
| resnet.stage2.downsample.paths | Main / projected shortcut | two matching Add operands | E006,E003 | — |
| resnet.stage2.downsample.main | Main convolution path | [B,128,4,4] | E002,E003 | — |
| resnet.stage2.downsample.conv1 | Conv2d 3x3 / stride 2 | [B,128,4,4] | E009,E002,E003 | layer2.0.conv1 |
| resnet.stage2.downsample.bn1 | BatchNorm2d | [B,128,4,4] | E002,E003 | layer2.0.bn1 |
| resnet.stage2.downsample.relu1 | ReLU | [B,128,4,4] | E003 | — |
| resnet.stage2.downsample.conv2 | Conv2d 3x3 / stride 1 | [B,128,4,4] | E009,E002,E003 | layer2.0.conv2 |
| resnet.stage2.downsample.bn2 | BatchNorm2d | [B,128,4,4] | E002,E003 | layer2.0.bn2 |
| resnet.stage2.downsample.shortcut | Projection shortcut | [B,128,4,4] | E006,E003 | — |
| resnet.stage2.downsample.proj_conv | Conv2d 1x1 / stride 2 | [B,128,4,4] | E006,E003 | layer2.0.downsample.0 |
| resnet.stage2.downsample.proj_bn | BatchNorm2d | [B,128,4,4] | E006,E003 | layer2.0.downsample.1 |
| resnet.stage2.downsample.add | Add two paths | [B,128,4,4] | E003 | — |
| resnet.stage2.downsample.relu2 | ReLU after Add | [B,128,4,4] | E003 | — |
| resnet.stage2.identity | Identity block x 1 | [B,128,4,4] | E006,E002,E003 | layer2.1; {'count': 1, 'independent_parameters': True} |
| resnet.stage3 | Stage 3 · 256 channels | [B,256,2,2] | E005,E006,E007 | — |
| resnet.stage3.downsample | Downsampling block | [B,256,2,2] | E006,E002,E003 | layer3.0 |
| resnet.stage3.downsample.paths | Main / projected shortcut | two matching Add operands | E006,E003 | — |
| resnet.stage3.downsample.main | Main convolution path | [B,256,2,2] | E002,E003 | — |
| resnet.stage3.downsample.conv1 | Conv2d 3x3 / stride 2 | [B,256,2,2] | E009,E002,E003 | layer3.0.conv1 |
| resnet.stage3.downsample.bn1 | BatchNorm2d | [B,256,2,2] | E002,E003 | layer3.0.bn1 |
| resnet.stage3.downsample.relu1 | ReLU | [B,256,2,2] | E003 | — |
| resnet.stage3.downsample.conv2 | Conv2d 3x3 / stride 1 | [B,256,2,2] | E009,E002,E003 | layer3.0.conv2 |
| resnet.stage3.downsample.bn2 | BatchNorm2d | [B,256,2,2] | E002,E003 | layer3.0.bn2 |
| resnet.stage3.downsample.shortcut | Projection shortcut | [B,256,2,2] | E006,E003 | — |
| resnet.stage3.downsample.proj_conv | Conv2d 1x1 / stride 2 | [B,256,2,2] | E006,E003 | layer3.0.downsample.0 |
| resnet.stage3.downsample.proj_bn | BatchNorm2d | [B,256,2,2] | E006,E003 | layer3.0.downsample.1 |
| resnet.stage3.downsample.add | Add two paths | [B,256,2,2] | E003 | — |
| resnet.stage3.downsample.relu2 | ReLU after Add | [B,256,2,2] | E003 | — |
| resnet.stage3.identity | Identity block x 1 | [B,256,2,2] | E006,E002,E003 | layer3.1; {'count': 1, 'independent_parameters': True} |
| resnet.stage4 | Stage 4 · 512 channels | [B,512,1,1] | E005,E006,E007 | — |
| resnet.stage4.downsample | Downsampling block | [B,512,1,1] | E006,E002,E003 | layer4.0 |
| resnet.stage4.downsample.paths | Main / projected shortcut | two matching Add operands | E006,E003 | — |
| resnet.stage4.downsample.main | Main convolution path | [B,512,1,1] | E002,E003 | — |
| resnet.stage4.downsample.conv1 | Conv2d 3x3 / stride 2 | [B,512,1,1] | E009,E002,E003 | layer4.0.conv1 |
| resnet.stage4.downsample.bn1 | BatchNorm2d | [B,512,1,1] | E002,E003 | layer4.0.bn1 |
| resnet.stage4.downsample.relu1 | ReLU | [B,512,1,1] | E003 | — |
| resnet.stage4.downsample.conv2 | Conv2d 3x3 / stride 1 | [B,512,1,1] | E009,E002,E003 | layer4.0.conv2 |
| resnet.stage4.downsample.bn2 | BatchNorm2d | [B,512,1,1] | E002,E003 | layer4.0.bn2 |
| resnet.stage4.downsample.shortcut | Projection shortcut | [B,512,1,1] | E006,E003 | — |
| resnet.stage4.downsample.proj_conv | Conv2d 1x1 / stride 2 | [B,512,1,1] | E006,E003 | layer4.0.downsample.0 |
| resnet.stage4.downsample.proj_bn | BatchNorm2d | [B,512,1,1] | E006,E003 | layer4.0.downsample.1 |
| resnet.stage4.downsample.add | Add two paths | [B,512,1,1] | E003 | — |
| resnet.stage4.downsample.relu2 | ReLU after Add | [B,512,1,1] | E003 | — |
| resnet.stage4.identity | Identity block x 1 | [B,512,1,1] | E006,E002,E003 | layer4.1; {'count': 1, 'independent_parameters': True} |
| resnet.head | Classification head | 2 x [B,10] | E005,E007 | — |
| resnet.flatten | Flatten | [B,512] | E007 | — |
| resnet.fc | Linear 512 -> 10 | [B,10] | E005,E007 | fc |
| resnet.returns | Return logits / probabilities | (logits, probas) | E007 | — |
| resnet.logits | Logits | [B,10] | E007 | — |
| resnet.softmax | Softmax | [B,10] | E007 | — |
| resnet.output | Forward return tuple | 2 x [B,10] | E007 | — |

## 与教科书/通用基础图的区别

- No model-specific reference PNG was supplied for this notebook; the diagram follows the reviewed code and shared Transformer visual theme.
- Do not copy an ImageNet ResNet diagram's 224x224 input or global average-pool path into this MNIST implementation.
- The 1x1 projection shortcuts are parameterized computations, not identity bypasses, and must be drawn before Add.
- Final ReLU follows residual addition; BatchNorm follows both convolutions, including the second convolution before Add.
- An attribute appearing in __init__ is not sufficient evidence for an executed operator: the unused avgpool is recorded in notes, not as a forward node.
- Independent source operands are routed from their actual producers; a display scope does not invent a Python tuple or shared-value fork.

## 源码事实与边界

- resnet18 constructs ResNet(BasicBlock, [2,2,2,2], NUM_CLASSES=10, GRAYSCALE=True); the factory actually reads these module globals.
- Input [B,1,28,28] passes through 7x7 stride2 convolution to 14x14, then 3x3 stride2 MaxPool to 7x7.
- Stage spatial sizes are 7,4,2,1 with channels 64,128,256,512; stride2 occurs only in the first block of stages 2-4.
- A BasicBlock applies Conv-BN-ReLU-Conv-BN, adds the shortcut, then applies a second ReLU. It is not a pre-activation block.
- Stages 2-4 use independent 1x1 stride2 Conv + BN shortcuts in their first block; parallel path collection precedes a separate arithmetic Add.
- Each stage contains two independent parameter sets; the repeated identity template in stage1 denotes layer1.0 and layer1.1, not tied weights.
- AvgPool2d(7) is constructed but not called by forward; after stage4 MNIST is already 1x1, so flatten yields 512 values.
- BatchNorm2d is retained in the eval graph and uses running statistics; Softmax is called inside forward, which returns both logits and probas.
