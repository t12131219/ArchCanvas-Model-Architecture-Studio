# Graph wavelet sparse layer：源码对应与程序化布局

案例键：`graphwavelet_sparse`。这是 **模块子图**，不是完整任务模型。

边界：One SparseGraphWaveletLayer only; supplied wavelet/inverse matrices, excludes wavelet construction, classifier and task network.

固定仓库：[benedekrozemberczki/GraphWaveletNeuralNetwork](https://github.com/benedekrozemberczki/GraphWaveletNeuralNetwork/tree/fbd93c8db066e03224f1bc66167985a56f1fe7aa)；commit `fbd93c8db066e03224f1bc66167985a56f1fe7aa`。

## 选定配置与证据强度

```json
{
  "in_channels": 8,
  "out_channels": 4,
  "ncount": "N",
  "input_sparse": true,
  "theta_learned": true,
  "diagonal_indices_buffer": false,
  "dropout": 0.5,
  "activation": "relu",
  "phi_preprocessing": "external",
  "library_kernels": "opaque torch_sparse spmm/spspmm",
  "selected_configuration": "explicit static module profile; not a runtime observation",
  "model_executed": false,
  "artifact_scope": "module"
}
```

上面的宽度、迭代次数和形状是适配器明确选择的静态示例，不是模型执行观察。固定源码 SHA256 / Git blob SHA 在 `staging/graph_source_manifest.json`（合并后 `source_manifest.json`）中。只解析 AST 和绘图声明，未导入或运行上游模型、Notebook、torch、NumPy 或 SciPy。

## 源码 ↔ 图元

| 图元稳定 ID | 算子/范围 | 静态形状 | 源码定位 |
| --- | --- | --- | --- |
| `graphwavelet_sparse.x` | Sparse X indices / values | `[N,8]` | [SparseGraphWaveletLayer.forward](https://github.com/benedekrozemberczki/GraphWaveletNeuralNetwork/blob/fbd93c8db066e03224f1bc66167985a56f1fe7aa/src/gwnn_layer.py#L45) |
| `graphwavelet_sparse.phi` | Supplied sparse wavelet Phi | `indices / values; [N,N]` | [SparseGraphWaveletLayer.forward](https://github.com/benedekrozemberczki/GraphWaveletNeuralNetwork/blob/fbd93c8db066e03224f1bc66167985a56f1fe7aa/src/gwnn_layer.py#L45) |
| `graphwavelet_sparse.inverse` | Supplied sparse inverse Phi | `indices / values; [N,N]` | [SparseGraphWaveletLayer.forward](https://github.com/benedekrozemberczki/GraphWaveletNeuralNetwork/blob/fbd93c8db066e03224f1bc66167985a56f1fe7aa/src/gwnn_layer.py#L45) |
| `graphwavelet_sparse.diagindices` | Fixed diagonal index Tensor | `[2,N]` | [GraphWaveletLayer.define_parameters](https://github.com/benedekrozemberczki/GraphWaveletNeuralNetwork/blob/fbd93c8db066e03224f1bc66167985a56f1fe7aa/src/gwnn_layer.py#L23) |
| `graphwavelet_sparse.theta` | Owned diagonal filter theta | `[N,1]` | [GraphWaveletLayer.define_parameters](https://github.com/benedekrozemberczki/GraphWaveletNeuralNetwork/blob/fbd93c8db066e03224f1bc66167985a56f1fe7aa/src/gwnn_layer.py#L23) |
| `graphwavelet_sparse.weight` | Owned feature projection W | `[8,4]` | [GraphWaveletLayer.define_parameters](https://github.com/benedekrozemberczki/GraphWaveletNeuralNetwork/blob/fbd93c8db066e03224f1bc66167985a56f1fe7aa/src/gwnn_layer.py#L23) |
| `graphwavelet_sparse.rescale` | Sparse Phi @ diag(theta) | `sparse pair [N,N]` | [SparseGraphWaveletLayer.forward](https://github.com/benedekrozemberczki/GraphWaveletNeuralNetwork/blob/fbd93c8db066e03224f1bc66167985a56f1fe7aa/src/gwnn_layer.py#L45) |
| `graphwavelet_sparse.project` | Sparse X @ W | `[N,4]` | [SparseGraphWaveletLayer.forward](https://github.com/benedekrozemberczki/GraphWaveletNeuralNetwork/blob/fbd93c8db066e03224f1bc66167985a56f1fe7aa/src/gwnn_layer.py#L45) |
| `graphwavelet_sparse.kernel` | Rescaled Phi @ Phi inverse | `sparse pair [N,N]` | [SparseGraphWaveletLayer.forward](https://github.com/benedekrozemberczki/GraphWaveletNeuralNetwork/blob/fbd93c8db066e03224f1bc66167985a56f1fe7aa/src/gwnn_layer.py#L45) |
| `graphwavelet_sparse.localize` | Learned wavelet kernel @ XW | `[N,4]` | [SparseGraphWaveletLayer.forward](https://github.com/benedekrozemberczki/GraphWaveletNeuralNetwork/blob/fbd93c8db066e03224f1bc66167985a56f1fe7aa/src/gwnn_layer.py#L45) |
| `graphwavelet_sparse.tail.relu` | ReLU localized features | `[N,4]` | [SparseGraphWaveletLayer.forward](https://github.com/benedekrozemberczki/GraphWaveletNeuralNetwork/blob/fbd93c8db066e03224f1bc66167985a56f1fe7aa/src/gwnn_layer.py#L45) |
| `graphwavelet_sparse.tail.drop` | Dropout .5 / caller mode | `[N,4]` | [SparseGraphWaveletLayer.forward](https://github.com/benedekrozemberczki/GraphWaveletNeuralNetwork/blob/fbd93c8db066e03224f1bc66167985a56f1fe7aa/src/gwnn_layer.py#L45) |
| `graphwavelet_sparse.output` | Selected module output | `[N,4]` | [SparseGraphWaveletLayer.forward](https://github.com/benedekrozemberczki/GraphWaveletNeuralNetwork/blob/fbd93c8db066e03224f1bc66167985a56f1fe7aa/src/gwnn_layer.py#L45) |

源码和排布的关键关系：图小波滤波显式先算 Phi·diag(theta)，再乘调用者提供的 Phi_inverse；另一方面做稀疏 XW，最后以新稀疏核作用于 XW，再 ReLU→Dropout。theta 与 W 是参数，diagonal_weight_indices 却只是普通 Tensor 属性，不能标成注册 buffer。这与已有特征域 SpectralFilter 是不同源码机制。

为什么这样对应：每个图元来自实际表达式、模块实例或明确的输入/状态边界；颜色表达算子/视觉角色，稳定 ID 与 `parameter_scope` / `instance_identity` 表达身份。两个同色 Linear 不能被推断成同一参数，两次读同一个输入也不能被改画成两个独立输入。展开层级只改变可见粒度。

## 关键源码事实与错误修正

- Source constructs Phi @ diag(theta) first, multiplies by supplied Phi_inverse second, then applies resulting sparse kernel to X@W. Parentheses, sparse representation and multiplication order remain explicit.
- theta[N,1] and W[8,4] are learned Parameters. Diagonal_weight_indices is an ordinary Tensor attribute moved to device, NOT registered_buffer and NOT Parameter.
- Supplied Phi/inverse preprocessing and torch_sparse kernels stay opaque. The diagram does not assert an orthogonal transform, compute a wavelet spectrum or run sparse products.
- Sparse forward applies ReLU then caller-mode Dropout after localization; Dense forward returns localization directly with no activation or Dropout.

- 修正：Do not equate this learned diagonal graph-wavelet filter with the existing eigenspace elementwise SpectralFilter.
- 修正：Do not register the fixed indices as a buffer absent in source or copy Sparse tail into Dense version.

## 真实依赖和参数/状态身份

| 源 | 目标端口 | 角色 |
| --- | --- | --- |
| `graphwavelet_sparse.phi:out` | `graphwavelet_sparse.rescale:phi` | `topology` |
| `graphwavelet_sparse.diagindices:out` | `graphwavelet_sparse.rescale:theta_indices` | `fixed_state` |
| `graphwavelet_sparse.theta:out` | `graphwavelet_sparse.rescale:theta_values` | `parameter_operand` |
| `graphwavelet_sparse.rescale:out` | `graphwavelet_sparse.kernel:rescaled_phi` | `tensor` |
| `graphwavelet_sparse.inverse:out` | `graphwavelet_sparse.kernel:phi_inverse` | `topology` |
| `graphwavelet_sparse.x:out` | `graphwavelet_sparse.project:X` | `tensor` |
| `graphwavelet_sparse.weight:out` | `graphwavelet_sparse.project:W` | `parameter_operand` |
| `graphwavelet_sparse.kernel:out` | `graphwavelet_sparse.localize:kernel` | `tensor` |
| `graphwavelet_sparse.project:out` | `graphwavelet_sparse.localize:features` | `tensor` |
| `graphwavelet_sparse.localize:out` | `graphwavelet_sparse.tail.relu:in` | `tensor` |
| `graphwavelet_sparse.tail.drop:out` | `graphwavelet_sparse.output:in` | `tensor` |

实线运送张量值；虚线区分参数、拓扑、形状和循环状态。参数与调用者提供的拓扑不被混入自动主链。回边表达下一轮状态，并不创建新算子或新参数实例。完整逐节点证据在生成结果的 `source_map.md`、`source_evidence.json` 与 `semantic_ir.json` 中。

## 自底向上的排布与紧凑路由

最底部输入行 → 模块算子区 → 最上方输出。内部 `graph.ranks` 也按自底向上排列；同一 rank 中各算子并列，不产生隐式加法、数据依赖或共享参数。嵌套 stage 只在第3粒度展开。

```python
# module_adapters/graphwavelet_sparse.py 的真实声明
from module_adapters.graphwavelet_sparse import build
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
python generate.py --module graphwavelet_sparse --png
python checks/graph_extended.py
```

开发中尚未合并时可使用：

```bash
python staging/preview_module.py graphwavelet_sparse \
  --manifest staging/graph_source_manifest.json \
  --out /tmp/module-graph-preview
```

验证覆盖固定源文件散列、实际 AST 表达式/顺序、声明的 IR 节点字段与真实端口。负例会实际改变关键边的源端点、参数/算子身份、执行声称以及源码表达式，必须被拒绝。三图再做几何与 SVG/PNG 导出核验并人工查看。通过这些检查不等于数值执行验证，也不证明可以解析任意替换源码。
