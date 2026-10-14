# InceptionC：1×7与7×1因式卷积

本例只绘制 `InceptionC only; no complete Inception network`，不新增完整模型。固定来源为 [pytorch/vision](https://github.com/pytorch/vision)，commit `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。源码经 AST 读取与 SHA256/Git blob 核对，未导入、执行模型、下载权重或运行 C++/CUDA kernel。

本例明确声明构造 `InceptionC(768,channels_7x7=128)`，输入 `[B,768,17,17]`，输出 `[B,768,17,17]`。shape 是选例与静态公式的推导，不是一次实际forward观测；含BN/Dropout的路径由调用方train/eval决定。

选定 `InceptionC(768,channels_7x7=128)`，输入输出均17×17与768通道。四路输出各192：单1×1；1×1→1×7→7×1；1×1→7×1→1×7→7×1→1×7；AvgPool3 stride1 padding1→1×1。第二与第三路中间宽度c7=128。输出按源码四路列表Concat(dim1)，不是Add。

因式核使用精确 `(1,7)/(7,1)` 与 `(0,3)/(3,0)` padding，非7×7方核或两个可交换的同一算子。每份BasicConv仍为Conv无bias、BN eps.001、inplace ReLU；不同属性独立。

## 源码证据范围

| 符号 | 本固定文件行号 | 原文件 |
|---|---|---|
| `InceptionC` | 290–337 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `InceptionC.__init__` | 292–314 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `InceptionC._forward` | 316–333 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `InceptionC.forward` | 335–337 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `BasicConv2d.__init__` | 465–473 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `BasicConv2d.forward` | 475–478 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |

完整片段与 E### 编号由生成时的 `source_evidence.json`、`source_map.md`保存；图上的E###指向符号范围，不能把一个范围编号当成该节点的逐行自动推理结果。

## 图中算子与参数身份

| 稳定节点 / 图框标签 | 源码操作与配置 | 声明输出 shape | 参数属性路径 |
|---|---|---|---|
| `inception_factorized.branch1x1.conv` / Conv 1 / 768→192 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,192,17,17]` | `branch1x1.conv` |
| `inception_factorized.branch1x1.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,192,17,17]` | `branch1x1.bn` |
| `inception_factorized.branch1x1.relu` / ReLU | `relu`；inplace=True | `[B,192,17,17]` | `无学习参数` |
| `inception_factorized.branch7x7_1.conv` / Conv 1 / 768→128 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,128,17,17]` | `branch7x7_1.conv` |
| `inception_factorized.branch7x7_1.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,128,17,17]` | `branch7x7_1.bn` |
| `inception_factorized.branch7x7_1.relu` / ReLU | `relu`；inplace=True | `[B,128,17,17]` | `无学习参数` |
| `inception_factorized.branch7x7_2.conv` / Conv (1, 7) / 128→128 | `conv`；kernel_size=(1, 7)；stride=1；padding=(0, 3)；dilation=1；groups=1；bias=False | `[B,128,17,17]` | `branch7x7_2.conv` |
| `inception_factorized.branch7x7_2.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,128,17,17]` | `branch7x7_2.bn` |
| `inception_factorized.branch7x7_2.relu` / ReLU | `relu`；inplace=True | `[B,128,17,17]` | `无学习参数` |
| `inception_factorized.branch7x7_3.conv` / Conv (7, 1) / 128→192 | `conv`；kernel_size=(7, 1)；stride=1；padding=(3, 0)；dilation=1；groups=1；bias=False | `[B,192,17,17]` | `branch7x7_3.conv` |
| `inception_factorized.branch7x7_3.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,192,17,17]` | `branch7x7_3.bn` |
| `inception_factorized.branch7x7_3.relu` / ReLU | `relu`；inplace=True | `[B,192,17,17]` | `无学习参数` |
| `inception_factorized.branch7x7dbl_1.conv` / Conv 1 / 768→128 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,128,17,17]` | `branch7x7dbl_1.conv` |
| `inception_factorized.branch7x7dbl_1.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,128,17,17]` | `branch7x7dbl_1.bn` |
| `inception_factorized.branch7x7dbl_1.relu` / ReLU | `relu`；inplace=True | `[B,128,17,17]` | `无学习参数` |
| `inception_factorized.branch7x7dbl_2.conv` / Conv (7, 1) / 128→128 | `conv`；kernel_size=(7, 1)；stride=1；padding=(3, 0)；dilation=1；groups=1；bias=False | `[B,128,17,17]` | `branch7x7dbl_2.conv` |
| `inception_factorized.branch7x7dbl_2.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,128,17,17]` | `branch7x7dbl_2.bn` |
| `inception_factorized.branch7x7dbl_2.relu` / ReLU | `relu`；inplace=True | `[B,128,17,17]` | `无学习参数` |
| `inception_factorized.branch7x7dbl_3.conv` / Conv (1, 7) / 128→128 | `conv`；kernel_size=(1, 7)；stride=1；padding=(0, 3)；dilation=1；groups=1；bias=False | `[B,128,17,17]` | `branch7x7dbl_3.conv` |
| `inception_factorized.branch7x7dbl_3.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,128,17,17]` | `branch7x7dbl_3.bn` |
| `inception_factorized.branch7x7dbl_3.relu` / ReLU | `relu`；inplace=True | `[B,128,17,17]` | `无学习参数` |
| `inception_factorized.branch7x7dbl_4.conv` / Conv (7, 1) / 128→128 | `conv`；kernel_size=(7, 1)；stride=1；padding=(3, 0)；dilation=1；groups=1；bias=False | `[B,128,17,17]` | `branch7x7dbl_4.conv` |
| `inception_factorized.branch7x7dbl_4.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,128,17,17]` | `branch7x7dbl_4.bn` |
| `inception_factorized.branch7x7dbl_4.relu` / ReLU | `relu`；inplace=True | `[B,128,17,17]` | `无学习参数` |
| `inception_factorized.branch7x7dbl_5.conv` / Conv (1, 7) / 128→192 | `conv`；kernel_size=(1, 7)；stride=1；padding=(0, 3)；dilation=1；groups=1；bias=False | `[B,192,17,17]` | `branch7x7dbl_5.conv` |
| `inception_factorized.branch7x7dbl_5.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,192,17,17]` | `branch7x7dbl_5.bn` |
| `inception_factorized.branch7x7dbl_5.relu` / ReLU | `relu`；inplace=True | `[B,192,17,17]` | `无学习参数` |
| `inception_factorized.branch_pool.pool` / averagePool 3 / 1 | `pool`；kernel_size=3；stride=1；padding=1；pool_type=average | `[B,768,17,17]` | `无学习参数` |
| `inception_factorized.branch_pool.conv` / Conv 1 / 768→192 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,192,17,17]` | `branch_pool.conv` |
| `inception_factorized.branch_pool.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,192,17,17]` | `branch_pool.bn` |
| `inception_factorized.branch_pool.relu` / ReLU | `relu`；inplace=True | `[B,192,17,17]` | `无学习参数` |
| `inception_factorized.concat` / Concat channel dim=1 | `concat`；dim=1 | `[B,768,17,17]` | `无学习参数` |

