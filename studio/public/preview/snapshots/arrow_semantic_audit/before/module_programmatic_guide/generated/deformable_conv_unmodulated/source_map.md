# DeformableConv unmodulated：源码与图框对应

来源：`pytorch/vision`，固定提交 `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E005 | [torchvision-v0.9.0-vision-extended/torchvision/ops/deform_conv.py](sources/torchvision-v0.9.0-vision-extended/torchvision/ops/deform_conv.py) · `deform_conv2d` | 12–103 | — |
| E001 | [torchvision-v0.9.0-vision-extended/torchvision/ops/deform_conv.py](sources/torchvision-v0.9.0-vision-extended/torchvision/ops/deform_conv.py) · `DeformConv2d` | 106–180 | — |
| E002 | [torchvision-v0.9.0-vision-extended/torchvision/ops/deform_conv.py](sources/torchvision-v0.9.0-vision-extended/torchvision/ops/deform_conv.py) · `DeformConv2d.__init__` | 111–145 | — |
| E004 | [torchvision-v0.9.0-vision-extended/torchvision/ops/deform_conv.py](sources/torchvision-v0.9.0-vision-extended/torchvision/ops/deform_conv.py) · `DeformConv2d.reset_parameters` | 147–153 | — |
| E003 | [torchvision-v0.9.0-vision-extended/torchvision/ops/deform_conv.py](sources/torchvision-v0.9.0-vision-extended/torchvision/ops/deform_conv.py) · `DeformConv2d.forward` | 155–167 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| deformable_conv_unmodulated.root | DeformableConv unmodulated / module | [B,16,16,16] | E002,E003 | — |
| deformable_conv_unmodulated.input | Module input | [B,8,16,16] | E002,E003 | — |
| deformable_conv_unmodulated.module | DeformConv2d wrapper | [B,16,16,16] | E002,E003 | — |
| deformable_conv_unmodulated.kernel | DeformConv / no mask | [B,16,16,16] | E002,E003,E005 | — |
| deformable_conv_unmodulated.output | Module output | [B,16,16,16] | E002,E003 | — |
| deformable_conv_unmodulated.offset | External sampling offsets | [B,18,16,16] | E002,E003,E005 | — |
| deformable_conv_unmodulated.weight | Learned convolution weight | [16,8,3,3] | E002,E003,E005 | weight; instance=deformable_conv_unmodulated.weight |

## 与教科书/通用基础图的区别

- Do not force modulation on the no-mask branch.
- The offset input has18 channels for3x3, mask has9; neither is the convolution weight.

## 源码事实与边界

- Offsets are caller-supplied, not produced by an invented convolution.
- Mask supplied selects DeformableConv v2; maskNone selects original nonmodulated deformation.
- Weight is a true Parameter; groups1 and offset_groups1 are distinct source-derived quantities.
- biasFalse passesNone and the wrapper creates zero bias; maskNone also creates an empty placeholder with use_maskFalse.
- The C++/CUDA kernel is opaque; no fabricated interpolation subnodes.
