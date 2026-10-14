# SpectralFilter (truncated graph basis module)：源码与图框对应

来源：`rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E004 | [rasbt-modules/pytorch_ipynb/gnn/gnn-basic-graph-spectral-1.py](sources/rasbt-modules/pytorch_ipynb/gnn/gnn-basic-graph-spectral-1.py) · `precompute_adjacency_matrix` | 85–111 | [13] |
| E003 | [rasbt-modules/pytorch_ipynb/gnn/gnn-basic-graph-spectral-1.py](sources/rasbt-modules/pytorch_ipynb/gnn/gnn-basic-graph-spectral-1.py) · `get_graph_laplacian` | 114–124 | [13] |
| E001 | [rasbt-modules/pytorch_ipynb/gnn/gnn-basic-graph-spectral-1.py](sources/rasbt-modules/pytorch_ipynb/gnn/gnn-basic-graph-spectral-1.py) · `GraphNet.__init__` | 147–166 | [16] |
| E002 | [rasbt-modules/pytorch_ipynb/gnn/gnn-basic-graph-spectral-1.py](sources/rasbt-modules/pytorch_ipynb/gnn/gnn-basic-graph-spectral-1.py) · `GraphNet.forward` | 170–200 | [16] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| spectral.root | SpectralFilter / selected subgraph | X + V + W -> Y | E001,E002 | — |
| spectral.xbranch | Image to node features | X: [B,784,1] | E002 | — |
| spectral.input | Input grayscale image | [B,1,28,28] | E002 | — |
| spectral.reshape | view(B,-1,1) | X: [B,784,1] | E002 | — |
| spectral.vbranch | Basis read / transpose view | V_T: [B,20,784] | E001,E002 | — |
| spectral.vread | Read same V buffer | V: [784,20] | E001,E002 | — |
| spectral.vt | V.T.expand(B,-1,-1) | V_T: [B,20,784] | E002 | — |
| spectral.wbranch | Node-domain filter read | W_batch: [B,784,2] | E001,E002 | — |
| spectral.wread | Read W_spectral buffer | W: [784,2] | E001,E002 | — |
| spectral.wexpand | W.expand(B,-1,-1) | W_batch: [B,784,2] | E002 | — |
| spectral.filter | Truncated spectral filtering | Y: [B,784,2] | E002 | — |
| spectral.xproject | Signal projection / V_T @ X | [B,20,1] | E002 | — |
| spectral.xproject.bmm | Batch MatMul / Signal projection | [B,20,1] | E002 | — |
| spectral.wproject | Filter projection / V_T @ W | [B,20,2] | E002 | — |
| spectral.wproject.bmm | Batch MatMul / Filter projection | [B,20,2] | E002 | — |
| spectral.vexpand | V.expand(B,-1,-1) | V_batch: [B,784,20] | E002 | — |
| spectral.product | Broadcast elementwise multiply | [B,20,2] | E002 | — |
| spectral.reconstruct | Reconstruct / V @ product | [B,784,2] | E002 | — |
| spectral.reconstruct.bmm | Batch MatMul / Reconstruct | [B,784,2] | E002 | — |
| spectral.output | Module result / node features Y | [B,784,2] | E002 | — |
| spectral.basis_init | Fixed basis / constructor | V: [N=784,K=20] | E004,E003,E001 | — |
| spectral.adj | Grid adjacency helper | A: [784,784] | E004 | — |
| spectral.laplacian | Normalized graph Laplacian | L: [784,784] | E003 | — |
| spectral.eigsh | eigsh / SciPy boundary | V: [784,20]; Lambda: [20] | E001 | — |
| spectral.vbuffer | from_numpy(V) / register V | V: [784,20] | E001 | — |
| spectral.w_init | Filter buffer / constructor | registered W: [N=784,F=2] | E001 | — |
| spectral.wcreate | Create Parameter / cast float | W: [784,2] | E001 | — |
| spectral.wkaiming | Kaiming uniform init | W: [784,2] | E001 | — |
| spectral.wbuffer | Register W buffer | W_spectral: [784,2] | E001 | — |

## 与教科书/通用基础图的区别

- Do not label this example FFT, Chebyshev filtering, a full eigendecomposition or a canonical learned GCN.
- Do not label W an optimizer parameter solely because its construction starts with nn.Parameter.
- Do not add eigenvalue multiplication, activation, pooling or a classification head inside the selected module.
- Do not chain overwritten unsqueeze results into expand or collapse Y into a one-channel image.

## 源码事实与边界

- Selected boundary ends at Y; it excludes the enclosing classification head and all training operations.
- Constructor creates A from an unsquared Euclidean-distance exponential kernel and threshold. Its triple-quoted degree-normalization block after return is not executed.
- L=I-D_hat A D_hat uses D=sum(A,axis0),epsilon1e-5; eigsh returns20 smallest-magnitude modes, not a full784-mode basis.
- A,L,V,W_spectral are all explicitly register_buffer entries. W starts from nn.Parameter(...).float(), then buffer registration; model.parameters() does not discover W through this registration.
- Whether float/to preserves Parameter identity, leaf status and gradients depends dtype/runtime. Drawing does not execute these conversions or claim W has requires_grad=False.
- V=torch.from_numpy(V) has no explicit float32 conversion. Dtype compatibility of bmm must be checked in a separate runtime audit; this source-grounded example does not silently cast or fix source.
- Live batch views are self.V.expand,self.V.T.expand,self.W_spectral.expand; three earlier unsqueeze assignments are overwritten and omitted from the live-dependency graph.
- X_hat=V_T@X is\[B,20,1\], W_hat=V_T@W is\[B,20,2\]; elementwise multiplication broadcasts the singleton feature axis.
- Reconstruction uses the same V buffer and produces Y\[B,784,2\]; Lambda is computed during construction but is not used in forward.
- W is a node-domain784x2 buffer, projected every forward; it is not a stored20x2 learned spectral coefficient parameter.
- Ranks are layout constraints on dependency stages; they do not promise Python parallel execution or reproduce the textual assignment order.
