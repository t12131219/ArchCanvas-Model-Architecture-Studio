# MixHop sparse multi-power stage：源码与图框对应

来源：`benedekrozemberczki/MixHop-and-N-GCN`，固定提交 `e9df5eb988f0dbe5192ac87902c55cbe6d8191fe`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [mixhop-modules/src/layers.py](sources/mixhop-modules/src/layers.py) · `SparseNGCNLayer.define_parameters` | 34–39 | — |
| E002 | [mixhop-modules/src/layers.py](sources/mixhop-modules/src/layers.py) · `SparseNGCNLayer.forward` | 48–73 | — |
| E004 | [mixhop-modules/src/trainer_and_networks.py](sources/mixhop-modules/src/trainer_and_networks.py) · `MixHopNetwork.setup_layer_structure` | 63–71 | — |
| E003 | [mixhop-modules/src/trainer_and_networks.py](sources/mixhop-modules/src/trainer_and_networks.py) · `MixHopNetwork.forward` | 101–111 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| mixhop_layer.root | MixHop sparse multi-power stage / module only | [N,12] | E003 | — |
| mixhop_layer.features | Supplied sparse node features | indices / values; [N,8] | E003 | — |
| mixhop_layer.adj | Supplied normalized sparse A | indices / values; [N,N] | E003 | — |
| mixhop_layer.params0 | Branch0 owned W, bias | W[8,4]; b[1,4] | E004,E001 | instance=upper_layers.0 |
| mixhop_layer.params1 | Branch1 owned W, bias | W[8,4]; b[1,4] | E004,E001 | instance=upper_layers.1 |
| mixhop_layer.params2 | Branch2 owned W, bias | W[8,4]; b[1,4] | E004,E001 | instance=upper_layers.2 |
| mixhop_layer.module | MixHop sparse multi-power stage / operators | [N,12] | E003 | — |
| mixhop_layer.branch0 | Branch0: A^0 / iterations1 | [N,4] | E004,E002,E001 | instance=upper_layers.0 |
| mixhop_layer.branch0.project | Sparse X @ OWNED W | [N,4] | E004,E002,E001 | upper_layers.0.weight_matrix |
| mixhop_layer.branch0.bias | Add OWNED bias BEFORE A | [N,4] | E004,E002,E001 | upper_layers.0.bias |
| mixhop_layer.branch0.drop | Dropout .5 / caller mode | [N,4] | E004,E002,E001 | — |
| mixhop_layer.branch0.relu | ReLU BEFORE propagation | [N,4] | E004,E002,E001 | — |
| mixhop_layer.branch1 | Branch1: A^1 / iterations2 | [N,4] | E004,E002,E001 | instance=upper_layers.1 |
| mixhop_layer.branch1.project | Sparse X @ OWNED W | [N,4] | E004,E002,E001 | upper_layers.1.weight_matrix |
| mixhop_layer.branch1.bias | Add OWNED bias BEFORE A | [N,4] | E004,E002,E001 | upper_layers.1.bias |
| mixhop_layer.branch1.drop | Dropout .5 / caller mode | [N,4] | E004,E002,E001 | — |
| mixhop_layer.branch1.relu | ReLU BEFORE propagation | [N,4] | E004,E002,E001 | — |
| mixhop_layer.branch1.prop0 | A @ features / pass1 | [N,4] | E004,E002,E001 | — |
| mixhop_layer.branch2 | Branch2: A^2 / iterations3 | [N,4] | E004,E002,E001 | instance=upper_layers.2 |
| mixhop_layer.branch2.project | Sparse X @ OWNED W | [N,4] | E004,E002,E001 | upper_layers.2.weight_matrix |
| mixhop_layer.branch2.bias | Add OWNED bias BEFORE A | [N,4] | E004,E002,E001 | upper_layers.2.bias |
| mixhop_layer.branch2.drop | Dropout .5 / caller mode | [N,4] | E004,E002,E001 | — |
| mixhop_layer.branch2.relu | ReLU BEFORE propagation | [N,4] | E004,E002,E001 | — |
| mixhop_layer.branch2.prop0 | A @ features / pass1 | [N,4] | E004,E002,E001 | — |
| mixhop_layer.branch2.prop1 | A @ features / pass2 | [N,4] | E004,E002,E001 | — |
| mixhop_layer.concat | Concat independent power branches | [N,12] | E003 | — |
| mixhop_layer.output | Selected module output | [N,12] | E003 | — |

## 与教科书/通用基础图的区别

- Do not substitute the DenseNGCN bias-at-end behavior or textbook sigma(A^j X W) ordering for this sparse source stage.
- Do not include the entire MixHop task model in a module diagram.

## 源码事实与边界

- The selected source constructs three SparseNGCNLayer instances with iterations1,2,3, then concatenates their outputs.
- Source loop range(iterations-1) produces ZERO, ONE, TWO adjacency multiplications; do not label branches A^1,A^2,A^3.
- Each sparse branch applies sparse feature projection, bias, Dropout and ReLU BEFORE any adjacency propagation.
- Branch weights/biases are independent owned instances; sparse input and supplied normalized topology are reused. Shape uses the source max sparse index+1 inference, not an observed execution.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
