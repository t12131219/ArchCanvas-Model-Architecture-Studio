# M2 参数审核与导出：独立验收 oracle

此阶段只验证有明确源码位置的字面量 Dropout `p` 和 MultiheadAttention `dropout` 参数。连接重绑定、配置追踪、通用模型变换、运行验证和多文件提交不属于此阶段。预期从以下手写源码与用户 intent 推导，不从 staged analyzer 输出反向生成。

## 最小参数模型

```python
from torch import nn

class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.left = nn.Dropout(p=0.1)
        self.right = nn.Dropout(p=0.1)
        self.attn = nn.MultiheadAttention(8, 2, dropout=0.1)

    def forward(self, q, memory):
        first = self.left(q)
        second = self.left(first)
        third = self.right(second)
        return self.attn(third, memory, memory, need_weights=False)[0]
```

人工预期：选择 `left.p` 从 0.1 改为 0.2，只能改 `self.left` 构造中的一个 literal；`right.p` 与 `attn.dropout` 保持 0.1。`left` 的两个调用共享同一个实例，两个调用的参数事实都变为 0.2；每个 call identity、producer/consumer、端口与输出不变。选择 `attn.dropout` 时，只改第三个构造，q/k/v/mask 关系不能变化。所有 source diff 要以实际字节核对，不能仅比较展示文本。

同一字面量出现多次不构成唯一 target。Target 必须绑定项目、entry、instance、parameter 和准确的 literal source span；`name == left` 的显示别名不参与源码解析。

## 必须拒绝的源码形态

- `p = 0.1; self.left = nn.Dropout(p=p)`：本阶段拒绝变量引用，不能默认改变量的定义。
- `self.left = nn.Dropout(p=0.05 * 2)`：本阶段拒绝派生表达式，即使静态求值结果为 0.1。
- `self.left = nn.Dropout(p=config.dropout)`、未知工厂、动态 `getattr` 或 shadowed torch symbol：拒绝缺少独立框架/source provenance 的目标。
- default 参数经多实例传递或共享 constructor span：若不能完整列出全部受影响实例/调用并证明唯一改动，拒绝歧义。
- NaN、infinity、非数值与不符合注册参数值域的新值：prepare 不产生可批准事务。

## 独立语义与字节预期

Expected delta 由原始源码和目标 intent 定义：仅指定参数的指定实例集合改变；图的端口、tensor producer/consumer、repeat/sharing、输出、operator kinds 和其他参数保持原值。Observed delta 从 staged 源码重新解析得到。Expected 不能由 staged 图提取，否则 staged 错改 `right` 或 q/k/v 连接可能一起被“认可”。

独立反例应在 prepare 后修改 staged 源码，分别改变另一个 Dropout literal、MHA key producer、return 输出和共享实例关系。Verify 或后续 guard 必须拒绝；不能因为指定参数也达到 0.2 而通过。反例作用是证明门能发现错误，而不是声明任意 PyTorch 语义已验证。

## Freshness 与审核绑定

Prepare/verify/review 不修改 originals。批准绑定具体 review digest、source corpus digest、staged digest、diff、intent 和验证结果；通用“批准所有”不能授权未来事务。CLI、服务和 UI 必须共享提交 guard。

在准备后修改任一原始 corpus 文件（包括只作为 imported helper 的文件）、新增相关源码文件、改变 staging、篡改 approval receipt 或重复使用 approval：commit 必须拒绝，保留当前 originals。未注册/不是同一个 project 的 target 不可借用别的图上的选择身份。

独立测试只在 `/tmp` 的模型副本执行成功 commit、模拟批准和故障注入。真实用户模型仍需展示具体 diff 和影响，取得与该 review 绑定的批准。

## 单文件提交与失败

成功后 source 字节必须等于人工只替换目标 literal 的预期字节；重分析反映指定参数且其他事实不变。Journal 登记实际状态与路径；批准不能再次提交。

在目标文件原子替换前注入 I/O 失败，原文件字节不变并记录失败。源文件 symlink、逃出注册根目录或外部修改不会被自动覆盖。若替换已成功但后续 journal 写失败，记录必须区分“源已经改变”与“源未改变”，不能统一报 rollback；重启恢复也不能自动覆盖新的人工作品。此阶段只承诺单文件，不能推广为多文件原子事务。

## 画布重分析与导出

成功 commit 后重新分析当前源码，以唯一 identity mapping 保留 display alias、node/edge style、legend、annotations、pinned、expanded frontier 与已建立 layout。删除/歧义对象要显式报告；不能按相似 label 猜测。新的 source/IR digest 与文档 id 与历史要更新；不能把旧语义 snapshot 通过视觉 undo 恢复为当前源码事实。

SVG 从当前保存 CanvasDocument 的正式 Scene renderer产生。PDF/PNG 只从这份 SVG 派生；receipt 保留 input SVG hash、document/revision/digest、页宽与转换器实际来源。85 mm 与 180 mm 的 PDF MediaBox 应与 SVG 物理尺寸吻合；PNG 像素尺寸与指定 DPI一致。旧环境、另一套 scene 样式或临时手工补图不得作为正式导出。

浏览器必须真实走一次参数选择 → prepare → verification → concrete review → approve → commit → reanalysis → save/reopen，仅使用隔离项目。除了可复核字节/关系检查，还检查图例、说明、别名、pin 与局部布局保存后保留。
