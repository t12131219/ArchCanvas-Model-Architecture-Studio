# Sigmoid bijector / Jacobian branch：源码与图框对应

来源：`ikostrikov/pytorch-flows`，固定提交 `bf12ed91b86867b38d74982f5e2d44c248604df9`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E002 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `Sigmoid.forward` | 184–192 | — |
| E001 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `Logit.forward` | 199–203 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| sigmoid_bijector.root | Sigmoid bijector / Jacobian branch |  | E002,E001 | — |
| sigmoid_bijector.x | Real-valued x | [B,4] | E002 | — |
| sigmoid_bijector.body | Sigmoid bijector module | [B,4] | E002,E001 | — |
| sigmoid_bijector.nonlinear | Elementwise transform |  | E002 | — |
| sigmoid_bijector.sigmoid | sigmoid(inputs) | [B,4] | E002 | — |
| sigmoid_bijector.jacobian | Derivative and log-volume |  | E002 | — |
| sigmoid_bijector.derivative | s(x) * (1-s(x)) | [B,4] | E002 | — |
| sigmoid_bijector.logsum | log then sum over D | [B,1] | E002 | — |
| sigmoid_bijector.y | s(x) in (0,1) | [B,4] | E002 | — |
| sigmoid_bijector.ld | Logdet per example | [B,1] | E002 | — |

## 与教科书/通用基础图的区别

- Do not silently replace the actual buggy Logit.forward by the textbook logit implementation.

## 源码事实与边界

- Sigmoid source implements a real direct/inverse bijector and returns the sum of log derivative.
- Logit subclass passes inverse as the second positional cond_inputs argument, leaving mode=direct. It is therefore not drawn as a correctly implemented logit wrapper.
