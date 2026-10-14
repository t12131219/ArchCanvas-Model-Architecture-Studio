# ResNet101：CIFAR-10、23 块第三阶段与真实训练 BN 模式

图依据固定 `rasbt/deeplearning-models @ 59beda3aa25337e576564f1c18c6edd26f9f30e3` 的 [cnn-resnet101-cifar10.ipynb](../sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.ipynb)。原Notebook、cell派生 [Python文件](../sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py)、哈希和行号映射见 [source_manifest.json](../source_manifest.json)。[resnet101.py适配器](../adapters/resnet101.py)只读源文本与AST，不导入上游模块或运行模型。

源码工厂确实名为 `resnet101`，并创建 `Bottleneck(expansion=4)`、`layers=[3,4,23,3]`。总共33个独立Bottleneck，主路每块三Conv，加stem Conv与fc构成通常101层命名。与前一份ResNet50-type的[3,4,6,3]不同，Stage3这里有23块，后续identity模板是×22；不能只改标题而沿用旧重复次数。

## 配置、调用模式与源码对应

Notebook cell10设置NUM_CLASSES10、GRAYSCALE=False、BATCH_SIZE128；cell12使用CIFAR10+ToTensor，无Resize，实际输入 `[B,3,32,32]`。工厂第232—237行虽然接受num_classes，但构造读取全局NUM_CLASSES；grayscale则实际使用传入参数，第247行传False。图保留两者不同来源。

**此Notebook没有任何 `model.eval()`。** 第274行model.train之后，`compute_accuracy`没有切模式；`torch.set_grad_enabled(False)`只关闭autograd，仍使用训练BatchNorm的batch统计并更新running statistics。因此图标注train/BN batch statistics，而非惯例推断的eval。此处只记录原源码行为，不改写上游。若用户另选eval是新的profile，需要明确重新配置；no_grad与eval并不等价。

| 图例 | 源码符号 / 派生行号 | 对应关系 |
| --- | --- | --- |
| ResNet101根外框 | `resnet101` 第232—238行 | 真正block类型与[3,4,23,3]决定层数与参数实例 |
| Conv stem | `ResNet.__init__` 第175—179行；forward第214—217行 | RGB Conv7×7(s2,p3)→BN→ReLU→MaxPool3×3(s2,p1) |
| Stage1—4 | 第180—183行；`_make_layer` 第196—211行 | 四个实际Sequential layer1…layer4，3/4/23/3块独立构造 |
| Main path | `Bottleneck.__init__` 第130—137行；forward第144—153行 | Conv1×1→BN→ReLU→Conv3×3→BN→ReLU→Conv1×1→BN |
| Projection shortcut | `_make_layer` 第198—206行；Bottleneck.forward第155—156行 | stride或通道不匹配就用Conv1×1(s)+BN，消耗原始x |
| Add / final ReLU | forward第158—159行 | BN3完成后才 `out += residual`，然后再ReLU |
| Identity template | `_make_layer` 第208—209行 | 后续块不传downsample，原始x无参数旁路进入Add |
| Flatten / Linear | ResNet.forward第225—226行 | `x.view(x.size(0),-1)`保留B，fc2048→10 |
| logits / probabilities返回 | 第227—228行 | Softmax(dim1)与原始logits都真实返回 |

`self.relu`在Bottleneck内调用三次，无学习参数；三个图元是调用点，不是三个可训练ReLU对象。Main path与stage内部模板等视觉边框帮助阅读，不虚构新的Python模块。`conv3x3`辅助函数虽存在，Bottleneck未使用它，其卷积均在自己的__init__直接构造。

## 静态形状、stride位置与四个投影

Conv/Pool空间公式为 `floor((H+2p−k)/s)+1`。卷积不带bias，BN默认affine且当前使用train统计。plane是Bottleneck中间通道，输出通道为plane×4。

