# APPNP restart propagation：源码与图框对应

来源：`benedekrozemberczki/APPNP`，固定提交 `338d98980ee8748e652630dd422341ef8b2a354a`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [appnp-modules/src/appnp_layer.py](sources/appnp-modules/src/appnp_layer.py) · `APPNPModel.forward` | 138–182 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| appnp_propagation.root | APPNP restart propagation / module only | [N,8] | E001 | — |
| appnp_propagation.h0 | Retained initial H0 | [N,8] | E001 | — |
| appnp_propagation.edges | Sparse topology / weights | indices[2,E], values[E] | E001 | — |
| appnp_propagation.module | APPNP restart propagation / operators | [N,8] | E001 | — |
| appnp_propagation.drop | Edge weight Dropout / once | [E] | E001 | — |
| appnp_propagation.step | Repeat K=3 / sparse propagation | [N,8] | E001 | —; 3 |
| appnp_propagation.step.spmm | A_drop @ current H | [N,8] | E001 | — |
| appnp_propagation.scale | Scale propagated state by 1-alpha | [N,8] | E001 | — |
| appnp_propagation.restart | Scale SAME H0 by alpha | [N,8] | E001 | — |
| appnp_propagation.add | Add restart to propagated state | [N,8] | E001 | — |
| appnp_propagation.output | Selected module output | [N,8] | E001 | — |

## 与教科书/通用基础图的区别

- Do not put log_softmax or the predictor MLP inside this propagation module.
- Do not resample edge dropout each iteration or use alpha*H_t as restart.

## 源码事实与边界

- One representative recurrence is shown with K=3 declared example repeats. Feedback edges carry next H, not fresh task logits.
- Edge Dropout occurs before the loop and is shared within a forward. Restart is always the same latent_features_2, never the latest H.
- Normalized topology is external at the chosen module boundary; torch_sparse.spmm remains a library boundary.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
