# Conditional ConvVAE：源码与图框对应

来源：`https://github.com/rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E007 | [deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.py](sources/deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.py) · `to_onehot` | 75–80 | [9] |
| E001 | [deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.py](sources/deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.py) · `ConditionalVariationalAutoencoder` | 83–221 | [9] |
| E002 | [deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.py](sources/deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.py) · `ConditionalVariationalAutoencoder.__init__` | 85–151 | [9] |
| E006 | [deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.py](sources/deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.py) · `ConditionalVariationalAutoencoder.reparameterize` | 154–160 | [9] |
| E004 | [deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.py](sources/deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.py) · `ConditionalVariationalAutoencoder.encoder` | 162–191 | [9] |
| E003 | [deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.py](sources/deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.py) · `ConditionalVariationalAutoencoder.decoder` | 193–214 | [9] |
| E005 | [deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.py](sources/deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.py) · `ConditionalVariationalAutoencoder.forward` | 216–221 | [9] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| ccvae.root | Conditional ConvVAE / MNIST | image + labels -> tuple | E001 | — |
| ccvae.input | MNIST grayscale image | [B,1,28,28] | E005 | — |
| ccvae.forward | Model forward | four-tensor tuple | E005 | — |
| ccvae.encoder | Conditional encoder | (mu,logvar,z): [B,50] x 3 | E002,E004 | — |
| ccvae.encoder_args | Image / condition operands | image + 10 label maps | E004 | — |
| ccvae.retain_image | Retain image values | [B,1,28,28] | E004 | — |
| ccvae.encoder_condition | Encoder label maps | [B,10,28,28] | E007,E004 | — |
| ccvae.encoder_onehot | One-hot labels / 10 classes | [B,10] | E007,E004 | — |
| ccvae.condition_view | View one-hot as channels | [B,10,1,1] | E004 | — |
| ccvae.condition_maps | Ones times one-hot / broadcast H,W | [B,10,28,28] | E004 | — |
| ccvae.encoder_concat | Concat image + label channels | [B,11,28,28] | E004 | — |
| ccvae.enc1 | Encode stage 1 | [B,16,12,12] | E002,E004 | enc_conv_1 |
| ccvae.enc1.conv | Conv2d 11 -> 16 | [B,16,12,12] | E002,E004 | enc_conv_1 |
| ccvae.enc1.activation | LeakyReLU 0.01 | [B,16,12,12] | E004 | — |
| ccvae.enc2 | Encode stage 2 | [B,32,5,5] | E002,E004 | enc_conv_2 |
| ccvae.enc2.conv | Conv2d 16 -> 32 | [B,32,5,5] | E002,E004 | enc_conv_2 |
| ccvae.enc2.activation | LeakyReLU 0.01 | [B,32,5,5] | E004 | — |
| ccvae.enc3 | Encode stage 3 | [B,64,2,2] | E002,E004 | enc_conv_3 |
| ccvae.enc3.conv | Conv2d 32 -> 64 | [B,64,2,2] | E002,E004 | enc_conv_3 |
| ccvae.enc3.activation | LeakyReLU 0.01 | [B,64,2,2] | E004 | — |
| ccvae.posterior | Independent posterior heads | mu + logvar results | E002,E004 | — |
| ccvae.mean_head | Mean head | [B,50] | E002,E004 | z_mean |
| ccvae.mean_view | View 64x2x2 -> 256 | [B,256] | E004 | — |
| ccvae.mu | Linear 256 -> 50 | mu: [B,50] | E002,E004 | z_mean |
| ccvae.logvar_head | Log-variance head | [B,50] | E002,E004 | z_log_var |
| ccvae.logvar_view | View 64x2x2 -> 256 | [B,256] | E004 | — |
| ccvae.logvar | Linear 256 -> 50 | logvar: [B,50] | E002,E004 | z_log_var |
| ccvae.sampling | Reparameterization / single latent | z: [B,50] | E006 | — |
| ccvae.sample_args | Mean / scaled-noise operands | mu + noise operands | E006 | — |
| ccvae.retain_mu | Retain mu values | [B,50] | E006 | — |
| ccvae.scaled_noise | Scale Gaussian noise | std * epsilon: [B,50] | E006 | — |
| ccvae.half_logvar | Divide logvar by 2 | [B,50] | E006 | — |
| ccvae.std | exp(logvar / 2) | std: [B,50] | E006 | — |
| ccvae.noise_product | Multiply std times epsilon | [B,50] | E006 | — |
| ccvae.z | Add mu + std * epsilon | z: [B,50] | E006 | — |
| ccvae.encoder_return | Return (mu, logvar, z) | 3 tensors [B,50] | E004 | — |
| ccvae.select_z | Select encoded z from tuple | [B,50] | E005 | — |
| ccvae.decoder | Conditional decoder | decoded: [B,11,28,28] | E002,E003 | — |
| ccvae.decoder_args | Latent / decoder-label operands | z + 10 label entries | E003 | — |
| ccvae.retain_z | Retain sampled z | [B,50] | E003 | — |
| ccvae.decoder_onehot | One-hot labels again | [B,10] | E007,E003 | — |
| ccvae.decoder_concat | Concat z + one-hot labels | [B,60] | E003 | — |
| ccvae.latent_projection | Latent projection + reshape | [B,64,2,2] | E002,E003 | — |
| ccvae.decoder_linear | Linear 60 -> 256 | [B,256] | E002,E003 | dec_linear_1 |
| ccvae.decoder_view | View as 64x2x2 feature map | [B,64,2,2] | E003 | — |
| ccvae.dec1 | Decode stage 1 | [B,32,4,4] | E002,E003 | dec_deconv_1 |
| ccvae.dec1.conv | ConvTranspose2d 64 -> 32 | [B,32,4,4] | E002,E003 | dec_deconv_1 |
| ccvae.dec1.activation | LeakyReLU 0.01 | [B,32,4,4] | E003 | — |
| ccvae.dec2 | Decode stage 2 | [B,16,11,11] | E002,E003 | dec_deconv_2 |
| ccvae.dec2.conv | ConvTranspose2d 32 -> 16 | [B,16,11,11] | E002,E003 | dec_deconv_2 |
| ccvae.dec2.activation | LeakyReLU 0.01 | [B,16,11,11] | E003 | — |
| ccvae.dec3 | Decode stage 3 | [B,11,28,28] | E002,E003 | dec_deconv_3 |
| ccvae.dec3.conv | ConvTranspose2d 16 -> 11 | [B,11,28,28] | E002,E003 | dec_deconv_3 |
| ccvae.dec3.activation | LeakyReLU 0.01 | [B,11,28,28] | E003 | — |
| ccvae.sigmoid | Sigmoid decoded pixels | [B,11,28,28] | E003 | — |
| ccvae.return | Return (mu, logvar, z, decoded) | [B,50] x 3; [B,11,28,28] | E005 | — |
| ccvae.epsilon | Internal Gaussian epsilon | [B,50] | E006 | — |
| ccvae.labels | External MNIST class labels | targets: [B] | E005 | — |

## 与教科书/通用基础图的区别

- No model-specific reference PNG is supplied; this graph follows the fixed notebook rather than a generic VAE illustration.
- Retain asymmetric decoder strides 2/3/3 and padding 0/1/4, rather than inventing a mirror of encoder stride 2.
- Draw one latent level and distinct mean/log-variance heads; logical operand bundles are not literal source tuples.
- Do not replace final LeakyReLU+Sigmoid by Sigmoid directly after convolution or by Softmax.
- Evaluation still samples epsilon; no deterministic z=mu path is present in this source.
- Preserve encoder spatial condition injection and decoder latent-vector condition injection as two separate calls, not a single shared embedding.
- The returned decoded tensor has 11 channels; do not silently fix it to one image channel merely because the visualization selects channel zero.
- Changing num_classes changes encoder/Linear dimensions but does not change hard-coded decoder out_channels=11.

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
- Encoder one-hot labels broadcast to 10 constant spatial maps and concatenate with the image before Conv2d(11,16).
- Decoder calls to_onehot again and concatenates 50 latent entries with 10 label entries before Linear(60,256).
- Final decoder ConvTranspose2d outputs 11 hard-coded channels, not a one-channel image; training BCE reconstructs augmented image+label maps.
- Only visualization slices decoded[:,0]; forward returns all 11 channels, with no label inference or Softmax head.
