# Graph wavelet sparse layer：源码与图框对应

来源：`benedekrozemberczki/GraphWaveletNeuralNetwork`，固定提交 `fbd93c8db066e03224f1bc66167985a56f1fe7aa`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [graphwavelet-modules/src/gwnn_layer.py](sources/graphwavelet-modules/src/gwnn_layer.py) · `GraphWaveletLayer.define_parameters` | 23–32 | — |
| E002 | [graphwavelet-modules/src/gwnn_layer.py](sources/graphwavelet-modules/src/gwnn_layer.py) · `GraphWaveletLayer.init_parameters` | 34–39 | — |
| E003 | [graphwavelet-modules/src/gwnn_layer.py](sources/graphwavelet-modules/src/gwnn_layer.py) · `SparseGraphWaveletLayer.forward` | 45–89 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| graphwavelet_sparse.root | Graph wavelet sparse layer / module only | [N,4] | E003 | — |
| graphwavelet_sparse.x | Sparse X indices / values | [N,8] | E003 | — |
| graphwavelet_sparse.phi | Supplied sparse wavelet Phi | indices / values; [N,N] | E003 | — |
| graphwavelet_sparse.inverse | Supplied sparse inverse Phi | indices / values; [N,N] | E003 | — |
| graphwavelet_sparse.diagindices | Fixed diagonal index Tensor | [2,N] | E001 | False |
| graphwavelet_sparse.theta | Owned diagonal filter theta | [N,1] | E001 | diagonal_weight_filter |
| graphwavelet_sparse.weight | Owned feature projection W | [8,4] | E001 | weight_matrix |
| graphwavelet_sparse.module | Graph wavelet sparse layer / operators | [N,4] | E003 | — |
| graphwavelet_sparse.rescale | Sparse Phi @ diag(theta) | sparse pair [N,N] | E003 | — |
| graphwavelet_sparse.project | Sparse X @ W | [N,4] | E003 | — |
| graphwavelet_sparse.kernel | Rescaled Phi @ Phi inverse | sparse pair [N,N] | E003 | — |
| graphwavelet_sparse.localize | Learned wavelet kernel @ XW | [N,4] | E003 | — |
| graphwavelet_sparse.tail | ReLU THEN Dropout .5 | [N,4] | E003 | — |
| graphwavelet_sparse.tail.relu | ReLU localized features | [N,4] | E003 | — |
| graphwavelet_sparse.tail.drop | Dropout .5 / caller mode | [N,4] | E003 | — |
| graphwavelet_sparse.output | Selected module output | [N,4] | E003 | — |

## 与教科书/通用基础图的区别

- Do not equate this learned diagonal graph-wavelet filter with the existing eigenspace elementwise SpectralFilter.
- Do not register the fixed indices as a buffer absent in source or copy Sparse tail into Dense version.

## 源码事实与边界

- Source constructs Phi @ diag(theta) first, multiplies by supplied Phi_inverse second, then applies resulting sparse kernel to X@W. Parentheses, sparse representation and multiplication order remain explicit.
- theta\[N,1\] and W\[8,4\] are learned Parameters. Diagonal_weight_indices is an ordinary Tensor attribute moved to device, NOT registered_buffer and NOT Parameter.
- Supplied Phi/inverse preprocessing and torch_sparse kernels stay opaque. The diagram does not assert an orthogonal transform, compute a wavelet spectrum or run sparse products.
- Sparse forward applies ReLU then caller-mode Dropout after localization; Dense forward returns localization directly with no activation or Dropout.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
