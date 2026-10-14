# Seq2seq dot attention / context fusion：源码、端口与程序化布局

选IBM `Attention(dim=16)` 模块，decoder output `[B,3,16]`，encoder context `[B,8,16]`。源码mask初始None；本图明确选择调用set_mask后的有效mask分支。不是完整encoder/decoder seq2seq模型。

目录依据：[固定Awesome-pytorch-list第30行](https://github.com/bharathgs/Awesome-pytorch-list/blob/06e9786eb64392cbe233d1a9ab7489256c0ac521/README.md#L30)。目录列举仓库；适配器进一步选择该仓库内明确的模块/源码子图。

实际源码冻结为 `IBM/pytorch-seq2seq` 提交 `f146087a9a271e9b50f46561e090324764b081fb`。所有文件保留SHA256、Git blob摘要和LICENSE；[来源记录](../staging/sequence_source_manifest.json)与正式source_manifest合并后继续绑定相同字节。适配器：[module_adapters/seq2seq_attention.py](../module_adapters/seq2seq_attention.py)。

- [ibm-seq2seq-attention/seq2seq/models/attention.py](../sources/ibm-seq2seq-attention/seq2seq/models/attention.py)；符号：`Attention.__init__`, `Attention.set_mask`, `Attention.forward`

## 每个图框为何对应这段源码

| 图框/稳定ID | 实际代码位置 | 对应理由与不能混淆的关系 |
|---|---|---|
| `ibm.score` | [第59行](../sources/ibm-seq2seq-attention/seq2seq/models/attention.py#L59)：`attn = torch.bmm(output` | decoder output直接与context转置相乘，没有sqrt(D)缩放 |
| `ibm.mask` | [第61行](../sources/ibm-seq2seq-attention/seq2seq/models/attention.py#L61)：`attn.data.masked_fill_` | True项用-inf原地覆盖，源码写的是.data操作 |
| `ibm.softmax` | [第62行](../sources/ibm-seq2seq-attention/seq2seq/models/attention.py#L62)：`attn = F.softmax` | view成二维后沿dim1归一化，再恢复[B,3,8] |
| `ibm.mix` | [第65行](../sources/ibm-seq2seq-attention/seq2seq/models/attention.py#L65)：`mix = torch.bmm` | 权重乘同一个context，它同时充当keys与values |
| `ibm.concat` | [第68行](../sources/ibm-seq2seq-attention/seq2seq/models/attention.py#L68)：`combined = torch.cat((mix, output)` | concat顺序严格是mix在前、原output在后，dim2 |
| `ibm.fusion` | [第70行](../sources/ibm-seq2seq-attention/seq2seq/models/attention.py#L70)：`output = F.tanh(self.linear_out` | view、唯一learned Linear、Tanh、restore view |
| `ibm.output` | [第72行](../sources/ibm-seq2seq-attention/seq2seq/models/attention.py#L72)：`return output, attn` | 返回新output和原归一化attention，源码无Dropout |

带颜色的容器是语义阶段与布局分组；只有明确指出真实类、Sequential或ModuleList实例时，才能把它当作源码模块实例。图中的group不会另建Python层；图元文字可以缩短，但IR中的source引用、参数身份和端口保持稳定。

## 形状、参数与依赖

score `[B,3,8]` 每个decoder位置归一化8个encoder位置。context读两次，但两条依赖都绑定同一source input，不是两个独立投影。combined宽32，linear_out.weight `[16,32]` 与bias `[16]` 是唯一两组learned参数。mask由调用方提供；图选择 `[B,3,8]` 以直接匹配分数大小，不虚构自动构造causal mask。

## 三个视图怎样分配位置与箭头

底部query/context/mask并列；dot→mask→Softmax→context mix→concat→fusion自底向上。context长旁路供mix的values，原query长旁路供concat第二项；softmax权重绕过fusion送到返回框的attention端口。

所有层级采用同一语义IR，源码调用顺序与数据依赖决定节点的先后，`graph.ranks`只分配底→顶的依赖层，不会创建隐式tensor边。每个branch容器内部继续自底向上；同一rank的节点并列、内容测量决定宽高，统一留白通道容纳正交连线。真实多输入算子通过不同命名端口接收依赖；旁路可跨多rank而不改来源。容器折叠时路由投影到最近可见祖先，不能把folded节点误认为实现缺失。

使用Transformer原型的字体、蓝/橙阶段对比、粉色输入、紫色Linear/输出、黄色汇流/归一化、绿色门函数和Softmax。颜色表达操作角色；相同颜色不证明共享权重。并列rank不自动表示fork/tuple或Add；这些关系必须由`extra_edges`和端口另行声明。连线保留终端留白，避免沿边框或穿过无关叶节点。箭头标签采用底部术语说明，减少文字穿边框。

## 范围与可复现验证

source optional mask分支明确选定；mask=None的替代profile需要另行绘制。不加入原文件未写出的投影、缩放或RNN门。

[checks/sequence_extended.py](../checks/sequence_extended.py)直接解析冻结源码AST，核对关键算子表达式、配置、参数与真实依赖，并注入错误producer/端口与错误语义字段。取证与图像验证包括源码hash/symbol证据、IR检查、框包含、节点间距、正交箭头、终端长度、SVG实际对象和PNG。只运行绘图/静态检查，不import、执行或训练上游模型；形状是显式profile下的推导。

在原型根目录中运行持久检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 checks/sequence_extended.py
```

正式生成后查看：[概览](../generated/seq2seq_attention/figure1_overview.svg) · [模块层](../generated/seq2seq_attention/figure2_modules.svg) · [算子层](../generated/seq2seq_attention/figure3_detailed.svg) · [图库](../generated/seq2seq_attention/index.html)。
