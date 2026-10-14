# FRN + learned TLU：二阶统计、广播参数与保留输入

本例直接绘制 `FilterResponseNormalization` 类，选定 `num_features=192, eps=1e-6`，示例输入 `[B,192,32,32]`。来源是 rasbt 的 FRN Notebook；代码单元只被提取和 AST 解析，没有执行。Notebook 后面重新定义了使用 BatchNorm 的 `NiN`，因此不能把最终 `NiN` 绑定当成 FRN 网络。完整版本、哈希和 Notebook 单元映射见 [来源清单](../source_manifest.json)。

[概览](../generated/frn_tlu/figure1_overview.svg) · [内部模块](../generated/frn_tlu/figure2_modules.svg) · [算子详细](../generated/frn_tlu/figure3_detailed.svg) · [逐节点源码对应](../generated/frn_tlu/source_map.md) · [适配器](../module_adapters/frn_tlu.py)

## 源码为什么对应这些图元

| 源码 | 图元与真实含义 | 不能替换成的常见画法 |
| --- | --- | --- |
| `x.pow(2)` → `mean(...,(2,3),keepdims=True)` | 平方 → H,W 均值，得到 `[B,C,1,1]` 的未中心化二阶矩 | BatchNorm 的批统计、LayerNorm、减均值 |
| `rsqrt(nu2 + abs(eps))` | 加绝对值 epsilon → 倒平方根 | 标准差、可学习 epsilon |
| `x * rsqrt(...)` | 原始 x 与统计结果相乘；左侧保留输入线必须来自归一化模块的输入 | 将已经平方的 x 直接送到最终乘法 |
| `gamma * x_hat + beta` | 独立的 gamma 乘法和 beta 加法，参数按通道广播 | 混合通道的 Linear 层 |
| `torch.max(y, self.tau)` | 两个张量逐元素取最大，learned TLU | MaxPool、最大值规约、固定阈值 ReLU |
| 三个 `nn.Parameter(...normal_())` | gamma/beta/tau 独立参数，形状 `[1,C,1,1]`，全都正态初始化 | 按论文惯例直接写 gamma=1、beta=tau=0 |
| `self.eps = torch.Tensor([eps])`；forward 中 `.to(tau.device)` | 普通 Tensor 属性，常量侧线进入加法 | Parameter 或注册 buffer |

没有批维或通道维规约，也没有 running mean/variance；训练与推理使用同一公式。参数面板的容器仅表示归属，gamma、beta、tau、eps 之间没有顺序运算线。四条侧线分别落到各自的实际 operand；相同参数颜色不表示参数共享。

## 排布如何分配

主链 `输入 → FRN → 输出` 自底向上。内部两段是顺序关系：先 response normalization，再 affine + threshold。详细图继续展开每段算子；其高度由字体换行、张量形状和固定间距测量产生，而非逐节点手写坐标。

保留 x 的线使用模块内部预留侧槽，提前横向离开中心主链，再从 Multiply 左侧接入。参数面板位于旁边，图框的 containment 不制造 tensor chain。参数端点与常量端点在 IR 中有不同角色，连线投影随折叠粒度改变，完整身份保留在 `semantic_ir.json`。源码没有这些坐标或颜色；布局器依据语义层次计算图框、端口、避障路径和至少 18px 的箭头终段。

这增加的是“逐实例逐通道空间二阶矩 + learned threshold”复合模块覆盖。原案例已有 Norm 图元和广播乘法，不能据此说 FRN 已被展开；新的统计维度、参数身份和 TLU 实际依赖才构成本例的新增适配。

## 可复用界限

可复用链、保留输入、参数面板与广播侧线图元；换 FRN 实现仍须重查统计轴、epsilon 存储、初始化和阈值公式。`validate_ir()` 检查这些关键事实及端点，无法取代对新源码的审阅，也没有验证数值运行。
