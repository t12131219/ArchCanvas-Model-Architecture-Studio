# Pyramid pooling：四个池化尺度与原特征保留

本例只绘制 `PSPModule only`，不新增完整模型。固定来源为 [Lextal/pspnet-pytorch](https://github.com/Lextal/pspnet-pytorch)，commit `4eb6ab61287e837f5e2d8c1ae09fadeaa0e31e37`。源码经 AST 读取与 SHA256/Git blob 核对，未导入、执行模型、下载权重或运行 C++/CUDA kernel。

本例明确声明构造 `PSPModule(features=64,out_features=128,sizes=(1,2,3,6))`，输入 `[B,64,24,24]`，输出 `[B,128,24,24]`。shape 是选例与静态公式的推导，不是一次实际forward观测；含BN/Dropout的路径由调用方train/eval决定。

源码是 `Lextal/pspnet-pytorch` 的 PSPModule，不能替换成另一个 PSPNet 实现。显式选择 features64、out_features128、sizes(1,2,3,6)，输入24×24。每个 stage 是 AdaptiveAvgPool到s×s、Conv1 `64→64,bias=False`，随后 `F.upsample(...,bilinear)` 到原H/W。源码没有 stage BN，也没有把每条路径降到C/4。

`priors = [四个上采样结果] + [feats]`：原输入是 **最后一个** Concat operand。总通道320，再 bottleneck Conv1 `320→128,bias=True`，ReLU。历史 F.upsample 调用未传 align_corners，文档和IR保留“omitted”，不为上游补一个默认值。仓库固定 tree 没有 LICENSE；来源清单如实记录缺失。

## 源码证据范围

| 符号 | 本固定文件行号 | 原文件 |
|---|---|---|
| `PSPModule` | 8–25 | [固定源码](../sources/pspnet-vision-extended/pspnet.py) |
| `PSPModule.__init__` | 9–14 | [固定源码](../sources/pspnet-vision-extended/pspnet.py) |
| `PSPModule._make_stage` | 16–19 | [固定源码](../sources/pspnet-vision-extended/pspnet.py) |
| `PSPModule.forward` | 21–25 | [固定源码](../sources/pspnet-vision-extended/pspnet.py) |

完整片段与 E### 编号由生成时的 `source_evidence.json`、`source_map.md`保存；图上的E###指向符号范围，不能把一个范围编号当成该节点的逐行自动推理结果。

## 图中算子与参数身份

| 稳定节点 / 图框标签 | 源码操作与配置 | 声明输出 shape | 参数属性路径 |
|---|---|---|---|
| `pyramid_pooling.pool0` / AdaptiveAvgPool 1x1 | `pool`；pool_type=adaptive_average；output_size=[1, 1] | `[B,64,1,1]` | `无学习参数` |
| `pyramid_pooling.conv0` / Conv 1 / 64→64 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,64,1,1]` | `stages.0.1` |
| `pyramid_pooling.resize0` / Bilinear upsample to H,W | `interpolate`；mode_argument=bilinear；align_corners_argument=omitted | `[B,64,24,24]` | `无学习参数` |
| `pyramid_pooling.pool1` / AdaptiveAvgPool 2x2 | `pool`；pool_type=adaptive_average；output_size=[2, 2] | `[B,64,2,2]` | `无学习参数` |
| `pyramid_pooling.conv1` / Conv 1 / 64→64 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,64,2,2]` | `stages.1.1` |
| `pyramid_pooling.resize1` / Bilinear upsample to H,W | `interpolate`；mode_argument=bilinear；align_corners_argument=omitted | `[B,64,24,24]` | `无学习参数` |
| `pyramid_pooling.pool2` / AdaptiveAvgPool 3x3 | `pool`；pool_type=adaptive_average；output_size=[3, 3] | `[B,64,3,3]` | `无学习参数` |
| `pyramid_pooling.conv2` / Conv 1 / 64→64 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,64,3,3]` | `stages.2.1` |
| `pyramid_pooling.resize2` / Bilinear upsample to H,W | `interpolate`；mode_argument=bilinear；align_corners_argument=omitted | `[B,64,24,24]` | `无学习参数` |
| `pyramid_pooling.pool3` / AdaptiveAvgPool 6x6 | `pool`；pool_type=adaptive_average；output_size=[6, 6] | `[B,64,6,6]` | `无学习参数` |
| `pyramid_pooling.conv3` / Conv 1 / 64→64 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=False | `[B,64,6,6]` | `stages.3.1` |
| `pyramid_pooling.resize3` / Bilinear upsample to H,W | `interpolate`；mode_argument=bilinear；align_corners_argument=omitted | `[B,64,24,24]` | `无学习参数` |
| `pyramid_pooling.retained` / Retain original feats | `identity`； | `[B,64,24,24]` | `无学习参数` |
| `pyramid_pooling.concat` / Concat priors then original | `concat`；dim=1 | `[B,320,24,24]` | `无学习参数` |
| `pyramid_pooling.bottleneck` / Conv 1 / 320→128 | `conv`；kernel_size=1；stride=1；padding=0；dilation=1；groups=1；bias=True | `[B,128,24,24]` | `bottleneck` |
| `pyramid_pooling.relu` / ReLU | `relu`；inplace=False | `[B,128,24,24]` | `无学习参数` |

不同属性路径对应不同实例；同色同形状不自动表示共享参数。BN的affine参数与running-stat buffer分别理解。未提供自定义替代block，本选例只针对固定源码与以上构造。

## 三粒度与排布理由

原输入的 H/W 通过实际 `input:shape → resize:size` 的虚线shape依赖传入，上采样读取的是池化前/resize前的原空间尺寸。PSP多尺度的四条resize分别保留该端口，PSPUpsample再按源码乘2；这条旁路只供size元数据，不替代张量主流。

四个pool stage和最后的原值保留路从左至右对应真实list。保留路是identity图元，不伪装成第五个池化。详细图在各stage内上行显示pool→Conv→resize；收集线汇入显式Concat，不能把list收集直接解释为tensor相加。

三粒度复用同一语义IR。`chain.items`按执行先后声明，由共享布局引擎反转画面y方向，实现内部与总体自底向上；`parallel.items`保持源码列表顺序，收集本身不执行tensor合并，Concat/Add必须另有真实节点。graph布局只声明rank/列对齐，数据依赖必须显式提供，不能从视觉相邻自动推断。

字体使用DejaVu Sans/Arial，深色边框；粉色输入、蓝色卷积/张量、黄色BN/Concat/Add、绿色Pool、紫色输出/参数，具体角色见生成的 `visual_style.json`。宽高来自标题、shape、证据文本和子容器测量；间距、转弯槽、箭头末段由共享引擎计算，不来自源码中的坐标。每条边保留语义端口，折叠视图映射到最近可见容器；上游kernel无Python内部证据时保持边界，而不为“更详细”虚造节点。

## 生成与验证

正式合并后，在专题目录运行：

```bash
python3 generate.py --module pyramid_pooling --png
python3 checks/vision_extended.py
```

适配器合并前可单独预览：

```bash
python3 staging/preview_module.py pyramid_pooling \
  --manifest staging/vision_source_manifest.json --out /tmp/module-vision-extended
```

输出的SVG可以继续编辑，但应修改适配器/布局再重新生成以保持源码、IR、图像同步。独立 `checks/vision_extended.py` 读取真实AST校验构造、branch选择、操作数和真实顺序；另有全部声明一致性guard。每例至少删除/交换真实依赖端点的负例，并验证shape、operator与参数身份错误能被拒绝。三个视图均检查边界、包含、正交路线、末段转弯空间、上行主流、避开边框与算子内部、文本范围和不同辅助张量的路线分离。PNG还需目视复查。

这些校验针对上述固定snapshot/选例，不代表任意源码自动提取、数值结果正确或所有运行时配置已验证。相邻版本、custom block、输入shape或条件分支变化均需重新取证和独立合同。
