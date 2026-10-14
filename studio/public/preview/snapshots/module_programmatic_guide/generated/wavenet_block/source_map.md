# WaveNet / gated residual and skip iteration：源码与图框对应

来源：`vincentherrmann/pytorch-wavenet`，固定提交 `26ba28989edcf8688f6216057aafda07601ff07e`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [pytorch-wavenet-sequence/wavenet_model.py](sources/pytorch-wavenet-sequence/wavenet_model.py) · `WaveNetModel.__init__` | 28–123 | — |
| E002 | [pytorch-wavenet-sequence/wavenet_model.py](sources/pytorch-wavenet-sequence/wavenet_model.py) · `WaveNetModel.wavenet` | 125–171 | — |
| E003 | [pytorch-wavenet-sequence/wavenet_model.py](sources/pytorch-wavenet-sequence/wavenet_model.py) · `WaveNetModel.wavenet_dilate` | 173–175 | — |
| E004 | [pytorch-wavenet-sequence/wavenet_modules.py](sources/pytorch-wavenet-sequence/wavenet_modules.py) · `dilate` | 10–39 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| wavenet_block.root | WaveNet / gated residual and skip iteration |  | E001,E003,E002 | — |
| wave.x | Previous loop residual x | [1,32,18] | E002 | — |
| wave.previous_skip | Previous tensor skip | [1,256,18] | E002 | — |
| wave.body | WaveNet loop iteration i=1 | x_next:[2,32,8]; skip_next:[1,256,16] | E001,E002,E004 | — |
| wave.dilate | Dilate2 / fold phases into N | [2,32,9] | E002,E003,E004 | — |
| wave.filter | Filter branch | [2,32,8] | E001,E002 | — |
| wave.filter_conv | Conv2 / 32 -> 32 | [2,32,8] | E001 | filter_convs.1 |
| wave.filter_act | Tanh | [2,32,8] | E002 | — |
| wave.gate | Gate branch | [2,32,8] | E001,E002 | — |
| wave.gate_conv | Conv2 / 32 -> 32 | [2,32,8] | E001 | gate_convs.1 |
| wave.gate_act | Sigmoid | [2,32,8] | E002 | — |
| wave.product | Filter * gate | [2,32,8] | E002 | — |
| wave.skip | Skip path / undo phase folding | [1,256,16] | E001,E002,E004 | — |
| wave.undilate | Restore phases / dilation1 | [1,32,16] | E002,E004 | — |
| wave.skip_conv | Skip Conv1 / 32 -> 256 | [1,256,16] | E001,E002 | skip_convs.1 |
| wave.res_conv | Residual Conv1 / 32 -> 32 | [2,32,8] | E001,E002 | residual_convs.1 |
| wave.res_crop | Crop residual left1 | [2,32,8] | E002 | — |
| wave.skip_crop | Keep last16 previous skip positions | [1,256,16] | E002 | — |
| wave.skip_add | s + cropped previous skip | [1,256,16] | E002 | — |
| wave.res_add | Projected x + cropped residual | [2,32,8] | E002 | — |
| wave.output_x | Updated loop x / phase-folded | [2,32,8] | E002 | — |
| wave.output_skip | Updated loop skip | [1,256,16] | E002 | — |

## 与教科书/通用基础图的区别

- Do not replace phase folding with a falsely claimed source dilation kwarg; do not swap skip and residual convolution outputs.
- Do not crop the residual right side as in TCN; do not call the selected loop states a source return tuple.

## 源码事实与边界

- The actual implementation obtains dilation through permute/view phase folding, not Conv1d(dilation=2); filter/gate Conv1d have ordinary dilation1.
- For selected N1,L18, dilation2 gives N2,L9, valid Conv2 gives L8; the skip helper restores N1,L16 before its1x1 Conv.
- The residual uses left-cropped phase-folded residual after(kernel_size-1); skip keeps the trailing new-skip length.
- Selected i1 has an existing tensor skip; the except zero initializer path is not selected.
- Two glyph outputs are loop-boundary variables, not a tuple returned by WaveNetModel.wavenet; its final waveform logits head is outside scope.
