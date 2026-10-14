# CORAL / shared ordinal score head：源码与图框对应

来源：`rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [rasbt-ordinal-modules/pytorch_ipynb/ordinal/CORAL_cement.py](sources/rasbt-ordinal-modules/pytorch_ipynb/ordinal/CORAL_cement.py) · `CoralLayer.__init__` | 135–145 | [17] |
| E002 | [rasbt-ordinal-modules/pytorch_ipynb/ordinal/CORAL_cement.py](sources/rasbt-ordinal-modules/pytorch_ipynb/ordinal/CORAL_cement.py) · `CoralLayer.forward` | 147–160 | [17] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| coral_head.root | CORAL / shared ordinal score head |  | E001,E002 | — |
| coral_head.x | Features after omitted MLP | [B,16] | E002 | — |
| coral_head.bias | Learned threshold biases | [4] | E001 | — |
| coral_head.body | CORAL module | [B,4] | E001,E002 | — |
| coral_head.score | Single shared score |  | E002 | — |
| coral_head.linear | Linear 16 -> 1 / no bias | [B,1] | E001,E002 | — |
| coral_head.broadcast | Broadcast across K-1 thresholds |  | E002 | — |
| coral_head.add | score + coral_bias | [B,4] | E002 | — |
| coral_head.y | Ordinal threshold logits | [B,4] | E002 | — |

## 与教科书/通用基础图的区别

- Do not draw K-1 independent score weight vectors or import an unreviewed external CoralLayer implementation.

## 源码事实与边界

- A single biasless linear score is shared by all K-1 logits, then each threshold receives its own learned bias.
- Default preinitialized bias is arange(K-1,0,-1)/(K-1), here \[1,.75,.5,.25\]; the source does not impose a hard sorted-bias constraint after updates.
- This view stops at logits. Sigmoid decoding and loss calls are outside the class.
