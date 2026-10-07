# M4 双输入端口与跳连可读性

> 历史 DuFX 阶段记录：下方“当前/本轮/最终”只指此文冻结时点。后续三角色 AI 测试、修复、DuFX 性能诊断和新研究包见 [最新阶段](m4-ai-simulated-current.md)及 [当前门状态](evidence/m4-current-gate-audit.json)。现行为 B_XH、347/347；旧证据与本篇事实不改写为新构建认证。

2026-10-06，正式构建为 `index-DuFXKOwG.js` / `index--unhoRTb.css`。Studio **342/342、0 skipped**，严格 TypeScript/Vite 退出 0；99 项输入在测试与构建前后保持一致，见 [最终检查](evidence/m4-draft-port-legibility-work/checks-final-attempt-3/receipt.json)。M4 仍为 `partial`，M5 为 `not_started`，真人为 0；[当前门状态](evidence/m4-current-gate-audit.json)列出未完成项。

## 产品改进

- 节点尺寸按实际目录端口计算：单输入保持 176×100，当前 Add/Concat 为 176×140，双输入间距 32 world units。渲染、端口命中、路由避障、添加碰撞、预制网络、排版、视图适配与提示框使用同一尺寸合同。旧手排坐标不自动移动；扩大的卡片发生重叠时明确报告。
- 在 53% 概览中，双输入端口名义字号约 8.1 CSS px。文字补偿有上限，不能保证任意低缩放都可读。纵向文字放在卡片外；输出文字再向左移 10 world units，避免 28 world 间距中与下张 Add/Concat 输入文字相挤。
- 数据流使用绿色实线，跳连使用棕色虚线及对应箭头、图例。角色只按当前完整连接结构识别：Add 的一条输入来自另一输入生产者的严格祖先时才标为跳连。兄弟分支、同源相加、Concat、未知或相关不完整/循环图保持普通线。选中箭头与选中线条同色。
- 键盘切换端口会清除旧悬停提示，让提示跟随当前焦点。

左侧库仍有 **17 个基础模块＋3 个透明网络起点**：MLP、CNN、残差 MLP，可点击或拖入；本轮未新增算子、训练或模型执行。新手操作包括从零添加模块、声明参数、连接端口、检查、保存重开和生成独立新模型；不结构改写导入的模型。

## 独立验证与实际浏览器

三位 AI 子 Agent 分别审查几何/合同、结构角色与当前构建、实际画面；root 使用 CUA 操作隔离标签页。AI 不计真人席位。

[端口几何](evidence/m4-draft-port-legibility-work/port-geometry-focused-pass/README.md)专项为 63/63；[纵向邻卡文字](evidence/m4-draft-port-legibility-work/vertical-label-gap-focused-pass/README.md)专项为 64/64；[角色合同](evidence/m4-draft-port-legibility-work/edge-role-independent/report.json)为 18/18，另七个手写 DAG 的静态源角色核对为 135/135。63/63、64/64 与 18/18 是最终 Studio suite 的子集，不再相加；135/135 是另一次静态源核对。模型与框架未被导入或执行。

最终 DuFX 构建的 [11 组实际浏览器补采](evidence/m4-draft-port-legibility-work/browser-current-attempt-3/manifest.json)保存 46 份原件与 22 张截图：纵向 Concat 4 节点/3 边在 56% 缩放的文字间距、键盘 b 端口提示与静态源码；新残差预制 6/6、Add 四向原生拖动 ±45 world units 并逐项撤销、保存重开、残差静态源码审看与最终预览。实际保存草稿原字节分别见 [Concat](evidence/m4-draft-port-legibility-work/saved-artifacts/concat/manifest.json)与 [当前残差](evidence/m4-draft-port-legibility-work/saved-artifacts/current-residual/manifest.json)。Concat 从零搭建、首次保存生成并打开新工作副本发生于 Bf83，最终 DuFX 对保存草稿和生成源码做限定补查，不能改称在最终构建重做了全流程。

截图文件中的 initial/settled 只表示采集顺序，稳定公开状态不证明画面同步。保留最终 Concat 生成 dialog 的两张失败截图、初始画面滞后以及首次 fit 的 CDP 命令失败；实际像素结论以独立亲看报告覆盖为准。Bf83 的四向相机 ±24 CSS px、左移重做与从零搭建为明确 [历史版本补采](evidence/m4-draft-port-legibility-work/browser-current-attempt-2/receipt.json)，不是 DuFX 全矩阵认证。首次相机批处理超时后只写出 12 的 DOM；该不完整记录保留，另名重试完成。选中跳连首次点击误中 ReLU，也保留未达任务的原件，实际线段点击重试单列。

当前小样本残差的基础旁路有四个折点；上下移动会增加必要的高差折点。纵向 Concat 第一输入需绕过第二输入卡片。未承诺复杂图全局最少交叉/弯折、全 17 种逐模块完整生成或全模型出版美观。

最终 [独立像素审看](evidence/m4-draft-port-legibility-work/pixel-independent-current-attempt-3/final-review.json)逐一亲看 22 个原图文件（19 份不同图像字节）：12 份有界匹配、9 份画面与对应状态不一致、1 份控件焦点同步有限证据。最终预览的 settled 图和四向节点移动的 settled 图有相应限定通过；Concat 的生成 modal 两图未显示对话框，保留失败，源码/DOM 正确不能替代其实际画面。

[独立公开合同](evidence/m4-draft-port-legibility-work/browser-contract-independent/README.md)对当前布局、四向节点/保存/源码、最终回读分阶段为 322/322、512/512、115/115，不能相加当作产品测试或像素通过。当前三份实际构建文件及 99 份源码/测试输入的 [独立回读](evidence/m4-draft-port-legibility-work/current-closeout-independent-attempt-1/final-source-build-readback-attempt-3.json)保持精确；几何、工件和像素结论分别陈述。

## 当前验收边界

静态基础模型 11/11、holdout 28/28、integrity 22/22 与 local 58/58 保留各自已有独立范围；此轮没有更改分析/运行后端，也不把计数累加为模型运行正确性。工程仍从头实现，可脱离失败旧目录运行，无新增认证复用片段。

当前构建没有新的性能采样。D60 历史 smoke 的 1008 ms、约 2.02 rAF/s 仍是失败/未认证证据；rAF 不是呈现 FPS。[呈现性能能力审计](evidence/m4-presented-performance-capability-audit/README.md)确认当前工具不能启动宿主原生 Performance Trace，未用截图或空 longTask 替代呈现 trace。

旧 D60 研究包保持原字节，因正式实施绑定已改变被 verify 拒绝为 stale，见 [独立过期检查](evidence/m4-draft-port-legibility-work/current-closeout-independent-attempt-1/old-d60-stale-report.json)。当前 DuFX 未准备研究包、未分配/收集席位、未启动席位服务；真人仍为 0。3–5 位真实研究使用者任务、85/180 mm 实际出版尺寸人审与呈现性能门仍开放。M4 不标完成，不进入 M5。

文档切换前 14 份入口原字节已 [归档](evidence/m4-draft-port-legibility-work/before-current-doc-update/manifest.json)。D4zr、Bf83 与更早 raw、manifest、失败和报告保留其构建范围。本轮隔离服务 session39008、tab63 在结束时实际读取并保留为预览，不承诺长期在线。
