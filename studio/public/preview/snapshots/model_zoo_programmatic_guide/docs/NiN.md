# NiN：三个 mlpconv 阶段与真实分类输出

本例来自 `rasbt/deeplearning-models` 的 `pytorch_ipynb/cnn/nin-cifar10.ipynb`。原 notebook 已冻结为本地来源，代码 cell 按原顺序派生为 `.py`，不运行 notebook、不加载 CIFAR-10、不执行 CUDA 训练。

[原 notebook](../sources/deeplearning-models-batch2/pytorch_ipynb/cnn/nin-cifar10.ipynb) · [派生源码](../sources/deeplearning-models-batch2/pytorch_ipynb/cnn/nin-cifar10.py) · [适配器](../adapters/nin.py) · [版本、哈希及 cell 映射](../source_manifest.json)

图针对 `NiN(NUM_CLASSES)`、`NUM_CLASSES=10`、CIFAR-10 三通道 32×32 输入。批量维 B 符号化；配置里的 `BATCH_SIZE=256` 是训练设置，不是模型强制维度。

## 与源码一一对应的结构

源码把所有卷积、激活、池化和 Dropout 放在一个 `self.classifier = nn.Sequential(...)` 中。绘图将相邻算子分成三个 `mlpconv` 和 feature stages，是对真实连续片段的逻辑分组，**不是声称源码定义了三个 mlpconv 类**。

| 图中模块 | Sequential 索引 / 参数身份 | 计算与输出形状 |
| --- | --- | --- |
| mlpconv 1 | Conv `classifier.0/.2/.4`，ReLU `.1/.3/.5` | 5×5：3→192；1×1：192→160；1×1：160→96，输出 `[B,96,32,32]` |
| 第一次降采样 | MaxPool `.6`；Dropout `.7` | kernel=3、stride=2、padding=1，输出 `[B,96,16,16]` |
| mlpconv 2 | Conv `.8/.10/.12`，ReLU `.9/.11/.13` | 5×5：96→192；两层独立 1×1：192→192，输出 `[B,192,16,16]` |
| 第二次降采样 | AvgPool `.14`；Dropout `.15` | kernel=3、stride=2、padding=1，输出 `[B,192,8,8]` |
| mlpconv 3 | Conv `.16/.18/.20`，ReLU `.17/.19/.21` | 3×3：192→192；1×1：192→192；1×1：192→10，输出 `[B,10,8,8]` |
| 最后平均池化 | AvgPool `.22` | 固定 kernel=8、stride=1、padding=0，输出 `[B,10,1,1]` |
| View | `NiN.forward` 的 `x.view(x.size(0),self.num_classes)` | 保留 batch 轴，得到 `[B,10]` logits |
| logits / probabilities 并列返回 | `torch.softmax(logits,dim=1)`；`return logits,probas` | 原始 logits 与 Softmax 的结果各为 `[B,10]` |

每一层卷积后都有 `ReLU(inplace=True)`，**包括最后输出 10 个 class maps 的 1×1 卷积**。源码不是用单独的 `Linear` 生成 logits；最后平均池化直接把每个类别的空间响应汇成一个数。由于这个实际 ReLU，所选路径的 logits 非负；随后 forward 内部 Softmax 生成概率。

两个 192→192 的同形 1×1 卷积是不同索引、不同参数。颜色相同表示同一种图例；`classifier.10` 与 `classifier.12` 不共享权重。每个 Conv 的核在其空间位置上共享，这是卷积算子的内在参数复用，与跨层共享不同。

## 三粒度与程序化排布

概览展示三个 feature stages、pooled map reshape 和双字段返回。模块图展开每个 stage 的 mlpconv 容器、降采样和 Dropout；详细图进一步展开九组 Conv/ReLU。所有视图基于同一语义 IR，不改变模型顺序或参数身份。

适配器按源码输入→输出顺序声明 `chain.items`，共享布局器反向分配纵坐标，使主流程和每个 mlpconv 内部都从下向上。主要 stage 等宽、内部 Conv/ReLU 沿中轴排列；标题、形状和证据编号占用预留区域。最后 `parallel` 仅表示原 logits 向保留分支、Softmax 分支分发，再收集为 tuple；它不隐含算术 Add。

字体、深色实线边框和配色保持 Transformer 系列一致：feature stages 浅蓝、卷积蓝色、池化浅绿、ReLU 中性色、Softmax 更鲜明的绿色。相同类型复用图元，参数身份留在 IR 和悬停提示中。

## 不能由概念图替代的实现差异

- 第一次降采样是 MaxPool，第二次是 AvgPool；不能把两处都概括为 MaxPool。
- 最后池化固定为 8×8，在当前 CIFAR-10 路径上相当于全局平均池化，但源码没有 `AdaptiveAvgPool2d`。
- 最后 1×1 Conv 的输出硬编码为 **10**，`num_classes` 只控制 View。改变构造参数不会自动修改 class maps。
- 输出包含 logits 和 probas，Softmax 确实属于 forward；损失 `cross_entropy(logits,targets)` 位于训练 cell。
- 原 `compute_accuracy` 没有调用 `model.eval()`；训练循环之后仅关闭梯度不会停用 Dropout。图如实保留两个 `Dropout(0.5)`，不把函数名“accuracy”误当作已进入 eval。

图表达的是 forward 结构，Dropout 的是否随机丢弃取决于调用方模型状态。源码的 CUDA 设备字符串与训练超参数不是架构算子，未画进模型图。形状来自指定 32×32 输入的静态推导，并非运行时观测；替换输入大小或类别配置需要重新审阅固定池化和 View 是否匹配。
