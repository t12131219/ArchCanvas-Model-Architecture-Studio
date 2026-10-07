# 新手搭建与左侧模块库：独立 AI 审查

正式工程已经具备左侧常用模块库、点击/拖入、可编辑网络起点和从空白草稿到新模型的图上流程。已有代表性原生 UI 记录支持这一结论；尚无真人小白记录，也没有逐一验证全部模块。本审查只读源码和冻结材料，亲自查看下列 3 张原始 JPEG；未操作共享浏览器、执行模型或安装依赖。精确输入快照与只读检查见 [receipt.json](receipt.json)。

当前目录只写本报告及输入快照，不修改产品、旧证据、当前阶段文档、状态或 root 封印。旧操作记录属于 ye7sAyyI 构建；本轮合并画面属于 BSA5RjBV 构建，旧记录不能直接认证新构建的完整交互范围。未访问或测试 DL Playground；下述差距针对用户所描述的“常用模块多、直接拖入、完全依赖视图”的目标。

## 实际模块范围

[正式目录定义](../../../../src/archcanvas_authoring/draft.py#L58)和[冻结左侧 UI](../../m4-authoring-interaction-work/browser-attempt-1/blank-four-before-connections.dom.txt)一致：17 种基础模块，分为 11 类。

| 分类 | 实际模块 |
| --- | --- |
| 输入与输出 | Input（输入）、Output（输出） |
| 全连接 | Linear（全连接） |
| 激活函数 | ReLU、GELU、SiLU |
| 基础算子 | Identity（恒等映射） |
| 正则化 | Dropout（随机失活） |
| 形状变换 | Flatten（展平） |
| 卷积 | Conv2d（二维卷积） |
| 池化 | MaxPool2d、AdaptiveAvgPool2d |
| 归一化 | BatchNorm2d、LayerNorm |
| 嵌入 | Embedding（词嵌入） |
| 合并与分支 | Add（两路相加）、Concat（两路拼接） |

[3 个透明网络起点](../../../../studio/src/authoringPresets.ts#L11)均由上述普通节点组成，可以继续改参数与连接；它们不是新增黑盒模块。

| 起点 | 声明输入 → 输出 | 节点 / 连线 | 已有原生操作证据 |
| --- | --- | --- | --- |
| 最小 MLP | float32 [1,16] → [1,4] | 5 / 4 | 点击加入、保存、显示静态生成源码；[保存观察](../../m4-authoring-interaction-work/browser-attempt-1/mlp-saved-settled.public.json)、[生成对话框](../../m4-authoring-interaction-work/browser-attempt-1/mlp-generated.dom.txt) |
| 小型 CNN | float32 [1,3,32,32] → [1,4] | 8 / 7 | 空白起步，原生卡片拖入、保存、静态生成；[拖入后观察](../../m4-authoring-interaction-work/browser-attempt-1/cnn-preset-native-drag-fit-after.public.json)、[生成对话框](../../m4-authoring-interaction-work/browser-attempt-1/cnn-generated.dom.txt) |
| 残差 MLP | float32 [1,16] → [1,16] | 6 / 6 | 点击加入和保存；[保存观察](../../m4-authoring-interaction-work/browser-attempt-1/residual-saved-settled.public.json)。这轮未生成此起点的源码 |

源码的同一基础卡片具有 `onClick` 与 `onDragStart`，画布 `onDrop` 按当前相机投影添加节点；起点也支持两种入口。搜索同时匹配类型、中文名称、说明与起点，并提供空结果提示（[UI 入口](../../../../studio/src/AuthoringStudio.tsx#L257)）。这是实现证据；现有原生记录只覆盖基础模块点击和 CNN 起点拖入，不代表 17 种基础模块均已拖入测试。

## 从空白到新模型的实际链

[操作声明](../../m4-authoring-interaction-work/browser-final-manifest-attempt-1.json)是原始工具操作之后的回顾记录，不是同步系统输入遥测。它与下列公共 DOM、保存文件、可见源码相互支持一个有限流程：

1. 空白模型点击 Input、Linear、GELU、Output；右侧设置坐标、Linear 16→8。此时 [4 节点 / 0 连线](../../m4-authoring-interaction-work/browser-attempt-1/blank-four-before-connections.public.json)。
2. Input→Linear 使用端口文字点击；Linear→GELU 使用圆点拖动；GELU→Output 使用 Enter/Space。完成后 [4 节点 / 3 连线](../../m4-authoring-interaction-work/browser-attempt-1/keyboard-third-connected.public.json)。重复输入连接被拒绝，撤销/重做恢复数量 3→2→3。
3. 保存后重开保留节点身份和纵向坐标；[真实保存副本](../../m4-authoring-interaction-work/actual-artifacts-attempt-1/vertical-draft-envelope.json)与[重开观察](../../m4-authoring-interaction-work/browser-attempt-1/vertical-final-reopened-after.public.json)一致。纵向位置由右侧坐标设置，`按连接排版` 当前产生横向分层。
4. 生成对话框显示源码，再打开新工作副本、保存/重开和导出 SVG；[可见源码](../../m4-authoring-interaction-work/browser-attempt-1/vertical-generated-source-visible.py)与[真实 model.py 副本](../../m4-authoring-interaction-work/actual-artifacts-attempt-1/vertical-model.py)相同。这是声明张量的静态路径，不是模型运行或训练证据。

手动操作不要求输入代码。但“完全依赖视图”仍有两个实际弱点：[画布节点](../../../../studio/src/AuthoringStudio.tsx#L277)只显示名称、类型和端口，不显示逐段声明 shape；[参数字段](../../../../studio/src/AuthoringStudio.tsx#L320)多数直接显示 `in_features`、`normalized_shape` 等技术名，只有 Linear 有具体形状示例。验证 API 已存在，但当前组件只在加载时调用它，编辑后的主要反馈在保存/生成时出现（[调用点](../../../../studio/src/AuthoringStudio.tsx#L51)）。

## 画面与尚未覆盖的范围

亲看 [纵向四节点](../../m4-authoring-interaction-work/browser-attempt-1/vertical-four-connected.jpg)、[CNN 拖入](../../m4-authoring-interaction-work/browser-attempt-1/cnn-preset-native-drag-fit.jpg)、[本轮清晰合并画面](../browser-attempt-2/merge-clear-after-generation.jpg)：前三条纵向箭头和 CNN 普通相邻箭头可跟随；CNN 有长两排回路线，本轮合并仍有绕到外侧的多折线。81%、85% 下端口字已细小，56% 合并下 `left/right/a/b` 难辨。新的公共合并路径确实绕开旧交点，但没有证明全局最少弯折或新手能轻松追踪（[本轮公共观察](../browser-attempt-2/merge-complete-fit.public.json)）。本审查不借用误名的 100% 或受模态遮挡画面作为通过证据。

明确未测：每个基础模块的点击/拖入/参数修改/生成整链；全部起点的点击与拖入两种入口；每种模块的初学者错误恢复；窄屏与不同浏览器；删除和复杂多输出的新手流程；持久按压、所有长标签及连续移动下的观感；真人从零独立完成率与出版尺寸阅读。本轮合并生成未打开新 managed 图，旧四节点的制图/导出证据不能外推给它。

目录明确排除 Sigmoid、Tanh、Conv1d、AvgPool2d、BatchNorm1d、MultiheadAttention、LSTM；Add 不含广播，Concat 固定两输入；仅有 3 个起点，尚无可保存个人子图的入口（[目录边界](../../../../src/archcanvas_authoring/draft.py#L155)、[组件入口](../../../../studio/src/AuthoringStudio.tsx#L269)）。因此当前“像左侧模块库一样直接搭建”的交互形式已存在，广度和引导仍需扩充。

## 建议下一步实现顺序

1. 优先改善端口文字和目标在缩放下的阅读/命中：连接时突出兼容目标、显示可读端口提示，验证多输入目标仍互不遮挡；同时修复 Escape 后仍显示“连接起点已选中”的通知（[取消后原始观察](../../m4-authoring-interaction-work/browser-attempt-1/vertical-100-canceled-v2.public.json)、[取消实现](../../../../studio/src/AuthoringStudio.tsx#L73)）。
2. 给参数加中文用途和当前声明形状例子，在节点或连线上显示明确标为“声明”的输入/输出 shape；增加编辑阶段的静态检查入口与定位。保留技术名与精确字段身份，避免将静态推导说成运行结果。
3. 左侧分类可折叠，起点卡片附小图预览，并提供独立模块/网络起点的快捷定位；当前长列表依赖滚动，3 起点置顶后基础输入卡片可能落到视口下方（[布局源码](../../../../studio/src/AuthoringStudio.css)、上面 3 张原始画面）。
4. 先在现有 17 模块内增加可独立验证的分类/嵌入/归一化起点，再分别为 Sigmoid、Tanh 等高频算子建立静态契约和生成事实证据。添加 Attention/LSTM 前需要新的端口与形状契约；卡片数量增加本身不是正确性证据。
5. 改善 CNN 两排回路线和合并长绕线的排布成本，加入用户可选择的横向/纵向排版；每次修改继续验证节点身份、连接事实和撤销/保存稳定。

这些是可实施候选，不是本审查已经改完的功能。AI 审查不替代真人参与；M4 仍为 partial，真人数量仍为 0。
