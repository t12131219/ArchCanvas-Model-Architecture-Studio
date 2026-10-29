# Tavotto 风格一致性与遮挡复核 · 2026-10-29

已完成第二轮交互模拟和代码修复。问题主要来自外层 Studio 与内嵌预览分别维护样式、浮层和反馈，首轮改造只统一了主要外壳，未覆盖深层状态。

本次继续使用正式项目，不引入 Tavotto 的运行时。Tavotto 在 `/tmp/archcanvas-tavotto-reference-20261029` 的隔离副本中运行，用于浏览器对照。以下“用户反馈”来自实际任务模拟，并非外部用户访谈。

## 用户视角：两边实际操作后的反馈

| 操作路径 | Tavotto 的体验 | 主程序修复前的问题 | 本次调整后的体验 |
| --- | --- | --- | --- |
| 打开顶栏菜单，再用键盘退出 | 灰白菜单；Esc 返回入口 | 外壳已有新色调，但菜单仍依赖普通层叠与容器边界 | 菜单进入浏览器顶层，按视口定位；方向键选择可用项，Esc 返回入口 |
| 打开设置并继续向下操作 | 展开项沿用相同的背景、字号和间距 | 布线抽屉被外层工具条盖住；遮罩因按钮圆角变成巨大圆形 | 抽屉与工具条分区，遮罩铺满；表单、范围滑块、展开辅助项保持中性色调 |
| 查看操作提示 | 浅色短提示，视觉负担较轻 | 顶部绿色横条与画布内深青色 toast 重复；toast 被工具条盖住 | 保留外层反馈，内嵌重复 toast 隐藏；普通提示浅灰、5 秒后消退；错误继续保留到关闭 |
| 展开模块预设、证据收据等多级内容 | 展开内容与主面板保持一致，层级可辨认 | 部分原始小字号、绿色字段和默认 disclosure 样式混杂 | 统一展开标题、箭头、分隔线、嵌套卡片、输入框和滚动区域 |
| 展开构件库和模型配置 | 任务面板结构清晰 | 旧字段、说明文字、库列表和源编辑器提示仍带绿色 | 基础样式中的绿色字面值改为共享主题变量；长列表仍有边界和搜索 |
| 使用缩略导航、缩放和底部工具 | 工具与右侧任务区边界清楚 | 内嵌导航与外层工具各自浮动，容易挤在一起 | 底部工具获得独立一行；缩略导航和缩放留在画布内；导航灰色、视口框蓝色 |
| 进入导出并寻找“生成文件” | 对话框风格与工作台一致 | 对话框与 SVG 预览分别滚动，操作按钮容易滚出窗口 | 固定标题和底部按钮，仅内容滚动；SVG 以缩略预览展示完整范围 |

体验取舍：底部仍保留 Tavotto 风格的圆角工具组，但为它预留 64 px 的独立区域。这样会使用一部分画布高度，换来工具、缩略导航、设置表单和提示之间稳定的边界。

Tavotto 对照实际打开了“更多”、画布“辅助显示”和“背景”，验证了展开样式与 Esc 返回入口。主程序实际检查了模型／视图／排列、选区操作、布线与辅助显示、模块预设、运行证据及嵌套收据、模型配置、构件源码列表、导入和导出。

## 程序员视角：根因与修复

1. **主题并未覆盖原始声明。** `styles.css`、`AuthoringStudio.css`、`PreviewStudio.css`、`ObjectFacts.css` 中大量控件颜色是硬编码，不能只靠修改根变量解决。将界面文字、表单、边框、状态卡片等改用主题变量，并统一源码编辑器的选中与交互状态。图中模型类别和语义图元的配色继续由模型表达。
2. **跨 iframe 的浮动区域互相不知道对方的位置。** 外层工具条由绝对定位改为主面板内的独立底部行，画布导航与内嵌抽屉自然终止在工具区上方。源码抽屉也终止在该行上方。
3. **菜单被工作区裁剪层和 stacking context 约束。** 使用原生 Popover 顶层显示菜单，增加按视口计算位置的函数；底部菜单向上展开，长菜单限制高度并可滚动。保留单菜单、外部点击关闭、方向键和 Esc 行为，补齐操作后返回入口的焦点。
4. **一次通知出现两个可见提示。** 内嵌 toast 已经通过同源桥接发送到主程序，因此在嵌入模式隐藏其重复显示。主程序的普通反馈使用中性表面和蓝色图标，并自动消退。
5. **内嵌默认按钮规则污染了遮罩。** 对遮罩明确设置完整宽高、零圆角以及固定背景，避免被胶囊按钮样式覆盖。深层滚动中的关闭按钮移入完整的固定标题栏，避免单独悬浮压住表单。
6. **展开内容缺少统一组件样式。** 对模块、证据、构件和模型配置统一嵌套 disclosure 的标题、边界和间距；修复统计字段原先上下堆叠的布局。
7. **仍有指向已删除 Summary 面板的旧文案。** 在嵌入桥接适配中把文档抽屉改名为“已保存与导入文档”，改写底部指引，并隐藏迁移来源的英文编号标题。
8. **导出窗口的滚动结构不适合任务完成。** 标题和操作区固定，SVG 缩略展示；屏幕缩略样式不改变实际导出的 SVG 尺寸、几何或预检计算。

