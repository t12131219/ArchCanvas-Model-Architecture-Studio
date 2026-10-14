# SimGNN graph attention readout：源码对应与程序化布局

案例键：`simgnn_readout`。这是 **模块子图**，不是完整任务模型。

边界：One AttentionModule on node embeddings; excludes graph convolutions, histogram, tensor similarity network and task head.

固定仓库：[benedekrozemberczki/SimGNN](https://github.com/benedekrozemberczki/SimGNN/tree/be3ee6193a7c286336260f6479a6aee8bdc56f8c)；commit `be3ee6193a7c286336260f6479a6aee8bdc56f8c`。

## 选定配置与证据强度

```json
{
  "filters_3": 8,
  "node_count": "N",
  "global_reduction": "mean nodes",
  "attention_normalizer": "sigmoid, not Softmax",
  "weighted_readout": "sum, not normalized mean",
  "output_orientation": "[8,1]",
  "selected_configuration": "explicit static module profile; not a runtime observation",
  "model_executed": false,
  "artifact_scope": "module"
}
```

上面的宽度、迭代次数和形状是适配器明确选择的静态示例，不是模型执行观察。固定源码 SHA256 / Git blob SHA 在 `staging/graph_source_manifest.json`（合并后 `source_manifest.json`）中。只解析 AST 和绘图声明，未导入或运行上游模型、Notebook、torch、NumPy 或 SciPy。

## 源码 ↔ 图元

| 图元稳定 ID | 算子/范围 | 静态形状 | 源码定位 |
| --- | --- | --- | --- |
| `simgnn_readout.embedding` | Retained node embeddings X | `[N,8]` | [AttentionModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L31) |
| `simgnn_readout.weight` | Owned context weight W | `[8,8]` | [AttentionModule.setup_weights](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L18) |
| `simgnn_readout.context.mm` | Node embeddings @ W | `[N,8]` | [AttentionModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L31) |
| `simgnn_readout.context.mean` | Mean over nodes / dim0 | `[8]` | [AttentionModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L31) |
| `simgnn_readout.context.tanh` | Tanh global context | `[8]` | [AttentionModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L31) |
| `simgnn_readout.context.view` | View column context | `[8,1]` | [AttentionModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L31) |
| `simgnn_readout.score.mm` | SAME X @ context | `[N,1]` | [AttentionModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L31) |
| `simgnn_readout.score.sigmoid` | Sigmoid / NOT Softmax | `[N,1]` | [AttentionModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L31) |
| `simgnn_readout.transpose` | Transpose SAME node embeddings | `[8,N]` | [AttentionModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L31) |
| `simgnn_readout.readout` | X.T @ sigmoid node weights | `[8,1]` | [AttentionModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L31) |
| `simgnn_readout.output` | Selected module output | `[8,1]` | [AttentionModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L31) |

源码和排布的关键关系：节点嵌入先经 W 并沿节点均值得到 global context，经过 Tanh 后，由原始嵌入计算独立 Sigmoid 权重。最终仍用原 Xᵀ 做加权求和。这不是归一化的 Softmax attention，也不是 GAT 的边注意力；三个原X用途各有真实依赖。

为什么这样对应：每个图元来自实际表达式、模块实例或明确的输入/状态边界；颜色表达算子/视觉角色，稳定 ID 与 `parameter_scope` / `instance_identity` 表达身份。两个同色 Linear 不能被推断成同一参数，两次读同一个输入也不能被改画成两个独立输入。展开层级只改变可见粒度。

## 关键源码事实与错误修正

- One W[8,8] creates a mean projected global context, then Tanh. The ORIGINAL node embeddings independently compute sigmoid gates against this context.
- Final representation is X.T @ sigmoid_scores, a weighted SUM. Sigmoid gates neither sum to one nor become Softmax attention.
- The SAME original embedding appears in context projection, node scoring and final readout; the output is a column [8,1].

- 修正：Do not substitute graph GAT incoming edge Softmax, dot-product sequence attention or normalize the weighted readout.

## 真实依赖和参数/状态身份

| 源 | 目标端口 | 角色 |
| --- | --- | --- |
| `simgnn_readout.embedding:out` | `simgnn_readout.context.mm:X` | `tensor` |
| `simgnn_readout.weight:out` | `simgnn_readout.context.mm:W` | `parameter_operand` |
| `simgnn_readout.embedding:out` | `simgnn_readout.score.mm:X` | `retained_value` |
| `simgnn_readout.context.view:out` | `simgnn_readout.score.mm:context` | `tensor` |
| `simgnn_readout.embedding:out` | `simgnn_readout.transpose:X` | `retained_value` |
| `simgnn_readout.transpose:out` | `simgnn_readout.readout:X_transpose` | `tensor` |
| `simgnn_readout.score.sigmoid:out` | `simgnn_readout.readout:node_weights` | `tensor` |
| `simgnn_readout.readout:out` | `simgnn_readout.output:in` | `tensor` |

实线运送张量值；虚线区分参数、拓扑、形状和循环状态。参数与调用者提供的拓扑不被混入自动主链。回边表达下一轮状态，并不创建新算子或新参数实例。完整逐节点证据在生成结果的 `source_map.md`、`source_evidence.json` 与 `semantic_ir.json` 中。

## 自底向上的排布与紧凑路由

最底部输入行 → 模块算子区 → 最上方输出。内部 `graph.ranks` 也按自底向上排列；同一 rank 中各算子并列，不产生隐式加法、数据依赖或共享参数。嵌套 stage 只在第3粒度展开。

```python
# module_adapters/simgnn_readout.py 的真实声明
from module_adapters.simgnn_readout import build
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
python generate.py --module simgnn_readout --png
python checks/graph_extended.py
```

开发中尚未合并时可使用：

```bash
python staging/preview_module.py simgnn_readout \
  --manifest staging/graph_source_manifest.json \
  --out /tmp/module-graph-preview
```

验证覆盖固定源文件散列、实际 AST 表达式/顺序、声明的 IR 节点字段与真实端口。负例会实际改变关键边的源端点、参数/算子身份、执行声称以及源码表达式，必须被拒绝。三图再做几何与 SVG/PNG 导出核验并人工查看。通过这些检查不等于数值执行验证，也不证明可以解析任意替换源码。
