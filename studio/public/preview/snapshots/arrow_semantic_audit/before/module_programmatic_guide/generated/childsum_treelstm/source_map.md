# Child-Sum TreeLSTM / per-child forgetting：源码与图框对应

来源：`dasguptar/treelstm.pytorch`，固定提交 `228a314add09fc7f39ea752aa7b1fcf756cfe277`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [childsum-treelstm-sequence/treelstm/model.py](sources/childsum-treelstm-sequence/treelstm/model.py) · `ChildSumTreeLSTM.__init__` | 10–17 | — |
| E003 | [childsum-treelstm-sequence/treelstm/model.py](sources/childsum-treelstm-sequence/treelstm/model.py) · `ChildSumTreeLSTM.node_forward` | 19–34 | — |
| E002 | [childsum-treelstm-sequence/treelstm/model.py](sources/childsum-treelstm-sequence/treelstm/model.py) · `ChildSumTreeLSTM.forward` | 36–48 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| childsum_treelstm.root | Child-Sum TreeLSTM / per-child forgetting |  | E001,E002,E003 | — |
| tree.x | One node input vector | [12] | E003,E002 | — |
| tree.child_c | Three child cell states | [3,16] | E003 | — |
| tree.child_h | Three child hidden states | [3,16] | E003 | — |
| tree.body | Child-Sum TreeLSTM / one node | c,h:[1,16] | E001,E003 | — |
| tree.iou | Node gates from summed children | i,o,u:[1,16] | E001,E003 | — |
| tree.ioux | Node input Linear / ioux | [48] | E001,E003 | ioux |
| tree.hsum | Sum child hidden / dim0 | [1,16] | E003 | — |
| tree.iouh | Child-sum Linear / iouh | [1,48] | E001,E003 | iouh |
| tree.iou_add | ioux + iouh / broadcast | [1,48] | E003 | — |
| tree.split | Split gates / i,o,u | three [1,16] | E003 | — |
| tree.i | Input gate / Sigmoid | [1,16] | E003 | — |
| tree.o | Output gate / Sigmoid | [1,16] | E003 | — |
| tree.u | Candidate / Tanh | [1,16] | E003 | — |
| tree.forget | Per-child forgetting | retained:[1,16] | E001,E003 | — |
| tree.fx | Node input Linear / fx | [16] | E001,E003 | fx |
| tree.fh | Per-child Linear / fh | [3,16] | E001,E003 | fh |
| tree.repeat | Repeat fx across3 children | [3,16] | E003 | — |
| tree.f_add | fh(child_h) + repeated fx | [3,16] | E003 | — |
| tree.f | Per-child forget / Sigmoid | [3,16] | E003 | — |
| tree.fc | Forget * each child cell | [3,16] | E003 | — |
| tree.fsum | Sum retained children / dim0 | [1,16] | E003 | — |
| tree.new | Input gate * candidate | [1,16] | E003 | — |
| tree.cell | New cell + retained children | [1,16] | E003 | — |
| tree.ctanh | Tanh new cell c | [1,16] | E003 | — |
| tree.hidden | Output gate * Tanh(c) | [1,16] | E003 | — |
| tree.output | Return c, h / cell first | c,h:[1,16] | E003 | — |

## 与教科书/通用基础图的区别

- Do not sum children before fh and thereby replace K forget gates with one shared forget gate.
- Do not swap child_c and child_h or label node_forward outputs as a full similarity model prediction.

## 源码事实与边界

- Child-Sum TreeLSTM first reduces child hidden states for shared i/o/u gates, but computes a distinct forget value for every child before reducing retained child cells.
- The selected source caller inputs\[tree.idx\] is a rank1 node vector; its ioux output broadcasts against the rank2 child-sum projection.
- Four independent nn.Linear instances ioux,iouh,fx,fh include default biases; repeat and per-child batch rows share fx/fh parameters.
- The source returns cell c first, hidden h second; this differs from the conventional hy,cy order of a sequence LSTM cell.
- The class recursively obtains child states outside node_forward; leaf callers supply a single zero child state, not a fabricated zero-length children tensor.
