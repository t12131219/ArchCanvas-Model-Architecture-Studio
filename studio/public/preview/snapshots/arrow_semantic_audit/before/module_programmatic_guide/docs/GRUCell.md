# GRUCell / explicit reset-update gates：源码、端口与程序化布局

本例选择 PyTorch v2.5.1 benchmark 的函数 `gru_cell(input, hidden, w_ih, w_hh, b_ih, b_hh)`，只画一个时间步。显式示例 I=H=16，输入与隐藏状态均为 `[B,16]`；四个权重/偏置由调用方传入。这个函数本身没有注册 nn.Parameter，也不包含时间循环。

目录依据：[固定deeplearning-models第274行](https://github.com/rasbt/deeplearning-models/blob/59beda3aa25337e576564f1c18c6edd26f9f30e3/README.md#L274)。该目录行仅建立相近的RNN/GRU/LSTM家族联系，实际内核取自下面明确单列的官方benchmark；不是该notebook里的源码展开。

实际源码冻结为 `pytorch/pytorch` 提交 `a8d6afb511a69687bbb2b7e88a3cf67917e1697e`。所有文件保留SHA256、Git blob摘要和LICENSE；[来源记录](../staging/sequence_source_manifest.json)与正式source_manifest合并后继续绑定相同字节。适配器：[module_adapters/gru_cell.py](../module_adapters/gru_cell.py)。

- [pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py)；符号：`gru_cell`

## 每个图框为何对应这段源码

| 图框/稳定ID | 实际代码位置 | 对应理由与不能混淆的关系 |
|---|---|---|
| `gru.gi / gru.gh` | [第119行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py#L119)：`gi = torch.mm` | 两条独立仿射路径分别有自己的权重与偏置；gh的bias必须在reset乘法之前 |
| `gru.ci / gru.ch` | [第121行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py#L121)：`i_r, i_i, i_n = gi.chunk` | 真实chunk(3,1)多输出，依次是reset、update、new三个槽 |
| `gru.reset / gru.update` | [第124行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py#L124)：`resetgate = torch.sigmoid` | 分别对输入/隐藏的对应切片求和再sigmoid；source inputgate命名对应通常的update gate |
| `gru.rhn / gru.candidate` | [第126行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py#L126)：`newgate = torch.tanh` | resetgate乘h_n，再加i_n作Tanh，不是先reset hidden再矩阵乘法 |
| `gru.delta / gru.zdelta / gru.hy` | [第127行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py#L127)：`hy = newgate` | 按原式 n+z*(hidden-n)拆出减法、乘法与加法，z是旧状态保留系数 |
| `gru.output` | [第129行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py#L129)：`return hy` | 只返回hy；没有LSTM的cell state或tuple |

带颜色的容器是语义阶段与布局分组；只有明确指出真实类、Sequential或ModuleList实例时，才能把它当作源码模块实例。图中的group不会另建Python层；图元文字可以缩短，但IR中的source引用、参数身份和端口保持稳定。

## 形状、参数与依赖

W_ih/W_hh分别为 `[48,16]`，b_ih/b_hh分别为 `[48]`，投影后 `[B,48]` 分成三个 `[B,16]` 槽。源表达式中的reset是 **reset-after-affine**；它连同h_n中已加入的隐藏偏置一起相乘。图中的参数输入框是视觉合并的调用方Tensor参数包，不能解释为本函数另建一个参数模块。

## 三个视图怎样分配位置与箭头

底部并列放x、previous hidden、调用方参数；两条仿射与两个chunk并列，reset/update门并列。候选沿中央主链向上，旧hidden和update通过侧通道到末尾融合。chunk槽使用命名出端口表达，避免用无类型的并列线暗示tuple相加。

所有层级采用同一语义IR，源码调用顺序与数据依赖决定节点的先后，`graph.ranks`只分配底→顶的依赖层，不会创建隐式tensor边。每个branch容器内部继续自底向上；同一rank的节点并列、内容测量决定宽高，统一留白通道容纳正交连线。真实多输入算子通过不同命名端口接收依赖；旁路可跨多rank而不改来源。容器折叠时路由投影到最近可见祖先，不能把folded节点误认为实现缺失。

使用Transformer原型的字体、蓝/橙阶段对比、粉色输入、紫色Linear/输出、黄色汇流/归一化、绿色门函数和Softmax。颜色表达操作角色；相同颜色不证明共享权重。并列rank不自动表示fork/tuple或Add；这些关系必须由`extra_edges`和端口另行声明。连线保留终端留白，避免沿边框或穿过无关叶节点。箭头标签采用底部术语说明，减少文字穿边框。

## 范围与可复现验证

这是一份明确单独取证的官方benchmark补充实现。目录中rasbt GRU notebook只调用库nn.GRU，不能声称本函数就是其实际运行内核；这里只补齐可解释的GRU结构选项。

[checks/sequence_extended.py](../checks/sequence_extended.py)直接解析冻结源码AST，核对关键算子表达式、配置、参数与真实依赖，并注入错误producer/端口与错误语义字段。取证与图像验证包括源码hash/symbol证据、IR检查、框包含、节点间距、正交箭头、终端长度、SVG实际对象和PNG。只运行绘图/静态检查，不import、执行或训练上游模型；形状是显式profile下的推导。

在原型根目录中运行持久检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 checks/sequence_extended.py
```

正式生成后查看：[概览](../generated/gru_cell/figure1_overview.svg) · [模块层](../generated/gru_cell/figure2_modules.svg) · [算子层](../generated/gru_cell/figure3_detailed.svg) · [图库](../generated/gru_cell/index.html)。
