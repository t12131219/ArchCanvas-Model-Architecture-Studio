# Split prior / conditional Gaussian density：源码与图框对应

来源：`rosinality/glow-pytorch`，固定提交 `97081ff115a694cf04aeedbd58447f33d242c879`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E003 | [glow-modules/model.py](sources/glow-modules/model.py) · `ZeroConv2d.__init__` | 140–146 | — |
| E004 | [glow-modules/model.py](sources/glow-modules/model.py) · `ZeroConv2d.forward` | 148–153 | — |
| E005 | [glow-modules/model.py](sources/glow-modules/model.py) · `gaussian_log_p` | 245–246 | — |
| E001 | [glow-modules/model.py](sources/glow-modules/model.py) · `Block.__init__` | 254–269 | — |
| E002 | [glow-modules/model.py](sources/glow-modules/model.py) · `Block.forward` | 271–296 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| glow_split_prior.root | Split prior / conditional Gaussian density |  | E001,E002,E003,E004,E005 | — |
| glow_split_prior.x | Features after omitted flows | [B,8,4,4] | E002 | — |
| glow_split_prior.body | Split prior module | [B,4,4,4] | E001,E002,E003,E004,E005 | — |
| glow_split_prior.split | Split channel halves |  | E002 | — |
| glow_split_prior.splitop | out.chunk(2,dim=1) | two [B,4,4,4] | E002 | — |
| glow_split_prior.prior | Prior on retained half |  | E002 | — |
| glow_split_prior.priorop | ZeroConv2d prior 4 -> 8 | [B,8,4,4] | E001,E002,E004 | instance=prior |
| glow_split_prior.heads | Mean / log standard deviation |  | E002 | — |
| glow_split_prior.headsop | chunk -> mean, log_sd | each [B,4,4,4] | E002 | — |
| glow_split_prior.density | Elementwise Gaussian log_p |  | E002 | — |
| glow_split_prior.gauss | gaussian_log_p(z_new,mean,log_sd) | [B,4,4,4] | E002,E005 | — |
| glow_split_prior.reduce | Per-example sum |  | E002 | — |
| glow_split_prior.sum | view(B,-1).sum(1) | [B] | E002 | — |
| glow_split_prior.keep | Retained out | [B,4,4,4] | E002 | — |
| glow_split_prior.z | Split latent z_new | [B,4,4,4] | E002 | — |
| glow_split_prior.lp | Conditional log_p | [B] | E002 | — |

## 与教科书/通用基础图的区别

- Do not call this a whole Glow block or add a reparameterization sample to forward.

## 源码事实与边界

- Prior sees retained out, whereas density is evaluated on z_new; these operands cannot be interchanged.
- log_sd denotes log standard deviation; density denominator is exp(2*log_sd), not exp(log_sd).
- The three outputs are independent values; there is no z-to-retained tensor chain.
