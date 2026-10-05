# 19 条编辑 UI 记录的独立末审

只读核对 `edited-ui-journal.json` 的 19 条公开 DOM 记录和对应的 19 SVG、19 AX 文件。3 组已提交 SVG 文本操作通过：撤销还原原文、重做恢复改文；比较时仅移除 SVG `data-revision` 与 metadata `revision`，其余整个 XML 结构完全相同。

| 模型 | 撤销 / 重做 | 保存 / 重开 SVG bytes | 重开 / 最终 raw SVG bytes | 最终视觉 / 存储版本 |
| --- | --- | --- | --- | --- |
| Residual CNN | 2 组结构 exact | exact | exact | 32 / 14 |
| MLP | 2 组结构 exact | exact | exact | 18 / 10 |
| Transformer | 2 组结构 exact | exact | exact | 41 / 18 |

三份最终画布的 canonical architecture、sourceDigest、irDigest 与冻结基线一致。说明 ID、文字、坐标与换行符合独立预期；MLP 和 Transformer 的框高度随一行 / 两行由 35 改为 50，再随撤销 / 重做还原。

CNN 的 `cnn-note-added` 是过渡记录：root 展开，block0/block1 的展开标记保留，但 repeat parent 处于收起状态，因此实际可见 8 个 L0 节点。它不是完整 L2 frontier。说明还在先前深层视图留下的 y2549；下一条 `cnn-l0-note-positioned` 恢复 root-only L0 并移到 y973。后续文本比较使用这个已定位的原文。

5 条 AX 输入框值与同条已提交 SVG 不同：CNN redo，MLP undo / redo，Transformer undo / redo。SVG、修订号与撤销 / 重做 footer 已匹配操作结果；未作后续 DOM input value 或像素采样，原因未知，不能认定为 draft、缓存或异步捕获。所有原始 AX / journal 保留；本审计不认证输入框同步。

保存条目的 footer 仍显示处理中，不能单独证明保存完成。此处持久化证据来自随后“已重开保存的画布”的公开记录和保存 / 重开 SVG bytes exact；重开 / 最终矩阵 raw SVG 也逐字节相同。相机变化作为视图状态单独保留。

19 条记录不等于 19 个研究员任务。未认证人工视觉审看、实际印样、字体、物理可读性、原生性能或研究验收。

详细字段、文件 SHA256、每条 AX 观察与相机记录见 `independent-edited-ui-final-audit.json`。