| 位置 | 块数 / planes | 输出 | 首块投影 |
| --- | --- | --- | --- |
| 输入 | — | `[B,3,32,32]` | — |
| Stem Conv | 3→64，k7/s2/p3 | `[B,64,16,16]` | — |
| Stem Pool | k3/s2/p1 | `[B,64,8,8]` | — |
| Stage1 | 3 / 64 | `[B,256,8,8]` | 64→256、s1、Conv1×1+BN |
| Stage2 | 4 / 128 | `[B,512,4,4]` | 256→512、s2、Conv1×1+BN |
| Stage3 | 23 / 256 | `[B,1024,2,2]` | 512→1024、s2、Conv1×1+BN |
| Stage4 | 3 / 512 | `[B,2048,1,1]` | 1024→2048、s2、Conv1×1+BN |
| Flatten | 2048×1×1 | `[B,2048]` | 无参数 |
| fc / 返回 | Linear2048→10 | 两个 `[B,10]` | 原始logits与Softmax结果 |

四个stage的首块都需要投影，Stage1虽然stride1，输入64与输出256仍不匹配，不能画为纯identity。后续2/3/22/2块采用identity，共29个identity与4个learned projection。

下采样位置是主路 **conv2的3×3** 和shortcut的1×1；主路conv1为1×1、固定s1。例如Stage2首块Conv1产生 `[B,128,8,8]`，Conv2降到 `[B,128,4,4]`，Conv3扩到512；shortcut得到 `[B,512,4,4]`再相加。不能套用把stride2放到conv1的另一版本。

第184行构造 `AvgPool2d(7,stride=1,padding=2)`，但第224行调用被注释；图直接从Stage4 flatten到2048。源码第185行注释的 `Linear(2048*expansion,...)`也不执行，真正fc是2048→10。存在成员或注释模板不表示它们已进入forward。不要加global average pooling，也不要从注释画出8192输入头。

## 参数身份、并列操作数与三种粒度

每个真实块分别拥有 `layerK.j.conv1/bn1/conv2/bn2/conv3/bn3`；首块另有 `layerK.0.downsample.0/.1`。Stage3的identity实例j=1…22，其他stage分别1…2、1…3、1…2。`repeat.count`、`instance_indices`、`independent_parameters=True`与真实参数成员保留完整数量；×22是顺序执行22套独立参数，不是同一层循环共享权重。

展开投影采用typed `operand_bundle`：主路/shortcut的child_inputs均从同一首块`:in`读value，两支横向并列，`literal_tuple=False`。汇集边只收集Add的两个操作数，上方独立Add才求和。源码没有该处局部tuple，不能因两条并列线而伪造tuple。identity旁路则从块原始输入接入主路末项Add，final ReLU放在外一层chain，保证旁路不误接到激活。

分类头的logits/probas是真实return tuple，保留同输入fork和tuple_collection，与内部Add操作数不同。概览显示stem、四个stages与head；模块图展开每stage首块projection和identity重复组。详细图展开Stage1的s1投影、identity模式与Stage2的s2投影；后续stage保留各自摘要、参数成员、真实形状和数量。完整IR67个节点，未声称把33块中每个内部调用全部展开。

布局列表按源码执行顺序声明，坐标统一自底向上。主/投影并列共用输入rank，短投影贴近底部；Add在并列组上方，ReLU在其上方。重复链折叠可以大幅压缩Stage3高度，同时不丢失22次独立实例身份。递归测量文字、shape与子图确定框宽高；主体等宽、正交端口、至少18px箭头末段与安全通道控制间距、转弯和线框关系。坐标保存于 `layout_*.json`。

共享Transformer字体、深边框、粗体标题、浅蓝stage、蓝色3×3/stem Conv、紫色1×1投影、黄色BN/Add、灰色ReLU、粉色输入、紫色fc与绿色Softmax用于一致视觉表达。紫色1×1仍为 `kind=conv2d`，不是nn.Linear；配色与参数共享、数学语义分开。

## 验证与边界

适配器检查源工厂、33块/[3,4,23,3]、Stage3的22个identity、四投影及独立参数、32×32 RGB形状、真实train/BN模式、factory参数使用、conv2 stride、共同输入操作数、BN3→Add→ReLU、未调用avgpool、2048fc和双返回。语义负例将Stage3 identity数从22错改为5会被拒绝。冻结源码/Notebook/AST、SVG与IR对应、线框几何及PNG导出是另几层独立核验。

形状静态推导，模型从未执行；训练/验证BN行为来源于控制流审阅，不是运行测量。本图不证明当前环境能执行原Notebook的cuda设备、数据加载或训练，也不提供精度结论。更换输入、layers、block、grayscale、class数、avgpool或mode必须重新审阅profile；只改模型显示名称不能自动支持新的ResNet源码。
