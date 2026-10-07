# M4：三角色 AI 模拟测试与体验修复

用户授权以 3–5 个子 Agent 模拟使用者，重点检查四向移动、视图秩序、连线、零基础搭建及左侧预制模块。本轮实际安排 **3 个 AI 角色**，通过真实浏览器界面操作，再由根 Agent 修复、补采和独立核对。AI 不计真人；M4 仍为 `partial`，M5 为 `not_started`，真人 0。

最终资产为 `index-B_XHk-wz.js` / `index--unhoRTb.css`。Studio **347/347、0 skipped**，strict TypeScript/Vite 退出 0；5 项新增回归包含在 347 项内，不相加。[最终检查收据](evidence/m4-ai-simulated-current/checks-final-attempt-3/receipt.json)绑定 100 个源码/测试/配置文件与 3 个构建文件，103 个绑定均精确。首次 strict 失败和后续修正记录保留。

## 三个实际模拟角色

| AI 角色 | 实际界面任务 | 主要发现与证据范围 |
| --- | --- | --- |
| 小白搭建 | 空白画布拖入 Input/Linear，点击添加 ReLU/Output，连接 4 节点 3 边；制造维度错误、修正、整理、保存重开、查看静态生成源码并打开新工作副本 | 中文错误定位可用；生成图出现 1.6 / 11.8 world 的多余横向小段。[原报告](evidence/m4-ai-simulated-current/novice/report.json)、[33 文件 manifest](evidence/m4-ai-simulated-current/novice/manifest.json)。273.245 秒是 AI/工具耗时，不用于真人 180 秒门。 |
| 操作与恢复 | 源模型和搭建残差图相机上/下/左/右移动；conv1/Add 四向拖动、撤销重做；缩放、适合视图、展开折叠重展开；保存重开；从零搭建双输入 Concat | 原 100% 按钮保留旧平移，使对象靠近视口外缘。[75 状态记录](evidence/m4-ai-simulated-current/gestures/README.md)、[manifest](evidence/m4-ai-simulated-current/gestures/manifest.json)。首次不完整连线及捕获字段遗漏保留并补采。 |
| 模块库与视觉 | 逐项检查 17 模块参数界面、跨类搜索、未支持模块说明；拖入 CNN 起点；CNN/残差节点四向移动与撤销；断连诊断修复和保存 | CNN 整理从两行 85% 变成一长行 40%；预制标签写入旧参数值。[库与视觉报告](evidence/m4-ai-simulated-current/catalog-visual/README.md)、[152 文件 manifest](evidence/m4-ai-simulated-current/catalog-visual/manifest.json)。16 个关键 SVG 的 105 条状态路线端点精确、无无关卡片内部穿越；不证明全局最少弯折。 |

三角色原始测试绑定 **DuFX**；不能改称最终 B_XH 全套操作认证。17 个模块全部检查的是参数界面，未逐种完成生成/执行。左库已有 17 个基础模块和 3 个透明网络起点，支持直接拖入；Attention/LSTM 仍无搭建支持说明以外的能力。本轮未新增模块种类。

## 已落实的修复

1. 源模型画布工具栏的 100% / 加 / 减以实际视口中心缩放，保留中心所对应的世界坐标，避免缩放时原关注位置漂走。
2. 首次创建生成模型的 CanvasDocument 时，先校验并应用已验证节点显示别名，再测量和布局。示例 4 节点链三条边最终均在 `x=177`，原多余小段消失；后续别名编辑保留用户布局。
3. 至少 7 节点的连通单输入单输出链按实际搭建视口折行，改善适合视图后的字号。分支/汇合、短链和未提供视口时继续使用原 rank 布局。判断条件是拓扑，不要求先通过生成检查。
4. 新预制图使用角色名称，如“卷积”“分类头”“自适应平均池化”，参数展示跟随真实参数。历史保存草稿的标签保持原值；`AdaptiveAvgPool2d` 的名称能覆盖 `output_size` 从 1×1 改为 2×2 的情形。

实现位于 `cameraProjection.ts`、`App.tsx`、`core/document.ts`、`authoring.ts`、`AuthoringStudio.tsx`、`authoringPresets.ts`；新增回归为 `studio/tests/ai-usability-regressions.test.ts`。正式工程从头实现，无 Temp runtime/fallback，无新增认证复用。本轮只做静态生成、分析与图编辑，未执行生成模型。

## 版本分开的补测与独立复核

