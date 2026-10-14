# Conditional BatchNorm / two condition heads：源码与图框对应

来源：`ajbrock/BigGAN-PyTorch`，固定提交 `98459431a5d618d644d54cd1e9fceb1e5045648d`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [biggan-modules/layers.py](sources/biggan-modules/layers.py) · `ccbn.__init__` | 279–303 | — |
| E002 | [biggan-modules/layers.py](sources/biggan-modules/layers.py) · `ccbn.forward` | 306–325 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| conditional_bn.root | Conditional BatchNorm / two condition heads |  | E001,E002 | — |
| conditional_bn.x | Feature x | [B,8,8,8] | E002 | — |
| conditional_bn.condition | Condition y | [B,16] | E002 | — |
| conditional_bn.body | Conditional BatchNorm module | [B,8,8,8] | E001,E002 | — |
| conditional_bn.norm | BatchNorm without affine |  | E002 | — |
| conditional_bn.bn | F.batch_norm / affine=None | [B,8,8,8] | E002 | — |
| conditional_bn.gain | Gain from condition |  | E002 | — |
| conditional_bn.gainlinear | Independent Linear 16 -> 8 | [B,8] | E001,E002 | instance=gain |
| conditional_bn.gainview | 1+gain(y); view B,C,1,1 | [B,8,1,1] | E002 | — |
| conditional_bn.bias | Bias from condition |  | E002 | — |
| conditional_bn.biaslinear | Independent Linear 16 -> 8 | [B,8] | E001,E002 | instance=bias |
| conditional_bn.biasview | bias(y); view B,C,1,1 | [B,8,1,1] | E002 | — |
| conditional_bn.multiply | Condition scale |  | E002 | — |
| conditional_bn.mul | out * gain | [B,8,8,8] | E002 | — |
| conditional_bn.add | Condition shift |  | E002 | — |
| conditional_bn.addop | scaled + bias | [B,8,8,8] | E002 | — |
| conditional_bn.y | Conditioned features | [B,8,8,8] | E002 | — |

## 与教科书/通用基础图的区别

- Do not replace conditional y by class indices or one-hot embeddings absent from this boundary.

## 源码事实与边界

- Two independent condition heads predict per-example gain and bias; gain has an explicit +1 offset.
- Feature normalization has no affine parameters. stored_mean/var are buffers and the selected training call may update them inside the library.
- F.batch_norm receives literal momentum .1, irrespective of the constructor self.momentum attribute.
- Other branches are excluded. The GN path references self.normstyle, a source typo, and is not silently repaired.
