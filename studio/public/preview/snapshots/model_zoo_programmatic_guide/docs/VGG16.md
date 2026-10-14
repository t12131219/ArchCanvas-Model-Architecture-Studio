# VGG16：真实 CIFAR-10 配置、五个卷积块与被注释的模块

图依据 `rasbt/deeplearning-models` 的 [cnn-vgg16.ipynb](../sources/deeplearning-models-batch3/pytorch_ipynb/cnn/cnn-vgg16.ipynb)，固定提交为 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。原 Notebook、文件哈希、由 code cell 派生的 [Python 文件](../sources/deeplearning-models-batch3/pytorch_ipynb/cnn/cnn-vgg16.py) 及单元行号映射保存在 [source_manifest.json](../source_manifest.json)。绘制入口是源码类 `VGG16`，通过 [vgg16.py 适配器](../adapters/vgg16.py)建立经过审阅的静态 IR，不执行或导入上游代码。

这份实现的实际数据集是 CIFAR-10、输入为 `[B,3,32,32]`、输出10类。第40行的“MNIST DATASET”注释是陈旧标题；第35行 `num_features=784` 虽传给构造函数，但 `__init__` 从未使用这个形参。图必须依据数据加载与算子参数表达结构，不能根据注释或无效参数画成 MNIST 全连接输入。绘制 eval profile，来自第232/247行的 `model.eval()`；本模型没有BN或Dropout，train/eval不会改变图中的算子序列。

## 源码层次与图例对应

以下行号均指固定的 Notebook 派生 Python 文件，可通过源证据记录反查原 code cell。

| 图例 | 源码证据 | 为什么这样对应 |
| --- | --- | --- |
| CIFAR-10 image | 第45—52行 `datasets.CIFAR10(...,ToTensor())` | 没有Resize，原生3通道32×32；`B`保留为符号，128只是一项DataLoader设置 |
| Five convolutional blocks 外框 | `VGG16.forward` 第210—214行 | 这是对依次执行的五个成员block建立的视觉分组，不是虚构 `self.features` 模块 |
| Block 1 / 2 | `VGG16.__init__` 第84 / 102行 | 每个真实Sequential包含两组Conv→ReLU，末尾MaxPool |
| Block 3 / 4 / 5 | 第119 / 143 / 166行 | 每个真实Sequential包含三组Conv→ReLU，末尾MaxPool；通道数不同，不能合并为一个共享实例 |
| Conv2d / ReLU / MaxPool | 每个 `block_k` 的Sequential项 | 顺序、卷积核、通道与pool参数来自构造；forward整体调用该Sequential |
| Flatten features | `forward` 第216行 `x.view(x.size(0),-1)` | 保留batch，展平的是512×1×1，而不是传入但未使用的784 |
| Classifier head | `__init__` 第189—197行；forward第217行 | 真实 `self.classifier` 为Linear512→4096→4096→10，中间两次ReLU |
| Return logits / probabilities | `forward` 第217—220行 | classifier结果分出原始logits及Softmax(dim=1)；二者是实际返回tuple的两个字段 |

13个卷积加3个Linear构成这里的“16”，ReLU、pool和Softmax不计入该命名层数。前五个block是真实源码成员；`Five convolutional blocks` 外框和 `Linear / ReLU`小外框仅帮助阅读，保留其所属真实参数路径，不把视觉层次误称为额外可训练模块。

## 形状推导与实际参数身份

所有Conv为3×3、stride1、padding1，所以空间大小不变；默认 `bias=True`。每个MaxPool2d为2×2、stride2、无padding，空间边长减半。张量按NCHW标注。

