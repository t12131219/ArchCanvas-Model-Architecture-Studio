# DCGAN (G-to-D caller)：源码与图框对应

来源：`rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py](sources/deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py) · `CelebaDataset` | 66–89 | [15] |
| E003 | [deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py](sources/deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py) · `CelebaDataset.__init__` | 69–77 | [15] |
| E002 | [deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py](sources/deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py) · `CelebaDataset.__getitem__` | 79–86 | [15] |
| E004 | [deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py](sources/deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py) · `CelebaDataset.__len__` | 88–89 | [15] |
| E009 | [deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py](sources/deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py) · `weights_init` | 134–144 | [19] |
| E005 | [deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py](sources/deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py) · `DCGAN` | 151–248 | [20] |
| E006 | [deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py](sources/deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py) · `DCGAN.__init__` | 153–239 | [20] |
| E008 | [deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py](sources/deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py) · `DCGAN.generator_forward` | 242–244 | [20] |
| E007 | [deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py](sources/deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py) · `DCGAN.discriminator_forward` | 246–248 | [20] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| dcgan.root | DCGAN / selected G-to-D caller path | caller composition, not DCGAN.forward | E006,E008,E007 | — |
| dcgan.noise | Caller latent noise z | [B,100,1,1] | E008 | — |
| dcgan.scoring | Caller: score generated image | z -> fake image -> score | E008,E007 | — |
| dcgan.generator | Entry 1: G(z) | fake image: [B,3,64,64] | E006,E008 | generator |
| dcgan.g1 | G stage 1 / 4x4 | [B,512,4,4] | E006,E008 | generator.0 |
| dcgan.g1.conv | ConvTranspose2d 100 -> 512 | [B,512,4,4] | E006,E008 | generator.0 |
| dcgan.g1.bn | BatchNorm2d 512 | [B,512,4,4] | E006,E008 | generator.1 |
| dcgan.g1.relu | ReLU | [B,512,4,4] | E006,E008 | — |
| dcgan.g2 | G stage 2 / 8x8 | [B,256,8,8] | E006,E008 | generator.3 |
| dcgan.g2.conv | ConvTranspose2d 512 -> 256 | [B,256,8,8] | E006,E008 | generator.3 |
| dcgan.g2.bn | BatchNorm2d 256 | [B,256,8,8] | E006,E008 | generator.4 |
| dcgan.g2.relu | ReLU | [B,256,8,8] | E006,E008 | — |
| dcgan.g3 | G stage 3 / 16x16 | [B,128,16,16] | E006,E008 | generator.6 |
| dcgan.g3.conv | ConvTranspose2d 256 -> 128 | [B,128,16,16] | E006,E008 | generator.6 |
| dcgan.g3.bn | BatchNorm2d 128 | [B,128,16,16] | E006,E008 | generator.7 |
| dcgan.g3.relu | ReLU | [B,128,16,16] | E006,E008 | — |
| dcgan.g4 | G stage 4 / 32x32 | [B,64,32,32] | E006,E008 | generator.9 |
| dcgan.g4.conv | ConvTranspose2d 128 -> 64 | [B,64,32,32] | E006,E008 | generator.9 |
| dcgan.g4.bn | BatchNorm2d 64 | [B,64,32,32] | E006,E008 | generator.10 |
| dcgan.g4.relu | ReLU | [B,64,32,32] | E006,E008 | — |
| dcgan.g5 | G stage 5 / 64x64 | [B,3,64,64] | E006,E008 | generator.12 |
| dcgan.g5.conv | ConvTranspose2d 64 -> 3 | [B,3,64,64] | E006,E008 | generator.12 |
| dcgan.g5.tanh | Tanh image output | [B,3,64,64] | E006,E008 | — |
| dcgan.fake | Retain fake image / no detach | [B,3,64,64] | E008 | — |
| dcgan.discriminator | Entry 2: D(img) | score: [B,1,1,1] | E006,E007 | global model.discriminator |
| dcgan.d1 | D stage 1 / 32x32 | [B,64,32,32] | E006,E007 | discriminator.0 |
| dcgan.d1.conv | Conv2d 3 -> 64 | [B,64,32,32] | E006,E007 | discriminator.0 |
| dcgan.d1.leaky | LeakyReLU 0.2 | [B,64,32,32] | E006,E007 | — |
| dcgan.d2 | D stage 2 / 16x16 | [B,128,16,16] | E006,E007 | discriminator.2 |
| dcgan.d2.conv | Conv2d 64 -> 128 | [B,128,16,16] | E006,E007 | discriminator.2 |
| dcgan.d2.bn | BatchNorm2d 128 | [B,128,16,16] | E006,E007 | discriminator.3 |
| dcgan.d2.leaky | LeakyReLU 0.2 | [B,128,16,16] | E006,E007 | — |
| dcgan.d3 | D stage 3 / 8x8 | [B,256,8,8] | E006,E007 | discriminator.5 |
| dcgan.d3.conv | Conv2d 128 -> 256 | [B,256,8,8] | E006,E007 | discriminator.5 |
| dcgan.d3.bn | BatchNorm2d 256 | [B,256,8,8] | E006,E007 | discriminator.6 |
| dcgan.d3.leaky | LeakyReLU 0.2 | [B,256,8,8] | E006,E007 | — |
| dcgan.d4 | D stage 4 / 4x4 | [B,512,4,4] | E006,E007 | discriminator.8 |
| dcgan.d4.conv | Conv2d 256 -> 512 | [B,512,4,4] | E006,E007 | discriminator.8 |
| dcgan.d4.bn | BatchNorm2d 512 | [B,512,4,4] | E006,E007 | discriminator.9 |
| dcgan.d4.leaky | LeakyReLU 0.2 | [B,512,4,4] | E006,E007 | — |
| dcgan.d5 | D stage 5 / 1x1 | [B,1,1,1] | E006,E007 | discriminator.11 |
| dcgan.d5.conv | Conv2d 512 -> 1 | [B,1,1,1] | E006,E007 | discriminator.11 |
| dcgan.d5.sigmoid | Sigmoid score | score: [B,1,1,1] | E006,E007 | — |
| dcgan.score | Returned discriminator score | [B,1,1,1] | E007 | — |

## 与教科书/通用基础图的区别

- Do not draw a single DCGAN.forward: this class exposes two custom entry methods, composed only by the notebook caller.
- Keep the source global model.discriminator receiver visible; do not silently rewrite it to self.discriminator.
- Do not fuse real and generated images into one simultaneous dataflow input; real scoring is a separate call.
- Do not place detach on the selected generator update path; detach appears on the fake branch of the discriminator update.
- Generator output uses Tanh and discriminator output uses Sigmoid; they are different activation/range semantics.
- Respect the asymmetry in BatchNorm and convolution bias placement; textbook defaults are not a substitute for this constructor.
- No model-specific reference PNG is supplied; source structure is rendered with the shared Transformer theme.

## 源码事实与边界

- DCGAN defines generator_forward and discriminator_forward but has no forward method.
- The graph is the notebook caller composition for scoring generated images in a generator update, not a fabricated DCGAN.forward.
- discriminator_forward calls the module global model.discriminator(img); the selected notebook global model is assumed to alias the constructed DCGAN instance.
- Generator has five ConvTranspose2d layers, four BatchNorm2d layers, four ReLU calls and a final Tanh.
- Generator channels/spatial sizes are 100@1 -> 512@4 -> 256@8 -> 128@16 -> 64@32 -> 3@64.
- Every generator convolution has bias=False; the first is kernel4/stride1/padding0, the others kernel4/stride2/padding1.
- Discriminator has five Conv2d layers, three BatchNorm2d layers, four LeakyReLU(0.2) calls and a final Sigmoid.
- Discriminator channels/spatial sizes are 3@64 -> 64@32 -> 128@16 -> 256@8 -> 512@4 -> 1@1.
- Discriminator first/last Conv2d use default bias=True; middle three set bias=False. No BN follows first/last Conv2d.
- The selected generator update scores fake_images without detach. The separate discriminator update scores real_images and fake_images.detach().
- Real-image and fake-image calls share the same selected discriminator parameters; they are alternative calls, not a Concat/Add of images.
- The method returns [B,1,1,1]; the caller .view(-1), BCELoss labels and optimizer steps are outside this graph.
- BatchNorm uses training batch statistics in the selected call; a monitoring generator-only call is a different scope.
- Intermediate same-family stages are folded in detailed view; the IR retains every parameterized/functional module call.
