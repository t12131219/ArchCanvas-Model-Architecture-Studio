# VGAE graph posterior sampling：源码对应与程序化布局

案例键：`vgae_posterior`。这是 **模块子图**，不是完整任务模型。

边界：Only VGAEModel.encoder posterior, not decoder/reconstruction/loss. GraphConv implementations kept explicitly opaque; exact constructor flags preserved.

固定仓库：[dmlc/dgl](https://github.com/dmlc/dgl/tree/3d16000b4170fa741ed9e9667f22ba84d3493026)；commit `3d16000b4170fa741ed9e9667f22ba84d3493026`。

## 选定配置与证据强度

```json
{
  "in_dim": 8,
  "hidden1_dim": 16,
  "hidden2_dim": 8,
  "shared_base": "layers.0",
  "independent_heads": [
    "layers.1",
    "layers.2"
  ],
  "distribution_quantity": "log_std",
  "always_samples": true,
  "eval_mean_shortcut": false,
  "device_origin": "from train import device",
  "graphconv_boundary": "opaque DGL library, not expanded",
  "allow_zero_in_degree": true,
  "selected_configuration": "explicit static module profile; not a runtime observation",
  "model_executed": false,
  "artifact_scope": "module"
}
```

上面的宽度、迭代次数和形状是适配器明确选择的静态示例，不是模型执行观察。固定源码 SHA256 / Git blob SHA 在 `staging/graph_source_manifest.json`（合并后 `source_manifest.json`）中。只解析 AST 和绘图声明，未导入或运行上游模型、Notebook、torch、NumPy 或 SciPy。

## 源码 ↔ 图元

| 图元稳定 ID | 算子/范围 | 静态形状 | 源码定位 |
| --- | --- | --- | --- |
| `vgae_posterior.features` | Node features | `[N,8]` | [VGAEModel.encoder](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/examples/pytorch/vgae/model.py#L38) |
| `vgae_posterior.g` | Supplied DGL graph | `N nodes / E edges` | [VGAEModel.encoder](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/examples/pytorch/vgae/model.py#L38) |
| `vgae_posterior.device` | Imported global device | `from train import device` | [__module__](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/examples/pytorch/vgae/model.py#L1) |
| `vgae_posterior.shared` | layers0 GraphConv8 -> 16 / ReLU | `[N,16]` | [VGAEModel.__init__](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/examples/pytorch/vgae/model.py#L10)；[VGAEModel.encoder](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/examples/pytorch/vgae/model.py#L38) |
| `vgae_posterior.mean` | layers1 GraphConv16 -> 8 / MEAN | `[N,8]` | [VGAEModel.__init__](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/examples/pytorch/vgae/model.py#L10)；[VGAEModel.encoder](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/examples/pytorch/vgae/model.py#L38) |
| `vgae_posterior.logstd` | layers2 GraphConv16 -> 8 / LOG STD | `[N,8]` | [VGAEModel.__init__](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/examples/pytorch/vgae/model.py#L10)；[VGAEModel.encoder](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/examples/pytorch/vgae/model.py#L38) |
| `vgae_posterior.noise` | Fresh Gaussian noise / to(device) | `[N,8]` | [VGAEModel.encoder](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/examples/pytorch/vgae/model.py#L38) |
| `vgae_posterior.exp` | exp(log_std) / to(device) | `[N,8]` | [VGAEModel.encoder](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/examples/pytorch/vgae/model.py#L38) |
| `vgae_posterior.multiply` | epsilon * standard deviation | `[N,8]` | [VGAEModel.encoder](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/examples/pytorch/vgae/model.py#L38) |
| `vgae_posterior.add` | mean + epsilon * std | `[N,8]` | [VGAEModel.encoder](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/examples/pytorch/vgae/model.py#L38) |
| `vgae_posterior.output` | Selected module output | `[N,8]` | [VGAEModel.encoder](https://github.com/dmlc/dgl/blob/3d16000b4170fa741ed9e9667f22ba84d3493026/examples/pytorch/vgae/model.py#L38) |

源码和排布的关键关系：layers0 是共同图特征底座，layers1 与 layers2 是不同参数的 mean/log_std 头。噪声的 N 只来自 features.shape，不读取特征值；σ=exp(log_std)，而不是 exp(log_var/2)。源码 eval 时也随机采样，且 device 来自 train 的全局导入。GraphConv 的实现没有在这张图中展开。

为什么这样对应：每个图元来自实际表达式、模块实例或明确的输入/状态边界；颜色表达算子/视觉角色，稳定 ID 与 `parameter_scope` / `instance_identity` 表达身份。两个同色 Linear 不能被推断成同一参数，两次读同一个输入也不能被改画成两个独立输入。展开层级只改变可见粒度。

## 关键源码事实与错误修正

- Three GraphConv instances are owned in ModuleList: one shared base and two independent posterior heads. Heads consume the SAME h and supplied graph, while weights are not shared.
- Source predicts log_std, so standard deviation is exp(log_std), with no log variance/2 operation.
- Fresh randn(N,hidden2_dim) occurs unconditionally even in eval mode; features supplies only the N shape to random generation. Global device comes from train import and is a runtime boundary.
- GraphConv implementation is deliberately not expanded in this example; glyphs state opaque DGL library, exact widths, activation and allow_zero_in_degree flags. No GCN formula or self-loop preprocessing is invented.

- 修正：Do not replace log_std with log_var, introduce an eval shortcut returning mean, or feed feature values into Gaussian noise.
- 修正：Do not include adjacency decoder in the posterior module; it has a separate inner_product_decoder adapter.

## 真实依赖和参数/状态身份

| 源 | 目标端口 | 角色 |
| --- | --- | --- |
| `vgae_posterior.features:out` | `vgae_posterior.shared:features` | `tensor` |
| `vgae_posterior.g:out` | `vgae_posterior.shared:graph` | `topology` |
| `vgae_posterior.shared:out` | `vgae_posterior.mean:h` | `tensor` |
| `vgae_posterior.shared:out` | `vgae_posterior.logstd:h` | `tensor` |
| `vgae_posterior.g:out` | `vgae_posterior.mean:graph` | `topology` |
| `vgae_posterior.g:out` | `vgae_posterior.logstd:graph` | `topology` |
| `vgae_posterior.logstd:out` | `vgae_posterior.exp:in` | `tensor` |
| `vgae_posterior.features:out` | `vgae_posterior.noise:N` | `shape_dependency` |
| `vgae_posterior.device:out` | `vgae_posterior.noise:device` | `control` |
| `vgae_posterior.device:out` | `vgae_posterior.exp:device` | `control` |
| `vgae_posterior.noise:out` | `vgae_posterior.multiply:epsilon` | `tensor` |
| `vgae_posterior.exp:out` | `vgae_posterior.multiply:std` | `tensor` |
| `vgae_posterior.mean:out` | `vgae_posterior.add:mean` | `tensor` |
| `vgae_posterior.multiply:out` | `vgae_posterior.add:scaled_noise` | `tensor` |
| `vgae_posterior.add:out` | `vgae_posterior.output:in` | `tensor` |

实线运送张量值；虚线区分参数、拓扑、形状和循环状态。参数与调用者提供的拓扑不被混入自动主链。回边表达下一轮状态，并不创建新算子或新参数实例。完整逐节点证据在生成结果的 `source_map.md`、`source_evidence.json` 与 `semantic_ir.json` 中。

## 自底向上的排布与紧凑路由

最底部输入行 → 模块算子区 → 最上方输出。内部 `graph.ranks` 也按自底向上排列；同一 rank 中各算子并列，不产生隐式加法、数据依赖或共享参数。嵌套 stage 只在第3粒度展开。

```python
# module_adapters/vgae_posterior.py 的真实声明
from module_adapters.vgae_posterior import build
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
python generate.py --module vgae_posterior --png
python checks/graph_extended.py
```

开发中尚未合并时可使用：

```bash
python staging/preview_module.py vgae_posterior \
  --manifest staging/graph_source_manifest.json \
  --out /tmp/module-graph-preview
```

验证覆盖固定源文件散列、实际 AST 表达式/顺序、声明的 IR 节点字段与真实端口。负例会实际改变关键边的源端点、参数/算子身份、执行声称以及源码表达式，必须被拒绝。三图再做几何与 SVG/PNG 导出核验并人工查看。通过这些检查不等于数值执行验证，也不证明可以解析任意替换源码。
