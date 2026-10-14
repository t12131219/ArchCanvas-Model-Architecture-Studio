# TuckER relation-conditioned core：源码对应与程序化布局

案例键：`tucker_core`。这是 **模块子图**，不是完整任务模型。

边界：Only relation embedding, learned core contraction, hidden_dropout1 and subject BMM; subject input is post bn0/input_dropout plus original e1.size(1) metadata. Excludes bn1, output table scoring, sigmoid/loss/task training.

固定仓库：[ibalazevic/TuckER](https://github.com/ibalazevic/TuckER/tree/23aff592115ee91e099ce490cdbea28ef026fc54)；commit `23aff592115ee91e099ce490cdbea28ef026fc54`。

## 选定配置与证据强度

```json
{
  "d1": 8,
  "d2": 6,
  "relation_count": "R",
  "hidden_dropout1": 0.3,
  "subject_boundary": "x after bn0/input_dropout; before x.view",
  "shape_boundary": "e1.size(1) from original E(e1_idx), shape only",
  "output_boundary": "x after bmm and restore; before bn1",
  "constructor_core_device": "cuda",
  "core_executed": false,
  "mode": "caller train/eval",
  "selected_configuration": "explicit static module profile; not a runtime observation",
  "model_executed": false,
  "artifact_scope": "module"
}
```

上面的宽度、迭代次数和形状是适配器明确选择的静态示例，不是模型执行观察。固定源码 SHA256 / Git blob SHA 在 `staging/graph_source_manifest.json`（合并后 `source_manifest.json`）中。只解析 AST 和绘图声明，未导入或运行上游模型、Notebook、torch、NumPy 或 SciPy。

## 源码 ↔ 图元

| 图元稳定 ID | 算子/范围 | 静态形状 | 源码定位 |
| --- | --- | --- | --- |
| `tucker_core.subject` | Subject features after input Dropout | `[B,8]` | [TuckER.forward](https://github.com/ibalazevic/TuckER/blob/23aff592115ee91e099ce490cdbea28ef026fc54/model.py#L28) |
| `tucker_core.relation` | Relation IDs r_idx | `[B]` | [TuckER.forward](https://github.com/ibalazevic/TuckER/blob/23aff592115ee91e099ce490cdbea28ef026fc54/model.py#L28) |
| `tucker_core.core` | Owned learned 3-way core W | `[6,8,8]` | [TuckER.__init__](https://github.com/ibalazevic/TuckER/blob/23aff592115ee91e099ce490cdbea28ef026fc54/model.py#L7) |
| `tucker_core.e1shape` | Original subject embedding WIDTH | `e1.size(1) = 8` | [TuckER.forward](https://github.com/ibalazevic/TuckER/blob/23aff592115ee91e099ce490cdbea28ef026fc54/model.py#L28) |
| `tucker_core.relationlookup` | Owned relation embedding R | `[B,6]` | [TuckER.__init__](https://github.com/ibalazevic/TuckER/blob/23aff592115ee91e099ce490cdbea28ef026fc54/model.py#L7)；[TuckER.forward](https://github.com/ibalazevic/TuckER/blob/23aff592115ee91e099ce490cdbea28ef026fc54/model.py#L28) |
| `tucker_core.subjectview` | View subject as row per batch | `[B,1,8]` | [TuckER.forward](https://github.com/ibalazevic/TuckER/blob/23aff592115ee91e099ce490cdbea28ef026fc54/model.py#L28) |
| `tucker_core.condition.mm` | r @ core.view(6,-1) | `[B,64]` | [TuckER.__init__](https://github.com/ibalazevic/TuckER/blob/23aff592115ee91e099ce490cdbea28ef026fc54/model.py#L7)；[TuckER.forward](https://github.com/ibalazevic/TuckER/blob/23aff592115ee91e099ce490cdbea28ef026fc54/model.py#L28) |
| `tucker_core.condition.reshape` | View conditioned matrix | `[B,8,8]` | [TuckER.__init__](https://github.com/ibalazevic/TuckER/blob/23aff592115ee91e099ce490cdbea28ef026fc54/model.py#L7)；[TuckER.forward](https://github.com/ibalazevic/TuckER/blob/23aff592115ee91e099ce490cdbea28ef026fc54/model.py#L28) |
| `tucker_core.condition.dropout` | Hidden Dropout1 .3 | `[B,8,8]` | [TuckER.__init__](https://github.com/ibalazevic/TuckER/blob/23aff592115ee91e099ce490cdbea28ef026fc54/model.py#L7)；[TuckER.forward](https://github.com/ibalazevic/TuckER/blob/23aff592115ee91e099ce490cdbea28ef026fc54/model.py#L28) |
| `tucker_core.multiply` | Subject row @ conditioned matrix | `[B,1,8]` | [TuckER.forward](https://github.com/ibalazevic/TuckER/blob/23aff592115ee91e099ce490cdbea28ef026fc54/model.py#L28) |
| `tucker_core.restore` | Restore feature axis | `[B,8]` | [TuckER.forward](https://github.com/ibalazevic/TuckER/blob/23aff592115ee91e099ce490cdbea28ef026fc54/model.py#L28) |
| `tucker_core.output` | Selected module output | `[B,8]` | [TuckER.forward](https://github.com/ibalazevic/TuckER/blob/23aff592115ee91e099ce490cdbea28ef026fc54/model.py#L28) |

源码和排布的关键关系：关系 ID 经独立关系表 R 得到6维向量，再与三阶核心 W[6,8,8] 收缩成为每个样本的8×8变换矩阵。hidden_dropout1 作用于这个矩阵，随后 subject 行向量做有序 bmm。选定模块边界在输入预处理之后、bn1之前；三个 view 仍读取原始 E(e1_idx) 的 e1.size(1)，因此从独立形状边界输入 e1shape 接入 subjectview、condition.reshape、restore，不把已处理 subject 的张量值误当作原始 e1。没有把知识图谱任务评分头放进这个可复用核心。CUDA初始化只是源事实，没有执行。

为什么这样对应：每个图元来自实际表达式、模块实例或明确的输入/状态边界；颜色表达算子/视觉角色，稳定 ID 与 `parameter_scope` / `instance_identity` 表达身份。两个同色 Linear 不能被推断成同一参数，两次读同一个输入也不能被改画成两个独立输入。展开层级只改变可见粒度。

## 关键源码事实与错误修正

- Owned relation embedding R[r_idx] contracts with owned core W[d2,d1,d1] to form one relation-conditioned square matrix per batch item. Subject features then multiply that matrix in ordered bmm.
- hidden_dropout1 applies to the conditioned matrix BEFORE subject multiplication; it is not dropout of the final entity score.
- Core constructor explicitly creates a CUDA tensor using NumPy random initialization. That is recorded as a runtime boundary; neither initialization nor CUDA/model code is executed.
- Selected boundary is a reusable feature-transformation suffix. It excludes input preprocessing and the later tied entity embedding scoring; no full knowledge-graph task model is claimed.

- 修正：Do not draw relation as a gate multiplying subject elementwise, collapse the 3-way core into a plain Linear, or include unrelated classifier/sigmoid in this module.

## 真实依赖和参数/状态身份

| 源 | 目标端口 | 角色 |
| --- | --- | --- |
| `tucker_core.relation:out` | `tucker_core.relationlookup:r_idx` | `tensor` |
| `tucker_core.relationlookup:out` | `tucker_core.condition.mm:r` | `tensor` |
| `tucker_core.core:out` | `tucker_core.condition.mm:W` | `parameter_operand` |
| `tucker_core.subject:out` | `tucker_core.subjectview:in` | `tensor` |
| `tucker_core.e1shape:shape` | `tucker_core.subjectview:d1` | `shape_dependency` |
| `tucker_core.e1shape:shape` | `tucker_core.condition.reshape:d1` | `shape_dependency` |
| `tucker_core.e1shape:shape` | `tucker_core.restore:d1` | `shape_dependency` |
| `tucker_core.subjectview:out` | `tucker_core.multiply:subject_row` | `tensor` |
| `tucker_core.condition.dropout:out` | `tucker_core.multiply:relation_matrix` | `tensor` |
| `tucker_core.multiply:out` | `tucker_core.restore:in` | `tensor` |
| `tucker_core.restore:out` | `tucker_core.output:in` | `tensor` |

实线运送张量值；虚线区分参数、拓扑、形状和循环状态。参数与调用者提供的拓扑不被混入自动主链。回边表达下一轮状态，并不创建新算子或新参数实例。完整逐节点证据在生成结果的 `source_map.md`、`source_evidence.json` 与 `semantic_ir.json` 中。

## 自底向上的排布与紧凑路由

最底部输入行 → 模块算子区 → 最上方输出。内部 `graph.ranks` 也按自底向上排列；同一 rank 中各算子并列，不产生隐式加法、数据依赖或共享参数。嵌套 stage 只在第3粒度展开。

```python
# module_adapters/tucker_core.py 的真实声明
from module_adapters.tucker_core import build
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
python generate.py --module tucker_core --png
python checks/graph_extended.py
```

开发中尚未合并时可使用：

```bash
python staging/preview_module.py tucker_core \
  --manifest staging/graph_source_manifest.json \
  --out /tmp/module-graph-preview
```

验证覆盖固定源文件散列、实际 AST 表达式/顺序、声明的 IR 节点字段与真实端口。负例会实际改变关键边的源端点、参数/算子身份、执行声称以及源码表达式，必须被拒绝。三图再做几何与 SVG/PNG 导出核验并人工查看。通过这些检查不等于数值执行验证，也不证明可以解析任意替换源码。
