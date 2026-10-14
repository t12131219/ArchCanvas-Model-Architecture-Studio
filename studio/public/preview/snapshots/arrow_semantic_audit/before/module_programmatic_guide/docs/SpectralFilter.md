# SpectralFilter：保留真实 buffer 身份的谱域滤波模块

这是从 `GraphNet.forward` 选出的局部依赖图，**上游没有名为 SpectralFilter 的独立类**。选定边界为图像、V/W buffer 的读取与重排，到 `Y` 的重构。Y 后面的展平、全图 `fc`、Softmax 和优化器都属于模块外部。

上游为 [rasbt/deeplearning-models](https://github.com/rasbt/deeplearning-models)，固定提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3`。来源为 [gnn-basic-graph-spectral-1.ipynb](../sources/rasbt-modules/pytorch_ipynb/gnn/gnn-basic-graph-spectral-1.ipynb)，派生 [gnn-basic-graph-spectral-1.py](../sources/rasbt-modules/pytorch_ipynb/gnn/gnn-basic-graph-spectral-1.py) 保留代码单元与行号映射。适配器不执行上游 notebook、模型、NumPy 距离计算或 SciPy 特征分解。

## 模块真正计算什么

固定配置 `img_size=28, num_filters=2`，所以 `N=784, F=2`。特征分解保留 `K=20` 个 `which='SM'` 模式。主流程为：

```python
# B is obtained from x.size(0)
V_tensor   = self.V.expand(B, -1, -1)          # [B,784,20]
V_tensor_T = self.V.T.expand(B, -1, -1)        # [B,20,784]
X          = x.view(B, -1, 1)                 # [B,784,1]
W          = self.W_spectral.expand(B, -1, -1)# [B,784,2]
X_hat = V_tensor_T.bmm(X)                     # [B,20,1]
W_hat = V_tensor_T.bmm(W)                     # [B,20,2]
product = X_hat * W_hat                       # broadcast → [B,20,2]
Y = V_tensor.bmm(product)                    # [B,784,2]
```

上述变量 X/W/product 是解释性的名称；源码实际使用 `x_reshape`、`W_spectral_tensor`，并在重构的 `bmm` 表达式中直接相乘。适配器保存原始表达式。

这里 W 是**节点域 `[784,2]`** 值，每次 forward 被投影为 `W_hat`，不是直接存储的 `[20,2]` 谱系数。乘法在最后一维将 `[B,20,1]` 广播到 `[B,20,2]`。输出为两个节点特征通道 `[B,784,2]`，不能画成 `[B,784]`、一通道图像或分类概率。

## 源码与图元对应

| 图元 / IR 身份 | 源码位置（派生 `.py`） | 真实含义与对应原因 |
|---|---|---|
| `spectral.basis_init` | `precompute_adjacency_matrix`，85–111；`get_graph_laplacian`，114–124；构造器，147–166 | 构造期来源面板，与逐批 forward 区分；固定 A/L/V 不来自图像值 |
| `spectral.adj` | adjacency helper | 归一化网格坐标、欧氏距离、`exp(-dist/sigma²)`、`.01` 阈值；源码使用未平方距离 |
| `spectral.laplacian` | Laplacian helper | `D=sum(A,axis=0)`，`D_hat=diag((D+1e-5)^(-.5))`，`L=I-D_hat A D_hat` |
| `spectral.eigsh` | `eigsh(L.numpy(), k=20, which='SM')` | 不展开库内部，不模拟执行；保留截断模式数与选择规则 |
| `spectral.vbuffer` → `spectral.vread` | `torch.from_numpy(V)`、`register_buffer('V',V)`、`self.V` | 注册与 forward 读取的是一个 V buffer；A/L 也被注册，但不参与当前 forward 运算 |
| `spectral.w_init` → `spectral.wread` | 构造器的 Parameter/cast/init/注册；forward 读取 | 保留 W 的实际构造与 buffer 身份，不能只看到 Parameter 字样就判为优化器参数 |
| `spectral.input` → `spectral.reshape` | forward，170–200 | `[B,1,28,28]` 图像重排成 `[B,784,1]` 节点特征 |
| `spectral.vt` / `spectral.vexpand` | `self.V.T.expand` / `self.V.expand` | 同一 V 的转置批视图和重构批视图；不同算子结果、相同来源身份 |
| `spectral.wexpand` | `self.W_spectral.expand` | 同一 W buffer 广播到批次，没有逐图新参数 |
| `spectral.xproject.bmm` / `spectral.wproject.bmm` | X_hat / W_hat 两条 `bmm` | 使用 Vᵀ 投影两个独立操作数；并列表示依赖结构，不保证并行执行 |
| `spectral.product` | `X_hat * W_hat` | 通道广播的逐元素乘法，既不是矩阵乘法，也不是拼接 |
| `spectral.reconstruct.bmm` | `V_tensor.bmm(X_hat * W_hat)` | 同一 V buffer 回到节点空间；Λ 未出现在 forward 中 |
| `spectral.output` | 选定边界中的 Y | 模块出口；完整 GraphNet 的返回值仍是外部分类头的 logits/probas |

adjacency helper 中 return 后的三引号字符串只是字符串内容，里面的度归一化不会执行。图元也不把那一段画成 A 的真实预处理。度因素在真正的 `get_graph_laplacian` 中计算，不能把这两个位置混为一谈。

## W：存储身份与梯度身份必须分开

```python
W_spectral = nn.Parameter(torch.ones((img_size**2, num_filters))).float()
torch.nn.init.kaiming_uniform_(W_spectral)
self.register_buffer('W_spectral', W_spectral)
```

最终注册入口是 **buffer**。后面的 `SGD(model.parameters(), ...)` 不会通过这个 buffer 注册发现 W。因此不能把它标为“优化器学习的谱参数”，也不能把 `nn.Parameter` 的构造图元放在 forward 主序列中。

这并不证明 W 的 `requires_grad=False`。Parameter 构造默认开启梯度；`.float()` 若无需转换可能保留原对象，若转换则可能影响 Tensor 子类型、叶子身份与梯度连接；后续 `.to(DEVICE)` 也有运行时相关行为。图与 IR 记录 `storage_kind='buffer'`、`optimizer_parameter=False`，并把梯度状态保留为有条件的运行时问题。本次静态取证没有执行这些转换。

V 的 `torch.from_numpy(V)` 没有显式 `.float()`，其 dtype 继承 SciPy 返回数组。图中保存这一事实，不自动修源码、插入 cast 或声称已验证 `bmm` 的 dtype 兼容性。形状可以静态推导，数值可运行性仍需另行实测。

## 只保留活跃值依赖

源码的三个 unsqueeze 赋值会执行，但马上被以下直接从 buffer 的 expand 赋值覆盖：

```python
V_tensor = self.V.unsqueeze(0)                 # overwritten
V_tensor = self.V.expand(B, -1, -1)
V_tensor_T = self.V.T.unsqueeze(0)              # overwritten
V_tensor_T = self.V.T.expand(B, -1, -1)
W_spectral_tensor = self.W_spectral.unsqueeze(0)# overwritten
W_spectral_tensor = self.W_spectral.expand(B, -1, -1)
```

所以本例画的是 Y 的活跃值依赖，不是完整的语句执行时间线。`profile.dead_assignments` 保存被覆盖语句，图中不构造错误的“unsqueeze 结果 → expand”数据边。类似地，构造器求出的 Λ 没有用于本模块的 forward，不能加上“乘特征值”的标准教科书流程。

## 程序化布局与三粒度

[spectral_filter.py](../module_adapters/spectral_filter.py) 使用显式 `graph`，而非把全图伪装成 Sequential。主图底部有三条独立来源链：图像节点特征、V 的转置批视图、W 的批视图。每条链内部自底向上；主图上层先放两项投影，再放乘法/重构 V 视图，最后放重构与模块出口。

`graph.ranks` 是从底到顶的层级约束，**不会自动生成边**。真实依赖通过 `extra_edges` 单独声明，包括投影的两个有序操作数、V 到重构的共享 buffer 边，以及 `B=x.size(0)` 的 shape 边。因此 V/W 不会被错误连接成图像值的两个分支，三个底部操作数也不是源码创建的 tuple。

显式层间距 72px、列间距 64px 为每端 24px 转弯终段留下空间；容器尺寸由实测文字和子级尺寸计算。箭头在预留通道提前转弯，端点通过节点端口接入，辅助来源/shape 依赖使用虚线。底部独立链与灰色构造器面板构成稳定层次；蓝色投影、黄色乘法、粉色输入、紫色输出延续 Transformer 原型的字体、颜色对比与深色轮廓。

- **概览**折叠各输入准备链和谱滤波作用域。
- **模块层**打开输入准备与两项投影、乘法、V 视图、重构关系。
- **算子层**展开投影/重构的具体 bmm 和构造器来源，所有模块内部保持自底向上。

```bash
cd module_programmatic_guide
python generate.py --module spectral_filter --png
python verify.py --module spectral_filter --png
```

结果包括 [详细 SVG](../generated/spectral_filter/figure3_detailed.svg)、[逐节点源码表](../generated/spectral_filter/source_map.md)、[语义 IR](../generated/spectral_filter/semantic_ir.json)、[布局记录](../generated/spectral_filter/layout_detailed.json)。固定哈希、AST/单元映射、专用语义守卫和几何核验共同验证出处、形状、操作数、存储身份和路由。专用守卫会拒绝把 W 改成优化器参数、把 Y 改成单通道、颠倒 bmm 操作数、添加假 fork 或丢失 B 的 shape 依赖。

这是经过审阅的固定配置模块适配器，不是任意 GNN 源码的自动解析器。其他模式数、通道数、邻接生成规则、注册方式或模型版本都需要相应审阅与适配。
