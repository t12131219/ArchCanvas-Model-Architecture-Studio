# CORN probability decoder：源码与图框对应

来源：`rasbt/deeplearning-models`，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E003 | [rasbt-ordinal-modules/pytorch_ipynb/ordinal/CORN_cement.py](sources/rasbt-ordinal-modules/pytorch_ipynb/ordinal/CORN_cement.py) · `__module__` | 1–213 | [4, 6, 8, 11, 12, 13, 16, 19, 20, 22, 23, 24, 28] |
| E001 | [rasbt-ordinal-modules/pytorch_ipynb/ordinal/CORN_cement.py](sources/rasbt-ordinal-modules/pytorch_ipynb/ordinal/CORN_cement.py) · `MLP.__init__` | 106–126 | [16] |
| E002 | [rasbt-ordinal-modules/pytorch_ipynb/ordinal/CORN_cement.py](sources/rasbt-ordinal-modules/pytorch_ipynb/ordinal/CORN_cement.py) · `MLP.forward` | 128–130 | [16] |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| corn_decoder.root | CORN probability decoder |  | E003,E001,E002 | — |
| corn_decoder.x | Logits from omitted MLP.fc | [B,4] | E003 | — |
| corn_decoder.body | CORN module | [B,4] | E003,E001,E002 | — |
| corn_decoder.conditional | Convert logits to conditionals |  | E003 | — |
| corn_decoder.sigmoid | torch.sigmoid(logits) | [B,4] | E003 | — |
| corn_decoder.cumulative | Ordered cumulative product |  | E003 | — |
| corn_decoder.cumprod | cumprod(probas,dim=1) | [B,4] | E003 | — |
| corn_decoder.y | Cumulative tail probabilities | [B,4] | E003 | — |

## 与教科书/通用基础图的区别

- Do not share all output score weights as in CORAL or replace cumprod by Softmax/sum.

## 源码事实与边界

- MLP.fc is an ordinary K-1-output Linear. Its logits enter this separate caller decoding block.
- The j-th tail probability is the product of conditional probabilities through threshold j; sigmoid alone is insufficient.
- Evidence uses Notebook module scope and preserved cell mappings, rather than inventing a CORNDecoder class.
