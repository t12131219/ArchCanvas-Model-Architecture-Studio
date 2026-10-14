# PixelShuffle：Conv4尾部与通道到空间重排

本例只绘制官方超分辨率示例 `Net.forward` 的 **`self.pixel_shuffle(self.conv4(x))` 尾部**。输入边界是前面的 `ReLU(conv3(...))` 特征 `[B,32,8,8]`；本例显式选择 `upscale_factor=3`，输出为 `[B,1,24,24]`。它不是整张超分辨率模型图。

来源入口是固定 Awesome-pytorch-list 的 [pytorch examples 条目](../upstream/Awesome-pytorch-list/README.md)。实际实现冻结为 `pytorch/examples` 提交 `acc295dc7b90714f1bf47f06004fc19a7fe235c4`；[源码副本](../sources/pytorch-examples-superres/super_resolution/model.py) 和 [许可证](../sources/pytorch-examples-superres/LICENSE) 一并保存。适配器为 [pixelshuffle.py](../module_adapters/pixelshuffle.py)，版本及文件摘要见 [source_manifest.json](../source_manifest.json)。

## 源码与图框的对应

| 图框 / 稳定 ID | 源码位置 | 对应理由 |
|---|---|---|
| `pixelshuffle.input` | `Net.forward` 第22行之后 | 输入不是原始图像；Conv1、Conv2、Conv3及其ReLU调用在当前绘图范围之外，图中明确标注该边界 |
| `pixelshuffle.projection` | 构造器第14行；forward第23行 | 展示所选Conv4阶段；这是视觉组织容器，不是另外创建的源码类或附加运算 |
| `pixelshuffle.conv4` | 同上 | 唯一被画出的卷积实例，32→r²通道、3×3核、stride1、padding1、bias默认True |
| `pixelshuffle.shuffle` | 构造器第15行；forward第23行 | 真实的 `nn.PixelShuffle(upscale_factor)` 实例及一次调用；图中保持一个库算子边界 |
| `pixelshuffle.output` | `Net.forward` 第24行 | 该尾部返回单个图像张量；源码没有尾部ReLU、Sigmoid或归一化 |

完整源码确实还定义了 `conv1`、`conv2`、`conv3`。保存完整源文件用于取证，不意味着应把这些成员都展开到选定模块图中。`artifact_scope='module'`、profile的 `drawing_scope` 与输入节点的 `scope_boundary` 一起限定实际绘图范围。

## 静态尺寸为什么是32→9→1

源码构造器的 `upscale_factor` 是参数，不是固定写死的3。本例将3作为**显式示例配置**，不能宣称源码只支持3倍上采样。

```text
输入特征              [B,32,8,8]
Conv4: 3×3, p=1, s=1  [B, 9,8,8]      9 = r² = 3²
PixelShuffle(r=3)      [B, 1,24,24]     1 = 9 / r²
```

Conv4保持空间大小，并产生用于空间偏移的九个通道。它有真实可学习参数 `conv4.weight:[9,32,3,3]` 和 `conv4.bias:[9]`。`Net._initialize_weights` 对Conv4.weight使用 orthogonal初始化，没有单独重设Conv4.bias；这是构造上下文，不是forward中额外的一层。本次绘图没有执行初始化。

`PixelShuffle` 本身没有weight或bias，也不重新计算卷积或插值值。其标准API形状契约是：

```text
[B, C*r², H, W] → [B, C, H*r, W*r]
```

以下关系是数学/标准API的辅助说明，**不是从这个源文件拆出的算子实现**。令X为Conv4输出、Y为重排结果，对于本例r=3：

```text
Y[b,c,3*h+i,3*w+j] = X[b,9*c+3*i+j,h,w]
0 ≤ i,j < 3
```

本例C=1，因此同一低分辨率位置 `(h,w)` 的九个通道依次对应高分辨率3×3位置偏移：

| 空间偏移 | j=0 | j=1 | j=2 |
|---|---|---|---|
| i=0 | 通道0 | 通道1 | 通道2 |
| i=1 | 通道3 | 通道4 | 通道5 |
| i=2 | 通道6 | 通道7 | 通道8 |

九个通道是Conv4产生的可学习特征值，`PixelShuffle` 将它们重新分配到空间位置。不能把该映射画成九组独立卷积参数，也不能把它替换为最近邻/双线性插值或转置卷积。

## 为什么没有虚构reshape子节点

本文件只有一个 `nn.PixelShuffle(...)` 定义和一次调用，没有提供其PyTorch内核实现。因此该节点标记：

```text
runtime_dependency = torch.nn.PixelShuffle
opaque_runtime_boundary = True
learnable = False
mapping_provenance = standard API contract, not source AST operators
```

这里的opaque表示**库实现未在所选源码中展开**，不表示不知道它的公开形状契约。可以解释标准映射，但不能把常见的reshape→permute→reshape说明图包装为本文件实际存在的三个源码算子。本例用一个标记library的真实调用框呈现边界，映射公式放在本说明中。

## 三种粒度与连线

概览显示输入特征边界、整个上采样头和输出。模块视图显示Channel projection与PixelShuffle两步；详细视图在projection容器内显示唯一真实Conv4节点，保留PixelShuffle库边界。没有并列输入、tuple汇流或残差线。

三个图复用同一语义IR，自底向上排布。`projection→shuffle` 代表Conv4的结果进入PixelShuffle；投影容器的出端口只是内部Conv4输出的层级边界，不引入第二次卷积。短主链由内容测量分配宽度、高度与统一间距，不手写每个节点的绝对坐标。

`validate_ir()` 核对显式r=3、32→9→1通道、卷积几何、无post-ReLU、无PixelShuffle参数、source order、输入范围和API公式出处；同时拒绝伪造的PixelShuffle内部子节点。形状来自静态推导，源码、初始化与库算子均未执行。

可复用的独立源码与负例检查见 [checks/spatial_modules.py](../checks/spatial_modules.py)。检查直接读取冻结源码AST，核对Conv4声明、实际尾部调用、初始化范围与静态尺寸；注入错误r、可学习Shuffle参数、额外ReLU、错误偏移公式、伪造内部子算子，以及替换冻结源码中的PixelShuffle调用，都必须被拒绝。在本原型目录内运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 checks/spatial_modules.py
```

脚本同时检查STN和PixelShuffle，不依赖已生成图或临时预览；所有取证与源码负例副本自动清理，不执行上游Net或其初始化。
