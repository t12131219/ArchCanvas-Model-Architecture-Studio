# InceptionC / independent module：源码与图框对应

来源：`pytorch/vision`，固定提交 `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E003 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionC` | 290–337 | — |
| E004 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionC.__init__` | 292–314 | — |
| E005 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionC._forward` | 316–333 | — |
| E006 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionC.forward` | 335–337 | — |
| E001 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `BasicConv2d.__init__` | 465–473 | — |
| E002 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `BasicConv2d.forward` | 475–478 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| inception_factorized.root | InceptionC / independent module / module | [B,768,17,17] | E004,E006 | — |
| inception_factorized.input | Module input | [B,768,17,17] | E004,E006 | — |
| inception_factorized.module | InceptionC | [B,768,17,17] | E004,E005,E006,E001,E002 | — |
| inception_factorized.branches | Source-ordered independent paths | ordered branch list | E004,E005,E006,E001,E002 | — |
| inception_factorized.path.branch1x1 | branch1x1 | [B,192,17,17] | E004,E005,E006,E001,E002 | — |
| inception_factorized.branch1x1 | branch1x1 | [B,192,17,17] | E004,E005,E006,E001,E002 | branch1x1 |
| inception_factorized.branch1x1.conv | Conv 1 / 768→192 | [B,192,17,17] | E004,E005,E006,E001,E002 | branch1x1.conv; instance=inception_factorized.branch1x1.conv |
| inception_factorized.branch1x1.bn | BatchNorm | [B,192,17,17] | E004,E005,E006,E001,E002 | branch1x1.bn; instance=inception_factorized.branch1x1.bn |
| inception_factorized.branch1x1.relu | ReLU | [B,192,17,17] | E004,E005,E006,E001,E002 | — |
| inception_factorized.path.branch7x7 | branch7x7 | [B,192,17,17] | E004,E005,E006,E001,E002 | — |
| inception_factorized.branch7x7_1 | branch7x7_1 | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7_1 |
| inception_factorized.branch7x7_1.conv | Conv 1 / 768→128 | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7_1.conv; instance=inception_factorized.branch7x7_1.conv |
| inception_factorized.branch7x7_1.bn | BatchNorm | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7_1.bn; instance=inception_factorized.branch7x7_1.bn |
| inception_factorized.branch7x7_1.relu | ReLU | [B,128,17,17] | E004,E005,E006,E001,E002 | — |
| inception_factorized.branch7x7_2 | branch7x7_2 | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7_2 |
| inception_factorized.branch7x7_2.conv | Conv (1, 7) / 128→128 | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7_2.conv; instance=inception_factorized.branch7x7_2.conv |
| inception_factorized.branch7x7_2.bn | BatchNorm | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7_2.bn; instance=inception_factorized.branch7x7_2.bn |
| inception_factorized.branch7x7_2.relu | ReLU | [B,128,17,17] | E004,E005,E006,E001,E002 | — |
| inception_factorized.branch7x7_3 | branch7x7_3 | [B,192,17,17] | E004,E005,E006,E001,E002 | branch7x7_3 |
| inception_factorized.branch7x7_3.conv | Conv (7, 1) / 128→192 | [B,192,17,17] | E004,E005,E006,E001,E002 | branch7x7_3.conv; instance=inception_factorized.branch7x7_3.conv |
| inception_factorized.branch7x7_3.bn | BatchNorm | [B,192,17,17] | E004,E005,E006,E001,E002 | branch7x7_3.bn; instance=inception_factorized.branch7x7_3.bn |
| inception_factorized.branch7x7_3.relu | ReLU | [B,192,17,17] | E004,E005,E006,E001,E002 | — |
| inception_factorized.path.branch7x7dbl | branch7x7dbl | [B,192,17,17] | E004,E005,E006,E001,E002 | — |
| inception_factorized.branch7x7dbl_1 | branch7x7dbl_1 | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7dbl_1 |
| inception_factorized.branch7x7dbl_1.conv | Conv 1 / 768→128 | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7dbl_1.conv; instance=inception_factorized.branch7x7dbl_1.conv |
| inception_factorized.branch7x7dbl_1.bn | BatchNorm | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7dbl_1.bn; instance=inception_factorized.branch7x7dbl_1.bn |
| inception_factorized.branch7x7dbl_1.relu | ReLU | [B,128,17,17] | E004,E005,E006,E001,E002 | — |
| inception_factorized.branch7x7dbl_2 | branch7x7dbl_2 | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7dbl_2 |
| inception_factorized.branch7x7dbl_2.conv | Conv (7, 1) / 128→128 | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7dbl_2.conv; instance=inception_factorized.branch7x7dbl_2.conv |
| inception_factorized.branch7x7dbl_2.bn | BatchNorm | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7dbl_2.bn; instance=inception_factorized.branch7x7dbl_2.bn |
| inception_factorized.branch7x7dbl_2.relu | ReLU | [B,128,17,17] | E004,E005,E006,E001,E002 | — |
| inception_factorized.branch7x7dbl_3 | branch7x7dbl_3 | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7dbl_3 |
| inception_factorized.branch7x7dbl_3.conv | Conv (1, 7) / 128→128 | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7dbl_3.conv; instance=inception_factorized.branch7x7dbl_3.conv |
| inception_factorized.branch7x7dbl_3.bn | BatchNorm | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7dbl_3.bn; instance=inception_factorized.branch7x7dbl_3.bn |
| inception_factorized.branch7x7dbl_3.relu | ReLU | [B,128,17,17] | E004,E005,E006,E001,E002 | — |
| inception_factorized.branch7x7dbl_4 | branch7x7dbl_4 | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7dbl_4 |
| inception_factorized.branch7x7dbl_4.conv | Conv (7, 1) / 128→128 | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7dbl_4.conv; instance=inception_factorized.branch7x7dbl_4.conv |
| inception_factorized.branch7x7dbl_4.bn | BatchNorm | [B,128,17,17] | E004,E005,E006,E001,E002 | branch7x7dbl_4.bn; instance=inception_factorized.branch7x7dbl_4.bn |
| inception_factorized.branch7x7dbl_4.relu | ReLU | [B,128,17,17] | E004,E005,E006,E001,E002 | — |
| inception_factorized.branch7x7dbl_5 | branch7x7dbl_5 | [B,192,17,17] | E004,E005,E006,E001,E002 | branch7x7dbl_5 |
| inception_factorized.branch7x7dbl_5.conv | Conv (1, 7) / 128→192 | [B,192,17,17] | E004,E005,E006,E001,E002 | branch7x7dbl_5.conv; instance=inception_factorized.branch7x7dbl_5.conv |
| inception_factorized.branch7x7dbl_5.bn | BatchNorm | [B,192,17,17] | E004,E005,E006,E001,E002 | branch7x7dbl_5.bn; instance=inception_factorized.branch7x7dbl_5.bn |
| inception_factorized.branch7x7dbl_5.relu | ReLU | [B,192,17,17] | E004,E005,E006,E001,E002 | — |
| inception_factorized.path.branch_pool | branch_pool | [B,192,17,17] | E004,E005,E006,E001,E002 | — |
| inception_factorized.branch_pool.pool | averagePool 3 / 1 | [B,768,17,17] | E005 | — |
| inception_factorized.branch_pool | branch_pool | [B,192,17,17] | E004,E005,E006,E001,E002 | branch_pool |
| inception_factorized.branch_pool.conv | Conv 1 / 768→192 | [B,192,17,17] | E004,E005,E006,E001,E002 | branch_pool.conv; instance=inception_factorized.branch_pool.conv |
| inception_factorized.branch_pool.bn | BatchNorm | [B,192,17,17] | E004,E005,E006,E001,E002 | branch_pool.bn; instance=inception_factorized.branch_pool.bn |
| inception_factorized.branch_pool.relu | ReLU | [B,192,17,17] | E004,E005,E006,E001,E002 | — |
| inception_factorized.concat | Concat channel dim=1 | [B,768,17,17] | E004,E006 | — |
| inception_factorized.output | Module output | [B,768,17,17] | E004,E006 | — |

## 与教科书/通用基础图的区别

- Do not interchange average/max pool, square/factorized kernels, or source concat order.
- InceptionE has two nested kernel splits and three actual Concat operations; no branch summation.

## 源码事实与边界

- Bounded AST adapter reads actual attribute order, kernels, stride/padding, list order and nested cats.
- Every BasicConv is Conv(biasFalse) -> BN(eps.001) -> inplace ReLU; real .conv/.bn attributes own independent parameters.
- Four or three source paths receive the same x; lists are collected and then channel concatenated.
- Repeated initial BasicConv bodies in the five-block path remain folded at detailed view; all operators and identities remain in IR.
