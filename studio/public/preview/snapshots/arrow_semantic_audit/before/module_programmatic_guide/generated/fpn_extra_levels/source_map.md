# FPN extra P6/P7 levels：源码与图框对应

来源：`pytorch/vision`，固定提交 `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py](sources/torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py) · `LastLevelP6P7` | 179–204 | — |
| E002 | [torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py](sources/torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py) · `LastLevelP6P7.__init__` | 183–190 | — |
| E003 | [torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py](sources/torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py) · `LastLevelP6P7.forward` | 192–204 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| fpn_extra_levels.root | FPN extra levels / module | C5 → P6 + P7 | E002,E003 | — |
| fpn_extra_levels.c5 | Caller c[-1] / C5 | [B,256,8,8] | E002,E003 | — |
| fpn_extra_levels.existing | Existing p + names / retain | p contains P5[128,8,8]; names match p | E002,E003 | — |
| fpn_extra_levels.module | LastLevelP6P7 / C5 branch | P6 and P7 / both retained | E002,E003 | — |
| fpn_extra_levels.p6 | P6 / Conv3 stride2 | [B,128,4,4] | E002,E003 | p6; instance=fpn_extra_levels.p6 |
| fpn_extra_levels.relu | ReLU | [B,128,4,4] | E002,E003 | — |
| fpn_extra_levels.p7 | P7 / Conv3 stride2 | [B,128,2,2] | E002,E003 | p7; instance=fpn_extra_levels.p7 |
| fpn_extra_levels.extend | Extend p and names / P6 + P7 | p + P6[128,4,4] + P7[128,2,2] | E002,E003 | — |
| fpn_extra_levels.output | Return extended p, names | (existing p + [P6,P7], names + [p6,p7]) | E002,E003 | — |

## 与教科书/通用基础图的区别

- Do not show only P7 at the output; P6 is independently retained.
- An equal-channel construction selects P5 and needs a separately reviewed profile.

## 源码事实与边界

- in_channels != out_channels selects C5, even though the caller p list contains P5.
- P6=Conv3 stride2(C5); P7=Conv3 stride2(ReLU(P6)); ReLU is not applied before P6 or to returned P6.
- Both P6 and P7 are appended to the existing p list, and matching names append in the same order.
- p6 and p7 are independent default-bias Conv families initialized with Kaiming(a=1), bias0.
