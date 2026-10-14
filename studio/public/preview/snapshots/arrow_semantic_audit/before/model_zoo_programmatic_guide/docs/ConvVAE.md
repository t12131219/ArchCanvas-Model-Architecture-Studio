# ConvVAE：独立后验头、内部采样与非对称卷积解码

本例对应 `rasbt/deeplearning-models` 固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3` 的 `pytorch_ipynb/autoencoder/ae-conv-var.ipynb`。入口为 `ConvVariationalAutoencoder.forward(features)`，选用 notebook 的 MNIST 配置。只解析冻结源码与 AST，不导入模型，不执行 notebook、训练或推理。

[原 notebook](../sources/deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-conv-var.ipynb) · [派生源码](../sources/deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-conv-var.py) · [适配器](../adapters/convvae.py) · [版本、文件哈希与 cell 映射](../source_manifest.json)

## 输入、形状与参数

输入是 `[B,1,28,28]` 的 MNIST 灰度图，调用方 `ToTensor` 将像素缩放到 `[0,1]`。与全连接 VAE 不同，调用方没有 Flatten，图像直接进入卷积。`num_latent=15`，B 是符号批量维；训练设置 `batch_size=128` 不表示所有调用都只能取 B=128。构造器虽然接收 `num_features=784`，实际没有使用这个参数来确定层的尺寸。

| 图中节点或容器 | 源码身份 / 表达式 | 输出与对应理由 |
| --- | --- | --- |
| Encode stage 1 | `enc_conv_1`：Conv2d `1→16`，k=6/s=2/p=0；随后 `F.leaky_relu` | `[B,16,12,12]`；卷积和激活是两次真实调用 |
| Encode stage 2 | `enc_conv_2`：Conv2d `16→32`，k=4/s=2/p=0；随后 LeakyReLU | `[B,32,5,5]`；与 stage 1 参数独立 |
| Encode stage 3 | `enc_conv_3`：Conv2d `32→64`，k=2/s=2/p=0；随后 LeakyReLU | `[B,64,2,2]`；两个后验头的共同生产者 |
| 并列 Mean / Log-variance heads | `z_mean`、`z_log_var`，各为 Linear `256→15`；各自调用 `x.view(-1,64*2*2)` | 两个 `[B,15]`；同输入、独立权重、不同统计量，无 head 后激活 |
| Internal Gaussian epsilon | `reparameterize` 内 `torch.randn(z_mu.size(0),z_mu.size(1)).to(device)` | 内部生成 `[B,15]` 的随机张量；只读取 mu 的形状，不读取其数值 |
| Scale Gaussian noise | `torch.exp(z_log_var/2.)` 和 `eps * ...` | 先除以 2 得到标准差，再逐元素缩放噪声 |
| Add mu + std * epsilon | `z_mu + eps * torch.exp(z_log_var/2.)` | 单个 `[B,15]` 潜向量 z，无第二层潜变量 |
| Encoder return | `return z_mean,z_log_var,encoded` | 真实三字段 tuple；不是 concat 或 add |
| Select encoded z | `forward` 解包后调用 `self.decoder(encoded)` | Decoder 只读取 z，不读取后验统计量的拼接 |
| Latent projection + reshape | `dec_linear_1`：Linear `15→256`；`x.view(-1,64,2,2)` | `[B,64,2,2]`；Linear 后没有激活 |
| Decode stage 1 | `dec_deconv_1`：ConvTranspose2d `64→32`，k=2/s=2/p=0；LeakyReLU | `[B,32,4,4]` |
| Decode stage 2 | `dec_deconv_2`：ConvTranspose2d `32→16`，k=4/s=3/p=1；LeakyReLU | `[B,16,11,11]` |
| Decode stage 3 + Sigmoid | `dec_deconv_3`：ConvTranspose2d `16→1`，k=6/s=3/p=4；LeakyReLU；`torch.sigmoid(x)` | `[B,1,28,28]`；末端也是先激活，再 Sigmoid |
| Forward return | `return z_mean,z_log_var,encoded,decoded` | 三个 `[B,15]` 和一个 `[B,1,28,28]`，不能简写成只返回图像 |

六个卷积均省略 `bias`，采用 API 默认 `True`；六次 `F.leaky_relu(x)` 均省略 slope，采用默认 `0.01`。源码没有 BatchNorm、Dropout、池化或 Encoder/Decoder 权重绑定。相同 Conv 图元表示同类算子；`enc_conv_1`、`enc_conv_2`、`enc_conv_3`、三个 `dec_deconv_*` 仍是六套独立参数。

## 为什么 Decoder 不是 Encoder 的镜像

Encoder 空间尺寸为 `28→12→5→2`。Conv2d 使用 `floor((n+2p−k)/s)+1`；这里 dilation=1。Decoder 使用转置卷积 `n_out=(n−1)s−2p+k`，dilation=1、output_padding=0：

```text
2 -- k2,s2,p0 --> 4
4 -- k4,s3,p1 --> 11
11 -- k6,s3,p4 --> 28
```

因此 Decoder 的 stride 是 `2/3/3`，而不是 Encoder 的 `2/2/2`。将两端画成完全镜像虽然常见，却不符合这份源码。图中展示真实 `2→4→11→28`；形状推导是静态计算，不是运行记录。该配置固定使用 `64×2×2=256` 的 View；换图像尺寸不能仅修改输入标签后继续沿用。

## 逻辑操作数和真实 tuple 的区分

后验头并列容器与采样操作数并列容器都声明 `semantic_mode='operand_bundle'`、`literal_tuple=False`。这是为绘图建立的逻辑分组；源码没有在两个 Linear 之间创建 `(mu,logvar)` tuple，也没有先创建 `(mu,std*epsilon)` tuple。

适配器通过 `child_inputs` 保留真实生产者：两个 head 分别读取 `enc3.activation`；采样的保留 Mean 分支读取 `mu`，缩放噪声分支读取 `logvar`。收集后仍需显式 Add 才得到 z，不能让并列容器隐含求和。真实 tuple 仅出现在 Encoder 和 Forward 的 `return`，字段通过同名保留端口分别到达返回节点。

epsilon 的入边是 `mu:shape→epsilon:shape`，类型为 `shape_dependency`；其出边才是到乘法 `epsilon` 端口的随机张量值。这样既忠实表达 `randn(z_mu.size(0),z_mu.size(1))`，又不会声称 Mean 的数值用于生成 Gaussian 值。随机源在 `reparameterize` 内创建，不是用户输入，也不是可学习参数；其 `device` 来自 notebook 的全局变量。

这份代码没有 `self.training` 分支。train 和 eval 均执行 `randn`，所以不能把 eval 图改成确定性的 `z=mu`。

## 三种粒度如何程序化排布

图沿用 Transformer 原型的 DejaVu Sans 字体、深色轮廓与浅色填充：Encoder 浅蓝、Decoder 浅粉、卷积计算块浅蓝、Linear/返回值紫色、算术合并黄色、随机源/Sigmoid 绿色、LeakyReLU 浅灰。颜色表示视觉角色，不表示参数共享。

主链的 `items` 依源码输入到输出顺序保存，布局器先测量尺寸，再把首项放在底部。因此 `Conv→LeakyReLU`、`Linear→View`、`logvar/2→exp→乘法` 内部都和全局流程一样自底向上。两个 head 按共同生产者并列；采样的 Mean 与噪声缩放也按独立操作数并列。并列表达数据依赖，未声称 Python 两次调用实际并发执行。

概览折叠整个 `forward`；模块图展示 Encoder、z 选择、Decoder 和四字段返回；详细图展开后验头、单层采样、投影与卷积 stage 1/3。stage 2 保留为独立折叠块，仍显示自己的参数、来源和形状，以避免重复结构占据过多高度。六个卷积 stage 全部保留在同一 IR；折叠不是删层，也不是 stage 1 权重复用。

mu/logvar/z 的保留线、内部 epsilon 和 shape 引用使用独立辅助路线。粗粒度时真实端点投影到可见容器边界；IR 与 SVG 提示仍记录原节点/端口。共享路由器检查端口、直角路径、至少 18px 末段、边框避让及不同辅助张量不共用线段。主张量路径上行；侧方 shape/保留线允许为避障局部下降，不能把这种下降解读为执行逆序。

## 范围、检查和扩展

KL 与像素 BCE 位于调用方训练循环，不属于 `forward`。随机生成示例直接调用 `model.decoder(rand_features)`，是另一入口；当前三张图的范围是完整重建 Forward，不能用独立随机生成替换 Encoder 采样。

`validate_ir` 检查关键节点、独立后验参数、真实生产者、内部随机源及其唯一形状入边、采样公式、保留字段、卷积尺寸/激活和末端 Sigmoid。语义负例将 epsilon 改成用户输入，会被拒绝。布局验证独立检查几何；两类验证均不能替代数值运行正确性检查。

`ccvae.py` 复用本适配器的 `_build/_validate` **绘图辅助函数**，不导入任何上游模型。共用模板并不表示两个 VAE 共用训练权重；CCVAE 的所有节点仍绑定自己的类、源文件和参数。换源码版本、潜维或图片尺寸时，需重新审阅适配器与 profile，不能把这个模板当作任意 VAE 自动识别器。
