# AI 新手体验只读审查（BG 当前构建）

审查时间：2026-10-06。审查对象是正式工程当前 `BGj2ZBSY` Studio；AI 角色不计入真人研究者或出版审看者分母。没有控制共享浏览器、没有运行模型、没有修改产品源码和已封存证据。

## 已实际验证

- 当前 BG 浏览器的有限 authoring 烟测点击“小型 CNN”：公开 DOM 显示 17 个模块按钮和 3 个网络起点，点击后实际得到 8 个节点、7 条连接；一次撤销回到 0/0，重做恢复插入图；保存和重开状态可见。重开 SVG 的唯一差异是首个 Input 的 `selected` class 清除，去除此选择态后 XML、ID、路径和几何一致。证据见 `docs/evidence/m4-repeat-outline-work/acceptance/browser-attempt-1/authoring/review.json` 和 `reopen-selection-correction.json`。
- 当前 BG 的模块库代码同时提供点击和原生拖入：模块按钮与三种起点都有 `draggable`/`onDragStart`，画布 `onDrop` 读取 `application/x-archcanvas-module` 或 `application/x-archcanvas-preset` 并插入草稿；按钮点击走同一个添加路径。见 `studio/src/AuthoringStudio.tsx:121`、`:205`、`:207`（以当前文件行为准）。
- 当前 BG 的四向 Transformer 节点拖动记录实际有左、右、上、下位移，撤销/重做和重开链条通过；上移案例明确记录 3 次 route segment 命中、2 对卡片穿入并显示 blocked 提示。四向尝试因此不是“四向均无冲突”。权威摘要见 `docs/evidence/m4-repeat-outline-work/acceptance/browser-attempt-1/SUMMARY.md`。
- 正式静态测试 `170/170` 通过，包含三个透明起点的原子 history、重做、坐标路由、独立节点/连接身份和非执行式 backend 源码生成检查；它证明合同和静态 pipeline，不等于当前浏览器完成 17 种模块逐项任务。收据见 `docs/evidence/m4-repeat-outline-work/root/full-studio-attempt-2/receipt.json` 与 `stdout.log`。

## 尚未验证或证据不足

- 没有当前 BG 浏览器中 17 种模块逐项“拖入 → 设置参数 → 连线 → 生成源码”的完整 E2E 记录。
- 没有当前 BG 浏览器中三个起点全部点击/拖入的完整记录；当前只对 CNN 起点有点击烟测。MLP、残差 MLP 只在静态测试或较早构建记录中出现，不能替代当前构建的浏览器证据。
- 没有当前 BG 的 saved draft payload/localStorage 内容核查，也没有把生成源码、创建 managed 工作副本、论文图导出串成一条当前浏览器链；按钮和后端静态测试不能单独证明该链已完成。
- 没有真人新手、真人出版尺寸或字体/箭头人工审看。AI 截图和几何审查不改变 `human=0`。

## 最影响新手的三个具体缺口

1. **连线在复杂图中仍可能紊乱。** 当前独立 BG 摘要仍报告 L3 有 19 对不同 tensor 重叠、20 对严格交叉；Transformer 上移的实际样本还有卡片穿入。系统会保留用户坐标并给 blocked/布局提示，但提示不等于自动得到美观、最少交叉或最少弯折的结果。复杂图从零搭建时，小白容易把“连上了”误解为“图面可读”。
2. **连接前的理解反馈太弱。** UI 连接逻辑首先检查端口方向、重复输入和环；形状/类型兼容性主要到后端保存或生成时静态检查。画布端口只显示端口名和输入/输出方向，没有在连线候选阶段直接显示上游/下游 shape、dtype 或不兼容原因。新手需要先连，再等底部错误定位，失败成本较高。
3. **常用模块覆盖仍不完整。** 当前 17 项包含 Input/Output、Linear、激活、Dropout、Flatten、Conv2d、池化、归一化、Embedding、Add/Concat；三个透明起点是 MLP/CNN/残差 MLP。目录明确把 `Sigmoid`、`Tanh`、`Conv1d`、`AvgPool2d`、`BatchNorm1d`、`MultiheadAttention`、`LSTM` 列为 unsupported，且没有任意 Python、自定义节点、循环、共享权重或动态形状。对只依赖视图搭模型的研究新手，搜索无命中后只能知道“暂不支持”，仍无法完成这些常见网络。

## “17 模块 + 3 起点能否点击/拖入并生成源码？”

结论要分成三层：

- **实现层：可以。** `AuthoringStudio.tsx` 为 17 模块按钮和 3 起点都注册了点击添加与原生拖放；落入画布后生成 authored draft 节点/typed edges。`authoringPresets.ts` 对 MLP（5/4）、CNN（8/7）、残差 MLP（6/6）预先建立普通可编辑节点和端口连接。
- **静态合同层：三起点与 17 模块组合有证据。** `authoring-presets.test.ts` 和当前 170 项测试覆盖起点 history、坐标路由、参数合同及非执行式 `generate_model`；文档列出的正例包括 17 种模块、Embedding→LayerNorm、残差分支、不同 Concat 轴、分组/膨胀卷积和 ceil pooling。生成结果标记 `modelExecution: not_run`。
- **当前浏览器逐项用户层：尚不能宣称全覆盖。** 仅 CNN 起点点击的 8/7 保存重开烟测已绑定当前 BG；当前没有 17 模块逐项拖入和每项源码生成的浏览器记录，也没有 MLP/残差起点在当前 BG 的完整拖入/生成记录。因此给小白的准确说法是“入口和代码路径已经存在，CNN 点击烟测已通过，完整逐项交互仍待真人/新矩阵复采”。

## 直接可执行的后续验收任务

- 在同一当前 BG 构建按模块类别完成 17 项：拖入、默认参数、修改一个关键参数、连到 Input/Output、生成源码；保存每项公开 DOM、生成 modal 源码和服务 receipt。
- 对三个起点各做一次点击与一次原生拖入，逐一验证节点数、端口绑定、生成源码和一次撤销；把静态测试与浏览器记录分开计数。
- 对 CNN、残差和 Transformer 密集图做四向移动后，人工看整图与出版尺寸，记录无关交叉、折点、端口净空和字体可读性；发生 blocked 时保留真实提示和截图，不将其标成通过。

## 文档一致性备注

`docs/m4-authoring.md` 的旧段落仍有“当前也不提供……复合预制网络”的历史表述；同一文档前文已描述 MLP、CNN、残差 MLP 三个透明起点。此处只记录歧义，未修改正式文档或任何封存文件；后续应由正式文档维护任务用当前 BG 证据修正措辞。
