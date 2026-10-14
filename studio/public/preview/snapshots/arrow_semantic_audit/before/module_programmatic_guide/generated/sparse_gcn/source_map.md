# Sparse GCN layer：源码与图框对应

来源：`tkipf/pygcn`，固定提交 `1600b5b748b3976413d1e307540ccc62605b4d6d`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [pygcn-modules/pygcn/layers.py](sources/pygcn-modules/pygcn/layers.py) · `GraphConvolution.__init__` | 14–23 | — |
| E002 | [pygcn-modules/pygcn/layers.py](sources/pygcn-modules/pygcn/layers.py) · `GraphConvolution.forward` | 31–37 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| sparse_gcn.root | Sparse GCN layer / module only | [N,4] | E002 | — |
| sparse_gcn.x | Node features X | [N,8] | E002 | — |
| sparse_gcn.adj | Supplied sparse adjacency | [N,N] | E002 | — |
| sparse_gcn.weight | Owned weight W | [8,4] | E001 | weight |
| sparse_gcn.bias | Owned bias b | [4] | E001 | bias |
| sparse_gcn.module | Sparse GCN layer / operators | [N,4] | E002 | — |
| sparse_gcn.project | Feature projection | [N,4] | E002 | — |
| sparse_gcn.project.mm | X @ W | [N,4] | E002 | — |
| sparse_gcn.aggregate | Sparse neighbor sum | [N,4] | E002 | — |
| sparse_gcn.aggregate.spmm | A @ support | [N,4] | E002 | — |
| sparse_gcn.add | Broadcast bias add | [N,4] | E002 | — |
| sparse_gcn.output | Selected module output | [N,4] | E002 | — |

## 与教科书/通用基础图的区别

- Do not substitute the existing fixed GraphNet A@pixels: this layer has an actual learned node-feature projection.
- Do not add preprocessing or classifier layers from a textbook GCN.

## 源码事实与边界

- Source projects node features before sparse adjacency multiplication.
- Adjacency is supplied by caller; this layer does not add self-loops, compute degree normalization or apply ReLU.
- Weight\[Nin,Nout\] and bias\[Nout\] are owned Parameters; same weight is used for every node.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
