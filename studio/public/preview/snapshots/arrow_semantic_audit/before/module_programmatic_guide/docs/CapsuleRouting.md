# Capsule agreement routing：源码对应与程序化布局

案例键：`capsule_routing`。这是 **模块子图**，不是完整任务模型。

边界：AgreementRouting only, initial routing plus3 refinements; excludes CapsLayer vote weights, primary capsules, task probability and reconstruction heads.

固定仓库：[adambielski/CapsNet-pytorch](https://github.com/adambielski/CapsNet-pytorch/tree/bee0cbee5bb8b30399e75c751d3085c2f261dea3)；commit `bee0cbee5bb8b30399e75c751d3085c2f261dea3`。

## 选定配置与证据强度

```json
{
  "input_caps": 1152,
  "output_caps": 10,
  "output_dim": 16,
  "n_iterations": 3,
  "initial_routing_passes": 1,
  "total_aggregation_passes": 4,
  "learned_initial_logits": true,
  "softmax_dim_argument": "omitted",
  "detach_votes": false,
  "selected_configuration": "explicit static module profile; not a runtime observation",
  "model_executed": false,
  "artifact_scope": "module"
}
```

上面的宽度、迭代次数和形状是适配器明确选择的静态示例，不是模型执行观察。固定源码 SHA256 / Git blob SHA 在 `staging/graph_source_manifest.json`（合并后 `source_manifest.json`）中。只解析 AST 和绘图声明，未导入或运行上游模型、Notebook、torch、NumPy 或 SciPy。

## 源码 ↔ 图元

| 图元稳定 ID | 算子/范围 | 静态形状 | 源码定位 |
| --- | --- | --- | --- |
| `capsule_routing.votes` | Fixed votes u_predict | `[B,1152,10,16]` | [AgreementRouting.forward](https://github.com/adambielski/CapsNet-pytorch/blob/bee0cbee5bb8b30399e75c751d3085c2f261dea3/net.py#L25) |
| `capsule_routing.b` | Learned initial routing logits b | `[1152,10]` | [AgreementRouting.__init__](https://github.com/adambielski/CapsNet-pytorch/blob/bee0cbee5bb8b30399e75c751d3085c2f261dea3/net.py#L20) |
| `capsule_routing.initial.softmax` | Softmax b / dim omitted | `[1152,10]` | [AgreementRouting.forward](https://github.com/adambielski/CapsNet-pytorch/blob/bee0cbee5bb8b30399e75c751d3085c2f261dea3/net.py#L25)；[squash](https://github.com/adambielski/CapsNet-pytorch/blob/bee0cbee5bb8b30399e75c751d3085c2f261dea3/net.py#L12) |
| `capsule_routing.initial.sum` | Broadcast c / sum input capsules | `[B,10,16]` | [AgreementRouting.forward](https://github.com/adambielski/CapsNet-pytorch/blob/bee0cbee5bb8b30399e75c751d3085c2f261dea3/net.py#L25)；[squash](https://github.com/adambielski/CapsNet-pytorch/blob/bee0cbee5bb8b30399e75c751d3085c2f261dea3/net.py#L12) |
| `capsule_routing.initial.squash` | Squash capsule vectors | `[B,10,16]` | [AgreementRouting.forward](https://github.com/adambielski/CapsNet-pytorch/blob/bee0cbee5bb8b30399e75c751d3085c2f261dea3/net.py#L25)；[squash](https://github.com/adambielski/CapsNet-pytorch/blob/bee0cbee5bb8b30399e75c751d3085c2f261dea3/net.py#L12) |
| `capsule_routing.expand` | Expand SAME b over batch | `[B,1152,10]` | [AgreementRouting.forward](https://github.com/adambielski/CapsNet-pytorch/blob/bee0cbee5bb8b30399e75c751d3085c2f261dea3/net.py#L25) |
| `capsule_routing.agreement` | Unsqueeze v / vote agreement | `[B,1152,10]` | [AgreementRouting.forward](https://github.com/adambielski/CapsNet-pytorch/blob/bee0cbee5bb8b30399e75c751d3085c2f261dea3/net.py#L25) |
| `capsule_routing.update` | Update batch routing state | `[B,1152,10]` | [AgreementRouting.forward](https://github.com/adambielski/CapsNet-pytorch/blob/bee0cbee5bb8b30399e75c751d3085c2f261dea3/net.py#L25) |
| `capsule_routing.couplings.view` | View batches of output capsules | `[B*1152,10]` | [AgreementRouting.forward](https://github.com/adambielski/CapsNet-pytorch/blob/bee0cbee5bb8b30399e75c751d3085c2f261dea3/net.py#L25) |
| `capsule_routing.couplings.softmax` | Softmax / dim omitted | `[B*1152,10]` | [AgreementRouting.forward](https://github.com/adambielski/CapsNet-pytorch/blob/bee0cbee5bb8b30399e75c751d3085c2f261dea3/net.py#L25) |
| `capsule_routing.couplings.restore` | Restore coupling axes | `[B,1152,10,1]` | [AgreementRouting.forward](https://github.com/adambielski/CapsNet-pytorch/blob/bee0cbee5bb8b30399e75c751d3085c2f261dea3/net.py#L25) |
| `capsule_routing.sum` | Weighted vote sum over input caps | `[B,10,16]` | [AgreementRouting.forward](https://github.com/adambielski/CapsNet-pytorch/blob/bee0cbee5bb8b30399e75c751d3085c2f261dea3/net.py#L25) |
| `capsule_routing.squash` | Squash / source has no epsilon | `[B,10,16]` | [squash](https://github.com/adambielski/CapsNet-pytorch/blob/bee0cbee5bb8b30399e75c751d3085c2f261dea3/net.py#L12) |
| `capsule_routing.output` | Selected module output | `[B,10,16]` | [AgreementRouting.forward](https://github.com/adambielski/CapsNet-pytorch/blob/bee0cbee5bb8b30399e75c751d3085c2f261dea3/net.py#L25) |

源码和排布的关键关系：源码的 b 是可学习 Parameter。循环前已有一次 softmax→加权求和→squash；3 次循环分别执行 agreement→b_batch更新→couplings→sum→squash，总计4次聚合。图是代表性循环模板；b_batch 更新对自身的状态依赖保存在 IR 的 b_next 端口，渲染器不画同节点自环，v 的下一轮回边仍可见。Repeat3 应理解为整个细化循环，不是只重复 softmax。

为什么这样对应：每个图元来自实际表达式、模块实例或明确的输入/状态边界；颜色表达算子/视觉角色，稳定 ID 与 `parameter_scope` / `instance_identity` 表达身份。两个同色 Linear 不能被推断成同一参数，两次读同一个输入也不能被改画成两个独立输入。展开层级只改变可见粒度。

## 关键源码事实与错误修正

- Unlike common textbook routing, source b is a learned Parameter initialized to zero and shared across batch. b_batch is per-forward state, not a new Parameter.
- Source performs an initial Softmax/sum/squash before the n_iterations loop; selected3 iterations therefore produce four aggregations, not three.
- Votes are retained and reused in every agreement and weighted sum; no detach occurs. b_batch and v are loop-carried state.
- Both F.softmax calls omit dim; loop reshapes to rows of output_caps, but runtime-dependent legacy dim behavior is preserved rather than silently repaired.
- squash divides by lengths with no epsilon in source; shape reasoning does not establish numerical behavior at zero length.

- 修正：Do not draw learned b as a fixed buffer, claim3 total passes, or invent independent parameters per routing round.
- 修正：Do not include CapsNet classifier/reconstruction in this module-only graph.

## 真实依赖和参数/状态身份

| 源 | 目标端口 | 角色 |
| --- | --- | --- |
| `capsule_routing.b:out` | `capsule_routing.initial.softmax:in` | `parameter_operand` |
| `capsule_routing.votes:out` | `capsule_routing.initial.sum:votes` | `retained_value` |
| `capsule_routing.initial.squash:out` | `capsule_routing.agreement:v_initial` | `initial_state` |
| `capsule_routing.b:out` | `capsule_routing.expand:in` | `parameter_operand` |
| `capsule_routing.votes:out` | `capsule_routing.agreement:votes` | `retained_value` |
| `capsule_routing.agreement:out` | `capsule_routing.update:agreement` | `tensor` |
| `capsule_routing.expand:out` | `capsule_routing.update:b_initial` | `initial_state` |
| `capsule_routing.update:out` | `capsule_routing.couplings.view:in` | `tensor` |
| `capsule_routing.couplings.restore:out` | `capsule_routing.sum:couplings` | `tensor` |
| `capsule_routing.votes:out` | `capsule_routing.sum:votes` | `retained_value` |
| `capsule_routing.sum:out` | `capsule_routing.squash:in` | `tensor` |
| `capsule_routing.squash:out` | `capsule_routing.agreement:v_next` | `loop_recurrence` |
| `capsule_routing.update:out` | `capsule_routing.update:b_next` | `loop_recurrence` |
| `capsule_routing.squash:out` | `capsule_routing.output:in` | `tensor` |

实线运送张量值；虚线区分参数、拓扑、形状和循环状态。参数与调用者提供的拓扑不被混入自动主链。回边表达下一轮状态，并不创建新算子或新参数实例。完整逐节点证据在生成结果的 `source_map.md`、`source_evidence.json` 与 `semantic_ir.json` 中。

## 自底向上的排布与紧凑路由

最底部输入行 → 模块算子区 → 最上方输出。内部 `graph.ranks` 也按自底向上排列；同一 rank 中各算子并列，不产生隐式加法、数据依赖或共享参数。嵌套 stage 只在第3粒度展开。

```python
# module_adapters/capsule_routing.py 的真实声明
from module_adapters.capsule_routing import build
model = build()
module = next(n for n in model["tree"]["items"] if n["id"].endswith(".module"))
print(module["ranks"])  # 由下至上；排布不自动创建语义边
print(model["extra_edges"])  # 真实输入、参数、拓扑、状态端口
```

外框/子模块的宽高先由文本行数、形状与嵌套内容测量，再分配位置。当前模块 graph 默认 rank gap72px、column gap64px，输入行 column gap48px；stage 内顺序 chain 的间隔24px。箭头使用显式侧端口和至少24px的起终端直线，折线避开叶节点、标题文本、其他张量线与边框，平行边框至少留8px。必要时参数、拓扑或保留张量从侧面接入；这是源码依赖决定的端口配合布局策略，而不是任意装饰线。

字体、饱和色、模块区分、浅色分组框和深色箭头复用 Transformer 风格。形状相同或颜色相同不表示计算相同；图元名与证据才是语义依据。

## 复用、生成与验证

合并中央注册表与 manifest 后可离线生成：

```bash
python generate.py --module capsule_routing --png
python checks/graph_extended.py
```

开发中尚未合并时可使用：

```bash
python staging/preview_module.py capsule_routing \
  --manifest staging/graph_source_manifest.json \
  --out /tmp/module-graph-preview
```

验证覆盖固定源文件散列、实际 AST 表达式/顺序、声明的 IR 节点字段与真实端口。负例会实际改变关键边的源端点、参数/算子身份、执行声称以及源码表达式，必须被拒绝。三图再做几何与 SVG/PNG 导出核验并人工查看。通过这些检查不等于数值执行验证，也不证明可以解析任意替换源码。
