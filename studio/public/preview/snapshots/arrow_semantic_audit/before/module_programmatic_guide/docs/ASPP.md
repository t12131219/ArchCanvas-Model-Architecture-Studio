# ASPP：空洞卷积、全局上下文与投影

本例只绘制 `ASPP only; no DeepLabHead/backbone`，不新增完整模型。固定来源为 [pytorch/vision](https://github.com/pytorch/vision)，commit `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。源码经 AST 读取与 SHA256/Git blob 核对，未导入、执行模型、下载权重或运行 C++/CUDA kernel。

本例明确声明构造 `ASPP(256,[6,12,18],out_channels=64)`，输入 `[B,256,32,32]`，输出 `[B,64,32,32]`。shape 是选例与静态公式的推导，不是一次实际forward观测；含BN/Dropout的路径由调用方train/eval决定。

本例显式选 `ASPP(256,[6,12,18],out_channels=64)`。源码 DeepLabHead 实际传 rates12/24/36、ASPP 默认宽256；这里不把选例配置说成完整 DeepLab 默认值。五条分支同读输入：pointwise1×1，三个3×3空洞卷积(dilation/padding分别6/12/18)，以及 AdaptiveAvgPool1→Conv1→BN→ReLU→bilinear resize。所有分支卷积 bias=False；每条路径输出64通道，Concat320后 project Conv1→BN→ReLU→Dropout(.5)。

全局路径的 resize 显式 `align_corners=False`，target H/W 保存自原输入。Dropout 与 BN 的 train/eval 行为取决于调用方；静态选例未执行。每个 `convs.i` 独立拥有权重，三种 rate 不能仅用同色图块来省略真实 dilation。

## 源码证据范围

| 符号 | 本固定文件行号 | 原文件 |
|---|---|---|
| `ASPP` | 65–93 | [固定源码](../sources/torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py) |
| `ASPP.__init__` | 66–86 | [固定源码](../sources/torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py) |
| `ASPP.forward` | 88–93 | [固定源码](../sources/torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py) |
| `ASPPConv.__init__` | 41–47 | [固定源码](../sources/torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py) |
| `ASPPPooling.__init__` | 51–56 | [固定源码](../sources/torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py) |
| `ASPPPooling.forward` | 58–62 | [固定源码](../sources/torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py) |

完整片段与 E### 编号由生成时的 `source_evidence.json`、`source_map.md`保存；图上的E###指向符号范围，不能把一个范围编号当成该节点的逐行自动推理结果。

## 图中算子与参数身份

| 稳定节点 / 图框标签 | 源码操作与配置 | 声明输出 shape | 参数属性路径 |
|---|---|---|---|
| `aspp.pointwise.conv` / Conv 1 / 256→64 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,64,32,32]` | `convs.0.0` |
| `aspp.pointwise.bn` / BatchNorm | `batch_norm2d`；eps=1e-05 | `[B,64,32,32]` | `convs.0.1` |
| `aspp.pointwise.relu` / ReLU | `relu`；inplace=False | `[B,64,32,32]` | `无学习参数` |
| `aspp.rate6.conv` / Conv 3 / 256→64 | `conv`；kernel_size=3；stride=1；padding=6；dilation=6；groups=1；bias=False | `[B,64,32,32]` | `convs.1.0` |
| `aspp.rate6.bn` / BatchNorm | `batch_norm2d`；eps=1e-05 | `[B,64,32,32]` | `convs.1.1` |
| `aspp.rate6.relu` / ReLU | `relu`；inplace=False | `[B,64,32,32]` | `无学习参数` |
| `aspp.rate12.conv` / Conv 3 / 256→64 | `conv`；kernel_size=3；stride=1；padding=12；dilation=12；groups=1；bias=False | `[B,64,32,32]` | `convs.2.0` |
| `aspp.rate12.bn` / BatchNorm | `batch_norm2d`；eps=1e-05 | `[B,64,32,32]` | `convs.2.1` |
| `aspp.rate12.relu` / ReLU | `relu`；inplace=False | `[B,64,32,32]` | `无学习参数` |
| `aspp.rate18.conv` / Conv 3 / 256→64 | `conv`；kernel_size=3；stride=1；padding=18；dilation=18；groups=1；bias=False | `[B,64,32,32]` | `convs.3.0` |
| `aspp.rate18.bn` / BatchNorm | `batch_norm2d`；eps=1e-05 | `[B,64,32,32]` | `convs.3.1` |
| `aspp.rate18.relu` / ReLU | `relu`；inplace=False | `[B,64,32,32]` | `无学习参数` |
| `aspp.pool` / Adaptive average pool1 | `pool`；pool_type=adaptive_average；output_size=1 | `[B,256,1,1]` | `无学习参数` |
| `aspp.pool_conv` / Conv 1 / 256→64 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,64,1,1]` | `convs.4.1` |
| `aspp.pool_bn` / BatchNorm | `batch_norm2d`；eps=1e-05 | `[B,64,1,1]` | `convs.4.2` |
| `aspp.pool_relu` / ReLU | `relu`；inplace=False | `[B,64,1,1]` | `无学习参数` |
| `aspp.resize` / Bilinear resize to input H,W | `interpolate`；mode_argument=bilinear；align_corners=False | `[B,64,32,32]` | `无学习参数` |
| `aspp.concat` / Concat all5 paths | `concat`；dim=1 | `[B,320,32,32]` | `无学习参数` |
| `aspp.project.conv` / Conv 1 / 320→64 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,64,32,32]` | `project.0` |
| `aspp.project.bn` / BatchNorm | `batch_norm2d`；eps=1e-05 | `[B,64,32,32]` | `project.1` |
| `aspp.project.relu` / ReLU | `relu`；inplace=False | `[B,64,32,32]` | `无学习参数` |
| `aspp.dropout` / Dropout p=0.5 | `dropout`； | `[B,64,32,32]` | `无学习参数` |

不同属性路径对应不同实例；同色同形状不自动表示共享参数。BN的affine参数与running-stat buffer分别理解。未提供自定义替代block，本选例只针对固定源码与以上构造。

## 三粒度与排布理由

原输入的 H/W 通过实际 `input:shape → resize:size` 的虚线shape依赖传入，上采样读取的是池化前/resize前的原空间尺寸。PSP多尺度的四条resize分别保留该端口，PSPUpsample再按源码乘2；这条旁路只供size元数据，不替代张量主流。

模块图横排五条分支，标签明确 pointwise、rate6、rate12、rate18、global pool。详细图把各 Conv/BN/ReLU 和 pool/resize 展开为自底向上，短路不拉伸为伪算子。global 路径最长决定容器高度；branch宽度和各自文本计算横向位置。concat 后 project仍在主轴上。

三粒度复用同一语义IR。`chain.items`按执行先后声明，由共享布局引擎反转画面y方向，实现内部与总体自底向上；`parallel.items`保持源码列表顺序，收集本身不执行tensor合并，Concat/Add必须另有真实节点。graph布局只声明rank/列对齐，数据依赖必须显式提供，不能从视觉相邻自动推断。

字体使用DejaVu Sans/Arial，深色边框；粉色输入、蓝色卷积/张量、黄色BN/Concat/Add、绿色Pool、紫色输出/参数，具体角色见生成的 `visual_style.json`。宽高来自标题、shape、证据文本和子容器测量；间距、转弯槽、箭头末段由共享引擎计算，不来自源码中的坐标。每条边保留语义端口，折叠视图映射到最近可见容器；上游kernel无Python内部证据时保持边界，而不为“更详细”虚造节点。

## 生成与验证

正式合并后，在专题目录运行：

```bash
python3 generate.py --module aspp --png
python3 checks/vision_extended.py
```

适配器合并前可单独预览：

```bash
python3 staging/preview_module.py aspp \
  --manifest staging/vision_source_manifest.json --out /tmp/module-vision-extended
```

输出的SVG可以继续编辑，但应修改适配器/布局再重新生成以保持源码、IR、图像同步。独立 `checks/vision_extended.py` 读取真实AST校验构造、branch选择、操作数和真实顺序；另有全部声明一致性guard。每例至少删除/交换真实依赖端点的负例，并验证shape、operator与参数身份错误能被拒绝。三个视图均检查边界、包含、正交路线、末段转弯空间、上行主流、避开边框与算子内部、文本范围和不同辅助张量的路线分离。PNG还需目视复查。

这些校验针对上述固定snapshot/选例，不代表任意源码自动提取、数值结果正确或所有运行时配置已验证。相邻版本、custom block、输入shape或条件分支变化均需重新取证和独立合同。
