# MobileNetV3-Large：Notebook 配置、库源码与图框对应

本例选择 `cnn-mobilenet-v3-large-cifar10.ipynb` 的 CIFAR-10 配置，联合固定 `pytorch/vision:v0.9.0` 的真实实现。不是根据 `torch.hub.load` 的名字补上一张通用 MobileNet 图。rasbt 提交为 `59beda3aa25337e576564f1c18c6edd26f9f30e3`；torchvision 提交为 `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。两份出处分别保留在 [源码证据](../generated/mobilenetv3/source_evidence.json) 中。

[三粒度预览](../generated/mobilenetv3/index.html) · [详细 SVG](../generated/mobilenetv3/figure3_detailed.svg) · [完整源码映射](../generated/mobilenetv3/source_map.md) · [适配器](../adapters/mobilenetv3.py)

## 选定路径与边界

Notebook cell12 指定 `mobilenet_v3_large, pretrained=False`，随后将 `classifier[-1]` 替换为 `Linear(1280,10)`；cell14 调用 `model.eval()`。测试输入经过 Resize70、CenterCrop64、ToTensor、mean/std 都为0.5的 Normalize。因此图中输入为符号形状 `[B,3,64,64]`，输出为 `[B,10]` logits。Checkpoint 文件名中残留 `mobilenet-v2` 不决定模型类型。

此处只有静态源码和整数形状推导；没有导入 torchvision、调用 torch.hub、读取 checkpoint、训练或执行模型。Notebook 调用的训练工具保留为范围外代码；图中采用明确的测试 eval 配置。

## 源码到图框

| 图框 / 稳定 ID | 真实源码 | 为什么这样映射 |
| --- | --- | --- |
| `m3.input`、最终 head 替换 | Notebook 的模块范围 `__module__`，cell9/12/14 | 这些操作位于顶层而非函数内；伪符号表示整个模块的取证范围，不虚构 `forward` |
| Stem / `m3.stem` | `MobileNetV3.__init__` + 引入的 `ConvBNActivation.__init__` | Conv3×3 3→16、stride2，后接 BN/Hardswish；不是 V2 的32通道/ReLU6 |
| 六个 Stage / `m3.stage1…6` | `_mobilenet_v3_conf` + `MobileNetV3.__init__` | 按相邻输出通道做视觉分组；真实源码的 `features` 是单个 Sequential，不存在六个具名 stage 类 |
| IR1…15 / `m3.block1…15` | `InvertedResidual.__init__/forward` | 每份 config 单独构造一个 block；参数路径为 `features.i.block`，不能因形状同型而共享权重 |
| Expansion / Depthwise / Project | `ConvBNActivation` 以及条件构造 | Expansion 当 expanded≠cin 才存在；depthwise groups=expanded；project 的 activation_layer 是 `nn.Identity` |
| Squeeze/excitation / `m3.blocki.se` | `SqueezeExcitation.__init__/_scale/forward` | 实际计算为 pool→Conv→ReLU→Conv→Hardsigmoid→逐元素乘法；乘法保留的输入是 depthwise 结果 |
| Identity Add / `m3.blocki.add` | `InvertedResidual.forward` | `stride==1 && cin==cout` 才 `result += input`；这条旁路保留 block 的原始输入，不是 SE 的输入 |
| Final pointwise / `m3.last` | `lastconv_output_channels=6*lastconv_input_channels` | 输出160×6=960；1280属于下一层 classifier 的隐藏维 |
| Pool / Flatten / Classifier | `_forward_impl` 与 `__init__` | pool1→flatten(x,1)→Linear960→1280→Hardswish→Dropout.2→替换 Linear1280→10；forward没有Softmax |

`__module__` 的 span、snippet、原 Notebook cell 范围照常参与哈希与 AST 核对；它提供完整 caller 证据，具体 cell 的选取仍需适配器审阅，不表示已经自动理解其中所有顶层语句。

## 15份配置与参数索引

下表按真实 `features` 顺序列出。RE=ReLU，HS=Hardswish；width=1、reduced_tail=False、dilated=False，所有 dilation=1。Squeeze 宽度为 `_make_divisible(expanded//4,8)`，不能简单用 C/4。

| features.i | cin→expanded→cout | k / stride | Act | SE squeeze | identity Add | 输出 H×W |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 16→16→16 | 3 / 1 | RE | — | 是 | 32×32 |
| 2 | 16→64→24 | 3 / 2 | RE | — | 否 | 16×16 |
| 3 | 24→72→24 | 3 / 1 | RE | — | 是 | 16×16 |
| 4 | 24→72→40 | 5 / 2 | RE | 24 | 否 | 8×8 |
| 5 | 40→120→40 | 5 / 1 | RE | 32 | 是 | 8×8 |
| 6 | 40→120→40 | 5 / 1 | RE | 32 | 是 | 8×8 |
| 7 | 40→240→80 | 3 / 2 | HS | — | 否 | 4×4 |
| 8 | 80→200→80 | 3 / 1 | HS | — | 是 | 4×4 |
| 9 | 80→184→80 | 3 / 1 | HS | — | 是 | 4×4 |
| 10 | 80→184→80 | 3 / 1 | HS | — | 是 | 4×4 |
| 11 | 80→480→112 | 3 / 1 | HS | 120 | 否 | 4×4 |
| 12 | 112→672→112 | 3 / 1 | HS | 168 | 是 | 4×4 |
| 13 | 112→672→160 | 5 / 2 | HS | 168 | 否 | 2×2 |
| 14 | 160→960→160 | 5 / 1 | HS | 240 | 是 | 2×2 |
| 15 | 160→960→160 | 5 / 1 | HS | 240 | 是 | 2×2 |

例如 IR1 无 expansion、无 SE：depthwise=`features.1.block.0`，project=`.1`；IR4 有 expansion、SE：expand=`features.4.block.0`、depthwise=`.1`、SE=`.2`（内部 `.fc1/.fc2`）、project=`.3`。CBA 内部 `.0` 是 Conv、`.1` 是 BN、`.2` 是 activation。适配器按条件递增 sequential 索引，不能假定所有 block 的 depthwise/project 都占相同位置。

## 三粒度与排布逻辑

概览只显示 Stem、六个逻辑 Stage、Final pointwise 和 Head。模块图展开 Stage，逐一显示15份 block 的 cin/expanded/cout、kernel、stride、SE与skip配置。详细图展开 IR1（无 expansion、ReLU、identity）、IR4（SE、ReLU、无skip）、IR12（SE、Hardswish、identity）。其余 block 保持折叠，完整算子与参数路径都留在同一语义 IR 中。

所有主链和子模块按 source-call 顺序 `chain(items=…)` 声明，绘图时将首项放在底部；后继逐项向上。递归测量决定框高与标题空间，主要容器使用 `fill_width` 对齐，算子保持本征宽度。纵向长图适合 SVG 缩放阅读，概览/模块视图提供更紧凑的阅读入口。

SE 的 retained-input 线从 SE 容器入口分流，经侧边走廊进入 Multiply 的侧口；block residual 从 block 入口进入 Add。两条线的出发位置不同，终点也不同；提前转弯和边框避障只改变几何路径，不改变语义端点。橙色表示 SE，浅蓝表示卷积，黄色表示 BN/Add，紫色表示 Linear，灰色区分 activation；绿色 Hardsigmoid 图框的算子由标签决定，颜色不表示它是 Softmax。

## 校验

`validate_ir` 校验15份完整配置、conditional expansion、depthwise groups、ReLU/Hardswish选择、8个SE与10个Add、圆整 squeeze width、门与保留张量端点、分类头顺序和caller替换位置。`verify.py` 还核对两来源的固定提交/文件哈希、AST范围、cell映射、SVG实际图框与路线、PNG尺寸。这些断言与导出检查不等同于数值等价证明。

```bash
python3 generate.py --model mobilenetv3 --png
python3 verify.py generated --model mobilenetv3 --png
```
