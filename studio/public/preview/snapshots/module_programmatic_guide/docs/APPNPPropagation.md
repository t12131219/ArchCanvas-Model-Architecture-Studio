# APPNP restart propagation：源码对应与程序化布局

案例键：`appnp_propagation`。这是 **模块子图**，不是完整任务模型。

边界：Approximate branch only: latent_features_2 boundary through localized_predictions; excludes both feature MLP layers and final log_softmax.

固定仓库：[benedekrozemberczki/APPNP](https://github.com/benedekrozemberczki/APPNP/tree/338d98980ee8748e652630dd422341ef8b2a354a)；commit `338d98980ee8748e652630dd422341ef8b2a354a`。

## 选定配置与证据强度

```json
{
  "alpha": 0.1,
  "iterations": 3,
  "model": "approximate",
  "display": "APPNP iteration template / alpha=.1 / K=3 / no task head",
  "edge_dropout_once_per_forward": true,
  "shared_fixed_restart": true,
  "selected_configuration": "explicit static module profile; not a runtime observation",
  "model_executed": false,
  "artifact_scope": "module"
}
```

上面的宽度、迭代次数和形状是适配器明确选择的静态示例，不是模型执行观察。固定源码 SHA256 / Git blob SHA 在 `staging/graph_source_manifest.json`（合并后 `source_manifest.json`）中。只解析 AST 和绘图声明，未导入或运行上游模型、Notebook、torch、NumPy 或 SciPy。

## 源码 ↔ 图元

| 图元稳定 ID | 算子/范围 | 静态形状 | 源码定位 |
| --- | --- | --- | --- |
| `appnp_propagation.h0` | Retained initial H0 | `[N,8]` | [APPNPModel.forward](https://github.com/benedekrozemberczki/APPNP/blob/338d98980ee8748e652630dd422341ef8b2a354a/src/appnp_layer.py#L138) |
| `appnp_propagation.edges` | Sparse topology / weights | `indices[2,E], values[E]` | [APPNPModel.forward](https://github.com/benedekrozemberczki/APPNP/blob/338d98980ee8748e652630dd422341ef8b2a354a/src/appnp_layer.py#L138) |
| `appnp_propagation.drop` | Edge weight Dropout / once | `[E]` | [APPNPModel.forward](https://github.com/benedekrozemberczki/APPNP/blob/338d98980ee8748e652630dd422341ef8b2a354a/src/appnp_layer.py#L138) |
| `appnp_propagation.step.spmm` | A_drop @ current H | `[N,8]` | [APPNPModel.forward](https://github.com/benedekrozemberczki/APPNP/blob/338d98980ee8748e652630dd422341ef8b2a354a/src/appnp_layer.py#L138) |
| `appnp_propagation.scale` | Scale propagated state by 1-alpha | `[N,8]` | [APPNPModel.forward](https://github.com/benedekrozemberczki/APPNP/blob/338d98980ee8748e652630dd422341ef8b2a354a/src/appnp_layer.py#L138) |
| `appnp_propagation.restart` | Scale SAME H0 by alpha | `[N,8]` | [APPNPModel.forward](https://github.com/benedekrozemberczki/APPNP/blob/338d98980ee8748e652630dd422341ef8b2a354a/src/appnp_layer.py#L138) |
| `appnp_propagation.add` | Add restart to propagated state | `[N,8]` | [APPNPModel.forward](https://github.com/benedekrozemberczki/APPNP/blob/338d98980ee8748e652630dd422341ef8b2a354a/src/appnp_layer.py#L138) |
| `appnp_propagation.output` | Selected module output | `[N,8]` | [APPNPModel.forward](https://github.com/benedekrozemberczki/APPNP/blob/338d98980ee8748e652630dd422341ef8b2a354a/src/appnp_layer.py#L138) |

源码和排布的关键关系：边权 Dropout 在循环之前采样一次；稀疏索引不经过 Dropout，单独接入 spmm。每轮状态更新为 (1-α)·A_drop·H_t + α·H0，重启项始终读原 H0。循环虚线表达 H_{t+1} 回到当前状态，绝不能把 α·H0 改成 α·H_t。

为什么这样对应：每个图元来自实际表达式、模块实例或明确的输入/状态边界；颜色表达算子/视觉角色，稳定 ID 与 `parameter_scope` / `instance_identity` 表达身份。两个同色 Linear 不能被推断成同一参数，两次读同一个输入也不能被改画成两个独立输入。展开层级只改变可见粒度。

## 关键源码事实与错误修正

- One representative recurrence is shown with K=3 declared example repeats. Feedback edges carry next H, not fresh task logits.
- Edge Dropout occurs before the loop and is shared within a forward. Restart is always the same latent_features_2, never the latest H.
- Normalized topology is external at the chosen module boundary; torch_sparse.spmm remains a library boundary.

- 修正：Do not put log_softmax or the predictor MLP inside this propagation module.
- 修正：Do not resample edge dropout each iteration or use alpha*H_t as restart.

## 真实依赖和参数/状态身份

| 源 | 目标端口 | 角色 |
| --- | --- | --- |
| `appnp_propagation.h0:out` | `appnp_propagation.step.spmm:state0` | `initial_state` |
| `appnp_propagation.edges:values` | `appnp_propagation.drop:in` | `topology` |
| `appnp_propagation.edges:indices` | `appnp_propagation.step.spmm:indices` | `topology` |
| `appnp_propagation.drop:out` | `appnp_propagation.step.spmm:weights` | `topology` |
| `appnp_propagation.step.spmm:out` | `appnp_propagation.scale:in` | `tensor` |
| `appnp_propagation.scale:out` | `appnp_propagation.add:propagated` | `tensor` |
| `appnp_propagation.h0:out` | `appnp_propagation.restart:in` | `retained_value` |
| `appnp_propagation.restart:out` | `appnp_propagation.add:restart` | `tensor` |
| `appnp_propagation.add:out` | `appnp_propagation.step.spmm:state_next` | `loop_recurrence` |
| `appnp_propagation.add:out` | `appnp_propagation.output:in` | `tensor` |

实线运送张量值；虚线区分参数、拓扑、形状和循环状态。参数与调用者提供的拓扑不被混入自动主链。回边表达下一轮状态，并不创建新算子或新参数实例。完整逐节点证据在生成结果的 `source_map.md`、`source_evidence.json` 与 `semantic_ir.json` 中。

## 自底向上的排布与紧凑路由

最底部输入行 → 模块算子区 → 最上方输出。内部 `graph.ranks` 也按自底向上排列；同一 rank 中各算子并列，不产生隐式加法、数据依赖或共享参数。嵌套 stage 只在第3粒度展开。

```python
# module_adapters/appnp_propagation.py 的真实声明
from module_adapters.appnp_propagation import build
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
python generate.py --module appnp_propagation --png
python checks/graph_extended.py
```

开发中尚未合并时可使用：

```bash
python staging/preview_module.py appnp_propagation \
  --manifest staging/graph_source_manifest.json \
  --out /tmp/module-graph-preview
```

验证覆盖固定源文件散列、实际 AST 表达式/顺序、声明的 IR 节点字段与真实端口。负例会实际改变关键边的源端点、参数/算子身份、执行声称以及源码表达式，必须被拒绝。三图再做几何与 SVG/PNG 导出核验并人工查看。通过这些检查不等于数值执行验证，也不证明可以解析任意替换源码。
