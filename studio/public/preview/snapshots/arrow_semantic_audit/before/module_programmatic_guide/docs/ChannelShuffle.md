# Channel shuffle：同 shape 下的真实通道重排

本例只绘制 `channel_shuffle(x, groups)` 函数，不绘制 ShuffleNetV2 或 InvertedResidual。来源为 `pytorch/vision` 固定提交 `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`，对应 [shufflenetv2.py](../sources/torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py) 的 21–34 行；源码未导入或执行。

本例声明 contiguous 输入 `[B,24,8,8]`，`groups=2`，`channels_per_group=24//2=12`。这些是显式模块配置，不是从完整 ShuffleNet 的某个运行 batch 推测出的张量。源码第一步使用 `view`，要求输入的存储布局兼容；本例用 contiguous 输入满足这个前提。通道数必须能被 groups 整除，否则目标 `view` 的元素数量不匹配。

| 节点 | 真实源码 | shape / 对应含义 |
|---|---|---|
| `shuffle.group_view` | 26–27 行 `x.view(batchsize,groups,channels_per_group,height,width)` | `[B,24,8,8]→[B,2,12,8,8]`；把 channel 轴拆为 group、组内通道 |
| `shuffle.transpose` | 29 行 `torch.transpose(x,1,2)` | `[B,2,12,8,8]→[B,12,2,8,8]`；交换 group 和组内通道轴 |
| `shuffle.contiguous` | 同一行 `.contiguous()` | shape 不变；必要时复制成新轴顺序下的 contiguous 存储，为后续 view 准备 |
| `shuffle.flatten_view` | 32 行 `x.view(batchsize,-1,height,width)` | `[B,12,2,8,8]→[B,24,8,8]`；按已交换顺序把两个轴合并 |

22–23 行 `x.size()` 和整数除法只读取/计算 shape 元数据，记录在 profile、表达式与源码证据中，不把它们画成学习层。最后的 `return x` 对应模块输出；没有参数、Conv、BN、Pooling、Concat 或专门的 `gather` 运算。

源码的核心顺序不能省略中间的存储步骤：

```python
x = x.view(batchsize, groups, channels_per_group, height, width)
x = torch.transpose(x, 1, 2).contiguous()
x = x.view(batchsize, -1, height, width)
```

Transpose 通常只建立非 contiguous 的张量视图；这里的 `contiguous()` 保留逻辑值和 shape，必要时改变存储排列。最终 `view` 按新的 contiguous 顺序合并轴，因此输出 shape 相同，通道顺序却已经变化。height、width 和每个通道内的空间坐标都没有交换、插值或混合。

可以只用静态索引解释，不运行模型，也不虚构额外算子。输入通道 `c=g*12+k`，拆轴后位置为 `(g,k)`，交换后为 `(k,g)`，最后输出通道为 `o=k*2+g`。所以 `y[:,o,h,w] = x[:,(o%2)*12 + o//2,h,w]`，输出至输入的完整映射为：

```text
输出 o:   0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23
输入 c:   0 12  1 13  2 14  3 15  4 16  5 17  6 18  7 19  8 20  9 21 10 22 11 23
```

也可把原来的两个 group 各自列为 `[0,...,11]` 和 `[12,...,23]`；输出逐个交替取两组元素。这个表、IR 的 `permutation_output_to_input` 和图例短序列都是从真实 `view/transpose/view` 推导的说明，不是源码中额外执行的 permutation matrix、index_select 或 gather。两个 view 都没有学习参数；transpose 与 contiguous 也没有学习参数，因此同色节点不涉及权重共享。

三个粒度沿用同一根结构输入→模块→输出。概览折叠函数；模块图显示第一 view、Swap+contiguous 逻辑组、最后 view；详细图把逻辑组展开为两个独立源码操作，完整流程由下向上读。`axis_swap` 只是对同一源码行中两个调用的绘图分组，不是额外 PyTorch 层。shape 与证据标签共同确定图框高度，连线沿共享引擎的预留通道提前转弯；无旁路或跨分支箭头。

图形使用 Transformer 同款字体和深色边框：蓝色张量重排、灰色 contiguous、粉色输入、紫色输出。控制颜色仅表达存储/操作角色，不暗示新增可学习控制模块。完整映射保存在文档与 profile，图例只呈现短序列，避免把说明塞进数据路径。

`validate_ir()` 检查 groups、全部中间 shape、transpose 轴、contiguous 前后顺序、最终 `-1` view、24 通道双射和无参数边界。负例应拒绝删除 contiguous、把 transpose 改成 `(2,3)`、把 groups 改为 12、交换中间 shape、增加卷积或把通道映射写成恒等。几何检查验证三个粒度的边界、包含、端点与箭头空间；这些是静态取证和规则检查，不代表已经运行模型。
