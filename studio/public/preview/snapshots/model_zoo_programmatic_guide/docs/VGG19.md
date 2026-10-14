# VGG19-type：真实 VGG16 符号中的 16 个卷积层

本图依据固定 `rasbt/deeplearning-models @ 59beda3aa25337e576564f1c18c6edd26f9f30e3` 的 [cnn-vgg19.ipynb](../sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-vgg19.ipynb)。原Notebook、code cell派生的 [Python文件](../sources/deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-vgg19.py)、文件哈希和单元行号映射见 [source_manifest.json](../source_manifest.json)。[vgg19.py适配器](../adapters/vgg19.py)只读源文本与AST；不导入或执行Notebook、数据下载或模型。

文件中的真实类名仍为 `VGG16`，构造调用也使用这个符号，但其五个block的Conv数实际为 **2/2/4/4/4，共16个Conv，加3个Linear构成VGG19-type**。图名描述结构，证据入口保留实际 `VGG16`，不根据旧类名删掉三个卷积，也不虚构 `VGG19` AST类。第36行MNIST数据标题同样陈旧，实际第41/46行均为CIFAR10。

## 固定输入、形状与逐节点对应

Notebook cell8设置 `num_features=784`、`num_classes=10`，实际加载CIFAR-10与ToTensor，无Resize。构造函数接受但从未使用num_features，所以输入为 `[B,3,32,32]`，不能由784推断输入或flatten宽度。图选择eval模式，来源是 `compute_accuracy` 第247行和 `compute_epoch_loss` 第262行的model.eval。这里没有BN或Dropout，train/eval不改变算子链。

| 图中图例 | 派生源码证据 | 真实输出形状 / 参数身份 |
| --- | --- | --- |
| CIFAR-10 image | 第41—48行数据构造 | `[B,3,32,32]`；B是符号，128只为loader设置 |
| Block1：2个Conv/ReLU | `VGG16.__init__` 第80—96行 | pool后 `[B,64,16,16]`；Conv为 `block_1.0/.2` |
| Block2：2个Conv/ReLU | 第98—113行 | `[B,128,8,8]`；`block_2.0/.2` |
| Block3：4个Conv/ReLU | 第115—142行 | `[B,256,4,4]`；`block_3.0/.2/.4/.6` |
| Block4：4个Conv/ReLU | 第145—172行 | `[B,512,2,2]`；`block_4.0/.2/.4/.6` |
| Block5：4个Conv/ReLU | 第174—201行 | `[B,512,1,1]`；`block_5.0/.2/.4/.6` |
| Flatten features | `forward` 第231行 `x.view(-1,512)` | 当前profile `[B,512]`；无参数 |
| Linear / ReLU1 | classifier第204—205行 | `[B,4096]`；`classifier.0`是Linear512→4096 |
| Linear / ReLU2 | 第206—207行 | `[B,4096]`；`classifier.2`是Linear4096→4096 |
| Final Linear | 第208行 | logits `[B,10]`；`classifier.4` |
| 返回两分支 | forward第232/234行 | Softmax(dim1)与原始logits，两个 `[B,10]`构成真实tuple |

每个block是真实 `nn.Sequential`，执行顺序为Conv→ReLU重复，再MaxPool。16个Conv全部3×3、stride1、padding1、默认bias=True；空间在Conv中不变，2×2/stride2 MaxPool再减半。每个block首Conv改变通道，例如Block3为128→256，后3层为256→256；相同图例不能掩盖不同输入通道。特征ReLU默认inplace=False，classifier两次ReLU(True)才为inplace=True。

`Five convolutional blocks` 外框只是对forward第226—230行五次成员调用的视觉分组，源码没有 `self.features`。两段Linear/ReLU外框同样是可读分组，真实成员属于classifier。每个图元仍保留源证据与实际参数路径，不把视觉层次解释为新增模块。

## 与前一份 VGG16 实现的实质区别

VGG19-type比前一模型在Block3/4/5各多一个真实Conv/ReLU，共16个Conv；不能仅复制旧图然后改标题。第四个Conv索引为`.6`，末尾pool为`.8`；Block1/2的pool为`.4`。所有16层参数身份分别保留，结构相同也不共享权重。

flatten使用的是 `x.view(-1,512)`，不是 `x.view(x.size(0),-1)`。32×32输入最终1×1，两者当前形状相同；若改为64×64，最终2×2，源码会产生4B行 `[4B,512]`，并不会得到保留B的 `[B,2048]`。适配器保存原表达式并限制所选profile，不能只替换图中输入尺寸就声称支持另一配置。

第212—221行对Conv与Linear权重都执行normal_(0,0.05)，bias清零；不同于前一VGG16文件的Kaiming初始化。初始化不是forward算子，不画在tensor主链中，但保留为profile和源事实。没有Dropout、BatchNorm、AvgPool，也没有标准ImageNet 224×224的7×7 flatten与池化头。Softmax确实执行并返回；模型外部训练loss使用logits，不混入模型forward。

## 三粒度、自底向上与紧凑布局

概览折叠features/classifier，保留图像输入、flatten与返回字段。模块图展开五个真实block和两段classifier。详细图展开Block1的两卷积模式和Block3的四卷积模式；Block2/4/5仍是三个独立图例，完整IR保留它们全部算子和参数。IR共58个节点。详细图表达代表模式，并未声明所有Conv都在同一视图完全展开。

适配器列表按源码输入→输出声明，布局引擎再自底向上放置。每个Sequential内部保持Conv→ReLU→…→pool，自底向上与整体一致。Conv串联不能改成并列；仅真实原始logits/Softmax返回采用同输入横向分支，`fork`与`tuple_collection`分别表达分出同一值和收集返回tuple。

递归测量标签、shape、证据和子模块确定框宽高；chain加总子高度、固定间距和padding，并列组按最长分支高度及两支宽度分配。主框等宽对齐、箭头终段至少18px、正交转弯留在通道内；各视图实际坐标存 `layout_*.json`。使用统一Transformer字体、加粗标题、深边框、粉色输入、蓝Conv、浅蓝block、紫Linear、灰ReLU、浅绿pool与绿色Softmax。视觉角色与 `kind`/参数/IR边分开，颜色相同不表示共享权重，浅蓝block也不是Transformer Encoder。

## 验证边界

`validate_ir`检查真实源类VGG16与19层结构差异、16个独立Conv、各block深度/shape、pool顺序、原始view表达式、512输入classifier、初始化事实、缺席模块与双返回。语义负例删除Block3/4/5的第4个Conv会被拒绝。固定文件/Notebook哈希、AST来源、SVG节点/端口与IR对应、线框几何及PNG导出另行检查。

这些结果针对固定32×32、10类配置。形状由源参数静态推导，没有运行forward、训练或checkpoint；关键不变量的通过不证明任意VGG变体已被自动识别。修改层数、输入大小、激活、class数或启用额外模块，需要重新审阅适配器与源码快照。