代码入口：

- [工作台菜单和焦点管理](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/WorkspaceUI.tsx)
- [菜单视口定位](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/workspaceMenuPosition.ts)
- [共享界面样式](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/WorkspaceUI.css)
- [嵌入预览界面样式](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/public/preview/yworks_edge_router_lab/studio-embed.css)
- [嵌入文案适配](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/public/preview/yworks_edge_router_lab/studio-bridge.js)
- [导出对话框](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/PreviewExportDialog.tsx)

## 附带发现并修复的真实导出失败

实际点击生成 SVG 时，Transformer 整图和 Feed-forward 详情都被现有服务端文本预算拒绝。DOM 检查发现，详情 SVG 中的 `metadata#archcanvas-preview-document` 包含约 **2,979,626 字符的完整编辑文档**，该详情的可见文字仅 134 字符。

在 [发布 SVG 清理过程](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/previewPublication.ts) 中移除这份特定的嵌入编辑文档；完整编辑内容继续由编辑 JSON 承载，发布来源绑定由导出收据承载。其他 metadata 保持现有处理。服务端限额保持原值。

修复后，当前 Transformer **整图 SVG 实际生成成功**，检查到可见 SVG 文本为 2061 字符、重复文档 metadata 为 0，并出现查看、下载与收据入口：`/api/exports/58d12d8d15ff4fe6bd533f3a57edbe32/figure.svg`。新增的大 metadata 回归样例也已加入现有真实 DOM 清理测试。

## 验证与边界

- `npm run build` 通过，仍有原有的超过 500 kB bundle 提示。
- `npm run audit:preview` 通过，正式主程序的预览权威边界检查通过。
- 本轮相关测试 **71 通过、0 失败、1 跳过**。覆盖菜单边界计算、任务面板、桥接、选区／导航、应用布局、请求顺序及导出绑定等。跳过项为现有真实 DOM SVG 测试：沙箱不能启动其独立 Chromium。上述实际 SVG 生成通过应用浏览器完成了验证。
- 最后标题栏调整后另复跑桥接与请求顺序测试，全部通过，见 `bridge-final.log`。
- `git diff --check` 通过；预览集成 manifest 的全部 bytes/SHA256 与当前文件匹配。
- 浏览器最终实测尺寸为 **970 × 835**。菜单矩形位于视口内，真实点击命中菜单表面；选区 ArrowDown 跳过禁用项，Esc 返回“选区操作”；导入弹窗聚焦“关闭导入”，关闭后返回“模型”。
- 提示可见时，画布底部为 y=737，工具条顶部为 y=745，相隔 8 px；iframe toast 的实际 `display` 为 `none`。提示背景为 `rgb(247,247,244)`。
- 在布线抽屉打开的实测 DOM 状态中，对非 SVG 界面元素检查文字、背景和边框，未检出绿色控件。模型类别色块不纳入界面残留判定。
- 尝试设置 680 × 640 的浏览器尺寸后，工具实际仍返回 1280 × 720，因此不声称已完成该尺寸的真实浏览器验证；窄视口和短窗口的菜单几何由单元测试覆盖。
- 第一轮已记录的 6 个旧基线测试失败不在本轮相关测试结果内，见 [第一轮报告](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/ui-tavotto-redesign-20261029.md)。本报告不将局部通过表述为全仓测试通过。

交互检查中执行了当前图的连线优化和进入编辑副本；检查结束已通过文档列表恢复原有 Transformer 文档的查看模式。参考 Tavotto 标签页及本轮临时参考服务已关闭。

## 截图与可复核证据

- [布线抽屉修复前](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/ui-tavotto-consistency-20261029/studio-routing-before.jpg)
- [中性提示与抽屉分区修复后](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/ui-tavotto-consistency-20261029/studio-feedback-after.jpg)
- [Tavotto 展开参考](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/ui-tavotto-consistency-20261029/tavotto-disclosure.jpg)
- [主程序模块展开修复前](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/ui-tavotto-consistency-20261029/studio-expansion-before.jpg)
- [主程序模块展开修复后](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/ui-tavotto-consistency-20261029/studio-expansion-after.jpg)
- [模型配置展开](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/ui-tavotto-consistency-20261029/studio-library-expanded.jpg)
- [构件多级展开](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/ui-tavotto-consistency-20261029/studio-assembly-expanded.jpg)
- [证据多级展开](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/ui-tavotto-consistency-20261029/studio-evidence-expanded.jpg)
- [导出操作区和生成结果](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/ui-tavotto-consistency-20261029/studio-export-after.jpg)
- [菜单层级](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/ui-tavotto-consistency-20261029/studio-menu-after.jpg)
- [最终查看界面](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/ui-tavotto-consistency-20261029/studio-final.jpg)
- [浏览器测量记录](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/ui-tavotto-consistency-20261029/browser-checks.json)
- [测试日志](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/ui-tavotto-consistency-20261029/tests.log)
