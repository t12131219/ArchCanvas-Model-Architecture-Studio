# 参数说明候选核对（AI，非真人验收）

日期：2026-10-06。审查对象：`studio/src/draftParameterHelp.ts`。
SHA-256：`fd84c1482c527ed940eab235788215258ef798bc82255e4a0e2b15b1d04abe40`。
本记录是参数说明作者的源合同核对，不是独立浏览器或真人研究者验收，也不证明 UI 已集成或文字在面板中的可读性。

依据正式 `AGENTS.md`、`skills/archcanvas/SKILL.md` 与 runtime-compatibility，以及当前 `src/archcanvas_authoring/draft.py` 的 `_CATALOG`、`_parameter`、`_axis`、`_infer`、`validate_draft`、`_source`。后端依据 SHA-256：`cce519d8ae9e865fedccb5981b34a9884c51cceca43c951eff59333ba322231d`。
没有阅读、迁移或执行失败 prototype；没有导入/执行模型、安装依赖、改写 API 或旧证据。

导出 `draftParameterHelp(kind: string, name: string): DraftParameterHelp | null`，其中 `DraftParameterHelp = { label: string; description: string }`。保留技术字段名由调用方完成。未知 kind/name（包括原型链名称）返回 null；返回说明副本，调用方修改返回值不会改变后续说明。

源字段覆盖核对使用 Python AST 阅读 `_CATALOG`，并读取 TypeScript 对象的模块/字段声明；不导入后端或执行模型。实际结果：注册模块 17，有参数模块 12，注册字段 34，说明字段 34，缺失与额外字段均为空。无参数的 Output、ReLU、SiLU、Identity、Add 不制造参数说明。未为低风险文案增加镜像单元测试。

| 模块 | 说明字段数 | 逐项合同核对 |
| --- | ---: | --- |
| Input | 2 | 1–8 维正整数形状是声明；类型选择与 float32 参数模块、int64 Embedding 需求分开。没有把声明当作测量或数据转换。 |
| Linear | 3 | in_features 必须匹配输入末维，out_features 只改变末维；bias 是按输出特征的加法偏置。 |
| GELU | 1 | none/tanh 两种注册选择；不改变声明的形状与浮点类型。 |
| Dropout | 1 | p 的范围包括 0、1；说明训练置零/保留元素缩放以及评估直接传递的区别，未声称执行结果。 |
| Flatten | 2 | 起止维均包含、从 0 计数、负数归一化、顺序与 rank 约束；特意提醒一维输入不能使用默认 start_dim=1。 |
| Conv2d | 8 | CHW/NCHW 的通道维、float32、[高,宽] 参数顺序、两侧零填充、步长/膨胀采样间距；groups 同时整除输入输出通道。 |
| MaxPool2d | 5 | 浮点 CHW/NCHW、显式默认 stride=[2,2]、负无穷填充与逐轴 padding≤kernel//2；ceil_mode 保留末端部分窗口并排除起点落入末端填充的窗口。没有把池化填充写成卷积的零填充。 |
| AdaptiveAvgPool2d | 1 | 固定正空间尺寸，保留通道/批次；[1,1] 表示每通道平均。 |
| BatchNorm2d | 5 | float32 4 维、通道匹配及当前合同每通道样本至少 2；eps 正值范围；momentum 是统计更新权重，区别于优化器动量；affine 按通道；track_running_stats 区分训练与评估统计来源。 |
| LayerNorm | 3 | normalized_shape 匹配末尾形状；eps 与可学习逐位置缩放/偏移；当前输入统计用于训练及评估，输出形状保留。 |
| Embedding | 2 | int64 索引范围条件不能由静态形状证明；输出 float32，并追加 embedding_dim。 |
| Concat | 1 | 固定 a/b 两路、支持负轴；dtype/rank 与非拼接维必须相同，拼接轴尺寸相加。 |

核对结论：候选说明符合当前注册/声明推断与生成构造合同。技术行为说明描述生成模块的预期语义，不是已执行、训练正确性或数值正确性的证据。尚需调用方集成后检查真实面板布局、键盘操作与浏览器文字阅读。
