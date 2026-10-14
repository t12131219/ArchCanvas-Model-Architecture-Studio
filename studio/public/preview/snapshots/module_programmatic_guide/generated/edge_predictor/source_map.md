# EdgePredictor (coordinate-to-adjacency module)：源码与图框对应

来源：`rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E003 | [rasbt-modules/pytorch_ipynb/gnn/gnn-basic-edge-1.py](sources/rasbt-modules/pytorch_ipynb/gnn/gnn-basic-edge-1.py) · `make_coordinate_array` | 90–104 | [13] |
| E001 | [rasbt-modules/pytorch_ipynb/gnn/gnn-basic-edge-1.py](sources/rasbt-modules/pytorch_ipynb/gnn/gnn-basic-edge-1.py) · `GraphNet.__init__` | 109–123 | [13] |
| E002 | [rasbt-modules/pytorch_ipynb/gnn/gnn-basic-edge-1.py](sources/rasbt-modules/pytorch_ipynb/gnn/gnn-basic-edge-1.py) · `GraphNet.forward` | 128–151 | [13] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| edge.root | EdgePredictor / selected subgraph | coord -> A | E001,E002 | — |
| edge.coord | Read registered coord buffer | [784,784,4] | E001,E002 | — |
| edge.forward | Coordinate-to-adjacency module | A: [N,N] | E002 | — |
| edge.mlp | Shared edge MLP / 4 -> 32 -> 1 | [N,N,1] | E001,E002 | instance=self.pred_edge_fc |
| edge.linear1 | Linear 4 -> 32 | [784,784,32] | E001,E002 | pred_edge_fc.0; instance=self.pred_edge_fc.0 |
| edge.relu | ReLU | [784,784,32] | E001,E002 | — |
| edge.linear2 | Linear 32 -> 1 | [784,784,1] | E001,E002 | pred_edge_fc.2; instance=self.pred_edge_fc.2 |
| edge.tanh | Tanh / signed edge weights | [784,784,1] | E001,E002 | — |
| edge.squeeze | squeeze() + assign self.A | A: [784,784] | E002 | — |
| edge.output | Module result / adjacency A | [784,784] | E002 | — |
| edge.init | Coordinate buffer / constructor | coord: [N,N,4] | E003,E001 | — |
| edge.grid | Grid coordinates / standardize | [784,2] | E003 | — |
| edge.pairs | Ordered coordinate pairs | [784,784,4] | E003 | — |
| edge.buffer | Register coord buffer | coord: [784,784,4] | E001 | — |

## 与教科书/通用基础图的区别

- Do not draw image pixels or batch B as edge-predictor inputs.
- Do not draw N*N independent MLPs, learned coordinate embeddings, normalized attention or guaranteed symmetric edges.
- Do not include the enclosing GraphNet classifier in this module-only example.

## 源码事实与边界

- This module boundary selects only self.pred_edge_fc(self.coord).squeeze(); pixel reshape/bmm, fc and Softmax are outside the artifact.
- make_coordinate_array standardizes each coordinate axis with epsilon1e-5, converts to float and concatenates ordered pairs.
- coord\[i,j\] is \[col_j,row_j,col_i,row_i\]; the helper does not encode undirected pair symmetry.
- coord is a fixed persistent buffer; one shared Sequential instance applies Linear4->32,ReLU,Linear32->1,Tanh to every pair.
- Linear defaults retain both biases; only the two Linear families contribute193 learned scalar parameters within this boundary.
- The resulting signed A depends on learned MLP weights and fixed coordinates, not image intensities or batch size.
- self.A is recomputed and assigned to an ordinary tensor attribute each forward; it is not registered as a parameter or buffer.
- No threshold, Softmax, symmetric constraint or degree normalization is present in this edge predictor.
- squeeze has no dim argument; with selected N784 it removes the final singleton. Other degenerate sizes need a separately reviewed shape profile.
