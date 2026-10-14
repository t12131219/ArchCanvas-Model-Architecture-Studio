# DCGAN：两个入口及明确的调用方组合

本适配器对应固定 `rasbt/deeplearning-models` 的 `pytorch_ipynb/gan/dcgan-celeba.ipynb`。源码的 `DCGAN` 类定义了 `generator_forward(z)` 和 `discriminator_forward(img)`，**没有定义 `forward`**。当前图明确绘制 Notebook 调用方的组合路径：latent noise → 生成器入口 → fake image → 判别器入口 → score。不能把这个组合命名为 `DCGAN.forward`。

[原 Notebook](../sources/deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.ipynb) · [派生源码](../sources/deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py) · [适配器](../adapters/dcgan.py) · [来源与原 cell 映射](../source_manifest.json)

原 Notebook cell 9 给出配置，cell 16 给出训练图像准备，cell 20 定义类，cell 21 构造全局 `model`，cell 25 是训练 loop；cell 索引从 0 起。训练 loop 位于模块顶层，没有自己的函数 AST 符号，因此其配置与调用证据保存在整个固定源码和原 cell 映射中；不会虚构一个训练函数来附行号。类与两个入口方法有独立 AST 证据。

绘图只读文本、Notebook 和 AST，不运行 CelebA 数据处理、torchsummary、模型或优化器。

## 所选图的执行范围

图选择生成器训练段的 fake-image scoring 语义，代码中的相关语句是：

```python
fake_images = model.generator_forward(random_vec)
# discriminator update uses fake_images.detach() in an earlier separate call
# ... discriminator optimizer update ...
discr_pred_fake = model.discriminator_forward(fake_images).view(-1)
```

当前架构图展示两个方法的数据路径，**不是训练时间线**。源码在两次相关调用之间还执行了 discriminator 的 loss/backward/optimizer update，这些步骤不在当前结构图范围；因此图不表示它们在训练 loop 中无其他操作地相邻执行。它也不绘制 optimizer、标签、BCELoss 或反向传播。

所选 generator update 的 D 输入是 `fake_images`，没有 detach。图中的 fake image 框是两方法之间的结果/调用边界标签，不新增计算。判别器方法返回 `[B,1,1,1]`，调用方 `.view(-1)` 得到 `[B]` 是另外一步，未塞进方法边框。

## 全局 model 接收者的源码事实

判别器方法真实写为：

```python
def discriminator_forward(self, img):
    pred = model.discriminator(img)
    return pred
```

它调用的是**模块全局 `model`** 的 discriminator，不是 `self.discriminator`。当前 profile 明确采用 Notebook 正常调用方式：cell 21 的 `model=DCGAN()` 与 cell 25 接收方法调用的 global `model` 是同一个选定实例，因此参数身份可关联到该实例的 `discriminator`。

这不是通用保证。如果创建第二个实例调用其 `discriminator_forward`，而 global `model` 仍指向第一个实例，执行会读取第一个实例的 discriminator。图保留了全局接收者和假设，没有悄悄“修正”为 self。原源码未修改。

## 固定配置和形状

配置为 `LATENT_DIM=100`、`NUM_MAPS_GEN=64`、`NUM_MAPS_DIS=64`、`IMAGE_SIZE=(64,64,3)`。图像张量实际使用 NCHW `[B,3,64,64]`；`IMAGE_SIZE` 元组是 HWC 配置，并不是 PyTorch tensor layout。训练 batch 设置 128，图中 B 保留符号化。固定监视噪声 batch 64 属于不同的 generator-only 调用，不混入所选训练路径。

Generator 的五个转置卷积：

| Stage | 模块索引 | 参数 / 顺序 | 输出形状 |
| --- | --- | --- | --- |
| G1 | `generator.0/.1/.2` | ConvTranspose `100→512`, k4/s1/p0 → BN → ReLU | `[B,512,4,4]` |
| G2 | `generator.3/.4/.5` | ConvTranspose `512→256`, k4/s2/p1 → BN → ReLU | `[B,256,8,8]` |
| G3 | `generator.6/.7/.8` | ConvTranspose `256→128`, k4/s2/p1 → BN → ReLU | `[B,128,16,16]` |
| G4 | `generator.9/.10/.11` | ConvTranspose `128→64`, k4/s2/p1 → BN → ReLU | `[B,64,32,32]` |
| G5 | `generator.12/.13` | ConvTranspose `64→3`, k4/s2/p1 → Tanh | `[B,3,64,64]` |

