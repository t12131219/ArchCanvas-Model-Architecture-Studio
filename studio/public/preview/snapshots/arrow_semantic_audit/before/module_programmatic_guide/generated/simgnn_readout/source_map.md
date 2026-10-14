# SimGNN graph attention readout：源码与图框对应

来源：`benedekrozemberczki/SimGNN`，固定提交 `be3ee6193a7c286336260f6479a6aee8bdc56f8c`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E002 | [simgnn-modules/src/layers.py](sources/simgnn-modules/src/layers.py) · `AttentionModule.setup_weights` | 18–23 | — |
| E001 | [simgnn-modules/src/layers.py](sources/simgnn-modules/src/layers.py) · `AttentionModule.forward` | 31–41 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| simgnn_readout.root | SimGNN graph attention readout / module only | [8,1] | E001 | — |
| simgnn_readout.embedding | Retained node embeddings X | [N,8] | E001 | — |
| simgnn_readout.weight | Owned context weight W | [8,8] | E002 | weight_matrix |
| simgnn_readout.module | SimGNN graph attention readout / operators | [8,1] | E001 | — |
| simgnn_readout.context | Mean projected global context | [8,1] | E001 | — |
| simgnn_readout.context.mm | Node embeddings @ W | [N,8] | E001 | — |
| simgnn_readout.context.mean | Mean over nodes / dim0 | [8] | E001 | — |
| simgnn_readout.context.tanh | Tanh global context | [8] | E001 | — |
| simgnn_readout.context.view | View column context | [8,1] | E001 | — |
| simgnn_readout.score | Independent per-node gates | [N,1] | E001 | — |
| simgnn_readout.score.mm | SAME X @ context | [N,1] | E001 | — |
| simgnn_readout.score.sigmoid | Sigmoid / NOT Softmax | [N,1] | E001 | — |
| simgnn_readout.transpose | Transpose SAME node embeddings | [8,N] | E001 | — |
| simgnn_readout.readout | X.T @ sigmoid node weights | [8,1] | E001 | — |
| simgnn_readout.output | Selected module output | [8,1] | E001 | — |

## 与教科书/通用基础图的区别

- Do not substitute graph GAT incoming edge Softmax, dot-product sequence attention or normalize the weighted readout.

## 源码事实与边界

- One W\[8,8\] creates a mean projected global context, then Tanh. The ORIGINAL node embeddings independently compute sigmoid gates against this context.
- Final representation is X.T @ sigmoid_scores, a weighted SUM. Sigmoid gates neither sum to one nor become Softmax attention.
- The SAME original embedding appears in context projection, node scoring and final readout; the output is a column \[8,1\].
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