不同属性路径对应不同实例；同色同形状不自动表示共享参数。BN的affine参数与running-stat buffer分别理解。未提供自定义替代block，本选例只针对固定源码与以上构造。

## 三粒度与排布理由

五BasicConv长路会使完全展开高度过大，详细视图保留前3个BasicConv折叠、展开最后2个；折叠只改变画面，不从IR移除内部Conv/BN/ReLU。源码取证与参数身份覆盖全部10套BasicConv。其他路径完整展开；各支路顺序保持outputs列表。

三粒度复用同一语义IR。`chain.items`按执行先后声明，由共享布局引擎反转画面y方向，实现内部与总体自底向上；`parallel.items`保持源码列表顺序，收集本身不执行tensor合并，Concat/Add必须另有真实节点。graph布局只声明rank/列对齐，数据依赖必须显式提供，不能从视觉相邻自动推断。

字体使用DejaVu Sans/Arial，深色边框；粉色输入、蓝色卷积/张量、黄色BN/Concat/Add、绿色Pool、紫色输出/参数，具体角色见生成的 `visual_style.json`。宽高来自标题、shape、证据文本和子容器测量；间距、转弯槽、箭头末段由共享引擎计算，不来自源码中的坐标。每条边保留语义端口，折叠视图映射到最近可见容器；上游kernel无Python内部证据时保持边界，而不为“更详细”虚造节点。

## 生成与验证

正式合并后，在专题目录运行：

```bash
python3 generate.py --module inception_factorized --png
python3 checks/vision_extended.py
```

适配器合并前可单独预览：

```bash
python3 staging/preview_module.py inception_factorized \
  --manifest staging/vision_source_manifest.json --out /tmp/module-vision-extended
```

输出的SVG可以继续编辑，但应修改适配器/布局再重新生成以保持源码、IR、图像同步。独立 `checks/vision_extended.py` 读取真实AST校验构造、branch选择、操作数和真实顺序；另有全部声明一致性guard。每例至少删除/交换真实依赖端点的负例，并验证shape、operator与参数身份错误能被拒绝。三个视图均检查边界、包含、正交路线、末段转弯空间、上行主流、避开边框与算子内部、文本范围和不同辅助张量的路线分离。PNG还需目视复查。

这些校验针对上述固定snapshot/选例，不代表任意源码自动提取、数值结果正确或所有运行时配置已验证。相邻版本、custom block、输入shape或条件分支变化均需重新取证和独立合同。
