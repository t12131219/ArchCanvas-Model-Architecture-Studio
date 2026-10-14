# MobileNetV2：从固定 torch.hub 调用追溯到真实反向残差实现

模型选择来自 `rasbt/deeplearning-models` 的 [CIFAR-10 Notebook 派生文件](../sources/deeplearning-models-batch2/pytorch_ipynb/cnn/cnn-mobilenet-v2-cifar10.py)。Notebook第86—90行调用 `torch.hub.load('pytorch/vision:v0.9.0','mobilenet_v2',pretrained=False)`，然后把 `model.classifier[-1]` 替换为 `Linear(1280,10)`。调用者本身没有定义反向残差内部结构；因此只看这一行不能声称已从源码提取全部模型。

原型额外固定了 [torchvision v0.9.0 的 mobilenetv2.py](../sources/torchvision-v0.9.0/torchvision/models/mobilenetv2.py)，按它的 `MobileNetV2`、`InvertedResidual`、`ConvBNActivation` 构造与前向路径建立 [适配器](../adapters/mobilenetv2.py)。两个来源项目、固定版本、文件哈希和Notebook单元映射记录在 [source_manifest.json](../source_manifest.json)。图框证据同时指向实际实现；调用者配置单独保留。

所有内容仅通过文本、AST与静态审阅获取；没有执行 `torch.hub.load`、导入torchvision、下载权重或运行模型。`pretrained=False`是调用者明确条件；之后加载训练checkpoint不改变该架构，图也不把checkpoint中的权重数值当作已验证结果。

## 固定配置和空间 / 通道变化

Notebook单元9的预处理是Resize70→Crop64→ToTensor→Normalize(mean=std=0.5)。实际模型输入为 `[B,3,64,64]`。宽度倍率、round_nearest与stage配置没有传入额外值，使用v0.9.0默认 `width_mult=1.0`、`round_nearest=8`，所以通道数保持下表值。

| 阶段 | 源码 `[t,c,n,s]` | 真实features索引 | 输出形状 | skip |
| --- | --- | --- | --- | --- |
| Stem | Conv3×3，stride2，3→32 | `features.0` | `[B,32,32,32]` | 无 |
| Stage1 | `[1,16,1,1]` | 1 | `[B,16,32,32]` | 无；输入32与输出16不同 |
| Stage2 | `[6,24,2,2]` | 2,3 | `[B,24,16,16]` | 首块无；后1块identity |
| Stage3 | `[6,32,3,2]` | 4,5,6 | `[B,32,8,8]` | 首块无；后2块identity |
| Stage4 | `[6,64,4,2]` | 7,8,9,10 | `[B,64,4,4]` | 首块无；后3块identity |
| Stage5 | `[6,96,3,1]` | 11,12,13 | `[B,96,4,4]` | 首块stride1但换通道，仍无；后2块identity |
| Stage6 | `[6,160,3,2]` | 14,15,16 | `[B,160,2,2]` | 首块无；后2块identity |
| Stage7 | `[6,320,1,1]` | 17 | `[B,320,2,2]` | 无；输入160与输出320不同 |
| Final features | Conv1×1+BN+ReLU6，320→1280 | 18 | `[B,1280,2,2]` | 无 |
| Pool / reshape | AdaptiveAvgPool(1,1)，reshape保留batch | `_forward_impl` | `[B,1280]` | 无 |
| Classifier | Dropout0.2→替换后的Linear1280→10 | `classifier.0/.1` | logits `[B,10]` | 无Softmax |

`t`是扩展倍数，`c`是输出通道，`n`是该逻辑stage的块数，`s`只用于其首块。总共17个真实 `InvertedResidual`，其中10个调用identity Add，每个块分别实例化参数。图中的7个stage只是对源码settings表建立的逻辑分组；上游 `features` 是一个整体Sequential。

## 图例为什么对应这些源码

