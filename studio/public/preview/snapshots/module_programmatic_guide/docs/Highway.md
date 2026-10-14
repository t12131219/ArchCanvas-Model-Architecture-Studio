# Highway：共享输入、互补门与 learned carry

本例只画 `Highway(size=16,num_layers=2,f=F.relu)` 模块。`size`、层数和 `f=F.relu` 是显式选择的例子配置；上游接受调用方提供的 `f`，源码没有固定成 ReLU。来源为 `analvikingur/pytorch_Highway`，版本和哈希见 [来源清单](../source_manifest.json)。

[概览](../generated/highway/figure1_overview.svg) · [内部模块](../generated/highway/figure2_modules.svg) · [算子详细](../generated/highway/figure3_detailed.svg) · [逐节点源码对应](../generated/highway/source_map.md) · [适配器](../module_adapters/highway.py)

## 源码到图框、分支与端口

| 源码结构 | 图中对应 | 对应理由 |
| --- | --- | --- |
| `gate`、`nonlinear`、`linear` 三个 `ModuleList` | 每层三条并列分支，分别持有独立的 Linear | 三者读同一层 x；没有分支之间的先后调用依赖 |
| `sigmoid(self.gate[layer](x))` | Linear → Sigmoid，得到 g | sigmoid 的输入来自 gate 权重，不能把 g 画成外部标量 |
| `f(self.nonlinear[layer](x))` | Linear → 选定的 f=ReLU | 非线性来自调用参数；图必须声明选择 |
| `self.linear[layer](x)` | learned linear carry | 该源码与教材常见的 identity carry 不同，不能直接用原 x 绘成 skip |
| `gate * nonlinear` | g 和 nonlinear 分别进入乘法端口 | 两个操作数有真实来源，连线不能只表达“分支汇合” |
| `(1-gate) * linear` | 同一个 g → `1-g`；再与 learned carry 相乘 | 互补门不是第二组独立 gate 参数 |
| 两个乘积相加并更新 `x` | Add → 下一层三分支 | 层间顺序更新 x；没有权重跨层共享 |

两层共 6 个 `Linear(16,16)`，均使用默认 `bias=True`。参数身份为 `gate.0/1`、`nonlinear.0/1`、`linear.0/1`；颜色重复表示相同运算角色，绝不表示同一组权重。概览显示两层边界，内部图展开第 0 层三分支与融合，详细图再展开分支内算子；第 1 层折叠，但其所有参数和依赖都留在 IR。

## 为什么这样排布

层间主流程自底向上；第 0 层最底一排并列 gate / nonlinear / learned carry，中间放互补门和两个乘积，顶部放 Add。行由 `graph.ranks` 明确指定，图元宽高先依据文字测量，同行按 `column_gap` 分配横坐标，行间按 `rank_gap` 分配纵坐标。这里 ranks 只管视觉位置，所有依赖由 `extra_edges` 明确提供；容器不会凭三分支位置自动生成虚假的 tuple 或 Add。

各分支接收同一当前 x，门值 g 分叉至两个真实端点；下一层则读更新后的 x。这些是源码语义。三分支左右顺序、色卡、间距、提前转弯和避框路径是设计规则。显式端口使 g、nonlinear、complement、carry 的线能在折叠后映射到对应图框，完整端点仍可从 SVG tooltip、IR 与 `source_map.md` 检查。

本例新增互补门融合与 learned carry 模块覆盖。已有残差块虽也含 Add，无法复用它的 identity 跳线来替代这里的门控公式。

## 后续适配

可复用图式为“同源输入 → 并列变换 → typed operand 乘法 → Add → 顺序层”。换 Highway 实现应重查 carry 是否 identity、gate 是否共享、层间权重是否共享及调用方的 f。当前不执行模型，图中形状是静态选定配置。`validate_ir()` 对实际边端点和六个参数身份做守卫，语义负例会故意改错 carry / gate 端点，以确认错误能被拒绝。
