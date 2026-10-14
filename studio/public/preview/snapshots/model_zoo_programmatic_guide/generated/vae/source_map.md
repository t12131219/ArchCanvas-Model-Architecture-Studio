# VAE (MNIST fully connected)：源码与图框对应

来源：`rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [deeplearning-models/pytorch_ipynb/autoencoder/ae-var.py](sources/deeplearning-models/pytorch_ipynb/autoencoder/ae-var.py) · `VariationalAutoencoder` | 74–124 | [9] |
| E002 | [deeplearning-models/pytorch_ipynb/autoencoder/ae-var.py](sources/deeplearning-models/pytorch_ipynb/autoencoder/ae-var.py) · `VariationalAutoencoder.__init__` | 76–94 | [9] |
| E006 | [deeplearning-models/pytorch_ipynb/autoencoder/ae-var.py](sources/deeplearning-models/pytorch_ipynb/autoencoder/ae-var.py) · `VariationalAutoencoder.reparameterize` | 96–102 | [9] |
| E004 | [deeplearning-models/pytorch_ipynb/autoencoder/ae-var.py](sources/deeplearning-models/pytorch_ipynb/autoencoder/ae-var.py) · `VariationalAutoencoder.encoder` | 104–110 | [9] |
| E003 | [deeplearning-models/pytorch_ipynb/autoencoder/ae-var.py](sources/deeplearning-models/pytorch_ipynb/autoencoder/ae-var.py) · `VariationalAutoencoder.decoder` | 112–117 | [9] |
| E005 | [deeplearning-models/pytorch_ipynb/autoencoder/ae-var.py](sources/deeplearning-models/pytorch_ipynb/autoencoder/ae-var.py) · `VariationalAutoencoder.forward` | 119–124 | [9] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| vae.root | MNIST fully connected VAE | (mu, logvar, z, decoded) | E005 | — |
| vae.input | Flattened MNIST features | [B,784] | E005 | — |
| vae.forward | Model forward | four-tensor tuple | E005 | — |
| vae.encoder | Encoder | (mu, logvar, z) | E002,E004 | hidden_1 / z_mean / z_log_var |
| vae.enc_linear | Linear 784 -> 500 | [B,500] | E002,E004 | hidden_1 |
| vae.enc_activation | LeakyReLU | [B,500] | E004 | — |
| vae.posterior | Posterior parameter heads | mu / logvar: independent operands | E004 | — |
| vae.mean_head | Mean head | mu: [B,15] | E002,E004 | z_mean |
| vae.mu | Linear 500 -> 15 | mu: [B,15] | E002,E004 | z_mean |
| vae.logvar_head | Log-variance head | logvar: [B,15] | E002,E004 | z_log_var |
| vae.logvar | Linear 500 -> 15 | logvar: [B,15] | E002,E004 | z_log_var |
| vae.sampling | Reparameterization | z: [B,15] | E006 | — |
| vae.sample_operands | Mean / scaled noise | two Add operands | E006 | — |
| vae.mean_operand | Retain mu | [B,15] | E006 | — |
| vae.scaled_noise | Standard deviation times noise | [B,15] | E006 | — |
| vae.half_logvar | Divide logvar by 2 | [B,15] | E006 | — |
| vae.std | Exponential | std: [B,15] | E006 | — |
| vae.noise_product | std times epsilon | [B,15] | E006 | — |
| vae.z | Add mu + std*epsilon | z: [B,15] | E006 | — |
| vae.encoder_return | Return (mu, logvar, z) | three [B,15] tensors | E004 | — |
| vae.select_z | Select encoded z | [B,15] | E005 | — |
| vae.decoder | Decoder | decoded: [B,784] | E002,E003 | linear_3 / linear_4 |
| vae.dec_linear1 | Linear 15 -> 500 | [B,500] | E002,E003 | linear_3 |
| vae.dec_activation | LeakyReLU | [B,500] | E003 | — |
| vae.dec_linear2 | Linear 500 -> 784 | [B,784] | E002,E003 | linear_4 |
| vae.dec_sigmoid | Sigmoid | decoded: [B,784] | E003 | — |
| vae.return | Return (mu, logvar, z, decoded) | [B,15] x 3; [B,784] | E005 | — |
| vae.epsilon | Internal Gaussian sample | epsilon: [B,15] | E006 | — |

## 与教科书/通用基础图的区别

- A generic VAE chart must show independent mean/log-variance heads, not one shared posterior Linear.
- Sampling must use exp(logvar/2) and an independent epsilon operand, not variance as standard deviation.
- The four-field forward tuple and the retained statistics are visible; drawing only reconstructed pixels omits returned values.
- KL/BCE, optimizer, and dataset flattening are caller operations; no loss node is inserted into model.forward.
- There is no Conv/BatchNorm/transposed-Conv stack in this supplied fully connected implementation.
- Independent source operands are routed from their actual producers; a display scope does not invent a Python tuple or shared-value fork.

## 源码事实与边界

- hidden_1 feeds two independent Linear heads: z_mean and z_log_var.
- z_log_var represents log variance; standard deviation is exp(logvar/2).
- epsilon is created by torch.randn inside reparameterize and is not an external feature input.
- This source samples in both train and eval; no training guard chooses mu instead of z.
- encoder returns (mu, logvar, encoded); decoder consumes only encoded.
- forward returns (mu, logvar, encoded, decoded), not only reconstruction.
- The KL sum and binary cross entropy are computed in the notebook training loop, outside forward.
- The decoder uses Linear 15->500->784, LeakyReLU then Sigmoid; no convolution or deconvolution.
- The graph represents the selected reconstruction call; standalone decoder(rand_features) generation is a separate call.
