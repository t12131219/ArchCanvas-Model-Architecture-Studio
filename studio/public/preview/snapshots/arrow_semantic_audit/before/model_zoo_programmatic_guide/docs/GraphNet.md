# GraphNet：固定像素邻接、buffer 与一次加权聚合

本图对应固定 `rasbt/deeplearning-models` 提交 `59beda3aa25337e576564f1c18c6edd26f9f30e3` 的 `pytorch_ipynb/gnn/gnn-basic-1.ipynb`。入口是 `GraphNet.forward(x)`，所选配置为 MNIST 灰度 28×28、10 类、eval；返回原始 logits 和 Softmax 概率。图另外保留 `__init__` 中邻接矩阵预计算的独立侧面板，说明 forward 读取的 buffer 来自哪里；这个面板不是每个 batch 执行的网络层。

[原 Notebook](../sources/deeplearning-models-batch4/pytorch_ipynb/gnn/gnn-basic-1.ipynb) · [派生 Python](../sources/deeplearning-models-batch4/pytorch_ipynb/gnn/gnn-basic-1.py) · [适配器](../adapters/graphnet.py) · [固定哈希与原 cell 映射](../source_manifest.json)

配置位于原 Notebook cell 9，数据加载位于 cell 11，`precompute_adjacency_matrix` 位于 cell 13，模型类在 cell 15，构造实例在 cell 16，评估函数和训练 loop 在 cell 18。cell 索引从 0 起。绘图只解析文本与 AST，不执行 Notebook、SciPy、邻接矩阵计算、MNIST 下载、模型或训练。

## 模型真实执行的结构

每张图片有 N=28×28=784 个像素节点，每个节点只有一个标量特征。x 为 `[B,1,28,28]`，展成 `[B,784,1]`。空间位置确定一份固定矩阵 A_hat，所有图像都使用这同一份矩阵；它不读取像素值，不由网络预测，也不是优化器中的参数。

forward 的 live 返回值依赖为：

```python
B = x.size(0)
A_tensor = self.A.expand(B, -1, -1)
x_reshape = x.view(B, -1, 1)
avg_neighbor_features = torch.bmm(A_tensor, x_reshape).view(B, -1)
logits = self.fc(avg_neighbor_features)
probas = F.softmax(logits, dim=1)
return logits, probas
```

每个聚合结果为 `f_i = sum_j A_hat[i,j] * x_j`。`avg_neighbor_features` 虽然含有 avg 字样，计算实际是加权求和，并不是求邻居的算术平均。`self.fc` 对整个 784 节点向量作 `Linear(784,10,bias=False)`；它不是对每个节点增加可学习 channel projection。唯一训练参数为 `fc.weight:[10,784]`。

这份源码没有多层 GCN、节点隐藏通道、ReLU、attention、图 pooling 或残差。固定图滤波加一个全图线性分类头足以描述当前实现；不能照搬常见 GCN 架构图补入不存在的层。模型里也没有 BN 或 Dropout，train/eval 不改变这里的算子序列。

## 源码与各图例对应

| 图中结构 | 源码绑定 | 为什么这样对应 |
| --- | --- | --- |
| Fixed graph / init | `precompute_adjacency_matrix` 与 `GraphNet.__init__` | 初始化时根据固定像素坐标预计算一次，与图像张量的 value 路径独立 |
| Grid coordinates / Euclidean distance | `np.meshgrid`、stack/reshape、`cdist` | 每个像素位置是一节点，图的边权依据二维位置距离 |
| Kernel / Threshold | `np.exp(-dist/sigma**2)`、`A[A<.01]=0` | 真实核参数与稀疏化规则决定固定权重；保留源码公式而非教材模板 |
| Degree factors / Scale rows and columns | `D=A.sum(1)`、`D_hat=(D+1e-5)**(-.5)`、左右乘 | 度数归一化需要保留原 A 与 degree factors 两个依赖，不是普通 row mean |
| register_buffer("A") | `self.register_buffer('A', A)` | 保存非学习状态，随 `model.to` 移动并默认进入 state_dict；不进入 parameters |
| External B shape route | `B=x.size(0)` | 只利用 batch 大小，为 expand 提供 shape；像素值不生成 A |
| Broadcast fixed adjacency | `self.A.expand(B,-1,-1)` | 同一 `[784,784]` buffer 的 batch 广播 view，不为每张图复制/训练一套邻接参数 |
| View pixels as node features | `x.view(B,-1,1)` | 单通道像素成为 N 个 scalar node features，不凭空添加节点特征编码 |
| Node values / fixed weights | bmm 的两个真实实参 | 逻辑 operand scope 表达独立 X 与 A，源码没有额外建立一个 tuple |
| Batch MatMul / View nodes | `torch.bmm(...).view(B,-1)` | bmm 先产生 `[B,N,1]`，其后的 view 才产生 `[B,N]` |
| Linear 784→10 / Softmax | `self.fc` 与 `F.softmax(logits,dim=1)` | 分类参数作用在全部节点；概率是真实 forward 运算和返回字段 |
| Return tuple | `return logits,probas` | 对同一 logits 进行保留与 Softmax 分支，最后返回两个 `[B,10]` tensor |

`Image pixels to graph nodes`、`Fixed neighbor aggregation`、`Whole-image linear head` 是绘图适配器为阅读建立的阶段组，源码没有这几个额外成员类或 Sequential。参数路径和实际语句保持原样。

## 预计算公式必须忠于代码

