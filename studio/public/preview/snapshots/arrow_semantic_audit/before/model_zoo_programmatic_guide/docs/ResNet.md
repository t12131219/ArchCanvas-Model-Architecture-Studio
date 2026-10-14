# ResNet18：显式残差、投影捷径与 MNIST 特有预测头

本图依据 `rasbt/deeplearning-models` 的 `pytorch_ipynb/cnn/cnn-resnet18-mnist.ipynb`，入口为 `ResNet`，构造者为 `resnet18`。固定的原 Notebook、由 code cell 转换的 Python 文件、来源和单元行号映射见 `source_manifest.json`。适配器只读取文本与 AST，不导入上游代码或运行训练。

源码：[cnn-resnet18-mnist.py](../sources/deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py)。适配器：[resnet.py](../adapters/resnet.py)。Notebook 默认配置为灰度 MNIST 28×28、10 类、`BasicBlock`、四个 stage 各两个 block。绘制 eval 路径，BatchNorm 使用已保存的 running statistics；训练模式对结构顺序没有影响，但统计方式不同。

## 源码与图中层次

| 图例 | 源码依据 | 对应理由 |
| --- | --- | --- |
| ResNet18 根容器 | `resnet18()` 创建 `ResNet(block=BasicBlock,layers=[2,2,2,2],...)` | 模型名称来自构造者，实际层类型与 stage 数来自构造参数 |
| Convolutional stem | `ResNet.__init__` 构造 `conv1,bn1,relu,maxpool`；`forward` 依序调用 | 画成自底向上 chain，不能把 pooling 放到卷积前 |
| Stage 1 / 2 / 3 / 4 | `self.layer1` 到 `self.layer4`；`_make_layer(...)` | 每个 `nn.Sequential` 包含两个 BasicBlock，每层拥有独立权重 |
| Identity block | `BasicBlock.forward` 保存 `residual=x`，`downsample=None` | 在主路两组 Conv/BN 后接 Add，旁路携带原输入 |
| Downsampling block | `_make_layer` 对 stride≠1 或通道不匹配创建 downsample | 主路和捷径都必须降采样，捷径不是无参数 identity |
| Main convolution path | `conv1→bn1→relu→conv2→bn2` | 最后 BN 之后才与捷径相加，不能提前 ReLU |
| Projection shortcut | `downsample = Sequential(Conv2d(1×1,stride=2),BatchNorm2d)` | 显式参数化路径，输入为同一个 block 的 x |
| Add two paths / ReLU after Add | `out += residual; out=self.relu(out)` | 分支收集不是求和，必须独立画 Add；激活顺序是 Add 后 ReLU |
| Flatten / Linear / 返回分支 | `view(...,-1); self.fc(x); F.softmax(...); return logits,probas` | 保留两个真实返回值，训练使用原始 logits |

`BasicBlock` 中同一个 `self.relu` 调用两次，但 ReLU 没有训练参数；用两个相同图例表示两个调用点。卷积与 BatchNorm 的参数路径分别为 `layerK.j.conv1/bn1/conv2/bn2`。投影路径另有 `layerK.0.downsample.0/.1`，颜色相近不表示与主路共享权重。

## 默认形状推导

所有图像张量按 `[B,C,H,W]` 标注。卷积与池化的空间计算采用 `floor((H+2p-k)/s)+1`，本配置没有 dilation，也没有 ceil_mode。

| 位置 | 算子 / stage | 输出形状 |
| --- | --- | --- |
| 输入 | native MNIST，无 32×32 Resize | `[B,1,28,28]` |
| Stem conv | kernel 7、stride 2、padding 3 | `[B,64,14,14]` |
| Stem pool | MaxPool kernel 3、stride 2、padding 1 | `[B,64,7,7]` |
| Stage 1 | 2 个 identity BasicBlock | `[B,64,7,7]` |
| Stage 2 | 首块 stride 2 投影；第二块 identity | `[B,128,4,4]` |
| Stage 3 | 首块 stride 2 投影；第二块 identity | `[B,256,2,2]` |
| Stage 4 | 首块 stride 2 投影；第二块 identity | `[B,512,1,1]` |
| Flatten | `x.view(x.size(0),-1)` | `[B,512]` |
| Linear | `fc=Linear(512*BasicBlock.expansion,10)`，expansion=1 | `[B,10]` |
| 返回值 | logits 与 Softmax(dim=1) | 两个 `[B,10]` |

