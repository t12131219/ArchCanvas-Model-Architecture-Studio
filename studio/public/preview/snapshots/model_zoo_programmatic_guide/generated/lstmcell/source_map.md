# LSTM (explicit gates, shared time steps)：源码与图框对应

来源：`https://github.com/pytorch/pytorch`，固定提交 `a8d6afb511a69687bbb2b7e88a3cf67917e1697e`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [pytorch-lstmcell-v2.5.1/benchmarks/fastrnns/custom_lstms.py](sources/pytorch-lstmcell-v2.5.1/benchmarks/fastrnns/custom_lstms.py) · `LSTMCell` | 122–153 | — |
| E002 | [pytorch-lstmcell-v2.5.1/benchmarks/fastrnns/custom_lstms.py](sources/pytorch-lstmcell-v2.5.1/benchmarks/fastrnns/custom_lstms.py) · `LSTMCell.__init__` | 123–130 | — |
| E003 | [pytorch-lstmcell-v2.5.1/benchmarks/fastrnns/custom_lstms.py](sources/pytorch-lstmcell-v2.5.1/benchmarks/fastrnns/custom_lstms.py) · `LSTMCell.forward` | 133–153 | — |
| E004 | [pytorch-lstmcell-v2.5.1/benchmarks/fastrnns/custom_lstms.py](sources/pytorch-lstmcell-v2.5.1/benchmarks/fastrnns/custom_lstms.py) · `LSTMLayer` | 221–235 | — |
| E005 | [pytorch-lstmcell-v2.5.1/benchmarks/fastrnns/custom_lstms.py](sources/pytorch-lstmcell-v2.5.1/benchmarks/fastrnns/custom_lstms.py) · `LSTMLayer.__init__` | 222–224 | — |
| E006 | [pytorch-lstmcell-v2.5.1/benchmarks/fastrnns/custom_lstms.py](sources/pytorch-lstmcell-v2.5.1/benchmarks/fastrnns/custom_lstms.py) · `LSTMLayer.forward` | 227–235 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| lstmcell.root | One LSTMLayer / three shared time steps | T=3, one layer, one direction | E005,E006 | — |
| lstmcell.sequence | Sequence input X | [T=3,B,I=8] | E006 | — |
| lstmcell.unbind | Unbind time axis 0 | 3 tensors [B,8] | E006 | — |
| lstmcell.x0 | Select x_0 | [B,8] | E006 | — |
| lstmcell.x1 | Select x_1 | [B,8] | E006 | — |
| lstmcell.x2 | Select x_2 | [B,8] | E006 | — |
| lstmcell.step0 | LSTM cell / time 0 | (output h, state(h,c)) | E006,E003 | cell; instance=self.cell |
| lstmcell.step0.x | Input x_0 | [B,8] | E006,E003 | — |
| lstmcell.step0.hx | Previous hidden h_-1 | [B,16] | E003 | — |
| lstmcell.step0.cx | Previous cell c_-1 | [B,16] | E003 | — |
| lstmcell.step0.affine | Fused four-gate affine | gates: [B,4H=64] | E002,E003 | cell |
| lstmcell.step0.x_mm | MatMul x W_ih^T | [B,64] | E002,E003 | cell.weight_ih |
| lstmcell.step0.h_mm | MatMul h W_hh^T | [B,64] | E002,E003 | cell.weight_hh |
| lstmcell.step0.b_ih | Add input bias b_ih | [B,64] | E002,E003 | cell.bias_ih |
| lstmcell.step0.affine_add | Add hidden projection | [B,64] | E003 | — |
| lstmcell.step0.b_hh | Add hidden bias b_hh | [B,64] | E002,E003 | cell.bias_hh |
| lstmcell.step0.chunk | Chunk gates: i / f / g / o | 4 x [B,16] | E003 | — |
| lstmcell.step0.gates | Four distinct gate slices | i, f, g, o: [B,H] | E003 | — |
| lstmcell.step0.i | Input gate i: Sigmoid | [B,16] | E003 | cell four fused parameters; i rows [0:16] |
| lstmcell.step0.f | Forget gate f: Sigmoid | [B,16] | E003 | cell four fused parameters; f rows [16:32] |
| lstmcell.step0.g | Candidate g: Tanh | [B,16] | E003 | cell four fused parameters; g rows [32:48] |
| lstmcell.step0.o | Output gate o: Sigmoid | [B,16] | E003 | cell four fused parameters; o rows [48:64] |
| lstmcell.step0.cell_update | Cell state update | c_t = f*c_prev + i*g | E003 | — |
| lstmcell.step0.forget_mul | Multiply f * previous c | [B,16] | E003 | — |
| lstmcell.step0.input_mul | Multiply i * candidate g | [B,16] | E003 | — |
| lstmcell.step0.cy | Add terms -> cell c_0 | [B,16] | E003 | — |
| lstmcell.step0.hidden_update | Hidden state update | h_t = o*tanh(c_t) | E003 | — |
| lstmcell.step0.tanh_c | Tanh updated cell | [B,16] | E003 | — |
| lstmcell.step0.hy | Multiply o * tanh(c) -> h_0 | [B,16] | E003 | — |
| lstmcell.step0.return | Return h, (h, c) | h: [B,16]; state: 2 tensors | E003 | — |
| lstmcell.step1 | LSTM cell / time 1 | (output h, state(h,c)) | E006,E003 | cell; instance=self.cell |
| lstmcell.step1.x | Input x_1 | [B,8] | E006,E003 | — |
| lstmcell.step1.hx | Previous hidden h_0 | [B,16] | E003 | — |
| lstmcell.step1.cx | Previous cell c_0 | [B,16] | E003 | — |
| lstmcell.step1.affine | Fused four-gate affine | gates: [B,4H=64] | E002,E003 | cell |
| lstmcell.step1.x_mm | MatMul x W_ih^T | [B,64] | E002,E003 | cell.weight_ih |
| lstmcell.step1.h_mm | MatMul h W_hh^T | [B,64] | E002,E003 | cell.weight_hh |
| lstmcell.step1.b_ih | Add input bias b_ih | [B,64] | E002,E003 | cell.bias_ih |
| lstmcell.step1.affine_add | Add hidden projection | [B,64] | E003 | — |
| lstmcell.step1.b_hh | Add hidden bias b_hh | [B,64] | E002,E003 | cell.bias_hh |
| lstmcell.step1.chunk | Chunk gates: i / f / g / o | 4 x [B,16] | E003 | — |
| lstmcell.step1.gates | Four distinct gate slices | i, f, g, o: [B,H] | E003 | — |
| lstmcell.step1.i | Input gate i: Sigmoid | [B,16] | E003 | cell four fused parameters; i rows [0:16] |
| lstmcell.step1.f | Forget gate f: Sigmoid | [B,16] | E003 | cell four fused parameters; f rows [16:32] |
| lstmcell.step1.g | Candidate g: Tanh | [B,16] | E003 | cell four fused parameters; g rows [32:48] |
| lstmcell.step1.o | Output gate o: Sigmoid | [B,16] | E003 | cell four fused parameters; o rows [48:64] |
| lstmcell.step1.cell_update | Cell state update | c_t = f*c_prev + i*g | E003 | — |
| lstmcell.step1.forget_mul | Multiply f * previous c | [B,16] | E003 | — |
| lstmcell.step1.input_mul | Multiply i * candidate g | [B,16] | E003 | — |
| lstmcell.step1.cy | Add terms -> cell c_1 | [B,16] | E003 | — |
| lstmcell.step1.hidden_update | Hidden state update | h_t = o*tanh(c_t) | E003 | — |
| lstmcell.step1.tanh_c | Tanh updated cell | [B,16] | E003 | — |
| lstmcell.step1.hy | Multiply o * tanh(c) -> h_1 | [B,16] | E003 | — |
| lstmcell.step1.return | Return h, (h, c) | h: [B,16]; state: 2 tensors | E003 | — |
| lstmcell.step2 | LSTM cell / time 2 | (output h, state(h,c)) | E006,E003 | cell; instance=self.cell |
| lstmcell.step2.x | Input x_2 | [B,8] | E006,E003 | — |
| lstmcell.step2.hx | Previous hidden h_1 | [B,16] | E003 | — |
| lstmcell.step2.cx | Previous cell c_1 | [B,16] | E003 | — |
| lstmcell.step2.affine | Fused four-gate affine | gates: [B,4H=64] | E002,E003 | cell |
| lstmcell.step2.x_mm | MatMul x W_ih^T | [B,64] | E002,E003 | cell.weight_ih |
| lstmcell.step2.h_mm | MatMul h W_hh^T | [B,64] | E002,E003 | cell.weight_hh |
| lstmcell.step2.b_ih | Add input bias b_ih | [B,64] | E002,E003 | cell.bias_ih |
| lstmcell.step2.affine_add | Add hidden projection | [B,64] | E003 | — |
| lstmcell.step2.b_hh | Add hidden bias b_hh | [B,64] | E002,E003 | cell.bias_hh |
| lstmcell.step2.chunk | Chunk gates: i / f / g / o | 4 x [B,16] | E003 | — |
| lstmcell.step2.gates | Four distinct gate slices | i, f, g, o: [B,H] | E003 | — |
| lstmcell.step2.i | Input gate i: Sigmoid | [B,16] | E003 | cell four fused parameters; i rows [0:16] |
| lstmcell.step2.f | Forget gate f: Sigmoid | [B,16] | E003 | cell four fused parameters; f rows [16:32] |
| lstmcell.step2.g | Candidate g: Tanh | [B,16] | E003 | cell four fused parameters; g rows [32:48] |
| lstmcell.step2.o | Output gate o: Sigmoid | [B,16] | E003 | cell four fused parameters; o rows [48:64] |
| lstmcell.step2.cell_update | Cell state update | c_t = f*c_prev + i*g | E003 | — |
| lstmcell.step2.forget_mul | Multiply f * previous c | [B,16] | E003 | — |
| lstmcell.step2.input_mul | Multiply i * candidate g | [B,16] | E003 | — |
| lstmcell.step2.cy | Add terms -> cell c_2 | [B,16] | E003 | — |
| lstmcell.step2.hidden_update | Hidden state update | h_t = o*tanh(c_t) | E003 | — |
| lstmcell.step2.tanh_c | Tanh updated cell | [B,16] | E003 | — |
| lstmcell.step2.hy | Multiply o * tanh(c) -> h_2 | [B,16] | E003 | — |
| lstmcell.step2.return | Return h, (h, c) | h: [B,16]; state: 2 tensors | E003 | — |
| lstmcell.stack | Stack all time outputs | [3,B,16] | E006 | — |
| lstmcell.return | Layer return: sequence, final state | [3,B,16], ([B,16],[B,16]) | E006 | — |
| lstmcell.initial_h | External initial hidden | [B,16] | E006 | — |
| lstmcell.initial_c | External initial cell | [B,16] | E006 | — |

