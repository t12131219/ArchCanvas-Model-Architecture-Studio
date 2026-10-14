# TextCNN：三种卷积宽度、长度掩码与拼接分类器

本例来自 `rasbt/deeplearning-models` 的 `pytorch_ipynb/cnn-nlp/cnn_imdb.ipynb`。这份冻结版本是带真实 **valid-window mask** 的新实现，不能套用旧版 torchtext 教程图。

[原 notebook](../sources/deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.ipynb) · [派生源码](../sources/deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py) · [适配器](../adapters/textcnn.py) · [版本、哈希及 cell 映射](../source_manifest.json)

绘图只读 AST、配置和函数体，不执行数据下载、词表构建、环境检测或模型训练。入口是 `TextCNN.forward(token_ids,lengths)`，所选视图为 `evaluate` 的 eval 状态，Dropout 不生效；所有结构仍按源码显示。

## 输入、配置和张量维度

`Config` 默认值为 embedding 宽度 E=200、卷积宽度 `(3,4,5)`、每种宽度 F=128 个 filters、最大 token 数 L=512、Dropout=0.5。实际词表行数 `V=len(vocabulary)` 由训练评论构建；`vocab_size=30000` 是含 pad/unk 的上限，不是已知的精确 V。

调用方 `make_loaders` 将每条评论截断到 512 token，并右侧填充 pad ID 0。空 token 序列替换成一个 unk，因此这个数据路径上 `1≤lengths≤512`。token IDs 是 `[B,L]`，lengths 是 `[B]`；B=128 是 batch 设置，图中 batch 仍是符号维度。

| 阶段 | 图中形状 | 源码对应 |
| --- | --- | --- |
| Token IDs + lengths | `[B,512]`，`[B]` | 调用方 `TensorDataset(ids,lengths,labels)`；forward 的两个参数 |
| Embedding | `[B,512,200]` | `nn.Embedding(V,200,padding_idx=0)`；同一张词表矩阵供三分支使用 |
| Transpose | `[B,200,512]` | `.transpose(1,2)`；把 embedding 维作为 Conv1d channels |
| k=3 分支 Conv/ReLU | `[B,128,510]` | `convolutions.0`，stride=1、padding=0，S=L−k+1 |
| k=4 分支 Conv/ReLU | `[B,128,509]` | `convolutions.1`，独立参数 |
| k=5 分支 Conv/ReLU | `[B,128,508]` | `convolutions.2`，独立参数 |
| 每分支 mask + amax | `[B,128]` | 无效窗口屏蔽后 `features.amax(dim=-1)` |
| Concat | `[B,384]` | `torch.cat(pooled,dim=1)`，顺序 k=3、4、5 |
| Dropout + Linear | `[B,384] → [B,2]` | `self.dropout`，`classifier=nn.Linear(3*128,2)` |

没有 forward Softmax。`evaluate` 对 logits 做 `argmax(dim=1)`，损失使用调用方的 CrossEntropy；模型返回的是两个类别的 raw logits。

## 为什么长度掩码要作为独立依赖

每个分支先 Conv1d 后 ReLU，再执行以下真实源码逻辑：

```python
width = convolution.kernel_size[0]
valid_windows = (lengths - width + 1).clamp(min=1)
positions = torch.arange(features.shape[-1], device=features.device)
mask = positions[None, :] >= valid_windows[:, None]
features = features.masked_fill(
    mask[:, None, :], torch.finfo(features.dtype).min
)
pooled.append(features.amax(dim=-1))
```

图把算子明确拆成“长度减 k 加 1”“Clamp 至少 1”“位置 arange”“比较产生 mask”“masked_fill”“amax”。lengths 从调用方辅助输入接入三个独立分支的 window-count 侧端口；它不从 Embedding 的值推导，也不是可学习特征。

mask 的两个控制操作数是有效窗口数 `[B]` 和位置编号 `[S]`；比较后广播成 `[B,S]`，再用 `mask[:,None,:]` 广播到所有 F=128 filters。mask 构造读取 Conv/ReLU 特征的 **形状** 来确定 S；卷积输出数值原样保留为另一个操作数。

这里两个内部 `parallel` 容器带 `semantic_mode='operand_bundle'`、`literal_tuple=False`：它们是**适配器的逻辑操作数分组**，源码没有生成 `(features,mask)` 或 `(valid_windows,positions)` tuple，也没有对 ReLU tensor 解包。它们不使用 tuple-field `dispatch`。只有外层三个卷积分支的结果收集对应源码真实的 `pooled` 列表。

| 内部操作数 | `child_inputs` / `input_relation` 类型 | 唯一真实生产者 |
| --- | --- | --- |
| Retain ReLU features | `value`，端口 `out` | 对应分支的 ReLU tensor 值 |
| valid_windows count | `external` | 调用方 lengths；只有 lengths 侧边连线提供输入 |
| positions | `shape`，端口 `shape` | 对应分支 `features.shape[-1]`；不读取 feature 数值 |
| mask | count、positions 的逻辑操作数收集 | 比较两个独立操作数，得到 `[B,S]` |
| masked_fill | features、mask 的逻辑操作数收集 | 原 ReLU 值与独立 mask，广播后执行填充 |

