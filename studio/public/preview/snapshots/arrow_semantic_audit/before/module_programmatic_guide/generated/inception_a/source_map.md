# InceptionA / parallel convolution module：源码与图框对应

来源：`pytorch/vision`，固定提交 `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E004 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `Inception3.__init__` | 65–131 | — |
| E005 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionA` | 214–254 | — |
| E006 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionA.__init__` | 216–234 | — |
| E007 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionA._forward` | 236–250 | — |
| E008 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `InceptionA.forward` | 252–254 | — |
| E001 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `BasicConv2d` | 463–478 | — |
| E002 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `BasicConv2d.__init__` | 465–473 | — |
| E003 | [torchvision-v0.9.0-modules/torchvision/models/inception.py](sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) · `BasicConv2d.forward` | 475–478 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| inca.root | InceptionA / module scope | One module; no backbone or classifier | E005 | — |
| inca.input | Module input x | [B,192,35,35] | E007 | — |
| inca.module | InceptionA / four independent paths | [B,192,35,35] -> [B,256,35,35] | E006,E007,E008 | instance=inception_a |
| inca.branches | Four paths / ordered output list | 64 + 64 + 96 + 32 channels | E006,E007 | — |
| inca.path_1x1 | 1x1 path | [B,64,35,35] | E006,E007 | — |
| inca.branch1x1 | BasicConv 1x1 | [B,64,35,35] | E006,E007,E002,E003 | branch1x1; instance=inception_a.branch1x1 |
| inca.branch1x1.conv | Conv 1×1 / 192→64 | [B,64,35,35] | E006,E007,E002,E003 | branch1x1.conv; instance=inception_a.branch1x1.conv |
| inca.branch1x1.bn | BatchNorm / eps=0.001 | [B,64,35,35] | E006,E007,E002,E003 | branch1x1.bn; instance=inception_a.branch1x1.bn |
| inca.branch1x1.relu | ReLU / inplace=True | [B,64,35,35] | E007,E003 | — |
| inca.path_5x5 | 1x1 -> 5x5 path | [B,64,35,35] | E006,E007 | — |
| inca.branch5x5_1 | BasicConv 1x1 | [B,48,35,35] | E006,E007,E002,E003 | branch5x5_1; instance=inception_a.branch5x5_1 |
| inca.branch5x5_1.conv | Conv 1×1 / 192→48 | [B,48,35,35] | E006,E007,E002,E003 | branch5x5_1.conv; instance=inception_a.branch5x5_1.conv |
| inca.branch5x5_1.bn | BatchNorm / eps=0.001 | [B,48,35,35] | E006,E007,E002,E003 | branch5x5_1.bn; instance=inception_a.branch5x5_1.bn |
| inca.branch5x5_1.relu | ReLU / inplace=True | [B,48,35,35] | E007,E003 | — |
| inca.branch5x5_2 | BasicConv 5x5 | [B,64,35,35] | E006,E007,E002,E003 | branch5x5_2; instance=inception_a.branch5x5_2 |
| inca.branch5x5_2.conv | Conv 5×5 / 48→64 | [B,64,35,35] | E006,E007,E002,E003 | branch5x5_2.conv; instance=inception_a.branch5x5_2.conv |
| inca.branch5x5_2.bn | BatchNorm / eps=0.001 | [B,64,35,35] | E006,E007,E002,E003 | branch5x5_2.bn; instance=inception_a.branch5x5_2.bn |
| inca.branch5x5_2.relu | ReLU / inplace=True | [B,64,35,35] | E007,E003 | — |
| inca.path_3x3dbl | 1x1 -> 3x3 -> 3x3 | [B,96,35,35] | E006,E007 | — |
| inca.branch3x3dbl_1 | BasicConv 1x1 | [B,64,35,35] | E006,E007,E002,E003 | branch3x3dbl_1; instance=inception_a.branch3x3dbl_1 |
| inca.branch3x3dbl_1.conv | Conv 1×1 / 192→64 | [B,64,35,35] | E006,E007,E002,E003 | branch3x3dbl_1.conv; instance=inception_a.branch3x3dbl_1.conv |
| inca.branch3x3dbl_1.bn | BatchNorm / eps=0.001 | [B,64,35,35] | E006,E007,E002,E003 | branch3x3dbl_1.bn; instance=inception_a.branch3x3dbl_1.bn |
| inca.branch3x3dbl_1.relu | ReLU / inplace=True | [B,64,35,35] | E007,E003 | — |
| inca.branch3x3dbl_2 | BasicConv 3x3 | [B,96,35,35] | E006,E007,E002,E003 | branch3x3dbl_2; instance=inception_a.branch3x3dbl_2 |
| inca.branch3x3dbl_2.conv | Conv 3×3 / 64→96 | [B,96,35,35] | E006,E007,E002,E003 | branch3x3dbl_2.conv; instance=inception_a.branch3x3dbl_2.conv |
| inca.branch3x3dbl_2.bn | BatchNorm / eps=0.001 | [B,96,35,35] | E006,E007,E002,E003 | branch3x3dbl_2.bn; instance=inception_a.branch3x3dbl_2.bn |
| inca.branch3x3dbl_2.relu | ReLU / inplace=True | [B,96,35,35] | E007,E003 | — |
| inca.branch3x3dbl_3 | BasicConv 3x3 | [B,96,35,35] | E006,E007,E002,E003 | branch3x3dbl_3; instance=inception_a.branch3x3dbl_3 |
| inca.branch3x3dbl_3.conv | Conv 3×3 / 96→96 | [B,96,35,35] | E006,E007,E002,E003 | branch3x3dbl_3.conv; instance=inception_a.branch3x3dbl_3.conv |
| inca.branch3x3dbl_3.bn | BatchNorm / eps=0.001 | [B,96,35,35] | E006,E007,E002,E003 | branch3x3dbl_3.bn; instance=inception_a.branch3x3dbl_3.bn |
| inca.branch3x3dbl_3.relu | ReLU / inplace=True | [B,96,35,35] | E007,E003 | — |
| inca.path_pool | AvgPool -> 1x1 path | [B,32,35,35] | E006,E007 | — |
| inca.avgpool | AvgPool 3x3 / stride=1 | [B,192,35,35] | E007 | — |
| inca.branch_pool | BasicConv 1x1 | [B,32,35,35] | E006,E007,E002,E003 | branch_pool; instance=inception_a.branch_pool |
| inca.branch_pool.conv | Conv 1×1 / 192→32 | [B,32,35,35] | E006,E007,E002,E003 | branch_pool.conv; instance=inception_a.branch_pool.conv |
| inca.branch_pool.bn | BatchNorm / eps=0.001 | [B,32,35,35] | E006,E007,E002,E003 | branch_pool.bn; instance=inception_a.branch_pool.bn |
| inca.branch_pool.relu | ReLU / inplace=True | [B,32,35,35] | E007,E003 | — |
| inca.concat | Concat / channel dim=1 | [B,256,35,35] | E008 | — |
| inca.output | Module output | [B,256,35,35] | E008 | — |

