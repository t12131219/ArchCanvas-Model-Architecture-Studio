# ResNet50-type：误命名工厂中的 Bottleneck、四个投影与真实残差操作数

本图依据 `rasbt/deeplearning-models` 的 [cnn-resnet50-mnist.ipynb](../sources/deeplearning-models-batch3/pytorch_ipynb/cnn/cnn-resnet50-mnist.ipynb)，固定提交为 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。派生 [Python 文件](../sources/deeplearning-models-batch3/pytorch_ipynb/cnn/cnn-resnet50-mnist.py)、原Notebook哈希与code cell行号映射见 [source_manifest.json](../source_manifest.json)。[resnet50.py 适配器](../adapters/resnet50.py)只读取源文本并建立经过审阅的静态IR，没有导入或执行上游模型。

文件名虽然写resnet50，源码工厂实际是第213行的 `resnet34`，docstring也写ResNet-34；其构造却明确使用 `Bottleneck`、`expansion=4`、`layers=[3,4,6,3]`。因此图名写 **ResNet50-type**，同时保留真实源符号 `resnet34`，不虚构 `resnet50()`，也不按工厂名字画成BasicBlock ResNet34。16个Bottleneck各有三个主路Conv，加stem Conv和fc形成通常50层计数；shortcut Conv不计入这一命名惯例。

固定profile为MNIST原生28×28、灰度1通道、10类、eval；调用者第271/298行设置 `model.eval()`，BN使用running statistics。工厂形参 `num_classes` 实际未被构造语句使用，它读取全局 `NUM_CLASSES=10`、`GRAYSCALE=True`。图保留这一配置来源，不能认为向该函数传另一个class数就已换了分类头。

## 图例与源码的逐层对应

行号均为固定Notebook派生Python文件。源码中的 `conv3x3` helper虽存在，但Bottleneck没有调用它；实际卷积参数来自Bottleneck自己的构造。

| 图例 | 源码符号 / 行号 | 对应理由 |
| --- | --- | --- |
| ResNet50-type根外框 | `resnet34` 第213—219行 | 构造的block类型、expansion与stage列表决定实际结构，不能只用名字判断 |
| Conv stem | `ResNet.__init__` 第155—159行；forward第193—196行 | Conv7×7(s2)→BN→ReLU→MaxPool3×3(s2)依次执行；短标题是显示别名 |
| Stage1—4 | 第160—163行；`_make_layer` 第175—190行 | 四个实际Sequential `layer1`…`layer4`，块数分别3/4/6/3；每块单独实例化 |
| First Bottleneck / projection | `_make_layer` 第177—185行 | stride≠1或输入通道≠planes×4就构造Conv1×1+BN投影，并传给首块 |
| Main convolution path | `Bottleneck.__init__` 第110—117行；forward第124—133行 | 1×1→BN→ReLU→3×3→BN→ReLU→1×1→BN；第三次BN后没有先加ReLU |
| Projection shortcut | `_make_layer` 第178—181行；Bottleneck.forward第135—136行 | learned Conv1×1(s)+BN实际接收该block的原始x，和主路是并列操作数 |
| Add two paths / final ReLU | forward第138—139行 | `out += residual`是真实Add；两个分支的收集不等于求和，Add后才ReLU |
| Identity Bottleneck | `_make_layer` 第187—188行；forward第122/138行 | 后续块不传downsample，原始x无参数旁路进入Add |
| Flatten / Linear / return | `ResNet.forward` 第206—209行 | 直接flatten→fc→Softmax，真实返回logits与probas两个字段 |

`Bottleneck.self.relu`在同一块中被调用三次。三次相同图例表示三个调用点，它没有训练参数；Conv1/2/3和BN1/2/3则必须分别保留真实参数路径。外框Main path是可读的视觉分组，并不伪造新的Python成员。

## MNIST空间形状与投影条件

空间公式为 `floor((H+2p−k)/s)+1`，本配置无dilation或ceil_mode。3×3、stride2、padding1使7→4，而不是7→3。Bottleneck的plane是中间通道数，输出通道是plane×4。

| 位置 | 块数 / 中间planes | 真实输出形状 | 首块shortcut |
| --- | --- | --- | --- |
| 输入 | — | `[B,1,28,28]` | — |
| Stem Conv | 1→64，7×7，s2，p3 | `[B,64,14,14]` | — |
| Stem MaxPool | 3×3，s2，p1 | `[B,64,7,7]` | — |
| Stage1 | 3 / 64 | `[B,256,7,7]` | Conv1×1，64→256，s1，后BN |
| Stage2 | 4 / 128 | `[B,512,4,4]` | Conv1×1，256→512，s2，后BN |
| Stage3 | 6 / 256 | `[B,1024,2,2]` | Conv1×1，512→1024，s2，后BN |
| Stage4 | 3 / 512 | `[B,2048,1,1]` | Conv1×1，1024→2048，s2，后BN |
| Flatten / fc | 2048→10 | `[B,2048]`→`[B,10]` | — |
| 返回 | logits / Softmax(dim=1) | 两个 `[B,10]` | — |

