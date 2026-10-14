# U-Net：源码到三层架构图

本例基于 `mateuszbuda/brain-segmentation-pytorch` 的 [UNet](../sources/brain-segmentation-pytorch/unet.py)，版本固定为 `d45f8908ab2f0246ba204c702a6161c9eb25f902`。源码文件哈希、上游地址和许可证保存在 [source_manifest.json](../source_manifest.json)。[adapters/unet.py](../adapters/unet.py) 将该版本的 forward 路径转成显式语义 IR。

这里的 U-Net 使用带 BatchNorm 的 same-padding 卷积。不能仅套用原论文中 valid convolution、中心裁剪和 64 初始通道的图。所有图框依据这份源码对应到 `_block`、`__init__` 或 `forward`；程序不导入模型、不执行训练。

## 选定配置和形状

图采用 `UNet.__init__` 的构造默认值：`in_channels=3`、`out_channels=1`、`init_features=32`。空间尺寸 256×256 取自 [train.py](../sources/brain-segmentation-pytorch/train.py) 的 `--image-size` 默认值。训练脚本实际通过 Dataset 属性传入通道参数；本原型固定绘制上述构造配置，未通过运行 Dataset 自动推断通道。

该仓库用于脑 MRI 分割，`3` 个输入通道不能仅凭维度标记成 RGB。记号统一为 `[B,C,H,W]`。

| 保存的特征 / 阶段 | 输出形状 | 与下一阶段的关系 |
| --- | --- | --- |
| enc1 | `[B,32,256,256]` | MaxPool 后进 encoder2；原尺寸特征送 decoder1 拼接 |
| enc2 | `[B,64,128,128]` | MaxPool 后进 encoder3；原尺寸特征送 decoder2 拼接 |
| enc3 | `[B,128,64,64]` | MaxPool 后进 encoder4；原尺寸特征送 decoder3 拼接 |
| enc4 | `[B,256,32,32]` | MaxPool 后进 bottleneck；原尺寸特征送 decoder4 拼接 |
| bottleneck | `[B,512,16,16]` | ConvTranspose 512→256，空间扩大到 32×32 |
| decoder4 | `[B,256,32,32]` | 上采样特征与 enc4 拼成 512 通道后进行双卷积 |
| decoder3 | `[B,128,64,64]` | 上采样特征与 enc3 拼成 256 通道 |
| decoder2 | `[B,64,128,128]` | 上采样特征与 enc2 拼成 128 通道 |
| decoder1 | `[B,32,256,256]` | 上采样特征与 enc1 拼成 64 通道 |
| 1×1 Conv + Sigmoid | `[B,1,256,256]` | 每像素单通道前景概率 |

## 图框、图例和源码的对应

| 图中结构 | 源码符号 / 位置 | 为什么这样画 |
| --- | --- | --- |
| Encoder 1…4 外框 | `UNet.__init__` 第 13—20 行；`forward` 第 46—49 行 | 各自调用一个独立 `_block`；同一结构不同参数，不能合并为共享编码层 |
| Double Conv + BN + ReLU | `_block` 第 68—98 行 | `OrderedDict` 明确列出 Conv→BN→ReLU→Conv→BN→ReLU 六个连续算子 |
| 四个独立 MaxPool 节点 | `__init__` 第 14/16/18/20 行；`forward` 第 47—51 行 | 池化在下一编码阶段之前执行，skip 必须来自池化前特征 |
| Bottleneck | `__init__` 第 22 行；`forward` 第 51 行 | 同类双卷积模块，通道 256→512，空间最低为 16×16 |
| Decoder 的 ConvTranspose | `__init__` 第 24—38 行 | 可学习转置卷积，kernel=2、stride=2，既扩大空间又减半通道 |
| Decoder 的 Concat | `forward` 第 54/57/60/63 行 | `torch.cat((dec_i,enc_i),dim=1)`；是两个真实输入，不是残差相加 |
| Decoder 双卷积 | `__init__` 第 27/31/35/39 行 | Concat 导致输入通道为 2f，双卷积输出为 f；参数和 encoder 分开实例化 |
| 1×1 输出 Conv / Sigmoid | `__init__` 第 41—43 行；`forward` 第 65 行 | 单通道二元概率，不能画成 Softmax 或多个互斥类别 |

同类算子有相同颜色和轮廓，但 IR 给出真实参数路径，例如 `encoder1.enc1conv1`、`decoder1.dec1conv1`、`upconv4` 和 `conv`。相同 `_block` 源码证据并不意味着 encoder 和 decoder 权重共享。

Encoder 边框的 `skip` 输出端口表示已经计算完成的 `enc_i`。后继 MaxPool 为单独节点，保证 side edge 起点不会误落到池化后的张量上；Decoder Concat 的主输入来自 ConvTranspose，侧输入来自匹配 encoder，明确区分拼接的两个操作数。

## 三个粒度和程序化排布

概览保留 4 个 encoder、4 个 pool、bottleneck、4 个 decoder 和预测头；四条 skip 的语义仍在。模块图展开 decoder 的转置卷积、Concat、双卷积容器。详细图进一步展开 **encoder1、bottleneck 和 decoder1** 的六个算子；其他同型双卷积模块保留折叠容器、形状和参数身份。完整 IR 含全部九个双卷积模块的六个算子，共 90 个节点。

为和 Transformer 及其他模型保持统一阅读顺序，U-Net 不强制排成传统纸面 U 形：源码执行顺序先 encoder1→encoder4→bottleneck，再 decoder4→decoder1，程序将这个主 chain 自底向上排布。长 skip 独立进入侧边走廊，并通过 Concat 标签说明来源和通道数。

主容器按递归测量计算尺寸，统一主要模块宽度。双卷积的内部列表同样自底向上，Conv/BN/ReLU 的顺序与源码一致。辅助依赖使用避障正交路由：避开叶子框和无关展开模块，提前转弯并保证接收端留有明确直线段。虚线在这套原型中表示主 chain 之外的显式数据依赖；**skip 是实际 forward 计算输入，不是装饰性说明线**。

外框使用 Transformer 相近的浅蓝 encoder / 浅粉 decoder，内部 Conv、Norm、Concat 各有稳定色彩。分组标题加粗，算子名称常规字重；证据编号与张量形状使用次级字号。模块颜色编码类型，参数路径编码身份。

## 已按源码纠正的概念图偏差

本任务没有新增 U-Net 基础 PNG，因此以下是针对经典示意图的源码差异说明：

- 3×3 卷积 `padding=1`，forward 不进行中心 crop 或 resize。不能添加经典原论文的 crop 箭头。
- 上采样是 `ConvTranspose2d`，不是插值或独立 Upsample。
- skip 送的是池化前的 encoder 输出，并通过通道 Concat 融合；不能画成 Add。
- 每个双卷积块实际含两次 BatchNorm；不是纯 Conv/ReLU。
- 基础通道数为 32，瓶颈为 512，不是 64/1024。
- 输出为逐像素 Sigmoid 概率，不是 Softmax。

## 原型边界

形状为源码静态推导，没有运行时检查。输入尺寸选择 256×256；一般要求 H、W 为 16 的倍数，以保证四次池化后的上采样分支能直接与 skip 拼接。源码没有修复奇数尺寸的插值或裁剪逻辑，因此图中没有主动补入这些操作。

更换输入通道、类别数、初始特征宽度或空间尺寸，需要更新选定 profile 和静态形状；若改用 bilinear U-Net、valid-convolution U-Net 或其他实现，应建立新的源码适配器，而不是只换模型标题。