| 位置 | Conv组数 / 输出通道 | block后的输出 | Conv在Sequential中的参数路径 |
| --- | --- | --- | --- |
| 输入 | 3通道 | `[B,3,32,32]` | 无参数 |
| Block1 | 2组 / 64 | `[B,64,16,16]` | `block_1.0`、`block_1.2` |
| Block2 | 2组 / 128 | `[B,128,8,8]` | `block_2.0`、`block_2.2` |
| Block3 | 3组 / 256 | `[B,256,4,4]` | `block_3.0`、`.2`、`.4` |
| Block4 | 3组 / 512 | `[B,512,2,2]` | `block_4.0`、`.2`、`.4` |
| Block5 | 3组 / 512 | `[B,512,1,1]` | `block_5.0`、`.2`、`.4` |
| Flatten | 512×1×1 | `[B,512]` | 无参数 |
| Hidden1 / Hidden2 | 4096 / 4096 | 两次 `[B,4096]` | `classifier.0`、`classifier.2` |
| Final Linear | 10 | logits `[B,10]` | `classifier.4` |
| Return | 原始logits / Softmax结果 | 两个 `[B,10]` | Softmax无参数 |

每个block的第一层Conv接上一个block输出通道，后续Conv在当前通道数内计算。例如Block3首层128→256，后两层256→256；并不是三个相同256→256。ReLU与pool无训练参数，颜色相同表达同类算子；13个不同Conv参数路径才说明它们拥有独立权重。

这里必须保留三个源码差异：第192/195行Dropout都被注释，因此没有构造这两层；第205行AdaptiveAvgPool构造和第215行调用都被注释；实现完全没有BatchNorm。不能复制通用ImageNet VGG图的224×224输入、7×7池化、512×7×7 flatten、Dropout或VGG-BN。特征块 `nn.ReLU()` 默认 `inplace=False`，classifier的 `nn.ReLU(True)` 才为inplace=True。

classifier中的注释不会占用Sequential索引，因此第三个Linear确实是 `classifier.4`，不能按含Dropout模板写成 `.6`。Softmax则有明确forward调用，并真实返回；训练损失在模型外部使用logits，不应删掉已执行的概率分支或把损失画入模型forward。

## 三种粒度与程序化排布

概览折叠五块features与classifier，保留输入、Flatten和两个返回字段。模块图展开五个真实block、classifier两段Linear/ReLU；详细图选Block1的两卷积模式和Block3的三卷积模式展开。其余Block2/4/5仍在图中分别存在，并在完整IR中保留所有原始算子及参数路径。完整IR包含52个节点；“详细”表达代表内部模式，并未声称全部算子在同一张图中同时可见。

适配器 `chain.items` 按输入→输出的实际执行顺序编写，布局统一把第一项放在底部，后续项向上依次排列；block中的Conv、ReLU、pool与整体方向一致。重复的独立Conv不能改画成横向分支，因为源码的Sequential是串联；只有原始logits和Softmax概率这两个真实返回字段采用同输入横向并列，再收集为tuple。

布局引擎递归测量标签、shape、证据行与子节点，chain高度是各子模块高度之和加固定间隔和外框留白，宽度由最宽子模块及左右padding确定。`fill_width`使五块与classifier主体宽度协调；并列返回组的宽度是两支宽度、支间距和padding之和。连线从底口/顶口接入，终段预留至少18px，转弯使用外框内的通道，避免沿边框走线。具体尺寸以各视图的 `layout_*.json` 为准。

继承Transformer样式的字体、加粗标题、深色细边、粉色输入、蓝色Conv、浅蓝block外框、紫色Linear、灰色ReLU、浅绿pool、绿色Softmax构成统一图例。`visual_roles`只决定外观；`kind`、shape、参数路径、source evidence与IR边决定真实语义。浅蓝block没有因此成为Transformer Encoder，相同颜色也不表示共享参数。

## 验证与复用边界

`validate_ir()`检查真实CIFAR-10配置、五块深度、13个独立Conv、pool顺序、512flatten、未构造模块和双返回字段。外部检查再核验冻结源文件、Notebook来源、SVG节点与IR对应、线框关系和导出尺寸。把IR中任一ReLU误改为Dropout会被语义检查拒绝；这只验证已审阅profile的关键不变量，并非证明任意VGG源码都能被自动解释。

换数据集、输入分辨率、class数、block定义或启用注释模块时，需要重新审阅适配器。形状全部由源码参数静态计算，没有运行forward或训练；训练精度和checkpoint内容不属于本图验证结果。