所有 G 的卷积 `bias=False`；G 有四个 BatchNorm，没有在最后输出层后补 BN。ReLU 的 `inplace=True` 是源码参数。Tanh 输出 `[-1,1]`，与真实图像调用方 `Normalize(mean=.5,std=.5)` 的范围匹配。

Discriminator 的五个普通卷积：

| Stage | 模块索引 | 参数 / 顺序 | 输出形状 |
| --- | --- | --- | --- |
| D1 | `discriminator.0/.1` | Conv `3→64`, k4/s2/p1, **bias=True** → LeakyReLU(.2) | `[B,64,32,32]` |
| D2 | `discriminator.2/.3/.4` | Conv `64→128`, k4/s2/p1, bias=False → BN → LeakyReLU(.2) | `[B,128,16,16]` |
| D3 | `discriminator.5/.6/.7` | Conv `128→256`, k4/s2/p1, bias=False → BN → LeakyReLU(.2) | `[B,256,8,8]` |
| D4 | `discriminator.8/.9/.10` | Conv `256→512`, k4/s2/p1, bias=False → BN → LeakyReLU(.2) | `[B,512,4,4]` |
| D5 | `discriminator.11/.12` | Conv `512→1`, k4/s1/p0, **bias=True** → Sigmoid | `[B,1,1,1]` |

D 首尾卷积不显式给 bias 参数，按 API 默认是 True；中间三层是 False。D 只有三个 BN，首层和最后一层没有。D 的 Sigmoid 是源码 Sequential 内的真实算子，输出二元 real/fake score，不是分类 Softmax，也不是还需 BCELossWithLogits 的原始 logits。

所选路径处于 `model.train()`：BN 使用 batch statistics，而不是 eval running statistics。来源版本旧不代表可以随意把模式改为 eval；模式属于审阅 profile。

## 多入口、real scoring 和 detach 的关系

训练 loop 中存在三类调用语义：

1. **D 真实图像路径**：`discriminator_forward(real_images)`；独立接收数据集图像。
2. **D 假图像更新路径**：`generator_forward(random_vec)` 后将 `fake_images.detach()` 交给 D；detach 切断向 G 的反向梯度。
3. **G 更新的打分路径**：D 接收没有 detach 的 `fake_images`，从该 score 的训练损失向 G 传播梯度。

它们使用同一选定 global discriminator 参数，是不同调用，不是三张图像同时 Concat/Add。当前主图选第 3 类结构，真实图像路径和第 2 类 detach 不作为辅助输入混接到同一次 D 调用。普通方法调用本身也不会自动冻结 D 参数；图不作这样的训练声明。

监视时 `generator_forward(fixed_noise)`、`.detach().cpu()` 和 `make_grid` 又是另一种仅生成图像的路径。完整训练流程如需绘图，应采用明确时间/优化器/梯度边界的单独视图，而非在本图随意添加一条 real-image 箭头。

## 源码层次与三粒度排布

`generator` / `discriminator` 各自是真实 `nn.Sequential`。G1…G5、D1…D5 是对它们连续操作的逻辑 stage 分组，便于折叠，源码没有额外的 stage 属性。参数身份直接使用 Sequential 索引，避免画面抽象改变权重指向。

根 chain 表示**调用方组合**，不是模型内单一 forward。概览显示折叠的 Generator / fake-image boundary / Discriminator 两个入口，并标明 latent、G-to-D 范围与最终 D score；模块视图展开两条入口的五个 stage；详细视图进一步代表性展开两端 stage。中间同型 stage 可折叠，完整 IR 仍保留五个 G 卷积、五个 D 卷积、七个 BN 及激活。

主流程及各 Sequential 都从底向上读。G 外框采用浅粉 Decoder 视觉角色，D 外框采用浅蓝 Encoder 视觉角色，仅表达生成/判别方向，不把它们解释为 Transformer 的 Encoder/Decoder 结构。卷积蓝、BN 黄、最后概率绿色，深色边框与字号沿用 Transformer。`fill_width` 对齐主要容器，源码依赖决定顺序，绘图规则决定几何位置和间距。

“同一个 DCGAN 类”不等于 G/D 共享权重；G 与 D 是独立参数族。D 跨 real/fake 多次调用复用同一参数是调用实例事实，不是图例配色推断。

## 核验边界

图像绑定固定 Notebook 哈希、原 cell 映射和 AST 证据，静态 shape 由 kernel/stride/padding 推导。没有执行模型或证明数值等价。由于类没有 forward，不能直接把 `model(z)` 宣称为可运行的生成入口；正常调用应明确选择 `generator_forward` 或 `discriminator_forward`，并满足这份源码的 global receiver 假设。
