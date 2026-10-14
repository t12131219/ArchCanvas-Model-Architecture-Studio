# RoIAlign：特征与坐标操作数的库边界

本例只绘制 `RoIAlign wrapper and actual kernel call only`，不新增完整模型。固定来源为 [pytorch/vision](https://github.com/pytorch/vision)，commit `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。源码经 AST 读取与 SHA256/Git blob 核对，未导入、执行模型、下载权重或运行 C++/CUDA kernel。

本例明确声明构造 `RoIAlign((7,7),spatial_scale=.25,sampling_ratio=2,aligned=True)`，输入 `[B,64,32,32]`，输出 `[K,64,7,7]`。shape 是选例与静态公式的推导，不是一次实际forward观测；含BN/Dropout的路径由调用方train/eval决定。

选 `RoIAlign((7,7),spatial_scale=.25,sampling_ratio=2,aligned=True)`，特征[B,64,32,32]，caller RoIs[K,5]，输出[K,64,7,7]。第一列batch index，后四列xyxy。源码 wrapper 正式调用 roi_align→`torch.ops.torchvision.roi_align`；Tensor boxes分支直接传入，不执行list boxes转换。

图中kernel为 **opaque runtime boundary**，没有学习参数。7×7、scale、fixed2×2 bin采样与aligned的说明来自API/显式配置；没有从Python AST伪造每个插值点、坐标预测器或C++内部公式。底部特征与旁侧坐标是不同操作数，不能接成全图pool。

## 源码证据范围

| 符号 | 本固定文件行号 | 原文件 |
|---|---|---|
| `RoIAlign` | 58–85 | [固定源码](../sources/torchvision-v0.9.0-vision-extended/torchvision/ops/roi_align.py) |
| `RoIAlign.__init__` | 62–73 | [固定源码](../sources/torchvision-v0.9.0-vision-extended/torchvision/ops/roi_align.py) |
| `RoIAlign.forward` | 75–76 | [固定源码](../sources/torchvision-v0.9.0-vision-extended/torchvision/ops/roi_align.py) |
| `roi_align` | 11–55 | [固定源码](../sources/torchvision-v0.9.0-vision-extended/torchvision/ops/roi_align.py) |

完整片段与 E### 编号由生成时的 `source_evidence.json`、`source_map.md`保存；图上的E###指向符号范围，不能把一个范围编号当成该节点的逐行自动推理结果。

## 图中算子与参数身份

| 稳定节点 / 图框标签 | 源码操作与配置 | 声明输出 shape | 参数属性路径 |
|---|---|---|---|
| `roi_align.kernel` / RoIAlign / torchvision kernel | `roi_align`；output_size=[7, 7] | `[K,64,7,7]` | `无学习参数` |
| `roi_align.boxes` / RoIs / batch index + xyxy | 辅助 `input`，origin=caller | `[K,5]` | `无学习参数` |

不同属性路径对应不同实例；同色同形状不自动表示共享参数。BN的affine参数与running-stat buffer分别理解。未提供自定义替代block，本选例只针对固定源码与以上构造。

## 三粒度与排布理由

三图以同一个wrapper为中心，module/detailed均只展开一个真实库调用，因此两个视图可以相同。坐标作为辅助粉色输入，通过专用rois端口侧接。虚线表示侧输入，不表示被忽略；IR保存 roi_coordinates 角色和精确端点。

三粒度复用同一语义IR。`chain.items`按执行先后声明，由共享布局引擎反转画面y方向，实现内部与总体自底向上；`parallel.items`保持源码列表顺序，收集本身不执行tensor合并，Concat/Add必须另有真实节点。graph布局只声明rank/列对齐，数据依赖必须显式提供，不能从视觉相邻自动推断。

字体使用DejaVu Sans/Arial，深色边框；粉色输入、蓝色卷积/张量、黄色BN/Concat/Add、绿色Pool、紫色输出/参数，具体角色见生成的 `visual_style.json`。宽高来自标题、shape、证据文本和子容器测量；间距、转弯槽、箭头末段由共享引擎计算，不来自源码中的坐标。每条边保留语义端口，折叠视图映射到最近可见容器；上游kernel无Python内部证据时保持边界，而不为“更详细”虚造节点。

## 生成与验证

正式合并后，在专题目录运行：

```bash
python3 generate.py --module roi_align --png
python3 checks/vision_extended.py
```

适配器合并前可单独预览：

```bash
python3 staging/preview_module.py roi_align \
  --manifest staging/vision_source_manifest.json --out /tmp/module-vision-extended
```

输出的SVG可以继续编辑，但应修改适配器/布局再重新生成以保持源码、IR、图像同步。独立 `checks/vision_extended.py` 读取真实AST校验构造、branch选择、操作数和真实顺序；另有全部声明一致性guard。每例至少删除/交换真实依赖端点的负例，并验证shape、operator与参数身份错误能被拒绝。三个视图均检查边界、包含、正交路线、末段转弯空间、上行主流、避开边框与算子内部、文本范围和不同辅助张量的路线分离。PNG还需目视复查。

这些校验针对上述固定snapshot/选例，不代表任意源码自动提取、数值结果正确或所有运行时配置已验证。相邻版本、custom block、输入shape或条件分支变化均需重新取证和独立合同。
