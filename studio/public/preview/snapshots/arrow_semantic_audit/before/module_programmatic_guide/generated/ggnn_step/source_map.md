# GGNN typed-edge propagation step：源码与图框对应

来源：`JamesChuanggg/ggnn.pytorch`，固定提交 `0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [ggnn-modules/model.py](sources/ggnn-modules/model.py) · `AttrProxy.__getitem__` | 14–15 | — |
| E004 | [ggnn-modules/model.py](sources/ggnn-modules/model.py) · `Propogator.__init__` | 23–40 | — |
| E005 | [ggnn-modules/model.py](sources/ggnn-modules/model.py) · `Propogator.forward` | 42–57 | — |
| E002 | [ggnn-modules/model.py](sources/ggnn-modules/model.py) · `GGNN.__init__` | 66–98 | — |
| E003 | [ggnn-modules/model.py](sources/ggnn-modules/model.py) · `GGNN.forward` | 106–125 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| ggnn_step.root | GGNN typed-edge propagation step / module only | [B,4,8] | E003 | — |
| ggnn_step.state | Current node state H_t | [B,4,8] | E003 | — |
| ggnn_step.adj | Directed typed adjacency A | [B,4,16] | E003 | — |
| ggnn_step.module | GGNN typed-edge propagation step / operators | [B,4,8] | E003 | — |
| ggnn_step.incoming | Incoming type maps | [B,8,8] | E002,E003 | — |
| ggnn_step.incoming.linear | Two distinct Linear 8 -> 8 | 2 x [B,4,8] | E002,E003 | — |
| ggnn_step.incoming.pack | Stack / transpose / view T*N | [B,8,8] | E002,E003 | — |
| ggnn_step.outgoing | Outgoing type maps | [B,8,8] | E002,E003 | — |
| ggnn_step.outgoing.linear | Two distinct Linear 8 -> 8 | 2 x [B,4,8] | E002,E003 | — |
| ggnn_step.outgoing.pack | Stack / transpose / view T*N | [B,8,8] | E002,E003 | — |
| ggnn_step.split | Slice incoming / outgoing blocks | 2 x [B,4,8] | E005 | — |
| ggnn_step.ain | BMM A_in @ states | [B,4,8] | E005 | — |
| ggnn_step.aout | BMM A_out @ states | [B,4,8] | E005 | — |
| ggnn_step.cat | Concat messages + current state | [B,4,24] | E005 | — |
| ggnn_step.reset | Reset gate | [B,4,8] | E004,E005 | — |
| ggnn_step.reset.linear | Linear 24 -> 8 | [B,4,8] | E004,E005 | propogator.reset_gate.0 |
| ggnn_step.reset.sigmoid | Sigmoid | [B,4,8] | E004,E005 | — |
| ggnn_step.update | Update gate | [B,4,8] | E004,E005 | — |
| ggnn_step.update.linear | Linear 24 -> 8 | [B,4,8] | E004,E005 | propogator.update_gate.0 |
| ggnn_step.update.sigmoid | Sigmoid | [B,4,8] | E004,E005 | — |
| ggnn_step.reset_state | r * SAME current state | [B,4,8] | E005 | — |
| ggnn_step.joined | Concat messages + reset state | [B,4,24] | E005 | — |
| ggnn_step.candidate | Candidate transform / source tansform | [B,4,8] | E004,E005 | — |
| ggnn_step.candidate.linear | Linear 24 -> 8 | [B,4,8] | E004,E005 | propogator.tansform.0 |
| ggnn_step.candidate.tanh | Tanh candidate | [B,4,8] | E004,E005 | — |
| ggnn_step.blend | GRU-style complementary blend | [B,4,8] | E005 | — |
| ggnn_step.output | Selected module output | [B,4,8] | E005 | — |

## 与教科书/通用基础图的区别

- Do not replace actual gates with opaque nn.GRU or LSTM merely because the docstring says LSTM.
- Do not share in_i and out_i or give each time step fresh learned parameters.

## 源码事实与边界

- Two edge types own distinct in_i and out_i Linear modules; all time steps reuse these same four modules and the same Propogator gates.
- Adjacency packs incoming and outgoing typed blocks. Separate BMMs form messages; source concatenates both messages and current state for two gates.
- Reset r acts on current state before candidate formation. Update formula is (1-z)*state_cur+z*h_hat, preserving the source gate convention.
- Class is misspelled Propogator and candidate member tansform in source; identities preserve those spellings.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
