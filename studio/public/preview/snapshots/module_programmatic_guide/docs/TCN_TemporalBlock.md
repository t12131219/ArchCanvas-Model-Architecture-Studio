# TCN TemporalBlock / causal residual：源码、端口与程序化布局

只绘制 `TemporalBlock(n_inputs=16,n_outputs=32,kernel_size=3,stride=1,dilation=2,padding=4,dropout=.2)`。示例序列长度16、eval；不画整个TemporalConvNet或任务分类器。

目录依据：[固定Awesome-pytorch-list第581行](https://github.com/bharathgs/Awesome-pytorch-list/blob/06e9786eb64392cbe233d1a9ab7489256c0ac521/README.md#L581)。目录列举仓库；适配器进一步选择该仓库内明确的模块/源码子图。

实际源码冻结为 `locuslab/TCN` 提交 `2f8c2b817050206397458dfd1f5a25ce8a32fe65`。所有文件保留SHA256、Git blob摘要和LICENSE；[来源记录](../staging/sequence_source_manifest.json)与正式source_manifest合并后继续绑定相同字节。适配器：[module_adapters/tcn_block.py](../module_adapters/tcn_block.py)。

- [tcn-sequence/TCN/tcn.py](../sources/tcn-sequence/TCN/tcn.py)；符号：`Chomp1d.__init__`, `Chomp1d.forward`, `TemporalBlock.__init__`, `TemporalBlock.init_weights`, `TemporalBlock.forward`

## 每个图框为何对应这段源码

| 图框/稳定ID | 实际代码位置 | 对应理由与不能混淆的关系 |
|---|---|---|
| `tcn.stage1 / stage2` | [第30行](../sources/tcn-sequence/TCN/tcn.py#L30)：`self.net = nn.Sequential` | 两个Conv→Chomp→ReLU→Dropout阶段顺序与真实Sequential一致 |
| `tcn.*.conv` | [第18行](../sources/tcn-sequence/TCN/tcn.py#L18)：`self.conv1 = weight_norm` | 两个独立legacy weight_norm Conv1d；真实dilation2、padding4、stride1 |
| `tcn.*.chomp` | [第12行](../sources/tcn-sequence/TCN/tcn.py#L12)：`return x[:, :, :-self.chomp_size].contiguous()` | 卷积后右裁4，调用contiguous；不是左crop或输入crop |
| `tcn.projection` | [第32行](../sources/tcn-sequence/TCN/tcn.py#L32)：`self.downsample = nn.Conv1d` | 16/32通道不同，明确选择learned1x1残差projection |
| `tcn.add / relu` | [第45行](../sources/tcn-sequence/TCN/tcn.py#L45)：`return self.relu(out + res)` | main+residual之后只有final ReLU |
| `TemporalConvNet配置关系` | [第54行](../sources/tcn-sequence/TCN/tcn.py#L54)：`dilation_size = 2 ** i` | 合法example的padding=(k-1)*dilation=4；不宣称整网唯一shape |

带颜色的容器是语义阶段与布局分组；只有明确指出真实类、Sequential或ModuleList实例时，才能把它当作源码模块实例。图中的group不会另建Python层；图元文字可以缩短，但IR中的source引用、参数身份和端口保持稳定。

## 形状、参数与依赖

每次Conv1d把L16扩为L20：floor((16+2*4-2*(3-1)-1)/1)+1=20；Chomp右4恢复16，去除将来位置对应的padding。Conv1/2的独立权重重参数化保留weight_g、weight_v和bias；legacy weight_norm来自库，不虚构内部kernel。downsample有自己的weight/bias，16→32、kernel1。两次Dropout处于eval，保留真实node但值保持。

## 三个视图怎样分配位置与箭头

主支路容器与learned shortcut并列；主支路内部两个stage连续自底向上，各stage中Conv/Chomp/ReLU/Dropout连续。shortcut跨主支路高度上升到Add residual端口，主支路到main端口，Add之后上升到final ReLU再输出。

所有层级采用同一语义IR，源码调用顺序与数据依赖决定节点的先后，`graph.ranks`只分配底→顶的依赖层，不会创建隐式tensor边。每个branch容器内部继续自底向上；同一rank的节点并列、内容测量决定宽高，统一留白通道容纳正交连线。真实多输入算子通过不同命名端口接收依赖；旁路可跨多rank而不改来源。容器折叠时路由投影到最近可见祖先，不能把folded节点误认为实现缺失。

使用Transformer原型的字体、蓝/橙阶段对比、粉色输入、紫色Linear/输出、黄色汇流/归一化、绿色门函数和Softmax。颜色表达操作角色；相同颜色不证明共享权重。并列rank不自动表示fork/tuple或Add；这些关系必须由`extra_edges`和端口另行声明。连线保留终端留白，避免沿边框或穿过无关叶节点。箭头标签采用底部术语说明，减少文字穿边框。

## 范围与可复现验证

通道相等时源码shortcut是identity，但本例明确选择projection分支。dilation是实际Conv kwarg，与WaveNet的phase-fold helper不同；全TCN的layer stack、数据/训练和task head不在scope。

[checks/sequence_extended.py](../checks/sequence_extended.py)直接解析冻结源码AST，核对关键算子表达式、配置、参数与真实依赖，并注入错误producer/端口与错误语义字段。取证与图像验证包括源码hash/symbol证据、IR检查、框包含、节点间距、正交箭头、终端长度、SVG实际对象和PNG。只运行绘图/静态检查，不import、执行或训练上游模型；形状是显式profile下的推导。

在原型根目录中运行持久检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 checks/sequence_extended.py
```

正式生成后查看：[概览](../generated/tcn_block/figure1_overview.svg) · [模块层](../generated/tcn_block/figure2_modules.svg) · [算子层](../generated/tcn_block/figure3_detailed.svg) · [图库](../generated/tcn_block/index.html)。
