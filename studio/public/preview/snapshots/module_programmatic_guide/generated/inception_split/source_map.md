# InceptionE / independent module：源码与图框对应

来源：`pytorch/vision`，固定提交 `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E003 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionE` | 376–425 | — |
| E004 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionE.__init__` | 378–397 | — |
| E005 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionE._forward` | 399–421 | — |
| E006 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionE.forward` | 423–425 | — |
| E001 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `BasicConv2d.__init__` | 465–473 | — |
| E002 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `BasicConv2d.forward` | 475–478 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| inception_split.root | InceptionE / independent module / module | [B,2048,8,8] | E004,E006 | — |
| inception_split.input | Module input | [B,1280,8,8] | E004,E006 | — |
| inception_split.module | InceptionE | [B,2048,8,8] | E004,E005,E006,E001,E002 | — |
| inception_split.branches | Source-ordered independent paths | ordered branch list | E004,E005,E006,E001,E002 | — |
| inception_split.path.branch1x1 | branch1x1 | [B,320,8,8] | E004,E005,E006,E001,E002 | — |
| inception_split.branch1x1 | branch1x1 | [B,320,8,8] | E004,E005,E006,E001,E002 | branch1x1 |
| inception_split.branch1x1.conv | Conv 1 / 1280→320 | [B,320,8,8] | E004,E005,E006,E001,E002 | branch1x1.conv; instance=inception_split.branch1x1.conv |
| inception_split.branch1x1.bn | BatchNorm | [B,320,8,8] | E004,E005,E006,E001,E002 | branch1x1.bn; instance=inception_split.branch1x1.bn |
| inception_split.branch1x1.relu | ReLU | [B,320,8,8] | E004,E005,E006,E001,E002 | — |
| inception_split.path.branch3x3 | branch3x3 | [B,768,8,8] | E004,E005,E006,E001,E002 | — |
| inception_split.branch3x3_1 | branch3x3_1 | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3_1 |
| inception_split.branch3x3_1.conv | Conv 1 / 1280→384 | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3_1.conv; instance=inception_split.branch3x3_1.conv |
| inception_split.branch3x3_1.bn | BatchNorm | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3_1.bn; instance=inception_split.branch3x3_1.bn |
| inception_split.branch3x3_1.relu | ReLU | [B,384,8,8] | E004,E005,E006,E001,E002 | — |
| inception_split.branch3x3.split | Factorized split kernels | 2 independent tensors | E004,E005,E006,E001,E002 | — |
| inception_split.branch3x3_2a | branch3x3_2a | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3_2a |
| inception_split.branch3x3_2a.conv | Conv (1, 3) / 384→384 | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3_2a.conv; instance=inception_split.branch3x3_2a.conv |
| inception_split.branch3x3_2a.bn | BatchNorm | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3_2a.bn; instance=inception_split.branch3x3_2a.bn |
| inception_split.branch3x3_2a.relu | ReLU | [B,384,8,8] | E004,E005,E006,E001,E002 | — |
| inception_split.branch3x3_2b | branch3x3_2b | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3_2b |
| inception_split.branch3x3_2b.conv | Conv (3, 1) / 384→384 | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3_2b.conv; instance=inception_split.branch3x3_2b.conv |
| inception_split.branch3x3_2b.bn | BatchNorm | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3_2b.bn; instance=inception_split.branch3x3_2b.bn |
| inception_split.branch3x3_2b.relu | ReLU | [B,384,8,8] | E004,E005,E006,E001,E002 | — |
| inception_split.branch3x3.concat | Concat split outputs | [B,768,8,8] | E005 | — |
| inception_split.path.branch3x3dbl | branch3x3dbl | [B,768,8,8] | E004,E005,E006,E001,E002 | — |
| inception_split.branch3x3dbl_1 | branch3x3dbl_1 | [B,448,8,8] | E004,E005,E006,E001,E002 | branch3x3dbl_1 |
| inception_split.branch3x3dbl_1.conv | Conv 1 / 1280→448 | [B,448,8,8] | E004,E005,E006,E001,E002 | branch3x3dbl_1.conv; instance=inception_split.branch3x3dbl_1.conv |
| inception_split.branch3x3dbl_1.bn | BatchNorm | [B,448,8,8] | E004,E005,E006,E001,E002 | branch3x3dbl_1.bn; instance=inception_split.branch3x3dbl_1.bn |
| inception_split.branch3x3dbl_1.relu | ReLU | [B,448,8,8] | E004,E005,E006,E001,E002 | — |
| inception_split.branch3x3dbl_2 | branch3x3dbl_2 | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3dbl_2 |
| inception_split.branch3x3dbl_2.conv | Conv 3 / 448→384 | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3dbl_2.conv; instance=inception_split.branch3x3dbl_2.conv |
| inception_split.branch3x3dbl_2.bn | BatchNorm | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3dbl_2.bn; instance=inception_split.branch3x3dbl_2.bn |
| inception_split.branch3x3dbl_2.relu | ReLU | [B,384,8,8] | E004,E005,E006,E001,E002 | — |
| inception_split.branch3x3dbl.split | Factorized split kernels | 2 independent tensors | E004,E005,E006,E001,E002 | — |
| inception_split.branch3x3dbl_3a | branch3x3dbl_3a | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3dbl_3a |
| inception_split.branch3x3dbl_3a.conv | Conv (1, 3) / 384→384 | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3dbl_3a.conv; instance=inception_split.branch3x3dbl_3a.conv |
| inception_split.branch3x3dbl_3a.bn | BatchNorm | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3dbl_3a.bn; instance=inception_split.branch3x3dbl_3a.bn |
| inception_split.branch3x3dbl_3a.relu | ReLU | [B,384,8,8] | E004,E005,E006,E001,E002 | — |
| inception_split.branch3x3dbl_3b | branch3x3dbl_3b | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3dbl_3b |
| inception_split.branch3x3dbl_3b.conv | Conv (3, 1) / 384→384 | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3dbl_3b.conv; instance=inception_split.branch3x3dbl_3b.conv |
| inception_split.branch3x3dbl_3b.bn | BatchNorm | [B,384,8,8] | E004,E005,E006,E001,E002 | branch3x3dbl_3b.bn; instance=inception_split.branch3x3dbl_3b.bn |
| inception_split.branch3x3dbl_3b.relu | ReLU | [B,384,8,8] | E004,E005,E006,E001,E002 | — |
| inception_split.branch3x3dbl.concat | Concat split outputs | [B,768,8,8] | E005 | — |
| inception_split.path.branch_pool | branch_pool | [B,192,8,8] | E004,E005,E006,E001,E002 | — |
| inception_split.branch_pool.pool | averagePool 3 / 1 | [B,1280,8,8] | E005 | — |
| inception_split.branch_pool | branch_pool | [B,192,8,8] | E004,E005,E006,E001,E002 | branch_pool |
| inception_split.branch_pool.conv | Conv 1 / 1280→192 | [B,192,8,8] | E004,E005,E006,E001,E002 | branch_pool.conv; instance=inception_split.branch_pool.conv |
| inception_split.branch_pool.bn | BatchNorm | [B,192,8,8] | E004,E005,E006,E001,E002 | branch_pool.bn; instance=inception_split.branch_pool.bn |
| inception_split.branch_pool.relu | ReLU | [B,192,8,8] | E004,E005,E006,E001,E002 | — |
| inception_split.concat | Concat channel dim=1 | [B,2048,8,8] | E004,E006 | — |
| inception_split.output | Module output | [B,2048,8,8] | E004,E006 | — |

## 与教科书/通用基础图的区别

- Do not interchange average/max pool, square/factorized kernels, or source concat order.
- InceptionE has two nested kernel splits and three actual Concat operations; no branch summation.

## 源码事实与边界

- Bounded AST adapter reads actual attribute order, kernels, stride/padding, list order and nested cats.
- Every BasicConv is Conv(biasFalse) -> BN(eps.001) -> inplace ReLU; real .conv/.bn attributes own independent parameters.
- Four or three source paths receive the same x; lists are collected and then channel concatenated.
- Repeated initial BasicConv bodies in the five-block path remain folded at detailed view; all operators and identities remain in IR.
