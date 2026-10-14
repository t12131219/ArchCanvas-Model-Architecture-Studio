# Signed graph deep convolution：源码对应与程序化布局

案例键：`signed_graphconv`。这是 **模块子图**，不是完整任务模型。

边界：One deep signed layer, x1/x2 separate feature states, norm=True,norm_embed=True,bias=True; excludes balanced/unbalanced task-network swaps and classifier.

固定仓库：[benedekrozemberczki/SGCN](https://github.com/benedekrozemberczki/SGCN/tree/c01e930c02968ea5b0eb72f1fe93eaab99e46eea)；commit `c01e930c02968ea5b0eb72f1fe93eaab99e46eea`。

## 选定配置与证据强度

```json
{
  "feature_dim": 8,
  "in_channels": 24,
  "out_channels": 4,
  "norm": true,
  "norm_embed": true,
  "bias": true,
  "positive_source": "x_1",
  "negative_source": "x_2",
  "self_loops": "remove then add in BOTH edge sets",
  "selected_configuration": "explicit static module profile; not a runtime observation",
  "model_executed": false,
  "artifact_scope": "module"
}
```

上面的宽度、迭代次数和形状是适配器明确选择的静态示例，不是模型执行观察。固定源码 SHA256 / Git blob SHA 在 `staging/graph_source_manifest.json`（合并后 `source_manifest.json`）中。只解析 AST 和绘图声明，未导入或运行上游模型、Notebook、torch、NumPy 或 SciPy。

## 源码 ↔ 图元

| 图元稳定 ID | 算子/范围 | 静态形状 | 源码定位 |
| --- | --- | --- | --- |
| `signed_graphconv.x1` | State x1 | `[N,8]` | [SignedSAGEConvolutionDeep.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L131) |
| `signed_graphconv.x2` | Distinct state x2 | `[N,8]` | [SignedSAGEConvolutionDeep.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L131) |
| `signed_graphconv.pos` | Positive edge indices | `[2,E+]` | [SignedSAGEConvolutionDeep.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L131) |
| `signed_graphconv.neg` | Negative edge indices | `[2,E-]` | [SignedSAGEConvolutionDeep.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L131) |
| `signed_graphconv.weight` | Owned weight W | `[24,4]` | [SignedSAGEConvolution.__init__](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L65) |
| `signed_graphconv.bias` | Owned bias b | `[4]` | [SignedSAGEConvolution.__init__](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L65) |
| `signed_graphconv.posloops` | Remove then ADD self loops | `[2,E_loop]` | [SignedSAGEConvolutionDeep.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L131) |
| `signed_graphconv.posmean` | Mean of x1 neighbors | `[N,8]` | [SignedSAGEConvolutionDeep.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L131) |
| `signed_graphconv.negloops` | Remove then ADD self loops | `[2,E_loop]` | [SignedSAGEConvolutionDeep.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L131) |
| `signed_graphconv.negmean` | Mean of x2 neighbors | `[N,8]` | [SignedSAGEConvolutionDeep.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L131) |
| `signed_graphconv.concat` | Concat pos, neg, SELF x1 | `[N,24]` | [SignedSAGEConvolutionDeep.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L131) |
| `signed_graphconv.project` | Concatenated states @ W | `[N,4]` | [SignedSAGEConvolutionDeep.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L131) |
| `signed_graphconv.biasadd` | Add owned bias | `[N,4]` | [SignedSAGEConvolutionDeep.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L131) |
| `signed_graphconv.normalize` | L2 normalize each node | `[N,4]` | [SignedSAGEConvolutionDeep.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L131) |
| `signed_graphconv.output` | Selected module output | `[N,4]` | [SignedSAGEConvolutionDeep.forward](https://github.com/benedekrozemberczki/SGCN/blob/c01e930c02968ea5b0eb72f1fe93eaab99e46eea/src/signedsageconvolution.py#L131) |

源码和排布的关键关系：正边从 x1 取邻居，负边从 x2 取邻居；两套边都先删已有自环再添加自环。两个 mean 结果与保留的 x1 按 out1→out2→x1 拼接，随后同一个 W、bias、L2 normalize。两个状态的来源和第三操作数不能被简化成一条共用输入线。

为什么这样对应：每个图元来自实际表达式、模块实例或明确的输入/状态边界；颜色表达算子/视觉角色，稳定 ID 与 `parameter_scope` / `instance_identity` 表达身份。两个同色 Linear 不能被推断成同一参数，两次读同一个输入也不能被改画成两个独立输入。展开层级只改变可见粒度。

## 关键源码事实与错误修正

- Positive mean reads x1 while negative mean reads x2. The retained third concatenation operand is x1, not x2.
- Source removes existing self loops and then adds self loops to BOTH edge sets before scatter_mean. This includes self contribution inside both means as well as explicit retained x1.
- One owned W[24,4] and bias[4] follow three-operand concat; optional norm_embed selects final L2 normalization.
- Library self-loop/scatter helpers remain opaque. Balanced/unbalanced caller state swaps are outside this source module boundary.

- 修正：Do not draw positive and negative paths as copies of the same x or omit the explicitly retained x1.
- 修正：Do not apply the first-layer Base self-loop policy to this Deep implementation.

## 真实依赖和参数/状态身份

| 源 | 目标端口 | 角色 |
| --- | --- | --- |
| `signed_graphconv.pos:out` | `signed_graphconv.posloops:edges` | `topology` |
| `signed_graphconv.neg:out` | `signed_graphconv.negloops:edges` | `topology` |
| `signed_graphconv.x1:out` | `signed_graphconv.posloops:num_nodes` | `shape_dependency` |
| `signed_graphconv.x2:out` | `signed_graphconv.negloops:num_nodes` | `shape_dependency` |
| `signed_graphconv.x1:out` | `signed_graphconv.posmean:features` | `tensor` |
| `signed_graphconv.x2:out` | `signed_graphconv.negmean:features` | `tensor` |
| `signed_graphconv.posloops:out` | `signed_graphconv.posmean:edges` | `topology` |
| `signed_graphconv.negloops:out` | `signed_graphconv.negmean:edges` | `topology` |
| `signed_graphconv.posmean:out` | `signed_graphconv.concat:out_1` | `tensor` |
| `signed_graphconv.negmean:out` | `signed_graphconv.concat:out_2` | `tensor` |
| `signed_graphconv.x1:out` | `signed_graphconv.concat:self_x1` | `retained_value` |
| `signed_graphconv.concat:out` | `signed_graphconv.project:features` | `tensor` |
| `signed_graphconv.weight:out` | `signed_graphconv.project:W` | `parameter_operand` |
| `signed_graphconv.project:out` | `signed_graphconv.biasadd:features` | `tensor` |
| `signed_graphconv.bias:out` | `signed_graphconv.biasadd:bias` | `parameter_operand` |
| `signed_graphconv.biasadd:out` | `signed_graphconv.normalize:in` | `tensor` |
| `signed_graphconv.normalize:out` | `signed_graphconv.output:in` | `tensor` |

实线运送张量值；虚线区分参数、拓扑、形状和循环状态。参数与调用者提供的拓扑不被混入自动主链。回边表达下一轮状态，并不创建新算子或新参数实例。完整逐节点证据在生成结果的 `source_map.md`、`source_evidence.json` 与 `semantic_ir.json` 中。

## 自底向上的排布与紧凑路由

最底部输入行 → 模块算子区 → 最上方输出。内部 `graph.ranks` 也按自底向上排列；同一 rank 中各算子并列，不产生隐式加法、数据依赖或共享参数。嵌套 stage 只在第3粒度展开。

```python
# module_adapters/signed_graphconv.py 的真实声明
from module_adapters.signed_graphconv import build
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
python generate.py --module signed_graphconv --png
python checks/graph_extended.py
```

开发中尚未合并时可使用：

```bash
python staging/preview_module.py signed_graphconv \
  --manifest staging/graph_source_manifest.json \
  --out /tmp/module-graph-preview
```

验证覆盖固定源文件散列、实际 AST 表达式/顺序、声明的 IR 节点字段与真实端口。负例会实际改变关键边的源端点、参数/算子身份、执行声称以及源码表达式，必须被拒绝。三图再做几何与 SVG/PNG 导出核验并人工查看。通过这些检查不等于数值执行验证，也不证明可以解析任意替换源码。
