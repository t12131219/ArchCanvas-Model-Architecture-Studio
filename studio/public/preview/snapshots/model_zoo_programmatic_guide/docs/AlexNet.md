# Grouped AlexNet：以 CIFAR-10 教学实现为准的三层架构图

这个模型来自 `rasbt/deeplearning-models` 的 `cnn-alexnet-cifar10-grouped.ipynb`。原 Notebook 与保持单元映射的 [派生 Python](../sources/deeplearning-models-batch2/pytorch_ipynb/cnn/cnn-alexnet-cifar10-grouped.py) 都固定保留；源码版本和 SHA256 见 [source_manifest.json](../source_manifest.json)。[适配器](../adapters/alexnet.py) 表达这个具体实现，而不是根据 AlexNet 名字补全原论文或 ImageNet 配置。

程序只读取源码文本和 AST，不导入上游模型、不执行 Notebook、不训练或下载 CIFAR-10。图中形状按选定 eval 配置静态推导。Notebook 单元 13 设 `NUM_CLASSES=10`；单元 17 在调用者中先 Resize 到 70×70，再 Crop 为 64×64，因此模型输入为 `[B,3,64,64]`，不是 CIFAR-10 原始 32×32，也不是 ImageNet 的 224×224。

## 源码对应关系与形状

| 图中节点 / 模块 | 对应源码 | 输入 → 输出 / 对应理由 |
| --- | --- | --- |
| Input image | 调用者 `Resize70 / Crop64` 第 83—89 行；`AlexNet.forward(x)` | `[B,3,64,64]`；图从预处理后模型输入开始 |
| Five convolutional stages | `self.features` 第 133—151 行；第 164 行调用 | 一个 Sequential，按输入→输出顺序形成主 chain |
| Conv stage 1 | `features.0/.1/.2`：Conv11、ReLU、MaxPool3 | 3→64 通道，Conv stride4/padding2：64→15；Pool stride2：15→7 |
| Conv stage 2 | `features.3/.4/.5`：Conv5、ReLU、MaxPool3 | 64→192，groups2；Conv保持7×7，Pool输出3×3 |
| Conv stages 3 / 4 | `features.6/.7` 和 `.8/.9` | 192→384→256，两个3×3 grouped Conv均保持3×3 |
| Conv stage 5 | `features.10/.11/.12` | Conv256→256保持3×3；最后MaxPool输出1×1 |
| AdaptiveAvgPool2d 6×6 | 第152行构造，第165行调用 | `[B,256,1,1] → [B,256,6,6]`，明确输出目标不是固定pool kernel |
| Flatten | 第166行 `view(B,256*6*6)` | `[B,9216]`，保留 batch轴 |
| Hidden classifier 1 / 2 | `classifier.0/.1/.2` 和 `.3/.4/.5` | 两组 Dropout0.5→Linear→ReLU：9216→4096→4096 |
| Final Linear | `classifier.6` | 4096→10，得到原始 class logits |
| Computed Softmax · unused | 第168行 `probas=F.softmax(logits,dim=1)` | 实际执行，得到 `[B,10]`，但这个局部变量没有被返回 |
| Returned logits | 第169行 `return logits` | 输出只有 `[B,10]` logits，不能画成 `(logits,probas)` |

卷积和池化的边长采用 `floor((H+2p-k)/s)+1`。本配置第一次卷积为 `floor((64+4-11)/4)+1=15`；第一次 Pool 输出7，第二次输出3，最后输出1。

AdaptiveAvgPool 的“池化”名称不保证输出尺寸一定小于输入。本源码指定 `(6,6)`，在64×64调用者配置下输入确实只有1×1，因此每个自适应输出bin仍取这个单一值，产生6×6。这是源码结构的实际对应；图没有自行修改成1×1 global average pool，也没有假设进入该算子时已经是6×6。

## groups=2 为什么不拆成伪并列模块

源码第二到第五个 Conv2d 都设置 `groups=2`，第一层为默认 `groups=1`。groups 控制同一卷积参数张量的通道分组：例如 Conv64→192，单组输入32、输出96，权重尺寸为 `[192,32,5,5]`。它不是两个单独命名的 Python module，也不需要适配器创造两套图框、Concat 或并行执行路径。

因此图保留每个真实 Conv2d 一个节点，标签标明 groups，参数身份为 `features.3`、`.6`、`.8`、`.10`。同色表示同类卷积，参数路径不同表示独立权重。整个模型共有5个卷积和3个Linear，均有不同参数身份。

该教学实现没有 LRN，也没有原论文的双GPU计算结构。仅凭名字加入这些图例会失去源码对应关系。

## 计算结果与返回结果

Softmax虽然没有返回，仍在 Python eager forward 中执行。适配器把它放在侧面，并通过 `computed_unused` 依赖接收 classifier 的 logits；节点标明 `returned=False / origin=internal_derived_unused`，没有任何连线回到返回值。这保留计算事实，同时保证主流程最终输出仍然只有 logits。

`aux_inputs` 在共享契约中也容纳主chain之外的内部派生节点；这个字段并不把 Softmax声明为用户输入。节点真实 `kind=softmax`、来源 `AlexNet.forward`、输入边和“computed / unused”标签共同明确它的角色。虚线侧边连线表示不在主chain上的真实数据依赖，并不表示解释性虚构算子。

两处 Dropout也是真实源码模块。图保持其调用位置并写明选定 eval 时为 identity；train时的随机置零与重缩放不是当前配置的数值行为。没有把 Dropout强行从语义IR中删除。

## 三种粒度与统一风格

概览折叠 features和classifier，保留 AdaptiveAvgPool、Flatten、最终返回以及旁边unused Softmax。模块图展开5个卷积阶段与2个隐藏分类阶段。详细图进一步展开各阶段真实的Conv/ReLU/Pool与Dropout/Linear/ReLU，完整IR含35个节点。

阶段是基于源码连续操作建立的逻辑分组，不声称上游存在额外的 `conv_stage1` 等属性。列表顺序来自Sequential和forward；所有嵌套chain统一自底向上。组尺寸由子节点测量、标题、内边距和间隔递归确定，主要组件等宽对齐；旁边Softmax的依赖由正交避障路由分配。

视觉主题沿用Transformer：输入粉、Conv蓝、Linear与返回紫、激活灰、池化浅绿、Softmax绿；深色实线边框、加粗分组标题和统一字号区分包含层级。真实语义仍为Conv2d、MaxPool、Dropout等，不把它们重命名为Attention或Transformer模块。

## 原型边界

配置变化需要重新推导输入边长、实际features输出和classifier尺寸。调整groups还会改变卷积权重形状；换成标准ImageNet AlexNet则应建立对应源码适配器。当前结论是固定源码和64×64、10类eval路径的审阅结果，不代表已运行模型或验证训练准确率。
