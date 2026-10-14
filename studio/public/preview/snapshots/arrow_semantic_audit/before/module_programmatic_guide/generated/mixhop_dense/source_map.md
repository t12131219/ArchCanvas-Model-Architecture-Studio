# MixHop dense power branch：源码与图框对应

来源：`benedekrozemberczki/MixHop-and-N-GCN`，固定提交 `e9df5eb988f0dbe5192ac87902c55cbe6d8191fe`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [mixhop-modules/src/layers.py](sources/mixhop-modules/src/layers.py) · `DenseNGCNLayer.define_parameters` | 92–97 | — |
| E002 | [mixhop-modules/src/layers.py](sources/mixhop-modules/src/layers.py) · `DenseNGCNLayer.forward` | 106–124 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| mixhop_dense.root | MixHop dense power branch / module only | [N,4] | E002 | — |
| mixhop_dense.x | Dense node features | [N,12] | E002 | — |
| mixhop_dense.adj | Supplied normalized sparse A | [N,N] | E002 | — |
| mixhop_dense.weight | Owned dense W | [12,4] | E001 | weight_matrix |
| mixhop_dense.bias | Owned dense bias | [1,4] | E001 | bias |
| mixhop_dense.module | MixHop dense power branch / operators | [N,4] | E002 | — |
| mixhop_dense.project | Dense X @ W | [N,4] | E002 | — |
| mixhop_dense.drop | Dropout .5 / caller mode | [N,4] | E002 | — |
| mixhop_dense.prop0 | A @ features / pass1 | [N,4] | E002 | — |
| mixhop_dense.prop1 | A @ features / pass2 | [N,4] | E002 | — |
| mixhop_dense.biasadd | Add bias AFTER propagation | [N,4] | E002 | — |
| mixhop_dense.output | Selected module output | [N,4] | E002 | — |

## 与教科书/通用基础图的区别

- Do not merge sparse/dense NGNC branches merely because both names contain GCN.
- Do not move bias before propagation or add a missing ReLU.

## 源码事实与边界

- DenseNGCN differs materially from SparseNGCN: dense mm, Dropout, iterations-1 adjacency products, THEN bias; no ReLU.
- iterations3 denotes two repeated uses of supplied adjacency, and the SAME node-feature weight is applied only once.
- Sparse multiplication remains an opaque torch_sparse library boundary; normalization is supplied externally.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
