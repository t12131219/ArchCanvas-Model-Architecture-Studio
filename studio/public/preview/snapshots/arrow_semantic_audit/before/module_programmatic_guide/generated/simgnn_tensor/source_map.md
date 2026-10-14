# SimGNN neural tensor comparison：源码与图框对应

来源：`benedekrozemberczki/SimGNN`，固定提交 `be3ee6193a7c286336260f6479a6aee8bdc56f8c`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E002 | [simgnn-modules/src/layers.py](sources/simgnn-modules/src/layers.py) · `TenorNetworkModule.setup_weights` | 56–66 | — |
| E001 | [simgnn-modules/src/layers.py](sources/simgnn-modules/src/layers.py) · `TenorNetworkModule.forward` | 76–89 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| simgnn_tensor.root | SimGNN neural tensor comparison / module only | [4,1] | E001 | — |
| simgnn_tensor.e1 | Graph representation1 | [8,1] | E001 | — |
| simgnn_tensor.e2 | Graph representation2 | [8,1] | E001 | — |
| simgnn_tensor.tensorweight | Owned bilinear tensor W | [8,8,4] | E002 | weight_matrix |
| simgnn_tensor.blockweight | Distinct owned block weight | [4,16] | E002 | weight_matrix_block |
| simgnn_tensor.bias | Owned comparison bias | [4,1] | E002 | bias |
| simgnn_tensor.module | SimGNN neural tensor comparison / operators | [4,1] | E001 | — |
| simgnn_tensor.bilinear | Tensor contraction / graph pair | [4,1] | E001 | — |
| simgnn_tensor.bilinear.first | e1.T @ W.view(8,-1) | [1,32] | E001 | — |
| simgnn_tensor.bilinear.reshape | View scoring as [8,4] | [8,4] | E001 | — |
| simgnn_tensor.bilinear.second | scoring.T @ e2 | [4,1] | E001 | — |
| simgnn_tensor.concat | Concat ordered graph columns | [16,1] | E001 | — |
| simgnn_tensor.block | W_block @ graph pair | [4,1] | E001 | — |
| simgnn_tensor.add | Bilinear + block score + bias | [4,1] | E001 | — |
| simgnn_tensor.relu | ReLU comparison features | [4,1] | E001 | — |
| simgnn_tensor.output | Selected module output | [4,1] | E001 | — |

## 与教科书/通用基础图的区别

- Do not replace the source view/order with an unverified einsum, remove affine block path, or force symmetry under swapping graph inputs.

## 源码事实与边界

- Source class is misspelled TenorNetworkModule; stable source identity keeps that spelling while display label explains neural tensor comparison.
- Tensor weight\[8,8,4\] contracts ordered graph columns in two actual matrix products with an intermediate view\[8,4\]. A separate block weight\[4,16\] acts on concatenated graph vectors.
- Bilinear features, block features and owned bias add before ReLU. This module returns four features, not a similarity probability or scalar graph edit distance.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
