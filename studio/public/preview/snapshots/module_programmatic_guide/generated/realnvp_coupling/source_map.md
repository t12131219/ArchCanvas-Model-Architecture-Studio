# RealNVP / masked coupling：源码与图框对应

来源：`ikostrikov/pytorch-flows`，固定提交 `bf12ed91b86867b38d74982f5e2d44c248604df9`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `CouplingLayer.__init__` | 407–440 | — |
| E002 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `CouplingLayer.forward` | 442–458 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| realnvp_coupling.root | RealNVP / masked coupling |  | E001,E002 | — |
| realnvp_coupling.x | Input x | [B,4] | E002 | — |
| realnvp_coupling.mask | Fixed mask [1,0,1,0] | [4] | E001 | — |
| realnvp_coupling.body | RealNVP module | [B,4] | E001,E002 | — |
| realnvp_coupling.masked | Condition from retained entries |  | E002 | — |
| realnvp_coupling.maskedop | inputs * mask | [B,4] | E002 | — |
| realnvp_coupling.snet | Independent scale network |  | E002 | — |
| realnvp_coupling.smlp | Linear4->8->8->4 / Tanh | [B,4] | E001,E002 | — |
| realnvp_coupling.smask | log_s * (1-mask) | [B,4] | E002 | — |
| realnvp_coupling.tnet | Independent translation network |  | E002 | — |
| realnvp_coupling.tmlp | Linear4->8->8->4 / ReLU | [B,4] | E001,E002 | — |
| realnvp_coupling.tmask | t * (1-mask) | [B,4] | E002 | — |
| realnvp_coupling.scale | Positive scale |  | E002 | — |
| realnvp_coupling.exp | exp(log_s) | [B,4] | E002 | — |
| realnvp_coupling.affine | Scale then shift |  | E002 | — |
| realnvp_coupling.mul | inputs * s + t | [B,4] | E002 | — |
| realnvp_coupling.det | Changed-entry logdet |  | E002 | — |
| realnvp_coupling.sum | log_s.sum(-1,keepdim=True) | [B,1] | E002 | — |
| realnvp_coupling.y | Masked affine output | [B,4] | E002 | — |
| realnvp_coupling.ld | Logdet per example | [B,1] | E002 | — |

## 与教科书/通用基础图的区别

- Do not share the scale/translation parameters or reorder affine operations.

## 源码事实与边界

- Source mask is an ordinary tensor attribute, not a registered buffer. Selected mask retains entries 0 and 2.
- The two MLPs are independent. Their outputs are masked with 1-mask, which makes the retained entries identity.
- This implementation uses exp(log_s) and x*s+t, unlike the Glow sigmoid and shift-then-scale form.
- Inner init(m) is defined but never applied; do not claim orthogonal initialization.
