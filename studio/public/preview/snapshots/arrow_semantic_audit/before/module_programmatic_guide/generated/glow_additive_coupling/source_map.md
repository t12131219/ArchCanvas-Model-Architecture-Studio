# Glow additive coupling：源码与图框对应

来源：`rosinality/glow-pytorch`，固定提交 `97081ff115a694cf04aeedbd58447f33d242c879`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E004 | [glow-modules/model.py](sources/glow-modules/model.py) · `ZeroConv2d.__init__` | 140–146 | — |
| E005 | [glow-modules/model.py](sources/glow-modules/model.py) · `ZeroConv2d.forward` | 148–153 | — |
| E001 | [glow-modules/model.py](sources/glow-modules/model.py) · `AffineCoupling.__init__` | 157–174 | — |
| E002 | [glow-modules/model.py](sources/glow-modules/model.py) · `AffineCoupling.forward` | 176–193 | — |
| E003 | [glow-modules/model.py](sources/glow-modules/model.py) · `AffineCoupling.reverse` | 195–209 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| glow_additive_coupling.root | Glow additive coupling |  | E001,E002,E003,E004,E005 | — |
| glow_additive_coupling.x | Input x | [B,8,8,8] | E002 | — |
| glow_additive_coupling.body | Glow additive coupling module | [B,8,8,8] | E001,E002,E003,E004,E005 | — |
| glow_additive_coupling.split | Channel split |  | E002 | — |
| glow_additive_coupling.splitop | chunk(2, dim=1) | a,b: [B,4,8,8] | E002 | — |
| glow_additive_coupling.net | Conditioner / a only |  | E002 | — |
| glow_additive_coupling.conv1 | Conv3x3 4 -> 16 | [B,16,8,8] | E001 | — |
| glow_additive_coupling.relu1 | ReLU inplace | [B,16,8,8] | E001 | — |
| glow_additive_coupling.conv2 | Conv1x1 16 -> 16 | [B,16,8,8] | E001 | — |
| glow_additive_coupling.relu2 | ReLU inplace | [B,16,8,8] | E001 | — |
| glow_additive_coupling.zero | ZeroConv2d 16 -> 4 | [B,4,8,8] | E004,E005,E001 | instance=net.4 |
| glow_additive_coupling.transform | Additive update |  | E002 | — |
| glow_additive_coupling.addop | in_b + net_out | [B,4,8,8] | E002 | — |
| glow_additive_coupling.det | No scale determinant |  | E002 | — |
| glow_additive_coupling.none | logdet = None | None | E002 | — |
| glow_additive_coupling.join | Retain a + transformed b |  | E002 | — |
| glow_additive_coupling.catop | cat([in_a,out_b],dim=1) | [B,8,8,8] | E002 | — |
| glow_additive_coupling.y | Retained / updated channels | [B,8,8,8] | E002 | — |
| glow_additive_coupling.ld | logdet=None | None | E002 | — |

## 与教科书/通用基础图的区别

- Do not exchange shift/scale order or feed b into the conditioner.
- This is one coupling block, not the Glow architecture.

## 源码事实与边界

- Conditioner consumes only a; b is retained through a separate update path. The two channel halves are rejoined in original order.
- Additive branch returns None as logdet, rather than constructing a numeric zero tensor.
- ZeroConv2d remains a source-defined call boundary; its expanded module is available separately.
