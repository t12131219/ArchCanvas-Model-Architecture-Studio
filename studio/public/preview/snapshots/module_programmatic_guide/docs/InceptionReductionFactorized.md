# InceptionD：因式卷积后的降采样

本例只绘制 `InceptionD only; no complete Inception network`，不新增完整模型。固定来源为 [pytorch/vision](https://github.com/pytorch/vision)，commit `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。源码经 AST 读取与 SHA256/Git blob 核对，未导入、执行模型、下载权重或运行 C++/CUDA kernel。

本例明确声明构造 `InceptionD(768)`，输入 `[B,768,17,17]`，输出 `[B,1280,8,8]`。shape 是选例与静态公式的推导，不是一次实际forward观测；含BN/Dropout的路径由调用方train/eval决定。

选定 `InceptionD(768)`，17×17→8×8。三路：1×1 `768→192`→3×3 stride2 `192→320`；1×1 `768→192`→1×7→7×1→3×3 stride2(均192)；MaxPool3 stride2保持768。Concat按源码顺序合成1280通道。

1×7/7×1在降采样前保持17×17，最后3×3 stride2且padding0才变8×8。所有6套BasicConv分别持有Conv与BN属性；BN eps=.001、ReLU inplace。

## 源码证据范围

| 符号 | 本固定文件行号 | 原文件 |
|---|---|---|
| `InceptionD` | 340–373 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `InceptionD.__init__` | 342–356 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `InceptionD._forward` | 358–369 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `InceptionD.forward` | 371–373 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `BasicConv2d.__init__` | 465–473 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |
| `BasicConv2d.forward` | 475–478 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/inception.py) |

完整片段与 E### 编号由生成时的 `source_evidence.json`、`source_map.md`保存；图上的E###指向符号范围，不能把一个范围编号当成该节点的逐行自动推理结果。

## 图中算子与参数身份

| 稳定节点 / 图框标签 | 源码操作与配置 | 声明输出 shape | 参数属性路径 |
|---|---|---|---|
| `inception_reduction_factorized.branch3x3_1.conv` / Conv 1 / 768→192 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,192,17,17]` | `branch3x3_1.conv` |
| `inception_reduction_factorized.branch3x3_1.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,192,17,17]` | `branch3x3_1.bn` |
| `inception_reduction_factorized.branch3x3_1.relu` / ReLU | `relu`；inplace=True | `[B,192,17,17]` | `无学习参数` |
| `inception_reduction_factorized.branch3x3_2.conv` / Conv 3 / 192→320 | `conv`；kernel_size=3；stride=2；padding=0；dilation=1；groups=1；bias=False | `[B,320,8,8]` | `branch3x3_2.conv` |
| `inception_reduction_factorized.branch3x3_2.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,320,8,8]` | `branch3x3_2.bn` |
| `inception_reduction_factorized.branch3x3_2.relu` / ReLU | `relu`；inplace=True | `[B,320,8,8]` | `无学习参数` |
| `inception_reduction_factorized.branch7x7x3_1.conv` / Conv 1 / 768→192 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,192,17,17]` | `branch7x7x3_1.conv` |
| `inception_reduction_factorized.branch7x7x3_1.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,192,17,17]` | `branch7x7x3_1.bn` |
| `inception_reduction_factorized.branch7x7x3_1.relu` / ReLU | `relu`；inplace=True | `[B,192,17,17]` | `无学习参数` |
| `inception_reduction_factorized.branch7x7x3_2.conv` / Conv (1, 7) / 192→192 | `conv`；kernel_size=(1, 7)；stride=1；padding=(0, 3)；dilation=1；groups=1；bias=False | `[B,192,17,17]` | `branch7x7x3_2.conv` |
| `inception_reduction_factorized.branch7x7x3_2.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,192,17,17]` | `branch7x7x3_2.bn` |
| `inception_reduction_factorized.branch7x7x3_2.relu` / ReLU | `relu`；inplace=True | `[B,192,17,17]` | `无学习参数` |
| `inception_reduction_factorized.branch7x7x3_3.conv` / Conv (7, 1) / 192→192 | `conv`；kernel_size=(7, 1)；stride=1；padding=(3, 0)；dilation=1；groups=1；bias=False | `[B,192,17,17]` | `branch7x7x3_3.conv` |
| `inception_reduction_factorized.branch7x7x3_3.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,192,17,17]` | `branch7x7x3_3.bn` |
| `inception_reduction_factorized.branch7x7x3_3.relu` / ReLU | `relu`；inplace=True | `[B,192,17,17]` | `无学习参数` |
| `inception_reduction_factorized.branch7x7x3_4.conv` / Conv 3 / 192→192 | `conv`；kernel_size=3；stride=2；padding=0；dilation=1；groups=1；bias=False | `[B,192,8,8]` | `branch7x7x3_4.conv` |
| `inception_reduction_factorized.branch7x7x3_4.bn` / BatchNorm | `batch_norm2d`；eps=0.001 | `[B,192,8,8]` | `branch7x7x3_4.bn` |
| `inception_reduction_factorized.branch7x7x3_4.relu` / ReLU | `relu`；inplace=True | `[B,192,8,8]` | `无学习参数` |
| `inception_reduction_factorized.branch_pool.pool` / maxPool 3 / 2 | `pool`；kernel_size=3；stride=2；padding=0；pool_type=max | `[B,768,8,8]` | `无学习参数` |
| `inception_reduction_factorized.concat` / Concat channel dim=1 | `concat`；dim=1 | `[B,1280,8,8]` | `无学习参数` |

