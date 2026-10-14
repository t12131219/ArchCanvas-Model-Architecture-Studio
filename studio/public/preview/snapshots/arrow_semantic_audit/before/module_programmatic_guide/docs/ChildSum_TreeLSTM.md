# Child-Sum TreeLSTM / per-child forgetting：源码、端口与程序化布局

选择直接被Awesome目录列举的dasguptar/treelstm.pytorch中的 `ChildSumTreeLSTM.node_forward`。静态示例in_dim=12、mem_dim=16，非叶节点有K=3个child；不画完整树遍历、词embedding或SimilarityTreeLSTM预测头。

目录依据：[固定Awesome-pytorch-list第419行](https://github.com/bharathgs/Awesome-pytorch-list/blob/06e9786eb64392cbe233d1a9ab7489256c0ac521/README.md#L419)。目录列举仓库；适配器进一步选择该仓库内明确的模块/源码子图。

实际源码冻结为 `dasguptar/treelstm.pytorch` 提交 `228a314add09fc7f39ea752aa7b1fcf756cfe277`。所有文件保留SHA256、Git blob摘要和LICENSE；[来源记录](../staging/sequence_source_manifest.json)与正式source_manifest合并后继续绑定相同字节。适配器：[module_adapters/childsum_treelstm.py](../module_adapters/childsum_treelstm.py)。

- [childsum-treelstm-sequence/treelstm/model.py](../sources/childsum-treelstm-sequence/treelstm/model.py)；符号：`ChildSumTreeLSTM.__init__`, `ChildSumTreeLSTM.forward`, `ChildSumTreeLSTM.node_forward`

## 每个图框为何对应这段源码

| 图框/稳定ID | 实际代码位置 | 对应理由与不能混淆的关系 |
|---|---|---|
| `tree.hsum / tree.iouh` | [第20行](../sources/childsum-treelstm-sequence/treelstm/model.py#L20)：`child_h_sum = torch.sum` | 先按dim0求hidden的和，保留[1,H]维度，再供共享节点门 |
| `tree.ioux / tree.iou_add` | [第22行](../sources/childsum-treelstm-sequence/treelstm/model.py#L22)：`iou = self.ioux(inputs)` | node input投影与child-sum投影相加；rank1向量结果广播成[1,3H] |
| `tree.split / i / o / u` | [第23行](../sources/childsum-treelstm-sequence/treelstm/model.py#L23)：`i, o, u = torch.split` | 真实顺序i,o,u，而不是普通sequence LSTM的i,f,g,o |
| `tree.fx / tree.fh` | [第16行](../sources/childsum-treelstm-sequence/treelstm/model.py#L16)：`self.fx = nn.Linear` | fx/fh独立实例且默认带bias；所有child行复用同一组fx/fh参数 |
| `tree.repeat / tree.f_add / tree.f` | [第28行](../sources/childsum-treelstm-sequence/treelstm/model.py#L28)：`self.fx(inputs).repeat(len(child_h), 1)` | 重复node input投影，逐child加对应的fh(child_h)再sigmoid |
| `tree.fc / tree.fsum / tree.cell` | [第32行](../sources/childsum-treelstm-sequence/treelstm/model.py#L32)：`c = torch.mul(i, u) + torch.sum` | 先f*每个child_c，再dim0求和；与i*u的新cell项相加 |
| `tree.hidden` | [第33行](../sources/childsum-treelstm-sequence/treelstm/model.py#L33)：`h = torch.mul(o, F.tanh(c))` | output gate读取更新后的cell |
| `tree.output` | [第34行](../sources/childsum-treelstm-sequence/treelstm/model.py#L34)：`return c, h` | 源码真实返回cell在前、hidden在后，不能换成习惯的(hy,cy) |
| `tree.x` | [第47行](../sources/childsum-treelstm-sequence/treelstm/model.py#L47)：`tree.state = self.node_forward(inputs[tree.idx]` | 实际caller按tree.idx取单个输入向量，递归与state读写在当前边界外 |

带颜色的容器是语义阶段与布局分组；只有明确指出真实类、Sequential或ModuleList实例时，才能把它当作源码模块实例。图中的group不会另建Python层；图元文字可以缩短，但IR中的source引用、参数身份和端口保持稳定。

## 形状、参数与依赖

child_h/child_c `[3,16]`；hidden和 `[1,16]` 经iouh为 `[1,48]`。实际caller的node input是 `[12]` 向量，ioux结果 `[48]` 和child-sum结果广播相加为 `[1,48]`，split成i/o/u各 `[1,16]`。fx `[16]` 重复为 `[3,16]`；fh逐行应用产生 `[3,16]`；K个forget对应K个child，而非K组权重。fc `[3,16]` 求和为 `[1,16]`，c/h均 `[1,16]`。ioux/iouh/fx/fh是四个独立nn.Linear，每个各有weight/bias，共八个参数张量；repeat不是参数实例复制。

## 三个视图怎样分配位置与箭头

节点门与逐child遗忘用蓝/橙两个容器并列。节点门内部child_h求和→iouh，与ioux支路汇合，再split并列i/o/u。forget容器内部fx/fh并列，fx重复后与fh汇合，sigmoid→f*child_c→sum。上方i*u与retained child sum分别连接cell Add的真实端口；o沿旁路进入h。顶端返回框有cell/hidden两个命名端口，表示真实(c,h)。

所有层级采用同一语义IR，源码调用顺序与数据依赖决定节点的先后，`graph.ranks`只分配底→顶的依赖层，不会创建隐式tensor边。每个branch容器内部继续自底向上；同一rank的节点并列、内容测量决定宽高，统一留白通道容纳正交连线。真实多输入算子通过不同命名端口接收依赖；旁路可跨多rank而不改来源。容器折叠时路由投影到最近可见祖先，不能把folded节点误认为实现缺失。

使用Transformer原型的字体、蓝/橙阶段对比、粉色输入、紫色Linear/输出、黄色汇流/归一化、绿色门函数和Softmax。颜色表达操作角色；相同颜色不证明共享权重。并列rank不自动表示fork/tuple或Add；这些关系必须由`extra_edges`和端口另行声明。连线保留终端留白，避免沿边框或穿过无关叶节点。箭头标签采用底部术语说明，减少文字穿边框。

## 范围与可复现验证

本图选择node_forward的非叶K3配置，未画recursive forward。原caller的叶节点分支提供一行零child状态，不是这里虚构的空children数组；SimilarityTreeLSTM还包含embedding与相似度计算，这些不属于此模块输出。

[checks/sequence_extended.py](../checks/sequence_extended.py)直接解析冻结源码AST，核对关键算子表达式、配置、参数与真实依赖，并注入错误producer/端口与错误语义字段。取证与图像验证包括源码hash/symbol证据、IR检查、框包含、节点间距、正交箭头、终端长度、SVG实际对象和PNG。只运行绘图/静态检查，不import、执行或训练上游模型；形状是显式profile下的推导。

在原型根目录中运行持久检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 checks/sequence_extended.py
```

正式生成后查看：[概览](../generated/childsum_treelstm/figure1_overview.svg) · [模块层](../generated/childsum_treelstm/figure2_modules.svg) · [算子层](../generated/childsum_treelstm/figure3_detailed.svg) · [图库](../generated/childsum_treelstm/index.html)。
