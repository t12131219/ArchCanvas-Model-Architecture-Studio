# M4 AI 模拟试用 v2 与 M5 入口

2026-10-07：当前工程验证稳定，Studio **483/483**、0 fail/skip/cancel，strict TypeScript/Vite exit 0，工程 `.venv` publication **11/11**、0 skip。统一收据见 [checks-final](evidence/m4-routing-user-simulation-v2/checks-final/receipt.json)。当前资产为 `index-CimCnLHA.js` / `index-BOWsNy5e.css`，JS SHA256 `4781fe1aeeb30af9b230f9092bc6318d52959d528894390b44c28668c2dfb732`。121 个 Studio 源码/测试/配置输入、13 个 publication 输入与 3 个 dist 分别绑定；不是完整传递依赖清单，也不把专项数量累加到全套。

按用户明确要求，**开始 M5，不等待真人席位与出版审看**。这改变推进顺序，不改变验收事实：M4 保持 `partial`，真人 0，出版人工审看、全局连线美观与持续呈现性能仍开放。M5 第一片段见 [Beta 发布工作](m5-beta-release.md)。

## 本轮修正与有限证据

标题与模块显示名称在失焦时提交；空值或控制字符显示提示，Escape 恢复上次有效名称。模块/连线分别在 128/384 上限前拒绝变更，不污染撤销历史。搜索常见但尚未支持的激活、卷积、池化、注意力与循环模块时，明确显示限制与可用选项。当前模块库仍为 **17 个基础模块、3 个透明网络起点**，未扩大模型执行范围。

[AI 新手审查](evidence/m4-routing-user-simulation-v2/ai-novice/README.md)核对 17 个静态生成正例、17 个反例、34 个参数帮助字段和三种预制起点。其清空名称/容量问题已由本轮修正；原报告属于修正前字节，不回写为通过。DL-Playground 仅作目录广度的只读行为参考，没有导入或复用代码。

[最终浏览器收据](evidence/m4-routing-user-simulation-v2/browser-final/receipt.json)记录当前构建中的 MLP 四向文字移动、四向原生拖动和各自撤销、四向平移、缩放/适合画布，以及 Residual CNN 适合画布。最终补测在空白草稿原生拖入最小 MLP 后得到 5 模块/4 连接，一次撤销返回 0/0；标题和模块名的清空/Escape 均实际观察。模型未执行。

独立 [视图回读](evidence/m4-routing-user-simulation-v2/browser-view/browser-visual-review.json)保留两项失败：02 的右移未生效，03 撤销收起了层级，均不计移动恢复成功。MLP 原生向上/下/左拖动会产生明确的布局/路线警告；向下与相邻卡片重叠 2 world units，不能宣称任意拖动后布局都美观。早期 browser/01–02 属于 B32 构建，不能认证最终搭建页。

[密集图独立几何](evidence/m4-routing-user-simulation-v2/ai-geometry/report.json)属于 B32 router 输入范围；当前 router 字节未变，但报告仍保留原 build 标签。基线 38 个不同 tensor 交叉仍存在，窄缝下移仍有 6 对非端点叶模块入侵。[窄缝候选](evidence/m4-routing-user-simulation-v2/ai-routing/tight-gap-analysis.json)虽然消除了中心线入侵，固定箭头 marker 仍进入上方模块约 0.1875 world units，因此候选被拒绝，`blocked` 未隐藏。

## 已冻结研究准备

`.archcanvas/m4-research-trial-routing-user-simulation-v2` 正式 verify 通过，manifest SHA256 `7ccb839dee6e1ec34492b35bc8928730d317838a6f2bed6d29b2bceb55d1160c`。88 implementation、4 baseline 与 5 slot envelope 的 97 个字节绑定一致；S01–S05 pristine、端口仅登记 43911–43915，assignment/collection/researcher 全为 0。没有启动研究席位服务或认证参与者。后续实现变化会使该包失效，不能更新旧 manifest 哈希继续使用。

AI 模拟可查找问题和验证修复，但不冒充真人研究者或出版审看者。M4 的未完成门被保留为 M5 已知限制；开始 M5 不等于 Beta 已发布或三宿主已经实测支持。