坐标为 `stack(col,row).reshape(-1,2)/img_size`。在28的配置中，坐标值为 `0/28` 到 `27/28`，不是除以27后使最后一格恰好等于1。`cdist(...,metric='euclidean')` 产生实际欧氏距离。

源码变量注释写 Gaussian filter，但实际计算 `exp(-dist/sigma**2)`，其中 `sigma=.05*pi`，**没有再对 dist 平方**。标准高斯/RBF 教材图不能覆盖这一差别。小于 `.01` 的值被置零，随后转换为 float32 Tensor，再做 `D_hat[:,None] * A * D_hat[None,:]`。

对角距离为零，因此归一化前 A 的对角项为 `exp(0)=1`；源码没有额外 `A+I`。归一化后对角权重还会受到 degree factors 缩放，不是仍然强制为1。`D+1e-5` 也必须保留，不能把图改成精确无 epsilon 或 row-stochastic 的归一化声明。

详细侧面板从坐标、距离、核、阈值、Tensor 转换、row sum、inverse square root 到左右 degree 缩放、buffer 注册，全部自底向上。A 在计算 D 的过程中继续被保留；一条明确的 retained-A 边连接 Float Tensor 与 normalization 的 A 侧端口，避免把归一化误读为只依赖度数的单输入运算。

## 被覆盖的 unsqueeze 为什么不接入主链

原 forward 实际还执行了一次：

```python
A_tensor = self.A.unsqueeze(0)
A_tensor = self.A.expand(B, -1, -1)
```

第一行结果没有被第二行读取：第二行仍然从 `self.A` 出发，并覆盖局部变量 A_tensor。当前图明确限定为**返回值的 live 数据依赖**，因此把第一行作为被覆盖的赋值事实记录在 profile、facts 和本文中，未将其画成主链执行节点。这不是宣称原语句不存在，也没有修改原源码。

如果需要展示逐语句执行或内存分配，应另加 dead-result 视图；不能把本图改成 `self.A → unsqueeze → expand` 并声称那是实际依赖。源码的 batch comments 以及“Output:[B,N]”注释也须由调用校正：bmm 输出 `[B,N,1]`，紧随其后的 view 才得到二维 tensor。

## 排布、颜色和三种粒度

主链自底向上为 Input → reshape → 聚合 operand scope → bmm → view → Linear → logits/Softmax tuple。并列 scope 中只有像素特征分支从 reshape 读取 value；固定 A 分支通过独立 buffer 边进入，B 通过 shape 边进入。它们不是同一个 tensor 的普通 fork，更不是 pixel-derived adjacency。

概览折叠 forward、显示 constructor 的固定 buffer 来源；模块图展示 reshape、aggregation、classifier；详细图展开聚合的两个 operand 和初始化预计算。两个辅助依赖可以经过侧方通道，主操作始终向上。constructor 侧面板的位置由其目标分支和可用空间决定，它的几何邻近不意味着和 forward 同时执行。

共享引擎递归测量标题、shape、证据标识和子节点，主阶段等宽对齐，并列宽度来自两支及其间距。副面板内部保持单列以减少宽度；保留 A 的侧边走线与 batch-shape 路线避开框边和节点，末段预留至少18px。Transformer 样式的字体、深边线、粉色输入、浅蓝聚合、紫色Linear、绿色Softmax和灰色buffer阶段用于视觉角色；颜色不能把 non-learnable buffer 推断成可训练层。

## 与 gnn-basic-edge-1 的区别

[gnn-basic-edge-1.py](../sources/deeplearning-models-batch4/pytorch_ipynb/gnn/gnn-basic-edge-1.py) 是同一固定仓库的另一个实现，适合未来建立独立适配器。它有显著新增的语义：

| 项目 | 当前 fixed-A GraphNet | edge-predictor 变体 |
| --- | --- | --- |
| 保存的 buffer | 固定 A_hat `[N,N]` | 标准化的像素对坐标 `coord:[N,N,4]` |
| 边权产生时机 | `__init__` 预计算一次 | 每次 forward 调用 `pred_edge_fc(self.coord)` |
| 学习参数 | 仅分类 `fc.weight` | 额外 edge MLP：Linear4→32→1，有 bias 与 ReLU/Tanh |
| 边权性质 | 距离核、threshold、symmetric-degree scaling | Tanh 可产生负权重；没有 threshold 或 degree normalization |
| 图像内容是否决定边 | 否 | 仍然否：预测器输入是固定坐标，不是图像特征 |
| A 的存储身份 | registered buffer | forward 将预测 Tensor 写到 `self.A`，不是注册的 A buffer/Parameter |

edge MLP 的参数从分类损失获得梯度，在所有像素对和图像之间复用；不能把它叫成 image-conditioned attention、每条边独立 Parameter 或当前 fixed-A 版本已有的模块。该变体当前只完成差异审阅，尚未绘图适配，也未执行模型。

## 验证与复用边界

`validate_ir()` 验证784 scalar节点、真实未平方距离核、阈值/degree epsilon、constructor buffer、A与B来源、typed bmm operands、bmm/view shape、唯一 bias-free Linear 权重与双返回字段。修改 A 的 learnable 标识或把核改成 squared distance，会被语义检查拒绝。

固定源码与 Notebook 哈希、原 cell 行号、AST 片段、导出与几何检查构成其余验证层。这些检查覆盖当前经过审阅的 grayscale28×28 profile，没有运行 forward 或证明当前库环境的数值结果。换图尺寸、节点特征宽度、邻接规则或引入 edge predictor，需要重新审阅和适配；只改图标签或 `--source-root` 不足以获得正确新图。
