# ConvAE (nearest-neighbor MNIST)：源码与图框对应

来源：`rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [deeplearning-models-batch2/pytorch_ipynb/autoencoder/ae-conv-nneighbor.py](sources/deeplearning-models-batch2/pytorch_ipynb/autoencoder/ae-conv-nneighbor.py) · `ConvolutionalAutoencoder` | 70–147 | [9] |
| E002 | [deeplearning-models-batch2/pytorch_ipynb/autoencoder/ae-conv-nneighbor.py](sources/deeplearning-models-batch2/pytorch_ipynb/autoencoder/ae-conv-nneighbor.py) · `ConvolutionalAutoencoder.__init__` | 72–127 | [9] |
| E003 | [deeplearning-models-batch2/pytorch_ipynb/autoencoder/ae-conv-nneighbor.py](sources/deeplearning-models-batch2/pytorch_ipynb/autoencoder/ae-conv-nneighbor.py) · `ConvolutionalAutoencoder.forward` | 129–147 | [9] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| convae.root | ConvolutionalAutoencoder / MNIST | (logits, probas) | E003 | — |
| convae.input | MNIST grayscale image | [B,1,28,28] | E003 | — |
| convae.encoder | Encoder: convolution + pooling | [B,8,7,7] | E002,E003 | — |
| convae.enc1 | Encode stage 1 / 1 -> 4 | [B,4,14,14] | E002,E003 | — |
| convae.conv1 | Conv2d 1 -> 4 | [B,4,28,28] | E002,E003 | conv_1 |
| convae.act1 | LeakyReLU | [B,4,28,28] | E003 | — |
| convae.pool1 | MaxPool2d 2x2 / 2 | [B,4,14,14] | E002,E003 | — |
| convae.enc2 | Encode stage 2 / 4 -> 8 | [B,8,7,7] | E002,E003 | — |
| convae.conv2 | Conv2d 4 -> 8 | [B,8,14,14] | E002,E003 | conv_2 |
| convae.act2 | LeakyReLU | [B,8,14,14] | E003 | — |
| convae.pool2 | MaxPool2d 2x2 / 2 | [B,8,7,7] | E002,E003 | — |
| convae.code | Encoded feature map | [B,8,7,7] | E003 | — |
| convae.decoder | Decoder: resize then convolution | logits: [B,1,28,28] | E002,E003 | — |
| convae.dec1 | Decode stage 1 / nearest + 8 -> 4 | [B,4,14,14] | E002,E003 | — |
| convae.resize1 | Nearest interpolation x 2 | [B,8,14,14] | E003 | — |
| convae.conv3 | Conv2d 8 -> 4 | [B,4,14,14] | E002,E003 | conv_3 |
| convae.act3 | LeakyReLU | [B,4,14,14] | E003 | — |
| convae.dec2 | Decode stage 2 / nearest + 4 -> 1 | [B,1,28,28] | E002,E003 | — |
| convae.resize2 | Nearest interpolation x 2 | [B,4,28,28] | E003 | — |
| convae.conv4 | Conv2d 4 -> 1 | [B,1,28,28] | E002,E003 | conv_4 |
| convae.act4 | LeakyReLU -> logits | logits: [B,1,28,28] | E003 | — |
| convae.returns | Return logits / decoded probabilities | (logits, probas) | E003 | — |
| convae.logits | Retain activated logits | [B,1,28,28] | E003 | — |
| convae.sigmoid | Sigmoid | probas: [B,1,28,28] | E003 | — |
| convae.output | Forward return tuple | 2 x [B,1,28,28] | E003 | — |

## 与教科书/通用基础图的区别

- The decoder comments say Unpool, but executed code is nearest interpolation; draw the actual function.
- Correct conv_3 channel label from the stale comment to the constructed 8->4 mapping.
- Do not substitute ConvTranspose2d, MaxUnpool2d or learned upsampling for this implementation.
- Keep the final LeakyReLU before Sigmoid, even though many other autoencoders omit it.
- Retain both forward outputs and keep binary_cross_entropy_with_logits outside the architecture.
- No model-specific reference PNG is supplied; the diagram follows source and the shared Transformer theme.

## 源码事实与边界

- Encoder is Conv1->LeakyReLU->MaxPool1->Conv2->LeakyReLU->MaxPool2.
- The code map has shape [B,8,7,7]; no fully connected latent layer or image flattening is present.
- Decoder performs two nearest-neighbor F.interpolate calls followed by ordinary Conv2d.
- conv_3 actually maps 8 to 4 channels; its nearby 14x14x8 comment is stale.
- MaxPool2d does not return indices, so no MaxUnpool2d or pooling-index dependency exists.
- Both F.leaky_relu calls in encoder and both in decoder use the API default negative_slope=0.01.
- The final Conv2d output is passed through LeakyReLU before being named logits and then Sigmoid.
- forward returns both activated logits and sigmoid probabilities; the loss uses logits in the caller.
- Four Conv2d modules have independent weights, with default bias=True; there is no BatchNorm.
