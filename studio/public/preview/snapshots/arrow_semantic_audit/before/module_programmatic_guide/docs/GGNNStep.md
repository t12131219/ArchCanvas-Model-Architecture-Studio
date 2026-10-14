# GGNN typed-edge propagation step：源码对应与程序化布局

案例键：`ggnn_step`。这是 **模块子图**，不是完整任务模型。

边界：One repeatable GGNN propagation step + Propogator update; excludes annotations and self.out task readout.

固定仓库：[JamesChuanggg/ggnn.pytorch](https://github.com/JamesChuanggg/ggnn.pytorch/tree/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e)；commit `0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e`。

## 选定配置与证据强度

```json
{
  "n_node": 4,
  "state_dim": 8,
  "n_edge_types": 2,
  "n_steps": 3,
  "iteration_template": true,
  "gates": "reset/update; GRU-style interpolation",
  "readout_excluded": true,
  "selected_configuration": "explicit static module profile; not a runtime observation",
  "model_executed": false,
  "artifact_scope": "module"
}
```

上面的宽度、迭代次数和形状是适配器明确选择的静态示例，不是模型执行观察。固定源码 SHA256 / Git blob SHA 在 `staging/graph_source_manifest.json`（合并后 `source_manifest.json`）中。只解析 AST 和绘图声明，未导入或运行上游模型、Notebook、torch、NumPy 或 SciPy。

## 源码 ↔ 图元

| 图元稳定 ID | 算子/范围 | 静态形状 | 源码定位 |
| --- | --- | --- | --- |
| `ggnn_step.state` | Current node state H_t | `[B,4,8]` | [GGNN.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L106) |
| `ggnn_step.adj` | Directed typed adjacency A | `[B,4,16]` | [GGNN.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L106) |
| `ggnn_step.incoming.linear` | Two distinct Linear 8 -> 8 | `2 x [B,4,8]` | [GGNN.__init__](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L66)；[GGNN.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L106) |
| `ggnn_step.incoming.pack` | Stack / transpose / view T*N | `[B,8,8]` | [GGNN.__init__](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L66)；[GGNN.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L106) |
| `ggnn_step.outgoing.linear` | Two distinct Linear 8 -> 8 | `2 x [B,4,8]` | [GGNN.__init__](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L66)；[GGNN.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L106) |
| `ggnn_step.outgoing.pack` | Stack / transpose / view T*N | `[B,8,8]` | [GGNN.__init__](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L66)；[GGNN.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L106) |
| `ggnn_step.split` | Slice incoming / outgoing blocks | `2 x [B,4,8]` | [Propogator.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L42) |
| `ggnn_step.ain` | BMM A_in @ states | `[B,4,8]` | [Propogator.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L42) |
| `ggnn_step.aout` | BMM A_out @ states | `[B,4,8]` | [Propogator.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L42) |
| `ggnn_step.cat` | Concat messages + current state | `[B,4,24]` | [Propogator.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L42) |
| `ggnn_step.reset.linear` | Linear 24 -> 8 | `[B,4,8]` | [Propogator.__init__](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L23)；[Propogator.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L42) |
| `ggnn_step.reset.sigmoid` | Sigmoid | `[B,4,8]` | [Propogator.__init__](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L23)；[Propogator.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L42) |
| `ggnn_step.update.linear` | Linear 24 -> 8 | `[B,4,8]` | [Propogator.__init__](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L23)；[Propogator.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L42) |
| `ggnn_step.update.sigmoid` | Sigmoid | `[B,4,8]` | [Propogator.__init__](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L23)；[Propogator.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L42) |
| `ggnn_step.reset_state` | r * SAME current state | `[B,4,8]` | [Propogator.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L42) |
| `ggnn_step.joined` | Concat messages + reset state | `[B,4,24]` | [Propogator.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L42) |
| `ggnn_step.candidate.linear` | Linear 24 -> 8 | `[B,4,8]` | [Propogator.__init__](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L23)；[Propogator.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L42) |
| `ggnn_step.candidate.tanh` | Tanh candidate | `[B,4,8]` | [Propogator.__init__](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L23)；[Propogator.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L42) |
| `ggnn_step.blend` | GRU-style complementary blend | `[B,4,8]` | [Propogator.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L42) |
| `ggnn_step.output` | Selected module output | `[B,4,8]` | [Propogator.forward](https://github.com/JamesChuanggg/ggnn.pytorch/blob/0c7897fe9b05e9b4f9a963ff55bd3ad917ea734e/model.py#L42) |

源码和排布的关键关系：两类边分别拥有 in_0/in_1 与 out_0/out_1，先生成不同方向的消息，再用 A_in/A_out 汇聚。消息与当前 H 拼接产生 r、z；r 只乘原 H 后用于候选状态，而 z 控制 (1-z)H+z·candidate。所有时间步复用同一批参数，侧向回边只是状态传递。

为什么这样对应：每个图元来自实际表达式、模块实例或明确的输入/状态边界；颜色表达算子/视觉角色，稳定 ID 与 `parameter_scope` / `instance_identity` 表达身份。两个同色 Linear 不能被推断成同一参数，两次读同一个输入也不能被改画成两个独立输入。展开层级只改变可见粒度。

## 关键源码事实与错误修正

- Two edge types own distinct in_i and out_i Linear modules; all time steps reuse these same four modules and the same Propogator gates.
- Adjacency packs incoming and outgoing typed blocks. Separate BMMs form messages; source concatenates both messages and current state for two gates.
- Reset r acts on current state before candidate formation. Update formula is (1-z)*state_cur+z*h_hat, preserving the source gate convention.
- Class is misspelled Propogator and candidate member tansform in source; identities preserve those spellings.

- 修正：Do not replace actual gates with opaque nn.GRU or LSTM merely because the docstring says LSTM.
- 修正：Do not share in_i and out_i or give each time step fresh learned parameters.

## 真实依赖和参数/状态身份

| 源 | 目标端口 | 角色 |
| --- | --- | --- |
| `ggnn_step.state:out` | `ggnn_step.incoming.linear:in` | `tensor` |
| `ggnn_step.state:out` | `ggnn_step.outgoing.linear:in` | `tensor` |
| `ggnn_step.adj:out` | `ggnn_step.split:in` | `topology` |
| `ggnn_step.incoming.pack:out` | `ggnn_step.ain:states` | `tensor` |
| `ggnn_step.outgoing.pack:out` | `ggnn_step.aout:states` | `tensor` |
| `ggnn_step.split:A_in` | `ggnn_step.ain:A_in` | `topology` |
| `ggnn_step.split:A_out` | `ggnn_step.aout:A_out` | `topology` |
| `ggnn_step.ain:out` | `ggnn_step.cat:a_in` | `tensor` |
| `ggnn_step.aout:out` | `ggnn_step.cat:a_out` | `tensor` |
| `ggnn_step.state:out` | `ggnn_step.cat:current` | `retained_value` |
| `ggnn_step.cat:out` | `ggnn_step.reset.linear:in` | `tensor` |
| `ggnn_step.cat:out` | `ggnn_step.update.linear:in` | `tensor` |
| `ggnn_step.reset.sigmoid:out` | `ggnn_step.reset_state:r` | `tensor` |
| `ggnn_step.state:out` | `ggnn_step.reset_state:state` | `retained_value` |
| `ggnn_step.ain:out` | `ggnn_step.joined:a_in` | `retained_value` |
| `ggnn_step.aout:out` | `ggnn_step.joined:a_out` | `retained_value` |
| `ggnn_step.reset_state:out` | `ggnn_step.joined:reset_state` | `tensor` |
| `ggnn_step.joined:out` | `ggnn_step.candidate.linear:in` | `tensor` |
| `ggnn_step.update.sigmoid:out` | `ggnn_step.blend:z` | `retained_value` |
| `ggnn_step.state:out` | `ggnn_step.blend:state` | `retained_value` |
| `ggnn_step.candidate.tanh:out` | `ggnn_step.blend:candidate` | `tensor` |
| `ggnn_step.blend:out` | `ggnn_step.output:in` | `tensor` |
| `ggnn_step.blend:out` | `ggnn_step.state:next_iteration` | `loop_recurrence` |

实线运送张量值；虚线区分参数、拓扑、形状和循环状态。参数与调用者提供的拓扑不被混入自动主链。回边表达下一轮状态，并不创建新算子或新参数实例。完整逐节点证据在生成结果的 `source_map.md`、`source_evidence.json` 与 `semantic_ir.json` 中。

## 自底向上的排布与紧凑路由

最底部输入行 → 模块算子区 → 最上方输出。内部 `graph.ranks` 也按自底向上排列；同一 rank 中各算子并列，不产生隐式加法、数据依赖或共享参数。嵌套 stage 只在第3粒度展开。

```python
# module_adapters/ggnn_step.py 的真实声明
from module_adapters.ggnn_step import build
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
python generate.py --module ggnn_step --png
python checks/graph_extended.py
```

开发中尚未合并时可使用：

```bash
python staging/preview_module.py ggnn_step \
  --manifest staging/graph_source_manifest.json \
  --out /tmp/module-graph-preview
```

验证覆盖固定源文件散列、实际 AST 表达式/顺序、声明的 IR 节点字段与真实端口。负例会实际改变关键边的源端点、参数/算子身份、执行声称以及源码表达式，必须被拒绝。三图再做几何与 SVG/PNG 导出核验并人工查看。通过这些检查不等于数值执行验证，也不证明可以解析任意替换源码。
