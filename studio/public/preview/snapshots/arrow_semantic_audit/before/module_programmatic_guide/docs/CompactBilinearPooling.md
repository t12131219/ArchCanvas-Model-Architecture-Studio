# Compact bilinear TensorSketch：源码对应与程序化布局

案例键：`compact_bilinear_pooling`。这是 **模块子图**，不是完整任务模型。

边界：Forward path of CompactBilinearPooling(x,y), explicit two inputs and force_cpu_scatter_add=False; excludes custom backward and task head.

固定仓库：[gdlg/pytorch_compact_bilinear_pooling](https://github.com/gdlg/pytorch_compact_bilinear_pooling/tree/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8)；commit `ecbb98bdccaf8987f2c2432ac0f1db5f370811e8`。

## 选定配置与证据强度

```json
{
  "input1_size": 8,
  "input2_size": 6,
  "output_size": 16,
  "force_cpu_scatter_add": false,
  "y_is_none": false,
  "learned_parameters": 0,
  "spatial_reduction": false,
  "historical_fft_api": true,
  "selected_configuration": "explicit static module profile; not a runtime observation",
  "model_executed": false,
  "artifact_scope": "module"
}
```

上面的宽度、迭代次数和形状是适配器明确选择的静态示例，不是模型执行观察。固定源码 SHA256 / Git blob SHA 在 `staging/graph_source_manifest.json`（合并后 `source_manifest.json`）中。只解析 AST 和绘图声明，未导入或运行上游模型、Notebook、torch、NumPy 或 SciPy。

## 源码 ↔ 图元

| 图元稳定 ID | 算子/范围 | 静态形状 | 源码定位 |
| --- | --- | --- | --- |
| `compact_bilinear_pooling.x` | Input x | `[B,8]` | [CompactBilinearPoolingFn.forward](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L143) |
| `compact_bilinear_pooling.y` | Independent input y | `[B,6]` | [CompactBilinearPoolingFn.forward](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L143) |
| `compact_bilinear_pooling.xbuffers` | Fixed sketch1 buffers h, s | `each[8]` | [CountSketch.__init__](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L85) |
| `compact_bilinear_pooling.ybuffers` | Distinct sketch2 buffers h, s | `each[6]` | [CountSketch.__init__](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L85) |
| `compact_bilinear_pooling.xsketch.sign` | Multiply by fixed random signs | `[B,8]` | [CountSketchFn_forward](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L7)；[CountSketch.__init__](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L85) |
| `compact_bilinear_pooling.xsketch.scatter` | Hash-index scatter_add | `[B,16]` | [CountSketchFn_forward](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L7)；[CountSketch.__init__](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L85) |
| `compact_bilinear_pooling.xfft` | Historical rFFT / library | `[B,9,2]` | [CompactBilinearPoolingFn.forward](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L143) |
| `compact_bilinear_pooling.ysketch.sign` | Multiply by fixed random signs | `[B,6]` | [CountSketchFn_forward](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L7)；[CountSketch.__init__](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L85) |
| `compact_bilinear_pooling.ysketch.scatter` | Hash-index scatter_add | `[B,16]` | [CountSketchFn_forward](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L7)；[CountSketch.__init__](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L85) |
| `compact_bilinear_pooling.yfft` | Historical rFFT / library | `[B,9,2]` | [CompactBilinearPoolingFn.forward](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L143) |
| `compact_bilinear_pooling.product` | Complex product / real and imag | `[B,9] real + imag` | [ComplexMultiply_forward](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L116) |
| `compact_bilinear_pooling.inverse.stack` | Stack real / imaginary | `[B,9,2]` | [CompactBilinearPoolingFn.forward](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L143) |
| `compact_bilinear_pooling.inverse.irfft` | Historical irFFT / library | `[B,16]` | [CompactBilinearPoolingFn.forward](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L143) |
| `compact_bilinear_pooling.output` | Selected module output | `[B,16]` | [CompactBilinearPoolingFn.forward](https://github.com/gdlg/pytorch_compact_bilinear_pooling/blob/ecbb98bdccaf8987f2c2432ac0f1db5f370811e8/compact_bilinear_pooling/__init__.py#L143) |

源码和排布的关键关系：h 是固定散列位置，s 是固定随机符号，两者都注册为 buffer。两个 CountSketch 独立拥有 h/s，乘符号后 scatter_add 得到16维草图，再做历史 rFFT、真实复数乘法和 irFFT。缓冲输入分别接到 sign 与 hash 端口，因此同色草图不能被当成共享同一随机投影。

为什么这样对应：每个图元来自实际表达式、模块实例或明确的输入/状态边界；颜色表达算子/视觉角色，稳定 ID 与 `parameter_scope` / `instance_identity` 表达身份。两个同色 Linear 不能被推断成同一参数，两次读同一个输入也不能被改画成两个独立输入。展开层级只改变可见粒度。

## 关键源码事实与错误修正

- Each sketch owns independently generated h/s buffers registered at construction; they are shared across calls and have no optimizer parameters.
- CountSketch uses signed hash scatter_add, then legacy torch.rfft spectra are multiplied using the actual real/imag formula, followed by legacy irfft.
- This is feature-axis circular convolution of sketches; source does not explicitly sum spatial positions, normalize, or add signed square-root postprocessing.
- Historical FFT APIs are preserved as source boundaries; no upstream code was run or silently migrated.

- 修正：Do not replace fixed sketches by learned Linear projections or confuse this compact convolution with BAN weighted bilinear pooling.

## 真实依赖和参数/状态身份

| 源 | 目标端口 | 角色 |
| --- | --- | --- |
| `compact_bilinear_pooling.x:out` | `compact_bilinear_pooling.xsketch.sign:in` | `tensor` |
| `compact_bilinear_pooling.y:out` | `compact_bilinear_pooling.ysketch.sign:in` | `tensor` |
| `compact_bilinear_pooling.xbuffers:s` | `compact_bilinear_pooling.xsketch.sign:s` | `fixed_buffer` |
| `compact_bilinear_pooling.xbuffers:h` | `compact_bilinear_pooling.xsketch.scatter:h` | `fixed_buffer` |
| `compact_bilinear_pooling.ybuffers:s` | `compact_bilinear_pooling.ysketch.sign:s` | `fixed_buffer` |
| `compact_bilinear_pooling.ybuffers:h` | `compact_bilinear_pooling.ysketch.scatter:h` | `fixed_buffer` |
| `compact_bilinear_pooling.xsketch.scatter:out` | `compact_bilinear_pooling.xfft:in` | `tensor` |
| `compact_bilinear_pooling.ysketch.scatter:out` | `compact_bilinear_pooling.yfft:in` | `tensor` |
| `compact_bilinear_pooling.xfft:out` | `compact_bilinear_pooling.product:Xcomplex` | `tensor` |
| `compact_bilinear_pooling.yfft:out` | `compact_bilinear_pooling.product:Ycomplex` | `tensor` |
| `compact_bilinear_pooling.product:out` | `compact_bilinear_pooling.inverse.stack:in` | `tensor` |
| `compact_bilinear_pooling.inverse.irfft:out` | `compact_bilinear_pooling.output:in` | `tensor` |

实线运送张量值；虚线区分参数、拓扑、形状和循环状态。参数与调用者提供的拓扑不被混入自动主链。回边表达下一轮状态，并不创建新算子或新参数实例。完整逐节点证据在生成结果的 `source_map.md`、`source_evidence.json` 与 `semantic_ir.json` 中。

## 自底向上的排布与紧凑路由

最底部输入行 → 模块算子区 → 最上方输出。内部 `graph.ranks` 也按自底向上排列；同一 rank 中各算子并列，不产生隐式加法、数据依赖或共享参数。嵌套 stage 只在第3粒度展开。

```python
# module_adapters/compact_bilinear_pooling.py 的真实声明
from module_adapters.compact_bilinear_pooling import build
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
python generate.py --module compact_bilinear_pooling --png
python checks/graph_extended.py
```

开发中尚未合并时可使用：

```bash
python staging/preview_module.py compact_bilinear_pooling \
  --manifest staging/graph_source_manifest.json \
  --out /tmp/module-graph-preview
```

验证覆盖固定源文件散列、实际 AST 表达式/顺序、声明的 IR 节点字段与真实端口。负例会实际改变关键边的源端点、参数/算子身份、执行声称以及源码表达式，必须被拒绝。三图再做几何与 SVG/PNG 导出核验并人工查看。通过这些检查不等于数值执行验证，也不证明可以解析任意替换源码。
