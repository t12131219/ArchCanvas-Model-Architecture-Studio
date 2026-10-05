# 独立只读 journal 与 matrix collection 审查

本次审查不操作浏览器、不执行模型、不调用 `browser_visual_matrix.collect`，不修改正式实现、原始采集或旧封存。两个新脚本只读取输入，重新调用当前冻结正式 core 和 publication normalization，并排他生成新 receipt。

- `independent-journal-three-final-audit.json`：SHA256 `142aaf1b8915301d2801542b1d7fcdee745adfdaec0992047158a568c5191380`，51 个输入 bindings。CNN visual 36→37→38→39→39→39，MLP 20→21→22→23→23→23，Transformer 49→50→51→52→52→52。
- `independent-matrix-collection-final-audit.json`：SHA256 `656323474f5eaba4df710ae67b7413f8bae79d6decfef718e2ee35c7ca445510`，809 个输入 bindings。36 个唯一 baseline、3 个独立 edited-after、234 个 captured 文件与 input 逐字节相同。36 个 core previews 与冻结候选相同，79 个 collect expected 文件与本审查重建结果逐字节相同。

Journal 的 undo 比较 before/undo，redo 比较 committed/redo；完整 SVG/XML 比较保留 tag、所有属性、文本、tail 和子节点顺序，只排除根 `data-revision` 与根 metadata 的 `revision` 数值。三类 redo/save/reopened 完整 XML **包含 revision** 相等，原序列化 DOM 字节也相等。最终 raw Scene 与 reopened 字节相同。source/IR metadata、source facts、rendered node/binding facts、完整 frontier 与 page 在各 clean sequence 内不变。

三类最终 actual document-store envelope 中的完整 Canvas 与 packaged export Canvas 逐字段相同，并从该完整 Canvas 重建的 interactive SVG 与当前 raw DOM 完整 XML 相等。当前 fixture source 字节与 Canvas architecture 内嵌 source 内容和其 digest 相等。这里没有中间每一步完整 Canvas envelope；其间文档一致性由完整 DOM journals 支撑，不能称为中间整份 Canvas 字节证据。

Collection 独立核验 spec 声明的 96 个 implementation/build/core 文件 bindings、另外的 spec/core report、全部 actual store snapshots、完整架构/source/IR、frontier/page、export/screen receipts、全部所采文件、出版输入 digest 与 normalization 完整输出字节。对 manifest 和逐图 review template 核验 `humanAcceptanceCertified=false`、所有人审 criteria/physical/pixel 状态为 pending。

36 个 baseline 最小文字测量为 2.530934–8.575399 pt，仅 10/36 达到建议 7 pt；这不是出版通过。baseline 相对于候选允许 layout 差异，不能宣称所有默认 layout 完全相同。39 例记录 viewport 1280×720、DPR 1；UA 从此前同一 IAB 的已绑定实际观测引用，当前 UA 并未直接读到，hardware/browser version/font bytes 均未知。

CNN 初轮、add/precommit snapshots 和 disabled Undo 尝试均保留，但不计入 clean committed-text-edit 成功样例。`independent-journal-cnn-audit.json` 是当时只审 CNN、尚无 packaged export 的历史范围；`independent-journal-three-raw-audit.json` 是三类 raw 已齐、Transformer 当时尚未 packaged 的历史范围。它们的 false 是当时尚未核到，不覆盖本最终 receipt，也未被重写。

这些审查证明本地文件、完整保存文档、当前正式 Scene 与规范化导出的一致性。截图原生来源仍是操作者记录，像素观感由另份实际 screenshot review 支撑；物理字体、出版人审、真实研究者任务和持续 presented/paint 性能仍未认证。