| 图中图例 | 源码符号 / 行号 | 对应关系 |
| --- | --- | --- |
| Conv / BN / ReLU6 | `ConvBNActivation.__init__` 第43—53行 | 构造顺序是Conv2d→norm→activation，默认BN与ReLU6；ConvBNReLU是同类的兼容alias |
| Pointwise expansion | `InvertedResidual.__init__` 第77—83行 | `hidden_dim=round(inp*t)`；仅t≠1时添加1×1 Conv/BN/ReLU6 |
| Depthwise spatial convolution | 同符号第85—86行 | 3×3、`groups=hidden_dim`、可能stride2；每个输入通道单独进行空间卷积 |
| Linear bottleneck Conv1×1 | 第87—89行 | 1×1 Conv→BN；没有接ReLU6，也不是nn.Linear |
| Add identity shortcut | `InvertedResidual.forward` 第95—99行 | 仅`stride==1 and inp==oup`时返回`x+self.conv(x)`；没有投影捷径或Add后的激活 |
| Stage外框 / 块索引 | `MobileNetV2.__init__` 第136—167行 | settings表和嵌套循环决定块数、首步stride及Sequential索引 |
| Adaptive pool / reshape | `_forward_impl` 第191—194行 | 先自适应池化到1×1，再reshape保留`x.shape[0]`，然后classifier |
| Replaced Linear | 库第170—173行 + Notebook第89—90行 | 库本来构造1000类头，调用者再替换为10类头；图只表达最终使用的那个Linear |
| Returned logits | `_forward_impl` 第195行；`forward`第197—198行 | forward委托_impl并返回classifier输出，不调用Softmax |

第一块t=1需要特别注意：输入为32通道，`hidden_dim=32`，扩展层完全不存在；depthwise以32通道执行，再projection到16。不能为了统一模板插入虚构的1×1 expansion。后面的t=6块才包含扩展层。

Depthwise的groups是一个Conv2d的真实属性，不把它画成数百条独立模块并列支路。Linear bottleneck的“linear”表示移除非线性；图保留 `kind=conv2d`、参数路径和“no activation”说明，而通过紫色投影角色表达降维，与真实`nn.Linear`分类器的类型区分开。

## skip和参数身份

这里不存在ResNet式用于通道匹配的1×1 projection shortcut。换通道或stride2时，前向直接返回 `self.conv(x)`；只有匹配形状才返回 `x+self.conv(x)`。因此Stage5与Stage7首块即使stride1也没有Add。

展开的identity模块设置`residual=True`，末项明确是Add；旁路起点是该块输入，终点是Add侧口。块后没有ReLU6；不能把旁路终点接到BN、卷积或下一块激活。折叠重复模块仍记录`use_res_connect=True`、块索引和运算顺序。

参数身份可由真实容器索引追溯。例如t=6的 `features.2.conv.0.0/.0.1` 是扩展Conv/BN，`.1.0/.1.1`是depthwise Conv/BN，`.2/.3`是projection Conv/BN。t=1的`features.1.conv`没有expansion，所以depthwise索引0，projection索引1、BN索引2，不能套用相同编号。

Stage3等重复identity模板中 `features.{j}.conv` 的j从`feature_indices`取值，例如Stage3为5、6；它们有相同结构但不同Conv/BN参数。图中的`×2 / ×3`表达顺序执行多个独立实例，不表示同一权重被循环调用。

替换后的 `classifier.1` 是新的 `nn.Linear`对象，默认权重初始化来自Notebook这次构造，而不是库构造末尾对原1000类head执行的初始化循环。图表示结构与参数身份，不混淆初始化的来源。

## 三种粒度和绘制风格

概览显示stem、7个stages、最终features与classifier；每stage保留通道、空间和settings。模块图展开stage中的首块与重复identity模板，并展开stem和head。详细图进一步展开t=1无expansion、t=6无skip、t=6有identity三种代表内部结构；后续重复块保留完整算子顺序摘要、独立参数成员和真实feature索引。完整IR含62个节点，未声称已经把17块的每个内部调用分别展开成数百个节点。

所有内部chain按源码执行顺序声明，再由共享布局自底向上摆放；Add位于末端，head位于顶部。stage外框采用浅蓝，Conv蓝、BN/Add黄、投影紫、ReLU6灰，输入粉、返回紫。分组标题加粗，算子与shape字号统一，主要组件等宽；这些是程序化视觉规则，不是从源码推导出的颜色或坐标。

## 适用边界

绘图绑定两个固定源码项目：Notebook配置和torchvision实现。仅替换Notebook下载地址不能自动识别另一torch.hub版本的内部模型。更改width_mult、stage表、norm_layer、block或输入大小，应重新审阅通道rounding、block索引、形状和skip条件；更换库版本应重新冻结来源并核验符号。

形状由源码参数静态计算，没有执行模型。与legacy DenseNet不同，这份源码特意使用batch-preserving reshape，不会在B=1时去掉batch轴；适配器保留了这个真实差别。checkpoint准确率、训练收敛或任意配置运行兼容性不属于这次图的验证结果。
