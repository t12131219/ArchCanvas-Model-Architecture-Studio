# BatchNormFlow / affine + logdet：源码与图框对应

来源：`ikostrikov/pytorch-flows`，固定提交 `bf12ed91b86867b38d74982f5e2d44c248604df9`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `BatchNormFlow.__init__` | 212–221 | — |
| E002 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `BatchNormFlow.forward` | 223–261 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| flow_batchnorm.root | BatchNormFlow / affine + logdet |  | E001,E002 | — |
| flow_batchnorm.x | Batch input x | [B,4] | E002 | — |
| flow_batchnorm.body | BatchNormFlow module | [B,4] | E001,E002 | — |
| flow_batchnorm.stats | Training statistics |  | E002 | — |
| flow_batchnorm.mean | mean over batch | [4] | E002 | — |
| flow_batchnorm.var | mean((x-mean)^2) + eps | [4] | E002 | — |
| flow_batchnorm.running | Update persistent statistics |  | E002 | — |
| flow_batchnorm.ema | old*m + batch*(1-m) | [4] | E001,E002 | — |
| flow_batchnorm.normalize | Standardize current batch |  | E002 | — |
| flow_batchnorm.norm | (inputs-mean) / sqrt(var) | [B,4] | E002 | — |
| flow_batchnorm.affine | Learned logscale / shift |  | E002 | — |
| flow_batchnorm.out | exp(log_gamma)*x_hat + beta | [B,4] | E002 | — |
| flow_batchnorm.det | Jacobian contribution |  | E002 | — |
| flow_batchnorm.detop | sum(log_gamma - .5*log(var)) | [1] | E002 | — |
| flow_batchnorm.y | Normalized affine y | [B,4] | E002 | — |
| flow_batchnorm.ld | Logdet / length-one tensor | [1] | E002 | — |

## 与教科书/通用基础图的区别

- Do not invent unbiased variance or per-example \[B,1\] determinant as the literal source return.

## 源码事实与边界

- Mean/variance are vectors of length D. Source returns determinant shape \[1\], broadcastable across B.
- Variance uses biased mean squared deviations and adds eps before sqrt; momentum weights the old value, unlike common PyTorch momentum naming.
- State-update arrows indicate mutation; they are not the input used to normalize this batch.
- Mean and variance have separate source producers and consumer ports; the variance glyph does not output a mean_var bundle.
