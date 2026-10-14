# InceptionD / independent module：源码与图框对应

来源：`pytorch/vision`，固定提交 `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E003 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionD` | 340–373 | — |
| E004 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionD.__init__` | 342–356 | — |
| E005 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionD._forward` | 358–369 | — |
| E006 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionD.forward` | 371–373 | — |
| E001 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `BasicConv2d.__init__` | 465–473 | — |
| E002 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `BasicConv2d.forward` | 475–478 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| inception_reduction_factorized.root | InceptionD / independent module / module | [B,1280,8,8] | E004,E006 | — |
| inception_reduction_factorized.input | Module input | [B,768,17,17] | E004,E006 | — |
| inception_reduction_factorized.module | InceptionD | [B,1280,8,8] | E004,E005,E006,E001,E002 | — |
| inception_reduction_factorized.branches | Source-ordered independent paths | ordered branch list | E004,E005,E006,E001,E002 | — |
| inception_reduction_factorized.path.branch3x3 | branch3x3 | [B,320,8,8] | E004,E005,E006,E001,E002 | — |
| inception_reduction_factorized.branch3x3_1 | branch3x3_1 | [B,192,17,17] | E004,E005,E006,E001,E002 | branch3x3_1 |
| inception_reduction_factorized.branch3x3_1.conv | Conv 1 / 768→192 | [B,192,17,17] | E004,E005,E006,E001,E002 | branch3x3_1.conv; instance=inception_reduction_factorized.branch3x3_1.conv |
| inception_reduction_factorized.branch3x3_1.bn | BatchNorm | [B,192,17,17] | E004,E005,E006,E001,E002 | branch3x3_1.bn; instance=inception_reduction_factorized.branch3x3_1.bn |
| inception_reduction_factorized.branch3x3_1.relu | ReLU | [B,192,17,17] | E004,E005,E006,E001,E002 | — |
| inception_reduction_factorized.branch3x3_2 | branch3x3_2 | [B,320,8,8] | E004,E005,E006,E001,E002 | branch3x3_2 |
| inception_reduction_factorized.branch3x3_2.conv | Conv 3 / 192→320 | [B,320,8,8] | E004,E005,E006,E001,E002 | branch3x3_2.conv; instance=inception_reduction_factorized.branch3x3_2.conv |
| inception_reduction_factorized.branch3x3_2.bn | BatchNorm | [B,320,8,8] | E004,E005,E006,E001,E002 | branch3x3_2.bn; instance=inception_reduction_factorized.branch3x3_2.bn |
| inception_reduction_factorized.branch3x3_2.relu | ReLU | [B,320,8,8] | E004,E005,E006,E001,E002 | — |
| inception_reduction_factorized.path.branch7x7x3 | branch7x7x3 | [B,192,8,8] | E004,E005,E006,E001,E002 | — |
| inception_reduction_factorized.branch7x7x3_1 | branch7x7x3_1 | [B,192,17,17] | E004,E005,E006,E001,E002 | branch7x7x3_1 |
| inception_reduction_factorized.branch7x7x3_1.conv | Conv 1 / 768→192 | [B,192,17,17] | E004,E005,E006,E001,E002 | branch7x7x3_1.conv; instance=inception_reduction_factorized.branch7x7x3_1.conv |
| inception_reduction_factorized.branch7x7x3_1.bn | BatchNorm | [B,192,17,17] | E004,E005,E006,E001,E002 | branch7x7x3_1.bn; instance=inception_reduction_factorized.branch7x7x3_1.bn |
| inception_reduction_factorized.branch7x7x3_1.relu | ReLU | [B,192,17,17] | E004,E005,E006,E001,E002 | — |
| inception_reduction_factorized.branch7x7x3_2 | branch7x7x3_2 | [B,192,17,17] | E004,E005,E006,E001,E002 | branch7x7x3_2 |
| inception_reduction_factorized.branch7x7x3_2.conv | Conv (1, 7) / 192→192 | [B,192,17,17] | E004,E005,E006,E001,E002 | branch7x7x3_2.conv; instance=inception_reduction_factorized.branch7x7x3_2.conv |
| inception_reduction_factorized.branch7x7x3_2.bn | BatchNorm | [B,192,17,17] | E004,E005,E006,E001,E002 | branch7x7x3_2.bn; instance=inception_reduction_factorized.branch7x7x3_2.bn |
| inception_reduction_factorized.branch7x7x3_2.relu | ReLU | [B,192,17,17] | E004,E005,E006,E001,E002 | — |
| inception_reduction_factorized.branch7x7x3_3 | branch7x7x3_3 | [B,192,17,17] | E004,E005,E006,E001,E002 | branch7x7x3_3 |
| inception_reduction_factorized.branch7x7x3_3.conv | Conv (7, 1) / 192→192 | [B,192,17,17] | E004,E005,E006,E001,E002 | branch7x7x3_3.conv; instance=inception_reduction_factorized.branch7x7x3_3.conv |
| inception_reduction_factorized.branch7x7x3_3.bn | BatchNorm | [B,192,17,17] | E004,E005,E006,E001,E002 | branch7x7x3_3.bn; instance=inception_reduction_factorized.branch7x7x3_3.bn |
| inception_reduction_factorized.branch7x7x3_3.relu | ReLU | [B,192,17,17] | E004,E005,E006,E001,E002 | — |
| inception_reduction_factorized.branch7x7x3_4 | branch7x7x3_4 | [B,192,8,8] | E004,E005,E006,E001,E002 | branch7x7x3_4 |
| inception_reduction_factorized.branch7x7x3_4.conv | Conv 3 / 192→192 | [B,192,8,8] | E004,E005,E006,E001,E002 | branch7x7x3_4.conv; instance=inception_reduction_factorized.branch7x7x3_4.conv |
| inception_reduction_factorized.branch7x7x3_4.bn | BatchNorm | [B,192,8,8] | E004,E005,E006,E001,E002 | branch7x7x3_4.bn; instance=inception_reduction_factorized.branch7x7x3_4.bn |
| inception_reduction_factorized.branch7x7x3_4.relu | ReLU | [B,192,8,8] | E004,E005,E006,E001,E002 | — |
| inception_reduction_factorized.path.branch_pool | branch_pool | [B,768,8,8] | E004,E005,E006,E001,E002 | — |
| inception_reduction_factorized.branch_pool.pool | maxPool 3 / 2 | [B,768,8,8] | E005 | — |
| inception_reduction_factorized.concat | Concat channel dim=1 | [B,1280,8,8] | E004,E006 | — |
| inception_reduction_factorized.output | Module output | [B,1280,8,8] | E004,E006 | — |

## 与教科书/通用基础图的区别

- Do not interchange average/max pool, square/factorized kernels, or source concat order.
- InceptionE has two nested kernel splits and three actual Concat operations; no branch summation.

## 源码事实与边界

- Bounded AST adapter reads actual attribute order, kernels, stride/padding, list order and nested cats.
- Every BasicConv is Conv(biasFalse) -> BN(eps.001) -> inplace ReLU; real .conv/.bn attributes own independent parameters.
- Four or three source paths receive the same x; lists are collected and then channel concatenated.
- Repeated initial BasicConv bodies in the five-block path remain folded at detailed view; all operators and identities remain in IR.
