# DGL multi-head graph attention：源码对应与程序化布局

案例键：`graph_attention`。这是 **模块子图**，不是完整任务模型。

边界：One homogeneous GATConv(8,4,heads2), graph.is_block=False, residual=False, edge_weight=None,activation=None,get_attention=False; library graph kernels opaque.

固定仓库：[dmlc/dgl](https://github.com/dmlc/dgl/tree/3d16000b4170fa741ed9e9667f22ba84d3493026)；commit `3d16000b4170fa741ed9e9667f22ba84d3493026`。

## 选定配置与证据强度

```json
{
  "in_feats": 8,
  "out_feats": 4,
  "num_heads": 2,
  "feat_drop": 0.1,
  "attn_drop": 0.2,
  "negative_slope": 0.2,
  "residual": false,
  "bias": true,
  "activation": null,
  "edge_weight": null,
  "get_attention": false,
  "homogeneous": true,
  "is_block": false,
  "allow_zero_in_degree": true,
  "head_axis_retained": true,
  "selected_configuration": "explicit static module profile; not a runtime observation",
  "model_executed": false,
  "artifact_scope": "module"
}
```

上面的宽度、迭代次数和形状是适配器明确选择的静态示例，不是模型执行观察。固定源码 SHA256 / Git blob SHA 在 `staging/graph_source_manifest.json`（合并后 `source_manifest.json`）中。只解析 AST 和绘图声明，未导入或运行上游模型、Notebook、torch、NumPy 或 SciPy。

## 源码 ↔ 图元

| 图元稳定 ID | 算子/范围 | 静态形状 | 源码定位 |
| --- | --- | --- | --- |
| `graph_attention.x` | Homogeneous node features | `[N,8]` | [GATConv.forward](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L239) |
| `graph_attention.g` | Supplied DGL graph topology | `N nodes / E edges` | [GATConv.forward](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L239) |
| `graph_attention.attention` | Distinct owned a_l and a_r | `each[1,2,4]` | [GATConv.__init__](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L135) |
| `graph_attention.bias` | Owned explicit bias | `[8]` | [GATConv.__init__](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L135) |
| `graph_attention.projection.drop` | Feature Dropout .1 | `[N,8]` | [GATConv.forward](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L239)；[GATConv.__init__](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L135) |
| `graph_attention.projection.linear` | Owned Linear8 -> 8 / no bias | `[N,8]` | [GATConv.forward](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L239)；[GATConv.__init__](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L135) |
| `graph_attention.projection.heads` | View head and feature axes | `[N,2,4]` | [GATConv.forward](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L239)；[GATConv.__init__](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L135) |
| `graph_attention.left` | Source contribution / a_l | `[N,2,1]` | [GATConv.forward](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L239) |
| `graph_attention.right` | Destination contribution / a_r | `[N,2,1]` | [GATConv.forward](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L239) |
| `graph_attention.score.add` | Gather el(src) + er(dst) | `[E,2,1]` | [GATConv.forward](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L239) |
| `graph_attention.score.leaky` | LeakyReLU slope .2 | `[E,2,1]` | [GATConv.forward](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L239) |
| `graph_attention.score.softmax` | Incoming-neighbor edge Softmax | `[E,2,1]` | [GATConv.forward](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L239) |
| `graph_attention.score.drop` | Attention Dropout .2 | `[E,2,1]` | [GATConv.forward](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L239) |
| `graph_attention.message` | Weighted source messages / SUM | `[N,2,4]` | [GATConv.forward](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L239) |
| `graph_attention.biasadd` | Broadcast bias / RETAIN heads | `[N,2,4]` | [GATConv.forward](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L239) |
| `graph_attention.output` | Selected module output | `[N,2,4]` | [GATConv.forward](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/python/dgl/nn/pytorch/conv/gatconv.py#L239) |

源码和排布的关键关系：同质图分支只做一次 feature Dropout 与一次共享 fc 投影；a_l、a_r 是不同参数。源码分别计算两个端点贡献后在实际边上相加，经过 LeakyReLU 与按目标节点入邻居归一化的 edge_softmax。graph 是 Softmax 与消息汇聚的真实拓扑操作数。输出保留 [N,heads,out_feats]，没有在本层自动拼接或平均 heads。

为什么这样对应：每个图元来自实际表达式、模块实例或明确的输入/状态边界；颜色表达算子/视觉角色，稳定 ID 与 `parameter_scope` / `instance_identity` 表达身份。两个同色 Linear 不能被推断成同一参数，两次读同一个输入也不能被改画成两个独立输入。展开层级只改变可见粒度。

## 关键源码事实与错误修正

- Homogeneous forward shares a single dropped feature tensor and single fc projection for source/destination nodes. Two attention vectors attn_l/attn_r remain independent owned Parameters.
- Implementation computes source and destination scalar contributions separately and ADDS them on edges before LeakyReLU; it does not materialize a concatenation or compute Transformer QK dot products.
- edge_softmax normalizes incoming neighbors for each destination/head, then attention Dropout and weighted-message sum follow. DGL graph kernels remain opaque boundaries.
- Selected residualFalse yields explicit bias[heads*out_feats]; no final activation, edge-weight multiplier, head mean/concat or attention tuple is introduced. Output retains [N,2,4].
- allow_zero_in_degree=True suppresses the source check; this module does not add self loops automatically.

- 修正：Do not draw a dense N*N attention matrix, reuse one vector for both endpoint contributions, or reduce the retained head axis.

## 真实依赖和参数/状态身份

| 源 | 目标端口 | 角色 |
| --- | --- | --- |
| `graph_attention.x:out` | `graph_attention.projection.drop:in` | `tensor` |
| `graph_attention.projection.heads:out` | `graph_attention.left:features` | `tensor` |
| `graph_attention.projection.heads:out` | `graph_attention.right:features` | `tensor` |
| `graph_attention.attention:a_l` | `graph_attention.left:a_l` | `parameter_operand` |
| `graph_attention.attention:a_r` | `graph_attention.right:a_r` | `parameter_operand` |
| `graph_attention.left:out` | `graph_attention.score.add:e_l` | `tensor` |
| `graph_attention.right:out` | `graph_attention.score.add:e_r` | `tensor` |
| `graph_attention.g:out` | `graph_attention.score.add:edge_pairs` | `topology` |
| `graph_attention.g:out` | `graph_attention.score.softmax:neighbors` | `topology` |
| `graph_attention.score.drop:out` | `graph_attention.message:a` | `tensor` |
| `graph_attention.projection.heads:out` | `graph_attention.message:ft` | `retained_value` |
| `graph_attention.g:out` | `graph_attention.message:neighbors` | `topology` |
| `graph_attention.message:out` | `graph_attention.biasadd:features` | `tensor` |
| `graph_attention.bias:out` | `graph_attention.biasadd:bias` | `parameter_operand` |
| `graph_attention.biasadd:out` | `graph_attention.output:in` | `tensor` |

实线运送张量值；虚线区分参数、拓扑、形状和循环状态。参数与调用者提供的拓扑不被混入自动主链。回边表达下一轮状态，并不创建新算子或新参数实例。完整逐节点证据在生成结果的 `source_map.md`、`source_evidence.json` 与 `semantic_ir.json` 中。

## 自底向上的排布与紧凑路由

最底部输入行 → 模块算子区 → 最上方输出。内部 `graph.ranks` 也按自底向上排列；同一 rank 中各算子并列，不产生隐式加法、数据依赖或共享参数。嵌套 stage 只在第3粒度展开。

```python
# module_adapters/graph_attention.py 的真实声明
from module_adapters.graph_attention import build
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
python generate.py --module graph_attention --png
python checks/graph_extended.py
```

开发中尚未合并时可使用：

```bash
python staging/preview_module.py graph_attention \
  --manifest staging/graph_source_manifest.json \
  --out /tmp/module-graph-preview
```

验证覆盖固定源文件散列、实际 AST 表达式/顺序、声明的 IR 节点字段与真实端口。负例会实际改变关键边的源端点、参数/算子身份、执行声称以及源码表达式，必须被拒绝。三图再做几何与 SVG/PNG 导出核验并人工查看。通过这些检查不等于数值执行验证，也不证明可以解析任意替换源码。
