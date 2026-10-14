# Sparse GCN layer：源码对应与程序化布局

案例键：`sparse_gcn`。这是 **模块子图**，不是完整任务模型。

边界：One GraphConvolution(8,4,bias=True); excludes the GCN classifier and normalization preprocessing.

固定仓库：[tkipf/pygcn](https://github.com/tkipf/pygcn/tree/1600b5b748b3976413d1e307540ccc62605b4d6d)；commit `1600b5b748b3976413d1e307540ccc62605b4d6d`。

## 选定配置与证据强度

```json
{
  "in_features": 8,
  "out_features": 4,
  "bias": true,
  "adjacency_normalized_inside": false,
  "activation": null,
  "selected_configuration": "explicit static module profile; not a runtime observation",
  "model_executed": false,
  "artifact_scope": "module"
}
```

上面的宽度、迭代次数和形状是适配器明确选择的静态示例，不是模型执行观察。固定源码 SHA256 / Git blob SHA 在 `staging/graph_source_manifest.json`（合并后 `source_manifest.json`）中。只解析 AST 和绘图声明，未导入或运行上游模型、Notebook、torch、NumPy 或 SciPy。

## 源码 ↔ 图元

| 图元稳定 ID | 算子/范围 | 静态形状 | 源码定位 |
| --- | --- | --- | --- |
| `sparse_gcn.x` | Node features X | `[N,8]` | [GraphConvolution.forward](https://github.com/tkipf/pygcn/blob/1600b5b748b3976413d1e307540ccc62605b4d6d/pygcn/layers.py#L31) |
| `sparse_gcn.adj` | Supplied sparse adjacency | `[N,N]` | [GraphConvolution.forward](https://github.com/tkipf/pygcn/blob/1600b5b748b3976413d1e307540ccc62605b4d6d/pygcn/layers.py#L31) |
| `sparse_gcn.weight` | Owned weight W | `[8,4]` | [GraphConvolution.__init__](https://github.com/tkipf/pygcn/blob/1600b5b748b3976413d1e307540ccc62605b4d6d/pygcn/layers.py#L14) |
| `sparse_gcn.bias` | Owned bias b | `[4]` | [GraphConvolution.__init__](https://github.com/tkipf/pygcn/blob/1600b5b748b3976413d1e307540ccc62605b4d6d/pygcn/layers.py#L14) |
| `sparse_gcn.project.mm` | X @ W | `[N,4]` | [GraphConvolution.forward](https://github.com/tkipf/pygcn/blob/1600b5b748b3976413d1e307540ccc62605b4d6d/pygcn/layers.py#L31) |
| `sparse_gcn.aggregate.spmm` | A @ support | `[N,4]` | [GraphConvolution.forward](https://github.com/tkipf/pygcn/blob/1600b5b748b3976413d1e307540ccc62605b4d6d/pygcn/layers.py#L31) |
| `sparse_gcn.add` | Broadcast bias add | `[N,4]` | [GraphConvolution.forward](https://github.com/tkipf/pygcn/blob/1600b5b748b3976413d1e307540ccc62605b4d6d/pygcn/layers.py#L31) |
| `sparse_gcn.output` | Selected module output | `[N,4]` | [GraphConvolution.forward](https://github.com/tkipf/pygcn/blob/1600b5b748b3976413d1e307540ccc62605b4d6d/pygcn/layers.py#L31) |

源码和排布的关键关系：先按通道用共享的 W 做 XW，再由调用者提供的稀疏 A 汇聚节点，最后加 b。因此图上 Projection、Sparse neighbor sum、Add 三块按此顺序自底向上，A 必须单独接入第二块。层内部没有自环预处理、度归一化或 ReLU。

为什么这样对应：每个图元来自实际表达式、模块实例或明确的输入/状态边界；颜色表达算子/视觉角色，稳定 ID 与 `parameter_scope` / `instance_identity` 表达身份。两个同色 Linear 不能被推断成同一参数，两次读同一个输入也不能被改画成两个独立输入。展开层级只改变可见粒度。

## 关键源码事实与错误修正

- Source projects node features before sparse adjacency multiplication.
- Adjacency is supplied by caller; this layer does not add self-loops, compute degree normalization or apply ReLU.
- Weight[Nin,Nout] and bias[Nout] are owned Parameters; same weight is used for every node.

- 修正：Do not substitute the existing fixed GraphNet A@pixels: this layer has an actual learned node-feature projection.
- 修正：Do not add preprocessing or classifier layers from a textbook GCN.

## 真实依赖和参数/状态身份

| 源 | 目标端口 | 角色 |
| --- | --- | --- |
| `sparse_gcn.x:out` | `sparse_gcn.project.mm:X` | `tensor` |
| `sparse_gcn.weight:out` | `sparse_gcn.project.mm:W` | `parameter_operand` |
| `sparse_gcn.adj:out` | `sparse_gcn.aggregate.spmm:A` | `topology` |
| `sparse_gcn.project.mm:out` | `sparse_gcn.aggregate.spmm:support` | `tensor` |
| `sparse_gcn.aggregate.spmm:out` | `sparse_gcn.add:value` | `tensor` |
| `sparse_gcn.bias:out` | `sparse_gcn.add:bias` | `parameter_operand` |
| `sparse_gcn.add:out` | `sparse_gcn.output:in` | `tensor` |

实线运送张量值；虚线区分参数、拓扑、形状和循环状态。参数与调用者提供的拓扑不被混入自动主链。回边表达下一轮状态，并不创建新算子或新参数实例。完整逐节点证据在生成结果的 `source_map.md`、`source_evidence.json` 与 `semantic_ir.json` 中。

## 自底向上的排布与紧凑路由

最底部输入行 → 模块算子区 → 最上方输出。内部 `graph.ranks` 也按自底向上排列；同一 rank 中各算子并列，不产生隐式加法、数据依赖或共享参数。嵌套 stage 只在第3粒度展开。

```python
# module_adapters/sparse_gcn.py 的真实声明
from module_adapters.sparse_gcn import build
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
python generate.py --module sparse_gcn --png
python checks/graph_extended.py
```

开发中尚未合并时可使用：

```bash
python staging/preview_module.py sparse_gcn \
  --manifest staging/graph_source_manifest.json \
  --out /tmp/module-graph-preview
```

验证覆盖固定源文件散列、实际 AST 表达式/顺序、声明的 IR 节点字段与真实端口。负例会实际改变关键边的源端点、参数/算子身份、执行声称以及源码表达式，必须被拒绝。三图再做几何与 SVG/PNG 导出核验并人工查看。通过这些检查不等于数值执行验证，也不证明可以解析任意替换源码。
