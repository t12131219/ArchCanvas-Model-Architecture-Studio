# LSTMCell：从显式四门源码到时间展开图

本例对应官方 `pytorch/pytorch` 的 `benchmarks/fastrnns/custom_lstms.py`，冻结版本为 `v2.5.1`，提交为 `a8d6afb511a69687bbb2b7e88a3cf67917e1697e`。选择其中普通 `LSTMCell` 和单向 `LSTMLayer`，展示输入门、遗忘门、候选状态、输出门，以及两条真正的递推状态。该文件是官方仓库中的自定义 TorchScript LSTM 参考/性能测试实现；这里不声称展开了原生 `nn.LSTM` 的 fused/backend 内核。

[源码副本](../sources/pytorch-lstmcell-v2.5.1/benchmarks/fastrnns/custom_lstms.py) · [官方固定版本源码](https://github.com/pytorch/pytorch/blob/a8d6afb511a69687bbb2b7e88a3cf67917e1697e/benchmarks/fastrnns/custom_lstms.py) · [适配器](../adapters/lstmcell.py) · [来源记录](../source_manifest.json) · [三粒度图像](../generated/lstmcell/index.html)

绘图只读取源码文本和 AST，未导入 `torch` 或上游模型，也不执行 TorchScript 编译、推理或训练。原有 [Packed LSTM 分类例](LSTM.md) 保留为另一例：它展示 token embedding、打包和分类头；本例展示有明确源码依据的 cell 内部和时间递推，两个入口不能混为同一模型。

## 所选配置与模型边界

本例按 `LSTMLayer(LSTMCell, input_size=8, hidden_size=16)` 的构造契约绘图。`I=8`、`H=16` 是本例选择的静态配置，不是上游类写死的常量。图中展开 `T=3` 个时间步，与参考图的三个重复单元对应；源码的循环长度实际取自输入，不固定为 3。`B` 保持符号化。

完整输入为 `[T,B,8]`，初始状态由调用方明确提供：`h_init:[B,16]`、`c_init:[B,16]`。`LSTMLayer.forward(input,state)` 没有默认 `state`，因此不能凭 `nn.LSTM` 的习惯补成“默认全零”。三个 cell 显示的是同一个 `self.cell` 的三次调用，没有新建三套权重。输出为 `stack(outputs):[T,B,16]` 及末状态 `(h_final,c_final)`。

范围内没有 token embedding、packing、分类头、Softmax、Dropout、双向分支或多层堆叠。源文件中其他类虽然包含 LayerNorm、reverse 或 stacked 变体，但它们不属于当前选定入口。

## 每个图例为什么这样对应

| 图中结构 | 源码依据 | 对应理由 |
| --- | --- | --- |
| 单个时间步输入 `x_t` | `LSTMLayer.forward` 的 `input.unbind(0)` 与 `inputs[i]`，行 230/233 | 沿时间轴 0 拆分，每次调用得到 `[B,I]` |
| 上一步 hidden `h_prev` | `LSTMCell.forward` 的 `hx,cx=state`，行 136 | 只有 hx 参与 hidden-to-gates 仿射计算 |
| 上一步 cell `c_prev` | 同一解包的 cx，以及行 150 的 `forgetgate * cx` | cx 进入遗忘乘法，不进入四门的仿射输入；没有 peephole |
| Input-to-gates 矩阵乘法与输入 bias | `torch.mm(input,self.weight_ih.t())` 与 `bias_ih`，行 138/139 | 一次矩阵乘法产生 `[B,4H]`，再显式加输入 bias |
| Hidden-to-gates 矩阵乘法 | `torch.mm(hx,self.weight_hh.t())`，行 140 | 读取上一步 hidden；它的结果加到 input projection 与输入 bias 的和上 |
| Hidden bias 与最终 gate logits | 行 137–142 的加法表达式，最后 `+self.bias_hh` | 保留源码左结合顺序：先输入矩阵乘法，再输入 bias，再 hidden 矩阵乘法，最后 hidden bias；不是 concat |
| 四路拆分 `i/f/g/o` | `ingate,forgetgate,cellgate,outgate=gates.chunk(4,1)`，行 143 | 沿特征轴分为四份 `[B,H]`，字段顺序由源码明确决定 |
| 输入门 i、遗忘门 f、输出门 o | 行 145/146/148 的三个 `torch.sigmoid` | 每个门的值用来逐元素调制另一张量 |
| 候选状态 g | 行 147 的 `torch.tanh(cellgate)` | 它提供待写入内容，激活是 tanh，不能画成第四个 Sigmoid |
| 遗忘乘法 | `forgetgate * cx`，行 150 | f 与旧 cell 逐元素相乘，保留/抑制历史状态 |
| 写入乘法 | `ingate * cellgate`，行 150 | i 与候选 g 逐元素相乘，得到新写入量 |
| cell 更新 Add | `(forgetgate * cx)+(ingate * cellgate)`，行 150 | 两个乘法结果通过显式 Add 得到 `cy=c_t`，并列容器不能隐含求和 |
| cell 输出 Tanh | `torch.tanh(cy)`，行 151 | 它与候选 g 的 Tanh 是两次不同调用，读取不同生产者 |
| hidden 更新乘法 | `outgate * torch.tanh(cy)`，行 151 | o 调制已经更新的 cell，得到 `hy=h_t` |
| 输出与下一状态 | `return hy,(hy,cy)`，行 153 | 本步输出 h_t 与下一状态的 hidden 是同一 hy 的两个引用；c_t 另走 cell 状态线 |
| 时间状态传递 | `out,state=self.cell(inputs[i],state)`，行 233 | 第 t 步返回的 `(h_t,c_t)` 成为第 t+1 步的 state，不能把两者合为一条未分字段的线 |
| 序列收集与末状态 | `outputs += [out]`；`return torch.stack(outputs),state`，行 234/235 | 收集每步输出 h，末 state 只取最后一步；stack 没有沿特征轴拼接状态 |

公式与图中运算节点一一对应：

```text
z_t = x_t W_ih^T + b_ih + h_prev W_hh^T + b_hh   [B,4H]
(z_i,z_f,z_g,z_o) = chunk(z_t,4,dim=1)
i_t = sigmoid(z_i)   f_t = sigmoid(z_f)
g_t = tanh(z_g)      o_t = sigmoid(z_o)
c_t = f_t ⊙ c_prev + i_t ⊙ g_t
h_t = o_t ⊙ tanh(c_t)
return h_t,(h_t,c_t)
```

`⊙` 表示逐元素乘法，不是矩阵乘法或点积。源码先后执行门激活，但四路没有彼此的数值依赖，因此图中按同一 producer 的不同结果并列展示；这不表示代码实际并发执行。详细图的 fused affine 容器有两个 MatMul 和三个 Add 节点，直接保留源码左结合顺序：`x_mm→加b_ih→加h_mm→加b_hh`。其中 h_mm 作为独立操作数侧向进入合成 Add；图没有把表达式重排为先计算两个各含 bias 的分支。

## 与教材参考图的相同点和必要修正

参考图的两个横向状态通道和中心展开 cell 与本例一致：cell 状态持续传递，hidden 同时作为下一步门输入及本步输出。内部采用输入、遗忘、候选、输出四路相互作用，其中有三个 Sigmoid 和两个位于不同位置的 Tanh。

教材图常把 `x_t` 与 `h_prev` 合成一路后分别送入四个“门层”。当前源码没有 `torch.cat([x_t,h_prev])`，也没有四个独立 `nn.Linear` 实例；它先用两份矩阵计算一份 `4H` gate logits，再 `chunk`。图中因此保留两个仿射输入和真实拆分，不能为模仿参考图而添加显式 Concat。四路逻辑门的参数身份来自同一矩阵的不同 **行切片**，而不是四个时间步或四个新模块。

对于本例 H=16，门的行切片依源码顺序为 `i:[0:16]`、`f:[16:32]`、`g:[32:48]`、`o:[48:64]`。`weight_ih:[64,8]`、`weight_hh:[64,16]`、`bias_ih:[64]`、`bias_hh:[64]` 共 1,664 个参数。参数初始化全部使用 `torch.randn`，不能将常见的“forget bias 初始化为 1”添加为此实现的事实。

参考图为方便描画会把 forget 分支放在最左；本例的字段绑定始终以源码 `i/f/g/o` 为准，视觉排列不能改变哪个 slice 对应哪个门。c 通道仅进入遗忘乘法、返回状态和 Tanh(c)，不能用一条经过全部门的小循环暗示不存在的 peephole。

## 三种粒度与程序化布局

概览将三个时间步 cell 折叠，横向时间顺序由 `t=0/1/2` 和递推依赖决定，分别显示 h 与 c 状态线、每步 x 输入和 h 输出。三个容器都记录同一个 `cell` 参数作用域；同色仅表示同类结构，参数共享需要作用域证据。

模块视图展开中间 cell，显示 fused affine 容器、Chunk、四门容器、cell 更新容器、hidden 更新容器及真实返回；相邻 cell 保持折叠。详细视图再展开 affine 中的两个 MatMul 和三个 Add、四路门激活、遗忘/写入两个乘法、cell Add、Tanh(c) 和 hidden 乘法。三个视图使用同一语义 IR，折叠是显示投影，不删除门或新增时间参数。

时间步整体采用左到右排列，以对应参考图的递推含义；**每个 cell 内部依旧自底向上**。x/h 输入在下层，仿射与拆分在其上，四门按共同层级并列，再上行到 cell/hidden 更新。门数量、输入生产者和依赖来自源码；列宽、行高、间距、绕线通道属于绘图规则。不同颜色区分 Linear/仿射、Sigmoid、Tanh、逐元素乘法和 Add，字体、深边框与角色配色沿用 Transformer 原型。

本例采用显式 `graph` 容器：`ranks` 按底到顶分配每个直接子节点；同层从左到右排列，但不由相邻位置推导数据边。全部 88 条真实边由 `extra_edges` 单独绑定。根容器的 `align_x` 把三个 x_t 分别对齐各自 Cell 的中心；内部 rank 间距 52px、列间距 48px，容器大小由实际子框递归测量。起止端口保留至少 24px 的法向直段，长线平行于框边时至少留 8px，避免贴框走线；这些数值属于显示策略。

各门的 SVG 悬停信息及 `source_map.md` 标明 fused 参数行切片；IR 的 `kind='activation'`、`kind='arithmetic'` 和具体 `activation / operation` 字段表达数学类型。绿色 Sigmoid 与黄色 Multiply/Add 另由 `visual_roles` 指定，借用颜色不会将算子误标为 Softmax 或 Normalization。

线路绑定具体的输入或结果端口：h 状态必须进入下步 hidden 仿射，c 状态必须进入下步遗忘乘法，x 不能沿着 cell 状态线传递。h 输出与下步 hidden 用同一生产者分支；末状态和序列 Stack 也保留各自字段。避免边框重叠和提前转弯属于几何约束，不能靠移动终点来改变源码依赖。

## 后续复用范围

本例补充的是“显式门级递推图”与带参数身份的时间展开，而不是将所有 RNN 自动替换为教材 LSTM。更换源码后需要核对 gate 顺序、激活、bias、状态更新式、返回结构和实例复用；peephole、projection、LayerNorm 或 GRU 各自有不同结构。`nn.LSTM` 的 opaque 模块也不能仅因名称一致就绑定到这个 benchmark 实现。

文件哈希、AST 片段、适配器规则和几何检查共同支持图像追溯；静态形状和参数数量来自所选配置的推导，不是数值运行报告。上游模型仍没有在绘图过程中执行。
