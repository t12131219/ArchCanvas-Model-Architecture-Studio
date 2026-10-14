# Spectral normalization / Linear wrapper：源码与图框对应

来源：`ajbrock/BigGAN-PyTorch`，固定提交 `98459431a5d618d644d54cd1e9fceb1e5045648d`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E007 | [biggan-modules/layers.py](sources/biggan-modules/layers.py) · `proj` | 16–17 | — |
| E005 | [biggan-modules/layers.py](sources/biggan-modules/layers.py) · `gram_schmidt` | 21–24 | — |
| E006 | [biggan-modules/layers.py](sources/biggan-modules/layers.py) · `power_iteration` | 28–50 | — |
| E002 | [biggan-modules/layers.py](sources/biggan-modules/layers.py) · `SN.__init__` | 61–73 | — |
| E001 | [biggan-modules/layers.py](sources/biggan-modules/layers.py) · `SN.W_` | 87–99 | — |
| E003 | [biggan-modules/layers.py](sources/biggan-modules/layers.py) · `SNLinear.__init__` | 117–120 | — |
| E004 | [biggan-modules/layers.py](sources/biggan-modules/layers.py) · `SNLinear.forward` | 121–122 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| spectral_norm_linear.root | Spectral normalization / Linear wrapper |  | E002,E001,E003,E004,E006,E005,E007 | — |
| spectral_norm_linear.x | Data x | [B,16] | E004 | — |
| spectral_norm_linear.weight | Learned W and u buffer | W [8,16]; u0 [1,8] | E003,E002 | — |
| spectral_norm_linear.body | Spectral normalization module | [B,8] | E002,E001,E003,E004,E006,E005,E007 | — |
| spectral_norm_linear.estimate | Power iteration / 1 SV |  | E004 | — |
| spectral_norm_linear.flatten | W.view(out_channels,-1) | [8,16] | E001 | — |
| spectral_norm_linear.vectors | v=norm(uW); u=norm(vW.T) | v[1,16]; u[1,8] | E006,E005 | — |
| spectral_norm_linear.sigma | sigma = squeeze(v W.T u.T) | scalar | E006 | — |
| spectral_norm_linear.normalize | Normalize learned weight |  | E004 | — |
| spectral_norm_linear.divide | weight / svs[0] | [8,16] | E001 | — |
| spectral_norm_linear.state | Training-only buffer writes |  | E004 | — |
| spectral_norm_linear.write | Update u0 and logging sv0 |  | E001,E006 | — |
| spectral_norm_linear.linear | F.linear with normalized weight |  | E004 | — |
| spectral_norm_linear.linearop | F.linear(x,W_,bias) | [B,8] | E004 | — |
| spectral_norm_linear.y | Spectrally normalized output | [B,8] | E004 | — |

## 与教科书/通用基础图的区别

- Do not turn spectral normalization into an activation normalization layer.

## 源码事实与边界

- Power vectors are estimated under no_grad, but the singular value calculation occurs outside that context.
- u0 and sv0 are buffers. sv0 is for logging, whereas division uses current svs\[0\]; replacing the denominator by the buffer changes semantics.
- Every forward normalizes W. Training controls the state writes, not whether normalization happens.
