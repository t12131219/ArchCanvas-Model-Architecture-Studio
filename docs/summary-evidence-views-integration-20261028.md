# Summary 源码、CPU 轨迹与合并证据视图接入

日期：2026-10-28。重叠能力使用 Summary 原生语义引擎；Studio 保留菜单、层级树、对象/图例/页面面板、折叠区及正式源码事务边界。本阶段接入文档已有运行记录的查看，不新增模型执行。

## 功能与面板衔接

| 功能 | Studio 面板与入口 | Summary 原生行为与完整性要求 |
| --- | --- | --- |
| 源码 / CPU 轨迹 / 合并 | 对象 → Summary 语义切面 → 证据视图 | 同一 canonical IR 上切换 `mode`，不另建宿主图元或推断运行事实 |
| 样例选择 | 合并模式显示 CPU 补证样例 | 精确记录原始 run index/case/status/truncated/replay；拒绝越界、非整数及无效记录 |
| 无 CPU 证据 | CPU 轨迹选项禁用，并显示无记录说明 | 必须存在原始 runtime-observations 才允许 CPU mode；合并允许纯源码事实 |
| F0/F1 与六档切面 | 继续使用已有折叠控件 | 保留当前证据模式和所选样例；原版前沿、角色、布线、完整归属账本继续负责投影 |
| 跨视图定位 | 原 Studio 完整层级树及定位入口 | 按 canonical identity 和父层级识别来源；定位另一视图对象时原生切换 mode，返回恢复原切面 |
| 运行记录详情 | CPU 记录与合并边界折叠区 | 展示原 IR 中记录、摘要及已匹配/未放置边界；明确切换不执行模型、未观察路径未知 |
| 撤销 / 重做 / 返回 | 原 Studio 工具栏及语义切面返回按钮 | 由 Summary 同一事务维护图、历史、选区与切面；相机按对应视图恢复 |
| 编辑 / 视图双模式 | 原 Studio 双模式按钮与组装编辑面板 | 即使从 CPU 子集进入编辑，也从完整 IR 建立独立组装稿；baseline 不裁剪、不取得 Python 写回权 |
| 保存、刷新、编辑 JSON | 顶栏保存与原有导出入口 | 原始 IR、证据模式、样例和原生布局/相机随文档恢复；不自动执行或重新分析来源路径 |

`studio-semantic.js` 只增加桥接校验、inspector 投影和跨证据模式定位；32 个登记的 Summary 原生 JS 模块保持原样。面板提交 `semantic-view` 消息，Worker 返回已提交 snapshot 后再更新宿主控件。测试等待面板实际 option.disabled；Playwright 的 isDisabled 会把标签中的 option 重定向到 label.control（整个 select），不能据此判定单个选项是否禁用。还通过 bridge 直接反例确认无轨迹模式被拒绝。

## 来源与合并限制

5 个预算内模型含归档运行记录：BranchMLP（87 节点、4 样例）、TinyCNN（32、1）、ReusedRecurrent（46、1）、SharedStack（109、2）、IndependentStack（125、2）。原始运行状态和 replay 记录完整保留；本次打开不会认证其产生环境，也不授予正式源码绑定。

当前目录所有 IR 的 `source_runtime_index.regions` 均为空。合并视图因此保留源码未知边界，不根据调用名称、相似结构或归档“passed”字样伪造源码内联；CPU 轨迹模式仍可查看完整运行观察。伪造 region、截断轨迹、replay 不匹配或 source_unchanged=false 均不能获得调用绑定。正式新执行需继续接入隔离/profile/receipt，不能启用原型旧 subprocess 代替。

## 自主测试与发现

新增 9 项专项核对真实五模型全部样例、F1、完整 IR/归属账本、原生 JSON 与文档恢复、相机返回、精确身份跨模式定位，以及非法 mode/index 和 malformed run 元数据的原子拒绝。显式 run 只允许 merged；数组外的伪造 `.length` 不构成运行记录。

浏览器直接操作主程序菜单、折叠面板、双模式和保存，核对完整 baseline，监视源码分析/runtime/事务写请求。首轮脚本误用不存在的 origin.documentSha256，已改为验证实际 caseId/irDigest/sourceSha256 与完整 baseline；第二次发现 Playwright isDisabled 对标签内 option 实际检查整个 select，已改为等待并核对原生 option.disabled，加测 bridge 拒绝无轨迹模式。失败证据保留，不计作通过。一次沙箱 Chromium 启动被 setsockopt 限制阻止，另以允许本地浏览器套接字的执行环境复核。

## 验证与剩余范围

本阶段最终结果及当前字节清单记录于 [validation](evidence/summary-evidence-views-20261028/validation.json)；不覆盖目录、D0 或更早阶段冻结证据。整体迁移仍在进行：3 个大图的传输/存储/历史/取消压力、新 CPU 执行的正式隔离与 receipt、测量反馈 adaptive-frontier、D1 旧正式依赖拆分继续保留为未完成项。


本阶段最终验证：完整前端 926 项（925 通过、0 失败、1 沙箱 Chromium 跳过）；主专项和独立副本各 100 项，真实 Chromium 37 项通过。主构建与独立副本构建、8 个最终运行/测试文件的独立字节对照、109 HTTP 资源核验通过。32 原生 JS 与 45 目录资产保持来源一致。详见 [证据视图验证](evidence/summary-evidence-views-20261028/validation.json)。本阶段没有后端执行改动，不挪用旧后端计数；整体移植仍在进行。
