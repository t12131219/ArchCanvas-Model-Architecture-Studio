# VGAE graph posterior sampling：源码与图框对应

来源：`dmlc/dgl`，固定提交 `3d16000b4170fa741ed9e9667f22ba84d3493026`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E003 | [dgl-graph-modules/examples/pytorch/vgae/model.py](sources/dgl-graph-modules/examples/pytorch/vgae/model.py) · `__module__` | 1–57 | — |
| E001 | [dgl-graph-modules/examples/pytorch/vgae/model.py](sources/dgl-graph-modules/examples/pytorch/vgae/model.py) · `VGAEModel.__init__` | 10–36 | — |
| E002 | [dgl-graph-modules/examples/pytorch/vgae/model.py](sources/dgl-graph-modules/examples/pytorch/vgae/model.py) · `VGAEModel.encoder` | 38–48 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| vgae_posterior.root | VGAE graph posterior sampling / module only | [N,8] | E002 | — |
| vgae_posterior.features | Node features | [N,8] | E002 | — |
| vgae_posterior.g | Supplied DGL graph | N nodes / E edges | E002 | — |
| vgae_posterior.device | Imported global device | from train import device | E003 | — |
| vgae_posterior.module | VGAE graph posterior sampling / operators | [N,8] | E002 | — |
| vgae_posterior.shared | layers0 GraphConv8 -> 16 / ReLU | [N,16] | E001,E002 | layers.0; instance=layers.0 |
| vgae_posterior.mean | layers1 GraphConv16 -> 8 / MEAN | [N,8] | E001,E002 | layers.1; instance=layers.1 |
| vgae_posterior.logstd | layers2 GraphConv16 -> 8 / LOG STD | [N,8] | E001,E002 | layers.2; instance=layers.2 |
| vgae_posterior.noise | Fresh Gaussian noise / to(device) | [N,8] | E002 | — |
| vgae_posterior.exp | exp(log_std) / to(device) | [N,8] | E002 | — |
| vgae_posterior.multiply | epsilon * standard deviation | [N,8] | E002 | — |
| vgae_posterior.add | mean + epsilon * std | [N,8] | E002 | — |
| vgae_posterior.output | Selected module output | [N,8] | E002 | — |

## 与教科书/通用基础图的区别

- Do not replace log_std with log_var, introduce an eval shortcut returning mean, or feed feature values into Gaussian noise.
- Do not include adjacency decoder in the posterior module; it has a separate inner_product_decoder adapter.

## 源码事实与边界

- Three GraphConv instances are owned in ModuleList: one shared base and two independent posterior heads. Heads consume the SAME h and supplied graph, while weights are not shared.
- Source predicts log_std, so standard deviation is exp(log_std), with no log variance/2 operation.
- Fresh randn(N,hidden2_dim) occurs unconditionally even in eval mode; features supplies only the N shape to random generation. Global device comes from train import and is a runtime boundary.
- GraphConv implementation is deliberately not expanded in this example; glyphs state opaque DGL library, exact widths, activation and allow_zero_in_degree flags. No GCN formula or self-loop preprocessing is invented.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
