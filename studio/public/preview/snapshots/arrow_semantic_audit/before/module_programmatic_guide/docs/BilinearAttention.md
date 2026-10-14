# BAN bilinear attention：源码对应与程序化布局

案例键：`bilinear_attention`。这是 **模块子图**，不是完整任务模型。

边界：BiAttention.forward_all(v,q,v_mask=True,logit=False); low-rank BCNet h_out2<=32 branch; excludes VQA classifier/counter.

固定仓库：[jnhwkim/ban-vqa](https://github.com/jnhwkim/ban-vqa/tree/ef4cc36d63f6b31344301ac1bd91afd807d132e5)；commit `ef4cc36d63f6b31344301ac1bd91afd807d132e5`。

## 选定配置与证据强度

```json
{
  "x_dim": 8,
  "y_dim": 6,
  "z_dim": 4,
  "k": 3,
  "glimpse": 2,
  "V": 5,
  "Q": 3,
  "v_mask": true,
  "logit": false,
  "output_tuple": [
    "probabilities",
    "masked_logits"
  ],
  "norm": "joint V*Q per glimpse",
  "mode": "caller train/eval",
  "between_examples_weight_sharing": "not implied",
  "selected_configuration": "explicit static module profile; not a runtime observation",
  "model_executed": false,
  "artifact_scope": "module"
}
```

上面的宽度、迭代次数和形状是适配器明确选择的静态示例，不是模型执行观察。固定源码 SHA256 / Git blob SHA 在 `staging/graph_source_manifest.json`（合并后 `source_manifest.json`）中。只解析 AST 和绘图声明，未导入或运行上游模型、Notebook、torch、NumPy 或 SciPy。

## 源码 ↔ 图元

| 图元稳定 ID | 算子/范围 | 静态形状 | 源码定位 |
| --- | --- | --- | --- |
| `bilinear_attention.v` | Visual features V | `[B,5,8]` | [BiAttention.forward_all](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/attention.py#L31) |
| `bilinear_attention.q` | Language features Q | `[B,3,6]` | [BiAttention.forward_all](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/attention.py#L31) |
| `bilinear_attention.scoreparams` | Owned h_mat(g,v), h_bias | `h[1,2,1,12]; b[1,2,1,1]` | [BiAttention.__init__](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/attention.py#L16)；[BCNet.__init__](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/bc.py#L19) |
| `bilinear_attention.vproject.drop` | Dropout .2 | `[B,5,8]` | [FCNet.__init__](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L13)；[FCNet.forward](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L33) |
| `bilinear_attention.vproject.linear` | WeightNorm Linear 8 -> 12 | `[B,5,12]` | [FCNet.__init__](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L13) |
| `bilinear_attention.vproject.relu` | ReLU | `[B,5,12]` | [FCNet.__init__](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L13)；[FCNet.forward](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L33) |
| `bilinear_attention.vproject.extra` | Extra attention Dropout .5 | `[B,5,12]` | [BCNet.__init__](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/bc.py#L19)；[BCNet.forward](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/bc.py#L41) |
| `bilinear_attention.qproject.drop` | Dropout .2 | `[B,3,6]` | [FCNet.__init__](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L13)；[FCNet.forward](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L33) |
| `bilinear_attention.qproject.linear` | WeightNorm Linear 6 -> 12 | `[B,3,12]` | [FCNet.__init__](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L13) |
| `bilinear_attention.qproject.relu` | ReLU | `[B,3,12]` | [FCNet.__init__](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L13)；[FCNet.forward](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/fc.py#L33) |
| `bilinear_attention.score` | Low-rank bilinear scores + bias | `[B,2,5,3]` | [BCNet.forward](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/bc.py#L41) |
| `bilinear_attention.mask` | Mask zero visual rows / -inf | `[B,2,5,3]` | [BiAttention.forward_all](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/attention.py#L31) |
| `bilinear_attention.normalize.flat` | View V*Q positions | `[B,2,15]` | [BiAttention.forward_all](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/attention.py#L31) |
| `bilinear_attention.normalize.softmax` | Softmax dim=2 | `[B,2,15]` | [BiAttention.forward_all](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/attention.py#L31) |
| `bilinear_attention.normalize.view` | Restore V,Q axes | `[B,2,5,3]` | [BiAttention.forward_all](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/attention.py#L31) |
| `bilinear_attention.output` | Selected module output | `p, logits: 2 x [B,2,5,3]` | [BiAttention.forward_all](https://github.com/jnhwkim/ban-vqa/blob/ef4cc36d63f6b31344301ac1bd91afd807d132e5/attention.py#L31) |

源码和排布的关键关系：这份 BAN 不使用 Transformer 的 QKᵀ：两个模态各经独立 FCNet，视觉分支再加额外0.5 Dropout，随后 V、Q 与 weight_norm 重参数化的 h_mat 一起做三操作数 einsum，并加 h_bias。原始 V 的零行决定 mask，最后对每个 glimpse 的全部 V×Q 位置一起归一化。评分参数和原始V旁路因此需要独立箭头；v.size(1)、q.size(1) 还分别给 flatten 与 restore 提供真实形状依赖，不能仅把5、3作为无来源常量。

为什么这样对应：每个图元来自实际表达式、模块实例或明确的输入/状态边界；颜色表达算子/视觉角色，稳定 ID 与 `parameter_scope` / `instance_identity` 表达身份。两个同色 Linear 不能被推断成同一参数，两次读同一个输入也不能被改画成两个独立输入。展开层级只改变可见粒度。

## 关键源码事实与错误修正

- h_out2<=32 selects the real low-rank einsum branch with k3 factors. h_mat is weight_norm reparameterized by BiAttention; it is not a plain final Parameter named h_mat.
- FCNet includes Dropout.2 before WeightNorm Linear and ReLU; only the visual path gets the extra attention Dropout.5.
- Zero visual rows are detected from original v; source mutates logits.data with -inf, then Softmax normalizes flattened V*Q jointly for each glimpse.
- forward_all returns p and masked logits; logit=True alternate raw-only path is outside this selected profile.

- 修正：Do not substitute Transformer QK^T/sqrt(d): BAN uses a learned three-operand low-rank bilinear einsum.
- 修正：Do not normalize only over question tokens or mask zero question rows.
- 修正：Do not silently replace the source data mutation with a different autograd implementation.

## 真实依赖和参数/状态身份

| 源 | 目标端口 | 角色 |
| --- | --- | --- |
| `bilinear_attention.v:out` | `bilinear_attention.vproject.drop:in` | `tensor` |
| `bilinear_attention.q:out` | `bilinear_attention.qproject.drop:in` | `tensor` |
| `bilinear_attention.vproject.extra:out` | `bilinear_attention.score:V` | `tensor` |
| `bilinear_attention.qproject.relu:out` | `bilinear_attention.score:Q` | `tensor` |
| `bilinear_attention.score:out` | `bilinear_attention.mask:logits` | `tensor` |
| `bilinear_attention.v:out` | `bilinear_attention.mask:mask_input` | `retained_value` |
| `bilinear_attention.mask:out` | `bilinear_attention.normalize.flat:in` | `tensor` |
| `bilinear_attention.v:shape` | `bilinear_attention.normalize.flat:v_num` | `shape_dependency` |
| `bilinear_attention.q:shape` | `bilinear_attention.normalize.flat:q_num` | `shape_dependency` |
| `bilinear_attention.v:shape` | `bilinear_attention.normalize.view:v_num` | `shape_dependency` |
| `bilinear_attention.q:shape` | `bilinear_attention.normalize.view:q_num` | `shape_dependency` |
| `bilinear_attention.normalize.view:out` | `bilinear_attention.output:probabilities` | `tensor` |
| `bilinear_attention.mask:out` | `bilinear_attention.output:masked_logits` | `retained_value` |
| `bilinear_attention.scoreparams:h_mat` | `bilinear_attention.score:h_mat` | `parameter_operand` |
| `bilinear_attention.scoreparams:h_bias` | `bilinear_attention.score:h_bias` | `parameter_operand` |

实线运送张量值；虚线区分参数、拓扑、形状和循环状态。参数与调用者提供的拓扑不被混入自动主链。回边表达下一轮状态，并不创建新算子或新参数实例。完整逐节点证据在生成结果的 `source_map.md`、`source_evidence.json` 与 `semantic_ir.json` 中。

## 自底向上的排布与紧凑路由

最底部输入行 → 模块算子区 → 最上方输出。内部 `graph.ranks` 也按自底向上排列；同一 rank 中各算子并列，不产生隐式加法、数据依赖或共享参数。嵌套 stage 只在第3粒度展开。

```python
# module_adapters/bilinear_attention.py 的真实声明
from module_adapters.bilinear_attention import build
model = build()
module = next(n for n in model["tree"]["items"] if n["id"].endswith(".module"))
print(module["ranks"])  # 由下至上；排布不自动创建语义边
print(model["extra_edges"])  # 真实输入、参数、拓扑、状态端口
```

外框/子模块的宽高先由文本行数、形状与嵌套内容测量，再分配位置。当前模块 graph 默认 rank gap72px、column gap64px，输入行 column gap48px；stage 内顺序 chain 的间隔24px。箭头使用显式侧端口和至少24px的起终端直线，折线避开叶节点、标题文本、其他张量线与边框，平行边框至少留8px。必要时参数、拓扑或保留张量从侧面接入；这是源码依赖决定的端口配合布局策略，而不是任意装饰线。

布局边界：当前保留值旁路复用共享引擎的外侧通道，有些长线会绕过模块外框后返回目标；检查确认通道避开文字、节点和边框，但这不代表所有连线都在外框内部或已经取得全局最短路线。此轮保留已验证的通道规则，不修改共享引擎。形状依赖使用显式独立端口，并与张量值依赖区别。

字体、饱和色、模块区分、浅色分组框和深色箭头复用 Transformer 风格。形状相同或颜色相同不表示计算相同；图元名与证据才是语义依据。

## 复用、生成与验证

合并中央注册表与 manifest 后可离线生成：

```bash
python generate.py --module bilinear_attention --png
python checks/graph_extended.py
```

开发中尚未合并时可使用：

```bash
python staging/preview_module.py bilinear_attention \
  --manifest staging/graph_source_manifest.json \
  --out /tmp/module-graph-preview
```

验证覆盖固定源文件散列、实际 AST 表达式/顺序、声明的 IR 节点字段与真实端口。负例会实际改变关键边的源端点、参数/算子身份、执行声称以及源码表达式，必须被拒绝。三图再做几何与 SVG/PNG 导出核验并人工查看。通过这些检查不等于数值执行验证，也不证明可以解析任意替换源码。
