# LeNet5：源码与图框对应

来源：`rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [deeplearning-models/pytorch_ipynb/cnn/cnn-lenet5-mnist.py](sources/deeplearning-models/pytorch_ipynb/cnn/cnn-lenet5-mnist.py) · `LeNet5` | 102–139 | [12] |
| E002 | [deeplearning-models/pytorch_ipynb/cnn/cnn-lenet5-mnist.py](sources/deeplearning-models/pytorch_ipynb/cnn/cnn-lenet5-mnist.py) · `LeNet5.__init__` | 104–131 | [12] |
| E003 | [deeplearning-models/pytorch_ipynb/cnn/cnn-lenet5-mnist.py](sources/deeplearning-models/pytorch_ipynb/cnn/cnn-lenet5-mnist.py) · `LeNet5.forward` | 134–139 | [12] |
| E004 | [deeplearning-models/pytorch_ipynb/cnn/cnn-lenet5-mnist.py](sources/deeplearning-models/pytorch_ipynb/cnn/cnn-lenet5-mnist.py) · `compute_accuracy` | 150–161 | [15] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| lenet.model | LeNet5 · MNIST | 2 x [B,10] | E001 | — |
| lenet.input | MNIST image | [B,1,32,32] | E003 | — |
| lenet.features | Convolutional features | [B,16,5,5] | E002,E003 | — |
| lenet.conv_stage1 | Conv / Tanh / Pool · 1 | [B,6,14,14] | E002,E003 | — |
| lenet.conv1 | Conv2d 1 -> 6 | [B,6,28,28] | E002,E003 | features.0 |
| lenet.tanh1 | Tanh | [B,6,28,28] | E002,E003 | — |
| lenet.pool1 | MaxPool2d | [B,6,14,14] | E002,E003 | — |
| lenet.conv_stage2 | Conv / Tanh / Pool · 2 | [B,16,5,5] | E002,E003 | — |
| lenet.conv2 | Conv2d 6 -> 16 | [B,16,10,10] | E002,E003 | features.3 |
| lenet.tanh2 | Tanh | [B,16,10,10] | E002,E003 | — |
| lenet.pool2 | MaxPool2d | [B,16,5,5] | E002,E003 | — |
| lenet.flatten | Flatten features | [B,400] | E003 | — |
| lenet.classifier | Fully connected classifier | logits: [B,10] | E002,E003 | — |
| lenet.hidden1 | Linear / Tanh · 1 | [B,120] | E002,E003 | — |
| lenet.fc1 | Linear 400 -> 120 | [B,120] | E002,E003 | classifier.0 |
| lenet.tanh3 | Tanh | [B,120] | E002,E003 | — |
| lenet.hidden2 | Linear / Tanh · 2 | [B,84] | E002,E003 | — |
| lenet.fc2 | Linear 120 -> 84 | [B,84] | E002,E003 | classifier.2 |
| lenet.tanh4 | Tanh | [B,84] | E002,E003 | — |
| lenet.fc3 | Linear 84 -> 10 | [B,10] | E002,E003 | classifier.4 |
| lenet.returns | Return logits / probabilities | (logits, probas) | E003 | — |
| lenet.logits | Logits | [B,10] | E003 | — |
| lenet.softmax | Softmax | [B,10] | E003 | — |
| lenet.output | Forward return tuple | 2 x [B,10] | E003 | — |

## 与教科书/通用基础图的区别

- No supplied model-specific reference PNG exists for this source; the layout is constructed from the reviewed implementation.
- Do not substitute the paper's average pooling, C5 convolution, or partial connection scheme for this simpler nn.Sequential implementation.
- The model input is 32x32 after caller-side resizing, not native 28x28 MNIST; drawing 28x28 would invalidate the fixed 400-feature classifier.
- Softmax is a real forward operator in this notebook and the logits branch is retained; it is not merely explanatory decoration.

## 源码事实与边界

- The caller resizes MNIST to 32x32 and constructs LeNet5(NUM_CLASSES, GRAYSCALE), with NUM_CLASSES=10 and GRAYSCALE=True.
- Both convolutions have kernel 5, stride 1, padding 0; spatial sizes are 32 -> 28 -> 14 -> 10 -> 5.
- This source uses Tanh and MaxPool2d, not ReLU or the average subsampling in the original LeNet-5 paper.
- The classifier receives 16*5*5=400 flattened features, then applies Linear 400->120->84->10 with two Tanh operations.
- forward computes Softmax(dim=1) and returns both raw logits and probabilities; cross_entropy consumes the logits branch.
- All five parameterized layers have separate parameter identities. Equal colors denote operator families, never weight sharing.
