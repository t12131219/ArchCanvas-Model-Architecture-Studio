# RoIAlign region sampling：源码与图框对应

来源：`pytorch/vision`，固定提交 `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E004 | [torchvision-v0.9.0-vision-extended/torchvision/ops/roi_align.py](sources/torchvision-v0.9.0-vision-extended/torchvision/ops/roi_align.py) · `roi_align` | 11–55 | — |
| E001 | [torchvision-v0.9.0-vision-extended/torchvision/ops/roi_align.py](sources/torchvision-v0.9.0-vision-extended/torchvision/ops/roi_align.py) · `RoIAlign` | 58–85 | — |
| E002 | [torchvision-v0.9.0-vision-extended/torchvision/ops/roi_align.py](sources/torchvision-v0.9.0-vision-extended/torchvision/ops/roi_align.py) · `RoIAlign.__init__` | 62–73 | — |
| E003 | [torchvision-v0.9.0-vision-extended/torchvision/ops/roi_align.py](sources/torchvision-v0.9.0-vision-extended/torchvision/ops/roi_align.py) · `RoIAlign.forward` | 75–76 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| roi_align.root | RoIAlign region sampling / module | [K,64,7,7] | E002,E003 | — |
| roi_align.input | Module input | [B,64,32,32] | E002,E003 | — |
| roi_align.module | RoIAlign module | [K,64,7,7] | E002,E003 | — |
| roi_align.kernel | RoIAlign / torchvision kernel | [K,64,7,7] | E002,E003,E004 | — |
| roi_align.output | Module output | [K,64,7,7] | E002,E003 | — |
| roi_align.boxes | RoIs / batch index + xyxy | [K,5] | E004 | — |

## 与教科书/通用基础图的区别

- This is torchvision RoIAlign, not longcw crop_and_resize.
- Do not pool the whole image or replace coordinates with feature values.

## 源码事实与边界

- Features and coordinates are different operands; each box first column selects a batch image.
- Tensor RoIs bypass convert_boxes_to_roi_format; output size is pair7x7.
- Source kernel call is opaque; interpolation/bin details are API context rather than invented AST nodes.
- No learning parameters; alignedTrue and fixed2x2 bin sampling are explicitly selected.
