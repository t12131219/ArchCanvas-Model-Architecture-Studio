# 条件卷积 VAE：两处条件注入与真实 11 通道重建

本例对应 `rasbt/deeplearning-models` 固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3` 的 `pytorch_ipynb/autoencoder/ae-cnn-cvae.ipynb`。入口是 `ConditionalVariationalAutoencoder.forward(features,targets)`，选用 MNIST 10 类、latent=50 的 notebook 配置。绘图只读 AST、源码与配置，不导入模型，不执行训练、推理或数据下载。

[原 notebook](../sources/deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.ipynb) · [派生源码](../sources/deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.py) · [适配器](../adapters/ccvae.py) · [共享绘图模板](../adapters/convvae.py) · [版本、哈希与 cell 映射](../source_manifest.json)

## 本源码的条件与返回值

输入 image 为 `[B,1,28,28]`，targets 是 `[B]` 的整数数字类别。`to_onehot` 通过 zeros 和 `scatter_` 创建 `[B,10]`，不是 Embedding，也不是分类 Softmax。Encoder 与 Decoder **分别调用一次**该函数，不能将两个 one-hot 调用合并为一个共享模块。

最容易误画的是输出：`dec_deconv_3` 明确硬编码 `out_channels=11`。Forward 返回 `(mu,logvar,z,decoded)`，前三项为 `[B,50]`，decoded 为 **`[B,11,28,28]`**。训练 BCE 的目标 `x_con` 也是图像与十个标签空间通道的拼接。图像展示 cell 使用 `decoded[:n_images,0]`，只选择第 0 通道用于看图；这不改变模型返回的 11 通道。

## 两处条件如何对应源码与连线

| 图中结构 | 真实源码 | 对应关系与形状 |
| --- | --- | --- |
| External class labels | `forward(features,targets)` 参数 | 调用方独立输入 `[B]`，分别接入两次 one-hot 的 `labels` 端口 |
| Encoder one-hot | `encoder` 的 `to_onehot(targets,self.num_classes,device)` | `[B,10]`；不消费图片数值 |
| View one-hot as channels | `.view(-1,self.num_classes,1,1)` | `[B,10,1,1]`，为二维空间广播准备 |
| Ones times one-hot | `torch.ones(B,K,H,W,dtype=features.dtype).to(device)`；`ones * onehot_targets` | `[B,10,28,28]`；每个空间位置共享该样本的 one-hot 类别 |
| Encoder concat | `torch.cat((features,ones),dim=1)` | `[B,11,28,28]`；在首个 Conv2d 前注入条件 |
| Encoder Conv 1 | `enc_conv_1` 的 `in_channels=1+self.num_classes` | 固定 K=10 时为 `11→16`，不能沿用无条件模型的 `1→16` |
| Select z / retain sampled z | Forward 只将 encoded 传给 Decoder | `[B,50]`；保留值作为 Decoder concat 的真实潜向量操作数 |
| Decoder one-hot again | `decoder` 的第二次 `to_onehot` | `[B,10]`；新调用，并不使用 Encoder 的空间 maps |
| Decoder concat | `torch.cat((encoded,onehot_targets),dim=1)` | `[B,60]`；在 `dec_linear_1` 前注入条件 |
| Decoder projection | `Linear(num_latent+self.num_classes,64*2*2)` | `60→256` 后 View `[B,64,2,2]`，Linear 后无激活 |
| Final ConvTranspose/LeakyReLU/Sigmoid | `dec_deconv_3` `16→11`、`F.leaky_relu`、`torch.sigmoid` | 输出全部 11 通道，不是返回单张图像，不是预测标签 logits |

Encoder 标签分支设置 `suppress_input_boundary=True` 和 `external` 输入绑定，避免父图框主链给 one-hot 生成伪图像输入。图片对 `condition_maps` 的侧边依赖只提供 B/H/W 与 dtype，类型为 `shape_dependency`；图片数值另行保留进入 Concat。标签的 Encoder 和 Decoder 两条侧线保留为独立接收端，均来自同一 caller targets。

图中 `Image / condition operands` 和 `Latent / decoder-label operands` 声明 `semantic_mode='operand_bundle'`、`literal_tuple=False`。它们是绘图的操作数分组，源码没有创建这些 tuple；收集后有真实黄色 Concat 算子。`child_inputs` 的 value 项绑定 image 或 selected z，external 项由 targets 侧线供给。条件不能沿主链误流进 Mean/Logvar，也不能被画成残差 Add。

## 卷积路径、后验头和采样

| 路径 | 尺寸变化 | 真实参数 |
| --- | --- | --- |
| Encoder | `[B,11,28,28] → [B,16,12,12] → [B,32,5,5] → [B,64,2,2]` | `enc_conv_1/2/3`，k=6/4/2、s=2/2/2、p=0/0/0 |
| 两个 head | 每个各自 View `[B,256]`，Linear `256→50` | `z_mean`、`z_log_var` 独立权重，均无 head 后激活 |
| Reparameterize | `z=mu+epsilon*exp(logvar/2)`，`[B,50]` | 单个潜变量；内部 `randn`，无训练/推理开关 |
| Decoder projection | Concat `[B,60]` → Linear `[B,256]` → View `[B,64,2,2]` | `dec_linear_1`；无额外激活 |
| Decoder | `[B,64,2,2] → [B,32,4,4] → [B,16,11,11] → [B,11,28,28]` | `dec_deconv_1/2/3`，k=2/4/6、s=2/3/3、p=0/1/4 |

六次卷积均有默认 bias=True，六次 LeakyReLU 均使用默认 slope=0.01；最终转置卷积后也有 LeakyReLU，再接 Sigmoid。没有 BatchNorm、Dropout、池化、attention 或多层潜变量。转置卷积尺寸由 `(n−1)s−2p+k` 静态推出 `2→4→11→28`，不能强行画成 Encoder 的镜像。

后验两个 head 逻辑并列，分别消费最终 Encoder 激活。采样逻辑操作数分组分别读取 mu 和 logvar；epsilon 是函数内生成的辅助随机值，其唯一入边 `mu:shape→epsilon:shape` 只表达 `z_mu.size(0/1)`，随后 epsilon 值输入乘法。它不是用户噪声输入，不包含 mu 的特征数值，也不是可学习参数。

`reparameterize` 没有 `self.training` 条件，所以 eval 也采样。Encoder 实际返回 `(mu,logvar,encoded)`；Forward 将 encoded 交给 Decoder，再返回四字段 tuple。图中 mu/logvar 旁路到两处返回节点，z 旁路到最终 encoded 端口；不能把它们一起送入 Decoder 的 Linear。

## 固定类数的边界

`self.num_classes` 用于首层 `in_channels=1+K`、两次 one-hot 与 Decoder `in_features=latent+K`。但是最后转置卷积的 `out_channels=11` 不是 `1+K` 表达式。修改 K 时不能声称输出自动跟随类别数；当前适配器只承诺 notebook 的 K=10 配置。

`num_features=784` 构造器参数没有被使用。内部两次 head View 与 Decoder View 都固定 `64×2×2`，因此这是 MNIST 28×28 的静态配置，不是任意图像分辨率的通用适配器。图中 B 保持符号化，形状不是运行时观测结果。

## 三种视图与 Transformer 风格布局

概览折叠 Forward；模块视图展示 Encoder、z 选择、Decoder 和实际返回；详细视图展开两个条件注入位置、独立 posterior heads、采样算术与投影。六个卷积 stage 各保持独立身份，stage 1/3 展开 Conv/LeakyReLU，stage 2 代表性折叠以缩短重复结构；全部语义节点、参数和来源仍保留在 IR。

主链以及模块内部都自底向上。并列布局由独立操作数及共同生产者决定：图像/标签 maps 两列、mu/logvar 两个头、mu/噪声缩放两列、z/Decoder one-hot 两列。并列不代表 Python 同时执行，也不表示相同颜色的节点共享权重。程序先测量文字与子框，再计算总高度、列宽、间距、入口/收集总线及外侧路由。

字体与配色继承 Transformer 原型：深色轮廓、浅蓝 Encoder/Conv、浅粉 Decoder/input、紫色 Linear/return、绿色采样/Sigmoid、黄色 Concat/Add、浅灰 LeakyReLU。条件张量采用浅蓝 tensor 图元，caller labels 采用粉色 input 图元，帮助区分源数据与计算结果。

独立标签、随机值、后验保留值和图片 shape 引用使用带角色的辅助线。折叠时真实端口投影到其可见容器；IR 与 SVG 提示保留真实生产者和接收端。共享引擎检查端点、直角路径、至少 18px 末段、边框避让及不同辅助张量不共用线段。主张量路径上行；侧边依赖为避障可局部下降。

## 图示纠正与核验范围

按本源码应保留两次不同空间形态的条件注入，不能只把标签画在 Encoder 的末端，也不能用一个共享 Embedding 代替两次 one-hot。没有 forward Softmax 或类别预测头；标签通道是重建目标的一部分。显示第 0 图像通道属于调用方预览，不应加入模型 Forward。

调用方训练循环重新构建 `x_con=cat(image,label_maps)` 并计算 KL+BCE。那些条件处理和损失是训练范围，不是 Forward 中第三个 one-hot。随机生成示例调用 `model.decoder(rand_features,labels)`，也是独立入口；本例绘制的是完整条件重建路径。

`validate_ir` 在共享 ConvVAE 检查之外核验两处条件生产者、仅由 labels 供给的两个 one-hot、图片 shape 引用、两处 Concat、Linear 输入 60 以及真实 11 通道输出。将输出篡改成 1 通道的 deepcopy 负例会被拒绝。静态语义与几何通过仍不能宣称模型已经数值运行验证。

`ccvae.py` 复用 `convvae.py` 的绘图模板；共享的是程序布局与语义构建逻辑，源引用仍绑定 `ConditionalVariationalAutoencoder`，与无条件 ConvVAE 无权重共享。新增来源或配置需独立审阅，不能仅替换 `--source-root` 后沿用。
