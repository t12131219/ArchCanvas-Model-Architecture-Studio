# ConvGAN：均匀噪声、两层判别器与 BCE raw logits

本例对应 `rasbt/deeplearning-models` 固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3` 的 `pytorch_ipynb/gan/gan-conv.ipynb`。采用 MNIST latent=100 的卷积 GAN 配置，静态解析源码与 AST，不执行 notebook、模型或训练。

[原 notebook](../sources/deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.ipynb) · [派生 Python](../sources/deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py) · [适配器](../adapters/convgan.py) · [共享绘图模板](../adapters/dcwgan.py) · [版本、哈希及 cell 映射](../source_manifest.json)

## 两个真实入口与三个调用位置

`GAN` 自身没有实现联合 `forward`。`generator_forward(z)` 使用 `self.generator`，返回 `[B,1,28,28]`；`discriminator_forward(img)` 实际使用全局 **`model.discriminator(img)`**，返回 `pred.view(-1)` 的 `[B]` raw logits。图没有修复这处 global receiver，也没有伪造 GAN tuple 返回。

整个根框是调用方训练数据 DAG：z→G，生成图分别进入 G 目标 D 和 D 目标 detached-fake D，真实图进入 D 目标 real D。三个 D 框表示三个调用位置，共用同一个判别器实例、参数和 BatchNorm buffers。此源码每 batch 各调用一次，共三次前向；与 DC-WGAN 每 batch 11 次不同。图左右并列表达来源依赖，Python 实际仍先更新 G，再执行 real/fake D 更新。

## 图例与源码结构

| 图中结构 | 源码身份和实际尺寸 | 对应原因 |
| --- | --- | --- |
| Caller Uniform noise | `zeros((targets.size(0),100)).uniform_(-1.0,1.0).to(device)`，`[B,100]` | 外部 `[−1,1)` 均匀分布，不是 Gaussian 或 DC-WGAN 的 `[0,1)` |
| G projection | `generator.0/.1/.2`：Linear100→3136 bias=False → BN1d3136 → LeakyReLU0.0001 | `[B,3136]`，真实三次模块调用 |
| Reshape1 | `generator.3`；`input.view(input.size(0),64,7,7)` | `[B,64,7,7]`，不是 64×4×4 |
| G upsample1 | `generator.4/.5/.6`：ConvTranspose64→32 k3/s2/p1 → BN → LeakyReLU | `[B,32,13,13]` |
| G upsample2 | `generator.7/.8/.9`：ConvTranspose32→16 k3/s2/p1 → BN → LeakyReLU | `[B,16,25,25]` |
| G upsample3 | `generator.10/.11/.12`：ConvTranspose16→8 k3/s1/p0 → BN → LeakyReLU | `[B,8,27,27]` |
| G upsample4 / Tanh | `generator.13/.14`：ConvTranspose8→1 k2/s1/p0 → Tanh | `[B,1,28,28]`，范围 `[-1,1]`，最后层不带 BN/LeakyReLU |
| D stage1 | `discriminator.0/.1/.2`：Conv1→8 k3/s2/p1 → BN8 → LeakyReLU | `[B,8,14,14]` |
| D stage2 | `discriminator.3/.4/.5`：Conv8→32 k3/s2/p1 → BN32 → LeakyReLU | `[B,32,7,7]`；只有两个 D Conv stage |
| D Flatten | `discriminator.6`；`input.view(input.size(0),-1)` | `[B,1568]`，7×7×32，不是 DC-WGAN 的512 |
| D Linear / view return | `discriminator.7` Linear1568→1 默认 bias=True；wrapper `pred.view(-1)` | `[B]` logits，末 Sigmoid 被注释 |

G 的四个 ConvTranspose 与两个 D Conv 均 bias=False，G Linear 也 bias=False；D Linear 保留默认 bias=True。全部 LeakyReLU 明确 slope=0.0001、inplace=True，不能改成默认0.01或普通 ReLU。各 BN 使用默认 affine=True、track_running_stats=True、eps=1e−5、momentum=0.1。

转置卷积 dilation=1/output_padding=0，按 `(n−1)s−2p+k` 推出 G 的 `7→13→25→27→28`。判别器 Conv2d 使用 floor 尺寸公式，得到 `28→14→7`。没有第三级 D Conv、池化、attention、Softmax、条件 Embedding 或实际 Dropout2d；Dropout 与 debug hooks 仅为注释/字符串。

## BCEWithLogits 的判别器没有 Sigmoid

源 `nn.Sigmoid()` 被注释掉，`discriminator_forward` 返回不受 `[0,1]` 约束的 raw logits。调用方使用 `F.binary_cross_entropy_with_logits`，其内部完成数值稳定的 Sigmoid/BCE 计算；不能因为任务是 GAN 就在网络里添加 Sigmoid，否则改变源码与损失输入语义。

valid=1、fake=0。G loss 对生成图 D score 使用 valid；D real/fake 分别使用1/0，`discr_loss=0.5*(real_loss+fake_loss)`。优化器都是 Adam、lr=1e−4，一次 D 更新/每 batch，没有 clipping 或 gradient penalty。损失、backward、优化器更新属于调用方训练操作，当前图保留 raw-score 数据路径并在 profile/docs 记录这些设置，不把它们伪装为网络层。

## 真实图片、size-only targets 与 detach

图片先经 ToTensor 为 `[0,1]`，调用方执行 `(features−0.5)*2` 归一化到 `[-1,1]`，再 `view(-1,IMG_SIZE)` 为 `[B,784]`。real D 调用前显式 View 回 `[B,1,28,28]`。图把 normalize/flatten/view 放在 caller 框；判别器从四维图像开始，其内部 Flatten 位于两个 Conv stage 之后。

targets 只用 `size(0)` 确定 B 和 valid/fake 向量长度，没有使用 MNIST 数字标签作为条件。图中 shape-only 虚线到 noise 的 `batch_shape` 端口，标签值不流进 G/D。图是一种无条件生成模型，即使训练数据含类别标签也不能补出 conditional GAN。

G 目标调用 `D(generated_features.view(...))`，没有 detach，损失梯度可经 D 回到 G。D fake 目标调用同一批 `generated_features.view(...).detach()`，保持图像值但阻止梯度返回 G。`detach` 节点明确位于 caller，不能放进 G 或 D Sequential，也不能把它理解成图像值变换。

源码先 `gener_loss.backward()`、`optim_gener.step()`，后进入 D 更新；fake D 复用 G 更新前已算出的 `generated_features`，没有重采样或再次 G forward。真实图片不经过 G。图保留三路独立端点、一个 G 输出的两路依赖和 fake-only detach，不用三列排布声称同时执行或模型返回三个张量。

当前图选择 `model.train()`，BN 使用当前 batch 统计并更新 running buffers；三个 D 调用复用同一组 BN 状态。最后单独的图片展示 cell 调用 `model.eval()` 后只运行 G，是另一范围，不能将其 eval BN 配置混入训练图。

## 相同图元与共享参数如何区分

生成器不同 stage 参数依次为 `generator.4/.7/.10/.13`，每个 kernel 在空间位置复用，但四层不共享参数。三个 D 调用中的 Conv/BN/Linear 节点各有不同调用节点 ID，却标注相同 `discriminator.0/.1/.3/.4/.7` 参数身份与 `instance_identity=model.discriminator`，这是跨调用真实共享。

`convgan.py` 复用 `dcwgan.py` 的 `_build/_validate` 绘图函数，来源引用仍全部绑定自己的 GAN 类与 `gan-conv.py`。共享模板不是共享训练权重，也不是导入上游模型。两种适配器必须保留不同噪声区间、D 深度/Flatten、loss 与更新设置。

## 三种粒度与 Transformer 风格布局

显式 `graph` 根容器的三个 bottom-to-top ranks 是输入、G/real preparation、三条 D 调用路径。它不生成默认 fork/tuple/reduction；所有依赖由带真实节点/端口的 `extra_edges` 指定。noise 和 G、real 和 real preparation/real D 用 `align_x` 对齐；阶段间留出至少两段转弯通道。内层 `chain` 按执行顺序保存，渲染时内部与整体都自底向上。

概览折叠 G、caller preparation 和三个目标路径；模块图展开 G 阶段与 caller View/detach；详细图展开 G projection、upsample1/4 和代表性 G 目标 D 的 stage1/Flatten/Linear/return。中间 G 同型 stage、D stage2 与另外两次 D 调用折叠；完整71个语义节点、参数、源映射与真实端口仍在 IR，没有删掉共享调用或用多个独立 D 替代。

字体与配色继承 Transformer：深边框、浅粉 G、浅蓝 D/Conv、紫色 Linear/return、黄色 BN、浅灰 LeakyReLU/detach、绿色 noise/Tanh。颜色表达角色，参数共享由稳定实例/参数字段表达。框尺寸与文字先测量，再计算纵向高度、列宽、列间距与路由；箭头终段预留、避免沿模块边框行走。

`validate_ir` 检查 Uniform[−1,1)、G 真正尺寸、两层 D/1568 Flatten、raw logits/global receiver、三调用一个实例、caller-only fake detach、无条件 targets 和 BCE/Adam 设置。错误负例取消 detach 的梯度阻断，会被拒绝。源码哈希/AST/cell 取证、语义检查与几何检查各自独立；当前未执行模型，不宣称数值等价或训练正确性已验证。
