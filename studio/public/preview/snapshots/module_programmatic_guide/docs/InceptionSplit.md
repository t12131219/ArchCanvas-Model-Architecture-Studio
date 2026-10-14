# InceptionE：两组分支内核拆分与三次Concat

本例只绘制 `InceptionE only; no complete Inception network`，不新增完整模型。固定来源为 [pytorch/vision](https://github.com/pytorch/vision)，commit `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。源码经 AST 读取与 SHA256/Git blob 核对，未导入、执行模型、下载权重或运行 C++/CUDA kernel。

本例明确声明构造 `InceptionE(1280)`，输入 `[B,1280,8,8]`，输出 `[B,2048,8,8]`。shape 是选例与静态公式的推导，不是一次实际forward观测；含BN/Dropout的路径由调用方train/eval决定。

选 `InceptionE(1280)`，8×8保持，四路最终输出320/768/768/192，合成2048通道。左路1×1→320。第二路1×1→384后，同一个中间值 **并行** 输入1×3与3×1(各384)，内部Concat得768。第三路1×1→448、3×3→384后同样并行拆分，内部Concat768。第四路AvgPool3 stride1 padding1→1×1(192)。

源码两次list赋值后各一次torch.cat，再四路最终cat，共 **3个Concat**。1×3与3×1不串联；`.2a/.2b`或`.3a/.3b`参数路径必须保持独立。9套BasicConv实际Conv无bias→BN eps.001→inplace ReLU。

## 源码证据范围

| 符号 | 本固定文件行号 | 原文件 |
|---|---|---|
| `InceptionE` | 376–425 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `InceptionE.__init__` | 378–397 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `InceptionE._forward` | 399–421 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `InceptionE.forward` | 423–425 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `BasicConv2d.__init__` | 465–473 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `BasicConv2d.forward` | 475–478 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |

完整片段与 E### 编号由生成时的 `source_evidence.json`、`source_map.md`保存；图上的E###指向符号范围，不能把一个范围编号当成该节点的逐行自动推理结果。

## 图中算子与参数身份

| 稳定节点 / 图框标签 | 源码操作与配置 | 声明输出 shape | 参数属性路径 |
|---|---|---|---|
| `inception_split.branch1x1.conv` / Conv 1 / 1280→320 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,320,8,8]` | `branch1x1.conv` |
| `inception_split.branch1x1.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,320,8,8]` | `branch1x1.bn` |
| `inception_split.branch1x1.relu` / ReLU | `relu`；inplace=True | `[B,320,8,8]` | `无学习参数` |
| `inception_split.branch3x3_1.conv` / Conv 1 / 1280→384 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,384,8,8]` | `branch3x3_1.conv` |
| `inception_split.branch3x3_1.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,384,8,8]` | `branch3x3_1.bn` |
| `inception_split.branch3x3_1.relu` / ReLU | `relu`；inplace=True | `[B,384,8,8]` | `无学习参数` |
| `inception_split.branch3x3_2a.conv` / Conv (1, 3) / 384→384 | `conv`；kernel_size=(1, 3)；stride=1；padding=(0, 1)；dilation=1；groups=1；bias=False | `[B,384,8,8]` | `branch3x3_2a.conv` |
| `inception_split.branch3x3_2a.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,384,8,8]` | `branch3x3_2a.bn` |
| `inception_split.branch3x3_2a.relu` / ReLU | `relu`；inplace=True | `[B,384,8,8]` | `无学习参数` |
| `inception_split.branch3x3_2b.conv` / Conv (3, 1) / 384→384 | `conv`；kernel_size=(3, 1)；stride=1；padding=(1, 0)；dilation=1；groups=1；bias=False | `[B,384,8,8]` | `branch3x3_2b.conv` |
| `inception_split.branch3x3_2b.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,384,8,8]` | `branch3x3_2b.bn` |
| `inception_split.branch3x3_2b.relu` / ReLU | `relu`；inplace=True | `[B,384,8,8]` | `无学习参数` |
| `inception_split.branch3x3.concat` / Concat split outputs | `concat`；dim=1 | `[B,768,8,8]` | `无学习参数` |
| `inception_split.branch3x3dbl_1.conv` / Conv 1 / 1280→448 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,448,8,8]` | `branch3x3dbl_1.conv` |
| `inception_split.branch3x3dbl_1.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,448,8,8]` | `branch3x3dbl_1.bn` |
| `inception_split.branch3x3dbl_1.relu` / ReLU | `relu`；inplace=True | `[B,448,8,8]` | `无学习参数` |
| `inception_split.branch3x3dbl_2.conv` / Conv 3 / 448→384 | `conv`；kernel_size=3；stride=1；padding=1；dilation=1；groups=1；bias=False | `[B,384,8,8]` | `branch3x3dbl_2.conv` |
| `inception_split.branch3x3dbl_2.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,384,8,8]` | `branch3x3dbl_2.bn` |
| `inception_split.branch3x3dbl_2.relu` / ReLU | `relu`；inplace=True | `[B,384,8,8]` | `无学习参数` |
| `inception_split.branch3x3dbl_3a.conv` / Conv (1, 3) / 384→384 | `conv`；kernel_size=(1, 3)；stride=1；padding=(0, 1)；dilation=1；groups=1；bias=False | `[B,384,8,8]` | `branch3x3dbl_3a.conv` |
| `inception_split.branch3x3dbl_3a.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,384,8,8]` | `branch3x3dbl_3a.bn` |
| `inception_split.branch3x3dbl_3a.relu` / ReLU | `relu`；inplace=True | `[B,384,8,8]` | `无学习参数` |
| `inception_split.branch3x3dbl_3b.conv` / Conv (3, 1) / 384→384 | `conv`；kernel_size=(3, 1)；stride=1；padding=(1, 0)；dilation=1；groups=1；bias=False | `[B,384,8,8]` | `branch3x3dbl_3b.conv` |
| `inception_split.branch3x3dbl_3b.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,384,8,8]` | `branch3x3dbl_3b.bn` |
| `inception_split.branch3x3dbl_3b.relu` / ReLU | `relu`；inplace=True | `[B,384,8,8]` | `无学习参数` |
| `inception_split.branch3x3dbl.concat` / Concat split outputs | `concat`；dim=1 | `[B,768,8,8]` | `无学习参数` |
| `inception_split.branch_pool.pool` / averagePool 3 / 1 | `pool`；kernel_size=3；stride=1；padding=1；pool_type=average | `[B,1280,8,8]` | `无学习参数` |
| `inception_split.branch_pool.conv` / Conv 1 / 1280→192 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,192,8,8]` | `branch_pool.conv` |
| `inception_split.branch_pool.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,192,8,8]` | `branch_pool.bn` |
| `inception_split.branch_pool.relu` / ReLU | `relu`；inplace=True | `[B,192,8,8]` | `无学习参数` |
| `inception_split.concat` / Concat channel dim=1 | `concat`；dim=1 | `[B,2048,8,8]` | `无学习参数` |

