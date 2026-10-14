# ResNet101 (CIFAR-10 notebook)：源码与图框对应

来源：`https://github.com/rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E009 | [deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py](sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py) · `conv3x3` | 119–122 | [15] |
| E001 | [deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py](sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py) · `Bottleneck` | 125–161 | [15] |
| E002 | [deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py](sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py) · `Bottleneck.__init__` | 128–139 | [15] |
| E003 | [deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py](sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py) · `Bottleneck.forward` | 141–161 | [15] |
| E004 | [deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py](sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py) · `ResNet` | 166–228 | [15] |
| E005 | [deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py](sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py) · `ResNet.__init__` | 168–194 | [15] |
| E006 | [deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py](sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py) · `ResNet._make_layer` | 196–211 | [15] |
| E007 | [deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py](sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py) · `ResNet.forward` | 213–228 | [15] |
| E010 | [deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py](sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py) · `resnet101` | 232–238 | [15] |
| E008 | [deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py](sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py) · `compute_accuracy` | 253–264 | [18] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| r101.root | ResNet101 · CIFAR-10 | 2 x [B,10] | E010,E004 | — |
| r101.input | CIFAR-10 image | [B,3,32,32] | E007 | — |
| r101.stem | Conv stem | [B,64,8,8] | E005,E007 | — |
| r101.stem.conv | Conv7x7 3 ->64 / s2 | [B,64,16,16] | E005,E007 | conv1 |
| r101.stem.bn | BatchNorm2d | [B,64,16,16] | E005,E007 | bn1 |
| r101.stem.relu | ReLU | [B,64,16,16] | E007 | — |
| r101.stem.pool | MaxPool3x3 / s2 | [B,64,8,8] | E005,E007 | — |
| r101.stage1 | Stage1 · 3 Bottlenecks | [B,256,8,8] | E005,E006,E007 | layer1 |
| r101.stage1.first | First Bottleneck · projection | [B,256,8,8] | E002,E003,E006 | layer1.0 |
| r101.stage1.first.paths | Main / projected shortcut | two matching operands | E006,E003 | — |
| r101.stage1.first.main | Bottleneck convolution path | [B,256,8,8] | E002,E003 | — |
| r101.stage1.first.main.conv1 | Conv1x1 64 -> 64 | [B,64,8,8] | E002 | layer1.0.conv1 |
| r101.stage1.first.main.bn1 | BatchNorm2d | [B,64,8,8] | E002 | layer1.0.bn1 |
| r101.stage1.first.main.relu1 | ReLU | [B,64,8,8] | E003 | — |
| r101.stage1.first.main.conv2 | Conv3x3 64 -> 64 | [B,64,8,8] | E002 | layer1.0.conv2 |
| r101.stage1.first.main.bn2 | BatchNorm2d | [B,64,8,8] | E002 | layer1.0.bn2 |
| r101.stage1.first.main.relu2 | ReLU | [B,64,8,8] | E003 | — |
| r101.stage1.first.main.conv3 | Conv1x1 64 -> 256 | [B,256,8,8] | E002 | layer1.0.conv3 |
| r101.stage1.first.main.bn3 | BatchNorm2d | [B,256,8,8] | E002 | layer1.0.bn3 |
| r101.stage1.first.shortcut | Projection shortcut | [B,256,8,8] | E006,E003 | — |
| r101.stage1.first.projection | Conv1x1 64 -> 256 / s1 | [B,256,8,8] | E006,E003 | layer1.0.downsample.0 |
| r101.stage1.first.projection_bn | BatchNorm2d | [B,256,8,8] | E006,E003 | layer1.0.downsample.1 |
| r101.stage1.first.add | Add two paths | [B,256,8,8] | E003 | — |
| r101.stage1.first.relu3 | ReLU | [B,256,8,8] | E003 | — |
| r101.stage1.identities | Identity Bottleneck x 2 | [B,256,8,8] | E006,E002,E003 | layer1.{j}; {'count': 2, 'index': 'j', 'instance_indices': [1, 2], 'independent_parameters': True} |
| r101.stage1.identities.main | Three convolutions + identity | [B,256,8,8] | E002,E003 | — |
| r101.stage1.identities.main.conv1 | Conv1x1 256 -> 64 | [B,64,8,8] | E002 | layer1.{j}.conv1 |
| r101.stage1.identities.main.bn1 | BatchNorm2d | [B,64,8,8] | E002 | layer1.{j}.bn1 |
| r101.stage1.identities.main.relu1 | ReLU | [B,64,8,8] | E003 | — |
| r101.stage1.identities.main.conv2 | Conv3x3 64 -> 64 | [B,64,8,8] | E002 | layer1.{j}.conv2 |
| r101.stage1.identities.main.bn2 | BatchNorm2d | [B,64,8,8] | E002 | layer1.{j}.bn2 |
| r101.stage1.identities.main.relu2 | ReLU | [B,64,8,8] | E003 | — |
| r101.stage1.identities.main.conv3 | Conv1x1 64 -> 256 | [B,256,8,8] | E002 | layer1.{j}.conv3 |
| r101.stage1.identities.main.bn3 | BatchNorm2d | [B,256,8,8] | E002 | layer1.{j}.bn3 |
| r101.stage1.identities.add | Add identity input | [B,256,8,8] | E003 | — |
| r101.stage1.identities.relu3 | ReLU | [B,256,8,8] | E003 | — |
| r101.stage2 | Stage2 · 4 Bottlenecks | [B,512,4,4] | E005,E006,E007 | layer2 |
| r101.stage2.first | First Bottleneck · projection | [B,512,4,4] | E002,E003,E006 | layer2.0 |
| r101.stage2.first.paths | Main / projected shortcut | two matching operands | E006,E003 | — |
| r101.stage2.first.main | Bottleneck convolution path | [B,512,4,4] | E002,E003 | — |
| r101.stage2.first.main.conv1 | Conv1x1 256 -> 128 | [B,128,8,8] | E002 | layer2.0.conv1 |
| r101.stage2.first.main.bn1 | BatchNorm2d | [B,128,8,8] | E002 | layer2.0.bn1 |
| r101.stage2.first.main.relu1 | ReLU | [B,128,8,8] | E003 | — |
| r101.stage2.first.main.conv2 | Conv3x3 128 -> 128 / s2 | [B,128,4,4] | E002 | layer2.0.conv2 |
| r101.stage2.first.main.bn2 | BatchNorm2d | [B,128,4,4] | E002 | layer2.0.bn2 |
| r101.stage2.first.main.relu2 | ReLU | [B,128,4,4] | E003 | — |
| r101.stage2.first.main.conv3 | Conv1x1 128 -> 512 | [B,512,4,4] | E002 | layer2.0.conv3 |
| r101.stage2.first.main.bn3 | BatchNorm2d | [B,512,4,4] | E002 | layer2.0.bn3 |
| r101.stage2.first.shortcut | Projection shortcut | [B,512,4,4] | E006,E003 | — |
| r101.stage2.first.projection | Conv1x1 256 -> 512 / s2 | [B,512,4,4] | E006,E003 | layer2.0.downsample.0 |
| r101.stage2.first.projection_bn | BatchNorm2d | [B,512,4,4] | E006,E003 | layer2.0.downsample.1 |
| r101.stage2.first.add | Add two paths | [B,512,4,4] | E003 | — |
| r101.stage2.first.relu3 | ReLU | [B,512,4,4] | E003 | — |
| r101.stage2.identities | Identity Bottleneck x 3 | [B,512,4,4] | E006,E002,E003 | layer2.{j}; {'count': 3, 'index': 'j', 'instance_indices': [1, 2, 3], 'independent_parameters': True} |
| r101.stage3 | Stage3 · 23 Bottlenecks | [B,1024,2,2] | E005,E006,E007 | layer3 |
| r101.stage3.first | First Bottleneck · projection | [B,1024,2,2] | E006,E002,E003 | layer3.0 |
| r101.stage3.identities | Identity Bottleneck x 22 | [B,1024,2,2] | E006,E002,E003 | layer3.{j}; {'count': 22, 'index': 'j', 'instance_indices': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22], 'independent_parameters': True} |
| r101.stage4 | Stage4 · 3 Bottlenecks | [B,2048,1,1] | E005,E006,E007 | layer4 |
| r101.stage4.first | First Bottleneck · projection | [B,2048,1,1] | E006,E002,E003 | layer4.0 |
| r101.stage4.identities | Identity Bottleneck x 2 | [B,2048,1,1] | E006,E002,E003 | layer4.{j}; {'count': 2, 'index': 'j', 'instance_indices': [1, 2], 'independent_parameters': True} |
| r101.head | Classifier head | 2 x [B,10] | E005,E007 | — |
| r101.flatten | Flatten | [B,2048] | E007 | — |
| r101.fc | Linear2048 ->10 | [B,10] | E005,E007 | fc |
| r101.returns | Return logits / probabilities | (logits, probas) | E007 | — |
| r101.logits | Retain logits | [B,10] | E007 | — |
| r101.softmax | Softmax | [B,10] | E007 | — |
| r101.output | Forward return tuple | 2 x [B,10] | E007 | — |

## 与教科书/通用基础图的区别

- Preserve the real resnet101 factory and its [3,4,23,3] counts, not the earlier [3,4,6,3] model.
- Do not label the selected source caller eval: no_grad leaves BN in train mode and compute_accuracy does not call eval.
- Use CIFAR-10 RGB32x32 rather than MNIST grayscale or ImageNet224x224; do not add executed average pooling.
- Draw stage1 projection despite stride1: expansion4 changes64 channels to256.
- Place downsampling in the3x3 conv2 and the shortcut1x1, not in the main conv1.
- Draw Bottleneck three-convolution structure, not ResNet18's two-convolution BasicBlock.
- Final ReLU follows residual Add; BN follows conv3 before Add; preserve both forward return fields.

## 源码事实与边界

- The actual resnet101 factory constructs33 Bottleneck(expansion4) blocks with [3,4,23,3]; stage3 has23 independent blocks.
- The factory reads global NUM_CLASSES=10 instead of its num_classes parameter, but actually uses its grayscale argument (False in caller).
- The source never calls model.eval(): model.train() stays active during compute_accuracy; no_grad does not change BatchNorm mode.
- Input[B,3,32,32] becomes64x16x16 after7x7 stride2 Conv, then64x8x8 after3x3 stride2 MaxPool.
- Four stages contain3,4,23,3 independent Bottlenecks, with output channels256,512,1024,2048 and spatial sizes8,4,2,1.
- Each Bottleneck executes Conv1x1-BN-ReLU ->Conv3x3-BN-ReLU ->Conv1x1-BN ->Add shortcut ->ReLU.
- Stride2 is on conv2, not conv1; projection shortcut uses matching stride. Stage1 also requires projection because64!=64*4 even at stride1.
- There are4 learned projection shortcuts and29 identity shortcuts; no across-block weight sharing.
- AvgPool2d(7,stride1,padding2) exists in __init__ but its forward call is commented; flatten directly receives2048x1x1.
- The classifier is Linear2048->10; forward computes Softmax and returns logits and probas.
- Stage1 projection/identity and stage2 downsampling projection expand as representative patterns; later templates preserve instance counts, scopes and parameter members.
