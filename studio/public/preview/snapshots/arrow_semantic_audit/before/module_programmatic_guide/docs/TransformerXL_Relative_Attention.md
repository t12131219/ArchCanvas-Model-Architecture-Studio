# Transformer-XL relative attention：源码、端口与程序化布局

选 `RelPartialLearnableMultiHeadAttn(n_head=2,d_model=16,d_head=8,dropout=.1,dropatt=.1,pre_lnorm=False)`，明确mems存在，current length3、memory length4、relative length7，三维mask含屏蔽项，eval。整个模型的memory更新不在此模块范围。

目录依据：[固定Awesome-pytorch-list第659行](https://github.com/bharathgs/Awesome-pytorch-list/blob/06e9786eb64392cbe233d1a9ab7489256c0ac521/README.md#L659)。目录列举仓库；适配器进一步选择该仓库内明确的模块/源码子图。

实际源码冻结为 `kimiyoung/transformer-xl` 提交 `44781ed21dbaec88b280f74d9ae2877f52b492a5`。所有文件保留SHA256、Git blob摘要和LICENSE；[来源记录](../staging/sequence_source_manifest.json)与正式source_manifest合并后继续绑定相同字节。适配器：[module_adapters/transformer_xl_relative.py](../module_adapters/transformer_xl_relative.py)。

- [transformer-xl-relative/pytorch/mem_transformer.py](../sources/transformer-xl-relative/pytorch/mem_transformer.py)；符号：`RelMultiHeadAttn.__init__`, `RelPartialLearnableMultiHeadAttn.__init__`, `RelMultiHeadAttn._rel_shift`, `RelPartialLearnableMultiHeadAttn.forward`

## 每个图框为何对应这段源码

| 图框/稳定ID | 实际代码位置 | 对应理由与不能混淆的关系 |
|---|---|---|
| `txl.cat / qkv / split` | [第222行](../sources/transformer-xl-relative/pytorch/mem_transformer.py#L222)：`cat = torch.cat([mems, w], 0)` | memory在前/current在后，联合QKV投影；K/V保留所有7个位置 |
| `txl.q / k / v` | [第230行](../sources/transformer-xl-relative/pytorch/mem_transformer.py#L230)：`w_head_q = w_head_q[-qlen:]` | Q只取尾部current3；K/V含memory而不是只取current |
| `txl.r / rw / rr` | [第249行](../sources/transformer-xl-relative/pytorch/mem_transformer.py#L249)：`rw_head_q = w_head_q + r_w_bias` | relative encodings经r_net；内容bias与relative bias是两个不同caller参数 |
| `txl.ac / bd` | [第250行](../sources/transformer-xl-relative/pytorch/mem_transformer.py#L250)：`AC = torch.einsum` | AC=(Q+r_w_bias)K；BD=(Q+r_r_bias)R，einsum方程不同 |
| `txl.shift` | [第254行](../sources/transformer-xl-relative/pytorch/mem_transformer.py#L254)：`BD = self._rel_shift(BD)` | 展开真实helper：zero column、cat、view、slice、view_as；zero_triu默认False |
| `txl.score / scale` | [第257行](../sources/transformer-xl-relative/pytorch/mem_transformer.py#L257)：`attn_score = AC + BD` | 两个分数相加后乘1/sqrt(d_head)，不是在token上加位置embedding |
| `txl.mask / softmax / dropatt` | [第270行](../sources/transformer-xl-relative/pytorch/mem_transformer.py#L270)：`attn_prob = F.softmax(attn_score, dim=1)` | 所选3D mask向heads广播，float masked_fill再type_as；key time axis1归一化 |
| `txl.aggregate / tail` | [第274行](../sources/transformer-xl-relative/pytorch/mem_transformer.py#L274)：`attn_vec = torch.einsum` | prob乘含memory的V，合并heads、o_net、output Dropout |
| `txl.residual / norm` | [第289行](../sources/transformer-xl-relative/pytorch/mem_transformer.py#L289)：`output = self.layer_norm(w + attn_out)` | 残差仅original current w；选post-norm，不拿cat memory作残差 |
| `txl.output` | [第291行](../sources/transformer-xl-relative/pytorch/mem_transformer.py#L291)：`return output` | 只返回current输出，不返回weights或更新memory |

带颜色的容器是语义阶段与布局分组；只有明确指出真实类、Sequential或ModuleList实例时，才能把它当作源码模块实例。图中的group不会另建Python层；图元文字可以缩短，但IR中的source引用、参数身份和端口保持稳定。

## 形状、参数与依赖

联合QKV将 `[7,B,16]` 映为 `[7,B,48]`；Q `[3,B,2,8]`，K/V `[7,B,2,8]`。r `[7,16]` 经r_net和view得到 `[7,2,8]`，不含batch。两个score为 `[3,7,B,2]`。relative shift的zero `[3,1,B,2]` 按BD shape/device/dtype生成，cat `[3,8,B,2]`，view `[8,3,B,2]` 后切掉第一行并view_as回原score形状。r_w_bias/r_r_bias均 `[2,8]`，由caller提供；模块自己的qkv_net/r_net/o_net均无bias，layer_norm有独立weight/bias。

## 三个视图怎样分配位置与箭头

底部current/memory/relative encodings/两个bias的视觉包/mask并列。memory concat→QKV→三分支视图；两种Q+bias score并列，BD经过局部expanded shift后与AC汇流。weight aggregation之后直上投影、current residual、post norm。memory旁路与current residual指向不同端口，不能靠视觉近邻混淆。

所有层级采用同一语义IR，源码调用顺序与数据依赖决定节点的先后，`graph.ranks`只分配底→顶的依赖层，不会创建隐式tensor边。每个branch容器内部继续自底向上；同一rank的节点并列、内容测量决定宽高，统一留白通道容纳正交连线。真实多输入算子通过不同命名端口接收依赖；旁路可跨多rank而不改来源。容器折叠时路由投影到最近可见祖先，不能把folded节点误认为实现缺失。

使用Transformer原型的字体、蓝/橙阶段对比、粉色输入、紫色Linear/输出、黄色汇流/归一化、绿色门函数和Softmax。颜色表达操作角色；相同颜色不证明共享权重。并列rank不自动表示fork/tuple或Add；这些关系必须由`extra_edges`和端口另行声明。连线保留终端留白，避免沿边框或穿过无关叶节点。箭头标签采用底部术语说明，减少文字穿边框。

## 范围与可复现验证

r输入的编码生成、上层r_w/r_r参数注册、memory创建/截断/detach和decoder FFN均在caller边界之外。nn.LayerNorm内部是显式library opaque边界，源码未传eps；图不虚构执行环境的默认数值结果。

[checks/sequence_extended.py](../checks/sequence_extended.py)直接解析冻结源码AST，核对关键算子表达式、配置、参数与真实依赖，并注入错误producer/端口与错误语义字段。取证与图像验证包括源码hash/symbol证据、IR检查、框包含、节点间距、正交箭头、终端长度、SVG实际对象和PNG。只运行绘图/静态检查，不import、执行或训练上游模型；形状是显式profile下的推导。

在原型根目录中运行持久检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 checks/sequence_extended.py
```

正式生成后查看：[概览](../generated/transformer_xl_relative/figure1_overview.svg) · [模块层](../generated/transformer_xl_relative/figure2_modules.svg) · [算子层](../generated/transformer_xl_relative/figure3_detailed.svg) · [图库](../generated/transformer_xl_relative/index.html)。
