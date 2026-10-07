# M4 Frontier-scoped movement（草稿，待 root 最终收据）

本阶段将一次视觉移动明确为两个范围：`all-frontiers` 与 `current-frontier`。省略 `scope` 仍保持原有 `all-frontiers` 语义；`current-frontier` 只修改当前可见 frontier 的活动布局，并在当前 frontier 下保存规范快照，其他已保存 frontier 的坐标与字节保持不变。移动量使用画布世界单位，不使用 CSS 像素。

正式实现涉及 `MoveScope`、typed `VisualOperation.move.scope`、移动预览、位置修复、四向自然语言指令和 Studio 的“移动范围”选择。自然语言可写“仅当前视图，向右移动 24 画布单位”；未指定范围时使用当前选择的默认范围（默认仍为所有视图）。拖动、对齐、位置修复和文字移动沿用选择的范围；预览和提交使用同一范围，取消或 stale revision 不提交。

## 已有独立证据

- [frontier literal tests](../../independent/README.md)中的新测试 **18/18**，覆盖四向、重复 ID、默认/显式 all、current-only cache、canonical/legacy frontier、pin 与父子选择、隐藏节点拒绝、负坐标、stale revision、undo/redo、JSON reload、预览与 Scene/SVG 一致性。冻结旧 core 的 17 项失败是新 scope 合同断言，不是 17 个独立旧产品缺陷。
- [workload readback](../../independent/workload-readback-report.json) **48/48** grouped relations。输入是未破坏的 grid revision 4，typed `{type:'move', ids:[output], dx:0, dy:-28590, scope:'current-frontier'}`，新候选 revision 5，pin revision 6，collapse revision 7，re-expand revision 8。304 bodies/300 leaves 保持 source、IR、canonical facts；expanded 302 routes，collapsed 2 routes，隐藏边仍属于完整 canonical graph。
- [UI command contract](../../ui-contract-review/README.md)受控 harness **14/14**，并核对 26/26 输入未变。它抽取真实 App callback 与 parser，覆盖四向、十进制、显式/current/default/all scope、重复选择、空选择、非法距离、复合命令拒绝，以及 pointer/preview/recovery 的范围快照。React 未挂载，原生事件、浏览器 paint 和像素新鲜度未认证。
- root 的完整 Studio/build/publication 收据、当前浏览器输入和最终 dist hash 由 root 后续补入；本草稿不得使用旧 CU5 hash 代替新收据。预留：`{{ROOT_FINAL_CHECKS_RECEIPT}}`、`{{ROOT_FINAL_BUILD_ASSET}}`、`{{ROOT_FINAL_BROWSER_RECEIPT}}`。

## 新 workload 的 frontier 语义

从 unbroken grid revision 4 产生新 candidate，不修改历史候选。expanded output 的 local/world Y 为 `1664/1756`，collapsed compact output 为 `262/354`；两者是不同 frontier 的合法位置。root 与 operated network 的位置锚点保持，输入 pin 的 world body 在两 frontier exact；不以所有 unpinned common bodies 的位置相等作为 oracle。current move 不应把历史 collapsed `-28236` 算术结果静默修正或迁移为新证据。

历史普通 move 的算术仍保留：在旧坏 candidate 上 `dy=-28590` 会把 compact local `262` 变为 `-28328`、world `354` 变为 `-28236`。该记录用于解释缺少 scope 的旧行为，不能被新 current-only candidate 覆盖，也不能宣称旧研究包已经被修复。旧 native `353/357` 诊断、旧失败和原 raw 继续保持原字节。

## 当前边界

本阶段证明 typed operation、frontier cache 选择、当前视图预览/提交与静态 Scene/SVG/source/IR 绑定。它不证明全局最少交叉、路线美观、出版尺寸、字体、presented FPS、输入到 paint、模型执行、真人新手可用性或物理出版审看。M4 仍 `partial`，M5 `not_started`，真人参与者 0。

历史 memory continuity research package 在本次产品源变更后属于 stale；不要把其旧 5 席 readiness 当作本阶段新的参与者包，也不要重新准备或分配席位，除非另有明确阶段任务。新阶段没有增加模型执行或 source writeback。

## 进入正式入口前的替换清单

1. 用 root 最终 unified checks 的实际 JS/CSS hash、Studio/publication/strict/build counts 替换三处占位；明确测试计数是否与原套件有重叠。
2. 用 root 最终浏览器 receipt、seed/input hash、视图操作和实际可见状态替换 browser 占位；只报告已完成的 browser 操作。
3. 在 gate 仅追加 `latestFrontierMove`，保留 currentStage、memory research metadata、M4/M5/humans 和历史 failure 字段；不要回写旧阶段 seal。
4. 在 README、`docs/m4-performance.md`、`docs/evidence/README.md` 和 Skill 入口增加本阶段链接；第二个 `##` 之后的历史正文仍 exact。
