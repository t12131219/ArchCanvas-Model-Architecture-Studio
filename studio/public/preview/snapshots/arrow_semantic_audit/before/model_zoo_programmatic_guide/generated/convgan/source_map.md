# Convolutional GAN (MNIST)：源码与图框对应

来源：`https://github.com/rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E009 | [deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py](sources/deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py) · `__module__` | 1–309 | [1, 5, 7, 9, 10, 11, 12, 14, 15, 17, 18, 19, 20] |
| E001 | [deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py](sources/deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py) · `Flatten` | 78–80 | [9] |
| E002 | [deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py](sources/deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py) · `Flatten.forward` | 79–80 | [9] |
| E007 | [deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py](sources/deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py) · `Reshape1` | 82–84 | [9] |
| E008 | [deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py](sources/deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py) · `Reshape1.forward` | 83–84 | [9] |
| E003 | [deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py](sources/deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py) · `GAN` | 87–143 | [9] |
| E004 | [deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py](sources/deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py) · `GAN.__init__` | 89–134 | [9] |
| E006 | [deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py](sources/deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py) · `GAN.generator_forward` | 137–139 | [9] |
| E005 | [deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py](sources/deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py) · `GAN.discriminator_forward` | 141–143 | [9] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| convgan.root | ConvGAN / training call paths | two model entries / three D calls / no joint forward | E009 | — |
| convgan.noise | Caller Uniform [-1,1) noise | z: [B,100] | E009 | — |
| convgan.real_input | Real MNIST image / ToTensor | [B,1,28,28] in [0,1] | E009 | — |
| convgan.generator | Generator G | generated_features: [B,1,28,28] | E004,E006 | generator; instance=model.generator |
| convgan.generator.projection | Latent projection / reshape | [B,64,7,7] | E004,E006,E008 | — |
| convgan.generator.linear | Linear 100 -> 3136 | [B,3136] | E004,E006 | generator.0 |
| convgan.generator.bn1d | BatchNorm1 / 3136 | [B,3136] | E004,E006 | generator.1; instance=generator.1 |
| convgan.generator.projection_activation | LeakyReLU 0.0001 | [B,3136] | E004,E006 | — |
| convgan.generator.reshape | Reshape1: 64 x 7 x 7 | [B,64,7,7] | E008,E004,E006 | instance=generator.3 |
| convgan.generator.stage1 | Generator upsample 1 | [B,32,13,13] | E004,E006 | — |
| convgan.generator.stage1.conv | ConvTranspose2d 64 -> 32 | [B,32,13,13] | E004,E006 | generator.4 |
| convgan.generator.stage1.bn | BatchNorm2 / 32 | [B,32,13,13] | E004,E006 | generator.5; instance=generator.5 |
| convgan.generator.stage1.activation | LeakyReLU 0.0001 | [B,32,13,13] | E004,E006 | — |
| convgan.generator.stage2 | Generator upsample 2 | [B,16,25,25] | E004,E006 | — |
| convgan.generator.stage2.conv | ConvTranspose2d 32 -> 16 | [B,16,25,25] | E004,E006 | generator.7 |
| convgan.generator.stage2.bn | BatchNorm2 / 16 | [B,16,25,25] | E004,E006 | generator.8; instance=generator.8 |
| convgan.generator.stage2.activation | LeakyReLU 0.0001 | [B,16,25,25] | E004,E006 | — |
| convgan.generator.stage3 | Generator upsample 3 | [B,8,27,27] | E004,E006 | — |
| convgan.generator.stage3.conv | ConvTranspose2d 16 -> 8 | [B,8,27,27] | E004,E006 | generator.10 |
| convgan.generator.stage3.bn | BatchNorm2 / 8 | [B,8,27,27] | E004,E006 | generator.11; instance=generator.11 |
| convgan.generator.stage3.activation | LeakyReLU 0.0001 | [B,8,27,27] | E004,E006 | — |
| convgan.generator.stage4 | Generator upsample 4 | [B,1,28,28] | E004,E006 | — |
| convgan.generator.stage4.conv | ConvTranspose2d 8 -> 1 | [B,1,28,28] | E004,E006 | generator.13 |
| convgan.generator.tanh | Tanh generated pixels | [B,1,28,28] | E004,E006 | — |
| convgan.real_prepare | Caller real-image preparation | features: [B,784] | E009 | — |
| convgan.normalize | Normalize pixels to [-1,1] | [B,1,28,28] | E009 | — |
| convgan.real_flatten | view(-1, IMG_SIZE) + to(device) | [B,784] | E009 | — |
| convgan.g_score_path | G objective / D(fake) | score [B] / no detach | E009 | — |
| convgan.g_image_view | Caller view as image | [B,1,28,28] | E009 | — |
| convgan.d_for_g | D call / generator objective | [B] raw scores / SAME D parameters | E004,E005,E002 | discriminator; instance=model.discriminator |
| convgan.d_for_g.stage1 | Discriminator stage 1 | [B,8,14,14] | E004,E005 | discriminator.0 |
| convgan.d_for_g.stage1.conv | Conv2d 1 -> 8 | [B,8,14,14] | E004,E005 | discriminator.0; instance=model.discriminator |
| convgan.d_for_g.stage1.bn | BatchNorm2 / 8 | [B,8,14,14] | E004,E005 | discriminator.1; instance=discriminator.1 |
| convgan.d_for_g.stage1.activation | LeakyReLU 0.0001 | [B,8,14,14] | E004,E005 | — |
| convgan.d_for_g.stage2 | Discriminator stage 2 | [B,32,7,7] | E004,E005 | discriminator.3 |
| convgan.d_for_g.stage2.conv | Conv2d 8 -> 32 | [B,32,7,7] | E004,E005 | discriminator.3; instance=model.discriminator |
| convgan.d_for_g.stage2.bn | BatchNorm2 / 32 | [B,32,7,7] | E004,E005 | discriminator.4; instance=discriminator.4 |
| convgan.d_for_g.stage2.activation | LeakyReLU 0.0001 | [B,32,7,7] | E004,E005 | — |
| convgan.d_for_g.flatten | Flatten feature map | [B,1568] | E002,E004,E005 | instance=discriminator.6 |
| convgan.d_for_g.linear | Linear 1568 -> 1 | [B,1] | E004,E005 | discriminator.7; instance=model.discriminator |
| convgan.d_for_g.return | view(-1): raw logits | [B] | E005 | — |
| convgan.fake_score_path | D objective / detached fake | fake score: [B] | E009 | — |
| convgan.fake_image_view | Caller view as image | [B,1,28,28] | E009 | — |
| convgan.detach | detach: block gradient to G | [B,1,28,28] | E009 | — |
| convgan.d_fake | D call / detached fake | [B] raw scores / SAME D parameters | E004,E005,E002 | discriminator; instance=model.discriminator |
| convgan.d_fake.stage1 | Discriminator stage 1 | [B,8,14,14] | E004,E005 | discriminator.0 |
| convgan.d_fake.stage1.conv | Conv2d 1 -> 8 | [B,8,14,14] | E004,E005 | discriminator.0; instance=model.discriminator |
| convgan.d_fake.stage1.bn | BatchNorm2 / 8 | [B,8,14,14] | E004,E005 | discriminator.1; instance=discriminator.1 |
| convgan.d_fake.stage1.activation | LeakyReLU 0.0001 | [B,8,14,14] | E004,E005 | — |
| convgan.d_fake.stage2 | Discriminator stage 2 | [B,32,7,7] | E004,E005 | discriminator.3 |
| convgan.d_fake.stage2.conv | Conv2d 8 -> 32 | [B,32,7,7] | E004,E005 | discriminator.3; instance=model.discriminator |
| convgan.d_fake.stage2.bn | BatchNorm2 / 32 | [B,32,7,7] | E004,E005 | discriminator.4; instance=discriminator.4 |
| convgan.d_fake.stage2.activation | LeakyReLU 0.0001 | [B,32,7,7] | E004,E005 | — |
| convgan.d_fake.flatten | Flatten feature map | [B,1568] | E002,E004,E005 | instance=discriminator.6 |
| convgan.d_fake.linear | Linear 1568 -> 1 | [B,1] | E004,E005 | discriminator.7; instance=model.discriminator |
| convgan.d_fake.return | view(-1): raw logits | [B] | E005 | — |
| convgan.real_score_path | D objective / real image | real score: [B] | E009 | — |
| convgan.real_image_view | Caller view as image | [B,1,28,28] | E009 | — |
| convgan.d_real | D call / real image | [B] raw scores / SAME D parameters | E004,E005,E002 | discriminator; instance=model.discriminator |
| convgan.d_real.stage1 | Discriminator stage 1 | [B,8,14,14] | E004,E005 | discriminator.0 |
| convgan.d_real.stage1.conv | Conv2d 1 -> 8 | [B,8,14,14] | E004,E005 | discriminator.0; instance=model.discriminator |
| convgan.d_real.stage1.bn | BatchNorm2 / 8 | [B,8,14,14] | E004,E005 | discriminator.1; instance=discriminator.1 |
| convgan.d_real.stage1.activation | LeakyReLU 0.0001 | [B,8,14,14] | E004,E005 | — |
| convgan.d_real.stage2 | Discriminator stage 2 | [B,32,7,7] | E004,E005 | discriminator.3 |
| convgan.d_real.stage2.conv | Conv2d 8 -> 32 | [B,32,7,7] | E004,E005 | discriminator.3; instance=model.discriminator |
| convgan.d_real.stage2.bn | BatchNorm2 / 32 | [B,32,7,7] | E004,E005 | discriminator.4; instance=discriminator.4 |
| convgan.d_real.stage2.activation | LeakyReLU 0.0001 | [B,32,7,7] | E004,E005 | — |
| convgan.d_real.flatten | Flatten feature map | [B,1568] | E002,E004,E005 | instance=discriminator.6 |
| convgan.d_real.linear | Linear 1568 -> 1 | [B,1] | E004,E005 | discriminator.7; instance=model.discriminator |
| convgan.d_real.return | view(-1): raw logits | [B] | E005 | — |
| convgan.batch_targets | Batch targets / size only | targets: [B] | E009 | — |

## 与教科书/通用基础图的区别

- Retain true7->13->25->27->28 generator geometry rather than textbook7->14->28 upsampling.
- Do not add GAN.forward, a shared tuple output, conditioning embedding, attention, Dropout2d or debug hooks absent from executed source.
- Keep raw discriminator scores; the commented Sigmoid is not an actual layer, including in the BCE GAN variant.
- Distinguish three D call sites from three D instances; retain shared parameter identities and the caller-only detach boundary.
- Do not detach the generator-objective path or regenerate fake samples for every D call when source reuses generated_features.
- Preserve the actual global model.discriminator receiver; drawing does not silently repair it to self.discriminator.
- ConvGAN uses uniform[-1,1) noise and two D Conv stages; do not import WGAN's third stage, signed labels or clipping.

## 源码事实与边界

- GAN defines generator_forward and discriminator_forward, without its own forward override; this figure is a caller data-flow DAG, not a joint model return.
- generator_forward uses self.generator; discriminator_forward actually uses global model.discriminator, not self.discriminator.
- Generator Sequential is Linear100->3136(bias=False), BN1d, LeakyReLU .0001, Reshape64x7x7, four transposed convolutions, Tanh.
- Generator ConvTranspose kernels/strides/padding are (3,2,1),(3,2,1),(3,1,0),(2,1,0); channels64->32->16->8->1 and spatial7->13->25->27->28.
- Generator BN2d and LeakyReLU follow its first three transposed convolutions; final ConvTranspose is followed directly by Tanh.
- All Conv/ConvTranspose layers and generator Linear use bias=False; discriminator Linear keeps default bias=True. LeakyReLU slope .0001 is explicit and inplace=True.
- All BatchNorm layers use default affine/running-stat settings; selected train profile uses batch statistics and updates same D buffers at each call site.
- Both discriminators have a commented-out Sigmoid, so they return pred.view(-1) raw scores [B], never probabilities.
- Caller noise is externally sampled Uniform(-1,1) with width100; targets values never provide class conditioning.
- Caller normalizes real image via (features-.5)*2, flattens to784, then views it back to[B,1,28,28] at discriminator entry.
- Generator objective calls D(generated.view(...)) without detach; D fake objective uses the same previously computed image.detach(), blocking only gradient to G.
- Three visible D call sites share one model.discriminator parameter family and BatchNorm buffers; they are not independent discriminators.
- Source updates G before D. The fake tensor is reused after G optimizer.step; no fresh G forward occurs inside the D update block.
- Losses, optimizers, backward, clipping and update order are caller operations outside the selected forward-data paths; graph ranks do not imply parallel Python execution.
- Dropout2d and debug hooks appear only in comments/string literals and are not executed model operators.
- The final visualization sets eval and calls generator_forward only; its different BatchNorm mode is not mixed into this selected training graph.
- ConvGAN discriminator has two Conv stages1->8->32, spatial28->14->7, Flatten1568 and Linear1568->1.
- Caller BCEWithLogits uses valid=1 and fake=0; logits remain unnormalized until loss calculation.
- Caller uses Adam lr1e-4 and one D update per batch, with no clipping or gradient penalty.
