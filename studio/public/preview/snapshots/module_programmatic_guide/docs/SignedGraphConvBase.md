# Signed graph first-layer convolution：源码对应与程序化布局

案例键：`signed_graphconv_base`。这是 **模块子图**，不是完整任务模型。

边界：One Base signed layer on one edge set, norm=True,norm_embed=True,bias=True; excludes paired task-network outputs.

固定仓库：[benedekrozemberczki/SGCN](https://github.com/benedekrozemberczki/SGCN/tree/c01e930c02968ea5b0eb72f1fe93eaab99e46eea)；commit `c01e930c02968ea5b0eb72f1fe93eaab99e46eea`。

## 选定配置与证据强度

```json
{
  "feature_dim": 8,
  "in_channels": 16,
  "out_channels": 4,
  "norm": true,
  "norm_embed": true,
  "bias": true,
  "self_loops": "remove only",
  "add_self_loops": false,
  "selected_configuration": "explicit static module profile; not a runtime observation",
  "model_executed": false,
  "artifact_scope": "module"
}
```

上面的宽度、迭代次数和形状是适配器明确选择的静态示例，不是模型执行观察。固定源码 SHA256 / Git blob SHA 在 `staging/graph_source_manifest.json`（合并后 `source_manifest.json`）中。只解析 AST 和绘图声明，未导入或运行上游模型、Notebook、torch、NumPy 或 SciPy。

## 源码 ↔ 图元

| 图元稳定 ID | 算子/范围 | 静态形状 | 源码定位 |
| --- | --- | --- | --- |
| `signed_graphconv_base.x` | Node features x | `[N,8]` | [SignedSAGEConvolutionBase.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L104) |
| `signed_graphconv_base.edges` | Supplied single edge set | `[2,E]` | [SignedSAGEConvolutionBase.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L104) |
| `signed_graphconv_base.weight` | Owned weight W | `[16,4]` | [SignedSAGEConvolution.__init__](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L65) |
| `signed_graphconv_base.bias` | Owned bias b | `[4]` | [SignedSAGEConvolution.__init__](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L65) |
| `signed_graphconv_base.remove` | REMOVE self loops only | `[2,E_without_self]` | [SignedSAGEConvolutionBase.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L104) |
| `signed_graphconv_base.mean` | Mean of neighbors without self | `[N,8]` | [SignedSAGEConvolutionBase.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L104) |
| `signed_graphconv_base.concat` | Concat NEIGHBOR then SELF | `[N,16]` | [SignedSAGEConvolutionBase.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L104) |
| `signed_graphconv_base.project` | Concatenated features @ W | `[N,4]` | [SignedSAGEConvolutionBase.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L104) |
| `signed_graphconv_base.biasadd` | Add owned bias | `[N,4]` | [SignedSAGEConvolutionBase.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L104) |
| `signed_graphconv_base.normalize` | L2 normalize each node | `[N,4]` | [SignedSAGEConvolutionBase.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L104) |
| `signed_graphconv_base.output` | Selected module output | `[N,4]` | [SignedSAGEConvolutionBase.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L104) |

源码和排布的关键关系：Base 第一层只有一个 x 与一套边，而且只删除自环。邻居 mean 与原 x 按 neighbor→self 拼接后做 W、bias、L2 normalize。Deep 的双状态、双自环添加策略不能套到 Base，否则边语义与输入宽度都会改变。

为什么这样对应：每个图元来自实际表达式、模块实例或明确的输入/状态边界；颜色表达算子/视觉角色，稳定 ID 与 `parameter_scope` / `instance_identity` 表达身份。两个同色 Linear 不能被推断成同一参数，两次读同一个输入也不能被改画成两个独立输入。展开层级只改变可见粒度。

## 关键源码事实与错误修正

- Base layer removes self loops, aggregates one feature state over one edge set, and concatenates neighbor mean then original x.
- There is no add_self_loops call in Base forward. This is a real semantic difference from the Deep signed layer.
- Owned weight[16,4], bias[4] and final L2 normalization are selected; outside caller may instantiate separate Base layers for different edge types.

- 修正：Do not copy the Deep two-state/three-operand structure or add self loops absent from this module.

## 真实依赖和参数/状态身份

| 源 | 目标端口 | 角色 |
| --- | --- | --- |
| `signed_graphconv_base.edges:out` | `signed_graphconv_base.remove:edges` | `topology` |
| `signed_graphconv_base.remove:out` | `signed_graphconv_base.mean:edges` | `topology` |
| `signed_graphconv_base.x:out` | `signed_graphconv_base.mean:features` | `tensor` |
| `signed_graphconv_base.mean:out` | `signed_graphconv_base.concat:neighbors` | `tensor` |
| `signed_graphconv_base.x:out` | `signed_graphconv_base.concat:self` | `retained_value` |
| `signed_graphconv_base.concat:out` | `signed_graphconv_base.project:features` | `tensor` |
| `signed_graphconv_base.weight:out` | `signed_graphconv_base.project:W` | `parameter_operand` |
| `signed_graphconv_base.project:out` | `signed_graphconv_base.biasadd:features` | `tensor` |
| `signed_graphconv_base.bias:out` | `signed_graphconv_base.biasadd:bias` | `parameter_operand` |
| `signed_graphconv_base.biasadd:out` | `signed_graphconv_base.normalize:in` | `tensor` |
| `signed_graphconv_base.normalize:out` | `signed_graphconv_base.output:in` | `tensor` |

实线运送张量值；虚线区分参数、拓扑、形状和循环状态。参数与调用者提供的拓扑不被混入自动主链。回边表达下一轮状态，并不创建新算子或新参数实例。完整逐节点证据在生成结果的 `source_map.md`、`source_evidence.json` 与 `semantic_ir.json` 中。

## 自底向上的排布与紧凑路由

最底部输入行 → 模块算子区 → 最上方输出。内部 `graph.ranks` 也按自底向上排列；同一 rank 中各算子并列，不产生隐式加法、数据依赖或共享参数。嵌套 stage 只在第3粒度展开。

```python
# module_adapters/signed_graphconv_base.py 的真实声明
from module_adapters.signed_graphconv_base import build
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
python generate.py --module signed_graphconv_base --png
python checks/graph_extended.py
```

开发中尚未合并时可使用：

```bash
python staging/preview_module.py signed_graphconv_base \
  --manifest staging/graph_source_manifest.json \
  --out /tmp/module-graph-preview
```

验证覆盖固定源文件散列、实际 AST 表达式/顺序、声明的 IR 节点字段与真实端口。负例会实际改变关键边的源端点、参数/算子身份、执行声称以及源码表达式，必须被拒绝。三图再做几何与 SVG/PNG 导出核验并人工查看。通过这些检查不等于数值执行验证，也不证明可以解析任意替换源码。
