# MaskedLinear / conditional projection：源码与图框对应

来源：`ikostrikov/pytorch-flows`，固定提交 `bf12ed91b86867b38d74982f5e2d44c248604df9`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E003 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `get_mask` | 12–29 | — |
| E001 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `MaskedLinear.__init__` | 33–45 | — |
| E002 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `MaskedLinear.forward` | 47–52 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| masked_linear.root | MaskedLinear / conditional projection |  | E001,E002,E003 | — |
| masked_linear.x | Main input x | [B,4] | E002 | — |
| masked_linear.cond | Condition vector c | [B,3] | E002 | — |
| masked_linear.mask | Registered degree mask | [8,4] | E001,E003 | — |
| masked_linear.body | MaskedLinear module | [B,8] | E001,E002,E003 | — |
| masked_linear.masked | Main masked affine |  | E002 | — |
| masked_linear.w_mask | W * mask | [8,4] | E002 | — |
| masked_linear.linear | F.linear(x,W*mask,b) | [B,8] | E002 | — |
| masked_linear.conditional | Independent condition affine |  | E002 | — |
| masked_linear.condlinear | Linear 3 -> 8 / bias=False | [B,8] | E001,E002 | — |
| masked_linear.sum | Add condition projection |  | E002 | — |
| masked_linear.add | output += cond_linear(c) | [B,8] | E002 | — |
| masked_linear.y | Combined projection | [B,8] | E002 | — |

## 与教科书/通用基础图的区别

- No Softmax, dropout or trainable mask is present.
- Do not apply the same mask to the conditional projection.

## 源码事实与边界

- Main and condition projections have distinct weights; only the main weight is masked.
- Source constructor accepts bias but does not pass it to the main Linear, which retains its default bias.
- get_mask compares output and input degrees; a strict autoregressive output mask requires the output degree offset.
