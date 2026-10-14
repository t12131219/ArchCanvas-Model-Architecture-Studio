# Structured hop attention：源码、端口与程序化布局

只绘制 `StructuredSelfAttention.forward` 从已计算的LSTM outputs到attention与平均sentence embedding的子图。选T=8、lstm_hid_dim=16、d_a=12、r=3；embedding、LSTM本身及分类头均在边界之外。该源码的LSTM是单向，且这段注意力没有padding mask。

目录依据：[固定Awesome-pytorch-list第597行](https://github.com/bharathgs/Awesome-pytorch-list/blob/06e9786eb64392cbe233d1a9ab7489256c0ac521/README.md#L597)。目录列举仓库；适配器进一步选择该仓库内明确的模块/源码子图。

实际源码冻结为 `kaushalshetty/Structured-Self-Attention` 提交 `84ed64f9cee75f84a5d871a46508a308182e4a6d`。所有文件保留SHA256、Git blob摘要和LICENSE；[来源记录](../staging/sequence_source_manifest.json)与正式source_manifest合并后继续绑定相同字节。适配器：[module_adapters/structured_attention.py](../module_adapters/structured_attention.py)。

- [structured-self-attention-sequence/attention/model.py](../sources/structured-self-attention-sequence/attention/model.py)；符号：`StructuredSelfAttention.__init__`, `StructuredSelfAttention.softmax`, `StructuredSelfAttention.forward`

## 每个图框为何对应这段源码

| 图框/稳定ID | 实际代码位置 | 对应理由与不能混淆的关系 |
|---|---|---|
| `struct.scorer` | [第103行](../sources/structured-self-attention-sequence/attention/model.py#L103)：`x = F.tanh(self.linear_first(outputs))` | 两层独立带bias的Linear，中间Tanh；init将bias置0但保持learnable |
| `struct.softmax` | [第105行](../sources/structured-self-attention-sequence/attention/model.py#L105)：`x = self.softmax(x,1)` | 真实softmax helper显式把原time axis1移到最后 |
| `struct.swap / flat / normalize / restore / swapback` | [第90行](../sources/structured-self-attention-sequence/attention/model.py#L90)：`input_2d = trans_input.contiguous().view` | 2D view后源码F.softmax没有dim参数；图保留omitted信息，不改写原调用 |
| `struct.attention` | [第106行](../sources/structured-self-attention-sequence/attention/model.py#L106)：`attention = x.transpose(1,2)` | 得到每hop一行的[B,3,8] attention |
| `struct.pool` | [第107行](../sources/structured-self-attention-sequence/attention/model.py#L107)：`sentence_embeddings = attention@outputs` | 值来源是最初LSTM outputs，不是12维或3维score |
| `struct.avg` | [第108行](../sources/structured-self-attention-sequence/attention/model.py#L108)：`avg_sentence_embeddings = torch.sum` | 按hop维sum/r平均，得到[B,16] |
| `struct.output` | [第108行](../sources/structured-self-attention-sequence/attention/model.py#L108)：`avg_sentence_embeddings = torch.sum` | 选择的边界变量；源码完整forward实际返回classifier output与attention |

带颜色的容器是语义阶段与布局分组；只有明确指出真实类、Sequential或ModuleList实例时，才能把它当作源码模块实例。图中的group不会另建Python层；图元文字可以缩短，但IR中的source引用、参数身份和端口保持稳定。

## 形状、参数与依赖

H `[B,8,16]` → Linear16→12 `[B,8,12]` → Tanh → Linear12→3 `[B,8,3]`。helper转置后 `[B,3,8]`，连续化成 `[B*3,8]` 作位置归一化，再还原；attention `[B,3,8]` 乘H得到三个 `[B,16]` 句子表示，最终取平均。源码没有BiLSTM的2H宽度、mask、attention dropout；单独l2_matrix_norm函数并不是这段forward里执行的正交正则化。

## 三个视图怎样分配位置与箭头

概览折叠整段注意力，模块视图显示score、source-softmax、transpose、weighted pooling和平均。详细视图展开两个Linear以及helper的五步。H保留侧路到A@H，attention另有输出侧路；图例明确无mask，而不是画一条未经源码支持的虚线。

所有层级采用同一语义IR，源码调用顺序与数据依赖决定节点的先后，`graph.ranks`只分配底→顶的依赖层，不会创建隐式tensor边。每个branch容器内部继续自底向上；同一rank的节点并列、内容测量决定宽高，统一留白通道容纳正交连线。真实多输入算子通过不同命名端口接收依赖；旁路可跨多rank而不改来源。容器折叠时路由投影到最近可见祖先，不能把folded节点误认为实现缺失。

使用Transformer原型的字体、蓝/橙阶段对比、粉色输入、紫色Linear/输出、黄色汇流/归一化、绿色门函数和Softmax。颜色表达操作角色；相同颜色不证明共享权重。并列rank不自动表示fork/tuple或Add；这些关系必须由`extra_edges`和端口另行声明。连线保留终端留白，避免沿边框或穿过无关叶节点。箭头标签采用底部术语说明，减少文字穿边框。

## 范围与可复现验证

旧源码的F.softmax省略dim；图解释2D helper的原轴语义，保留API版本边界，不执行或宣称验证现代PyTorch对这份旧教程的兼容性。

[checks/sequence_extended.py](../checks/sequence_extended.py)直接解析冻结源码AST，核对关键算子表达式、配置、参数与真实依赖，并注入错误producer/端口与错误语义字段。取证与图像验证包括源码hash/symbol证据、IR检查、框包含、节点间距、正交箭头、终端长度、SVG实际对象和PNG。只运行绘图/静态检查，不import、执行或训练上游模型；形状是显式profile下的推导。

在原型根目录中运行持久检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 checks/sequence_extended.py
```

正式生成后查看：[概览](../generated/structured_attention/figure1_overview.svg) · [模块层](../generated/structured_attention/figure2_modules.svg) · [算子层](../generated/structured_attention/figure3_detailed.svg) · [图库](../generated/structured_attention/index.html)。
