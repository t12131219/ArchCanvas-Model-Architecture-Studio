# Bahdanau attention / query-key-value roles：源码、端口与程序化布局

本例选择eladhoffer `AttentionLayer` 的mode=bahdanau，query_size=12、key_size=16、value_size=20、batch_first=True、normalize=False、weight_norm=False、query_transform/output_transform=True，output_nonlinearity=tanh。选3个query、8个key，显式values和key mask，eval，Dropout参数0.1。

目录依据：[固定Awesome-pytorch-list第462行](https://github.com/bharathgs/Awesome-pytorch-list/blob/06e9786eb64392cbe233d1a9ab7489256c0ac521/README.md#L462)。目录列举仓库；适配器进一步选择该仓库内明确的模块/源码子图。

实际源码冻结为 `eladhoffer/seq2seq.pytorch` 提交 `769c9995594ea0059075280f49a86ac4dace28bd`。所有文件保留SHA256、Git blob摘要和LICENSE；[来源记录](../staging/sequence_source_manifest.json)与正式source_manifest合并后继续绑定相同字节。适配器：[module_adapters/seq2seq_additive_attention.py](../module_adapters/seq2seq_additive_attention.py)。

- [seq2seq-additive-sequence/seq2seq/models/modules/attention.py](../sources/seq2seq-additive-sequence/seq2seq/models/modules/attention.py)；符号：`AttentionLayer.__init__`, `AttentionLayer.set_mask`, `AttentionLayer.calc_score`, `AttentionLayer.forward`

## 每个图框为何对应这段源码

| 图框/稳定ID | 实际代码位置 | 对应理由与不能混淆的关系 |
|---|---|---|
| `addatt.query` | [第98行](../sources/seq2seq-additive-sequence/seq2seq/models/modules/attention.py#L98)：`att_query = self.linear_q(query)` | 只有query变换12→16；keys不经过新增K投影 |
| `addatt.qexpand / kexpand` | [第66行](../sources/seq2seq-additive-sequence/seq2seq/models/modules/attention.py#L66)：`att_query = att_query.unsqueeze(2)` | 把query/keys扩成所有pair，分别unsqueeze2/1 |
| `addatt.add / scoring` | [第68行](../sources/seq2seq-additive-sequence/seq2seq/models/modules/attention.py#L68)：`sum_qk = att_query + att_keys` | 相加→view→Tanh→linear_att16→1→restore，是真实Bahdanau分支 |
| `addatt.mask` | [第106行](../sources/seq2seq-additive-sequence/seq2seq/models/modules/attention.py#L106)：`scores.masked_fill_(mask, -1e12)` | key mask沿query广播，填有限-1e12 |
| `addatt.softmax / drop` | [第113行](../sources/seq2seq-additive-sequence/seq2seq/models/modules/attention.py#L113)：`scores_normalized = self.dropout` | 沿key axis2归一化后dropout，返回值也读取dropout之后的变量 |
| `addatt.context` | [第114行](../sources/seq2seq-additive-sequence/seq2seq/models/modules/attention.py#L114)：`context = torch.bmm(scores_normalized, values)` | 明确values输入宽20，不偷偷以keys替代 |
| `addatt.concat / fusion` | [第117行](../sources/seq2seq-additive-sequence/seq2seq/models/modules/attention.py#L117)：`context = self.linear_out(torch.cat([query, context], 2))` | 原始12维query在前，20维context在后；32→12线性和Tanh |
| `addatt.output` | [第129行](../sources/seq2seq-additive-sequence/seq2seq/models/modules/attention.py#L129)：`return context, scores_normalized` | 返回融合context与post-dropout权重 |

带颜色的容器是语义阶段与布局分组；只有明确指出真实类、Sequential或ModuleList实例时，才能把它当作源码模块实例。图中的group不会另建Python层；图元文字可以缩短，但IR中的source引用、参数身份和端口保持稳定。

## 形状、参数与依赖

linear_q `[16,12]`、linear_att `[1,16]`、linear_out `[12,32]` 分别拥有独立bias。配对张量 `[B,3,8,16]` 的广播不创建独立parameter；同一linear_att共享于全部query-key pair。values=None时源码会复用keys，但本profile明确传入 `[B,8,20]` 的values。eval使attention Dropout保持值，节点和真实返回依赖仍保留在IR中。

## 三个视图怎样分配位置与箭头

query投影首先上升，再与keys扩展并列；汇到pair-add与score容器。mask/softmax/drop依次在上方；显式values绕过scorer进入bmm，原始query绕过linear_q到concat。顶部weights端口连接Dropout输出，而非直接连接Softmax。

所有层级采用同一语义IR，源码调用顺序与数据依赖决定节点的先后，`graph.ranks`只分配底→顶的依赖层，不会创建隐式tensor边。每个branch容器内部继续自底向上；同一rank的节点并列、内容测量决定宽高，统一留白通道容纳正交连线。真实多输入算子通过不同命名端口接收依赖；旁路可跨多rank而不改来源。容器折叠时路由投影到最近可见祖先，不能把folded节点误认为实现缺失。

使用Transformer原型的字体、蓝/橙阶段对比、粉色输入、紫色Linear/输出、黄色汇流/归一化、绿色门函数和Softmax。颜色表达操作角色；相同颜色不证明共享权重。并列rank不自动表示fork/tuple或Add；这些关系必须由`extra_edges`和端口另行声明。连线保留终端留白，避免沿边框或穿过无关叶节点。箭头标签采用底部术语说明，减少文字穿边框。

## 范围与可复现验证

该类还有dot_prod、normalize/weight_norm、single_query、batch_first=False和输出nonlinearity分支，本图只表达明确列出的profile，不把未选分支拼成同一个执行流程。

[checks/sequence_extended.py](../checks/sequence_extended.py)直接解析冻结源码AST，核对关键算子表达式、配置、参数与真实依赖，并注入错误producer/端口与错误语义字段。取证与图像验证包括源码hash/symbol证据、IR检查、框包含、节点间距、正交箭头、终端长度、SVG实际对象和PNG。只运行绘图/静态检查，不import、执行或训练上游模型；形状是显式profile下的推导。

在原型根目录中运行持久检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 checks/sequence_extended.py
```

正式生成后查看：[概览](../generated/seq2seq_additive_attention/figure1_overview.svg) · [模块层](../generated/seq2seq_additive_attention/figure2_modules.svg) · [算子层](../generated/seq2seq_additive_attention/figure3_detailed.svg) · [图库](../generated/seq2seq_additive_attention/index.html)。
