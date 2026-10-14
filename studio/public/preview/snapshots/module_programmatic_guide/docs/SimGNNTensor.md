# SimGNN neural tensor comparison：源码对应与程序化布局

案例键：`simgnn_tensor`。这是 **模块子图**，不是完整任务模型。

边界：One source TenorNetworkModule on two graph representations; excludes AttentionModule, histogram and final similarity score head.

固定仓库：[benedekrozemberczki/SimGNN](https://github.com/benedekrozemberczki/SimGNN/tree/be3ee6193a7c286336260f6479a6aee8bdc56f8c)；commit `be3ee6193a7c286336260f6479a6aee8bdc56f8c`。

## 选定配置与证据强度

```json
{
  "filters_3": 8,
  "tensor_neurons": 4,
  "source_class": "TenorNetworkModule",
  "graph_vectors": "each[8,1]",
  "tensor_instance_shared_across_pairs": true,
  "output": "similarity feature vector, not scalar probability",
  "selected_configuration": "explicit static module profile; not a runtime observation",
  "model_executed": false,
  "artifact_scope": "module"
}
```

上面的宽度、迭代次数和形状是适配器明确选择的静态示例，不是模型执行观察。固定源码 SHA256 / Git blob SHA 在 `staging/graph_source_manifest.json`（合并后 `source_manifest.json`）中。只解析 AST 和绘图声明，未导入或运行上游模型、Notebook、torch、NumPy 或 SciPy。

## 源码 ↔ 图元

| 图元稳定 ID | 算子/范围 | 静态形状 | 源码定位 |
| --- | --- | --- | --- |
| `simgnn_tensor.e1` | Graph representation1 | `[8,1]` | [TenorNetworkModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L76) |
| `simgnn_tensor.e2` | Graph representation2 | `[8,1]` | [TenorNetworkModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L76) |
| `simgnn_tensor.tensorweight` | Owned bilinear tensor W | `[8,8,4]` | [TenorNetworkModule.setup_weights](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L56) |
| `simgnn_tensor.blockweight` | Distinct owned block weight | `[4,16]` | [TenorNetworkModule.setup_weights](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L56) |
| `simgnn_tensor.bias` | Owned comparison bias | `[4,1]` | [TenorNetworkModule.setup_weights](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L56) |
| `simgnn_tensor.bilinear.first` | e1.T @ W.view(8,-1) | `[1,32]` | [TenorNetworkModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L76) |
| `simgnn_tensor.bilinear.reshape` | View scoring as [8,4] | `[8,4]` | [TenorNetworkModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L76) |
| `simgnn_tensor.bilinear.second` | scoring.T @ e2 | `[4,1]` | [TenorNetworkModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L76) |
| `simgnn_tensor.concat` | Concat ordered graph columns | `[16,1]` | [TenorNetworkModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L76) |
| `simgnn_tensor.block` | W_block @ graph pair | `[4,1]` | [TenorNetworkModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L76) |
| `simgnn_tensor.add` | Bilinear + block score + bias | `[4,1]` | [TenorNetworkModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L76) |
| `simgnn_tensor.relu` | ReLU comparison features | `[4,1]` | [TenorNetworkModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L76) |
| `simgnn_tensor.output` | Selected module output | `[4,1]` | [TenorNetworkModule.forward](https://github.com/benedekrozemberczki/SimGNN/blob/be3ee6193a7c286336260f6479a6aee8bdc56f8c/src/layers.py#L76) |

源码和排布的关键关系：源码类名写作 TenorNetworkModule。W[8,8,4] 的 view 与两次 mm 实现有序图向量的双线性比较；另一支用独立 W_block 作用于 concatenated(e1,e2)。两支与 bias 相加再 ReLU，返回4个比较特征而不是单个相似度概率，也不能擅自假定交换两个图后对称。

为什么这样对应：每个图元来自实际表达式、模块实例或明确的输入/状态边界；颜色表达算子/视觉角色，稳定 ID 与 `parameter_scope` / `instance_identity` 表达身份。两个同色 Linear 不能被推断成同一参数，两次读同一个输入也不能被改画成两个独立输入。展开层级只改变可见粒度。

## 关键源码事实与错误修正

- Source class is misspelled TenorNetworkModule; stable source identity keeps that spelling while display label explains neural tensor comparison.
- Tensor weight[8,8,4] contracts ordered graph columns in two actual matrix products with an intermediate view[8,4]. A separate block weight[4,16] acts on concatenated graph vectors.
- Bilinear features, block features and owned bias add before ReLU. This module returns four features, not a similarity probability or scalar graph edit distance.

- 修正：Do not replace the source view/order with an unverified einsum, remove affine block path, or force symmetry under swapping graph inputs.

## 真实依赖和参数/状态身份

| 源 | 目标端口 | 角色 |
| --- | --- | --- |
| `simgnn_tensor.e1:out` | `simgnn_tensor.bilinear.first:embedding1` | `tensor` |
| `simgnn_tensor.tensorweight:out` | `simgnn_tensor.bilinear.first:tensor` | `parameter_operand` |
| `simgnn_tensor.e2:out` | `simgnn_tensor.bilinear.second:embedding2` | `tensor` |
| `simgnn_tensor.e1:out` | `simgnn_tensor.concat:first` | `retained_value` |
| `simgnn_tensor.e2:out` | `simgnn_tensor.concat:second` | `retained_value` |
| `simgnn_tensor.concat:out` | `simgnn_tensor.block:embedding_pair` | `tensor` |
| `simgnn_tensor.blockweight:out` | `simgnn_tensor.block:W_block` | `parameter_operand` |
| `simgnn_tensor.bilinear.second:out` | `simgnn_tensor.add:bilinear` | `tensor` |
| `simgnn_tensor.block:out` | `simgnn_tensor.add:affine` | `tensor` |
| `simgnn_tensor.bias:out` | `simgnn_tensor.add:bias` | `parameter_operand` |
| `simgnn_tensor.add:out` | `simgnn_tensor.relu:in` | `tensor` |
| `simgnn_tensor.relu:out` | `simgnn_tensor.output:in` | `tensor` |

实线运送张量值；虚线区分参数、拓扑、形状和循环状态。参数与调用者提供的拓扑不被混入自动主链。回边表达下一轮状态，并不创建新算子或新参数实例。完整逐节点证据在生成结果的 `source_map.md`、`source_evidence.json` 与 `semantic_ir.json` 中。

## 自底向上的排布与紧凑路由

最底部输入行 → 模块算子区 → 最上方输出。内部 `graph.ranks` 也按自底向上排列；同一 rank 中各算子并列，不产生隐式加法、数据依赖或共享参数。嵌套 stage 只在第3粒度展开。

```python
# module_adapters/simgnn_tensor.py 的真实声明
from module_adapters.simgnn_tensor import build
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
python generate.py --module simgnn_tensor --png
python checks/graph_extended.py
```

开发中尚未合并时可使用：

```bash
python staging/preview_module.py simgnn_tensor \
  --manifest staging/graph_source_manifest.json \
  --out /tmp/module-graph-preview
```

验证覆盖固定源文件散列、实际 AST 表达式/顺序、声明的 IR 节点字段与真实端口。负例会实际改变关键边的源端点、参数/算子身份、执行声称以及源码表达式，必须被拒绝。三图再做几何与 SVG/PNG 导出核验并人工查看。通过这些检查不等于数值执行验证，也不证明可以解析任意替换源码。
