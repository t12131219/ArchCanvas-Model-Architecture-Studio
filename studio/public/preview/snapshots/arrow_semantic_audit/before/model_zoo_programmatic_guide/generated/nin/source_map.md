# NiN (Network in Network)：源码与图框对应

来源：`rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [deeplearning-models-batch2/pytorch_ipynb/cnn/nin-cifar10.py](sources/deeplearning-models-batch2/pytorch_ipynb/cnn/nin-cifar10.py) · `NiN` | 120–157 | [10] |
| E002 | [deeplearning-models-batch2/pytorch_ipynb/cnn/nin-cifar10.py](sources/deeplearning-models-batch2/pytorch_ipynb/cnn/nin-cifar10.py) · `NiN.__init__` | 121–151 | [10] |
| E003 | [deeplearning-models-batch2/pytorch_ipynb/cnn/nin-cifar10.py](sources/deeplearning-models-batch2/pytorch_ipynb/cnn/nin-cifar10.py) · `NiN.forward` | 153–157 | [10] |
| E004 | [deeplearning-models-batch2/pytorch_ipynb/cnn/nin-cifar10.py](sources/deeplearning-models-batch2/pytorch_ipynb/cnn/nin-cifar10.py) · `compute_accuracy` | 168–179 | [13] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| nin.root | NiN / CIFAR-10 | [B,3,32,32] -> (logits,probas) | E001 | — |
| nin.input | CIFAR-10 image | [B,3,32,32] | E003 | — |
| nin.stage1 | Feature stage 1 | [B,96,16,16] | E002,E003 | — |
| nin.mlpconv1 | mlpconv 1 / spatial + 1x1 stack | [B,96,32,32] | E002,E003 | — |
| nin.mlpconv1.conv1 | Conv 5x5: 3 -> 192 | [B,192,32,32] | E002,E003 | classifier.0 |
| nin.mlpconv1.relu1 | ReLU | [B,192,32,32] | E002,E003 | — |
| nin.mlpconv1.conv2 | Conv 1x1: 192 -> 160 | [B,160,32,32] | E002,E003 | classifier.2 |
| nin.mlpconv1.relu2 | ReLU | [B,160,32,32] | E002,E003 | — |
| nin.mlpconv1.conv3 | Conv 1x1: 160 -> 96 | [B,96,32,32] | E002,E003 | classifier.4 |
| nin.mlpconv1.relu3 | ReLU | [B,96,32,32] | E002,E003 | — |
| nin.pool1 | MaxPool 3x3 / 2 | [B,96,16,16] | E002,E003 | — |
| nin.dropout1 | Dropout p=0.5 | [B,96,16,16] | E002,E003 | classifier.7 |
| nin.stage2 | Feature stage 2 | [B,192,8,8] | E002,E003 | — |
| nin.mlpconv2 | mlpconv 2 / spatial + 1x1 stack | [B,192,16,16] | E002,E003 | — |
| nin.mlpconv2.conv1 | Conv 5x5: 96 -> 192 | [B,192,16,16] | E002,E003 | classifier.8 |
| nin.mlpconv2.relu1 | ReLU | [B,192,16,16] | E002,E003 | — |
| nin.mlpconv2.conv2 | Conv 1x1: 192 -> 192 | [B,192,16,16] | E002,E003 | classifier.10 |
| nin.mlpconv2.relu2 | ReLU | [B,192,16,16] | E002,E003 | — |
| nin.mlpconv2.conv3 | Conv 1x1: 192 -> 192 | [B,192,16,16] | E002,E003 | classifier.12 |
| nin.mlpconv2.relu3 | ReLU | [B,192,16,16] | E002,E003 | — |
| nin.pool2 | Average pool 3x3 / 2 | [B,192,8,8] | E002,E003 | — |
| nin.dropout2 | Dropout p=0.5 | [B,192,8,8] | E002,E003 | classifier.15 |
| nin.stage3 | Class feature maps + global pool | [B,10,1,1] | E002,E003 | — |
| nin.mlpconv3 | mlpconv 3 / spatial + 1x1 stack | [B,10,8,8] | E002,E003 | — |
| nin.mlpconv3.conv1 | Conv 3x3: 192 -> 192 | [B,192,8,8] | E002,E003 | classifier.16 |
| nin.mlpconv3.relu1 | ReLU | [B,192,8,8] | E002,E003 | — |
| nin.mlpconv3.conv2 | Conv 1x1: 192 -> 192 | [B,192,8,8] | E002,E003 | classifier.18 |
| nin.mlpconv3.relu2 | ReLU | [B,192,8,8] | E002,E003 | — |
| nin.mlpconv3.conv3 | Conv 1x1: 192 -> 10 | [B,10,8,8] | E002,E003 | classifier.20 |
| nin.mlpconv3.relu3 | ReLU | [B,10,8,8] | E002,E003 | — |
| nin.pool3 | Average pool 8x8 / 1 | [B,10,1,1] | E002,E003 | — |
| nin.view | View pooled maps as logits | [B,10] | E003 | — |
| nin.returns | Return logits / probabilities | (logits, probas) | E003 | — |
| nin.logits | Retain logits | [B,10] | E003 | — |
| nin.softmax | Softmax over classes | [B,10] | E003 | — |
| nin.output | Forward return tuple | 2 x [B,10] | E003 | — |

## 与教科书/通用基础图的区别

- No supplied NiN reference PNG exists; this is a new layout grounded in the selected notebook rather than a generic paper diagram.
- Do not replace the second AvgPool by MaxPool, or the fixed final pool by AdaptiveAvgPool.
- Retain the final ReLU after Conv1x1(192,10); the logits are not produced by a separate Linear layer.
- Draw two return fields: raw logits and the forward Softmax result.
- Do not silently treat num_classes as controlling final Conv channels, or infer eval mode from the accuracy-function name.

## 源码事实与边界

- NiN.classifier is one nn.Sequential; three mlpconv/stage containers are logical source-grounded drawing groups.
- The nine independent Conv2d channel changes are 3->192->160->96->192->192->192->192->192->10.
- Each stage uses one spatial Conv followed by two 1x1 Conv; ReLU follows all nine convolutions, including the final class convolution.
- The first reduction uses MaxPool2d(3,2,1); the second uses AvgPool2d(3,2,1); each is followed by Dropout(0.5).
- Final class maps have 10 hard-coded channels; fixed AvgPool2d(8,1,0) globally averages selected 8x8 maps.
- forward preserves batch while viewing pooled maps, computes Softmax(dim=1), and returns both logits and probabilities.
- The num_classes argument controls only the final view; the last Conv2d is hard-coded to 10 channels.
- compute_accuracy does not call model.eval in this notebook; graph records Dropout and does not imply validation disables it.
- Convolution weights are shared across spatial positions, while all nine classifier layer instances own separate parameters.
