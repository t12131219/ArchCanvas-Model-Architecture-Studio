# AlexNet (grouped CIFAR-10)：源码与图框对应

来源：`rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [deeplearning-models-batch2/pytorch_ipynb/cnn/cnn-alexnet-cifar10-grouped.py](sources/deeplearning-models-batch2/pytorch_ipynb/cnn/cnn-alexnet-cifar10-grouped.py) · `AlexNet` | 129–169 | [20] |
| E002 | [deeplearning-models-batch2/pytorch_ipynb/cnn/cnn-alexnet-cifar10-grouped.py](sources/deeplearning-models-batch2/pytorch_ipynb/cnn/cnn-alexnet-cifar10-grouped.py) · `AlexNet.__init__` | 131–161 | [20] |
| E003 | [deeplearning-models-batch2/pytorch_ipynb/cnn/cnn-alexnet-cifar10-grouped.py](sources/deeplearning-models-batch2/pytorch_ipynb/cnn/cnn-alexnet-cifar10-grouped.py) · `AlexNet.forward` | 163–169 | [20] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| alex.model | Grouped AlexNet · CIFAR-10 | logits: [B,10] | E001 | — |
| alex.input | CIFAR-10 image | [B,3,64,64] | E003 | — |
| alex.features | Conv features · 5 stages | [B,256,1,1] | E002,E003 | — |
| alex.conv_stage1 | Conv stage 1 | [B,64,7,7] | E002,E003 | — |
| alex.conv_stage1.conv | Conv2d 3 -> 64 | [B,64,15,15] | E002,E003 | features.0 |
| alex.conv_stage1.relu | ReLU | [B,64,15,15] | E002,E003 | — |
| alex.conv_stage1.pool | MaxPool2d 3x3 / 2 | [B,64,7,7] | E002,E003 | — |
| alex.conv_stage2 | Conv stage 2 · groups=2 | [B,192,3,3] | E002,E003 | — |
| alex.conv_stage2.conv | Conv2d 64 -> 192 | [B,192,7,7] | E002,E003 | features.3 |
| alex.conv_stage2.relu | ReLU | [B,192,7,7] | E002,E003 | — |
| alex.conv_stage2.pool | MaxPool2d 3x3 / 2 | [B,192,3,3] | E002,E003 | — |
| alex.conv_stage3 | Conv stage 3 · groups=2 | [B,384,3,3] | E002,E003 | — |
| alex.conv_stage3.conv | Conv2d 192 -> 384 | [B,384,3,3] | E002,E003 | features.6 |
| alex.conv_stage3.relu | ReLU | [B,384,3,3] | E002,E003 | — |
| alex.conv_stage4 | Conv stage 4 · groups=2 | [B,256,3,3] | E002,E003 | — |
| alex.conv_stage4.conv | Conv2d 384 -> 256 | [B,256,3,3] | E002,E003 | features.8 |
| alex.conv_stage4.relu | ReLU | [B,256,3,3] | E002,E003 | — |
| alex.conv_stage5 | Conv stage 5 · groups=2 | [B,256,1,1] | E002,E003 | — |
| alex.conv_stage5.conv | Conv2d 256 -> 256 | [B,256,3,3] | E002,E003 | features.10 |
| alex.conv_stage5.relu | ReLU | [B,256,3,3] | E002,E003 | — |
| alex.conv_stage5.pool | MaxPool2d 3x3 / 2 | [B,256,1,1] | E002,E003 | — |
| alex.adaptive_pool | AdaptiveAvgPool2d 6x6 | [B,256,6,6] | E002,E003 | — |
| alex.flatten | Flatten spatial features | [B,9216] | E003 | — |
| alex.classifier | Classifier head | logits: [B,10] | E002,E003 | — |
| alex.hidden1 | Hidden classifier 1 | [B,4096] | E002,E003 | — |
| alex.hidden1.dropout | Dropout 0.5 | [B,9216] | E002,E003 | — |
| alex.hidden1.linear | Linear 9216 -> 4096 | [B,4096] | E002,E003 | classifier.1 |
| alex.hidden1.relu | ReLU | [B,4096] | E002,E003 | — |
| alex.hidden2 | Hidden classifier 2 | [B,4096] | E002,E003 | — |
| alex.hidden2.dropout | Dropout 0.5 | [B,4096] | E002,E003 | — |
| alex.hidden2.linear | Linear 4096 -> 4096 | [B,4096] | E002,E003 | classifier.4 |
| alex.hidden2.relu | ReLU | [B,4096] | E002,E003 | — |
| alex.fc3 | Linear 4096 -> 10 | logits: [B,10] | E002,E003 | classifier.6 |
| alex.output | Returned logits | [B,10] | E003 | — |
| alex.unused_softmax | Computed Softmax · unused | probas: [B,10] | E003 | — |

## 与教科书/通用基础图的区别

- Use the notebook's 64x64 crop rather than ImageNet 224x224 input; do not assume final convolutional maps are 6x6.
- Do not add paper-era LRN, two-GPU split modules, or an explicit concatenation for the grouped Conv2d implementations.
- Do not change the computed unused Softmax into a returned probability tuple; this source returns logits alone.
- Keep AdaptiveAvgPool2d and its actual output target rather than silently replacing it with global average pooling.

## 源码事实与边界

- The notebook resizes CIFAR-10 to 70x70 then crops to 64x64; the model receives [B,3,64,64].
- Only the first convolution has groups=1; convolutions 2-5 have groups=2 within individual Conv2d modules.
- The feature path spatial sizes are 64->15->7->3->1; no local response normalization exists in this implementation.
- AdaptiveAvgPool2d((6,6)) consumes the actual 1x1 feature and produces 6x6, then view yields 256*6*6=9216 features.
- The classifier uses Dropout0.5->Linear9216->4096->ReLU->Dropout0.5->Linear4096->4096->ReLU->Linear4096->10.
- Dropout is retained as a source operator but is an identity in the selected eval profile.
- forward computes local probas=Softmax(logits,dim=1) but returns only logits; the side node has no return dependency.
- Eight parameterized Conv/Linear modules have distinct parameter paths; groups=2 does not create two Python-level modules or branches.
