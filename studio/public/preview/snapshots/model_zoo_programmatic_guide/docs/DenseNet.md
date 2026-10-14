# DenseNet-BC-100：源码到三层架构图

本例绘制的是 `bamos/densenet.pytorch` 的 **CIFAR-10 DenseNet-BC-100**，不是仅根据“DenseNet”这个名称套用 ImageNet DenseNet-121 图。模型入口是 [DenseNet](../sources/densenet.pytorch/densenet.py)，配置来自 [train.py](../sources/densenet.pytorch/train.py) 的 `main()`；源码版本固定为 `d1cd5e1957975628286e516512c6d1c14430f810`，文件 SHA256 与许可证记录在 [source_manifest.json](../source_manifest.json)。

绘图适配器是 [adapters/densenet.py](../adapters/densenet.py)。它显式声明模型语义、重复模板和拼接依赖；程序只读源码进行 AST 取证，不导入模型、不下载 CIFAR-10、不执行训练。图框上的 E 编号及悬停信息对应生成目录里的源码映射。

## 选定配置和静态形状

训练入口明确创建 `DenseNet(growthRate=12, depth=100, reduction=0.5, bottleneck=True, nClasses=10)`。输入为 `[B,3,32,32]`。图中采用评估路径、`B>1`；示例训练 batch 默认 64。

`nDenseBlocks = (depth-4)//3` 后，bottleneck 分支再次整除 2，所以每个 dense block 有 **16 个 Bottleneck**，三个块共 48 个，参数分别创建。每层新增 `k=12` 个通道，1×1 瓶颈宽度 `4k=48`。图中每个块展开一个带 `j=0...15` 的符号模板，`×16` 表示顺序执行 16 个独立实例。

| 阶段 | 通道变化 | 空间变化 | 源码依据 |
| --- | --- | --- | --- |
| Stem | 3 → 24 | 32×32 → 32×32 | `DenseNet.__init__`：`2*growthRate`，3×3、padding=1 |
| Dense block 1 | 24 → 216 | 保持 32×32 | 24 + 16×12 |
| Transition 1 | 216 → 108 | 32×32 → 16×16 | `floor(C*0.5)`，平均池化 2 |
| Dense block 2 | 108 → 300 | 保持 16×16 | 108 + 16×12 |
| Transition 2 | 300 → 150 | 16×16 → 8×8 | 同一类结构，独立实例 |
| Dense block 3 | 150 → 342 | 保持 8×8 | 150 + 16×12 |
| Final BN/ReLU/pool/squeeze | 342 | 8×8 → 1×1 → 去掉单例轴 | `DenseNet.forward` 第 114 行 |
| FC / LogSoftmax | 342 → 10 | `[B,342] → [B,10]` | `DenseNet.forward` 第 115 行 |

## 图例为什么这样对应源码

| 图中结构 | 源码符号 / 位置 | 对应理由 |
| --- | --- | --- |
| 浅蓝 Dense block 外框 | `DenseNet._make_dense`，第 99—107 行 | 一个 `nn.Sequential` 顺序执行 16 层；外框表示复合模块，不是单个卷积 |
| Bottleneck 模板内的两组 BN/ReLU/Conv | `Bottleneck.__init__` 第 19—27 行；`forward` 第 29—33 行 | 调用顺序是 BN→ReLU→Conv1×1→BN→ReLU→Conv3×3，属于 pre-activation |
| Retain dense input x / Concat | `torch.cat((x,out),1)`，第 32 行 | 卷积仅生成 k 个新特征；原有全部通道原样保留并沿通道轴拼接 |
| 旁路 x→Concat | 同一 `Bottleneck.forward` | 这是第二个拼接操作数，不能通过主卷积分支推导，也不能画成残差 Add |
| Transition | `Transition.forward` 第 54—57 行 | BN/ReLU/1×1 压缩先执行，随后平均池化减半空间尺寸 |
| 最后分类器 | `DenseNet.forward` 第 114—116 行 | 固定 8×8 平均池化后 squeeze，再 FC 和 LogSoftmax；返回值是 log 概率 |

“Dense”连接不需要在图中绘制所有前层到后层的上百条箭头。第 j 层的输入 `x` 已经包含第 0…j−1 层的所有特征，因此每个代表模板的 **x→Concat** 旁路足以表达递归累积。适配器记录 `Cj=块输入通道+12j`，而不是将所有模板的输入都写成固定通道数。

同一种卷积/归一化使用相同图例；它们仍通过 `dense1[j].conv1`、`dense2[j].bn1`、`trans1.conv1` 等参数身份区分。共用 `Bottleneck` 类及一份源码证据，不等于共用权重。

## 三个粒度及排布

- 概览只展示 Stem、三个 Dense block、两个 Transition 和分类器；每块的完整通道变化仍然可见。
- 模块图显示每块一个符号 Bottleneck 模板，保持 `×16`、`j` 和独立参数说明。
- 详细图展开模板内的八个节点、Transition 内四个节点及分类器。语义 IR 共 51 个节点，模板外的其余 15 次实例通过 repeat 元数据表达。

主列表按 `DenseNet.forward` 的执行顺序声明，但共享布局器把第一个子节点放在容器底部，输出放在顶部。每组高度由子节点高度、24px 子模块间距、标题区域和内边距递归求和；主要容器等宽对齐。Retain x→Concat 依赖作为带语义端口的侧边连线交给避障路由器；拼接前最后一段提前进入 Concat 侧口，不沿模块边框走线。

配色和字体复用 Transformer 原型的主题：主要计算模块使用明显色块，BN 采用黄色，线性投影采用紫色，张量整形采用浅蓝、ReLU 采用浅灰；相同颜色表示图元类别。绘图程序把参数身份和源码编号独立保存，避免颜色被误读为参数共享。

## 已按源码修正的常见框架图偏差

本任务没有新增 DenseNet 基础 PNG，因此这些是与常见概念图的区分，并不是指控某张用户图画错：

- 该实现有三个 dense stages、3×3 CIFAR stem；没有 ImageNet 7×7 stride-2 stem、初始 MaxPool 或第四个 dense block。
- Dense 连接是通道 **Concat**，并不保留相同宽度做 Add。
- Transition 使用 Average Pool，不使用 MaxPool；通道压缩还包含 `floor`。
- 输出是 `F.log_softmax` 的 log 概率，不是 logits，也不是普通 Softmax 概率。
- 源码确实使用固定 kernel=8 平均池化和无 `dim` 的 squeeze；图中没有自行改为自适应池化或 Flatten。

## 原型边界

形状来自指定输入和源码的静态推导。旧版 `torch.squeeze(...)` 会去掉 **所有** 单例轴：`B=1` 时 batch 轴也被移除，因此图中明确写 `B>1`。旧版 `F.log_softmax` 没有显式 `dim`，本适配器按所选二维分类输出解释 class 轴，未声称这些旧训练代码可直接在当前 PyTorch 运行。

若更换 depth、growthRate、reduction、bottleneck 分支或输入空间大小，必须同步更新适配器的重复次数、通道表达式和池化形状，并重新审阅源码；只改变源码目录不能自动完成这些修改。
