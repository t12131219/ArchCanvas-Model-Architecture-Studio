# VAE：从实际源码到三个粒度的架构图

本适配器对应 `rasbt/deeplearning-models` 的 `pytorch_ipynb/autoencoder/ae-var.ipynb`，使用固定提交的 notebook 与逐 cell 派生的 `.py` 副本取证。模型是 **MNIST 全连接 VAE**，不是卷积 VAE。入口为 `VariationalAutoencoder.forward(features)`；绘图读取 AST 和文本，不导入或执行 notebook。

[源码副本](../sources/deeplearning-models/pytorch_ipynb/autoencoder/ae-var.py) · [原 notebook](../sources/deeplearning-models/pytorch_ipynb/autoencoder/ae-var.ipynb) · [适配器](../adapters/vae.py) · [来源与 cell 映射](../source_manifest.json)

## 固定配置与真实返回值

源码设置 `num_features=784`、`num_hidden_1=500`、`num_latent=15`。`B` 是符号化批量维；训练设置的 `batch_size=128` 不是所有调用都必须固定的维度。MNIST `[B,1,28,28]` 在**调用方训练循环**通过 `features.view(-1,28*28)` 变为 `[B,784]`，不是 `forward` 内部的 Flatten 模块。

该模型返回四个张量：

```python
z_mean, z_log_var, encoded = self.encoder(features)
decoded = self.decoder(encoded)
return z_mean, z_log_var, encoded, decoded
```

因此图像顶部必须明确保留 `(mu, logvar, z, decoded)`，不能只画重建图片。前三项均为 `[B,15]`，最后一项为 `[B,784]`。图中的 tuple 收集不表示求和、拼接或同时执行。

## 图例与源码对应

| 图中结构 | 源码位置 / 参数身份 | 对应理由 |
| --- | --- | --- |
| Encoder 的 Linear `784→500` | `__init__.hidden_1`，`encoder` 的 `self.hidden_1(features)` | 真实可学习层；对应独立 `hidden_1` 权重 |
| Encoder 的 LeakyReLU | `encoder` 的 `F.leaky_relu(..., negative_slope=0.0001)` | 函数式算子，无独立参数；不能改成普通 ReLU |
| 并列 Mean / Log-variance heads | `z_mean`、`z_log_var` 两个 `Linear(500,15)` | 两者读取同一个隐藏张量，独立参数，结果语义不同；并列布局来自共同生产者 |
| 标准差分支 | `reparameterize` 的 `torch.exp(z_log_var/2.)` | `logvar` 是 log 方差；采样所需标准差是 `exp(logvar/2)`，不是 `exp(logvar)` |
| 内部 Gaussian sample | `reparameterize` 的 `torch.randn(...).to(device)` | 这是函数内新生成的随机张量，作为独立算术操作数进入乘法；不是调用方真实输入 |
| Add `mu + std*epsilon` | `reparameterize` 的 `z_mu + eps * ...` | 加法两个操作数必须保持独立；噪声不会通过 Mean head |
| Encoder tuple 返回 | `encoder` 的 `return z_mean, z_log_var, encoded` | Mean / Logvar 通过保留路线到达 tuple，z 是主采样路径结果 |
| Select encoded z | `forward` 的 tuple 解包及 `self.decoder(encoded)` | Decoder 仅接收采样结果；不接收 Mean/Logvar 的拼接 |
| Decoder | `linear_3` `15→500` → LeakyReLU → `linear_4` `500→784` → Sigmoid | 两个 Linear 各有独立权重，输出像素概率由真实 Sigmoid 产生 |
| Forward tuple 返回 | `forward` 的四字段 `return` | Mean、Logvar、z 越过 Decoder 保留到模型返回值，Decoder 不覆盖这些张量 |

`torch.randn` 在这份源码中没有 `self.training` 条件：**即使 eval，也仍然采样**。不能套用其他 VAE 实现的“推理阶段直接取 mu”。末端 Sigmoid 属于 `decoder`，训练损失不属于 `forward`。

## 依赖关系如何决定排布

整个图从下到上阅读，`chain.items` 按源码输入到输出排列，布局引擎计算高度后反向安排纵坐标。Encoder 和 Decoder 使用与 Transformer 一致的蓝 / 粉外围层级；Linear 使用紫色，Sigmoid 与随机源使用绿色，LeakyReLU 与指数运算使用浅灰，算术合并使用黄色。同色表示图例角色相同，**不表示共享参数**。

Mean / Logvar heads 使用 `parallel`：输入从同一 Encoder hidden 分叉，两列按各自最小宽高测量，先留出分叉总线和收集总线，再计算列间距。采样的 Mean 与 `std*epsilon` 也并列，但标记为 tuple 字段分发（`dispatch=True`），因为两个分支输入分别是 `z_mu` 和 `z_log_var`。它们的顶部 tuple 还必须经过显式 Add 才成为 z；布局引擎不会把并列自动理解为求和。

Mean/Logvar 的保留值是 `extra_edges`，终点分别为 `encoder_return` 和 `return` 的同名端口。z 的保留路线到达最终 `encoded` 端口。Gaussian sample 作为辅助计算节点位于侧方，进入乘法的 `epsilon` 端口。辅助路线不改变主链的执行顺序；共同的直角连线引擎进行避障、保持末段，并检查不沿模块边框行走。

三个视图共用同一 IR：概览折叠 `forward`；模块级展开 `forward`，展示 Encoder / Decoder 边界、z 的选择和四字段返回；详细级继续展开 Encoder、Decoder、两个独立 posterior heads 和采样操作数。折叠只改变显示，不删除参数身份、tuple 字段或取证关系。

## 与常见教材图的差异和绘图边界

常见示意图把 VAE 的最终结果简写为 reconstruction，这份代码实际返回四个张量。图中补齐了两处 tuple 返回和统计量旁路，也保留了两条独立 head。源码没有 Conv、BatchNorm、ConvTranspose、注意力，也没有 decoder 和 encoder 的权重绑定。

训练循环计算 `kl_divergence` 与 `binary_cross_entropy(decoded, features, reduction='sum')`，然后相加。它们位于 notebook 训练 cell，属于另一张训练 / 损失图的范围，**不能塞进模型 forward 作为伪节点**。随机生成示例直接调用 `model.decoder(rand_features)`，是另一种入口；当前图以完整重建 forward 为范围。

适配器将实际模块调用、函数式算子、tuple 保留关系写入语义 IR。配置常量和训练代码保存为来源副本；AST 行号通过 `source_manifest.json` 追溯到原 notebook cell。语义依然是经过源码审阅的显式适配器，不是任意 notebook 的自动结构识别。
