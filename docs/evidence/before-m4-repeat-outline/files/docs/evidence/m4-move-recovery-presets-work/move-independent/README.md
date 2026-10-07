# 移动诊断与显式位置修复独立复核

审查者：AI 子 Agent `/root/move_contract_review`。只改新增独立测试与本目录证据，未改产品源码、旧 raw、旧 seal 或历史报告。此次属于代码及独立夹具验证，不计真人研究者、出版审看、实际浏览器交互或呈现帧率验收。

## 最终可复核结果

最终收据是 `attempt-3/command-receipts.json`，对应 Node `v24.19.0`。两条命令都在 `/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio` 执行：

1. `/home/fzg/.nvm/versions/node/v24.19.0/bin/node --experimental-strip-types --test --test-isolation=none tests/move-recovery-independent.test.ts`：2026-10-05T12:57:10.306459Z 至 12:57:10.545819Z，退出码 0，**10/10**。
2. `/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/node_modules/.bin/tsc --noEmit`：2026-10-05T12:57:10.545942Z 至 12:57:12.794626Z，退出码 0。

13 个输入文件在两命令前后字节摘要相等，`inputsStable=true`。每次命令的 stdout/stderr 完整保存到相应 `command-N.log`；输入原字节另存 `source-snapshot/`。可用 `run-audit.py <全新目录名>` 重跑收据，不复用或覆盖已有目录。此次未执行产品全套测试或 build；root 的全套/build 收据属于其自身范围。

## 独立测试范围

测试手写 canonical architecture、两层容器、typed ports、同 tensor fanout 和固定无关对象；不读取历史 capture，不借用产品 router 的路径解析、候选生成或碰撞 helper 计算期望值。手工坐标为 root `(50,92)`、network local `(30,162)`、first local `(30,62)`、second local `(30,162)`，对应 first 的公开 body `(110,316,194,62)`。

- 四向自由移动 ±52，始终保留精确手工位置。左移越界 22；上移进入标题；下移与 second 重叠 14；右移保持正常。新增越界诊断使用展示别名。
- 同源 fanout 使用一个 canonical 输出端口；固定输入端点由独立算式 `50+30+194/2=177`、`92+62+62=216` 验证。
- 恢复 Scene 的 body、祖先标题、父范围和 incident routes 用独立几何检查；路径必须正交、绑定 canonical ports、处于 bounds 内。污染控制可检出故意进入标题与重入端点 body 的错误路径。
- ready 方案未修改原 Canvas/history；预览 Scene/SVG 与 guarded apply 一致；一次提交、一次 undo/redo；源架构、aliases/styles、annotations、legend、page、pins 和无关 layout 不变；所有已存 frontier 对所移最高对象只增加对应 dx/dy。
- 选中容器整体修复只移动最高根，子节点 local 不变；无关 pinned 对象完整 SceneNode 不变。
- selected pin、descendant pin、隐藏和未知对象返回 unavailable；已有无关 Output/spare 重叠仍保留，不将局部修复说成全局无冲突。
- 内部子节点 local x=-22 的越界无法靠整体平移修复。即便另有 17 个障碍，也拒绝方案；新版 helper 提前给出“选择内部冲突对象”的原因。
- 新反例证明 severity gate 有必要：两个兄弟占据上下槽位，first 右移到 x=346 后 body 与 incident routes 都畅通，但 parent width 从 254 增至 490。同一 network/outside 诊断 pair 的面积从 `14×8=112` 增至 `194×8=1552`，没有新增 pair ID。方案返回 unavailable，拒绝扩大既有无关固定对象冲突。

最后一项验证了真实的几何程度增长；未以产品 severity 函数计算 expected。其他 ready 结果亦检查没有新增诊断 signature。

## 源码审查结论与范围

`layoutRecovery.ts` 在 Scene 上限定可见对象，保护其 pinned 子树；最多检查 64 个候选。它拒绝所移子树相关对象、标题、越界与 incident route 冲突，并检查无关可见对象的位置/尺寸不变。候选不写源模型，也不在自由拖动、`buildScene` 或 pointer release 时隐式 clamp。

新增 severity Map 对已有相同 signature 比较 body 重叠面积、header 重叠面积、outside 距离和 blocked 路线侵入总长度。header 程度计算额外包含 4 单位预留；它是代码中的布局保护度量，不等同像素标题边界。blocked 度量是一个诊断所列对象的侵入长度总和，未认证每个障碍的单独侵入都单调，也未认证箭头美观或所有弯折必要。现有源码诊断不带 layout code，因此不会被位置修复改变或伪装为已解决。

新增诊断不改 nodes、canonical ports 或已有路径的几何；既有 73 份冻结几何 oracle 不比较 diagnostics，故不应通过改手工锚点去适配该历史合同。该条是源码/合同审查，不替代 root 的现行全套结果。

`App.tsx` 的 active recovery 必须绑定同一 CanvasDocument 引用、单对象 selection 与 plan id；apply 前再核 document 引用。selection 变化、取消、普通手势和模式切换清掉预览。save callback（含 Ctrl+S）检测 active recovery 并返回提示；保存及导出论文图按钮都禁用。源码可证明这些 guard 存在；实际 DOM disabled、键盘取消与保存/重开仍需 root 的真实浏览器记录。

公开 `data-scene-kind` 放在现有 `.publication-scene` wrapper 最合适，因该 wrapper 同时持有 actual rendered SVG 与 canonical pinned/expanded ids。当前代码已采用 `committed`、`move-preview`、`recovery-preview`，并同处公开 `data-committed-revision`。审查确认位置与表达式一致：预览可持有 prospective SVG revision+1，但 wrapper 的 committed revision 仍取 current CanvasDocument。新浏览器 journal 应一起采集二者，不能将预览 SVG revision 当成已提交/已保存操作。

## 保留的失败与先前结果

`attempt-1` 的 focused 为 9/10、退出码 1，strict 为退出码 0；两次的 13 输入仍稳定。失败来自本独立夹具把新 blocker 设为未连接节点并采用长 label，使其与 first 共处自动 rank 行，容器内容最小宽度成为 511.68，违反原先手算 254 的夹具前提。没有把 511.68 直接替换为 expected；修正为短 label 和 typed blocker→first data edge，独立链级别恢复单列，保留手算 254/490。root 的 `../root/studio-full-1.log` 同样记录了该旧夹具失败，不用后来的绿色 focused 覆写它。

`attempt-2` 的 10/10 focused 和 strict 都退出码 0。随后增加一条必要断言：侧移反例的 incident routes 也确实畅通，排除仅由旧 route guard 拒绝的解释；`attempt-3` 是最终稳定测试版本。更早仅有工具输出的 5/5、9/9 运行不混入本次最终收据。

本目录清单仅绑定静态报告、命令收据/log、输入 snapshot 与审计脚本，不绑定可变服务 store/log，也没有浏览器操作或用户模型执行。
