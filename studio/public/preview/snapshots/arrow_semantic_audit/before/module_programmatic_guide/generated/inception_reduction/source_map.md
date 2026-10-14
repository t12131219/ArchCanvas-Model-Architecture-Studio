# InceptionB / independent module：源码与图框对应

来源：`pytorch/vision`，固定提交 `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E003 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionB` | 257–287 | — |
| E004 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionB.__init__` | 259–271 | — |
| E005 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionB._forward` | 273–283 | — |
| E006 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionB.forward` | 285–287 | — |
| E001 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `BasicConv2d.__init__` | 465–473 | — |
| E002 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `BasicConv2d.forward` | 475–478 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| inception_reduction.root | InceptionB / independent module / module | [B,768,17,17] | E004,E006 | — |
| inception_reduction.input | Module input | [B,288,35,35] | E004,E006 | — |
| inception_reduction.module | InceptionB | [B,768,17,17] | E004,E005,E006,E001,E002 | — |
| inception_reduction.branches | Source-ordered independent paths | ordered branch list | E004,E005,E006,E001,E002 | — |
| inception_reduction.path.branch3x3 | branch3x3 | [B,384,17,17] | E004,E005,E006,E001,E002 | — |
| inception_reduction.branch3x3 | branch3x3 | [B,384,17,17] | E004,E005,E006,E001,E002 | branch3x3 |
| inception_reduction.branch3x3.conv | Conv 3 / 288→384 | [B,384,17,17] | E004,E005,E006,E001,E002 | branch3x3.conv; instance=inception_reduction.branch3x3.conv |
| inception_reduction.branch3x3.bn | BatchNorm | [B,384,17,17] | E004,E005,E006,E001,E002 | branch3x3.bn; instance=inception_reduction.branch3x3.bn |
| inception_reduction.branch3x3.relu | ReLU | [B,384,17,17] | E004,E005,E006,E001,E002 | — |
| inception_reduction.path.branch3x3dbl | branch3x3dbl | [B,96,17,17] | E004,E005,E006,E001,E002 | — |
| inception_reduction.branch3x3dbl_1 | branch3x3dbl_1 | [B,64,35,35] | E004,E005,E006,E001,E002 | branch3x3dbl_1 |
| inception_reduction.branch3x3dbl_1.conv | Conv 1 / 288→64 | [B,64,35,35] | E004,E005,E006,E001,E002 | branch3x3dbl_1.conv; instance=inception_reduction.branch3x3dbl_1.conv |
| inception_reduction.branch3x3dbl_1.bn | BatchNorm | [B,64,35,35] | E004,E005,E006,E001,E002 | branch3x3dbl_1.bn; instance=inception_reduction.branch3x3dbl_1.bn |
| inception_reduction.branch3x3dbl_1.relu | ReLU | [B,64,35,35] | E004,E005,E006,E001,E002 | — |
| inception_reduction.branch3x3dbl_2 | branch3x3dbl_2 | [B,96,35,35] | E004,E005,E006,E001,E002 | branch3x3dbl_2 |
| inception_reduction.branch3x3dbl_2.conv | Conv 3 / 64→96 | [B,96,35,35] | E004,E005,E006,E001,E002 | branch3x3dbl_2.conv; instance=inception_reduction.branch3x3dbl_2.conv |
| inception_reduction.branch3x3dbl_2.bn | BatchNorm | [B,96,35,35] | E004,E005,E006,E001,E002 | branch3x3dbl_2.bn; instance=inception_reduction.branch3x3dbl_2.bn |
| inception_reduction.branch3x3dbl_2.relu | ReLU | [B,96,35,35] | E004,E005,E006,E001,E002 | — |
| inception_reduction.branch3x3dbl_3 | branch3x3dbl_3 | [B,96,17,17] | E004,E005,E006,E001,E002 | branch3x3dbl_3 |
| inception_reduction.branch3x3dbl_3.conv | Conv 3 / 96→96 | [B,96,17,17] | E004,E005,E006,E001,E002 | branch3x3dbl_3.conv; instance=inception_reduction.branch3x3dbl_3.conv |
| inception_reduction.branch3x3dbl_3.bn | BatchNorm | [B,96,17,17] | E004,E005,E006,E001,E002 | branch3x3dbl_3.bn; instance=inception_reduction.branch3x3dbl_3.bn |
| inception_reduction.branch3x3dbl_3.relu | ReLU | [B,96,17,17] | E004,E005,E006,E001,E002 | — |
| inception_reduction.path.branch_pool | branch_pool | [B,288,17,17] | E004,E005,E006,E001,E002 | — |
| inception_reduction.branch_pool.pool | maxPool 3 / 2 | [B,288,17,17] | E005 | — |
| inception_reduction.concat | Concat channel dim=1 | [B,768,17,17] | E004,E006 | — |
| inception_reduction.output | Module output | [B,768,17,17] | E004,E006 | — |

## 与教科书/通用基础图的区别

- Do not interchange average/max pool, square/factorized kernels, or source concat order.
- InceptionE has two nested kernel splits and three actual Concat operations; no branch summation.

## 源码事实与边界

- Bounded AST adapter reads actual attribute order, kernels, stride/padding, list order and nested cats.
- Every BasicConv is Conv(biasFalse) -> BN(eps.001) -> inplace ReLU; real .conv/.bn attributes own independent parameters.
- Four or three source paths receive the same x; lists are collected and then channel concatenated.
- Repeated initial BasicConv bodies in the five-block path remain folded at detailed view; all operators and identities remain in IR.
