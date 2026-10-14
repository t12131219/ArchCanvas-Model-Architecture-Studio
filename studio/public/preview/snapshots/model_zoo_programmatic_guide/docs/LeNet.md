# LeNet5：从 MNIST 教学源码到三层程序化架构图

本适配器表达 `rasbt/deeplearning-models` 的 `pytorch_ipynb/cnn/cnn-lenet5-mnist.ipynb` 中 `LeNet5`，而不是根据“LeNet”名称绘制原论文结构。原始 Notebook 与逐单元转换后的 Python 文件都保留在 `sources` 中；固定版本、下载来源、摘要和单元行号映射见 `source_manifest.json`。绘图只读取源码文本和 AST，不导入 Notebook，不下载数据或训练模型。

绘图入口为 [LeNet5 源码](../sources/deeplearning-models/pytorch_ipynb/cnn/cnn-lenet5-mnist.py)；显式语义适配器为 [lenet.py](../adapters/lenet.py)。选定配置来自 Notebook 单元 8、10、13：`NUM_CLASSES=10`、`GRAYSCALE=True`，调用者先把 MNIST 从 28×28 缩放为 32×32，然后构造 `LeNet5(NUM_CLASSES, GRAYSCALE)`。图从模型收到的 32×32 张量开始；缩放是输入条件，不画成模型内部层。

## 源码、图例与形状逐项对应

| 图中节点 / 模块 | 源码依据 | 输入 → 输出 | 为什么这样对应 |
| --- | --- | --- | --- |
| MNIST image | `LeNet5.forward(x)` 和 Notebook 的 `Resize((32,32))` | `[B,1,32,32]` | 模型接收 NCHW 灰度图，固定全连接层需要最终 5×5 特征 |
| Convolutional features | `self.features = nn.Sequential(...)`；`x = self.features(x)` | 图像 → `[B,16,5,5]` | Sequential 给出实际调用顺序，因此可以直接映射为嵌套竖向 chain |
| Conv2d 1→6 | `features.0`，5×5、默认 stride 1 / padding 0 | 32×32 → 28×28 | 不补 padding；边长由 `floor((H+2p-k)/s)+1` 决定 |
| Tanh | `features.1` | `[B,6,28,28]` 不变 | 是源码明确构造的激活，不能替换成常见 ReLU |
| MaxPool2d | `features.2`，kernel 2、默认 stride 2 | 28×28 → 14×14 | 来源是 max pooling，不能套用原论文的平均下采样 |
| Conv2d 6→16 / Tanh / MaxPool2d | `features.3 / .4 / .5` | 14×14 → 10×10 → 5×5 | 与前一组颜色相同，因为算子类型相同；第二个卷积拥有另一套权重 |
| Flatten features | `torch.flatten(x, 1)` | `[B,16,5,5]` → `[B,400]` | 从维度 1 起展平，保留 batch；400 正好等于 classifier 输入维度 |
| Fully connected classifier | `self.classifier`；`logits = self.classifier(x)` | 400 → 120 → 84 → 10 | 三个 Linear，中间两处 Tanh；最后 Linear 输出未经激活的 logits |
| Logits / Softmax 两分支 | `probas = F.softmax(logits, dim=1)`；`return logits, probas` | 一个 `[B,10]` → 两个 `[B,10]` | 一个保留原值，一个计算概率，fork 表示同一输入的两种结果，不是求和 |
| Forward return tuple | `return logits, probas` | `(logits, probas)` | 两个返回值必须保留；训练代码将 logits 传给 `cross_entropy` |

`features.0`、`features.3`、`classifier.0`、`classifier.2`、`classifier.4` 是五个不同参数身份。`Tanh`、pool、flatten 和 Softmax 没有可训练参数。同色只表示同一算子家族，并不表示共享权重。

## 与教科书结构的差异

这个教学实现使用 Tanh、MaxPool 和三个 Linear；原始 LeNet-5 的平均下采样、C5 卷积、部分连接方案不能仅凭模型名字加入图中。虽然 `Linear(16*5*5,120)` 与某些 C5 的输出大小相似，这里仍然画为 Linear，因为实际模块类型和参数组织就是 Linear。

Softmax 属于 `forward`，不是“为了说明概率”额外添加的图例。它与上次 Transformer 示例中可能置于模型返回值之外的解释性 Softmax 应区别对待。因此图中用两条实线结果分支，并标明返回 tuple。

## 三种粒度与程序化排布

概览图折叠 features、classifier 和返回分支，保留输入、展平、主要模块与输出。模块图展开两个 Sequential：features 显示两个 Conv/Tanh/Pool 组合，classifier 显示两个 Linear/Tanh 组合和最后一个 Linear。详细图展开四个组合中的实际算子，展示张量形状、参数路径和源码证据，语义 IR 共 24 个节点。组合只是按连续源码操作建立的逻辑分组，不声称上游有额外的 `nn.Sequential` 属性，也不添加运算或参数。

适配器中的 `chain.items` 按源码输入→输出声明，布局器按自底向上排列。由此输入在底部，Conv/Tanh/Pool 按调用顺序向上；Flatten 位于两个不同 rank 的结构之间；两个输出分支在顶部并列。`parallel` 只表示 logits 的分叉和返回值收集，不代表多线程或相加。

`visual_roles` 将真实算子类型映射到共用视觉样式：输入粉、输出紫、卷积蓝、池化浅绿、Linear 紫、Softmax 绿、Tanh 浅灰。group 采用实色深边框和加粗标题，核心组件列入 `fill_width`，使同层模块等宽。`kind` 保留 `conv2d`、`max_pool2d`、`tanh` 等真实语义，不为了使用 Transformer 配色把卷积伪装成 Attention。

## 边界与核验

这是对固定源码与灰度 32×32、10 类配置的审阅适配器。类默认 `grayscale=False` 会选择 3 通道，但 Notebook 的实际调用设置为 True；不能仅改输入标签为 RGB 就声称已验证另一个配置。通道变为 3 时第一个卷积权重身份不变，权重尺寸却会变化，应该重新构建配置证据。

源码证据确认符号、范围与固定版本；手工审阅的适配器声明拓扑；几何检查确认排布与导出。上述过程没有运行模型，形状由源码层参数静态推导，也不证明任何训练结果或任意输入尺寸都可用。
