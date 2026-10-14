# FPN P6/P7：来源选择与双输出保留

本例只绘制 `LastLevelP6P7 only; excludes backbone and base FPN`，不新增完整模型。固定来源为 [pytorch/vision](https://github.com/pytorch/vision)，commit `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。源码经 AST 读取与 SHA256/Git blob 核对，未导入、执行模型、下载权重或运行 C++/CUDA kernel。

本例明确声明构造 `LastLevelP6P7(256,128)`，输入 `c[-1][B,256,8,8]; existing p[-1][B,128,8,8]; names`，输出 `(extended p including P6[B,128,4,4],P7[B,128,2,2], extended names)`。shape 是选例与静态公式的推导，不是一次实际forward观测；含BN/Dropout的路径由调用方train/eval决定。

选 `LastLevelP6P7(256,128)`，in/out通道不同，源码use_P5=False：输入conv operand来自c[-1]的C5[B,256,8,8]；既有p列表虽含P5[B,128,8,8]，仍不被选为p6的tensor输入。P6=Conv3 stride2 padding1 256→128，4×4；P7=Conv3 stride2 padding1(ReLU(P6))，2×2。两Conv均默认biasTrue、独立参数、Kaiming(a1)/bias0。

`p.extend([p6,p7]); names.extend(["p6","p7"])` 同时保留两个新增特征，返回(p,names)，并修改caller列表。P6在经过ReLU/P7前还需旁路到list extension，不可仅画P7出口。等通道构造会选择P5，当前profile不画这个替代分支。

## 源码证据范围

| 符号 | 本固定文件行号 | 原文件 |
|---|---|---|
| `LastLevelP6P7` | 179–204 | [固定源码](../sources/torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py) |
| `LastLevelP6P7.__init__` | 183–190 | [固定源码](../sources/torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py) |
| `LastLevelP6P7.forward` | 192–204 | [固定源码](../sources/torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py) |

完整片段与 E### 编号由生成时的 `source_evidence.json`、`source_map.md`保存；图上的E###指向符号范围，不能把一个范围编号当成该节点的逐行自动推理结果。

## 图中算子与参数身份

| 稳定节点 / 图框标签 | 源码操作与配置 | 声明输出 shape | 参数属性路径 |
|---|---|---|---|
| `fpn_extra_levels.p6` / P6 / Conv3 stride2 | `conv`；kernel_size=3；stride=2；padding=1；dilation=1；groups=1；bias=True | `[B,128,4,4]` | `p6` |
| `fpn_extra_levels.relu` / ReLU | `relu`；inplace=False | `[B,128,4,4]` | `无学习参数` |
| `fpn_extra_levels.p7` / P7 / Conv3 stride2 | `conv`；kernel_size=3；stride=2；padding=1；dilation=1；groups=1；bias=True | `[B,128,2,2]` | `p7` |
| `fpn_extra_levels.extend` / Extend p and names / P6 + P7 | `tensor`； | `p + P6[128,4,4] + P7[128,2,2]` | `无学习参数` |

不同属性路径对应不同实例；同色同形状不自动表示共享参数。BN的affine参数与running-stat buffer分别理解。未提供自定义替代block，本选例只针对固定源码与以上构造。

## 三粒度与排布理由

两个不同根输入分别表示C5和原p/names。P6→ReLU→P7为上行主流，P6旁路直接进入上方extension的P6端口；原列表在外侧保留后接extension，不进入Conv。最后返回tuple整体图框不意味着两个tensor输出被Concat。详细与模块视图相同，因为没有额外可展开Python子模块。

三粒度复用同一语义IR。`chain.items`按执行先后声明，由共享布局引擎反转画面y方向，实现内部与总体自底向上；`parallel.items`保持源码列表顺序，收集本身不执行tensor合并，Concat/Add必须另有真实节点。graph布局只声明rank/列对齐，数据依赖必须显式提供，不能从视觉相邻自动推断。

字体使用DejaVu Sans/Arial，深色边框；粉色输入、蓝色卷积/张量、黄色BN/Concat/Add、绿色Pool、紫色输出/参数，具体角色见生成的 `visual_style.json`。宽高来自标题、shape、证据文本和子容器测量；间距、转弯槽、箭头末段由共享引擎计算，不来自源码中的坐标。每条边保留语义端口，折叠视图映射到最近可见容器；上游kernel无Python内部证据时保持边界，而不为“更详细”虚造节点。

## 生成与验证

正式合并后，在专题目录运行：

```bash
python3 generate.py --module fpn_extra_levels --png
python3 checks/vision_extended.py
```

适配器合并前可单独预览：

```bash
python3 staging/preview_module.py fpn_extra_levels \
  --manifest staging/vision_source_manifest.json --out /tmp/module-vision-extended
```

输出的SVG可以继续编辑，但应修改适配器/布局再重新生成以保持源码、IR、图像同步。独立 `checks/vision_extended.py` 读取真实AST校验构造、branch选择、操作数和真实顺序；另有全部声明一致性guard。每例至少删除/交换真实依赖端点的负例，并验证shape、operator与参数身份错误能被拒绝。三个视图均检查边界、包含、正交路线、末段转弯空间、上行主流、避开边框与算子内部、文本范围和不同辅助张量的路线分离。PNG还需目视复查。

这些校验针对上述固定snapshot/选例，不代表任意源码自动提取、数值结果正确或所有运行时配置已验证。相邻版本、custom block、输入shape或条件分支变化均需重新取证和独立合同。
