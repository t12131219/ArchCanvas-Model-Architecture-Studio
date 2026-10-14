# InceptionA：四分支模块的源码与图形对应

本例只绘制 `torchvision v0.9.0` 的 **一个 InceptionA 模块**，不代表整个 Inception-v3。来源为 `pytorch/vision` 固定提交 `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。入口、构造、分支和输出均来自 [inception.py](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py)；源码未导入或执行。

选定构造为 `InceptionA(192, pool_features=32, conv_block=None)`，使用默认 `BasicConv2d`。该通道配置与源码 `Inception3.__init__` 的 `Mixed_5b` 一致。输入 `[B,192,35,35]` 是本例明确声明的代表性 shape，不是运行观测；也不据此补画 Mixed_5b 的前后网络。BN 的 train/eval 行为由调用方决定。

| 图中结构 / 稳定节点 | 源码属性与操作 | 选择该对应关系的理由 |
|---|---|---|
| 四分支 `inca.branches` | `InceptionA._forward`，236–250 行 | 四个局部变量均从同一个 `x` 开始；同输入扇出，不是按 channel 切分输入 |
| `inca.path_1x1` | `branch1x1`，225、237 行 | `192→64` 的单个 1×1 BasicConv2d |
| `inca.path_5x5` | `branch5x5_1/.branch5x5_2`，227–228、239–240 行 | 依次 `192→48` 1×1、`48→64` 5×5；本版本确实是一个 5×5 |
| `inca.path_3x3dbl` | `branch3x3dbl_1/_2/_3`，230–232、242–244 行 | 依次 `192→64` 1×1、`64→96` 3×3、`96→96` 3×3 |
| `inca.path_pool` | `F.avg_pool2d` 后接 `branch_pool`，234、246–247 行 | 平均池化 3×3、stride=1、padding=1 保持空间尺寸；然后 1×1 `192→32` |
| 每个 BasicConv 图框 | `BasicConv2d.__init__/forward`，463–478 行 | 每份实际属性都包含 Conv→BN→ReLU；详细图按真实顺序展开 |
| `inca.concat` | `outputs=[...]` 249 行；`torch.cat(outputs,1)` 254 行 | 有序 list 合并为 channel Concat；不是四路 Add，也不是完整模型的返回 tuple |

各支路输出为 `[B,64,35,35]`、`[B,64,35,35]`、`[B,96,35,35]`、`[B,32,35,35]`，按源码 list 顺序从左至右排列。所有卷积 stride=1、dilation=1、groups=1；1×1 padding=0、5×5 padding=2、3×3 padding=1，故可沿 channel 轴拼接：`64+64+96+32=256`。

每个 BasicConv2d 精确展开为：

```python
self.conv = nn.Conv2d(in_channels, out_channels, bias=False, **kwargs)
self.bn = nn.BatchNorm2d(out_channels, eps=0.001)
# forward:
x = self.conv(x)
x = self.bn(x)
return F.relu(x, inplace=True)
```

BN 的未显式覆盖默认值为 `momentum=0.1`、`affine=True`、`track_running_stats=True`。它既有独立 affine 参数，也有 running statistics buffer；buffer 不被当成另一份学习参数。模块直接构造与完整 Inception3 包装器的全模型初始化应分开理解，本例不执行或补画后者。

七份 BasicConv2d 使用七个真实属性名定位。例如 `branch1x1.conv` 与 `branch3x3dbl_1.conv` 虽然都是 `192→64` 的 1×1 卷积，仍是两个实例、两组权重。IR 同时保存相对参数路径和 `inception_a.<attribute>.conv/.bn` 的实例身份。ReLU 和 AvgPool 无学习参数；空间位置复用同一卷积核，与跨属性共享权重是不同关系。

三个粒度共用一个语义 IR：概览为输入→InceptionA→输出；模块图展开四个分支、七个 BasicConv 图框、平均池化和 Concat；详细图展开七套 Conv→BN→ReLU。所有 `chain.items` 按源码执行顺序声明，由引擎自底向上放置；四分支在 `parallel.items` 中保持源码 list 顺序。短支路底部对齐输入总线，顶部用独立竖线接入收集总线，避免把不同分支拉伸成假算子。尺寸由文本、shape、证据标签和嵌套容器计算，间距与箭头末段由共享引擎分配；源码不含这些视觉坐标。

统一引擎把有序容器的收集边称为 `tuple_collection`；这里通过 `collection_type="list"`、`literal_list=True`、`literal_tuple=False` 明确它是源码 list 的字段收集。该收集本身不执行 tensor 运算，真正合并由下一节点 `torch.cat(dim=1)` 完成。

字体、深色边框与蓝色 Conv、黄色 BN/Concat、绿色 Pool、灰色 ReLU 沿用 Transformer 风格。颜色区分图形角色；节点标签和参数路径决定实际算子与实例，颜色不代表权重共享。

`validate_ir()` 对四路同输入、list 顺序、七套参数身份、实际核大小、BN eps、池化类别、Concat 轴与输出 shape 做语义检查。负例应拒绝把 Concat 改成 Add、把 pool 改成 MaxPool、把 5×5 改成 3×3、把 BN eps 改成 `.00001` 或把分支权重身份合并。几何检查验证三个粒度的边界、包含关系、端点与转弯空间。静态检查不等价于模型运行或任意版本源码自动提取。
