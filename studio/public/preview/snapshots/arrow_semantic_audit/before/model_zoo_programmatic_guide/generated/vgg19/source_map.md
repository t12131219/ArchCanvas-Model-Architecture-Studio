# VGG19-type (source class VGG16)：源码与图框对应

来源：`https://github.com/rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-vgg19.py](sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-vgg19.py) · `VGG16` | 71–234 | [10] |
| E002 | [deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-vgg19.py](sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-vgg19.py) · `VGG16.__init__` | 73–221 | [10] |
| E003 | [deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-vgg19.py](sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-vgg19.py) · `VGG16.forward` | 224–234 | [10] |
| E004 | [deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-vgg19.py](sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-vgg19.py) · `compute_accuracy` | 246–258 | [12] |
| E005 | [deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-vgg19.py](sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-vgg19.py) · `compute_epoch_loss` | 261–274 | [12] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| v19.root | VGG19-type · CIFAR-10 | 2 x [B,10] | E001 | — |
| v19.input | CIFAR-10 image | [B,3,32,32] | E003 | — |
| v19.features | Five convolutional blocks | [B,512,1,1] | E002,E003 | — |
| v19.block1 | Block 1 · 2 Conv/ReLU pairs | [B,64,16,16] | E002,E003 | block_1 |
| v19.block1.conv1 | Conv2d 3 -> 64 | [B,64,32,32] | E002,E003 | block_1.0 |
| v19.block1.relu1 | ReLU | [B,64,32,32] | E002,E003 | — |
| v19.block1.conv2 | Conv2d 64 -> 64 | [B,64,32,32] | E002,E003 | block_1.2 |
| v19.block1.relu2 | ReLU | [B,64,32,32] | E002,E003 | — |
| v19.block1.pool | MaxPool2d 2x2 / 2 | [B,64,16,16] | E002,E003 | — |
| v19.block2 | Block 2 · 2 Conv/ReLU pairs | [B,128,8,8] | E002,E003 | block_2 |
| v19.block2.conv1 | Conv2d 64 -> 128 | [B,128,16,16] | E002,E003 | block_2.0 |
| v19.block2.relu1 | ReLU | [B,128,16,16] | E002,E003 | — |
| v19.block2.conv2 | Conv2d 128 -> 128 | [B,128,16,16] | E002,E003 | block_2.2 |
| v19.block2.relu2 | ReLU | [B,128,16,16] | E002,E003 | — |
| v19.block2.pool | MaxPool2d 2x2 / 2 | [B,128,8,8] | E002,E003 | — |
| v19.block3 | Block 3 · 4 Conv/ReLU pairs | [B,256,4,4] | E002,E003 | block_3 |
| v19.block3.conv1 | Conv2d 128 -> 256 | [B,256,8,8] | E002,E003 | block_3.0 |
| v19.block3.relu1 | ReLU | [B,256,8,8] | E002,E003 | — |
| v19.block3.conv2 | Conv2d 256 -> 256 | [B,256,8,8] | E002,E003 | block_3.2 |
| v19.block3.relu2 | ReLU | [B,256,8,8] | E002,E003 | — |
| v19.block3.conv3 | Conv2d 256 -> 256 | [B,256,8,8] | E002,E003 | block_3.4 |
| v19.block3.relu3 | ReLU | [B,256,8,8] | E002,E003 | — |
| v19.block3.conv4 | Conv2d 256 -> 256 | [B,256,8,8] | E002,E003 | block_3.6 |
| v19.block3.relu4 | ReLU | [B,256,8,8] | E002,E003 | — |
| v19.block3.pool | MaxPool2d 2x2 / 2 | [B,256,4,4] | E002,E003 | — |
| v19.block4 | Block 4 · 4 Conv/ReLU pairs | [B,512,2,2] | E002,E003 | block_4 |
| v19.block4.conv1 | Conv2d 256 -> 512 | [B,512,4,4] | E002,E003 | block_4.0 |
| v19.block4.relu1 | ReLU | [B,512,4,4] | E002,E003 | — |
| v19.block4.conv2 | Conv2d 512 -> 512 | [B,512,4,4] | E002,E003 | block_4.2 |
| v19.block4.relu2 | ReLU | [B,512,4,4] | E002,E003 | — |
| v19.block4.conv3 | Conv2d 512 -> 512 | [B,512,4,4] | E002,E003 | block_4.4 |
| v19.block4.relu3 | ReLU | [B,512,4,4] | E002,E003 | — |
| v19.block4.conv4 | Conv2d 512 -> 512 | [B,512,4,4] | E002,E003 | block_4.6 |
| v19.block4.relu4 | ReLU | [B,512,4,4] | E002,E003 | — |
| v19.block4.pool | MaxPool2d 2x2 / 2 | [B,512,2,2] | E002,E003 | — |
| v19.block5 | Block 5 · 4 Conv/ReLU pairs | [B,512,1,1] | E002,E003 | block_5 |
| v19.block5.conv1 | Conv2d 512 -> 512 | [B,512,2,2] | E002,E003 | block_5.0 |
| v19.block5.relu1 | ReLU | [B,512,2,2] | E002,E003 | — |
| v19.block5.conv2 | Conv2d 512 -> 512 | [B,512,2,2] | E002,E003 | block_5.2 |
| v19.block5.relu2 | ReLU | [B,512,2,2] | E002,E003 | — |
| v19.block5.conv3 | Conv2d 512 -> 512 | [B,512,2,2] | E002,E003 | block_5.4 |
| v19.block5.relu3 | ReLU | [B,512,2,2] | E002,E003 | — |
| v19.block5.conv4 | Conv2d 512 -> 512 | [B,512,2,2] | E002,E003 | block_5.6 |
| v19.block5.relu4 | ReLU | [B,512,2,2] | E002,E003 | — |
| v19.block5.pool | MaxPool2d 2x2 / 2 | [B,512,1,1] | E002,E003 | — |
| v19.flatten | Flatten features | [B,512] | E003 | — |
| v19.classifier | Classifier head | logits: [B,10] | E002,E003 | — |
| v19.hidden1 | Linear / ReLU · 1 | [B,4096] | E002,E003 | — |
| v19.hidden1.linear | Linear 512 -> 4096 | [B,4096] | E002,E003 | classifier.0 |
| v19.hidden1.relu | ReLU | [B,4096] | E002,E003 | — |
| v19.hidden2 | Linear / ReLU · 2 | [B,4096] | E002,E003 | — |
| v19.hidden2.linear | Linear 4096 -> 4096 | [B,4096] | E002,E003 | classifier.2 |
| v19.hidden2.relu | ReLU | [B,4096] | E002,E003 | — |
| v19.fc3 | Linear 4096 -> 10 | logits: [B,10] | E002,E003 | classifier.4 |
| v19.returns | Return logits / probabilities | (logits, probas) | E003 | — |
| v19.logits | Retain logits | [B,10] | E003 | — |
| v19.softmax | Softmax | [B,10] | E003 | — |
| v19.output | Forward return tuple | 2 x [B,10] | E003 | — |

## 与教科书/通用基础图的区别

- Do not infer13 convolution layers from stale class name VGG16 or invent a VGG19 source class. Actual block depths are2,2,4,4,4.
- Retain x.view(-1,512): larger inputs can alter the effective batch row count; arbitrary input sizes are not supported by merely changing labels.
- Draw CIFAR-10 rather than the stale MNIST section label; unused num_features=784 is not a flatten width.
- Do not copy ImageNet224x224 shapes, a512*7*7 classifier input or an AdaptiveAvgPool7x7 into this implementation.
- Do not add standard VGG Dropout/AvgPool or introduce VGG-BN normalization absent from this implementation.
- Retain all16 convolution parameter identities even when same-family blocks are folded.
- Softmax is a real forward output here, not an unused local variable as in the grouped AlexNet notebook.

## 源码事实与边界

- The source class is still named VGG16, but16 Conv plus3 Linear with [2,2,4,4,4] blocks forms VGG19-type; keep the real class symbol.
- Flatten uses x.view(-1,512), not a batch-preserving expression: it keeps B only for the selected32x32 profile.
- Conv/Linear weights use normal_(0,0.05) and zero biases rather than the previous VGG16 notebook initialization.
- The actual dataset is CIFAR10 with ToTensor and no resize; the MNIST comment and num_features=784 do not define input shape.
- VGG16 accepts num_features but never uses it in __init__; selected input is3-channel32x32, and num_classes=10 controls the final Linear.
- Five actual Sequential blocks contain2,2,4,4,4 independent Conv-ReLU pairs and one MaxPool2d(2,2) each.
- All16 Conv2d layers use kernel3,stride1,padding1,bias=True; spatial sizes after pools are16,8,4,2,1.
- Flatten receives [B,512,1,1] and outputs512 values; classifier is Linear512->4096->4096->10 with two ReLUs.
- No Dropout, BatchNorm or adaptive avgpool is constructed in this notebook.
- Feature-block ReLUs use default inplace=False; classifier ReLUs are explicitly inplace=True.
- forward computes Softmax(dim=1) and returns logits and probabilities; loss uses logits outside forward.
- All16 convolution and3 Linear modules have distinct parameters; blocks1 and3 expand as representative2- and4-convolution structures.
