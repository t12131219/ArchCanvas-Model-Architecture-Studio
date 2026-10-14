# Capsule agreement routing：源码与图框对应

来源：`adambielski/CapsNet-pytorch`，固定提交 `bee0cbee5bb8b30399e75c751d3085c2f261dea3`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E003 | [capsnet-modules/net.py](sources/capsnet-modules/net.py) · `squash` | 12–16 | — |
| E001 | [capsnet-modules/net.py](sources/capsnet-modules/net.py) · `AgreementRouting.__init__` | 20–23 | — |
| E002 | [capsnet-modules/net.py](sources/capsnet-modules/net.py) · `AgreementRouting.forward` | 25–42 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| capsule_routing.root | Capsule agreement routing / module only | [B,10,16] | E002 | — |
| capsule_routing.votes | Fixed votes u_predict | [B,1152,10,16] | E002 | — |
| capsule_routing.b | Learned initial routing logits b | [1152,10] | E001 | b |
| capsule_routing.module | Capsule agreement routing / operators | [B,10,16] | E002 | — |
| capsule_routing.initial | Initial routing before loop | [B,10,16] | E002,E003 | — |
| capsule_routing.initial.softmax | Softmax b / dim omitted | [1152,10] | E002,E003 | — |
| capsule_routing.initial.sum | Broadcast c / sum input capsules | [B,10,16] | E002,E003 | — |
| capsule_routing.initial.squash | Squash capsule vectors | [B,10,16] | E002,E003 | — |
| capsule_routing.expand | Expand SAME b over batch | [B,1152,10] | E002 | — |
| capsule_routing.agreement | Unsqueeze v / vote agreement | [B,1152,10] | E002 | — |
| capsule_routing.update | Update batch routing state | [B,1152,10] | E002 | — |
| capsule_routing.couplings | Repeat3 / new couplings | [B,1152,10,1] | E002 | —; 3 |
| capsule_routing.couplings.view | View batches of output capsules | [B*1152,10] | E002 | — |
| capsule_routing.couplings.softmax | Softmax / dim omitted | [B*1152,10] | E002 | — |
| capsule_routing.couplings.restore | Restore coupling axes | [B,1152,10,1] | E002 | — |
| capsule_routing.sum | Weighted vote sum over input caps | [B,10,16] | E002 | — |
| capsule_routing.squash | Squash / source has no epsilon | [B,10,16] | E003 | — |
| capsule_routing.output | Selected module output | [B,10,16] | E002 | — |

## 与教科书/通用基础图的区别

- Do not draw learned b as a fixed buffer, claim3 total passes, or invent independent parameters per routing round.
- Do not include CapsNet classifier/reconstruction in this module-only graph.

## 源码事实与边界

- Unlike common textbook routing, source b is a learned Parameter initialized to zero and shared across batch. b_batch is per-forward state, not a new Parameter.
- Source performs an initial Softmax/sum/squash before the n_iterations loop; selected3 iterations therefore produce four aggregations, not three.
- Votes are retained and reused in every agreement and weighted sum; no detach occurs. b_batch and v are loop-carried state.
- Both F.softmax calls omit dim; loop reshapes to rows of output_caps, but runtime-dependent legacy dim behavior is preserved rather than silently repaired.
- squash divides by lengths with no epsilon in source; shape reasoning does not establish numerical behavior at zero length.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
