# QANet context-query attention：源码、端口与程序化布局

只画QANet `CQAttention`。冻结config的d_model=96、dropout=0.1保持不变；context length8、query length5是显式模块示例，eval。输入C/Q是channels-first，不包含encoder blocks、Pointer或词/字符embedding。

目录依据：[固定Awesome-pytorch-list第595行](https://github.com/bharathgs/Awesome-pytorch-list/blob/06e9786eb64392cbe233d1a9ab7489256c0ac521/README.md#L595)。目录列举仓库；适配器进一步选择该仓库内明确的模块/源码子图。

实际源码冻结为 `hengruo/QANet-pytorch` 提交 `04605e21172b3a5e8b0e2b7a869f2e55ef02e8fb`。所有文件保留SHA256、Git blob摘要和LICENSE；[来源记录](../staging/sequence_source_manifest.json)与正式source_manifest合并后继续绑定相同字节。适配器：[module_adapters/qanet_context_query_attention.py](../module_adapters/qanet_context_query_attention.py)。

- [qanet-attention-sequence/models.py](../sources/qanet-attention-sequence/models.py)；符号：`CQAttention.__init__`, `mask_logits`, `CQAttention.forward`
- [qanet-attention-sequence/config.py](../sources/qanet-attention-sequence/config.py)；符号：`__module__`

## 每个图框为何对应这段源码

| 图框/稳定ID | 实际代码位置 | 对应理由与不能混淆的关系 |
|---|---|---|
| `cq.c / q / ct / qt` | [第227行](../sources/qanet-attention-sequence/models.py#L227)：`Ct = C.unsqueeze(2).expand(shape)` | 转为length-first后扩出全部context-query pair |
| `cq.cq / features` | [第230行](../sources/qanet-attention-sequence/models.py#L230)：`S = torch.cat([Ct, Qt, CQ], dim=3)` | pair features是[C,Q,C*Q]，而不是多个QKV向量 |
| `cq.score` | [第231行](../sources/qanet-attention-sequence/models.py#L231)：`S = torch.matmul(S, self.w)` | 一个288维learned vector对全部pair评分，无bias |
| `cq.s1 / s2` | [第232行](../sources/qanet-attention-sequence/models.py#L232)：`S1 = F.softmax(mask_logits(S, qmask), dim=2)` | 同一S分别按query/context mask处理；S1 dim2、S2 dim1 |
| `cq.qmask / cmask` | [第22行](../sources/qanet-attention-sequence/models.py#L22)：`return target * (1-mask)` | 真实mask_logits算术公式，mask1为padding，有限-1e30 |
| `cq.a` | [第234行](../sources/qanet-attention-sequence/models.py#L234)：`A = torch.bmm(S1, Q)` | 权重从query位置抽取query values |
| `cq.cross / b` | [第235行](../sources/qanet-attention-sequence/models.py#L235)：`B = torch.bmm(torch.bmm(S1, S2.transpose(1, 2)), C)` | 双矩阵乘法先得context-context权重，再乘原C；没有max reduction |
| `cq.ca / cb / fuse` | [第236行](../sources/qanet-attention-sequence/models.py#L236)：`out = torch.cat([C, A, torch.mul(C, A), torch.mul(C, B)], dim=2)` | 严格四项[C,A,C*A,C*B]，最终4D=384 |
| `cq.tail / output` | [第238行](../sources/qanet-attention-sequence/models.py#L238)：`return out.transpose(1, 2)` | 输出Dropout后恢复channels-first，只返回out |

带颜色的容器是语义阶段与布局分组；只有明确指出真实类、Sequential或ModuleList实例时，才能把它当作源码模块实例。图中的group不会另建Python层；图元文字可以缩短，但IR中的source引用、参数身份和端口保持稳定。

## 形状、参数与依赖

C `[B,96,8]`、Q `[B,96,5]` → C/Qt `[B,8,5,96]` → features `[B,8,5,288]` → S `[B,8,5]`。qmask扩 `[B,1,5]`，cmask扩 `[B,8,1]`，不能交换。S1@Q输出A `[B,8,96]`；S1@S2.T为 `[B,8,8]`，再乘C得到B `[B,8,96]`。所有矩阵均不是标准self-attention的head维。最终concat为 `[B,8,384]`，返回 `[B,384,8]`。

## 三个视图怎样分配位置与箭头

两条C/Q转置和广播并列，pair score汇聚到中央，然后S1/S2两个归一化容器并列。A与S1@S2.T并列，B位于后者上方；C*A、C*B并列后四项汇流。输入mask分别有命名mask端口和虚线，C/Q数值依赖保持实线。

所有层级采用同一语义IR，源码调用顺序与数据依赖决定节点的先后，`graph.ranks`只分配底→顶的依赖层，不会创建隐式tensor边。每个branch容器内部继续自底向上；同一rank的节点并列、内容测量决定宽高，统一留白通道容纳正交连线。真实多输入算子通过不同命名端口接收依赖；旁路可跨多rank而不改来源。容器折叠时路由投影到最近可见祖先，不能把folded节点误认为实现缺失。

使用Transformer原型的字体、蓝/橙阶段对比、粉色输入、紫色Linear/输出、黄色汇流/归一化、绿色门函数和Softmax。颜色表达操作角色；相同颜色不证明共享权重。并列rank不自动表示fork/tuple或Add；这些关系必须由`extra_edges`和端口另行声明。连线保留终端留白，避免沿边框或穿过无关叶节点。箭头标签采用底部术语说明，减少文字穿边框。

## 范围与可复现验证

这份实现与有max-reduction的BiDAF示意图不同；以实际S2和双bmm为准。config默认最大长度400/50不被误当成本模块唯一合法shape。

[checks/sequence_extended.py](../checks/sequence_extended.py)直接解析冻结源码AST，核对关键算子表达式、配置、参数与真实依赖，并注入错误producer/端口与错误语义字段。取证与图像验证包括源码hash/symbol证据、IR检查、框包含、节点间距、正交箭头、终端长度、SVG实际对象和PNG。只运行绘图/静态检查，不import、执行或训练上游模型；形状是显式profile下的推导。

在原型根目录中运行持久检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 checks/sequence_extended.py
```

正式生成后查看：[概览](../generated/qanet_context_query_attention/figure1_overview.svg) · [模块层](../generated/qanet_context_query_attention/figure2_modules.svg) · [算子层](../generated/qanet_context_query_attention/figure3_detailed.svg) · [图库](../generated/qanet_context_query_attention/index.html)。
