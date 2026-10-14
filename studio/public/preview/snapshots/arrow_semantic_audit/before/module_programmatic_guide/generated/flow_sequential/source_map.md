# FlowSequential / dual-stream composition：源码与图框对应

来源：`ikostrikov/pytorch-flows`，固定提交 `bf12ed91b86867b38d74982f5e2d44c248604df9`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E004 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `Sigmoid.forward` | 184–192 | — |
| E002 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `Reverse.__init__` | 388–391 | — |
| E003 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `Reverse.forward` | 393–399 | — |
| E001 | [density-flow-modules/flows.py](sources/density-flow-modules/flows.py) · `FlowSequential.forward` | 467–488 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| flow_sequential.root | FlowSequential / dual-stream composition |  | E001,E004,E002,E003 | — |
| flow_sequential.x | Input features | [B,4] | E001 | — |
| flow_sequential.body | FlowSequential module | [B,4] | E001,E004,E002,E003 | — |
| flow_sequential.init | Initialize accumulator |  | E001 | — |
| flow_sequential.zeros | zeros(B,1) if logdets=None | [B,1] | E001 | — |
| flow_sequential.first | Registered component 0 |  | E001 | — |
| flow_sequential.call0 | Sigmoid call -> u, det0 | u[B,4]; det0[B,1] | E004,E001 | instance=0 |
| flow_sequential.second | Registered component 1 |  | E001 | — |
| flow_sequential.call1 | Reverse call -> v, det1=0 | v[B,4]; det1[B,1] | E003,E002,E001 | instance=1 |
| flow_sequential.add0 | Accumulate component 0 |  | E001 | — |
| flow_sequential.sum0 | logdets += det0 | [B,1] | E001 | — |
| flow_sequential.add1 | Accumulate component 1 |  | E001 | — |
| flow_sequential.sum1 | logdets += det1 | [B,1] | E001 | — |
| flow_sequential.y | Composed transform output | [B,4] | E001 | — |
| flow_sequential.ld | Accumulated logdet | [B,1] | E001 | — |

## 与教科书/通用基础图的区别

- Do not chain component logdet into the next feature tensor or imply duplicate instances on inverse traversal.

## 源码事实与边界

- Registration order controls direct traversal; inverse uses reversed(self._modules.values()) and asks each same instance for its inverse branch.
- Each component returns a feature tensor and a logdet tensor. Feature composition and logdet accumulation are two distinct streams.
- Selected Sigmoid/Reverse components are an illustrative constructor profile, not a claim that an upstream callsite instantiates this exact pair.
- Reverse perm and inv_perm are ordinary NumPy attributes; no learned parameters. Their scalar Jacobian is zero.
