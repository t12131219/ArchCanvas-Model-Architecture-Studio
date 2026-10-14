# InceptionB：三路降采样模块

本例只绘制 `InceptionB only; no complete Inception network`，不新增完整模型。固定来源为 [pytorch/vision](https://github.com/pytorch/vision)，commit `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。源码经 AST 读取与 SHA256/Git blob 核对，未导入、执行模型、下载权重或运行 C++/CUDA kernel。

本例明确声明构造 `InceptionB(288)`，输入 `[B,288,35,35]`，输出 `[B,768,17,17]`。shape 是选例与静态公式的推导，不是一次实际forward观测；含BN/Dropout的路径由调用方train/eval决定。

选定 `InceptionB(288)`，35×35→17×17。左路3×3 stride2 `288→384`；中路1×1 `288→64`、3×3 padding1 `64→96`、3×3 stride2 `96→96`；右路MaxPool3 stride2保持288通道。输出list按这三路顺序，Concat得768通道。pool无需卷积投影。

每个BasicConv实际为 Conv(bias=False)→BN(eps=.001)→inplace ReLU，独立 `.conv/.bn` 参数。B不是保持空间尺寸的InceptionA，也不使用averagePool。

## 源码证据范围

| 符号 | 本固定文件行号 | 原文件 |
|---|---|---|
| `InceptionB` | 257–287 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `InceptionB.__init__` | 259–271 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `InceptionB._forward` | 273–283 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `InceptionB.forward` | 285–287 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `BasicConv2d.__init__` | 465–473 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `BasicConv2d.forward` | 475–478 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |

完整片段与 E### 编号由生成时的 `source_evidence.json`、`source_map.md`保存；图上的E###指向符号范围，不能把一个范围编号当成该节点的逐行自动推理结果。

## 图中算子与参数身份

| 稳定节点 / 图框标签 | 源码操作与配置 | 声明输出 shape | 参数属性路径 |
|---|---|---|---|
| `inception_reduction.branch3x3.conv` / Conv 3 / 288→384 | `conv`；kernel_size=3；stride=2；padding=0；dilation=1；groups=1；bias=False | `[B,384,17,17]` | `branch3x3.conv` |
| `inception_reduction.branch3x3.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,384,17,17]` | `branch3x3.bn` |
| `inception_reduction.branch3x3.relu` / ReLU | `relu`；inplace=True | `[B,384,17,17]` | `无学习参数` |
| `inception_reduction.branch3x3dbl_1.conv` / Conv 1 / 288→64 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,64,35,35]` | `branch3x3dbl_1.conv` |
| `inception_reduction.branch3x3dbl_1.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,64,35,35]` | `branch3x3dbl_1.bn` |
| `inception_reduction.branch3x3dbl_1.relu` / ReLU | `relu`；inplace=True | `[B,64,35,35]` | `无学习参数` |
| `inception_reduction.branch3x3dbl_2.conv` / Conv 3 / 64→96 | `conv`；kernel_size=3；stride=1；padding=1；dilation=1；groups=1；bias=False | `[B,96,35,35]` | `branch3x3dbl_2.conv` |
| `inception_reduction.branch3x3dbl_2.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,96,35,35]` | `branch3x3dbl_2.bn` |
| `inception_reduction.branch3x3dbl_2.relu` / ReLU | `relu`；inplace=True | `[B,96,35,35]` | `无学习参数` |
| `inception_reduction.branch3x3dbl_3.conv` / Conv 3 / 96→96 | `conv`；kernel_size=3；stride=2；padding=0；dilation=1；groups=1；bias=False | `[B,96,17,17]` | `branch3x3dbl_3.conv` |
| `inception_reduction.branch3x3dbl_3.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,96,17,17]` | `branch3x3dbl_3.bn` |
| `inception_reduction.branch3x3dbl_3.relu` / ReLU | `relu`；inplace=True | `[B,96,17,17]` | `无学习参数` |
| `inception_reduction.branch_pool.pool` / maxPool 3 / 2 | `pool`；kernel_size=3；stride=2；padding=0；pool_type=max | `[B,288,17,17]` | `无学习参数` |
| `inception_reduction.concat` / Concat channel dim=1 | `concat`；dim=1 | `[B,768,17,17]` | `无学习参数` |

不同属性路径对应不同实例；同色同形状不自动表示共享参数。BN的affine参数与running-stat buffer分别理解。未提供自定义替代block，本选例只针对固定源码与以上构造。

## 三粒度与排布理由

按源码outputs列表横排三路。所有长短路从同一x扇出，详细图保留中路三套BasicConv；短路从底部开始，较长接线连接顶端收集总线。降采样发生在stride2 Conv/MaxPool节点，不能把尺寸变化归给Concat。

三粒度复用同一语义IR。`chain.items`按执行先后声明，由共享布局引擎反转画面y方向，实现内部与总体自底向上；`parallel.items`保持源码列表顺序，收集本身不执行tensor合并，Concat/Add必须另有真实节点。graph布局只声明rank/列对齐，数据依赖必须显式提供，不能从视觉相邻自动推断。

字体使用DejaVu Sans/Arial，深色边框；粉色输入、蓝色卷积/张量、黄色BN/Concat/Add、绿色Pool、紫色输出/参数，具体角色见生成的 `visual_style.json`。宽高来自标题、shape、证据文本和子容器测量；间距、转弯槽、箭头末段由共享引擎计算，不来自源码中的坐标。每条边保留语义端口，折叠视图映射到最近可见容器；上游kernel无Python内部证据时保持边界，而不为“更详细”虚造节点。

## 生成与验证

正式合并后，在专题目录运行：

```bash
python3 generate.py --module inception_reduction --png
python3 checks/vision_extended.py
```

适配器合并前可单独预览：

```bash
python3 staging/preview_module.py inception_reduction \
  --manifest staging/vision_source_manifest.json --out /tmp/module-vision-extended
```

输出的SVG可以继续编辑，但应修改适配器/布局再重新生成以保持源码、IR、图像同步。独立 `checks/vision_extended.py` 读取真实AST校验构造、branch选择、操作数和真实顺序；另有全部声明一致性guard。每例至少删除/交换真实依赖端点的负例，并验证shape、operator与参数身份错误能被拒绝。三个视图均检查边界、包含、正交路线、末段转弯空间、上行主流、避开边框与算子内部、文本范围和不同辅助张量的路线分离。PNG还需目视复查。

这些校验针对上述固定snapshot/选例，不代表任意源码自动提取、数值结果正确或所有运行时配置已验证。相邻版本、custom block、输入shape或条件分支变化均需重新取证和独立合同。
