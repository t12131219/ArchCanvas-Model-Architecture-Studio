# MADESplit / autoregressive affine：源码与图框对应

来源：`ikostrikov/pytorch-flows`，固定提交 `bf12ed91b86867b38d74982f5e2d44c248604df9`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E005 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `get_mask` | 12–29 | — |
| E003 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `MaskedLinear.__init__` | 33–45 | — |
| E004 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `MaskedLinear.forward` | 47–52 | — |
| E001 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `MADESplit.__init__` | 63–100 | — |
| E002 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `MADESplit.forward` | 102–130 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| made_split.root | MADESplit / autoregressive affine |  | E001,E002,E003,E004,E005 | — |
| made_split.x | Input x | [B,4] | E002 | — |
| made_split.body | MADESplit module | [B,4] | E001,E002,E003,E004,E005 | — |
| made_split.mnet | s_* network -> m |  | E002 | — |
| made_split.mnetjoin | MaskedLinear 4 -> 8 | [B,8] | E001,E004 | — |
| made_split.mnetact1 | Tanh | [B,8] | E001 | — |
| made_split.mnethidden | MaskedLinear 8 -> 8 | [B,8] | E001,E004 | — |
| made_split.mnetact2 | Tanh | [B,8] | E001 | — |
| made_split.mnetout | MaskedLinear 8 -> 4 | [B,4] | E001,E004 | — |
| made_split.anet | t_* network -> a |  | E002 | — |
| made_split.anetjoin | MaskedLinear 4 -> 8 | [B,8] | E001,E004 | — |
| made_split.anetact1 | ReLU | [B,8] | E001 | — |
| made_split.anethidden | MaskedLinear 8 -> 8 | [B,8] | E001,E004 | — |
| made_split.anetact2 | ReLU | [B,8] | E001 | — |
| made_split.anetout | MaskedLinear 8 -> 4 | [B,4] | E001,E004 | — |
| made_split.shift | Subtract conditional mean |  | E002 | — |
| made_split.sub | inputs - m | [B,4] | E002 | — |
| made_split.scale | Inverse scale |  | E002 | — |
| made_split.exp | exp(-a) | [B,4] | E002 | — |
| made_split.affine | Affine output |  | E002 | — |
| made_split.mul | (inputs-m) * exp(-a) | [B,4] | E002 | — |
| made_split.det | Log determinant |  | E002 | — |
| made_split.sum | -a.sum(-1,keepdim=True) | [B,1] | E002 | — |
| made_split.u | Transformed u | [B,4] | E002 | — |
| made_split.ld | Logdet per example | [B,1] | E002 | — |

## 与教科书/通用基础图的区别

- Do not swap m/a, use dense unmasked hidden layers, or claim pre_exp_tanh acts in MADE.

## 源码事实与边界

- Degree masks enforce strict autoregressive dependence through the output degree offset; masks are registered buffers.
- MADESplit uses independent s_* and t_* networks. Despite their names, s_* predicts m with Tanh and t_* predicts a with ReLU.
- Inverse builds coordinates one at a time with the same learned networks; the direct view is a DAG, not that inverse execution.
- The returned logdet follows the exact source expression. It is not a third sequential layer applied to u.
