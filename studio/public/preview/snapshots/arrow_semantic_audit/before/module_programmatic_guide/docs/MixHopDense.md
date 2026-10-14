# MixHop dense power branch：源码对应与程序化布局

案例键：`mixhop_dense`。这是 **模块子图**，不是完整任务模型。

边界：One DenseNGCNLayer(12,4,iterations3,dropout.5); excludes multi-branch concatenation and classifier.

固定仓库：[benedekrozemberczki/MixHop-and-N-GCN](https://github.com/benedekrozemberczki/MixHop-and-N-GCN/tree/e9df5eb988f0dbe5192ac87902c55cbe6d8191fe)；commit `e9df5eb988f0dbe5192ac87902c55cbe6d8191fe`。

## 选定配置与证据强度

```json
{
  "in_channels": 12,
  "out_channels": 4,
  "iterations": 3,
  "adjacency_multiplications": 2,
  "dropout": 0.5,
  "activation": null,
  "bias_position": "after propagation",
  "selected_configuration": "explicit static module profile; not a runtime observation",
  "model_executed": false,
  "artifact_scope": "module"
}
```

上面的宽度、迭代次数和形状是适配器明确选择的静态示例，不是模型执行观察。固定源码 SHA256 / Git blob SHA 在 `staging/graph_source_manifest.json`（合并后 `source_manifest.json`）中。只解析 AST 和绘图声明，未导入或运行上游模型、Notebook、torch、NumPy 或 SciPy。

## 源码 ↔ 图元

| 图元稳定 ID | 算子/范围 | 静态形状 | 源码定位 |
| --- | --- | --- | --- |
| `mixhop_dense.x` | Dense node features | `[N,12]` | [DenseNGCNLayer.forward](https://github.com/benedekrozemberczki/MixHop-and-N-GCN/blob/e9df5eb988f0dbe5192ac87902c55cbe6d8191fe/src/layers.py#L106) |
| `mixhop_dense.adj` | Supplied normalized sparse A | `[N,N]` | [DenseNGCNLayer.forward](https://github.com/benedekrozemberczki/MixHop-and-N-GCN/blob/e9df5eb988f0dbe5192ac87902c55cbe6d8191fe/src/layers.py#L106) |
| `mixhop_dense.weight` | Owned dense W | `[12,4]` | [DenseNGCNLayer.define_parameters](https://github.com/benedekrozemberczki/MixHop-and-N-GCN/blob/e9df5eb988f0dbe5192ac87902c55cbe6d8191fe/src/layers.py#L92) |
| `mixhop_dense.bias` | Owned dense bias | `[1,4]` | [DenseNGCNLayer.define_parameters](https://github.com/benedekrozemberczki/MixHop-and-N-GCN/blob/e9df5eb988f0dbe5192ac87902c55cbe6d8191fe/src/layers.py#L92) |
| `mixhop_dense.project` | Dense X @ W | `[N,4]` | [DenseNGCNLayer.forward](https://github.com/benedekrozemberczki/MixHop-and-N-GCN/blob/e9df5eb988f0dbe5192ac87902c55cbe6d8191fe/src/layers.py#L106) |
| `mixhop_dense.drop` | Dropout .5 / caller mode | `[N,4]` | [DenseNGCNLayer.forward](https://github.com/benedekrozemberczki/MixHop-and-N-GCN/blob/e9df5eb988f0dbe5192ac87902c55cbe6d8191fe/src/layers.py#L106) |
| `mixhop_dense.prop0` | A @ features / pass1 | `[N,4]` | [DenseNGCNLayer.forward](https://github.com/benedekrozemberczki/MixHop-and-N-GCN/blob/e9df5eb988f0dbe5192ac87902c55cbe6d8191fe/src/layers.py#L106) |
| `mixhop_dense.prop1` | A @ features / pass2 | `[N,4]` | [DenseNGCNLayer.forward](https://github.com/benedekrozemberczki/MixHop-and-N-GCN/blob/e9df5eb988f0dbe5192ac87902c55cbe6d8191fe/src/layers.py#L106) |
| `mixhop_dense.biasadd` | Add bias AFTER propagation | `[N,4]` | [DenseNGCNLayer.forward](https://github.com/benedekrozemberczki/MixHop-and-N-GCN/blob/e9df5eb988f0dbe5192ac87902c55cbe6d8191fe/src/layers.py#L106) |
| `mixhop_dense.output` | Selected module output | `[N,4]` | [DenseNGCNLayer.forward](https://github.com/benedekrozemberczki/MixHop-and-N-GCN/blob/e9df5eb988f0dbe5192ac87902c55cbe6d8191fe/src/layers.py#L106) |

源码和排布的关键关系：DenseNGCN 与 SparseNGCN 的名字相近，顺序却不同：dense mm→Dropout→2次A传播→bias，且没有 ReLU。因此独立保留这个模块，而不是给前一案例换一个标签。iterations=3 在这里仍意味着2次邻接乘法。

为什么这样对应：每个图元来自实际表达式、模块实例或明确的输入/状态边界；颜色表达算子/视觉角色，稳定 ID 与 `parameter_scope` / `instance_identity` 表达身份。两个同色 Linear 不能被推断成同一参数，两次读同一个输入也不能被改画成两个独立输入。展开层级只改变可见粒度。

## 关键源码事实与错误修正

- DenseNGCN differs materially from SparseNGCN: dense mm, Dropout, iterations-1 adjacency products, THEN bias; no ReLU.
- iterations3 denotes two repeated uses of supplied adjacency, and the SAME node-feature weight is applied only once.
- Sparse multiplication remains an opaque torch_sparse library boundary; normalization is supplied externally.

- 修正：Do not merge sparse/dense NGNC branches merely because both names contain GCN.
- 修正：Do not move bias before propagation or add a missing ReLU.

## 真实依赖和参数/状态身份

| 源 | 目标端口 | 角色 |
| --- | --- | --- |
| `mixhop_dense.x:out` | `mixhop_dense.project:X` | `tensor` |
| `mixhop_dense.weight:out` | `mixhop_dense.project:W` | `parameter_operand` |
| `mixhop_dense.project:out` | `mixhop_dense.drop:in` | `tensor` |
| `mixhop_dense.drop:out` | `mixhop_dense.prop0:features` | `tensor` |
| `mixhop_dense.adj:out` | `mixhop_dense.prop0:A` | `topology` |
| `mixhop_dense.prop0:out` | `mixhop_dense.prop1:features` | `tensor` |
| `mixhop_dense.adj:out` | `mixhop_dense.prop1:A` | `topology` |
| `mixhop_dense.prop1:out` | `mixhop_dense.biasadd:features` | `tensor` |
| `mixhop_dense.bias:out` | `mixhop_dense.biasadd:bias` | `parameter_operand` |
| `mixhop_dense.biasadd:out` | `mixhop_dense.output:in` | `tensor` |

实线运送张量值；虚线区分参数、拓扑、形状和循环状态。参数与调用者提供的拓扑不被混入自动主链。回边表达下一轮状态，并不创建新算子或新参数实例。完整逐节点证据在生成结果的 `source_map.md`、`source_evidence.json` 与 `semantic_ir.json` 中。

## 自底向上的排布与紧凑路由

最底部输入行 → 模块算子区 → 最上方输出。内部 `graph.ranks` 也按自底向上排列；同一 rank 中各算子并列，不产生隐式加法、数据依赖或共享参数。嵌套 stage 只在第3粒度展开。

```python
# module_adapters/mixhop_dense.py 的真实声明
from module_adapters.mixhop_dense import build
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
python generate.py --module mixhop_dense --png
python checks/graph_extended.py
```

开发中尚未合并时可使用：

```bash
python staging/preview_module.py mixhop_dense \
  --manifest staging/graph_source_manifest.json \
  --out /tmp/module-graph-preview
```

验证覆盖固定源文件散列、实际 AST 表达式/顺序、声明的 IR 节点字段与真实端口。负例会实际改变关键边的源端点、参数/算子身份、执行声称以及源码表达式，必须被拒绝。三图再做几何与 SVG/PNG 导出核验并人工查看。通过这些检查不等于数值执行验证，也不证明可以解析任意替换源码。
