# GraphNet (fixed MNIST pixel graph)：源码与图框对应

来源：`https://github.com/rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E005 | [deeplearning-models-batch4/pytorch_ipynb/gnn/gnn-basic-1.py](sources/deeplearning-models-batch4/pytorch_ipynb/gnn/gnn-basic-1.py) · `precompute_adjacency_matrix` | 85–107 | [13] |
| E001 | [deeplearning-models-batch4/pytorch_ipynb/gnn/gnn-basic-1.py](sources/deeplearning-models-batch4/pytorch_ipynb/gnn/gnn-basic-1.py) · `GraphNet` | 119–152 | [15] |
| E002 | [deeplearning-models-batch4/pytorch_ipynb/gnn/gnn-basic-1.py](sources/deeplearning-models-batch4/pytorch_ipynb/gnn/gnn-basic-1.py) · `GraphNet.__init__` | 120–127 | [15] |
| E003 | [deeplearning-models-batch4/pytorch_ipynb/gnn/gnn-basic-1.py](sources/deeplearning-models-batch4/pytorch_ipynb/gnn/gnn-basic-1.py) · `GraphNet.forward` | 131–152 | [15] |
| E004 | [deeplearning-models-batch4/pytorch_ipynb/gnn/gnn-basic-1.py](sources/deeplearning-models-batch4/pytorch_ipynb/gnn/gnn-basic-1.py) · `compute_acc` | 163–172 | [18] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| graphnet.root | GraphNet: fixed pixel graph | 2 x [B,10] | E002,E003 | — |
| graphnet.input | MNIST grayscale image | [B,1,28,28] | E003 | — |
| graphnet.forward | GraphNet forward | (logits,probas) | E003 | — |
| graphnet.layout | Image pixels to graph nodes | [B,N=784,F=1] | E003 | — |
| graphnet.reshape | View pixels as node features | [B,784,1] | E003 | — |
| graphnet.aggregation | Fixed neighbor aggregation | [B,784] | E003 | — |
| graphnet.operands | Node values / fixed weights | X and A operands | E003 | — |
| graphnet.features_operand | Retain pixel features | [B,784,1] | E003 | — |
| graphnet.broadcast | Broadcast fixed adjacency | [B,N,N] | E003 | — |
| graphnet.expand | self.A.expand(B,-1,-1) | [B,784,784] | E003 | same buffer self.A for every batch item |
| graphnet.bmm | Batch MatMul: A @ X | [B,784,1] | E003 | — |
| graphnet.flatten | View aggregated nodes | [B,784] | E003 | — |
| graphnet.head | Whole-image linear head | 2 x [B,10] | E002,E003 | — |
| graphnet.fc | Linear 784 -> 10 / no bias | [B,10] | E002,E003 | fc.weight |
| graphnet.returns | Return logits / probabilities | (logits,probas) | E003 | — |
| graphnet.logits | Retain logits | [B,10] | E003 | — |
| graphnet.softmax | Softmax along classes | [B,10] | E003 | — |
| graphnet.output | Forward return tuple | 2 x [B,10] | E003 | — |
| graphnet.adjacency | Fixed graph / init | fixed A: [784,784] | E005,E002 | fixed adjacency buffer A; constructed once |
| graphnet.coords | Normalized grid coords | coord: [N,2] | E005 | — |
| graphnet.dist | Pairwise Euclidean distance | dist: [N,N] | E005 | — |
| graphnet.kernel | exp(-distance / sigma^2) | A: [N,N] | E005 | — |
| graphnet.threshold | Set A < .01 to zero | A: [N,N] | E005 | — |
| graphnet.float | Convert NumPy to float tensor | A: [N,N] | E005 | — |
| graphnet.row_sum | Sum A over columns | D: [N] | E005 | — |
| graphnet.inv_sqrt | Inverse sqrt / epsilon | D_hat: [N] | E005 | — |
| graphnet.normalize | Scale rows and columns | A_hat: [N,N] | E005 | — |
| graphnet.buffer | register_buffer("A") | self.A: [784,784] | E002 | buffer self.A; no learned parameters; shared across images |

## 与教科书/通用基础图的区别

- Do not replace this simple GraphNet with stacked GCN layers, hidden-node channel projections, ReLU, attention or pooling absent from source.
- Do not label A as learned edges, an image-dependent graph, a row-average matrix, or an extra self-loop addition.
- Do not silently square distance in the source kernel or discard its threshold and degree epsilon.
- Do not chain unused unsqueeze output into expand: source expands self.A directly after overwriting A_tensor.
- Do not mix gnn-basic-edge-1 learned edge predictor into this fixed-buffer variant.

## 源码事实与边界

- Each grayscale28x28 image supplies784 scalar node features; graph edges come only from fixed pixel coordinates.
- The helper computes Euclidean distances of coordinates divided by img_size, then exp(-dist/sigma^2), not exp(-dist^2/sigma^2).
- Weights below.01 are zeroed, then symmetric inverse-square-root degree factors include epsilon1e-5.
- A starts with unit diagonal because distance(i,i)=0; source never separately adds identity or performs row-mean normalization.
- GraphNet.__init__ calls the helper once and registers A as a non-learnable persistent buffer, not an optimizer parameter.
- The same fixed matrix is broadcast over B with self.A.expand(B,-1,-1); batch size comes from input shape, not pixel values.
- The first A_tensor=self.A.unsqueeze(0) assignment executes but is overwritten immediately; its result is not on returned-value dependencies.
- bmm outputs[B,N,1]; only the subsequent view creates[B,N]. The variable name avg_neighbor_features is a weighted sum, not a row arithmetic mean.
- self.fc=Linear784->10 with bias=False classifies the entire node vector; there is no separate per-node learned feature transform.
- forward computes Softmax(dim=1) and actually returns both logits and probabilities. Loss and accuracy decisions are outside forward.
- The selected eval profile does not change operators: no Dropout or BatchNorm exists. No model/helper/scipy computation was executed.