不同属性路径对应不同实例；同色同形状不自动表示共享参数。BN的affine参数与running-stat buffer分别理解。未提供自定义替代block，本选例只针对固定源码与以上构造。

## 三粒度与排布理由

外层横排四路，第二、第三路容器内各有一层parallel，内部上方放真正Concat，再接外层收集总线。模块图已经保留内嵌拆分和Concat；详细图展开BasicConv。内层并列表达共享同一前驱，与外层四路同读x是两个不同层次。

三粒度复用同一语义IR。`chain.items`按执行先后声明，由共享布局引擎反转画面y方向，实现内部与总体自底向上；`parallel.items`保持源码列表顺序，收集本身不执行tensor合并，Concat/Add必须另有真实节点。graph布局只声明rank/列对齐，数据依赖必须显式提供，不能从视觉相邻自动推断。

字体使用DejaVu Sans/Arial，深色边框；粉色输入、蓝色卷积/张量、黄色BN/Concat/Add、绿色Pool、紫色输出/参数，具体角色见生成的 `visual_style.json`。宽高来自标题、shape、证据文本和子容器测量；间距、转弯槽、箭头末段由共享引擎计算，不来自源码中的坐标。每条边保留语义端口，折叠视图映射到最近可见容器；上游kernel无Python内部证据时保持边界，而不为“更详细”虚造节点。

## 生成与验证

正式合并后，在专题目录运行：

```bash
python3 generate.py --module inception_split --png
python3 checks/vision_extended.py
```

适配器合并前可单独预览：

```bash
python3 staging/preview_module.py inception_split \
  --manifest staging/vision_source_manifest.json --out /tmp/module-vision-extended
```

输出的SVG可以继续编辑，但应修改适配器/布局再重新生成以保持源码、IR、图像同步。独立 `checks/vision_extended.py` 读取真实AST校验构造、branch选择、操作数和真实顺序；另有全部声明一致性guard。每例至少删除/交换真实依赖端点的负例，并验证shape、operator与参数身份错误能被拒绝。三个视图均检查边界、包含、正交路线、末段转弯空间、上行主流、避开边框与算子内部、文本范围和不同辅助张量的路线分离。PNG还需目视复查。

这些校验针对上述固定snapshot/选例，不代表任意源码自动提取、数值结果正确或所有运行时配置已验证。相邻版本、custom block、输入shape或条件分支变化均需重新取证和独立合同。
