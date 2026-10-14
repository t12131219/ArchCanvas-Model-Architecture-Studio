# Degree mask / strict autoregressive topology：源码与图框对应

来源：`ikostrikov/pytorch-flows`，固定提交 `bf12ed91b86867b38d74982f5e2d44c248604df9`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `get_mask` | 12–29 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| autoregressive_mask.root | Degree mask / strict autoregressive topology |  | E001 | — |
| autoregressive_mask.dims | Static constructor dimensions | in=8; out=8; flowD=4 | E001 | — |
| autoregressive_mask.body | Degree mask module | [8,8] | E001 | — |
| autoregressive_mask.inputdegree | Hidden-input degrees |  | E001 | — |
| autoregressive_mask.i_arange | arange(in_features) | [8] | E001 | — |
| autoregressive_mask.i_mod | modulo (flowD - 1) | [8] | E001 | — |
| autoregressive_mask.outputdegree | Strict output degrees |  | E001 | — |
| autoregressive_mask.o_arange | arange(out_features) | [8] | E001 | — |
| autoregressive_mask.o_mod | modulo flowD; subtract 1 | [8] | E001 | — |
| autoregressive_mask.compare | Broadcast dependency comparison |  | E001 | — |
| autoregressive_mask.ge | out_deg[:,None] >= in_deg[None,:] | [8,8] | E001 | — |
| autoregressive_mask.float | float() / binary connectivity | [8,8] | E001 | — |
| autoregressive_mask.mask | Output-layer mask | [8,8] | E001 | — |

## 与教科书/通用基础图的区别

- Do not omit output degree minus1, transpose the mask, or treat the >= comparison as a Softmax.

## 源码事实与边界

- Input degrees use modulo D-1 for hidden units. Output degrees use modulo D then minus1, so output coordinate i can only depend on preceding input degrees.
- Comparison result has row=output unit and column=input unit. The float mask is fixed topology, not an attention probability or learned parameter.
- This function merely returns a tensor; register_buffer belongs to its MaskedLinear caller. Input/hidden mask types are alternate source branches not mixed into this selected view.
