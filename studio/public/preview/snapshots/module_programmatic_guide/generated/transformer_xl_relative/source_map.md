# Transformer-XL relative attention：源码与图框对应

来源：`kimiyoung/transformer-xl`，固定提交 `44781ed21dbaec88b280f74d9ae2877f52b492a5`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [transformer-xl-relative/pytorch/mem_transformer.py](sources/transformer-xl-relative/pytorch/mem_transformer.py) · `RelMultiHeadAttn.__init__` | 144–163 | — |
| E002 | [transformer-xl-relative/pytorch/mem_transformer.py](sources/transformer-xl-relative/pytorch/mem_transformer.py) · `RelMultiHeadAttn._rel_shift` | 194–207 | — |
| E003 | [transformer-xl-relative/pytorch/mem_transformer.py](sources/transformer-xl-relative/pytorch/mem_transformer.py) · `RelPartialLearnableMultiHeadAttn.__init__` | 213–216 | — |
| E004 | [transformer-xl-relative/pytorch/mem_transformer.py](sources/transformer-xl-relative/pytorch/mem_transformer.py) · `RelPartialLearnableMultiHeadAttn.forward` | 218–291 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| transformer_xl_relative.root | Transformer-XL relative attention |  | E001,E003,E002,E004 | — |
| txl.w | Current sequence w | [3,B,16] | E004 | — |
| txl.memory | Caller memory / fixed branch | [4,B,16] | E004 | — |
| txl.position | Supplied relative encoding r | [7,16] | E004 | — |
| txl.biases | Caller content / relative biases | r_w_bias,r_r_bias:[2,8] | E004 | — |
| txl.external_mask | Caller 3D attention mask | [3,7,B] | E004 | — |
| txl.body | Relative attention / memory branch | [3,B,16] | E001,E003,E004,E002 | — |
| txl.cat | Concat [memory, current w] / time | [7,B,16] | E004 | — |
| txl.qkv | Joint QKV Linear16 -> 48 | [7,B,48] | E001,E004 | qkv_net |
| txl.split | Chunk Q_all,K,V / last axis | each:[7,B,16] | E004 | — |
| txl.q | Keep last3 Q + view heads | [3,B,2,8] | E004 | — |
| txl.k | View memory + current K heads | [7,B,2,8] | E004 | — |
| txl.v | View memory + current V heads | [7,B,2,8] | E004 | — |
| txl.r | Relative-position projection | [7,2,8] | E003,E004 | — |
| txl.rlinear | Position Linear16 -> 16 | [7,16] | E003,E004 | r_net |
| txl.rview | View relative heads / no batch | [7,2,8] | E004 | — |
| txl.rw | Q + external content bias | [3,B,2,8] | E004 | — |
| txl.rr | Q + external relative bias | [3,B,2,8] | E004 | — |
| txl.ac | Content score AC / einsum | [3,7,B,2] | E004 | — |
| txl.bd | Relative score BD / einsum | [3,7,B,2] | E004 | — |
| txl.shift | Relative shift / source helper | [3,7,B,2] | E002 | — |
| txl.zero | Zeros from BD shape/device/dtype | [3,1,B,2] | E002 | — |
| txl.pad | Prepend zero column / dim1 | [3,8,B,2] | E002 | — |
| txl.shift_view | View [K+1,T,B,heads] | [8,3,B,2] | E002 | — |
| txl.shift_slice | Drop first row + view_as(BD) | [3,7,B,2] | E002 | — |
| txl.score | AC + shifted BD | [3,7,B,2] | E004 | — |
| txl.scale | Multiply by 1 / sqrt(d_head8) | [3,7,B,2] | E001,E004 | — |
| txl.mask | 3D mask / True -> -inf | [3,7,B,2] | E004 | — |
| txl.softmax | Softmax on key-time axis1 | [3,7,B,2] | E004 | — |
| txl.dropatt | Attention Dropout .1 / eval | [3,7,B,2] | E001,E004 | — |
| txl.aggregate | einsum(prob, memory+current V) | [3,B,2,8] | E004 | — |
| txl.tail | Head merge and output projection | [3,B,16] | E001,E004 | — |
| txl.merge | Contiguous + merge heads | [3,B,16] | E004 | — |
| txl.olinear | Output Linear16 -> 16 | [3,B,16] | E001,E004 | o_net |
| txl.odrop | Output Dropout .1 / eval | [3,B,16] | E001,E004 | — |
| txl.residual | Original current w + attention out | [3,B,16] | E004 | — |
| txl.norm | Post LayerNorm16 / library | [3,B,16] | E001,E004 | layer_norm |
| txl.output | Return normalized current output | [3,B,16] | E004 | — |

## 与教科书/通用基础图的区别

- Do not add sinusoidal encodings to token embeddings in place of the relative score term.
- Do not use memory positions as queries or residual state; do not treat zero padding as a learned parameter.
- Do not claim this isolated attention module updates or detaches its memory input.

## 源码事实与边界

- Memory and current sequence concatenate before joint QKV projection; only Q keeps the trailing current positions, while K/V retain all7.
- r_net projects caller-provided relative encodings, without a batch dimension; content and relative biases are separate caller arguments.
- AC uses Q+r_w_bias against K; BD uses Q+r_r_bias against r_net(r), then the actual _rel_shift helper changes relative alignment.
- Selected relative shift uses prepend zeros, view, slice and view_as; zero_triu defaultFalse is retained.
- Scores add AC+shiftedBD, scale by1/sqrt(d_head), optionally mask and normalize key-time dim1 before attention Dropout.
- The residual adds original current w only; post LayerNorm is selected. Memory creation/update/detach in the enclosing model is outside this module.
- The module returns output only, not attention probability or newly generated memory.
