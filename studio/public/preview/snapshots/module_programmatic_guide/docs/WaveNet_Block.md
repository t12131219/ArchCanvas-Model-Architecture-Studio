# WaveNet / gated residual and skip iteration：源码、端口与程序化布局

本例选 `WaveNetModel.wavenet` 循环的 i=1 迭代，使用真实 `wavenet_dilate` 路径，dilation=2、init_dilation=1、kernel_size=2，默认bias=False。它不是独立源码类，也不是完整WaveNet：输出是本次迭代更新的x/skip两个边界变量。

目录依据：[固定Awesome-pytorch-list第41行](https://github.com/bharathgs/Awesome-pytorch-list/blob/06e9786eb64392cbe233d1a9ab7489256c0ac521/README.md#L41)。目录列举仓库；适配器进一步选择该仓库内明确的模块/源码子图。

实际源码冻结为 `vincentherrmann/pytorch-wavenet` 提交 `26ba28989edcf8688f6216057aafda07601ff07e`。所有文件保留SHA256、Git blob摘要和LICENSE；[来源记录](../staging/sequence_source_manifest.json)与正式source_manifest合并后继续绑定相同字节。适配器：[module_adapters/wavenet_block.py](../module_adapters/wavenet_block.py)。

- [pytorch-wavenet-sequence/wavenet_model.py](../sources/pytorch-wavenet-sequence/wavenet_model.py)；符号：`WaveNetModel.__init__`, `WaveNetModel.wavenet_dilate`, `WaveNetModel.wavenet`
- [pytorch-wavenet-sequence/wavenet_modules.py](../sources/pytorch-wavenet-sequence/wavenet_modules.py)；符号：`dilate`

## 每个图框为何对应这段源码

| 图框/稳定ID | 实际代码位置 | 对应理由与不能混淆的关系 |
|---|---|---|
| `wave.dilate` | [第144行](../sources/pytorch-wavenet-sequence/wavenet_model.py#L144)：`residual = dilation_func` | 调用真实dilate helper，按相位permute/view，不是Conv1d(dilation=2) |
| `wave.filter / wave.gate` | [第147行](../sources/pytorch-wavenet-sequence/wavenet_model.py#L147)：`filter = self.filter_convs` | 同一个phase-folded residual进入两个独立Conv2，分别Tanh和Sigmoid |
| `wave.product` | [第151行](../sources/pytorch-wavenet-sequence/wavenet_model.py#L151)：`x = filter * gate` | 逐元素乘法，不是Add/concat |
| `wave.skip / wave.undilate` | [第156行](../sources/pytorch-wavenet-sequence/wavenet_model.py#L156)：`s = dilate(x, 1` | 把相位折回时间轴后进入skip_convs[1] |
| `wave.skip_crop / skip_add` | [第159行](../sources/pytorch-wavenet-sequence/wavenet_model.py#L159)：`skip = skip[:, :, -s.size(2):]` | 对已有tensor skip保留尾段，再与s相加；只读取s的长度决定crop |
| `wave.res_conv / res_crop / res_add` | [第165行](../sources/pytorch-wavenet-sequence/wavenet_model.py#L165)：`x = x + residual` | residual_convs[1]结果加左裁剪的原phase residual |
| `wave.output_x / output_skip` | [第162行](../sources/pytorch-wavenet-sequence/wavenet_model.py#L162)：`skip = s + skip` | 显式标记loop boundary，不伪造函数tuple return |

带颜色的容器是语义阶段与布局分组；只有明确指出真实类、Sequential或ModuleList实例时，才能把它当作源码模块实例。图中的group不会另建Python层；图元文字可以缩短，但IR中的source引用、参数身份和端口保持稳定。

## 形状、参数与依赖

选定上次x `[1,32,18]`，18可被2整除，因此无补零：dilate后 `[2,32,9]`，普通valid Conv2后 `[2,32,8]`。skip的undilate得到 `[1,32,16]`，skip Conv1产生 `[1,256,16]`；上次skip `[1,256,18]` 取最后16位置。residual原值 `[2,32,9]` 从左裁掉1个位置，和residual Conv1结果一起得到 `[2,32,8]`。这里第一维按实现承载dilation phase，图不宣称它是任意batch。四个ModuleList index1各有独立weight，均无bias。

## 三个视图怎样分配位置与箭头

filter/gate双列，乘积在上一层汇合。skip的undilate+Conv1、residual Conv1、residual crop、previous skip crop在同一依赖层并列；分别汇到skip Add与residual Add。s→skip crop是shape_dependency虚线，不传递s像素值。两路顶部结果按来源分别到输出框。

所有层级采用同一语义IR，源码调用顺序与数据依赖决定节点的先后，`graph.ranks`只分配底→顶的依赖层，不会创建隐式tensor边。每个branch容器内部继续自底向上；同一rank的节点并列、内容测量决定宽高，统一留白通道容纳正交连线。真实多输入算子通过不同命名端口接收依赖；旁路可跨多rank而不改来源。容器折叠时路由投影到最近可见祖先，不能把folded节点误认为实现缺失。

使用Transformer原型的字体、蓝/橙阶段对比、粉色输入、紫色Linear/输出、黄色汇流/归一化、绿色门函数和Softmax。颜色表达操作角色；相同颜色不证明共享权重。并列rank不自动表示fork/tuple或Add；这些关系必须由`extra_edges`和端口另行声明。连线保留终端留白，避免沿边框或穿过无关叶节点。箭头标签采用底部术语说明，减少文字穿边框。

## 范围与可复现验证

start_conv、输出端两个Conv、整个层/块循环、fast-generation queue和try/except的zero初始化路径均不在当前图范围。dilate helper是有源码的复合调用；与PyTorch内部Conv核边界不同。

[checks/sequence_extended.py](../checks/sequence_extended.py)直接解析冻结源码AST，核对关键算子表达式、配置、参数与真实依赖，并注入错误producer/端口与错误语义字段。取证与图像验证包括源码hash/symbol证据、IR检查、框包含、节点间距、正交箭头、终端长度、SVG实际对象和PNG。只运行绘图/静态检查，不import、执行或训练上游模型；形状是显式profile下的推导。

在原型根目录中运行持久检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 checks/sequence_extended.py
```

正式生成后查看：[概览](../generated/wavenet_block/figure1_overview.svg) · [模块层](../generated/wavenet_block/figure2_modules.svg) · [算子层](../generated/wavenet_block/figure3_detailed.svg) · [图库](../generated/wavenet_block/index.html)。
