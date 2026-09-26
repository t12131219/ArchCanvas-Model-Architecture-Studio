# Scene Visual Lab Reference Bundle

本目录把最小原型中的 39 类父模块内部图，连接到可复查的论文图示、官方文档和固定版本源码。它只用于设计追溯，不参与 Vite 构建，也不会被原型或正式 Studio 导入执行。

## 入口

- [`SOURCE_TRACEABILITY.md`](./SOURCE_TRACEABILITY.md)：逐图例、逐数据流说明语义、对应源码与简化边界。
- [`MODEL_FAMILY_TRACEABILITY.md`](./MODEL_FAMILY_TRACEABILITY.md)：新增 30 个模型家族的逐图例、逐箭头、固定源码、视觉核对与别名边界。
- [`UPSTREAM_SOURCES.sha256`](./UPSTREAM_SOURCES.sha256)：离线上游文件的 SHA-256，可用于确认文件未漂移。
- [`NEW_UPSTREAM_SOURCES.sha256`](./NEW_UPSTREAM_SOURCES.sha256)：传统 ML、视觉、扩散、GNN、Mamba、CLIP、RL 与 LoRA 新增快照的 SHA-256。
- [`upstream-code/`](./upstream-code/)：按固定 tag 或 commit 保存的原始上游源码。
- [`licenses/`](./licenses/)：与离线源码一同保存的原许可证。

## 固定版本

| 项目 | 固定 ref | 解析对象 | 本地内容 | 许可证 |
|---|---|---|---|---|
| PyTorch | `v2.7.1` | `e2d141dbde55c2a4370fac5165b0561b6af4798b` | `torch/nn/modules` 中与九类图例直接相关的 9 个模块 | BSD-3-Clause |
| Hugging Face Transformers | `v4.56.2` | `cd74917ffc3e8f84e4a886052c5ab32b7ac623cc`（annotated tag `04a6c04…` 解引用） | Switch Transformers router、专家与稀疏 MLP | Apache-2.0 |
| Harvard NLP Annotated Transformer | commit | `debc9fd747bb2123160a98046ad1c2d4da44a567` | 可运行的 Transformer 教学实现 | MIT |
| scikit-learn | `1.7.2` | release tag | 线性、SVM、树、森林、K-Means、PCA | BSD-3-Clause |
| torchvision | `v0.22.1` | release tag | ResNet、GoogLeNet、MobileNetV2、ViT | BSD-3-Clause |
| Hugging Face Diffusers | `v0.35.1` | release tag | 条件 U-Net 与 DDPM scheduler | Apache-2.0 |
| PyTorch Geometric | `2.6.1` | release tag | MessagePassing 与 GCNConv | MIT |
| state-spaces/mamba | `2.2.6` | release tag | Mamba block 与 selective scan 调用链 | Apache-2.0 |
| OpenAI CLIP | commit | `a1d0717` | 图像/文本双编码与相似度矩阵 | MIT |
| Stable-Baselines3 | `v2.7.0` | release tag | DQN 与 PPO 训练循环 | MIT |
| Hugging Face PEFT | `v0.17.1` | release tag | LoRA A/B、forward 与 merge | Apache-2.0 |

下载与核对日期：2026-09-26。所有远程 URL 均指向固定 tag 或 commit；网页解释链接不作为源码版本锁。

固定源码入口：

- PyTorch：[`v2.7.1/torch/nn/modules`](https://github.com/pytorch/pytorch/tree/v2.7.1/torch/nn/modules)；[许可证](https://github.com/pytorch/pytorch/blob/v2.7.1/LICENSE)。
- Transformers：[`v4.56.2/modeling_switch_transformers.py`](https://github.com/huggingface/transformers/blob/v4.56.2/src/transformers/models/switch_transformers/modeling_switch_transformers.py)；[许可证](https://github.com/huggingface/transformers/blob/v4.56.2/LICENSE)。
- Annotated Transformer：[`debc9fd/the_annotated_transformer.py`](https://github.com/harvardnlp/annotated-transformer/blob/debc9fd747bb2123160a98046ad1c2d4da44a567/the_annotated_transformer.py)；[许可证](https://github.com/harvardnlp/annotated-transformer/blob/debc9fd747bb2123160a98046ad1c2d4da44a567/LICENSE)。

## 网页与图像核对记录

### Attention / FFN / Add & Norm / Embedding

[The Annotated Transformer](https://nlp.seas.harvard.edu/annotated-transformer/) 的正文、公式、代码和配图已同时核对：

- Scaled Dot-Product Attention 图标出 `Q`、`K` 进入第一次 `MatMul`，之后依次经过 `Scale`、可选 `Mask`、`Softmax`，再与 `V` 进入第二次 `MatMul`。
- 公式明确为 `softmax(QK^T / sqrt(d_k))V`；多头公式明确为 `Concat(head_1, ..., head_h)W^O`。
- 页面代码展示 Q/K/V 线性投影、`view + transpose` 分头、注意力计算、`transpose + contiguous + view` 合并，以及最终输出线性层。
- FFN 页面是两个线性变换，中间使用激活；嵌入页面把 token embedding 与 positional encoding 相加并做 dropout。
- 页面文字给出 post-norm 公式 `LayerNorm(x + Sublayer(x))`，但该教学实现的 `SublayerConnection.forward` 实际使用 pre-norm 形式 `x + Dropout(Sublayer(LayerNorm(x)))`。追溯时分别记录，不能混为同一种执行顺序。

### LSTM

[Understanding LSTM Networks](https://colah.github.io/posts/2015-08-Understanding-LSTMs/#step-by-step-lstm-walk-through) 的逐步图已视觉核对：

- 黄色方框是 sigmoid/tanh 神经网络层，粉色圆圈是逐元素加法或乘法，分叉线表示复制，合并线表示 concat。
- cell state 沿上方直通；forget gate 控制 `f_t * c_{t-1}`，input gate 与候选状态形成 `i_t * g_t`，两者相加为 `c_t`，output gate 再控制 `o_t * tanh(c_t)` 得到 `h_t`。
- 原网页的图像资源包括 `LSTM3-chain.png`、`LSTM3-C-line.png`、`LSTM3-gate.png`、`LSTM3-focus-f.png`、`LSTM3-focus-i.png`、`LSTM3-focus-C.png` 与 `LSTM3-focus-o.png`。

### Mixture of Experts

[Mixture of Experts Explained](https://huggingface.co/blog/moe) 的文字、公式和 Switch Layer 图已核对：

- 页面把 sparse MoE 定义为替代 dense FFN 的专家集合，以及决定 token 去向的 gate/router。
- `y = sum_i G(x)_i E_i(x)` 对应原型的专家分支和 `Σ`；Noisy Top-k 的 `G(x) = Softmax(KeepTopK(H(x), k))` 对应 `Router -> Top-k`。
- 页面图片的可见标注包括 `Switch Layer`、`MoE Transformer Encoder` 与 `Switch Transformer Layer`。Switch Transformer 本身是 top-1；原型的 `k = 1 or 2` 是对更一般 sparse MoE 的概括。

## 使用边界

- 本目录证明“图例为何这样画、箭头代表哪一步”，不证明任意模型都采用完全相同的实现顺序。
- `module-details.ts` 是展示定义；真实模型源码与 IR 仍是正式 Studio 的语义权威。
- 上游文件保留原版权与许可证，不应直接复制进产品代码。迁移时应重新实现最小必要逻辑并保留来源说明。
- 新增家族图是可检索的结构模板，不是 300 余个别名都共享同一执行图的声明；采用前必须检查文档中的差异轴。
