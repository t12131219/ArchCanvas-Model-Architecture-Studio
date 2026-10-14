# MADE / autoregressive affine：源码与图框对应

来源：`ikostrikov/pytorch-flows`，固定提交 `bf12ed91b86867b38d74982f5e2d44c248604df9`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E005 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `get_mask` | 12–29 | — |
| E003 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `MaskedLinear.__init__` | 33–45 | — |
| E004 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `MaskedLinear.forward` | 47–52 | — |
| E001 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `MADE.__init__` | 137–161 | — |
| E002 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `MADE.forward` | 163–177 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| made_affine.root | MADE / autoregressive affine |  | E001,E002,E003,E004,E005 | — |
| made_affine.x | Input x | [B,4] | E002 | — |
| made_affine.body | MADE module | [B,4] | E001,E002,E003,E004,E005 | — |
| made_affine.net | Shared masked network |  | E002 | — |
| made_affine.netjoin | MaskedLinear 4 -> 8 | [B,8] | E001,E004 | — |
| made_affine.netact1 | ReLU | [B,8] | E001 | — |
| made_affine.nethidden | MaskedLinear 8 -> 8 | [B,8] | E001,E004 | — |
| made_affine.netact2 | ReLU | [B,8] | E001 | — |
| made_affine.netout | MaskedLinear 8 -> 8 | [B,8] | E001,E004 | — |
| made_affine.heads | Split m and a |  | E002 | — |
| made_affine.chunk | chunk(2,dim=1) | each [B,4] | E002 | — |
| made_affine.shift | Subtract conditional mean |  | E002 | — |
| made_affine.sub | inputs - m | [B,4] | E002 | — |
| made_affine.scale | Inverse scale |  | E002 | — |
| made_affine.exp | exp(-a) | [B,4] | E002 | — |
| made_affine.affine | Affine output |  | E002 | — |
| made_affine.mul | (inputs-m) * exp(-a) | [B,4] | E002 | — |
| made_affine.det | Log determinant |  | E002 | — |
| made_affine.sum | -a.sum(-1,keepdim=True) | [B,1] | E002 | — |
| made_affine.u | Transformed u | [B,4] | E002 | — |
| made_affine.ld | Logdet per example | [B,1] | E002 | — |

## 与教科书/通用基础图的区别

- Do not swap m/a, use dense unmasked hidden layers, or claim pre_exp_tanh acts in MADE.

## 源码事实与边界

- Degree masks enforce strict autoregressive dependence through the output degree offset; masks are registered buffers.
- MADE shares a masked trunk and chunks its 2D output into m then a; pre_exp_tanh is accepted but unused by this class.
- Inverse builds coordinates one at a time with the same learned networks; the direct view is a DAG, not that inverse execution.
- The returned logdet follows the exact source expression. It is not a third sequential layer applied to u.
