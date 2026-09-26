# 扩展模型家族图例、箭头与源码追溯

本文档覆盖 Scene Visual Lab 新增的 30 类结构家族。原有 Attention、FFN、Add & Norm、Convolution、Tensor Transform、Embedding、LSTM、Sparse MoE 和 Pooling 九类仍由 [`SOURCE_TRACEABILITY.md`](./SOURCE_TRACEABILITY.md) 追溯。

## 约定与边界

- 图例实现位于 [`catalog-details.ts`](../src/catalog-details.ts)，家族名称、别名和必须检查的差异轴位于 [`model-family-catalog.ts`](../src/model-family-catalog.ts)。
- `aliases` 只是检索入口，不表示同一家族下每个名称具有完全相同的执行图。正式 Studio 应先读取真实 IR、框架类型和源码证据，再根据 `differenceAxes` 选择精确视图。
- `flow()` 画带箭头的数据流，`wire()` 画无箭头的复制/分叉线。线性模板的公共箭头由 `pipeline()`（116-133 行）生成；分支汇聚模板由 `splitMerge()`（136-151 行）生成。
- 本文的“固定源码”是本目录内可校验的上游快照。“网页/论文”用于核对公式、可见标注和结构图，不替代固定源码。
- 优化器、学习率、损失、学习范式和运行时不是稳定的执行拓扑，保存在 `NON_ARCHITECTURE_CONCEPTS`，不伪装成父模块。

## 已执行的网络与视觉核对

核对日期为 2026-09-26。以下页面同时检查了正文和页面中的结构图或可见标注：

