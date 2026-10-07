# AI 新手搭建审查 v2（静态合同与目录核查）

本目录记录一次 AI 模拟新手审查，时间为 2026-10-07。AI 角色不计作真人研究者，也不替代真人出版审看；本轮没有控制共享浏览器、没有运行模型、没有安装依赖、没有修改产品源码或旧 evidence。产品工作区已有的局部改动（搭建页 inspector 恢复与拖拽反馈）由当前工程状态直接读取。

审查从 `AGENTS.md` 和当前阶段文档开始，随后读取当前 Authoring Studio、authoring catalog、preset 插入、字段帮助、静态检查/错误定位、API 路由和命名的 `Source_Code_Project/DL-Playground` 目录注册表。DL-Playground 只用于观察常用模块的目录广度和侧栏交互启发；没有导入或复用其代码。

## 可复现检查

```bash
cd /home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio
.venv/bin/python -I -S -B docs/evidence/m4-routing-user-simulation-v2/ai-novice/check_contracts.py
node --experimental-strip-types docs/evidence/m4-routing-user-simulation-v2/ai-novice/check_frontend.mjs
```

`check_contracts.py` 对当前后端目录逐一构造 17 个手写形状期望图，静态生成源码并只解析 AST；`builtins.exec` 和 `builtins.eval` 均被拒绝，验证结果要求 `modelExecution=not_run`。同时覆盖 17 个错误/不完整反例、部分草稿保存重开和草稿字节不变。结果为 17/17 正例、17/17 反例、16 个精确输入绑定、真人 0、模型执行 0。

`check_frontend.mjs` 读取当前前端实际 TS/TSX 表达式：核对 34 个参数字段均有帮助说明，MLP/CNN/残差 MLP 的 5/4、8/7、6/6 节点/连线与单步历史插入，12 个搜索词（含 `Sigmoid`、`Softmax`、`LSTM`、`注意力` 空结果），从源码重建 `new blank` 未保存保护，并构造清空标题、清空节点标签和 129 节点的缓存边界反例。它还以 TypeScript AST 读取 DL-Playground 注册表：14 组、80 个声明条目、79 个唯一键，其中 `repeat_layer` 在两组重复；这是只读库存记录，不代表参考产品正确性。结果为 5 个前端检查组、34 字段、3 个预制、12 个搜索词、3 个缓存反例、真人 0。

机器报告见 [contract-report.json](contract-report.json)、[frontend-report.json](frontend-report.json)。每个报告包含输入文件字节和 SHA-256；`artifacts/` 下的 17 份生成源码/草稿仅作为本轮静态输出，不是运行工件。

## 新手可复现问题与优先级

### P0：基本搭建能做，但搜索和错误恢复仍让新手停住

- 当前 authored catalog 有 17 个模块、11 类、34 个参数字段；3 个透明网络起点分别是最小 MLP（5/4）、小型 CNN（8/7）和残差 MLP（6/6）。Input、Output、Linear、ReLU/GELU/SiLU、卷积/池化/归一化、Embedding、Add、Concat 覆盖了 MLP/CNN/残差和部分嵌入任务。
- `Sigmoid`、`Tanh`、`Softmax`、`Conv1d`、`AvgPool2d`、`BatchNorm1d`、`MultiheadAttention`、`LSTM`、`GRU` 等搜索没有命中；空结果说明目前只明确提到 Attention/LSTM。新手按常见输出激活或序列任务搜索时只看到“没有找到匹配”，没有说明“可用的替代起点/暂不支持的具体项”。
- 修正闭环存在：静态诊断包含真实 node/parameter/port 身份，右侧能显示字段帮助、检查问题和定位按钮；但这需要用户知道先完成连接后点“检查模型”。建议在搜索空结果中按类别列出“暂不支持”与可用替代网络起点，并在首次错误后将“定位出错模块”提升为明确的下一步。

### P1：目录和预制入口可用，但不等于 DL-Playground 的常用模块广度

- DL-Playground 的只读 registry 有 14 组、80 个声明条目，包含 Sigmoid/Tanh/Softmax、Conv1d/3d、更多池化/归一化、RNN/GRU/LSTM/MultiheadAttention、形状与张量算子、损失和指标。ArchCanvas 当前 17 项是有界静态 authored subset，不能声称“尽量多的常用模块”。
- 当前侧栏默认“基础模块”与“网络起点”切换已降低混淆；搜索词非空时跨两类搜索。新增算子不应只增加卡片：每个新 kind 需要参数/端口、静态形状、源码生成、AST/IR round-trip 和错误反馈合同。优先候选应由真实研究任务选定，建议先评估 Sigmoid/Softmax、Conv1d 和一个有界序列模块，而不是按数量复制参考 registry。

### P1：空白模型保护语义安全但缺少可见新建分支

- `startBlankDraft` 在当前草稿有未保存节点/修订时显示“请先保存或重开后再新建空白模型”，不会静默丢失旧草稿；这是安全行为。
- 但按钮没有“另存当前草稿并新建”或“确认放弃并新建”分支，新手试验第二个网络时只能先保存/重开。建议增加显式确认对话框：保存并新建、放弃并新建、取消；保持旧草稿可重开。

### P1：编辑字段直接提交导致恢复依赖浏览器缓存边界

- 当前标题和模块显示名称输入的 `onChange` 直接提交空字符串，随后 `parseDraftCache`/后端会拒绝空文本。错误结构比参数字段更隐蔽：参数字段有范围反馈和 Escape 恢复，标题/显示名称没有同等级提示。
- 建议为标题和显示名称统一最小长度、字符提示与 Escape 恢复；提交前显示轻量 inline 错误，避免新手保存后才看到失败。

### P2：上限与运行边界应在卡片操作前可见

- 后端草稿预算为 128 个节点、384 条连接；当前单个按钮/拖入路径不在前端提前显示剩余预算，超限后才收到后端错误。`addDraftNode` 本身不检查上限；缓存边界会拒绝 129 节点。
- 建议在模块库底部/状态栏显示“已用 N/128 模块、M/384 连接”，接近上限时禁用添加并解释原因。

### P2：连线成功不代表图面可读

- 当前路由会诚实报告 blocked/overlap，并提供“按连接排版”；复杂 CNN/残差/大图仍需真人或固定浏览器视觉检查，不能把 0 连接错误等同于出版美观。新手应看到更具体的“连线已建立，但有 N 条路线穿过模块/相交”的下一步提示。

## 当前结论

AI 模拟已经确认：当前工程有可独立生成并静态核对的 17 模块/3 起点闭环，参数帮助和错误身份合同存在；同时确认常用模块覆盖明显小于 DL-Playground registry，搜索空结果、未保存新建和标题/标签空值是实际新手风险。AI 证据不能替代 3–5 位真实参与者的五步任务、视图四向操作、人审连线美观或 85/180 mm 出版审看，M4 仍为 `partial`，真人记录仍为 0。
