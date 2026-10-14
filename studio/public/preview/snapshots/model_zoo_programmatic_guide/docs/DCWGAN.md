# DC-WGAN：真实生成器、critic 与训练调用边界

本例取自 `rasbt/deeplearning-models` 固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3` 的 `pytorch_ipynb/gan/dc-wgan-1.ipynb`。配置为 MNIST、latent=100 的卷积 Wasserstein GAN。绘图读取源码、AST 与 notebook cell 映射，不导入或执行模型。

[原 notebook](../sources/deeplearning-models-batch4/pytorch_ipynb/gan/dc-wgan-1.ipynb) · [派生 Python](../sources/deeplearning-models-batch4/pytorch_ipynb/gan/dc-wgan-1.py) · [适配器](../adapters/dcwgan.py) · [版本、哈希和 cell 映射](../source_manifest.json)

## 图的范围不是一个 GAN.forward

源码 `GAN` 没有自定义 `forward`，只有 `generator_forward(z)` 和 `discriminator_forward(img)` 两个入口。前者调用 `self.generator` 并返回 `[B,1,28,28]` 图片；后者实际调用的是 **全局 `model.discriminator(img)`**，再返回 `pred.view(-1)` 的 `[B]` critic 分数。图保留这一接收者事实，没有悄悄修复为 `self.discriminator`。

整图是训练 cell 中的**数据依赖片段**：噪声到 G，再分别进入 G 目标的 D 调用与 D 目标的 detached fake 调用；真实图像进入第三个 D 调用。三路顶部互不合并，没有模型三字段 tuple，也没有伪造联合 `GAN.forward`。层内部依然是两个真实 `nn.Sequential`。

图上的三张 D 调用框是三个调用位置，**共享一个 `model.discriminator` 实例、参数和 BatchNorm 缓冲区**。每个 batch 实际先执行 G 目标 D 一次，再在 `num_iter_critic=5` 中分别执行 real/fake：共有 `1+5×2=11` 次 critic 前向。三列是调用位置的投影，不是只有三次执行，也不是三个独立 critic。

## 生成器图例与精确尺寸

| 图中结构 | 源码 Sequential 身份 | 静态输出 |
| --- | --- | --- |
| Caller Uniform noise | 训练 cell 的 `zeros((targets.size(0),LATENT_DIM)).uniform_(0.0,1.0)` | z `[B,100]`，外部均匀分布 `[0,1)`，不是 Gaussian |
| Linear / BN / LeakyReLU | `generator.0/.1/.2`；Linear `100→3136`，bias=False；BN1d3136；slope=0.0001 | `[B,3136]` |
| Reshape1 | `generator.3`；类内 `input.view(input.size(0),64,7,7)` | `[B,64,7,7]` |
| Upsample 1 | `generator.4/.5/.6`；ConvTranspose64→32，k3/s2/p1；BN32；LeakyReLU | `[B,32,13,13]` |
| Upsample 2 | `generator.7/.8/.9`；ConvTranspose32→16，k3/s2/p1；BN16；LeakyReLU | `[B,16,25,25]` |
| Upsample 3 | `generator.10/.11/.12`；ConvTranspose16→8，k3/s1/p0；BN8；LeakyReLU | `[B,8,27,27]` |
| Upsample 4 / Tanh | `generator.13/.14`；ConvTranspose8→1，k2/s1/p0；Tanh | `[B,1,28,28]`，像素范围 `[-1,1]` |

转置卷积 dilation=1、output_padding=0，空间尺寸用 `(n−1)s−2p+k` 得到 `7→13→25→27→28`。不能套用 DCGAN 常见的 `7→14→28` 教材图。这份源四个 ConvTranspose 全部 bias=False，末层没有 BN 或 LeakyReLU，直接 Tanh。

targets 的**类别值不参与条件生成**。只有 `targets.size(0)` 为噪声、valid/fake 标签向量和 View 提供 B。图使用 `targets:shape→noise:batch_shape` 的虚线形状依赖，目标大小节点不会把数字标签送入 Linear；没有 Embedding、one-hot 或条件 concat。

## critic 与源码参数共享

| critic 阶段 | 所有调用共用的参数身份 | 输出 |
| --- | --- | --- |
| Conv/BN/LeakyReLU 1 | `discriminator.0/.1/.2`；Conv1→8，k3/s2/p1 | `[B,8,14,14]` |
| Conv/BN/LeakyReLU 2 | `discriminator.3/.4/.5`；Conv8→16，k3/s2/p1 | `[B,16,7,7]` |
| Conv/BN/LeakyReLU 3 | `discriminator.6/.7/.8`；Conv16→32，k3/s2/p1 | `[B,32,4,4]` |
| Flatten | `discriminator.9`；`input.view(input.size(0),-1)` | `[B,512]`，`32×4×4=512` |
| Linear | `discriminator.10`；Linear512→1，默认 bias=True | `[B,1]` |
| discriminator_forward return | `pred.view(-1)` | `[B]` 原始 critic score |

三个 Conv2d 均 bias=False；全部真实 LeakyReLU 明确 slope=0.0001、inplace=True。末 `nn.Sigmoid()` 是注释，所以图不画概率头。WGAN score 不是 logits→Sigmoid 后的真假概率，不要求处于 `[0,1]`。

BN 层采用默认 affine=True、track_running_stats=True、eps=1e−5、momentum=0.1。当前图选训练循环的 `model.train()`，BN 使用 batch 统计并更新 running buffers；不能与最后展示 cell 的 `model.eval()` 混用。相同 D 的三处调用共享 BN affine 和缓冲区，调用次数增多不产生新实例。

源码中 `Dropout2d`、debug hooks 只在注释或多行字符串中出现，没有被执行。图没有把这些内容算作网络层。

## 三路调用与 detach 的意义

```python
# Generator objective: 不 detach，梯度经 D 回到 G
generated_features = model.generator_forward(z)
discr_pred = model.discriminator_forward(generated_features.view(B,1,28,28))

