# TCN TemporalBlock / causal residual：源码与图框对应

来源：`locuslab/TCN`，固定提交 `2f8c2b817050206397458dfd1f5a25ce8a32fe65`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [tcn-sequence/TCN/tcn.py](sources/tcn-sequence/TCN/tcn.py) · `Chomp1d.__init__` | 7–9 | — |
| E002 | [tcn-sequence/TCN/tcn.py](sources/tcn-sequence/TCN/tcn.py) · `Chomp1d.forward` | 11–12 | — |
| E003 | [tcn-sequence/TCN/tcn.py](sources/tcn-sequence/TCN/tcn.py) · `TemporalBlock.__init__` | 16–34 | — |
| E005 | [tcn-sequence/TCN/tcn.py](sources/tcn-sequence/TCN/tcn.py) · `TemporalBlock.init_weights` | 36–40 | — |
| E004 | [tcn-sequence/TCN/tcn.py](sources/tcn-sequence/TCN/tcn.py) · `TemporalBlock.forward` | 42–45 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| tcn_block.root | TCN TemporalBlock / causal residual |  | E001,E002,E003,E005,E004 | — |
| tcn.input | Input causal sequence | [B,16,16] | E004 | — |
| tcn.body | TemporalBlock / projected shortcut | [B,16,16] -> [B,32,16] | E003,E004 | — |
| tcn.main | net / two convolution stages | [B,32,16] | E003,E004 | — |
| tcn.stage1 | Causal Conv stage 1 | [B,32,16] | E003,E004,E002 | — |
| tcn.stage1.conv | Weight-norm Conv3 / dilation2 | [B,32,20] | E003 | conv1 |
| tcn.stage1.chomp | Chomp right4 + contiguous | [B,32,16] | E003,E002 | — |
| tcn.stage1.relu | ReLU | [B,32,16] | E003 | — |
| tcn.stage1.drop | Dropout p=.2 / eval identity | [B,32,16] | E003 | — |
| tcn.stage2 | Causal Conv stage 2 | [B,32,16] | E003,E004,E002 | — |
| tcn.stage2.conv | Weight-norm Conv3 / dilation2 | [B,32,20] | E003 | conv2 |
| tcn.stage2.chomp | Chomp right4 + contiguous | [B,32,16] | E003,E002 | — |
| tcn.stage2.relu | ReLU | [B,32,16] | E003 | — |
| tcn.stage2.drop | Dropout p=.2 / eval identity | [B,32,16] | E003 | — |
| tcn.projection | Residual Conv1 / 16 -> 32 | [B,32,16] | E003,E004 | downsample |
| tcn.add | Main out + projected residual | [B,32,16] | E004 | — |
| tcn.relu | Final ReLU after residual sum | [B,32,16] | E003,E004 | — |
| tcn.output | TemporalBlock output | [B,32,16] | E004 | — |

## 与教科书/通用基础图的区别

- Do not put dilation2 into a stride; do not crop left or crop before convolution.
- Do not add final Dropout after Add; final source operation is ReLU.

## 源码事实与边界

- Two independent legacy weight_norm Conv1d instances expand length16 to20; each right Chomp4 restores16 and removes future-padding positions.
- Both stages execute Conv, Chomp.contiguous, ReLU, Dropout; the selected eval profile preserves the source Dropout nodes with identity behavior.
- Channel widths differ, so downsample is a learned1x1 Conv; identity shortcut is the source alternative when widths match.
- TemporalConvNet defines dilation=2**i and padding=(k-1)*dilation; this module selects a valid d2/k3 example, not a complete stack.
- weight_norm exposes weight_g and weight_v plus bias; this caller source does not expand the library reparameterization.