Stage1首块即使stride1也必须有投影，因为stem输出64通道，Bottleneck输出256通道，原始x不能直接Add。四个stage首块都需要learned projection；后续块分别2/3/5/2个identity，总计4个projection和12个identity。

降采样位置必须准确：Bottleneck的 `conv1` 是1×1、固定stride1；`conv2` 才是3×3并使用block的stride；`conv3`再扩展到plane×4。Stage2首块主路在conv2从7×7变为4×4，shortcut的1×1 stride2同样得到4×4；二者在Add前已完全同形状。不能采用把stride2放到conv1的另一种ResNet变体模板。

第164行的 `AvgPool2d(7,stride=1)`确实被构造，但第204行forward调用被注释。当前MNIST走完Stage4已经1×1，因此真实路径直接Flatten2048；存在成员对象不代表它实际进入forward。图不画执行中的AvgPool，也不照搬ImageNet输入和global average pooling。

## 残差边、操作数与真实返回tuple

展开projection时，将main path与shortcut横向并列，两者 `child_inputs` 均写为 `{role:'value',producer:first_block,src_port:'in'}`。它们消耗同一个block输入x；`semantic_mode='operand_bundle'`、`literal_tuple=False`把外框定义为显示用的操作数集合。两个分支出口带 `operand_collection`，上方独立Add负责数值相加。源码没有生成局部tuple，这种表达不会把并列外框误称为源码中的tuple对象。

identity模板的旁路起点是该模板的原始输入，进入主路末项Add侧口。主路最后BN3完成后才Add，最终ReLU放在包住这条链的外一层chain中。这样共享 `residual=True`连线规则不会把旁路错接到ReLU，也不会从Conv1输出误分出shortcut。

相比之下，分类头 `return logits,probas`确实产生tuple：fc输出分向原始logits和Softmax两个调用分支，保留 `fork`与`tuple_collection`。操作数并列、实际tuple返回和数值Add三者在IR中有不同意义，不能仅凭“都画两条线”就使用同一种绑定。

## 独立参数与三个视图

每个Bottleneck独立拥有 `layerK.j.conv1/bn1/conv2/bn2/conv3/bn3`；首块额外拥有 `layerK.0.downsample.0/.1`。同颜色表达算子类别，同模板表示结构重复，均不表示跨block共享权重。重复模板的j分别为Stage1的1/2，Stage2的1/2/3，Stage3的1…5，Stage4的1/2；`repeat.independent_parameters=True`及`instance_indices`明确保留这些独立实例。

概览显示stem、四个stage与head。模块图展开每stage的“首块projection / 后续identity”层次。详细图进一步展开Stage1首块的s1投影、Stage1的identity代表模板、Stage2首块的s2投影；Stage3/4的首块与重复identity保留完整执行顺序摘要、真实成员参数列表、实例数量、stride及shape，避免重复画满16块。完整IR为67个节点，不声称16个Bottleneck内部的每一次调用都已分别展开。

每条chain按源码执行顺序声明，再由共享布局从底向上摆放。并列操作数由最长支路确定高度，两支共用输入/输出rank，较短projection贴近输入底部并通过安全通道向上汇集。Add放在并列组上方，最终ReLU再在Add上方。所有stage主体等宽；嵌套框宽度、标题留白和高度由子模块及字体测量递归计算，连线终段预留至少18px，拐弯不沿边框。各视图的实际坐标与端口保存在 `layout_*.json`。

Transformer风格通过共享字体、加粗层次标题、深色边线、浅蓝stage、蓝色3×3/stem Conv、紫色1×1投影、黄色BN/Add、灰色ReLU、粉色输入、紫色Linear和绿色Softmax实现。1×1图例视觉角色为紫色，并不把其真实 `kind=conv2d` 改成 `nn.Linear`；stage浅蓝也不把它解释为Transformer Encoder。

## 验证与边界

适配器检查真实误命名工厂、4个stage数目/shape、16个独立block及4个projection、并列主/shortcut的共同输入、conv2的stride、Stage1通道投影、BN3→Add→ReLU、跳过avgpool与两个返回字段。把Stage2主路stride2错误挪到conv1会被 `validate_ir()`拒绝。源文件/Notebook哈希、AST符号、SVG与IR关系及几何检查另行完成，避免把线画得正确当作语义已正确。

这里验证的是固定MNIST eval配置及经过审阅的关键不变量，所有shape均由参数静态推导，没有执行forward或训练。切换输入尺寸、block类型、planes、层数、gray设置或启用avgpool需要重新审阅；仅改图中输入shape或工厂显示名称不能支持任意ResNet变体。checkpoint精度与动态运行兼容性不属于本次静态图结果。
