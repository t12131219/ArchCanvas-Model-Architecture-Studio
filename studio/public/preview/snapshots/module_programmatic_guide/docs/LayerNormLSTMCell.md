# LayerNormLSTMCell / three independent norms：源码、端口与程序化布局

本例选择官方benchmark `LayerNormLSTMCell(input_size=16, hidden_size=16, decompose_layernorm=True)` 的单步计算。`decompose_layernorm=True` 是显式示例配置；源码默认False时使用库nn.LayerNorm，这里主动选择源码中可以展开的custom LayerNorm。

目录依据：[固定deeplearning-models第271行](https://github.com/rasbt/deeplearning-models/blob/59beda3aa25337e576564f1c18c6edd26f9f30e3/README.md#L271)。该目录行仅建立相近的RNN/GRU/LSTM家族联系，实际内核取自下面明确单列的官方benchmark；不是该notebook里的源码展开。

实际源码冻结为 `pytorch/pytorch` 提交 `a8d6afb511a69687bbb2b7e88a3cf67917e1697e`。所有文件保留SHA256、Git blob摘要和LICENSE；[来源记录](../staging/sequence_source_manifest.json)与正式source_manifest合并后继续绑定相同字节。适配器：[module_adapters/layernorm_lstm_cell.py](../module_adapters/layernorm_lstm_cell.py)。

- [pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py)；符号：`LayerNormLSTMCell.__init__`, `LayerNorm.__init__`, `LayerNorm.compute_layernorm_stats`, `LayerNorm.forward`, `LayerNormLSTMCell.forward`

## 每个图框为何对应这段源码

| 图框/稳定ID | 实际代码位置 | 对应理由与不能混淆的关系 |
|---|---|---|
| `lnlstm.wi / lnlstm.wh` | [第205行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py#L205)：`igates = self.layernorm_i` | input与hx分别矩阵乘法，没有bias_ih/bias_hh |
| `lnlstm.lni / lnlstm.lnh` | [第196行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py#L196)：`self.layernorm_i = ln` | 两个64维归一化实例独立；先各自归一化再相加 |
| `lnlstm.*.mean / *.std` | [第172行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py#L172)：`mu = input.mean` | 沿最后一维算mean与population std(unbiased=False)，保留维度 |
| `lnlstm.*.center / *.divide / *.affine` | [第179行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py#L179)：`return (input - mu) / sigma` | custom实现没有epsilon；逐元素除std后乘weight加bias |
| `lnlstm.split / i,f,g,o` | [第208行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py#L208)：`ingate, forgetgate, cellgate, outgate = gates.chunk` | 真实四门槽，sigmoid/sigmoid/tanh/sigmoid |
| `lnlstm.keep / new / cadd / lnc` | [第215行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py#L215)：`cy = self.layernorm_c` | 先f*cx+i*g，再独立cell LayerNorm；不是norm(tanh(cell)) |
| `lnlstm.ctanh / hy` | [第216行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py#L216)：`hy = outgate` | o乘normalized cy的Tanh |
| `lnlstm.output` | [第218行](../sources/pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py#L218)：`return hy, (hy, cy)` | 保留嵌套返回结构，hy重复出现在主输出和state.hidden |

带颜色的容器是语义阶段与布局分组；只有明确指出真实类、Sequential或ModuleList实例时，才能把它当作源码模块实例。图中的group不会另建Python层；图元文字可以缩短，但IR中的source引用、参数身份和端口保持稳定。

## 形状、参数与依赖

两个矩阵分别 `[64,16]`。`layernorm_i/h/c` 各有自己的weight与bias，宽度分别64、64、16，共六个独立归一化参数张量；矩阵投影本身只有weight。均值与标准差读取同一个待归一化输入，不通过互相串联来计算。custom LayerNorm的式子是 `(input-mu)/sigma*weight+bias`；不得把现代nn.LayerNorm的默认epsilon偷换进来。

## 三个视图怎样分配位置与箭头

输入投影双列，两个64维norm双列；每个norm内部mean/std并列，再向上接center/divide/affine。四门横向并列，在上一层形成保留与新增cell两项，再进入16维cell norm。原cell与output gate保留侧路；顶端返回框有hy、state_hidden、state_cell三个命名端口。

所有层级采用同一语义IR，源码调用顺序与数据依赖决定节点的先后，`graph.ranks`只分配底→顶的依赖层，不会创建隐式tensor边。每个branch容器内部继续自底向上；同一rank的节点并列、内容测量决定宽高，统一留白通道容纳正交连线。真实多输入算子通过不同命名端口接收依赖；旁路可跨多rank而不改来源。容器折叠时路由投影到最近可见祖先，不能把folded节点误认为实现缺失。

使用Transformer原型的字体、蓝/橙阶段对比、粉色输入、紫色Linear/输出、黄色汇流/归一化、绿色门函数和Softmax。颜色表达操作角色；相同颜色不证明共享权重。并列rank不自动表示fork/tuple或Add；这些关系必须由`extra_edges`和端口另行声明。连线保留终端留白，避免沿边框或穿过无关叶节点。箭头标签采用底部术语说明，减少文字穿边框。

## 范围与可复现验证

来源是单独冻结的官方benchmark补充，不能称为目录中的普通nn.LSTM已经识别出的内部执行路径。该图也不包含stack、反向循环或bidirectional组合。

[checks/sequence_extended.py](../checks/sequence_extended.py)直接解析冻结源码AST，核对关键算子表达式、配置、参数与真实依赖，并注入错误producer/端口与错误语义字段。取证与图像验证包括源码hash/symbol证据、IR检查、框包含、节点间距、正交箭头、终端长度、SVG实际对象和PNG。只运行绘图/静态检查，不import、执行或训练上游模型；形状是显式profile下的推导。

在原型根目录中运行持久检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 checks/sequence_extended.py
```

正式生成后查看：[概览](../generated/layernorm_lstm_cell/figure1_overview.svg) · [模块层](../generated/layernorm_lstm_cell/figure2_modules.svg) · [算子层](../generated/layernorm_lstm_cell/figure3_detailed.svg) · [图库](../generated/layernorm_lstm_cell/index.html)。