## 与教科书/通用基础图的区别

- The reference image shows temporal recurrence and cell equations; replace implicit concatenation with the actual two source MatMuls.
- Draw one input gate, one forget gate, one output gate and a Tanh candidate; four gates are slices, not four independently constructed Linear modules.
- The candidate is not a fourth Sigmoid; the cell memory route is separate from the hidden-state route.
- Do not add peepholes, forget-bias+1, Dropout, LayerNorm, packing or a classifier absent from this chosen source variant.
- Time advances horizontally; operator dependencies inside the central cell advance bottom-to-top.
- Existing packed and bidirectional LSTM examples retain their separate source/configuration and explicit library boundaries.

## 源码事实与边界

- Official custom LSTMCell explicitly defines two 4H matrices and two biases; no opaque nn.LSTM is substituted.
- Source affine addition order is x W_ih^T + b_ih + h_prev W_hh^T + b_hh; the diagram preserves that order.
- gates.chunk(4,1) yields i,f,g,o; i/f/o use Sigmoid and candidate g uses Tanh.
- Cell update is f*c_prev+i*g; hidden update is o*tanh(c); c_prev never directly supplies the affine gates.
- Cell returns hy,(hy,cy), with the exact same hy tensor as output and state hidden.
- LSTMLayer creates one self.cell; its time loop reuses all four parameter tensors and carries both h and c.
- Three steps are a selected T=3 input; the input and hidden widths 8/16 are illustrative configuration, not inferred defaults.
- Layer unbinds time axis0 and stacks all outputs, returning the complete sequence and only the final h/c state.
- Initial h/c are mandatory supplied state arguments; the source does not create a zero default inside LSTMLayer.forward.
