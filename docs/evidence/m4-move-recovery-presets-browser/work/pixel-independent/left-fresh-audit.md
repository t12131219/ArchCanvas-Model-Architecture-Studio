# 左侧 fresh 7 PNG 独立像素审核

实际逐一 `view_image(detail="original")` 查看指定 7 张 PNG，并对照同名 public JSON、before DOM 与 after DOM。28 个文件按读取字节绑定 SHA-256；结束复核 28/28 未改变。初始 JPEG 与 later captures 均不继承本报告结论。

**2/7 组有明确像素与配对记录差异。** 7 组 before/after DOM 字节完全相同，仍不能将其作为像素同步证明。差异仅记录证据状态，不推断产品原因。

| 输入 | 实际像素 | 配对 public/before/after | 结论 |
|---|---|---|---|
| mlp-left-fresh | rev19；X66/Y316；越界警告；修复已应用底栏 | rev20；X58/Y316；越界警告；位置已调整底栏 | 版本/位置/底栏不同 |
| mlp-left-preview-fresh | rev20；X110/Y316；预览应用/取消；控制灰置 | 同；预览 SVG rev21、committed rev20 | 粗状态相符 |
| mlp-left-ctrl-s-fresh | rev20；X110/Y316；预览应用/取消；阻止保存底栏 | 同状态 | 粗状态相符 |
| mlp-left-cancel-fresh | rev20；X58/Y316；警告恢复；无预览应用/取消 | 同状态 | 粗状态相符 |
| mlp-left-applied-fresh | rev20；仍预览应用/取消；控制灰置；预览底栏 | committed rev21；无预览条；控制可用；应用完成 | 场景种类/版本/控制/底栏不同 |
| mlp-left-undo-fresh | rev22；X58/Y316；警告；撤销底栏 | 同状态 | 粗状态相符 |
| mlp-left-redo-fresh | rev23；X110/Y316；无警告/预览条；重做底栏 | 同状态 | 粗状态相符 |

cancel 后保留阻止保存底栏在像素和结构记录中一致；记录该现象，未当作同步差异。预览 SVG 候选版本 21 与已提交/footer版本 20 按语义区分。

管理式原生捕获由父代理执行，本代理未重跑。未执行浏览器、产品、测试或构建动作。46% 整页截图不足以认证小字、端口边界、论文审美、性能或实际 presented paint；人工验收人数仍为 0。

完整 28 个绑定及逐图事实见同名 JSON。
