# TuckER relation-conditioned core：源码与图框对应

来源：`ibalazevic/TuckER`，固定提交 `23aff592115ee91e099ce490cdbea28ef026fc54`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [tucker-modules/model.py](sources/tucker-modules/model.py) · `TuckER.__init__` | 7–21 | — |
| E002 | [tucker-modules/model.py](sources/tucker-modules/model.py) · `TuckER.forward` | 28–45 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| tucker_core.root | TuckER relation-conditioned core / module only | [B,8] | E002 | — |
| tucker_core.subject | Subject features after input Dropout | [B,8] | E002 | — |
| tucker_core.relation | Relation IDs r_idx | [B] | E002 | — |
| tucker_core.core | Owned learned 3-way core W | [6,8,8] | E001 | W |
| tucker_core.e1shape | Original subject embedding WIDTH | e1.size(1) = 8 | E002 | — |
| tucker_core.module | TuckER relation-conditioned core / operators | [B,8] | E002 | — |
| tucker_core.relationlookup | Owned relation embedding R | [B,6] | E001,E002 | R.weight; instance=R |
| tucker_core.subjectview | View subject as row per batch | [B,1,8] | E002 | — |
| tucker_core.condition | Contract relation into core | [B,8,8] | E001,E002 | — |
| tucker_core.condition.mm | r @ core.view(6,-1) | [B,64] | E001,E002 | — |
| tucker_core.condition.reshape | View conditioned matrix | [B,8,8] | E001,E002 | — |
| tucker_core.condition.dropout | Hidden Dropout1 .3 | [B,8,8] | E001,E002 | — |
| tucker_core.multiply | Subject row @ conditioned matrix | [B,1,8] | E002 | — |
| tucker_core.restore | Restore feature axis | [B,8] | E002 | — |
| tucker_core.output | Selected module output | [B,8] | E002 | — |

## 与教科书/通用基础图的区别

- Do not draw relation as a gate multiplying subject elementwise, collapse the 3-way core into a plain Linear, or include unrelated classifier/sigmoid in this module.

## 源码事实与边界

- Owned relation embedding R\[r_idx\] contracts with owned core W\[d2,d1,d1\] to form one relation-conditioned square matrix per batch item. Subject features then multiply that matrix in ordered bmm.
- hidden_dropout1 applies to the conditioned matrix BEFORE subject multiplication; it is not dropout of the final entity score.
- Core constructor explicitly creates a CUDA tensor using NumPy random initialization. That is recorded as a runtime boundary; neither initialization nor CUDA/model code is executed.
- Selected boundary is a reusable feature-transformation suffix. It excludes input preprocessing and the later tied entity embedding scoring; no full knowledge-graph task model is claimed.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