不同属性路径对应不同实例；同色同形状不自动表示共享参数。BN的affine参数与running-stat buffer分别理解。未提供自定义替代block，本选例只针对固定源码与以上构造。

## 三粒度与排布理由

三分支横排、各自内部自底向上。详细图完整展开六套BasicConv，右侧Pool短路接长竖线收集；其空白只是不同计算深度，不是丢失卷积或需新增identity算子。

三粒度复用同一语义IR。`chain.items`按执行先后声明，由共享布局引擎反转画面y方向，实现内部与总体自底向上；`parallel.items`保持源码列表顺序，收集本身不执行tensor合并，Concat/Add必须另有真实节点。graph布局只声明rank/列对齐，数据依赖必须显式提供，不能从视觉相邻自动推断。

字体使用DejaVu Sans/Arial，深色边框；粉色输入、蓝色卷积/张量、黄色BN/Concat/Add、绿色Pool、紫色输出/参数，具体角色见生成的 `visual_style.json`。宽高来自标题、shape、证据文本和子容器测量；间距、转弯槽、箭头末段由共享引擎计算，不来自源码中的坐标。每条边保留语义端口，折叠视图映射到最近可见容器；上游kernel无Python内部证据时保持边界，而不为“更详细”虚造节点。

## 生成与验证

正式合并后，在专题目录运行：

```bash
python3 generate.py --module inception_reduction_factorized --png
python3 checks/vision_extended.py
```

适配器合并前可单独预览：

```bash
python3 staging/preview_module.py inception_reduction_factorized \
  --manifest staging/vision_source_manifest.json --out /tmp/module-vision-extended
```

输出的SVG可以继续编辑，但应修改适配器/布局再重新生成以保持源码、IR、图像同步。独立 `checks/vision_extended.py` 读取真实AST校验构造、branch选择、操作数和真实顺序；另有全部声明一致性guard。每例至少删除/交换真实依赖端点的负例，并验证shape、operator与参数身份错误能被拒绝。三个视图均检查边界、包含、正交路线、末段转弯空间、上行主流、避开边框与算子内部、文本范围和不同辅助张量的路线分离。PNG还需目视复查。

这些校验针对上述固定snapshot/选例，不代表任意源码自动提取、数值结果正确或所有运行时配置已验证。相邻版本、custom block、输入shape或条件分支变化均需重新取证和独立合同。
