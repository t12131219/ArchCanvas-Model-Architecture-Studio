# Glow ActNorm / data-initialized affine：源码与图框对应

来源：`rosinality/glow-pytorch`，固定提交 `97081ff115a694cf04aeedbd58447f33d242c879`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [glow-modules/model.py](sources/glow-modules/model.py) · `ActNorm.__init__` | 12–19 | — |
| E003 | [glow-modules/model.py](sources/glow-modules/model.py) · `ActNorm.initialize` | 21–40 | — |
| E002 | [glow-modules/model.py](sources/glow-modules/model.py) · `ActNorm.forward` | 42–57 | — |
| E004 | [glow-modules/model.py](sources/glow-modules/model.py) · `ActNorm.reverse` | 59–60 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| glow_actnorm.root | Glow ActNorm / data-initialized affine |  | E001,E003,E002,E004 | — |
| glow_actnorm.x | Input x | [B,8,8,8] | E002 | — |
| glow_actnorm.state | loc / scale + init flag | [1,8,1,1] | E001 | — |
| glow_actnorm.body | Glow ActNorm module | [B,8,8,8] | E001,E003,E002,E004 | — |
| glow_actnorm.init | One-time initialization |  | E002 | — |
| glow_actnorm.guard | If initialized == 0 |  | E002 | — |
| glow_actnorm.stats | Channel mean / std | [1,8,1,1] | E003 | — |
| glow_actnorm.copy | Copy loc=-mean; scale=1/(std+eps) |  | E003,E002 | — |
| glow_actnorm.affine | Broadcast affine |  | E002 | — |
| glow_actnorm.shift | x + loc | [B,8,8,8] | E002 | — |
| glow_actnorm.scale | scale * shifted x | [B,8,8,8] | E002 | — |
| glow_actnorm.det | Log-volume contribution |  | E002 | — |
| glow_actnorm.abslog | log(abs(scale)) | [1,8,1,1] | E002 | — |
| glow_actnorm.sum | H*W * sum log(abs(scale)) | scalar | E002 | — |
| glow_actnorm.y | Affine output y | [B,8,8,8] | E002 | — |
| glow_actnorm.ld | logdet / scalar | scalar | E002 | — |

## 与教科书/通用基础图的区别

- Do not draw logscale as the stored parameter: this implementation stores scale directly.
- No batch-statistics recomputation after initialized becomes 1.

## 源码事实与边界

- loc and scale are learned Parameters, initialized from the first input under no_grad; initialized is a uint8 buffer.
- Returned logdet is one scalar shared across batch, not a per-example vector. The data stream and determinant are separate outputs.
- Reverse is output/scale-loc. Source torch.std default is left version-dependent.
- Initialization mutates the original loc/scale Parameter state. The affine shift, scale multiplication and determinant read named loc/scale state ports, including calls where initialization is skipped.
