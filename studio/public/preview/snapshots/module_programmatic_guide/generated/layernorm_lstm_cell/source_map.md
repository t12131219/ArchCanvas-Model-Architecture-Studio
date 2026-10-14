# LayerNormLSTMCell / three independent norms：源码与图框对应

来源：`pytorch/pytorch`，固定提交 `a8d6afb511a69687bbb2b7e88a3cf67917e1697e`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py](sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py) · `LayerNorm.__init__` | 157–168 | — |
| E002 | [pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py](sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py) · `LayerNorm.compute_layernorm_stats` | 171–174 | — |
| E003 | [pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py](sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py) · `LayerNorm.forward` | 177–179 | — |
| E004 | [pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py](sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py) · `LayerNormLSTMCell.__init__` | 183–198 | — |
| E005 | [pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py](sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py) · `LayerNormLSTMCell.forward` | 201–218 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| layernorm_lstm_cell.root | LayerNormLSTMCell / three independent norms |  | E004,E001,E002,E003,E005 | — |
| lnlstm.x | Input x | [B,16] | E005 | — |
| lnlstm.h | State hidden hx | [B,16] | E005 | — |
| lnlstm.c | State cell cx | [B,16] | E005 | — |
| lnlstm.body | LayerNorm LSTM / one step | [B,16] | E005 | — |
| lnlstm.wi | Input matrix product / no bias | [B,64] | E004,E005 | — |
| lnlstm.wh | Hidden matrix product / no bias | [B,64] | E004,E005 | — |
| lnlstm.lni | Custom LayerNorm / i | [B,64] | E001,E002,E003 | — |
| lnlstm.lni.mean | Mean over last axis | [B,1] | E001,E002,E003 | — |
| lnlstm.lni.std | Std / unbiased=False | [B,1] | E001,E002,E003 | — |
| lnlstm.lni.center | Input - mean | [B,64] | E001,E002,E003 | — |
| lnlstm.lni.divide | Divide by std / no epsilon | [B,64] | E001,E002,E003 | — |
| lnlstm.lni.affine | Learned gamma + beta | [B,64] | E001,E002,E003 | — |
| lnlstm.lnh | Custom LayerNorm / h | [B,64] | E001,E002,E003 | — |
| lnlstm.lnh.mean | Mean over last axis | [B,1] | E001,E002,E003 | — |
| lnlstm.lnh.std | Std / unbiased=False | [B,1] | E001,E002,E003 | — |
| lnlstm.lnh.center | Input - mean | [B,64] | E001,E002,E003 | — |
| lnlstm.lnh.divide | Divide by std / no epsilon | [B,64] | E001,E002,E003 | — |
| lnlstm.lnh.affine | Learned gamma + beta | [B,64] | E001,E002,E003 | — |
| lnlstm.gates | Add separately normalized affines | [B,64] | E005 | — |
| lnlstm.split | Chunk4 / input,forget,cell,output | [B,16] | E005 | — |
| lnlstm.i | Sigmoid input i | [B,16] | E005 | — |
| lnlstm.f | Sigmoid forget f | [B,16] | E005 | — |
| lnlstm.g | Tanh cell candidate g | [B,16] | E005 | — |
| lnlstm.o | Sigmoid output o | [B,16] | E005 | — |
| lnlstm.keep | f * previous cell | [B,16] | E005 | — |
| lnlstm.new | i * candidate g | [B,16] | E005 | — |
| lnlstm.cadd | Sum retained + new cell | [B,16] | E005 | — |
| lnlstm.lnc | Custom LayerNorm / c | [B,16] | E001,E002,E003 | — |
| lnlstm.lnc.mean | Mean over last axis | [B,1] | E001,E002,E003 | — |
| lnlstm.lnc.std | Std / unbiased=False | [B,1] | E001,E002,E003 | — |
| lnlstm.lnc.center | Input - mean | [B,16] | E001,E002,E003 | — |
| lnlstm.lnc.divide | Divide by std / no epsilon | [B,16] | E001,E002,E003 | — |
| lnlstm.lnc.affine | Learned gamma + beta | [B,16] | E001,E002,E003 | — |
| lnlstm.ctanh | Tanh normalized cell cy | [B,16] | E005 | — |
| lnlstm.hy | o * tanh(cy) | [B,16] | E005 | — |
| lnlstm.output | Return hy, (hy,cy) | hy,cy:[B,16] | E005 | — |

## 与教科书/通用基础图的区别

- Do not merge the two affine products before normalization; do not add bias_ih/bias_hh absent from this cell.
- Do not substitute default nn.LayerNorm epsilon into the explicitly selected custom branch.

## 源码事实与边界

- The supplementary PyTorch benchmark source selects custom LayerNorm when decompose_layernorm=True; the defaultFalse branch uses opaque nn.LayerNorm.
- Input and hidden products have no separate bias tensors; each has its own learned LayerNorm weight/bias.
- The source custom norm uses population std(unbiased=False), no epsilon, then elementwise gamma/beta; three norms have independent parameters.
- Cell accumulation is normalized by layernorm_c before both state return and tanh; hy returns twice in hy,(hy,cy).
