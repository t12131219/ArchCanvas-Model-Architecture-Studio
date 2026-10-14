# Graph inner-product decoder：源码与图框对应

来源：`dmlc/dgl`，固定提交 `3d16000b4170fa741ed9e9667f22ba84d3493026`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [dgl-graph-modules/examples/pytorch/vgae/model.py](sources/dgl-graph-modules/examples/pytorch/vgae/model.py) · `VGAEModel.decoder` | 50–52 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| inner_product_decoder.root | Graph inner-product decoder / module only | [N,N] | E001 | — |
| inner_product_decoder.z | Node latents Z | [N,8] | E001 | — |
| inner_product_decoder.module | Graph inner-product decoder / operators | [N,N] | E001 | — |
| inner_product_decoder.transpose | Transpose same Z | [8,N] | E001 | — |
| inner_product_decoder.product | All node-pair inner products | [N,N] | E001 | — |
| inner_product_decoder.product.mm | Z @ Z.T | [N,N] | E001 | — |
| inner_product_decoder.sigmoid | Elementwise Sigmoid | [N,N] | E001 | — |
| inner_product_decoder.output | Selected module output | [N,N] | E001 | — |

## 与教科书/通用基础图的区别

- Do not turn the decoder into adjacency-conditioned message passing or a classification head.

## 源码事实与边界

- Decoder reuses exactly one Z in both matrix operands, giving symmetric dense pair scores.
- Sigmoid is elementwise; source does not perform row Softmax, masking, diagonal deletion or learned decoder Linear.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
