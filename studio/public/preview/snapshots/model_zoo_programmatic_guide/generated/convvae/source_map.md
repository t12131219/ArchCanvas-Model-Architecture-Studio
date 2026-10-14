# Convolutional VAE：源码与图框对应

来源：`https://github.com/rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-conv-var.py](sources/deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-conv-var.py) · `ConvVariationalAutoencoder` | 72–191 | [9] |
| E002 | [deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-conv-var.py](sources/deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-conv-var.py) · `ConvVariationalAutoencoder.__init__` | 74–137 | [9] |
| E006 | [deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-conv-var.py](sources/deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-conv-var.py) · `ConvVariationalAutoencoder.reparameterize` | 140–146 | [9] |
| E004 | [deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-conv-var.py](sources/deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-conv-var.py) · `ConvVariationalAutoencoder.encoder` | 148–165 | [9] |
| E003 | [deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-conv-var.py](sources/deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-conv-var.py) · `ConvVariationalAutoencoder.decoder` | 167–184 | [9] |
| E005 | [deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-conv-var.py](sources/deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-conv-var.py) · `ConvVariationalAutoencoder.forward` | 186–191 | [9] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| convvae.root | ConvVAE / MNIST | image -> tuple | E001 | — |
| convvae.input | MNIST grayscale image | [B,1,28,28] | E005 | — |
| convvae.forward | Model forward | four-tensor tuple | E005 | — |
| convvae.encoder | Convolutional encoder | (mu,logvar,z): [B,15] x 3 | E002,E004 | — |
| convvae.enc1 | Encode stage 1 | [B,16,12,12] | E002,E004 | enc_conv_1 |
| convvae.enc1.conv | Conv2d 1 -> 16 | [B,16,12,12] | E002,E004 | enc_conv_1 |
| convvae.enc1.activation | LeakyReLU 0.01 | [B,16,12,12] | E004 | — |
| convvae.enc2 | Encode stage 2 | [B,32,5,5] | E002,E004 | enc_conv_2 |
| convvae.enc2.conv | Conv2d 16 -> 32 | [B,32,5,5] | E002,E004 | enc_conv_2 |
| convvae.enc2.activation | LeakyReLU 0.01 | [B,32,5,5] | E004 | — |
| convvae.enc3 | Encode stage 3 | [B,64,2,2] | E002,E004 | enc_conv_3 |
| convvae.enc3.conv | Conv2d 32 -> 64 | [B,64,2,2] | E002,E004 | enc_conv_3 |
| convvae.enc3.activation | LeakyReLU 0.01 | [B,64,2,2] | E004 | — |
| convvae.posterior | Independent posterior heads | mu + logvar results | E002,E004 | — |
| convvae.mean_head | Mean head | [B,15] | E002,E004 | z_mean |
| convvae.mean_view | View 64x2x2 -> 256 | [B,256] | E004 | — |
| convvae.mu | Linear 256 -> 15 | mu: [B,15] | E002,E004 | z_mean |
| convvae.logvar_head | Log-variance head | [B,15] | E002,E004 | z_log_var |
| convvae.logvar_view | View 64x2x2 -> 256 | [B,256] | E004 | — |
| convvae.logvar | Linear 256 -> 15 | logvar: [B,15] | E002,E004 | z_log_var |
| convvae.sampling | Reparameterization / single latent | z: [B,15] | E006 | — |
| convvae.sample_args | Mean / scaled-noise operands | mu + noise operands | E006 | — |
| convvae.retain_mu | Retain mu values | [B,15] | E006 | — |
| convvae.scaled_noise | Scale Gaussian noise | std * epsilon: [B,15] | E006 | — |
| convvae.half_logvar | Divide logvar by 2 | [B,15] | E006 | — |
| convvae.std | exp(logvar / 2) | std: [B,15] | E006 | — |
| convvae.noise_product | Multiply std times epsilon | [B,15] | E006 | — |
| convvae.z | Add mu + std * epsilon | z: [B,15] | E006 | — |
| convvae.encoder_return | Return (mu, logvar, z) | 3 tensors [B,15] | E004 | — |
| convvae.select_z | Select encoded z from tuple | [B,15] | E005 | — |
| convvae.decoder | Convolutional decoder | decoded: [B,1,28,28] | E002,E003 | — |
| convvae.latent_projection | Latent projection + reshape | [B,64,2,2] | E002,E003 | — |
| convvae.decoder_linear | Linear 15 -> 256 | [B,256] | E002,E003 | dec_linear_1 |
| convvae.decoder_view | View as 64x2x2 feature map | [B,64,2,2] | E003 | — |
| convvae.dec1 | Decode stage 1 | [B,32,4,4] | E002,E003 | dec_deconv_1 |
| convvae.dec1.conv | ConvTranspose2d 64 -> 32 | [B,32,4,4] | E002,E003 | dec_deconv_1 |
| convvae.dec1.activation | LeakyReLU 0.01 | [B,32,4,4] | E003 | — |
| convvae.dec2 | Decode stage 2 | [B,16,11,11] | E002,E003 | dec_deconv_2 |
| convvae.dec2.conv | ConvTranspose2d 32 -> 16 | [B,16,11,11] | E002,E003 | dec_deconv_2 |
| convvae.dec2.activation | LeakyReLU 0.01 | [B,16,11,11] | E003 | — |
| convvae.dec3 | Decode stage 3 | [B,1,28,28] | E002,E003 | dec_deconv_3 |
| convvae.dec3.conv | ConvTranspose2d 16 -> 1 | [B,1,28,28] | E002,E003 | dec_deconv_3 |
| convvae.dec3.activation | LeakyReLU 0.01 | [B,1,28,28] | E003 | — |
| convvae.sigmoid | Sigmoid decoded pixels | [B,1,28,28] | E003 | — |
| convvae.return | Return (mu, logvar, z, decoded) | [B,15] x 3; [B,1,28,28] | E005 | — |
| convvae.epsilon | Internal Gaussian epsilon | [B,15] | E006 | — |

## 与教科书/通用基础图的区别

- No model-specific reference PNG is supplied; this graph follows the fixed notebook rather than a generic VAE illustration.
- Retain asymmetric decoder strides 2/3/3 and padding 0/1/4, rather than inventing a mirror of encoder stride 2.
- Draw one latent level and distinct mean/log-variance heads; logical operand bundles are not literal source tuples.
- Do not replace final LeakyReLU+Sigmoid by Sigmoid directly after convolution or by Softmax.
- Evaluation still samples epsilon; no deterministic z=mu path is present in this source.

## 源码事实与边界

- Encoder convolutions use kernels 6/4/2, strides 2/2/2, zero padding, and channels 16/32/64; 28->12->5->2 spatial sizes.
- Two independent Linear(256,latent) posterior heads each call x.view(-1,64*2*2); no intermediate hidden latent hierarchy exists.
- Internal epsilon is randn(B,latent).to(module global device); z=mu+epsilon*exp(logvar/2) with no train/eval gate.
- randn dimensions read z_mu.size(0/1); mu->epsilon is a shape dependency only, not a feature-value input.
- encoder returns (mu,logvar,encoded), and forward returns (mu,logvar,encoded,decoded); decoder receives selected z.
- Decoder Linear projects to 256 before reshape to 64x2x2; transposed convolutions use (k,s,p)=(2,2,0),(4,3,1),(6,3,4).
- Decoder spatial sizes are 2->4->11->28; LeakyReLU follows all three transposed convolutions, then Sigmoid.
- All six convolution calls use default bias=True; all six LeakyReLU calls use API default negative_slope=0.01; no BatchNorm or Dropout.
- num_features constructor argument is unused; source fixes posterior/decoder base map at 64x2x2.
- Losses, label-map reconstruction targets and standalone random decoder calls belong to notebook caller cells, outside forward.