特别是 7→4 而不是 7→3：3×3、stride 2、padding 1 时输出为 `floor((7+2−3)/2)+1=4`。1×1 投影的 stride 2 同样得到 4，两个分支形状匹配，才可执行 Add。

## 为什么不画 AvgPool

`ResNet.__init__` 的确构造了 `self.avgpool = nn.AvgPool2d(7,stride=1)`，但 `forward` 中 `#x = self.avgpool(x)` 被注释，旁边说明 MNIST 已经是 1×1。因此真实前向图直接 Flatten，不能照搬 ImageNet ResNet 图中的 global average pooling。

这体现了源码到图的关键规则：存在一个成员对象，仅证明它可被调用；真正进入图中的节点，需要前向路径上的调用证据。未执行的对象记录到说明中，以便核对，但不伪造实线流程。

该版本采用 post-activation BasicBlock；它不包含 ResNet v2 的预激活顺序，也不是 expansion=4 的 Bottleneck。`resnet18(num_classes)` 的函数参数实际上没有在构造语句中使用，源码读取模块全局 `NUM_CLASSES` 和 `GRAYSCALE`；本图使用已固定的默认值 10 与 True。

## 重复模板、层数与紧凑度

四个 stage 均存在两套独立 BasicBlock 参数，总计八个 block。Stage 1 用一个展开的 identity 模板加 `repeat.count=2` 表示 `layer1.0 / layer1.1`；参数路径 `layer1.{i}` 的 i 取 0、1。它表示结构重复，不表示循环复用同一层。

Stages 2–4 显式区分首个投影 block 和第二个 identity block。投影 block 可在详细图展开两个分支；第二个 block 保持紧凑图例，记录完整执行顺序及其四个参数成员，并标明与展开的 identity 模板结构相同。这样的折叠减少重复图形，同时保留投影位置、独立参数身份、每阶段块数和形状变化。

概览折叠 stem、stages 和 head；模块图展开 stage 的“首块 / identity”关系；详细图展开代表 identity 与每个 projection 的内部算子。嵌套 chain 的列表始终是源码输入→输出顺序，坐标布局统一从底向上。两个 projection 分支横向并列，对齐同一个输入和输出 rank，再在它们上方单独放 Add。

identity 模板的旁路从该模板输入处分出，进入最后的 Add，而 final ReLU 位于包含模板的外一层 chain 中。这样 `residual=True` 不会把旁路误接到最终 ReLU，也不会把跳连起点接到 Conv1 的输出。

视觉角色与真实语义分离：`kind=conv2d`、`batch_norm2d`、`add` 等保留真实算子；`visual_roles` 给卷积蓝、BN/Add 黄、Linear 紫、Softmax 绿。Stage 外框使用浅蓝的 encoder 视觉角色，仅表达包含关系，不把 ResNet stage 解释为 Transformer Encoder。`fill_width` 让 stem、四个 stages 与 head 的主体等宽，结构顺序、同输入并列、Add 汇合由 IR 决定；颜色、字体、间距和转弯由共享样式及布局规则决定。

## 验证边界

这份图审阅的是固定源码和 28×28 灰度、10 类 eval 配置。静态形状由 layer 参数推导，没有执行模型。换成 224×224 输入后会得到不同空间尺寸；由于该源码仍跳过 avgpool，Flatten 维度可能与 `fc(512,10)` 不符。不能仅替换图上的输入形状就认为另一个配置已被支持。

源码证据、结构适配器、几何检查和导出检查各有作用：符号/行号能追溯出处，适配器表达经过审阅的结构，几何检查检查线与框的关系。它们不等同于自动证明任意源码的完整模型语义或训练性能。