| 对象 | 可见结构核对 | 采用的原型语义 |
|---|---|---|
| 决策树 | [scikit-learn Decision Trees](https://scikit-learn.org/stable/modules/tree.html) 的 Iris 树图；节点显示阈值、左右分支和叶值 | `feature j <= t?` 分叉，叶节点统一到预测出口 |
| ResNet | [D2L Residual Blocks](https://d2l.ai/chapter_convolutional-modern/resnet.html#residual-blocks) 图 8.6.2；恒等线绕过权重层并在 `+` 汇合 | 变换支路与 identity/projection shortcut 相加 |
| U-Net | [U-Net 官方页](https://lmb.informatik.uni-freiburg.de/people/ronneber/u-net/)；蓝色编码/解码特征图、白色 copied feature maps、横向 skip | 对称 encoder/bottleneck/decoder 与同尺度 copy/crop/concat |
| ViT | [Google Research ViT](https://research.google/blog/transformers-for-image-recognition-at-scale/)；图像被切成 patch 序列并加入位置表示 | `image -> patchify -> embedding -> pos/CLS -> Transformer -> head` |
| Mamba | [state-spaces/mamba](https://github.com/state-spaces/mamba) 的 Selective State Space Model 图；`x_t` 生成 `B_t`、`C_t`、`Delta_t` 并更新状态 | local Conv1d、selective scan 与 gate 的乘法汇合 |
| CLIP | [openai/CLIP](https://github.com/openai/CLIP) 的 Approach 图；Text Encoder 与 Image Encoder 汇入 `I_i dot T_j` 矩阵 | 双塔编码后计算归一化相似度矩阵 |
| GNN | [PyG Creating Message Passing Networks](https://pytorch-geometric.readthedocs.io/en/latest/tutorial/create_gnn.html) 的公式与 API；`message -> aggregate -> update` | 邻居消息经 `sum/mean/max/attention` 聚合，再与中心状态更新 |
| DQN | [Stable-Baselines3 DQN](https://stable-baselines3.readthedocs.io/en/v2.7.0/modules/dqn.html)；文档明确 replay buffer、target network、epsilon-greedy | 在线 Q 网络选动作，环境 transition 进入 replay，目标网络构造 TD target |
| LoRA | [Hugging Face PEFT LoRA](https://huggingface.co/docs/peft/main/en/conceptual_guides/lora) 的训练/合并图；冻结 `W` 与低秩 `A/B` 支路相加 | `Wx + alpha BAx`，训练后可合并权重 |
| Autoencoder | [TensorFlow Intro to Autoencoders](https://www.tensorflow.org/tutorials/generative/autoencoder?hl=en) 的 basic、denoising 与 anomaly-detection 示例；正文明确先压缩到低维 latent representation，再解码回输入空间 | `x -> Encoder -> z -> Decoder -> x_hat`，变体差异留给噪声、卷积或离散瓶颈 |

## 1. 传统机器学习

### `linear-model`

- 图例：`X`、`Xw + b`、`link`、`y_hat`，实现见 `catalog-details.ts` 155-161 行。
- 箭头：父入口 -> `X` -> 线性得分 -> identity/sigmoid/softmax link -> `y_hat` -> 父出口。
- 固定源码：[`linear_model_base.py`](./upstream-code/scikit-learn-1.7.2/linear_model_base.py#L274) 的 `_decision_function()` 执行 `X @ coef_ + intercept_`，284 行以后把得分送入预测路径；PyTorch [`linear.py`](./upstream-code/pytorch-v2.7.1/linear.py#L124) 对应神经网络中的仿射层。
- 资料与边界：[scikit-learn Linear Models](https://scikit-learn.org/1.7/modules/linear_model.html)。回归、GLM、朴素贝叶斯、LDA/QDA 和 CRF 只共享“从输入得到决策分数”这一抽象；概率假设、link、结构化输出必须由差异轴再区分。

### `kernel-machine`

- 图例：`x`、`phi(x)`、`sum alpha_i K(x_i,x)`、`margin`，实现见 164-170 行。
- 箭头：父入口 -> 输入 -> 显式/隐式核映射 -> 支持向量加权和 -> 分类符号或回归值 -> 父出口。
- 固定源码：[`svm_classes.py`](./upstream-code/scikit-learn-1.7.2/svm_classes.py#L614) 的 `SVC` 与 1771 行 `predict()`；固定文件保留 kernel、support vector 和 decision function 的参数入口。
- 资料与边界：[scikit-learn SVM](https://scikit-learn.org/1.7/modules/svm.html)。KNN/KDE/LOF 使用邻居聚合而非支持向量，目录别名只提供检索，正式视图必须切换到邻域变体。

### `decision-tree`

- 图例：输入 `x`、阈值节点 `feature j <= t?`、`left child`、`right child`、`leaf value`，实现见 173-189 行。
- 箭头：`x` -> 阈值节点；true/false 各走一条子路径；每个样本实际只进入一个叶节点；图中两支汇入父出口仅表示统一 API 返回值。
- 固定源码：[`tree_classes.py`](./upstream-code/scikit-learn-1.7.2/tree_classes.py#L506) 的 `predict()` 与 704/1111 行分类树、回归树类型。
- 资料与边界：[scikit-learn Decision Trees](https://scikit-learn.org/1.7/modules/tree.html) 给出 `x_j <= t_m` 的左右集合定义。Isolation Forest 的叶值是隔离路径统计，不应解释为普通类别概率。

### `ensemble`

- 图例：三个 `Tree / learner` 分支与 `Vote / sum` 汇聚，实现在 192-198 行。
- 箭头：公共输入分派给多个 learner；各输出流向 Vote/sum；汇聚结果连接父出口。
- 固定源码：[`ensemble_forest.py`](./upstream-code/scikit-learn-1.7.2/ensemble_forest.py#L150) 的并行建树，723 行 `_accumulate_prediction()` 与 882/921/1044 行预测汇聚。
- 资料与边界：[scikit-learn Ensemble Methods](https://scikit-learn.org/1.7/modules/ensemble.html)。当前图准确表示 bagging/voting 的共同汇聚外形；boosting 是按残差串行拟合，不能把三支并行箭头当成其精确训练图。

### `clustering`

- 图例：`samples`、`assign`、`centroids`、`update`、`clusters` 和无箭头 `iterate` 回路，实现在 200-211 行。
- 箭头：样本 -> 最近中心分配 -> 当前质心 -> 均值更新 -> 聚类结果；上方回路表示分配/更新反复迭代。
- 固定源码：[`cluster_kmeans.py`](./upstream-code/scikit-learn-1.7.2/cluster_kmeans.py#L624) 的 Lloyd 循环，755 行 labels/inertia，1066 行预测分配。
- 资料与边界：[scikit-learn K-Means](https://scikit-learn.org/1.7/modules/clustering.html#k-means)。DBSCAN、层次聚类、谱聚类和 GMM 不使用同一更新回路，真实类型必须从 IR 选择密度、树或概率变体。

## 2. 表示与连接结构

### `decomposition`

- 图例：`X`、`center / scale`、`basis V/W`、`project XV or WH`、低维 `Z`，实现见 214-221 行。
- 箭头：输入矩阵 -> 预处理 -> 学得基 -> 投影/重构系数 -> 低维表示 -> 父出口。
- 固定源码：[`decomposition_pca.py`](./upstream-code/scikit-learn-1.7.2/decomposition_pca.py#L113) 的 `PCA` 与 444 行 `fit_transform()`。
- 资料与边界：[scikit-learn Decomposition](https://scikit-learn.org/1.7/modules/decomposition.html)。PCA/SVD、NMF、ICA、字典学习和流形方法的基约束及是否支持外样本 transform 不同。

### `mlp`

- 图例：`x`、上投影 `Linear`、`phi / gate`、下投影 `Linear`、`y`，实现见 224-231 行。
- 箭头：父入口 -> 输入 -> hidden expansion -> activation/gate -> contraction -> 输出 -> 父出口。
- 固定源码：PyTorch [`linear.py`](./upstream-code/pytorch-v2.7.1/linear.py#L124) 和 [`activation.py`](./upstream-code/pytorch-v2.7.1/activation.py)；原有 FFN 的精确两层映射另见 `SOURCE_TRACEABILITY.md`。
- 资料与边界：[D2L Multilayer Perceptrons](https://d2l.ai/chapter_multilayer-perceptrons/mlp.html)。GLU/GEGLU/SwiGLU 需要并行门控乘法，当前圆形 gate 是家族级压缩表达。

### `normalization`

- 图例：输入 `x`、`statistics`、`identity x`、`-/divide`、可选仿射 `gamma * x_hat + beta`，实现见 234-249 行。
- 箭头：输入分为统计支路和原值支路；两者在标准化算子汇合；随后执行可选 affine 并离开父模块。
- 固定源码：PyTorch [`normalization.py`](./upstream-code/pytorch-v2.7.1/normalization.py#L94) 的 `LayerNorm` 与 216 行 `forward()`；同文件还包含 GroupNorm/RMSNorm 等实现。
- 资料与边界：[PyTorch normalization layers](https://pytorch.org/docs/2.7/nn.html#normalization-layers)。Batch/Layer/Group/Instance/RMSNorm 的统计轴、均值消除和训练/推理状态不同。

### `residual-block`

- 图例：`x`、变换支路 `Conv / Linear -> Norm + phi`、恒等/投影捷径、`+`、可选输出激活，实现见 252-264 行。
- 箭头：输入一分为二；上支执行 `F(x)`，下支复制或投影 `x`；两支在 `+` 汇合后输出。
- 固定源码：[`torchvision resnet.py`](./upstream-code/torchvision-v0.22.1/resnet.py#L89) 的 `BasicBlock.forward()` 和 143 行 `Bottleneck.forward()`；源码在相加前按需执行 downsample。
- 资料与边界：[D2L ResNet](https://d2l.ai/chapter_convolutional-modern/resnet.html#residual-blocks)。pre-activation、post-activation、basic/bottleneck 和 grouped convolution 必须按具体 block 区分。

### `dense-connection`

- 图例：`x0`、`H1`、`H2`、`H3` 与 `[x0, x1, ...] channel concat`，实现见 267-283 行。
- 箭头：主链逐层前进；早期特征另以复制线直达后续层输入；最后特征离开父模块。
- 固定源码：PyTorch [`conv.py`](./upstream-code/pytorch-v2.7.1/conv.py#L553) 提供卷积算子；拼接语义由原型 276-279 行直接定义。未把某一 DenseNet 实现复制进产品。
- 资料与边界：[D2L DenseNet](https://d2l.ai/chapter_convolutional-modern/densenet.html)。DenseNet 是全历史 concat，CSP/FPN 只复用部分通道或跨尺度特征。

## 3. 视觉与门控序列

### `inception`

- 图例：`1x1 Conv`、`1x1 -> 3x3 Conv`、`1x1 -> 5x5 Conv`、`3x3 Pool -> 1x1`、`Concat`，实现见 286-293 行。
- 箭头：共同输入分到四条尺度支路；四个输出流入 channel concat；concat 连接父出口。
- 固定源码：[`googlenet.py`](./upstream-code/torchvision-v0.22.1/googlenet.py#L184) 的 `Inception`，226-228 行收集各 branch 并 `torch.cat(outputs, 1)`。
- 资料与边界：[D2L GoogLeNet](https://d2l.ai/chapter_convolutional-modern/googlenet.html)。Inception-ResNet 还需要 residual merge；MaxViT/CoAtNet 是卷积-注意力混合，不应解释成原始四支 Inception。

### `depthwise-convolution`

- 图例：feature maps、`DW kxk`、`BN + phi`、`PW 1x1`、output，实现见 295-302 行。
- 箭头：输入通道 -> 逐通道空间滤波 -> 归一化/激活 -> 1x1 通道混合 -> 输出。
- 固定源码：[`mobilenetv2.py`](./upstream-code/torchvision-v0.22.1/mobilenetv2.py#L19) 的 `InvertedResidual` 与 60 行 forward；PyTorch [`conv.py`](./upstream-code/pytorch-v2.7.1/conv.py#L378) 的 `groups` 参数提供 depthwise/grouped 语义。
- 资料与边界：[torchvision MobileNetV2](https://pytorch.org/vision/0.22/models/mobilenetv2.html)。MobileNetV2/V3 还含 expansion、残差、SE 或不同激活。

### `unet`

- 图例：`Enc 1..3`、bottleneck、`Dec 1..3`、三条同尺度 skip，实现见 305-329 行。
- 箭头：父入口沿 encoder 左到右进入 bottleneck，再沿 decoder 到父出口；encoder 各尺度用无箭头复制线连接镜像 decoder。
- 固定源码：Diffusers [`unet_2d_condition.py`](./upstream-code/diffusers-v0.35.1/unet_2d_condition.py#L1207) 收集 down-block residual samples，1245 行执行 mid block，1268-1277 行把对应 residual 送入 up blocks。
- 资料与边界：[U-Net 官方结构图](https://lmb.informatik.uni-freiburg.de/people/ronneber/u-net/)。UNet++、DeepLab、Mask2Former 和 SAM 的嵌套 skip、context、query 或 prompt 结构不同，当前父模块只表示 encoder-decoder 家族骨架。

### `vision-transformer`

- 图例：image、patchify、Linear patch embedding、`+ pos / CLS`、`Transformer xL`、head，实现见 332-340 行。
- 箭头：图像 -> patch 网格/序列 -> 线性嵌入 -> 位置与 class token -> 编码器堆栈 -> 分类/池化头。
- 固定源码：[`vision_transformer.py`](./upstream-code/torchvision-v0.22.1/vision_transformer.py#L277) 的 patch projection，289-303 行的 class token、encoder 与 head。
- 资料与边界：[Google Research ViT](https://research.google/blog/transformers-for-image-recognition-at-scale/)。Swin/PVT/MViT 使用层级或窗口 token；DETR 使用 object queries，必须从差异轴选择不同视图。

### `gru`

- 图例：`x_t`、`h_{t-1}`、update gate `z_t`、reset gate `r_t`、乘法、候选 `h_tilde`、mix、`h_t`，实现见 343-359 行。
- 箭头：输入和旧状态共同生成 gates；`r_t` 调制旧状态参与候选；候选和 `z_t` 与旧状态混合得到新状态并接父出口。
- 固定源码：PyTorch [`rnn.py`](./upstream-code/pytorch-v2.7.1/rnn.py#L1162) 的 `GRU`、1720 行 `GRUCell` 和 1793 行 forward；类文档内保留 gate 方程。
- 资料与边界：[PyTorch GRU](https://pytorch.org/docs/2.7/generated/torch.nn.GRU.html)。SRU/QRNN/IndRNN 的并行性或门方程不同，仅能共享“门控状态更新”父类。

## 4. 序列与潜变量

### `bidirectional-recurrent`

- 图例：正向 `t=1..T`、反向 `t=T..1` 和 `Concat / sum`，实现见 362-366 行。
- 箭头：共同序列输入分到两个时间方向；每个位置的两个状态在合并算子汇合；结果连接父出口。
- 固定源码：PyTorch [`rnn.py`](./upstream-code/pytorch-v2.7.1/rnn.py#L1162) 的 RNN/GRU `bidirectional` 参数与返回形状；LSTM 对应 795 行以后。
- 资料与边界：[PyTorch RNN](https://pytorch.org/docs/2.7/generated/torch.nn.RNN.html)。wav2vec/HuBERT 等 Transformer encoder 不是双向 RNN，别名只表示双向上下文检索入口。

### `seq2seq`

- 图例：source tokens、Encoder states、Attention context、Decoder、Softmax、target，实现见 369-377 行。
- 箭头：源序列 -> encoder states -> attention context -> 条件 decoder -> next-token distribution -> target。
- 固定源码：[`the_annotated_transformer.py`](./upstream-code/annotated-transformer-debc9fd/the_annotated_transformer.py) 的 encoder-decoder、cross-attention 和 generator；原有 Attention 的逐箭头追溯见 `SOURCE_TRACEABILITY.md`。
- 资料与边界：[D2L Encoder-Decoder](https://d2l.ai/chapter_recurrent-modern/encoder-decoder.html)。CTC、并行 TTS、beam search 和 teacher forcing 改变损失或解码过程，不都具有相同的 attention 箭头。

### `state-space`

- 图例：输入 `x`、local `Conv1d + SiLU`、gate `z`、`Selective SSM`、乘法、out projection，实现见 380-396 行。
- 箭头：输入拆成 local/SSM 主支和 gate 支；主支生成输入依赖的 `Delta/B/C` 并 scan；两支逐元素相乘后投影到父出口。
- 固定源码：[`mamba_simple.py`](./upstream-code/mamba-2.2.6/mamba_simple.py#L119) 的 forward，172 行 causal Conv1d，182 行参数投影，189 行 selective scan，205 行输出投影；208-252 行是单步递推。
- 资料与边界：[Mamba 官方仓库](https://github.com/state-spaces/mamba)。S4、RWKV、RetNet、Hyena 和 Neural ODE 只共享长程状态/卷积目标，不能套用相同 `Delta/B/C` 细节。

### `autoencoder`

- 图例：输入 `x`、Encoder、瓶颈 `z`、Decoder、重建 `x_hat`，实现见 399-406 行。
- 箭头：输入 -> 压缩编码 -> 潜表示 -> 扩张解码 -> 重建 -> 父出口。
- 固定源码：编码器/解码器可由本地 PyTorch `linear.py`、`conv.py` 和 activation 模块组合；本图的明确步骤由 `catalog-details.ts` 399-406 行保存。
- 资料与边界：[TensorFlow Intro to Autoencoders](https://www.tensorflow.org/tutorials/generative/autoencoder?hl=en) 展示 basic、denoising 与 anomaly-detection 三类实例，并明确 encoder 将输入压缩为低维 latent representation、decoder 再重建输入。VQ-VAE 还需 codebook/quantize，Masked AE 还需 mask/restore token，不能把圆形 `z` 当作同一种瓶颈。

### `variational-autoencoder`

- 图例：`x`、`q_phi(z|x)`、`mu`、`log sigma^2`、噪声 `epsilon ~ N(0,I)`、`mu + sigma epsilon`、`p_theta(x|z)`、`x_hat`，实现见 409-424 行。
- 箭头：encoder 输出分到均值和方差；二者与随机噪声汇入重参数节点；样本 `z` 进入 decoder 并得到重建。
- 固定源码：展示代码固定在 `catalog-details.ts` 409-424 行；通用张量、线性和激活算子来自本地 PyTorch 快照。没有用任意单一 VAE 实现冒充 beta-VAE/VQ-VAE/VGAE。
- 资料与边界：[Auto-Encoding Variational Bayes](https://arxiv.org/abs/1312.6114)。先验/后验族、KL 权重、条件输入和 graph decoder 必须按模型证据展开。

## 5. 生成、图与时间序列

### `gan`

- 图例：latent `z`、Generator、fake sample、real sample、共享 Discriminator、real/fake 输出，实现见 427-440 行。
- 箭头：`z -> G -> fake`；fake 与 real 两支都进入同一个 `D`；判别结果连接父出口。训练时 `D` 的梯度也反传到 `G`，图中不另画优化器箭头。
- 固定源码：生成器/判别器使用本地 PyTorch conv/linear/activation 算子；结构展示固定在 `catalog-details.ts` 427-440 行。
- 资料与边界：[D2L GAN](https://d2l.ai/chapter_generative-adversarial-networks/gan.html) 与 [Generative Adversarial Nets](https://arxiv.org/abs/1406.2661)。WGAN、CycleGAN、StyleGAN 和条件 GAN 会改变损失、生成器输入或判别器数量。

### `diffusion`

- 图例：clean `x0`、加噪 `+ epsilon`、`x_t`、denoiser `epsilon_theta(x_t,t,c)`、scheduler、`x_{t-1}`，实现见 443-451 行。
- 箭头：训练正向从 `x0` 加噪得到 `x_t`；去噪网络预测噪声/速度/样本；scheduler 合成前一时刻并输出。生成时该反向步重复到 `x0`。
- 固定源码：Diffusers [`scheduling_ddpm.py`](./upstream-code/diffusers-v0.35.1/scheduling_ddpm.py#L398) 的 `step()`、474/491/499 行前一状态和 501 行 `add_noise()`；[`unet_2d_condition.py`](./upstream-code/diffusers-v0.35.1/unet_2d_condition.py#L1039) 是条件 denoiser。
- 资料与边界：[DDPM](https://arxiv.org/abs/2006.11239) 和 [Diffusers DDPM pipeline](https://huggingface.co/docs/diffusers/api/pipelines/ddpm)。LDM 使用 latent，DiT 替换 U-Net，flow matching/consistency model 的训练向量场不同。

### `normalizing-flow`

- 图例：data `x`、可逆 `f1`、`f2`、`fK`、base sample `z`、`log p(x)`，实现见 454-462 行。
- 箭头：数据沿可逆变换到 base distribution；双向箭头表示采样可反向执行；log density 由 base density 与各步 log-determinant 相加。
- 固定源码：图形和箭头由 `catalog-details.ts` 454-462 行固定；没有把某个 flow 库作为运行依赖。
- 资料与边界：[Real NVP](https://arxiv.org/abs/1605.08803)。coupling、autoregressive 和 continuous flow 的逆向成本与 Jacobian 计算不同。

### `graph-message-passing`

- 图例：邻居 `u1/u2`、中心 `v`、`message phi`、self state、聚合 `sum`、`update gamma`、更新节点 `v'`，实现见 465-479 行。
- 箭头：每个邻居经 message function 进入聚合；中心状态绕过聚合并与聚合消息共同进入 update；新状态连接父出口。
- 固定源码：PyG [`message_passing.py`](./upstream-code/pytorch-geometric-2.6.1/message_passing.py#L421) 的 `propagate()`，565/577/609 行 `message/aggregate/update`；[`gcn_conv.py`](./upstream-code/pytorch-geometric-2.6.1/gcn_conv.py#L227) 的 GCN forward 和 270 行 message。
- 资料与边界：[PyG Message Passing](https://pytorch-geometric.readthedocs.io/en/latest/tutorial/create_gnn.html)。GCN/SAGE/GAT/GIN 与异构图分别改变消息、聚合权重和边类型参数。

### `time-series-forecast`

- 图例：Trend/level、Seasonal/residual、Covariates 三支和 `Forecast sum`，实现见 482-487 行。
- 箭头：共同历史输入分到趋势、季节/残差和协变量支路；各分量在 forecast 汇聚后输出。
- 固定源码：此图是家族级分解契约，直接固定在 `catalog-details.ts` 482-487 行；未保存单一库实现，因为 ARIMA/ETS/Prophet 与 PatchTST/TimesNet 的真实执行图不一致。
- 资料与边界：[Forecasting: Principles and Practice](https://otexts.com/fpp3/components.html)。只有显式分解模型能把三支理解为可观测成分；深度模型可能只在隐空间学习这些依赖。

## 6. 多模态、强化学习与适配

### `dual-encoder`

- 图例：Image Encoder、Text Encoder 和 `v dot t^T / tau` 相似度汇聚，实现在 490-495 行。
- 箭头：图像与文本分别进入独立编码器；两个归一化 embedding 共同进入批内相似度矩阵；矩阵连接父出口。
- 固定源码：OpenAI CLIP [`model.py`](./upstream-code/openai-clip-a1d0717/model.py#L340) 的 `encode_image/encode_text`，358-372 行归一化、temperature scale 和双向 logits。
- 资料与边界：[openai/CLIP Approach](https://github.com/openai/CLIP#approach)。ColBERT/SuperGlue 等 token-level interaction 不是纯 late interaction，必须按差异轴替换汇聚节点。

### `dqn`

- 图例：state、online `Q_theta(s,.)`、`argmax / epsilon`、Environment、transition `r,s'`、`Replay + target`，实现见 497-505 行。
- 箭头：状态经在线 Q 网络选动作；动作进入环境得到 transition；transition 存入 replay；采样 transition 与 target network 构造 TD 更新。父出口表示训练后的控制结果，不是 replay 的直接张量输出。
- 固定源码：SB3 [`dqn.py`](./upstream-code/stable-baselines3-v2.7.0/dqn.py#L171) 的 target 更新，187-217 行 replay sampling、target/current Q 与 loss，233 行 epsilon-greedy predict。
- 资料与边界：[Stable-Baselines3 DQN](https://stable-baselines3.readthedocs.io/en/v2.7.0/modules/dqn.html)。表格 Q-learning、SARSA、distributional/dueling/recurrent DQN 需要不同 head 或 target 箭头。

### `actor-critic`

- 图例：state、Actor、Critic、Environment、Advantage、Policy update，实现见 508-522 行。
- 箭头：state 分到 actor 与 critic；actor action 驱动环境；环境 returns 与 critic value 汇入 advantage；advantage 进入 policy update 并离开父模块。
- 固定源码：SB3 [`ppo.py`](./upstream-code/stable-baselines3-v2.7.0/ppo.py#L184) 的训练循环，216-227 行 advantage 与 clipped policy loss，234-256 行 value/entropy/总损失。
- 资料与边界：[Spinning Up PPO](https://spinningup.openai.com/en/latest/algorithms/ppo.html) 与 [SB3 PPO](https://stable-baselines3.readthedocs.io/en/v2.7.0/modules/ppo.html)。SAC/DDPG 加入 Q critics 与 replay；Dreamer/MuZero 加 world model；DPO/BC/QMIX 不是同一个 actor-critic 执行图，仅作检索入口。

### `distillation`

- 图例：冻结 Teacher soft logits、可训练 Student logits、可选 hard labels、`KL + CE`，实现见 525-530 行。
- 箭头：同一输入进入 teacher/student；teacher soft target 与 student prediction 进入 KL；labels 与 student prediction 进入 CE；两项汇聚为训练目标。
- 固定源码：teacher/student 的 logits 由本地 PyTorch 模块产生；具体图形与箭头固定在 `catalog-details.ts` 525-530 行。
- 资料与边界：[Distilling the Knowledge in a Neural Network](https://arxiv.org/abs/1503.02531)。feature distillation 还需中间层对齐，pseudo-label/self-training 不一定保留同时运行的 teacher 支路。

### `adapter-lora`

- 图例：输入 `x`、冻结 `W`、低秩 `A: d->r`、`B: r->d`、加法节点、`y = Wx + alpha BAx`，实现见 533-546 行。
- 箭头：输入同时进入 base projection 与 `A -> B` 支路；两支在 `+` 逐元素汇合；结果可直接输出或在推理前并入权重。
- 固定源码：PEFT [`lora_layer.py`](./upstream-code/peft-v0.17.1/lora_layer.py#L217) 创建 A/B，629 行 merge，710 行 delta weight，744-771 行 base result 加低秩增量。
- 资料与边界：[PEFT LoRA](https://huggingface.co/docs/peft/main/en/conceptual_guides/lora)。Adapter/Prefix/Prompt tuning 是串接瓶颈或可学习上下文；pruning/quantization 是参数变换，不应把 LoRA 的加法支路当成其精确图。

## 别名选择规则

`model-family-catalog.ts` 的 300 余个别名用于把用户名称路由到候选家族。正式接入时至少按以下顺序收窄：

1. 先确定对象是执行结构、训练算法、损失还是部署变换；非执行结构不生成父模块。
2. 再读取框架类、源码调用和 tensor shape，检查该家族的 `differenceAxes`。
3. 只有证据满足当前图中的全部关键节点和箭头时，才采用该展开图；否则生成更窄的专用变体。
4. 一个别名可命中多个候选，例如 `BiGRU` 同时命中 GRU cell 与 bidirectional wrapper；最终视图必须由 IR 层级决定。

## 完整性检查

- `catalog.test.ts` 验证 30 个家族都有名称、展开尺寸和可构建图元。
- 同一测试验证 30 个家族在六个目录场景中各出现一次，并检查代表性 SVG 标注。
- `vite.config.ts` 为每个父模块生成 `expanded-<kind>.svg/.json`，并为每个目录生成 `expanded-all.svg/.json`。
- `UPSTREAM_SOURCES.sha256` 与 `NEW_UPSTREAM_SOURCES.sha256` 分别校验原有和新增的固定源码及许可证。
