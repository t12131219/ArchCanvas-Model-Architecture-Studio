# MI-LSTM / multiplicative gate integration：源码与图框对应

来源：`pytorch/pytorch`，固定提交 `a8d6afb511a69687bbb2b7e88a3cf67917e1697e`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py](sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py) · `milstm_cell` | 7–25 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| milstm_projection.root | MI-LSTM / multiplicative gate integration |  | E001 | — |
| mi.x | Current input x | [B,12] | E001 | — |
| mi.h | Previous hidden hx | [B,16] | E001 | — |
| mi.params | Caller weights / coefficients | W_ih:[64,12]; W_hh:[64,16]; vectors:[64] | E001 | — |
| mi.body | MI gate preactivation subgraph | [B,64] | E001 | — |
| mi.wx | Input projection / Wx | [B,64] | E001 | — |
| mi.uz | Hidden projection / Uz | [B,64] | E001 | — |
| mi.coupling | Coupling term | [B,64] | E001 | — |
| mi.alpha_wx | alpha * Wx | [B,64] | E001 | — |
| mi.product | (alpha * Wx) * Uz | [B,64] | E001 | — |
| mi.input_term | beta_i * Wx | [B,64] | E001 | — |
| mi.hidden_term | beta_h * Uz | [B,64] | E001 | — |
| mi.add_input | Coupling + input term | [B,64] | E001 | — |
| mi.add_hidden | Add hidden term | [B,64] | E001 | — |
| mi.bias | Add one gate bias | [B,64] | E001 | — |
| mi.output | Boundary: gates before chunk | [B,64] | E001 | — |

## 与教科书/通用基础图的区别

- Do not replace the interaction term by Wx+Uz or confuse beta_i with beta_h.
- Do not claim gates is a source function return or that this benchmark implements the directory notebook kernel.

## 源码事实与边界

- Multiplicative integration introduces alpha*Wx*Uz plus independently weighted input and hidden terms before the ordinary four-gate LSTM suffix.
- The source multiplication is left-associated: alpha*Wx first, then multiply Uz; the diagram retains that operation order.
- Matrix projections have no separate b_ih/b_hh; a single supplied gate bias is added after the three terms.
- This is a source subgraph with gates as its chosen boundary; milstm_cell actually continues with chunk4 and returns hy,cy.
- Coefficient vectors and matrix weights are caller Tensor arguments; the function itself registers no Parameters.