`external` 子分支不生成来自父图框的伪入边；`shape` 关系使用形状引用边，而不是当作张量值传递。mask 控制图框的入口也标记为 `boundary_input_role='shape'`。因此 features 的形状不会进入 `lengths-k+1`，lengths 也不会进入卷积输入；边的类型和生产者在 IR 中保留，可独立核验。

对长度 n≥k 的评论，保留 n−k+1 个完整真实 token 窗口。对 n<k 的短评论，源码不是让所有窗口都无效，而是因 clamp 保留第 0 个由真实 token 和右侧零 padding 组成的窗口。后续 amax 因此总有一个候选。这不是额外的 Conv padding 参数：Conv1d 本身仍是 padding=0。

填充值是 `torch.finfo(features.dtype).min`，为当前浮点类型的**有限最小值**，不是字面 `-inf`。调用方 eval 使用 CUDA bfloat16 autocast，但图不固定内部 dtype，也没有执行核验；填充值在运行时根据实际 features dtype 选择。

## 结构与参数身份

Embedding、三个 Conv1d、Linear 384→2 是独立可学习层。三个分支共用同一 embedded sequence，但各有 `convolutions.0/.1/.2` 参数。每个核在自身的位置轴上重复使用，并不是三种 kernel widths 共用权重。

Embedding 初始化为 uniform[-0.25,0.25]，padding_idx=0 的行在构造中显式置零。图只画一个共享词表节点，没有插入 pretrained embedding、位置编码或 attention。`make_loaders` 的 HTML 清理、lowercase 和 tokenization 属于调用方，保存在来源证据中，没有伪装成 forward 算子。

分支最后一个 amax 只压缩各自的位置轴。收集到 `pooled` 列表后，`torch.cat(...,dim=1)` 把三个 `[B,128]` 张量连成 `[B,384]`；因此 Concat 是显式黄色算子，而不是并行容器自动执行求和或拼接。

## 三种粒度与布局规则

概览展示 Embedding、三卷积宽度容器和分类头，并保留长度输入依赖。模块图展开共享 Embedding/Transpose、三条并列分支和 Concat/Dropout/Linear；分支内部折叠。详细图完整展开 **k=3** 的 mask 操作数、有效窗口数和位置比较；k=4、k=5 仍分别显示其 Conv/ReLU、masked_fill 和 amax，只将同型的 features/mask 操作数图框折叠，以缩短图宽。

这个代表性展开由 `view_overrides["2"]` 控制，仅影响详细视图的显示。三分支全部 54 个语义节点、源码来源、参数身份、shape 引用和 lengths 输入仍保留在 IR；k=4、k=5 的 lengths 连线投影到对应的折叠操作数图框，真实终点仍是各自 count 节点的 `lengths` 端口。三条分支既没有合并参数，也没有用 k=3 的 mask 代替另两种宽度的 mask。

全部 chain 使用源码执行顺序，布局器让内部和外部都自底向上。三分支根据内在宽高并列排布；不同 S 只影响形状标签，不改变分支顺序。内部控制操作数并列是数据依赖的表达，不是声称 Python for loop 三次迭代并发执行。实际源码顺序执行 ModuleList 三次，架构图采用并列来体现“共享生产者、独立权重、结果收集”的关系。

lengths 的三条辅助线采用独立路线和独立接收端；折叠后端点投影到对应的可见容器边界。详细图的 k=3 显式进入 count 节点，k=4/5 投影到各自折叠的操作数容器；悬停提示与 IR 记录真实 count 终点。字体、实色边框、浅蓝计算块、粉色 Embedding、黄色 Concat、紫色 Linear 继承 Transformer 原型；相同色彩只表示同类算子，权重身份另存 IR。

## 已按源码纠正的常见图示偏差

- 输入是 batch-first `[B,L]`，卷积前 transpose 到 `[B,E,L]`；不是把词向量画成 Conv2d 图像。
- 三个分支的宽度 3/4/5、filter 数 128，输出位置分别 510/509/508，不能忽略 valid convolution 的长度变化。
- 长度 mask 先于 amax，防止 padding 区间产生候选；不能直接对全部卷积输出做 max pooling。
- 短评论采用 clamp 至少一个窗口；不能补全失效输出或擅自改成 `-inf`。
- 三分支结果通过 Concat 形成 384 维，不是 Add，也不共享 Conv 权重。
- forward 不包含 Softmax、Sigmoid、LSTM packing、双向 RNN 或 attention。

源码附 `check_model`：比较同一 token 序列补更多右侧 padding 后的 logits。本次只把这个函数作为来源证据保存，未运行其断言；静态图不宣称已经完成模型推理正确性验证。更换分支宽度、filters 数或最大长度后，需要同步更新适配器 profile、shape 和参数身份，重新进行源码审阅。
