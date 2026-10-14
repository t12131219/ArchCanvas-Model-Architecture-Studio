# DGL multi-head graph attention：源码与图框对应

来源：`dmlc/dgl`，固定提交 `3d16000b4170fa741ed9e9667f22ba84d3493026`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [dgl-graph-modules/python/dgl/nn/pytorch/conv/gatconv.py](sources/dgl-graph-modules/python/dgl/nn/pytorch/conv/gatconv.py) · `GATConv.__init__` | 135–196 | — |
| E002 | [dgl-graph-modules/python/dgl/nn/pytorch/conv/gatconv.py](sources/dgl-graph-modules/python/dgl/nn/pytorch/conv/gatconv.py) · `GATConv.forward` | 239–370 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| graph_attention.root | DGL multi-head graph attention / module only | [N,2,4] | E002 | — |
| graph_attention.x | Homogeneous node features | [N,8] | E002 | — |
| graph_attention.g | Supplied DGL graph topology | N nodes / E edges | E002 | — |
| graph_attention.attention | Distinct owned a_l and a_r | each[1,2,4] | E001 | — |
| graph_attention.bias | Owned explicit bias | [8] | E001 | bias |
| graph_attention.module | DGL multi-head graph attention / operators | [N,2,4] | E002 | — |
| graph_attention.projection | ONE shared homogeneous projection | [N,2,4] | E002,E001 | — |
| graph_attention.projection.drop | Feature Dropout .1 | [N,8] | E002,E001 | — |
| graph_attention.projection.linear | Owned Linear8 -> 8 / no bias | [N,8] | E002,E001 | fc.weight; instance=fc |
| graph_attention.projection.heads | View head and feature axes | [N,2,4] | E002,E001 | — |
| graph_attention.left | Source contribution / a_l | [N,2,1] | E002 | attn_l |
| graph_attention.right | Destination contribution / a_r | [N,2,1] | E002 | attn_r |
| graph_attention.score | Edge attention / incoming Softmax | [E,2,1] | E002 | — |
| graph_attention.score.add | Gather el(src) + er(dst) | [E,2,1] | E002 | — |
| graph_attention.score.leaky | LeakyReLU slope .2 | [E,2,1] | E002 | — |
| graph_attention.score.softmax | Incoming-neighbor edge Softmax | [E,2,1] | E002 | — |
| graph_attention.score.drop | Attention Dropout .2 | [E,2,1] | E002 | — |
| graph_attention.message | Weighted source messages / SUM | [N,2,4] | E002 | — |
| graph_attention.biasadd | Broadcast bias / RETAIN heads | [N,2,4] | E002 | — |
| graph_attention.output | Selected module output | [N,2,4] | E002 | — |

## 与教科书/通用基础图的区别

- Do not draw a dense N*N attention matrix, reuse one vector for both endpoint contributions, or reduce the retained head axis.

## 源码事实与边界

- Homogeneous forward shares a single dropped feature tensor and single fc projection for source/destination nodes. Two attention vectors attn_l/attn_r remain independent owned Parameters.
- Implementation computes source and destination scalar contributions separately and ADDS them on edges before LeakyReLU; it does not materialize a concatenation or compute Transformer QK dot products.
- edge_softmax normalizes incoming neighbors for each destination/head, then attention Dropout and weighted-message sum follow. DGL graph kernels remain opaque boundaries.
- Selected residualFalse yields explicit bias\[heads*out_feats\]; no final activation, edge-weight multiplier, head mean/concat or attention tuple is introduced. Output retains \[N,2,4\].
- allow_zero_in_degree=True suppresses the source check; this module does not add self loops automatically.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