| 构建/证据 | 结论与限制 |
| --- | --- |
| CC91：根 Agent [21 组界面记录](evidence/m4-ai-simulated-current/browser-fixes/receipt.json) | CNN/MLP 缩放、移动/聚焦；空白 4/3 搭建、保存重开、源码、新工作副本及保存重开。3 条生成图路线 `x=177`，5 个保存/重开状态保持直线。 |
| CC91：[模块库补测](evidence/m4-ai-simulated-current/catalog-followup/README.md) | 较大视口 CNN 为 3 列 3 行、91%；四向移动、Conv 8→10 与 Linear 8→10 修正、保存重开。22 状态、154 条状态路线无端点偏差/无关卡片穿越；18 张有限匹配、4 张滞后，原件保留。 |
| CC91：[缩放独立复核](evidence/m4-ai-simulated-current/zoom-followup/README.md) | 实际 SVG rect / 公开 DOM bbox 方法 7/7 达界限，最大 world 误差 0.00020591、CSS 误差 0.00024709；11 张原图中 9 张有限匹配、2 张滞后。CSS 序列化方法的一项更严格界限失败也保留。 |
| 静态实现：[26+9 属性](evidence/m4-ai-simulated-current/fix-independent/final-static-receipt.json) | 中心缩放、初始别名/源码不变/序列化/重展开/历史及 n=7/8/17/CNN 折行、保留/确定性/障碍/分支不折行均通过。这些独立断言不计为额外 Studio 测试或真人。 |
| **B_XH 最终**：[7 状态/30 文件](evidence/m4-ai-simulated-current/final-browser/receipt.json) | 重开直线链；新 CNN 整理；池化 1×1→2×2 后正确报告 Linear 8 与上游 32 不符，改为 32 通过，保存重开/适合视图。637×619.5 视口为 **2 列 4 行、84%**，不能套用 CC91 的 91%。 |
| **B_XH 独立末读**：[构建核对](evidence/m4-ai-simulated-current/final-readback/catalog-independent/implementation-report.json)、[界面核对](evidence/m4-ai-simulated-current/final-readback/catalog-independent/final-browser-report.json) | 103 绑定精确；相对 CC91 仅池化名称改动，另 99 个输入文件相同。独立亲看最终 7 原图，7 个有限匹配；6 个草稿状态 42 条状态路线端点误差 0、无无关卡片内部穿越，3 条源图边直线。保存 JSON 的池化 2×2、Linear 32、坐标与界面及服务原件相同。 |

![最终 CNN 保存重开后的实际界面](evidence/m4-ai-simulated-current/final-browser/07-final-cnn-settled.jpg)

独立浏览器不可用的补测保留为 [not-performed](evidence/m4-ai-simulated-current/novice-followup/not-performed.json)，不算成功。较早滞后截图、错误 oracle、strict 失败、界面保存保护的自动审批拒绝及随后通过可见保存解除的过程均未删除。最终 7 图的有限匹配来自实际逐图审看，不是像素算法、任意复杂图美学、完整最终四向矩阵或实际出版尺寸认证。

## 性能与真人研究门

本轮修复前取得 **DuFX** 的两组原生展开/折叠诊断，每组 2 个捕获/有效/匹配；匹配子集 p95 40 ms，rAF 约 60 Hz，12→14→12 对象、无 pin、锚点漂移 0。见 [原始收据](evidence/m4-dufx-performance-visibility/receipt.json)和 [独立条件审计](evidence/m4-current-performance-condition-review/README.md)。宿主 visibility 两组均为 false，不能建立显示/隐藏 A/B；测量开销与完整输入分母未认证。rAF 回调频率不等于实际呈现帧率，亦非 300 对象性能门。旧 D60 的 1008 ms / 约 2.02 rAF Hz 失败继续保留。**最终 B_XH 无性能采样**。

新 [B_XH 真人研究准备](evidence/m4-ai-simulated-current/research-final-preparation/report.json) prepare、verify 和独立 273/273 核对通过。包为 `.archcanvas/m4-research-trial-bxh-current`，manifest SHA256 `61ac9fbb61d26d1dd6b68bc0873955a3ec467bd2988b2e927e22f0a299162cdf`；5 个空白席位，43451–43455 仅登记，未检测端口/启动席位服务、未分配/收集、真人 0。19 个旧包共 325 文件不变；DuFX/CC91 旧包因实现变化被正式 verify 拒绝，拒绝日志保留。[最终独立复核目录](evidence/m4-ai-simulated-current/final-readback/catalog-independent/README.md)另有 612/612 准备/字节断言；它们不是额外产品测试或参与者。

真人五步任务、85/180 mm 出版尺寸人审、300 对象实际呈现性能及复杂图路由仍未完成。当前门状态见 [机器记录](evidence/m4-current-gate-audit.json)，准备复核见 [研究协议](m4-research-protocol.md)。本轮入口文档修改前 [15 文件原字节](evidence/m4-ai-simulated-current/before-entry-update/manifest.json)、产品修复前 [源码/构建](evidence/m4-ai-simulated-current/before-fixes/manifest.json)和最终池化名称前 [4 文件](evidence/m4-ai-simulated-current/before-final-label/manifest.json)均保留；旧证据仅按自身版本与冻结时点阅读。
