# Fire：压缩后的同源扩展与通道拼接

本例只绘制 `One Fire block only`，不新增完整模型。固定来源为 [pytorch/vision](https://github.com/pytorch/vision)，commit `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。源码经 AST 读取与 SHA256/Git blob 核对，未导入、执行模型、下载权重或运行 C++/CUDA kernel。

本例明确声明构造 `Fire(64,16,64,64)`，输入 `[B,64,32,32]`，输出 `[B,128,32,32]`。shape 是选例与静态公式的推导，不是一次实际forward观测；含BN/Dropout的路径由调用方train/eval决定。

输入先经过 squeeze 1×1 `64→16` 和 inplace ReLU。两个 expand 分支都读取这个 **16 通道中间值**：1×1 `16→64` 与 3×3 `16→64,padding=1` 各接独立 ReLU。源码 list 按 expand1x1、expand3x3 排序，Concat(dim=1) 得到128通道。三个 Conv 的 bias 均使用默认 True；没有 BN、pool 或 residual Add。

虽然两个 expand 都是16→64，核大小与属性路径不同，因此参数不共享。squeeze 是两路的共同前驱，绘图必须把它放在分支分发之前。

## 源码证据范围

| 符号 | 本固定文件行号 | 原文件 |
|---|---|---|
| `Fire` | 15–40 | [固定源码](../sources/torchvision-v0.9.0-vision-extended/torchvision/models/squeezenet.py) |
| `Fire.__init__` | 17–33 | [固定源码](../sources/torchvision-v0.9.0-vision-extended/torchvision/models/squeezenet.py) |
| `Fire.forward` | 35–40 | [固定源码](../sources/torchvision-v0.9.0-vision-extended/torchvision/models/squeezenet.py) |

完整片段与 E### 编号由生成时的 `source_evidence.json`、`source_map.md`保存；图上的E###指向符号范围，不能把一个范围编号当成该节点的逐行自动推理结果。

## 图中算子与参数身份

| 稳定节点 / 图框标签 | 源码操作与配置 | 声明输出 shape | 参数属性路径 |
|---|---|---|---|
| `fire.squeeze.conv` / Conv 1 / 64→16 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=True | `[B,16,32,32]` | `squeeze` |
| `fire.squeeze.relu` / ReLU | `relu`；inplace=True | `[B,16,32,32]` | `无学习参数` |
| `fire.expand1x1.conv` / Conv 1 / 16→64 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=True | `[B,64,32,32]` | `expand1x1` |
| `fire.expand1x1.relu` / ReLU | `relu`；inplace=True | `[B,64,32,32]` | `无学习参数` |
| `fire.expand3x3.conv` / Conv 3 / 16→64 | `conv`；kernel_size=3；stride=1；padding=1；dilation=1；groups=1；bias=True | `[B,64,32,32]` | `expand3x3` |
| `fire.expand3x3.relu` / ReLU | `relu`；inplace=True | `[B,64,32,32]` | `无学习参数` |
| `fire.concat` / Concat channel dim=1 | `concat`；dim=1 | `[B,128,32,32]` | `无学习参数` |

不同属性路径对应不同实例；同色同形状不自动表示共享参数。BN的affine参数与running-stat buffer分别理解。未提供自定义替代block，本选例只针对固定源码与以上构造。

## 三粒度与排布理由

概览折叠一个 Fire。模块图展开 squeeze、两路 expand 和 Concat；详细图再展开每条路径的 Conv→ReLU。两支路按源码 list 从左到右，底部同输入对齐，顶部接独立收集线。共享总线是同值扇出，不是将输入 channel 一分为二。

三粒度复用同一语义IR。`chain.items`按执行先后声明，由共享布局引擎反转画面y方向，实现内部与总体自底向上；`parallel.items`保持源码列表顺序，收集本身不执行tensor合并，Concat/Add必须另有真实节点。graph布局只声明rank/列对齐，数据依赖必须显式提供，不能从视觉相邻自动推断。

字体使用DejaVu Sans/Arial，深色边框；粉色输入、蓝色卷积/张量、黄色BN/Concat/Add、绿色Pool、紫色输出/参数，具体角色见生成的 `visual_style.json`。宽高来自标题、shape、证据文本和子容器测量；间距、转弯槽、箭头末段由共享引擎计算，不来自源码中的坐标。每条边保留语义端口，折叠视图映射到最近可见容器；上游kernel无Python内部证据时保持边界，而不为“更详细”虚造节点。

## 生成与验证

正式合并后，在专题目录运行：

```bash
python3 generate.py --module fire --png
python3 checks/vision_extended.py
```

适配器合并前可单独预览：

```bash
python3 staging/preview_module.py fire \
  --manifest staging/vision_source_manifest.json --out /tmp/module-vision-extended
```

输出的SVG可以继续编辑，但应修改适配器/布局再重新生成以保持源码、IR、图像同步。独立 `checks/vision_extended.py` 读取真实AST校验构造、branch选择、操作数和真实顺序；另有全部声明一致性guard。每例至少删除/交换真实依赖端点的负例，并验证shape、operator与参数身份错误能被拒绝。三个视图均检查边界、包含、正交路线、末段转弯空间、上行主流、避开边框与算子内部、文本范围和不同辅助张量的路线分离。PNG还需目视复查。

这些校验针对上述固定snapshot/选例，不代表任意源码自动提取、数值结果正确或所有运行时配置已验证。相邻版本、custom block、输入shape或条件分支变化均需重新取证和独立合同。
