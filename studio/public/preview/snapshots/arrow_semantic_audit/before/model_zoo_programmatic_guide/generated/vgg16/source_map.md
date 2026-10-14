# VGG16 (CIFAR-10 notebook)：源码与图框对应

来源：`https://github.com/rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [deeplearning-models-batch3/pytorch_ipynb/cnn/cnn-vgg16.py](sources/deeplearning-models-batch3/pytorch_ipynb/cnn/cnn-vgg16.py) · `VGG16` | 75–220 | [10] |
| E002 | [deeplearning-models-batch3/pytorch_ipynb/cnn/cnn-vgg16.py](sources/deeplearning-models-batch3/pytorch_ipynb/cnn/cnn-vgg16.py) · `VGG16.__init__` | 77–203 | [10] |
| E003 | [deeplearning-models-batch3/pytorch_ipynb/cnn/cnn-vgg16.py](sources/deeplearning-models-batch3/pytorch_ipynb/cnn/cnn-vgg16.py) · `VGG16.forward` | 208–220 | [10] |
| E004 | [deeplearning-models-batch3/pytorch_ipynb/cnn/cnn-vgg16.py](sources/deeplearning-models-batch3/pytorch_ipynb/cnn/cnn-vgg16.py) · `compute_accuracy` | 231–243 | [12] |
| E005 | [deeplearning-models-batch3/pytorch_ipynb/cnn/cnn-vgg16.py](sources/deeplearning-models-batch3/pytorch_ipynb/cnn/cnn-vgg16.py) · `compute_epoch_loss` | 246–259 | [12] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| vgg.root | VGG16 · CIFAR-10 | 2 x [B,10] | E001 | — |
| vgg.input | CIFAR-10 image | [B,3,32,32] | E003 | — |
| vgg.features | Five convolutional blocks | [B,512,1,1] | E002,E003 | — |
| vgg.block1 | Block 1 · 2 Conv/ReLU pairs | [B,64,16,16] | E002,E003 | block_1 |
| vgg.block1.conv1 | Conv2d 3 -> 64 | [B,64,32,32] | E002,E003 | block_1.0 |
| vgg.block1.relu1 | ReLU | [B,64,32,32] | E002,E003 | — |
| vgg.block1.conv2 | Conv2d 64 -> 64 | [B,64,32,32] | E002,E003 | block_1.2 |
| vgg.block1.relu2 | ReLU | [B,64,32,32] | E002,E003 | — |
| vgg.block1.pool | MaxPool2d 2x2 / 2 | [B,64,16,16] | E002,E003 | — |
| vgg.block2 | Block 2 · 2 Conv/ReLU pairs | [B,128,8,8] | E002,E003 | block_2 |
| vgg.block2.conv1 | Conv2d 64 -> 128 | [B,128,16,16] | E002,E003 | block_2.0 |
| vgg.block2.relu1 | ReLU | [B,128,16,16] | E002,E003 | — |
| vgg.block2.conv2 | Conv2d 128 -> 128 | [B,128,16,16] | E002,E003 | block_2.2 |
| vgg.block2.relu2 | ReLU | [B,128,16,16] | E002,E003 | — |
| vgg.block2.pool | MaxPool2d 2x2 / 2 | [B,128,8,8] | E002,E003 | — |
| vgg.block3 | Block 3 · 3 Conv/ReLU pairs | [B,256,4,4] | E002,E003 | block_3 |
| vgg.block3.conv1 | Conv2d 128 -> 256 | [B,256,8,8] | E002,E003 | block_3.0 |
| vgg.block3.relu1 | ReLU | [B,256,8,8] | E002,E003 | — |
| vgg.block3.conv2 | Conv2d 256 -> 256 | [B,256,8,8] | E002,E003 | block_3.2 |
| vgg.block3.relu2 | ReLU | [B,256,8,8] | E002,E003 | — |
| vgg.block3.conv3 | Conv2d 256 -> 256 | [B,256,8,8] | E002,E003 | block_3.4 |
| vgg.block3.relu3 | ReLU | [B,256,8,8] | E002,E003 | — |
| vgg.block3.pool | MaxPool2d 2x2 / 2 | [B,256,4,4] | E002,E003 | — |
| vgg.block4 | Block 4 · 3 Conv/ReLU pairs | [B,512,2,2] | E002,E003 | block_4 |
| vgg.block4.conv1 | Conv2d 256 -> 512 | [B,512,4,4] | E002,E003 | block_4.0 |
| vgg.block4.relu1 | ReLU | [B,512,4,4] | E002,E003 | — |
| vgg.block4.conv2 | Conv2d 512 -> 512 | [B,512,4,4] | E002,E003 | block_4.2 |
| vgg.block4.relu2 | ReLU | [B,512,4,4] | E002,E003 | — |
| vgg.block4.conv3 | Conv2d 512 -> 512 | [B,512,4,4] | E002,E003 | block_4.4 |
| vgg.block4.relu3 | ReLU | [B,512,4,4] | E002,E003 | — |
| vgg.block4.pool | MaxPool2d 2x2 / 2 | [B,512,2,2] | E002,E003 | — |
| vgg.block5 | Block 5 · 3 Conv/ReLU pairs | [B,512,1,1] | E002,E003 | block_5 |
| vgg.block5.conv1 | Conv2d 512 -> 512 | [B,512,2,2] | E002,E003 | block_5.0 |
| vgg.block5.relu1 | ReLU | [B,512,2,2] | E002,E003 | — |
| vgg.block5.conv2 | Conv2d 512 -> 512 | [B,512,2,2] | E002,E003 | block_5.2 |
| vgg.block5.relu2 | ReLU | [B,512,2,2] | E002,E003 | — |
| vgg.block5.conv3 | Conv2d 512 -> 512 | [B,512,2,2] | E002,E003 | block_5.4 |
| vgg.block5.relu3 | ReLU | [B,512,2,2] | E002,E003 | — |
| vgg.block5.pool | MaxPool2d 2x2 / 2 | [B,512,1,1] | E002,E003 | — |
| vgg.flatten | Flatten features | [B,512] | E003 | — |
| vgg.classifier | Classifier head | logits: [B,10] | E002,E003 | — |
| vgg.hidden1 | Linear / ReLU · 1 | [B,4096] | E002,E003 | — |
| vgg.hidden1.linear | Linear 512 -> 4096 | [B,4096] | E002,E003 | classifier.0 |
| vgg.hidden1.relu | ReLU | [B,4096] | E002,E003 | — |
| vgg.hidden2 | Linear / ReLU · 2 | [B,4096] | E002,E003 | — |
| vgg.hidden2.linear | Linear 4096 -> 4096 | [B,4096] | E002,E003 | classifier.2 |
| vgg.hidden2.relu | ReLU | [B,4096] | E002,E003 | — |
| vgg.fc3 | Linear 4096 -> 10 | logits: [B,10] | E002,E003 | classifier.4 |
| vgg.returns | Return logits / probabilities | (logits, probas) | E003 | — |
| vgg.logits | Retain logits | [B,10] | E003 | — |
| vgg.softmax | Softmax | [B,10] | E003 | — |
| vgg.output | Forward return tuple | 2 x [B,10] | E003 | — |

## 与教科书/通用基础图的区别

- Draw CIFAR-10 rather than the stale MNIST section label; unused num_features=784 is not a flatten width.
- Do not copy ImageNet224x224 shapes, a512*7*7 classifier input or an AdaptiveAvgPool7x7 into this implementation.
- Do not turn commented Dropout or avgpool into forward operators or introduce VGG-BN normalization.
- Retain all13 convolution parameter identities even when same-family blocks are folded.
- Softmax is a real forward output here, not an unused local variable as in the grouped AlexNet notebook.

## 源码事实与边界

- The actual dataset is CIFAR10 with ToTensor and no resize; the MNIST comment and num_features=784 do not define input shape.
- VGG16 accepts num_features but never uses it in __init__; selected input is3-channel32x32, and num_classes=10 controls the final Linear.
- Five actual Sequential blocks contain2,2,3,3,3 independent Conv-ReLU pairs and one MaxPool2d(2,2) each.
- All13 Conv2d layers use kernel3,stride1,padding1,bias=True; spatial sizes after pools are16,8,4,2,1.
- Flatten receives [B,512,1,1] and outputs512 values; classifier is Linear512->4096->4096->10 with two ReLUs.
- Dropout and adaptive avgpool statements are commented, not constructed; no BatchNorm exists.
- Feature-block ReLUs use default inplace=False; classifier ReLUs are explicitly inplace=True.
- forward computes Softmax(dim=1) and returns logits and probabilities; loss uses logits outside forward.
- All13 convolution and3 Linear modules have distinct parameters; blocks1 and3 expand as representative2- and3-convolution structures.
