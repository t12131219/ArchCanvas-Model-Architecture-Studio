# ShuffleNetV2 stride1：分割、保留与独立学习路

本例只绘制 `One ShuffleNetV2 InvertedResidual only`，不新增完整模型。固定来源为 [pytorch/vision](https://github.com/pytorch/vision)，commit `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。源码经 AST 读取与 SHA256/Git blob 核对，未导入、执行模型、下载权重或运行 C++/CUDA kernel。

本例明确声明构造 `InvertedResidual(24,24,stride=1)`，输入 `[B,24,16,16]`，输出 `[B,24,16,16]`。shape 是选例与静态公式的推导，不是一次实际forward观测；含BN/Dropout的路径由调用方train/eval决定。

选 `InvertedResidual(24,24,1)`，16×16保持。真实 `x.chunk(2,dim=1)` 产生x1/x2两个12通道值；x1直接保留，branch2只接x2。branch2实际Sequential为Conv1→BN→ReLU→depthwiseConv3 groups12 stride1→BN→Conv1→BN→ReLU。Concat(x1,branch2(x2))按channel轴恢复24，再channel_shuffle(groups2)。

stride1构造branch1是空Sequential，forward没有调用它，因此图中不画一个学习branch1。所有Conv biasFalse，BN eps使用默认1e-5；branch2真实索引0/1/3/4/5/6对应独立参数。无MobileNet residualAdd、expansionRatio或shortcut。shuffle内部已在独立ChannelShuffle例展开，本例保留函数调用边界。

## 源码证据范围

| 符号 | 本固定文件行号 | 原文件 |
|---|---|---|
| `InvertedResidual` | 37–96 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py) |
| `InvertedResidual.__init__` | 38–74 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py) |
| `InvertedResidual.depthwise_conv` | 77–85 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py) |
| `InvertedResidual.forward` | 87–96 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py) |
| `channel_shuffle` | 21–34 | [固定源码](../sources/torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py) |

完整片段与 E### 编号由生成时的 `source_evidence.json`、`source_map.md`保存；图上的E###指向符号范围，不能把一个范围编号当成该节点的逐行自动推理结果。

## 图中算子与参数身份

| 稳定节点 / 图框标签 | 源码操作与配置 | 声明输出 shape | 参数属性路径 |
|---|---|---|---|
| `shuffle_ir_stride1.chunk` / Chunk channel dim1 into2 | `chunk`；dim=1 | `2 tensors [B,12,16,16]` | `无学习参数` |
| `shuffle_ir_stride1.retained` / Retain x1 / no learned branch1 | `identity`； | `[B,12,16,16]` | `无学习参数` |
| `shuffle_ir_stride1.b2.conv1` / Conv 1 / 12→12 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,12,16,16]` | `branch2.0` |
| `shuffle_ir_stride1.b2.bn1` / BatchNorm | `batch_norm2d`；eps=1e-05 | `[B,12,16,16]` | `branch2.1` |
| `shuffle_ir_stride1.b2.relu1` / ReLU | `relu`；inplace=True | `[B,12,16,16]` | `无学习参数` |
| `shuffle_ir_stride1.b2.dw` / Depthwise Conv3 / C=12 | `conv`；kernel_size=3；stride=1；padding=1；dilation=1；groups=12；bias=False | `[B,12,16,16]` | `branch2.3` |
| `shuffle_ir_stride1.b2.bn2` / BatchNorm | `batch_norm2d`；eps=1e-05 | `[B,12,16,16]` | `branch2.4` |
| `shuffle_ir_stride1.b2.project` / Conv 1 / 12→12 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,12,16,16]` | `branch2.5` |
| `shuffle_ir_stride1.b2.bn3` / BatchNorm | `batch_norm2d`；eps=1e-05 | `[B,12,16,16]` | `branch2.6` |
| `shuffle_ir_stride1.b2.relu2` / ReLU | `relu`；inplace=True | `[B,12,16,16]` | `无学习参数` |
| `shuffle_ir_stride1.concat` / Concat channel dim=1 | `concat`；dim=1 | `[B,24,16,16]` | `无学习参数` |
| `shuffle_ir_stride1.shuffle` / channel_shuffle / groups=2 | `channel_shuffle`；groups=2 | `[B,24,16,16]` | `无学习参数` |

不同属性路径对应不同实例；同色同形状不自动表示共享参数。BN的affine参数与running-stat buffer分别理解。未提供自定义替代block，本选例只针对固定源码与以上构造。

## 三粒度与排布理由

先chunk后dispatch：从同一容器的item[0]/item[1]端口接保留路/学习路，不能误用相同x的fork。详细图展开branch2八操作；左侧保留路短而非空缺计算，最后channelConcat和shuffle在主轴依次上行。

三粒度复用同一语义IR。`chain.items`按执行先后声明，由共享布局引擎反转画面y方向，实现内部与总体自底向上；`parallel.items`保持源码列表顺序，收集本身不执行tensor合并，Concat/Add必须另有真实节点。graph布局只声明rank/列对齐，数据依赖必须显式提供，不能从视觉相邻自动推断。

字体使用DejaVu Sans/Arial，深色边框；粉色输入、蓝色卷积/张量、黄色BN/Concat/Add、绿色Pool、紫色输出/参数，具体角色见生成的 `visual_style.json`。宽高来自标题、shape、证据文本和子容器测量；间距、转弯槽、箭头末段由共享引擎计算，不来自源码中的坐标。每条边保留语义端口，折叠视图映射到最近可见容器；上游kernel无Python内部证据时保持边界，而不为“更详细”虚造节点。

## 生成与验证

正式合并后，在专题目录运行：

```bash
python3 generate.py --module shuffle_ir_stride1 --png
python3 checks/vision_extended.py
```

适配器合并前可单独预览：

```bash
python3 staging/preview_module.py shuffle_ir_stride1 \
  --manifest staging/vision_source_manifest.json --out /tmp/module-vision-extended
```

输出的SVG可以继续编辑，但应修改适配器/布局再重新生成以保持源码、IR、图像同步。独立 `checks/vision_extended.py` 读取真实AST校验构造、branch选择、操作数和真实顺序；另有全部声明一致性guard。每例至少删除/交换真实依赖端点的负例，并验证shape、operator与参数身份错误能被拒绝。三个视图均检查边界、包含、正交路线、末段转弯空间、上行主流、避开边框与算子内部、文本范围和不同辅助张量的路线分离。PNG还需目视复查。

这些校验针对上述固定snapshot/选例，不代表任意源码自动提取、数值结果正确或所有运行时配置已验证。相邻版本、custom block、输入shape或条件分支变化均需重新取证和独立合同。
