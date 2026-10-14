# GraphSAGE sampled mean：源码对应与程序化布局

案例键：`graphsage_mean`。这是 **模块子图**，不是完整任务模型。

边界：One Encoder with MeanAggregator, gcn=False, cuda=False, num_sample10; excludes classifier and multi-layer task network.

固定仓库：[williamleif/graphsage-simple](https://github.com/williamleif/graphsage-simple/tree/d3105e5223e9602ba3ef2dd27e343d044fe4bb5f)；commit `d3105e5223e9602ba3ef2dd27e343d044fe4bb5f`。

## 选定配置与证据强度

```json
{
  "feature_dim": 8,
  "embed_dim": 4,
  "num_sample": 10,
  "gcn": false,
  "cuda": false,
  "output_orientation": "[embed_dim,M]",
  "nonempty_neighbors_assumed": true,
  "feature_callable_shared": true,
  "selected_configuration": "explicit static module profile; not a runtime observation",
  "model_executed": false,
  "artifact_scope": "module"
}
```

上面的宽度、迭代次数和形状是适配器明确选择的静态示例，不是模型执行观察。固定源码 SHA256 / Git blob SHA 在 `staging/graph_source_manifest.json`（合并后 `source_manifest.json`）中。只解析 AST 和绘图声明，未导入或运行上游模型、Notebook、torch、NumPy 或 SciPy。

## 源码 ↔ 图元

| 图元稳定 ID | 算子/范围 | 静态形状 | 源码定位 |
| --- | --- | --- | --- |
| `graphsage_mean.nodes` | Queried node IDs | `[M]` | [Encoder.forward](https://github.com/williamleif/graphsage-simple/blob/d3105e5223e9602ba3ef2dd27e343d044fe4bb5f/graphsage/encoders.py#L33) |
| `graphsage_mean.adj` | Supplied adjacency lists | `neighbor sets` | [Encoder.forward](https://github.com/williamleif/graphsage-simple/blob/d3105e5223e9602ba3ef2dd27e343d044fe4bb5f/graphsage/encoders.py#L33) |
| `graphsage_mean.features` | Shared feature callable | `IDs -> [count,8]` | [Encoder.forward](https://github.com/williamleif/graphsage-simple/blob/d3105e5223e9602ba3ef2dd27e343d044fe4bb5f/graphsage/encoders.py#L33) |
| `graphsage_mean.weight` | Owned Encoder weight | `[4,16]` | [Encoder.__init__](https://github.com/williamleif/graphsage-simple/blob/d3105e5223e9602ba3ef2dd27e343d044fe4bb5f/graphsage/encoders.py#L10) |
| `graphsage_mean.neighbors` | Read queried neighbor sets | `M sets` | [Encoder.forward](https://github.com/williamleif/graphsage-simple/blob/d3105e5223e9602ba3ef2dd27e343d044fe4bb5f/graphsage/encoders.py#L33) |
| `graphsage_mean.sample` | Sample up to10 neighbors | `M sampled sets` | [MeanAggregator.forward](https://github.com/williamleif/graphsage-simple/blob/d3105e5223e9602ba3ef2dd27e343d044fe4bb5f/graphsage/aggregators.py#L30) |
| `graphsage_mean.unique` | Union / unique node IDs | `[U]` | [MeanAggregator.forward](https://github.com/williamleif/graphsage-simple/blob/d3105e5223e9602ba3ef2dd27e343d044fe4bb5f/graphsage/aggregators.py#L30) |
| `graphsage_mean.mask` | Binary membership / row divide | `[M,U]` | [MeanAggregator.forward](https://github.com/williamleif/graphsage-simple/blob/d3105e5223e9602ba3ef2dd27e343d044fe4bb5f/graphsage/aggregators.py#L30) |
| `graphsage_mean.lookup` | Query features(unique IDs) | `[U,8]` | [MeanAggregator.forward](https://github.com/williamleif/graphsage-simple/blob/d3105e5223e9602ba3ef2dd27e343d044fe4bb5f/graphsage/aggregators.py#L30) |
| `graphsage_mean.selflookup` | Query SAME features(nodes) | `[M,8]` | [Encoder.forward](https://github.com/williamleif/graphsage-simple/blob/d3105e5223e9602ba3ef2dd27e343d044fe4bb5f/graphsage/encoders.py#L33) |
| `graphsage_mean.mean` | mask @ neighbor embeddings | `[M,8]` | [MeanAggregator.forward](https://github.com/williamleif/graphsage-simple/blob/d3105e5223e9602ba3ef2dd27e343d044fe4bb5f/graphsage/aggregators.py#L30) |
| `graphsage_mean.concat` | Concat SELF then NEIGHBOR | `[M,16]` | [Encoder.forward](https://github.com/williamleif/graphsage-simple/blob/d3105e5223e9602ba3ef2dd27e343d044fe4bb5f/graphsage/encoders.py#L33) |
| `graphsage_mean.project.transpose` | Transpose combined | `[16,M]` | [Encoder.forward](https://github.com/williamleif/graphsage-simple/blob/d3105e5223e9602ba3ef2dd27e343d044fe4bb5f/graphsage/encoders.py#L33) |
| `graphsage_mean.project.mm` | W @ combined transpose | `[4,M]` | [Encoder.forward](https://github.com/williamleif/graphsage-simple/blob/d3105e5223e9602ba3ef2dd27e343d044fe4bb5f/graphsage/encoders.py#L33) |
| `graphsage_mean.project.relu` | ReLU / retain [embed_dim,M] | `[4,M]` | [Encoder.forward](https://github.com/williamleif/graphsage-simple/blob/d3105e5223e9602ba3ef2dd27e343d044fe4bb5f/graphsage/encoders.py#L33) |
| `graphsage_mean.output` | Selected module output | `[4,M]` | [Encoder.forward](https://github.com/williamleif/graphsage-simple/blob/d3105e5223e9602ba3ef2dd27e343d044fe4bb5f/graphsage/encoders.py#L33) |

源码和排布的关键关系：查询节点先取邻居集合并最多随机采样10个，生成去重邻居列和按行计数归一化的 membership mask。邻居与自身特征查询调用同一个外部 features callable。最后按 self→neighbor 拼接，再做 W·combinedᵀ 和 ReLU，因此输出确实是 [4,M]，图中保留这个节点轴方向。

为什么这样对应：每个图元来自实际表达式、模块实例或明确的输入/状态边界；颜色表达算子/视觉角色，稳定 ID 与 `parameter_scope` / `instance_identity` 表达身份。两个同色 Linear 不能被推断成同一参数，两次读同一个输入也不能被改画成两个独立输入。展开层级只改变可见粒度。

## 关键源码事实与错误修正

- Neighbor sampling, membership-mask normalization and matrix multiplication are source operations; a textbook abstract mean glyph alone would hide these steps.
- Both self and neighbor lookups call the SAME externally supplied features callable. Its parameter ownership is unknown at this module boundary.
- Encoder owns weight[4,16], with no bias, and multiplies W by combined.t(); output is [4,M], not [M,4].
- Selected gcn=False bypasses the source gcn=True set-addition branch. Nonempty neighborhoods are assumed for static shape discussion; division has no epsilon.
- Frozen repository has no license file; README is retained and no license is invented.

- 修正：Do not include queried node itself in sampled neighbors under the selected gcn=False branch.
- 修正：Do not infer separate learned embedding tables from the two lookup glyphs or silently transpose the returned output.

## 真实依赖和参数/状态身份

| 源 | 目标端口 | 角色 |
| --- | --- | --- |
| `graphsage_mean.nodes:out` | `graphsage_mean.neighbors:nodes` | `tensor` |
| `graphsage_mean.adj:out` | `graphsage_mean.neighbors:adj_lists` | `topology` |
| `graphsage_mean.neighbors:out` | `graphsage_mean.sample:neighbor_sets` | `topology` |
| `graphsage_mean.sample:out` | `graphsage_mean.unique:sets` | `topology` |
| `graphsage_mean.sample:out` | `graphsage_mean.mask:membership` | `topology` |
| `graphsage_mean.unique:out` | `graphsage_mean.mask:columns` | `topology` |
| `graphsage_mean.unique:out` | `graphsage_mean.lookup:ids` | `tensor` |
| `graphsage_mean.features:out` | `graphsage_mean.lookup:callable` | `callable` |
| `graphsage_mean.mask:out` | `graphsage_mean.mean:mask` | `tensor` |
| `graphsage_mean.lookup:out` | `graphsage_mean.mean:embeddings` | `tensor` |
| `graphsage_mean.nodes:out` | `graphsage_mean.selflookup:ids` | `tensor` |
| `graphsage_mean.features:out` | `graphsage_mean.selflookup:callable` | `callable` |
| `graphsage_mean.selflookup:out` | `graphsage_mean.concat:self` | `tensor` |
| `graphsage_mean.mean:out` | `graphsage_mean.concat:neighbors` | `tensor` |
| `graphsage_mean.concat:out` | `graphsage_mean.project.transpose:in` | `tensor` |
| `graphsage_mean.weight:out` | `graphsage_mean.project.mm:W` | `parameter_operand` |
| `graphsage_mean.project.relu:out` | `graphsage_mean.output:in` | `tensor` |

实线运送张量值；虚线区分参数、拓扑、形状和循环状态。参数与调用者提供的拓扑不被混入自动主链。回边表达下一轮状态，并不创建新算子或新参数实例。完整逐节点证据在生成结果的 `source_map.md`、`source_evidence.json` 与 `semantic_ir.json` 中。

## 自底向上的排布与紧凑路由

最底部输入行 → 模块算子区 → 最上方输出。内部 `graph.ranks` 也按自底向上排列；同一 rank 中各算子并列，不产生隐式加法、数据依赖或共享参数。嵌套 stage 只在第3粒度展开。

```python
# module_adapters/graphsage_mean.py 的真实声明
from module_adapters.graphsage_mean import build
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
python generate.py --module graphsage_mean --png
python checks/graph_extended.py
```

开发中尚未合并时可使用：

```bash
python staging/preview_module.py graphsage_mean \
  --manifest staging/graph_source_manifest.json \
  --out /tmp/module-graph-preview
```

验证覆盖固定源文件散列、实际 AST 表达式/顺序、声明的 IR 节点字段与真实端口。负例会实际改变关键边的源端点、参数/算子身份、执行声称以及源码表达式，必须被拒绝。三图再做几何与 SVG/PNG 导出核验并人工查看。通过这些检查不等于数值执行验证，也不证明可以解析任意替换源码。
