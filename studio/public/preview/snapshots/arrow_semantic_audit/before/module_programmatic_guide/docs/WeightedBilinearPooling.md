# Weighted bilinear pooling：源码对应与程序化布局

案例键：`weighted_bilinear_pooling`。这是 **模块子图**，不是完整任务模型。

边界：Only BCNet.forward_with_weights(v,q,w), k3/h_dim4; excludes attention score generation and VQA task head.

固定仓库：[jnhwkim/ban-vqa](https://github.com/jnhwkim/ban-vqa/tree/ef4cc36d63f6b31344301ac1bd91afd807d132e5)；commit `ef4cc36d63f6b31344301ac1bd91afd807d132e5`。

## 选定配置与证据强度

```json
{
  "v_dim": 8,
  "q_dim": 6,
  "h_dim": 4,
  "k": 3,
  "h_out": null,
  "output_shape": [
    "B",
    4
  ],
  "pool": "AvgPool*k equals grouped sum",
  "attention_dropout_used": false,
  "selected_configuration": "explicit static module profile; not a runtime observation",
  "model_executed": false,
  "artifact_scope": "module"
}
```

上面的宽度、迭代次数和形状是适配器明确选择的静态示例，不是模型执行观察。固定源码 SHA256 / Git blob SHA 在 `staging/graph_source_manifest.json`（合并后 `source_manifest.json`）中。只解析 AST 和绘图声明，未导入或运行上游模型、Notebook、torch、NumPy 或 SciPy。

## 源码 ↔ 图元

| 图元稳定 ID | 算子/范围 | 静态形状 | 源码定位 |
| --- | --- | --- | --- |
| `weighted_bilinear_pooling.v` | Visual features V | `[B,5,8]` | [BCNet.forward_with_weights](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/bc.py#L64) |
| `weighted_bilinear_pooling.q` | Language features Q | `[B,3,6]` | [BCNet.forward_with_weights](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/bc.py#L64) |
| `weighted_bilinear_pooling.w` | External pair weights w | `[B,5,3]` | [BCNet.forward_with_weights](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/bc.py#L64) |
| `weighted_bilinear_pooling.vproject.drop` | Dropout .2 | `[B,5,8]` | [FCNet.__init__](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L13)；[FCNet.forward](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L33) |
| `weighted_bilinear_pooling.vproject.linear` | WeightNorm Linear 8 -> 12 | `[B,5,12]` | [FCNet.__init__](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L13) |
| `weighted_bilinear_pooling.vproject.relu` | ReLU | `[B,5,12]` | [FCNet.__init__](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L13)；[FCNet.forward](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L33) |
| `weighted_bilinear_pooling.qproject.drop` | Dropout .2 | `[B,3,6]` | [FCNet.__init__](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L13)；[FCNet.forward](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L33) |
| `weighted_bilinear_pooling.qproject.linear` | WeightNorm Linear 6 -> 12 | `[B,3,12]` | [FCNet.__init__](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L13) |
| `weighted_bilinear_pooling.qproject.relu` | ReLU | `[B,3,12]` | [FCNet.__init__](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L13)；[FCNet.forward](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L33) |
| `weighted_bilinear_pooling.einsum` | Weighted bilinear contraction | `[B,12]` | [BCNet.forward_with_weights](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/bc.py#L64) |
| `weighted_bilinear_pooling.pool.unsqueeze` | Insert pool channel axis | `[B,1,12]` | [BCNet.forward_with_weights](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/bc.py#L64) |
| `weighted_bilinear_pooling.pool.avg` | AvgPool1d k3 / stride3 | `[B,1,4]` | [BCNet.forward_with_weights](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/bc.py#L64) |
| `weighted_bilinear_pooling.pool.sum` | Squeeze + multiply by k | `[B,4]` | [BCNet.forward_with_weights](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/bc.py#L64) |
| `weighted_bilinear_pooling.output` | Selected module output | `[B,4]` | [BCNet.forward_with_weights](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/bc.py#L64) |

源码和排布的关键关系：外部 w 提供 V×Q 的成对权重，两个投影后的模态与 w 一起收缩，输出12个因子。AvgPool1d(3,stride3) 后乘3等价于求和，所以最后是4维 grouped sum，不能画成普通平均池化。此方法没有注意力评分分支特有的额外视觉 Dropout 或 h_mat。

为什么这样对应：每个图元来自实际表达式、模块实例或明确的输入/状态边界；颜色表达算子/视觉角色，稳定 ID 与 `parameter_scope` / `instance_identity` 表达身份。两个同色 Linear 不能被推断成同一参数，两次读同一个输入也不能被改画成两个独立输入。展开层级只改变可见粒度。

## 关键源码事实与错误修正

- Two FCNet projections are separate owned parameter families; external w is a two-axis pair weight input, not a learned module parameter.
- einsum contracts both visual and question positions; k3 feature factors then pool by AvgPool1d and multiplication by3, which implements sum-pooling.
- This method does not use BCNet.dropout(.5), h_mat or h_bias; attention-generation and pooling examples do not imply shared instances.

- 修正：Do not add Softmax, concatenate modalities, or insert the attention-only extra visual Dropout.5.
- 修正：Do not label the output as average pooling: source multiplies pooled values by k.

## 真实依赖和参数/状态身份

| 源 | 目标端口 | 角色 |
| --- | --- | --- |
| `weighted_bilinear_pooling.v:out` | `weighted_bilinear_pooling.vproject.drop:in` | `tensor` |
| `weighted_bilinear_pooling.q:out` | `weighted_bilinear_pooling.qproject.drop:in` | `tensor` |
| `weighted_bilinear_pooling.vproject.relu:out` | `weighted_bilinear_pooling.einsum:V` | `tensor` |
| `weighted_bilinear_pooling.qproject.relu:out` | `weighted_bilinear_pooling.einsum:Q` | `tensor` |
| `weighted_bilinear_pooling.w:out` | `weighted_bilinear_pooling.einsum:weights` | `tensor` |
| `weighted_bilinear_pooling.einsum:out` | `weighted_bilinear_pooling.pool.unsqueeze:in` | `tensor` |
| `weighted_bilinear_pooling.pool.sum:out` | `weighted_bilinear_pooling.output:in` | `tensor` |

实线运送张量值；虚线区分参数、拓扑、形状和循环状态。参数与调用者提供的拓扑不被混入自动主链。回边表达下一轮状态，并不创建新算子或新参数实例。完整逐节点证据在生成结果的 `source_map.md`、`source_evidence.json` 与 `semantic_ir.json` 中。

## 自底向上的排布与紧凑路由

最底部输入行 → 模块算子区 → 最上方输出。内部 `graph.ranks` 也按自底向上排列；同一 rank 中各算子并列，不产生隐式加法、数据依赖或共享参数。嵌套 stage 只在第3粒度展开。

```python
# module_adapters/weighted_bilinear_pooling.py 的真实声明
from module_adapters.weighted_bilinear_pooling import build
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
python generate.py --module weighted_bilinear_pooling --png
python checks/graph_extended.py
```

开发中尚未合并时可使用：

```bash
python staging/preview_module.py weighted_bilinear_pooling \
  --manifest staging/graph_source_manifest.json \
  --out /tmp/module-graph-preview
```

验证覆盖固定源文件散列、实际 AST 表达式/顺序、声明的 IR 节点字段与真实端口。负例会实际改变关键边的源端点、参数/算子身份、执行声称以及源码表达式，必须被拒绝。三图再做几何与 SVG/PNG 导出核验并人工查看。通过这些检查不等于数值执行验证，也不证明可以解析任意替换源码。
