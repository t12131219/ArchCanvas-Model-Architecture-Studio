# GRUCell / explicit reset-update gates：源码与图框对应

来源：`pytorch/pytorch`，固定提交 `a8d6afb511a69687bbb2b7e88a3cf67917e1697e`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py](sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py) · `gru_cell` | 118–129 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| gru_cell.root | GRUCell / explicit reset-update gates |  | E001 | — |
| gru.x | Current input x | [B,16] | E001 | — |
| gru.h | Previous hidden h | [B,16] | E001 | — |
| gru.params | Caller weights / biases | W_ih,W_hh:[48,16]; b:[48] | E001 | — |
| gru.body | GRU / one functional step | [B,16] | E001 | — |
| gru.gi | Input affine: x W_ih^T + b_ih | [B,48] | E001 | — |
| gru.gh | Hidden affine: h W_hh^T + b_hh | [B,48] | E001 | — |
| gru.ci | Chunk input affine / r,z,n | [B,16] | E001 | — |
| gru.ch | Chunk hidden affine / r,z,n | [B,16] | E001 | — |
| gru.reset | Reset gate r | [B,16] | E001 | — |
| gru.r_add | i_r + h_r | [B,16] | E001 | — |
| gru.r | Sigmoid reset gate | [B,16] | E001 | — |
| gru.update | Update gate z / source inputgate | [B,16] | E001 | — |
| gru.z_add | i_i + h_i | [B,16] | E001 | — |
| gru.z | Sigmoid update gate | [B,16] | E001 | — |
| gru.rhn | r * h_n / bias already included | [B,16] | E001 | — |
| gru.candidate | Candidate n | [B,16] | E001 | — |
| gru.n_add | i_n + r * h_n | [B,16] | E001 | — |
| gru.n | Tanh candidate | [B,16] | E001 | — |
| gru.delta | h_previous - n | [B,16] | E001 | — |
| gru.zdelta | z * (h_previous - n) | [B,16] | E001 | — |
| gru.hy | n + z * (h_previous - n) | [B,16] | E001 | — |
| gru.output | Next hidden hy / one tensor | [B,16] | E001 | — |

## 与教科书/通用基础图的区别

- Do not reset hidden before W_hh; do not swap reset/update gates; do not invent an LSTM cell state.
- Do not present the supplementary benchmark as the kernel extracted from the directory-listed rasbt notebook.

## 源码事实与边界

- The rasbt GRU model previously had an opaque nn.GRU boundary; this separately sourced benchmark function exposes a concrete GRU step.
- gi and gh each include their own bias before chunk(3,1); reset multiplies the complete h_n affine slice, including b_hh.
- The source inputgate is the standard update z. hy is n + z*(hidden-n); z retains old state.
- Weights and biases are Tensor arguments; this function does not register Parameters or prove the caller uses this implementation.