## 与教科书/通用基础图的区别

- Use the literal5x5 convolution in this version; do not replace it with two3x3 convolutions from a different Inception variant.
- The fourth path starts with average pooling, not MaxPool or an identity shortcut.
- The branch join is Concat along channel dim1, not Add; its output is256 channels, not192 or288.
- ReLU belongs after BN inside all seven BasicConv2d instances; there is no extra ReLU after Concat.
- The figure is a module example, not a complete Inception-v3 diagram or an executed model profile.

## 源码事实与边界

- This artifact contains one InceptionA instance; no Inception-v3 stem, reductions, Aux head, or classifier is inferred.
- Constructor dimensions match Inception3.Mixed_5b, while 35x35 is a declared representative input rather than an observed tensor.
- All four branches read the same x and keep its 35x35 spatial resolution using stride1 and exact padding.
- The source list order is branch1x1,branch5x5,branch3x3dbl,branch_pool, with widths64,64,96,32.
- The seven separate BasicConv2d attributes each apply Conv2d(bias=False),BatchNorm2d(eps=.001),F.relu(inplace=True).
- BatchNorm defaults are affine=True,momentum=.1,track_running_stats=True; behavior follows the caller mode.
- The pool branch applies F.avg_pool2d(x,3,stride=1,padding=1), then BasicConv2d(192,32,1).
- InceptionA._forward returns a list; InceptionA.forward applies torch.cat(outputs,1), giving64+64+96+32=256 channels.
- Shared-engine tuple_collection edges denote ordered field collection; collection_type=list explicitly preserves the literal source list.
- Each attribute owns distinct Conv and BN parameters; equal colors or matching kernel sizes do not imply weight sharing.
