# Channel shuffle / tensor permutation：源码与图框对应

来源：`pytorch/vision`，固定提交 `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py](sources/torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py) · `channel_shuffle` | 21–34 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| shuffle.root | Channel shuffle | Function module | E001 | — |
| shuffle.input | Input x / contiguous | [B,24,8,8] | E001 | — |
| shuffle.module | Shuffle groups=2 | [B,24,8,8] -> [B,24,8,8] | E001 | instance=channel_shuffle_call_1; no learned parameters |
| shuffle.group_view | View C as groups x C/G | [B,2,12,8,8] | E001 | — |
| shuffle.axis_swap | Transpose + contiguous | 2 x 12 -> 12 x 2 axes | E001 | — |
| shuffle.transpose | Transpose axes 1 and 2 | [B,12,2,8,8] | E001 | — |
| shuffle.contiguous | Contiguous memory layout | [B,12,2,8,8] | E001 | — |
| shuffle.flatten_view | View group axes as channels | [B,24,8,8] | E001 | — |
| shuffle.output | Shuffled output | [B,24,8,8] | E001 | — |

## 与教科书/通用基础图的区别

- Do not draw grouped/depthwise convolutions, branch concat, BatchNorm or a classifier around this isolated function.
- The final shape matches the input, but channel values are reordered; equal shapes do not mean an identity operation.
- Keep contiguous between transpose and final view; transpose alone generally leaves a noncontiguous tensor.
- groups2 reshapes24 channels into2x12 before swapping to12x2; it is not a12-group example.
- A channel-index mapping is a static explanation; the source contains no explicit permutation matrix or gather operator.

## 源码事实与边界

- This artifact contains one channel_shuffle(x,groups) call and excludes ShuffleNetV2/InvertedResidual convolutions and branch splitting.
- The declared example uses contiguous\[B,24,8,8\] input,groups2,channels_per_group=24//2=12; C must be divisible by groups.
- The function reads x.size() metadata and computes channels_per_group; these are configuration/shape arithmetic, not new learned feature nodes.
- The literal tensor operation order is view(B,2,12,8,8),transpose(1,2),contiguous(),view(B,-1,8,8).
- Transpose swaps group and within-group axes to\[B,12,2,8,8\]; it does not swap height/width or mix pixels.
- contiguous preserves logical values and shape and provides the storage order required by the following view.
- Output has the same\[B,24,8,8\] shape; output channel o reads input(o%2)*12+o//2 at the same spatial coordinate.
- The static permutation is0,12,1,13,...,11,23; this explanatory mapping is not a separate gather/index_select call in the source.
- All operations are nonparameterized; train/eval mode does not change this function's transformation.
