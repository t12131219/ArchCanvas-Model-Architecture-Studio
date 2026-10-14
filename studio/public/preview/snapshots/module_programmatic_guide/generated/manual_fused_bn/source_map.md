# Manual / fused BatchNorm arithmetic：源码与图框对应

来源：`ajbrock/BigGAN-PyTorch`，固定提交 `98459431a5d618d644d54cd1e9fceb1e5045648d`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [biggan-modules/layers.py](sources/biggan-modules/layers.py) · `fused_bn` | 173–185 | — |
| E002 | [biggan-modules/layers.py](sources/biggan-modules/layers.py) · `manual_bn` | 191–208 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| manual_fused_bn.root | Manual / fused BatchNorm arithmetic |  | E002,E001 | — |
| manual_fused_bn.x | Feature tensor x | [B,8,8,8] | E002 | — |
| manual_fused_bn.gain | Provided gain / bias | [1,8,1,1] | E002 | — |
| manual_fused_bn.body | Manual module | [B,8,8,8] | E002,E001 | — |
| manual_fused_bn.stats | Statistics from float32 x |  | E002 | — |
| manual_fused_bn.cast | x.float() | [B,8,8,8] | E002 | — |
| manual_fused_bn.moments | m=E[x]; m2=E[x^2] | each [1,8,1,1] | E002 | — |
| manual_fused_bn.variance | var=m2-m^2; cast back | [1,8,1,1] | E002 | — |
| manual_fused_bn.scale | Fuse gain into scale |  | E002 | — |
| manual_fused_bn.rsqrt | rsqrt(var+eps) | [1,8,1,1] | E001 | — |
| manual_fused_bn.gainop | scale *= gain | [1,8,1,1] | E001 | — |
| manual_fused_bn.shift | Fuse bias into shift |  | E002 | — |
| manual_fused_bn.shiftop | shift = mean*scale - bias | [1,8,1,1] | E001 | — |
| manual_fused_bn.affine | Apply fused arithmetic |  | E002 | — |
| manual_fused_bn.out | x*scale - shift | [B,8,8,8] | E001 | — |
| manual_fused_bn.y | Normalized affine output | [B,8,8,8] | E002 | — |

## 与教科书/通用基础图的区别

- Do not add running EMA or locally learned gain/bias to this function-only subgraph.

## 源码事实与边界

- Statistics are accumulated in float32, then mean and variance are cast to the original dtype.
- The source uses E\[x²\]-E\[x\]² without clamping. Both moment reductions read the same input; their glyph is a compound statistics operation.
- gain and bias are input arguments, not parameters declared by these functions.
