# EdgePredictor：由固定坐标预测边权的模块案例

这是从 `GraphNet` 中选出的局部计算图，**上游没有名为 EdgePredictor 的独立类**。边界是构造器中的 `pred_edge_fc`、注册坐标缓冲区，以及 `forward` 的这一条表达式：

```python
self.A = self.pred_edge_fc(self.coord).squeeze()
```

绘图不包含后面的图像像素重排、邻居聚合 `bmm`、全图分类 `fc` 或 Softmax。因此本例可以用于研究“模块适配”，不能冒充完整的 GraphNet 模型图。

上游为 [rasbt/deeplearning-models](https://github.com/rasbt/deeplearning-models)，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。来源是 [gnn-basic-edge-1.ipynb](../sources/rasbt-modules/pytorch_ipynb/gnn/gnn-basic-edge-1.ipynb)；静态、逐代码单元拼接得到 [gnn-basic-edge-1.py](../sources/rasbt-modules/pytorch_ipynb/gnn/gnn-basic-edge-1.py)，可由证据文件的 `line_map` 回溯 notebook 单元。本次不导入、不执行 notebook、模型或坐标计算。

## 源码与图元逐项对应

| 图元 / IR 身份 | 源码位置（派生 `.py`） | 表达的真实结构 | 为什么这样对应 |
|---|---|---|---|
| `edge.init` | `make_coordinate_array`，90–104；`GraphNet.__init__`，109–123 | 构造器时的固定坐标来源 | 坐标在构造器创建、注册，不是每批图像的计算结果；放在灰色辅助面板 |
| `edge.grid` | helper 中 meshgrid、stack、标准化与转 float | `[784,2]` 网格坐标，各轴均值/标准差标准化，分母加 `1e-5` | 图中用一枚张量处理图元概括固定预处理，源码片段保留完整运算 |
| `edge.pairs` | helper 的两个 repeat 与 `cat(dim=2)` | `[784,784,4]` 有序坐标对 | 并不是像素特征，也不是随机/可学习位置嵌入 |
| `edge.buffer` → `edge.coord` | `register_buffer('coord', coord)`；forward 读取 `self.coord` | 固定持久 buffer 的注册与读取 | 虚线连接携带同一个 `coord` 值；不引入图像输入或批大小 |
| `edge.mlp` | `self.pred_edge_fc = nn.Sequential(...)` | 一个共享 MLP：Linear 4→32、ReLU、Linear 32→1、Tanh | Sequential 的前后顺序提供主流向；相同参数实例应用在所有坐标对上 |
| `edge.linear1` / `edge.linear2` | Sequential 索引 `.0` / `.2` | 两组不同的 Linear 参数 | 同色表示算子类型；参数身份区分两个实例，不能因为同色就认为权重相同 |
| `edge.squeeze` | `GraphNet.forward`，128–151，选定表达式 | 移除单例维并赋值普通属性 `self.A` | 图例和输出形状都采用固定 `N=784`；`squeeze()` 没有显式 dim |
| `edge.output` | `self.A` 的选定子图出口 | `[784,784]` 邻接边权 | 是模块的选定结果，不是完整 `GraphNet.forward` 的返回值 |

对坐标对 `[i,j]`，源码第一项为 `coord.unsqueeze(0)` 后重复，第二项为 `coord.unsqueeze(1)` 后重复。因此输入顺序是：

```text
coord[i,j] = [col_j, row_j, col_i, row_i]
```

不应猜测为相反顺序，也不能假设任意 MLP 都满足 `A[i,j] == A[j,i]`。

## 张量与参数关系

```text
fixed coord [N,N,4]
      ↑ Linear 4→32    weight [32,4], bias [32]
      ↑ ReLU
      ↑ Linear 32→1    weight [1,32], bias [1]
      ↑ Tanh
      ↑ squeeze()
       A [N,N]        N=784
```

图中实际流程自底向上，文字序列按执行顺序列出。`nn.Linear` 对最后一维计算，两个 `[N,N]` 前导维保留。全体 `N²` 坐标对共享同一组 MLP 参数，参数数量为 `(4×32+32)+(32×1+1)=193`，不是 `193×N²`。`coord` 本身是固定 buffer。

`Tanh` 允许负边权；源码没有 Softmax、阈值、度归一化或对称化。A 由固定坐标和当前 MLP 权重决定，同一次模型状态下所有图像使用同一个 A。它不读取图像强度、不需要 B 轴。A 在每次 forward 重新计算，存到普通张量属性 `self.A`，与构造器注册的 `coord` buffer 是两种身份。

## 三粒度与程序化排布

1. **概览**：`coord` 输入、折叠的坐标→A 模块、A 输出；构造器坐标面板单独显示。
2. **内部模块**：打开 `edge.forward`，共享 MLP 与 squeeze 分开；保留 MLP 的整体身份。
3. **详细算子**：打开 `edge.mlp` 和构造器坐标面板；每个算子一枚图元，统一自底向上。

适配器 [edge_predictor.py](../module_adapters/edge_predictor.py) 用 `chain` 记录真实顺序。共享引擎根据实际文字测量宽高，链内节点按 24px 间隔紧凑堆放，父级尺寸从子级尺寸和内边距计算。固定 `coord` 依赖通过辅助虚线接入读取图元，与主序列分开。颜色沿用 Transformer 样式：粉色输入、紫色 Linear、灰色 ReLU、绿色 Tanh、深色轮廓。绿色表示呈现中的激活角色，不等价于 Softmax 语义；IR 的 `kind='tanh', activation='tanh'` 保留确切算子，视觉别名只控制颜色。

```bash
cd module_programmatic_guide
python generate.py --module edge_predictor --png
python verify.py --module edge_predictor --png
```

可查看 [详细 SVG](../generated/edge_predictor/figure3_detailed.svg)、[逐节点源码表](../generated/edge_predictor/source_map.md)、[语义 IR](../generated/edge_predictor/semantic_ir.json) 和 [布局记录](../generated/edge_predictor/layout_detailed.json)。生成器只执行已审阅的绘图适配器和静态证据采集；不会运行上游模型。

## 核验与适用范围

固定版本哈希与 AST 符号核验保证绘图取证针对同一源码；专用语义校验检查有序坐标对、两个参数实例、共享关系、Tanh、A 的普通属性身份，以及没有图像/B 输入。几何校验检查容器、文字、正交走线、端点、终段和边框间距。

当前形状只针对 `img_size=28, coord_features=4`。例如 `N=1` 时无 dim 的 squeeze 会移除更多单例维；其他 `out_size` 还涉及 helper 的重复规则。改配置或换源码必须重新审阅适配器，不能只更换路径后沿用形状结论。
