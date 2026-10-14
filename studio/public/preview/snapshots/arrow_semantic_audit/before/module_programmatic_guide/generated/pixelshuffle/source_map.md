# Conv4 + PixelShuffle head：源码与图框对应

来源：`pytorch/examples`，固定提交 `acc295dc7b90714f1bf47f06004fc19a7fe235c4`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [pytorch-examples-superres/super_resolution/model.py](sources/pytorch-examples-superres/super_resolution/model.py) · `Net.__init__` | 7–17 | — |
| E003 | [pytorch-examples-superres/super_resolution/model.py](sources/pytorch-examples-superres/super_resolution/model.py) · `Net.forward` | 19–24 | — |
| E002 | [pytorch-examples-superres/super_resolution/model.py](sources/pytorch-examples-superres/super_resolution/model.py) · `Net._initialize_weights` | 26–30 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| pixelshuffle.root | PixelShuffle tail / r=3 | [B,1,24,24] | E003 | — |
| pixelshuffle.input | Input after omitted Conv1-3 + ReLU | [B,32,8,8] | E003 | — |
| pixelshuffle.head | Conv4 + PixelShuffle head | [B,32,8,8] -> [B,1,24,24] | E001,E003 | — |
| pixelshuffle.projection | Channel projection | [B,9,8,8] | E001,E003 | conv4 |
| pixelshuffle.conv4 | Conv3x3: 32 -> 9 | [B,9,8,8] | E001,E003,E002 | instance=conv4 |
| pixelshuffle.shuffle | PixelShuffle r=3 / library | [B,1,24,24] | E001,E003 | instance=pixel_shuffle; no learned parameters |
| pixelshuffle.output | Upscaled single-channel output | [B,1,24,24] | E003 | — |

## 与教科书/通用基础图的区别

- Do not label the entire super-resolution Net as this module; keep the omitted Conv1-3 feature boundary visible.
- Do not replace PixelShuffle with interpolation or ConvTranspose, and do not give it learned weights.
- Do not present reshape/permute/reshape or a3x3 offset diagram as implementation nodes extracted from this file; the source contains one nn.PixelShuffle call.

## 源码事实与边界

- The frozen Net supports a constructor argument upscale_factor. This module example explicitly chooses r=3 and input features\[B,32,8,8\].
- Only conv4 and pixel_shuffle are drawn. conv1, conv2, conv3 and their ReLU calls produce the omitted upstream feature boundary.
- conv4 is Conv2d32->r^2 with kernel3, stride1, padding1 and default bias=True, so r=3 produces\[B,9,8,8\].
- Net.forward calls pixel_shuffle(conv4(x)) directly; no ReLU, normalization or interpolation is inserted after conv4.
- PixelShuffle is a real nn.PixelShuffle(r) instance with no learned parameters. It rearranges\[B,C*r^2,H,W\] into\[B,C,H*r,W*r\].
- For r=3, nine channel offsets map to a3x3 spatial neighborhood and yield\[B,1,24,24\]. The formula is a standard API/mathematical explanation, not four AST-derived reshape operators.
- The PixelShuffle library implementation is not frozen or expanded. Its single source-bound glyph is explicitly marked opaque_runtime_boundary.
- The example initializes conv4.weight orthogonally but does not explicitly reinitialize conv4.bias; initialization is constructor context, not an extra forward layer.
- All shapes are statically inferred under the explicit example profile. No source model, initializer, pixel rearrangement, training or image data was executed.
