# M3 局部连接重绑定：独立验收 oracle

M3 的候选范围是直接编写的根 `forward` 中，一个 unary module 调用的准确 `Name` 参数替换。此记录先定义独立预期；实现、测试或浏览器任务未实际完成前，不能据此宣称连接写回已通过。

## 可成立的受限合同

仅 `torch.nn.Identity`、`Dropout`、`ReLU`、`GELU` 的已证明外部构造与直接调用进入候选。所有调用都必须在直线代码里，变量单一赋值，新的 producer 在目标之前且在作用域内可用；每一步只接受一项直接 tensor `Name` positional 输入，首批不支持 `input=...` keyword 或 `alias = existing_name`。`inplace=True`、alias/mutation/未知 call、动态分支、循环、嵌套作用域或重赋值不进入此范围。

shape/dtype 兼容只表示受限 unary 链保留同一 base input 的符号签名；没有已知的实际维数或 dtype，也没有执行模型。不同输入 `x` 与 `memory` 的符号不能因为显示形状相似而合并。GELU/ReLU 等合同不证明任意 dtype 的输入可执行，也不证明数值或训练行为等价。连接修改明确改变计算依赖，不能以“形状未改”表示行为未改。

## 独立手写源码

```python
from torch import nn

class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.first = nn.Identity()
        self.branch = nn.Dropout(p=0.1)
        self.other = nn.GELU()
        self.sink = nn.ReLU(inplace=False)
        self.tail = nn.Identity()

    def forward(self, x, memory):
        original = self.first(x)
        candidate = self.branch(x)
        separate = self.other(memory)
        result = self.sink(original)  # exactly this Name, not every original
        return self.tail(result)
```

人工预期：把 `sink.input` 从 `first.output` 改为 `branch.output`，源码只把 `self.sink(original)` 的 `original` 换为 `candidate`。构造参数、注释、换行、其他出现的名称均不改。图只有 `sink.input` 的 incoming producer/tensor identity 改变；first/branch/other/sink/tail 的 call identity、端口、各自 output identity 与其余边不变。`other` 来自 `memory`，必须拒绝作为这次替代 producer。`tail` 出现在 sink 之后，也必须拒绝。

该 oracle 从手写字节和独立关系表导出，不复制 lowering 的预期计算，不从 staged analyzer 输出生成 ExpectedDelta。API 选择身份可以取自初始 analysis，但验证要单独检查指定关系及不应改变的全部关系。

## 必须拒绝的反例

- 目标实参是 `original[0]`、`original + candidate`、属性、unpacked 或嵌套调用；不能把其中某个 `Name` 当作唯一 argument anchor。
- producer 在 consumer 之后、producer 或原输入变量被重赋值、名字来自不同/nested scope；仅同名不能证明 dominance。
- `x` 与 `memory` 两个 base input、Linear/reshape 等未纳入合同的路径、未知 dtype/shape 改变来源。
- `nn`、`torch`、module 属性或局部 constructor shadow；本地 `torch.py`、用户定义同名 ReLU；没有独立 PyTorch symbol provenance。
- 导入时 `nn.ReLU = nn.Identity`、`setattr(nn, ...)` 或未知顶层调用；它们可能改变外部符号，不能只因 AST 名称解析为 `torch.nn.ReLU` 就发出兼容证明。首批检查完整冻结 corpus 的顶层副作用、类 body 替换及 decorators，不执行它们。
- `Hook.__init_subclass__` 中改写 `nn.ReLU`，再声明 `class Trigger(Hook)`；类创建会触发继承 hook，也必须拒绝，不能将任意非入口 class body 都当作无副作用定义。
- in-place operator、未知 mutation/call、分支/循环/异常路径、共享源码 anchor 影响多个调用却没有完整影响证明。

## 审核与提交守卫

使用与 M2 相同的隔离准备、全 corpus freshness、精确 review digest、签名 approval、单文件 backup/journal 与写后验证。M3 新增重点是：篡改 staged 的另一条连接不能因为目标也达到要求而通过；参数事务的批准不能授权连接事务；commit 后关系与字节必须吻合此 oracle。

成功 commit 和模拟批准只操作验收自行创建的 `/tmp` 项目。HTTP 仍只操作受管理副本。实际用户模型需要具体 diff、前后影响和合同限制的审核与批准。

## 浏览器与视觉验收

完整任务是选择目标 input → 查看可证明 producer 候选及不支持原因 → prepare → 前后连接 review → approve → commit → reanalysis → save/reopen。单纯新增画布箭头不构成源码连接编辑。重分析后的 alias、样式、图例、说明、pin 与布局应按唯一身份保留；视觉 undo 不回滚源码。

M3 的另行视觉任务可覆盖三层展开、黑白 85/180 mm 审看，但这些不能替代连接的独立字节/关系与提交守卫证据。
