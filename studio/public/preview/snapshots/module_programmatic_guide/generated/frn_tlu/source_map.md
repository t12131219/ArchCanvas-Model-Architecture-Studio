# FRN + learned TLU：源码与图框对应

来源：`rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [rasbt-modules/pytorch_ipynb/cnn/nin-cifar10_filter-response-norm.py](sources/rasbt-modules/pytorch_ipynb/cnn/nin-cifar10_filter-response-norm.py) · `FilterResponseNormalization` | 10–37 | [4] |
| E002 | [rasbt-modules/pytorch_ipynb/cnn/nin-cifar10_filter-response-norm.py](sources/rasbt-modules/pytorch_ipynb/cnn/nin-cifar10_filter-response-norm.py) · `FilterResponseNormalization.__init__` | 11–26 | [4] |
| E003 | [rasbt-modules/pytorch_ipynb/cnn/nin-cifar10_filter-response-norm.py](sources/rasbt-modules/pytorch_ipynb/cnn/nin-cifar10_filter-response-norm.py) · `FilterResponseNormalization.forward` | 28–37 | [4] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| frn.root | FRN + TLU module | [B,192,32,32] | E001 | — |
| frn.input | Feature map x | [B,192,32,32] | E003 | — |
| frn.module | FRN / learned TLU | [B,192,32,32] | E002,E003 | — |
| frn.norm | Response normalization | [B,192,32,32] | E003 | — |
| frn.square | Elementwise x^2 | [B,192,32,32] | E003 | — |
| frn.mean | Mean over H,W | [B,192,1,1] | E003 | — |
| frn.eps_add | nu2 + abs(eps) | [B,192,1,1] | E003 | — |
| frn.rsqrt | Reciprocal square root | [B,192,1,1] | E003 | — |
| frn.scale | Retained x * rsqrt | [B,192,32,32] | E003 | — |
| frn.affine | Affine + learned threshold | [B,192,32,32] | E002,E003 | — |
| frn.gamma_mul | gamma * normalized x | [B,192,32,32] | E002,E003 | gamma |
| frn.beta_add | Add beta | [B,192,32,32] | E002,E003 | beta |
| frn.threshold | Elementwise max(y,tau) | [B,192,32,32] | E002,E003 | tau |
| frn.output | Normalized / thresholded x | [B,192,32,32] | E003 | — |
| frn.state | Parameters / constant | module-owned state | E002,E003 | — |
| frn.gamma | gamma / channel Parameter | [1,192,1,1] | E002 | gamma |
| frn.beta | beta / channel Parameter | [1,192,1,1] | E002 | beta |
| frn.tau | tau / channel Parameter | [1,192,1,1] | E002 | tau |
| frn.epsilon | eps / ordinary tensor | [1] | E002,E003 | — |

## 与教科书/通用基础图的区别

- Do not reuse BatchNorm/LayerNorm statistics: source normalizes uncentered second moment over H,W separately for each B,C.
- Do not set gamma=1/beta=tau=0 merely from the usual paper defaults; this source initializes all3 with normal_.
- Do not draw eps as a learned parameter or registered buffer; its source storage identity differs.
- Do not silently bind the duplicated NiN symbol; only the unique FilterResponseNormalization class is selected.

## 源码事实与边界

- Unique FilterResponseNormalization class computes mean(x.pow(2),(2,3),keepdims=True); no subtraction of mean, batch reduction or running statistics.
- Original x multiplies rsqrt(nu2+abs(eps)); this retained input is a different value from the squared/statistic branch.
- gamma,beta,tau are three registered Parameters of shape\[1,C,1,1\], each initialized with normal_ rather than usual FRN ones/zeros.
- Threshold is torch.max(gamma*x_hat+beta,tau), an elementwise learned TLU; not a max-pool, scalar reduction or fixedzeroReLU.
- eps is a plain Tensor attribute, not registered buffer/Parameter; forward explicitly moves it to tau.device.
- Notebook later redefines NiN as a BN model. This example scopes the unique FRN class directly and does not claim the final NiN binding uses FRN.
