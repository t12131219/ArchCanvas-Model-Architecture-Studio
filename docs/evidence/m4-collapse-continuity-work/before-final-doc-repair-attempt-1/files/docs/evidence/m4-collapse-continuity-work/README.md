# 折叠后的空间连续性修复准备

已完成只读诊断、合同与前状态副本，并仅修改 `studio/src/core/document.ts`，独立测试与 root 构建/浏览器验收待完成。正式工程从头实现，不读取失败原型；本轮不执行模型，不修改历史文档或现有 dist。[implementation-review.json](implementation-review.json) 记录源码与前状态版本。

实际 CNN rev14 保存了 root、两个 block 的展开记忆，Repeat 本身已折叠。公开画布只显示 root 概览；`document.ts` 却使用所有 expandedIds 作为缓存键，使 `root|block0|block1` 查询失败。已有 `root` 快照中的 pool localY 为362，当前却为1938。

[diagnosis-attempt-1/diagnosis.json](diagnosis-attempt-1/diagnosis.json) 保留 22个输入前后 hash 与精确副本，独立祖先遍历证实 raw key miss / effective key hit。公开 SVG 的前 body bottom416、pooltop2030，因此 body gap1614；Repeat backplates 还延伸到423，[outline-supplement.json](diagnosis-attempt-1/outline-supplement.json) 明确其 **完整可见轮廓 gap1607**。不能混用前 body 与完整轮廓。

建议采用 **有效可见展开层级** 作为新缓存键：只有祖先全部展开时，当前容器的展开状态才进入 displayed frontier。原 expandedIds 保留所有隐藏记忆，隐藏节点 layout 也保留原值。恢复目标快照只写可见、未受固定子树保护的节点，且保留正在操作的容器锚点；手动 move 仍更新各快照。

兼容历史 key 时按同样祖先规则投影，精确新 key优先；若多个旧 key 对可见坐标存在冲突，采用保守规则，不能随便选一个重排。节点 identity 原合同允许任意字符串，现有 `|` key 分隔有既存歧义；新实现不扩展这种歧义，也不能默默把无法解析的 key当作空概览。

已坏旧文档的首次 toggle 还有一个陷阱：不能在恢复前把当前伸长布局写入已有的紧凑 effective key，破坏唯一正确快照。保留有效快照会让后续展开→折叠恢复紧凑视图；用户 move 已同步进去。但若用户直接编辑JSON，当前与缓存谁更新不可证明，需保守处理并明确范围。普通 view操作路径优先，不能承诺任意冲突历史JSON自动修复。

[repair-contract.json](repair-contract.json) 列出了直接祖先折叠、重新展开、手动移动、固定、undo/redo、save/reopen与旧快照兼容要求。已有 `visual-fixture.test.ts` 用 block2→block1→Repeat 顺序逐个收起，未覆盖直接收起祖先保留隐藏展开的情况；这应由独立验收增加真实失败链，而非只测试新key函数。

root 已允许实现；新缓存按可见展开集合采用 JSON key，并只保存可见位置。旧 key 的有效祖先投影读取、冲突保守保留和坏旧 collapsed cache 保护均已写入源码。旧诊断、合同、原文档与预修复失败原件不变；本阶段尚不认证浏览器视觉恢复、出版或性能，M4仍partial、真人0。
