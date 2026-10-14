# MI-LSTM / multiplicative gate integration：源码、端口与程序化布局

本例选择官方benchmark `milstm_cell` 从x/hx矩阵投影到gates预激活的源码子图；I=12、H=16、gate width=4H=64。顶端gates是人为选定的子图边界，原函数还会进行四门chunk、普通LSTM更新并返回hy,cy。

目录依据：[固定deeplearning-models第271行](https://github.com/rasbt/deeplearning-models/blob/59beda3aa25337e576564f1c18c6edd26f9f30e3/README.md#L271)。该目录行仅建立相近的RNN/GRU/LSTM家族联系，实际内核取自下面明确单列的官方benchmark；不是该notebook里的源码展开。

实际源码冻结为 `pytorch/pytorch` 提交 `a8d6afb511a69687bbb2b7e88a3cf67917e1697e`。所有文件保留SHA256、Git blob摘要和LICENSE；[来源记录](../staging/sequence_source_manifest.json)与正式source_manifest合并后继续绑定相同字节。适配器：[module_adapters/milstm_projection.py](../module_adapters/milstm_projection.py)。

- [pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py)；符号：`milstm_cell`

## 每个图框为何对应这段源码

| 图框/稳定ID | 实际代码位置 | 对应理由与不能混淆的关系 |
|---|---|---|
| `mi.wx / mi.uz` | [第8行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py#L8)：`Wx = x.mm(w_ih.t())` | 输入和隐藏有独立矩阵；都没有仿射bias |
| `mi.alpha_wx / mi.product` | [第12行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py#L12)：`gates = alpha * Wx * Uz` | 先alpha*Wx，再乘Uz，保留Python源式左结合顺序 |
| `mi.input_term / mi.hidden_term` | [第12行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py#L12)：`gates = alpha * Wx * Uz` | beta_i只乘Wx；beta_h只乘Uz，两条支路共享已经投影的真实producer |
| `mi.add_input / mi.add_hidden / mi.bias` | [第12行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py#L12)：`gates = alpha * Wx * Uz` | 三项按原顺序相加，最后只加一个gate bias |
| `mi.params` | [第7行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py#L7)：`def milstm_cell` | 矩阵/alpha/beta_i/beta_h/bias均为函数Tensor参数，而不是本函数注册的模块 |
| `mi.output` | [第15行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py#L15)：`ingate, forgetgate, cellgate, outgate = gates.chunk` | 此图止于chunk之前的gates；不是原函数return |

带颜色的容器是语义阶段与布局分组；只有明确指出真实类、Sequential或ModuleList实例时，才能把它当作源码模块实例。图中的group不会另建Python层；图元文字可以缩短，但IR中的source引用、参数身份和端口保持稳定。

## 形状、参数与依赖

x `[B,12]`、hx `[B,16]` 分别乘 `[64,12]`、`[64,16]` 转置矩阵得到Wx/Uz `[B,64]`。alpha、beta_i、beta_h、bias选择合法的 `[64]` 广播向量；函数本身并未约束唯一caller shape，也不注册Parameter。source没有独立b_ih/b_hh。先 `(alpha*Wx)*Uz`，再依次加beta_i*Wx、beta_h*Uz、bias；这种拆分保持源算子的结合次序。cx属于原函数普通LSTM后缀输入，不是当前预激活子图的操作数，故不画到本图输入。

## 三个视图怎样分配位置与箭头

两条矩阵投影并列，上一层并列耦合、输入加权项、隐藏加权项；三个项依次汇入三层Add。耦合容器内部alpha*Wx在下，乘Uz在上。Uz从第二操作数侧端口进入上层乘法，以避开下层alpha*Wx；它的主路仍从下向上。调用方参数包的命名端口分别供给六个实际参数使用点。

所有层级采用同一语义IR，源码调用顺序与数据依赖决定节点的先后，`graph.ranks`只分配底→顶的依赖层，不会创建隐式tensor边。每个branch容器内部继续自底向上；同一rank的节点并列、内容测量决定宽高，统一留白通道容纳正交连线。真实多输入算子通过不同命名端口接收依赖；旁路可跨多rank而不改来源。容器折叠时路由投影到最近可见祖先，不能把folded节点误认为实现缺失。

使用Transformer原型的字体、蓝/橙阶段对比、粉色输入、紫色Linear/输出、黄色汇流/归一化、绿色门函数和Softmax。颜色表达操作角色；相同颜色不证明共享权重。并列rank不自动表示fork/tuple或Add；这些关系必须由`extra_edges`和端口另行声明。连线保留终端留白，避免沿边框或穿过无关叶节点。箭头标签采用底部术语说明，减少文字穿边框。

## 范围与可复现验证

这是明确补充的benchmark实现与选定局部子图；没有声称rasbt notebook调用该函数。标准chunk/四门/状态更新后缀不在图中，实际函数return仍是(hy,cy)，不能将gates描述为独立源码类或函数返回。

[checks/sequence_extended.py](../checks/sequence_extended.py)直接解析冻结源码AST，核对关键算子表达式、配置、参数与真实依赖，并注入错误producer/端口与错误语义字段。取证与图像验证包括源码hash/symbol证据、IR检查、框包含、节点间距、正交箭头、终端长度、SVG实际对象和PNG。只运行绘图/静态检查，不import、执行或训练上游模型；形状是显式profile下的推导。

在原型根目录中运行持久检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 checks/sequence_extended.py
```

正式生成后查看：[概览](../generated/milstm_projection/figure1_overview.svg) · [模块层](../generated/milstm_projection/figure2_modules.svg) · [算子层](../generated/milstm_projection/figure3_detailed.svg) · [图库](../generated/milstm_projection/index.html)。
