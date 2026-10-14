# Compact bilinear TensorSketch：源码与图框对应

来源：`gdlg/pytorch_compact_bilinear_pooling`，固定提交 `ecbb98bdccaf8987f2c2432ac0f1db5f370811e8`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E006 | [compact-bilinear-modules/compact_bilinear_pooling/__init__.py](sources/compact-bilinear-modules/compact_bilinear_pooling/__init__.py) · `CountSketchFn_forward` | 7–27 | — |
| E005 | [compact-bilinear-modules/compact_bilinear_pooling/__init__.py](sources/compact-bilinear-modules/compact_bilinear_pooling/__init__.py) · `CountSketch.__init__` | 85–107 | — |
| E004 | [compact-bilinear-modules/compact_bilinear_pooling/__init__.py](sources/compact-bilinear-modules/compact_bilinear_pooling/__init__.py) · `ComplexMultiply_forward` | 116–119 | — |
| E003 | [compact-bilinear-modules/compact_bilinear_pooling/__init__.py](sources/compact-bilinear-modules/compact_bilinear_pooling/__init__.py) · `CompactBilinearPoolingFn.forward` | 143–173 | — |
| E001 | [compact-bilinear-modules/compact_bilinear_pooling/__init__.py](sources/compact-bilinear-modules/compact_bilinear_pooling/__init__.py) · `CompactBilinearPooling.__init__` | 252–257 | — |
| E002 | [compact-bilinear-modules/compact_bilinear_pooling/__init__.py](sources/compact-bilinear-modules/compact_bilinear_pooling/__init__.py) · `CompactBilinearPooling.forward` | 259–263 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| compact_bilinear_pooling.root | Compact bilinear TensorSketch / module only | [B,16] | E003 | — |
| compact_bilinear_pooling.x | Input x | [B,8] | E003 | — |
| compact_bilinear_pooling.y | Independent input y | [B,6] | E003 | — |
| compact_bilinear_pooling.xbuffers | Fixed sketch1 buffers h, s | each[8] | E005 | — |
| compact_bilinear_pooling.ybuffers | Distinct sketch2 buffers h, s | each[6] | E005 | — |
| compact_bilinear_pooling.module | Compact bilinear TensorSketch / operators | [B,16] | E003 | — |
| compact_bilinear_pooling.xsketch | X fixed CountSketch | [B,16] | E006,E005 | — |
| compact_bilinear_pooling.xsketch.sign | Multiply by fixed random signs | [B,8] | E006,E005 | — |
| compact_bilinear_pooling.xsketch.scatter | Hash-index scatter_add | [B,16] | E006,E005 | — |
| compact_bilinear_pooling.xfft | Historical rFFT / library | [B,9,2] | E003 | — |
| compact_bilinear_pooling.ysketch | Y fixed CountSketch | [B,16] | E006,E005 | — |
| compact_bilinear_pooling.ysketch.sign | Multiply by fixed random signs | [B,6] | E006,E005 | — |
| compact_bilinear_pooling.ysketch.scatter | Hash-index scatter_add | [B,16] | E006,E005 | — |
| compact_bilinear_pooling.yfft | Historical rFFT / library | [B,9,2] | E003 | — |
| compact_bilinear_pooling.product | Complex product / real and imag | [B,9] real + imag | E004 | — |
| compact_bilinear_pooling.inverse | Stack complex pair / inverse FFT | [B,16] | E003 | — |
| compact_bilinear_pooling.inverse.stack | Stack real / imaginary | [B,9,2] | E003 | — |
| compact_bilinear_pooling.inverse.irfft | Historical irFFT / library | [B,16] | E003 | — |
| compact_bilinear_pooling.output | Selected module output | [B,16] | E003 | — |

## 与教科书/通用基础图的区别

- Do not replace fixed sketches by learned Linear projections or confuse this compact convolution with BAN weighted bilinear pooling.

## 源码事实与边界

- Each sketch owns independently generated h/s buffers registered at construction; they are shared across calls and have no optimizer parameters.
- CountSketch uses signed hash scatter_add, then legacy torch.rfft spectra are multiplied using the actual real/imag formula, followed by legacy irfft.
- This is feature-axis circular convolution of sketches; source does not explicitly sum spatial positions, normalize, or add signed square-root postprocessing.
- Historical FFT APIs are preserved as source boundaries; no upstream code was run or silently migrated.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
