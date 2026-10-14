# Feature Pyramid Network：源码与图框对应

来源：`pytorch/vision`，固定提交 `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py](sources/torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py) · `FeaturePyramidNetwork` | 33–161 | — |
| E002 | [torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py](sources/torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py) · `FeaturePyramidNetwork.__init__` | 70–95 | — |
| E004 | [torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py](sources/torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py) · `FeaturePyramidNetwork.get_result_from_inner_blocks` | 97–111 | — |
| E005 | [torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py](sources/torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py) · `FeaturePyramidNetwork.get_result_from_layer_blocks` | 113–127 | — |
| E003 | [torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py](sources/torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py) · `FeaturePyramidNetwork.forward` | 129–161 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| fpn.root | FeaturePyramidNetwork / module | 3 scales → 3 scales | E002,E003,E004,E005 | — |
| fpn.input0 | feat0 / caller feature | [B,64,32,32] | E002,E003 | — |
| fpn.input1 | feat1 / caller feature | [B,128,16,16] | E002,E003 | — |
| fpn.input2 | feat2 / caller feature | [B,256,8,8] | E002,E003 | — |
| fpn.module | FPN / lateral and top-down | OrderedDict feat0/feat1/feat2 | E002,E003,E004,E005 | — |
| fpn.lateral0 | Lateral1x1 / feat0 | [B,128,32,32] | E002,E003,E004,E005 | inner_blocks.0; instance=fpn.inner_blocks.0 |
| fpn.lateral1 | Lateral1x1 / feat1 | [B,128,16,16] | E002,E003,E004,E005 | inner_blocks.1; instance=fpn.inner_blocks.1 |
| fpn.lateral2 | Lateral1x1 / feat2 | [B,128,8,8] | E002,E003,E004,E005 | inner_blocks.2; instance=fpn.inner_blocks.2 |
| fpn.up1 | Nearest resize / 8→16 | [B,128,16,16] | E002,E003 | — |
| fpn.add1 | Add lateral1 + top-down | [B,128,16,16] | E002,E003 | — |
| fpn.up0 | Nearest resize / 16→32 | [B,128,32,32] | E002,E003 | — |
| fpn.add0 | Add lateral0 + top-down | [B,128,32,32] | E002,E003 | — |
| fpn.output_conv0 | Output3x3 / feat0 | [B,128,32,32] | E002,E003,E004,E005 | layer_blocks.0; instance=fpn.layer_blocks.0 |
| fpn.output_conv1 | Output3x3 / feat1 | [B,128,16,16] | E002,E003,E004,E005 | layer_blocks.1; instance=fpn.layer_blocks.1 |
| fpn.output_conv2 | Output3x3 / feat2 | [B,128,8,8] | E002,E003,E004,E005 | layer_blocks.2; instance=fpn.layer_blocks.2 |
| fpn.output | OrderedDict / high resolution first | feat0[128,32,32] / feat1[128,16,16] / feat2[128,8,8] | E002,E003 | — |

## 与教科书/通用基础图的区别

- Do not send smoothed output2/output1 into top-down interpolation.
- Different input resolutions are explicit operands, not three visual copies of one tensor.
- extra_blocks=None excludes P6/P7 and MaxPool.

## 源码事实与边界

- Three different dictionary features feed independent lateral1x1 Conv weights, not one same-input fork.
- Coarsest lateral2 produces output2 and the first top-down value. Later last_inner values are Add results, not layer_blocks outputs.
- Nearest resize reads target H/W from the current lateral feature; shape-only edges do not carry tensor values.
- Processing loop is low-resolution to high-resolution; results.insert(0,...) restores caller key order/highest resolution first.
- Six independent Conv families retain default biases, Kaiming(a=1) and zero bias initialization; no BN or ReLU is present.
