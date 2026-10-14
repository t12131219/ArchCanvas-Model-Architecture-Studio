# PSPUpsample：双线性插值后的可学习PReLU

本例只绘制 `PSPUpsample only; PSP pooling, enclosing decoder and classifier excluded`，不新增完整模型。固定来源为 [Lextal/pspnet-pytorch](https://github.com/Lextal/pspnet-pytorch)，commit `4eb6ab61287e837f5e2d8c1ae09fadeaa0e31e37`。源码经 AST 读取与 SHA256/Git blob 核对，未导入、执行模型、下载权重或运行 C++/CUDA kernel。

本例明确声明构造 `PSPUpsample(64,32)`，输入 `[B,64,8,8]`，输出 `[B,32,16,16]`。shape 是选例与静态公式的推导，不是一次实际forward观测；含BN/Dropout的路径由调用方train/eval决定。

选 `PSPUpsample(64,32)`，8×8→16×16。源码先计算h,w=2×input空间维度，bilinear F.upsample，再nn.Sequential的Conv3 padding1 `64→32`、BN32、nn.PReLU()。Conv默认biasTrue、BN默认eps1e-5；历史upsample未传align_corners，保留omitted。

PReLU拥有 `conv.2.weight` 形状[1]、初始值0.25，默认num_parameters=1使一个学习斜率共享于全部输出通道。它不是固定ReLU，不是每channel32个参数，也不是与Conv或BN共享参数。空间放大发生在resize而非卷积；此例既不是PixelShuffle也不是ConvTranspose。

## 源码证据范围

| 符号 | 本固定文件行号 | 原文件 |
|---|---|---|
| `PSPUpsample` | 28–40 | [固定源码](../sources/pspnet-vision-extended/pspnet.py) |
| `PSPUpsample.__init__` | 29–35 | [固定源码](../sources/pspnet-vision-extended/pspnet.py) |
| `PSPUpsample.forward` | 37–40 | [固定源码](../sources/pspnet-vision-extended/pspnet.py) |

完整片段与 E### 编号由生成时的 `source_evidence.json`、`source_map.md`保存；图上的E###指向符号范围，不能把一个范围编号当成该节点的逐行自动推理结果。

## 图中算子与参数身份

| 稳定节点 / 图框标签 | 源码操作与配置 | 声明输出 shape | 参数属性路径 |
|---|---|---|---|
| `psp_upsample.resize` / Bilinear resize / 2x H,W | `interpolate`；mode_argument=bilinear；align_corners_argument=omitted | `[B,64,16,16]` | `无学习参数` |
| `psp_upsample.conv_op` / Conv 3 / 64→32 | `conv`；kernel_size=3；stride=1；padding=1；dilation=1；groups=1；bias=True | `[B,32,16,16]` | `conv.0` |
| `psp_upsample.bn` / BatchNorm | `batch_norm2d`；eps=1e-05 | `[B,32,16,16]` | `conv.1` |
| `psp_upsample.prelu` / PReLU / one learned slope | `prelu`；num_parameters=1；initial_slope=0.25 | `[B,32,16,16]` | `conv.2` |

不同属性路径对应不同实例；同色同形状不自动表示共享参数。BN的affine参数与running-stat buffer分别理解。未提供自定义替代block，本选例只针对固定源码与以上构造。

## 三粒度与排布理由

原输入的 H/W 通过实际 `input:shape → resize:size` 的虚线shape依赖传入，上采样读取的是池化前/resize前的原空间尺寸。PSP多尺度的四条resize分别保留该端口，PSPUpsample再按源码乘2；这条旁路只供size元数据，不替代张量主流。

模块图先显示resize后显示Conv/BN/PReLU逻辑组；详细图展开真实Sequential索引0/1/2自底向上。PReLU颜色沿用activation角色，文字和IR精确标出学习身份，不能仅凭灰色推断它无参数。

三粒度复用同一语义IR。`chain.items`按执行先后声明，由共享布局引擎反转画面y方向，实现内部与总体自底向上；`parallel.items`保持源码列表顺序，收集本身不执行tensor合并，Concat/Add必须另有真实节点。graph布局只声明rank/列对齐，数据依赖必须显式提供，不能从视觉相邻自动推断。

字体使用DejaVu Sans/Arial，深色边框；粉色输入、蓝色卷积/张量、黄色BN/Concat/Add、绿色Pool、紫色输出/参数，具体角色见生成的 `visual_style.json`。宽高来自标题、shape、证据文本和子容器测量；间距、转弯槽、箭头末段由共享引擎计算，不来自源码中的坐标。每条边保留语义端口，折叠视图映射到最近可见容器；上游kernel无Python内部证据时保持边界，而不为“更详细”虚造节点。

## 生成与验证

正式合并后，在专题目录运行：

```bash
python3 generate.py --module psp_upsample --png
python3 checks/vision_extended.py
```

适配器合并前可单独预览：

```bash
python3 staging/preview_module.py psp_upsample \
  --manifest staging/vision_source_manifest.json --out /tmp/module-vision-extended
```

输出的SVG可以继续编辑，但应修改适配器/布局再重新生成以保持源码、IR、图像同步。独立 `checks/vision_extended.py` 读取真实AST校验构造、branch选择、操作数和真实顺序；另有全部声明一致性guard。每例至少删除/交换真实依赖端点的负例，并验证shape、operator与参数身份错误能被拒绝。三个视图均检查边界、包含、正交路线、末段转弯空间、上行主流、避开边框与算子内部、文本范围和不同辅助张量的路线分离。PNG还需目视复查。

这些校验针对上述固定snapshot/选例，不代表任意源码自动提取、数值结果正确或所有运行时配置已验证。相邻版本、custom block、输入shape或条件分支变化均需重新取证和独立合同。
