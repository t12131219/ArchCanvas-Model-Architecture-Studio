# ConvAE：nearest 插值解码器的源码对应

本适配器对应固定 `rasbt/deeplearning-models` Notebook `pytorch_ipynb/autoencoder/ae-conv-nneighbor.ipynb`，入口为 `ConvolutionalAutoencoder.forward(x)`。它是 **MNIST 卷积自编码器**，解码器使用 nearest-neighbor 插值与普通 Conv2d。图像不能因为源码注释写了“Unpool”就改画为 MaxUnpool 或转置卷积。

[原 Notebook](../sources/deeplearning-models-batch2/pytorch_ipynb/autoencoder/ae-conv-nneighbor.ipynb) · [派生源码](../sources/deeplearning-models-batch2/pytorch_ipynb/autoencoder/ae-conv-nneighbor.py) · [适配器](../adapters/convae.py) · [来源与原 cell 映射](../source_manifest.json)

程序冻结原 Notebook、顺序派生 `.py`、保存 cell 索引及原 cell 内行号，再用 AST 定位类和方法。绘图没有导入上游代码、下载 MNIST 或执行训练。配置来自原 Notebook cell 7，构造/forward 来自 cell 9，模型调用与训练损失在 cell 11；cell 索引从 0 起。

## 固定配置与静态形状

输入是未 flatten 的 `[B,1,28,28]` MNIST 张量，调用方 `ToTensor` 把像素缩放到 `[0,1]`。`B` 是运行时批量维度，训练 batch 设置 128 不等于所有调用都固定为 128。

所有 Conv2d 都是 kernel 3、stride 1、padding 1、默认 bias=True；因此空间边长不变。两次 MaxPool 的 kernel/stride 均为 2，没有 padding，边长依次减半。解码器两次 `F.interpolate(...,scale_factor=2,mode='nearest')` 加倍空间边长，通道数不变。

| 源码步骤 | 输入 / 输出形状 | 参数身份或函数依据 |
| --- | --- | --- |
| `conv_1` → LeakyReLU | `[B,1,28,28]` → `[B,4,28,28]` | `self.conv_1`，`F.leaky_relu(x)` |
| `pool_1` | `[B,4,28,28]` → `[B,4,14,14]` | `MaxPool2d(2,2)` |
| `conv_2` → LeakyReLU | `[B,4,14,14]` → `[B,8,14,14]` | `self.conv_2` |
| `pool_2` | `[B,8,14,14]` → `[B,8,7,7]` | `MaxPool2d(2,2)` |
| 第一次 nearest interpolation | `[B,8,7,7]` → `[B,8,14,14]` | `F.interpolate(scale_factor=2,mode='nearest')` |
| `conv_3` → LeakyReLU | `[B,8,14,14]` → `[B,4,14,14]` | 实际构造 `Conv2d(8,4,...)` |
| 第二次 nearest interpolation | `[B,4,14,14]` → `[B,4,28,28]` | 同样的函数，但另一个调用点 |
| `conv_4` → LeakyReLU | `[B,4,28,28]` → `[B,1,28,28]` | `self.conv_4`；激活后变量命名为 `logits` |
| Sigmoid | `[B,1,28,28]` → `[B,1,28,28]` | `probas = torch.sigmoid(logits)` |
| Forward tuple | 两个 `[B,1,28,28]` | `return logits, probas` |

源码只给 `F.leaky_relu(x)`，不传负半轴斜率；适配器按该 API 默认契约记录 `negative_slope=0.01`。它与前一批全连接 VAE 中显式 `negative_slope=0.0001` 不同，不能把两者复用为同一配置。

## 图框如何对应源码

Encoder 外框表达 `forward` 注释分区中的连续编码路径；Decoder 外框表达对应解码路径。四个 stage 框是适配器对连续算子的**逻辑分组**，便于模块级展示，并不声称上游额外定义了四个 `nn.Sequential` 属性。

编码两个 stage 分别是 Conv→LeakyReLU→MaxPool。解码两个 stage 分别是 nearest interpolate→Conv→LeakyReLU。主要阶段通过 `fill_width` 对齐宽度；详细粒度再展开 stage 的三个实际算子。

“Encoded feature map” 是 `pool_2` 输出的逻辑标签，保存形状 `[B,8,7,7]`；它不是 Flatten、Linear、采样或新的真实计算。模型没有全连接 latent，也没有 VAE 的 mean/logvar heads。

末端并列图例一条保留 activated logits，一条执行 Sigmoid，输出汇集为真实 tuple。`parallel` 在这里复制同一个 logits 到两条路径，不使用 tuple 字段 dispatch；汇集总线不意味着求和或拼接。四个卷积参数身份为 `conv_1` 至 `conv_4`，完全独立。两个插值算子和两个 pooling 算子没有训练权重。

## 源码注释与真实执行不一致时如何处理

该 Notebook 的 decoder 注释两次写“Unpool”，但实际 `forward` 调用 `F.interpolate`。池化也没有 `return_indices=True`，不保存最大值位置；因此不能补画 MaxPool indices→MaxUnpool 的旁路。这里的 nearest 插值只是非参数化 resize，后续 Conv2d 才承担通道变换和学习。

`conv_3` 上方注释写了 `14x14x8 => 14x14x8`，实际 `out_channels=4`。图按构造与真实调用把它标为 **8→4**，说明中保留这个注释差异，原始源码没有被修改。

最后 `conv_4` 之后仍执行 LeakyReLU，再命名为 logits，随后 Sigmoid。其他自编码器可能直接对最终卷积输出应用 Sigmoid，但这份源码不是如此；图保留这项行为，没有以“常见架构”替换。

## 三种粒度和风格

概览保留输入、Encoder、encoded map、Decoder、返回分支和 tuple。模块粒度展开 Encoder/Decoder，显示四个逻辑 stage；详细粒度展开各 stage 中的 Conv、activation、pool/resize，并保留张量形状、参数身份和来源证据。三个视图来自同一 IR，折叠仅改变显示。

所有 `chain.items` 按输入→输出声明，共享引擎将列表首项放在底部，内外都从下向上读取。Encoder 浅蓝、Decoder 浅粉，Conv 蓝、概率绿色、张量选择浅蓝，激活中性浅色；深色边框和字体沿用 Transformer 风格。同色表示绘图角色，不表示相同实现或权重共享；nearest 与 pool 也不会因为放大/缩小对称就具有互逆语义。

训练 cell 11 把 logits 交给 `binary_cross_entropy_with_logits(logits, features)`。这个 loss、Adam、反向传播与数据加载属于调用方训练流程，不作为模型 forward 节点。图只解释该固定实现的前向重建结构，没有验证数值性能或模型在现代 PyTorch 环境的运行结果。