# Discriminator objective: 同一批生成图，仅此处 detach
discr_pred_fake = model.discriminator_forward(
    generated_features.view(B,1,28,28).detach()
)
```

`detach` 属于调用方，不属于 Generator 或 critic 的 Sequential。它保留图像值与形状，切断 autograd 回到 G 的路径。G 目标路径必须不 detach；D fake 目标必须 detach。不能把三列都切断，也不能把 `detach` 画成图像变换。

真实图从 `[0,1]` ToTensor 值通过 `(features−0.5)*2` 归一化到 `[-1,1]`。源码先 `.view(-1,IMG_SIZE)` 得到 `[B,784]`，到 D 调用时再 View 回 `[B,1,28,28]`；图保留调用方的这两次变形，不把 Flatten784 当作 critic 第一层输入。

Python 先执行 Generator 目标的 backward 与 `optim_gener.step()`，再执行五次 critic 更新。D fake 调用复用更新 G 前已经计算的 `generated_features`，没有在 critic 循环里重新采样 z 或调用 G。数据依赖图不以左右顺序代替这个更新时间顺序；原始调用方范围证据保留在 `__module__` 的全源码片段和 notebook cell 映射中。

## WGAN 损失与裁剪在图外

`wasserstein_loss(y_true,y_pred)=mean(y_true*y_pred)`，源码 valid=−1、fake=+1。因此 G 目标为 `−mean(D(fake))`；critic 的 `discr_loss=0.5*(real_loss+fake_loss)` 为 `0.5*(−mean(D(real))+mean(D(fake)))`。图中的 raw scores 是这些损失的输入；loss、反向传播和优化步骤属于另一张训练图的范围。

两优化器为 RMSprop，学习率 `5e−5`。每次 critic step 后遍历 **全部 `model.discriminator.parameters()`** 执行 `clamp_(−0.01,0.01)`，包括 BN 的 affine 参数，不只卷积权重；running mean/variance 是 buffers，不在这个 parameters 循环里。没有 gradient penalty，因此不能标为 WGAN-GP。

## 三种粒度与程序化排布

`graph` 根框是有类型的 DAG 容器，`ranks` 从底到上配置：外部 noise/real → Generator/real preparation → 三个 D 调用目标路径。该容器不生成假公共输入、tuple 收集或求和；每条依赖来自 `extra_edges`。`align_x` 将 noise 对齐 G，将 real 对齐 real preparation/real D。显式 out→in 端口与预留 rank 间距使箭头提前转弯，并保持可见末段与边框间隔。

各 Sequential 仍用 `chain.items`，内部全部自底向上。三个目标路径并列表示两种来源和三个调用位置的数据依赖，不声称 Python 同步执行。概览折叠两个网络与三个调用路径；模块图展开 G 阶段与 caller View/detach；详细图展开 G projection、upsample1/4 和 G 目标 D 的 Conv/BN/LeakyReLU1、Flatten/Linear/raw return。重复的 G middle stages 和 D stage2/3 代表性折叠；fake/real 的两个 D 调用保持单独身份并折叠，不删参数、不改共享关系。

字体和颜色沿用 Transformer 原型：深色轮廓、浅粉 G、浅蓝 D/Conv、紫 Linear/输出、黄 BN、灰 LeakyReLU/detach、绿 noise/Tanh。配色区分视觉角色；G 的不同 stage 各有独立参数，而三个 D 调用中相同 `discriminator.*` 身份表示真实共享。

`validate_ir` 检查两入口范围、noise 区间、shape-only targets、每个 Sequential index 和卷积尺寸、三次 D 的共享身份、无 Sigmoid、global model 接收者以及 fake-only detach。错误负例给 critic 加 Sigmoid 会触发拒绝。几何验证另外检查端口、正交路线、至少18px末段、避框/避节点及不同张量不共用路线；通过静态核验不代表训练数值或旧环境兼容性验证完成。
