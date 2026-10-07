# 左侧初始 8 JPEG 独立像素审核

实际逐一 `view_image(detail="original")` 查看 8 张 JPEG，并对照同名 public JSON 与 DOM 文本。24 个输入按读取字节绑定 SHA-256；结束复核 24/24 未改变。范围仅限本报告的绑定，不继承到后来新增截图。

**5/8 组有明确像素与配对记录差异，不能作为同步捕获通过证据。** 这些差异是证据状态不同步；未据此推断产品原因或人工验收。

| 输入 | 实际像素 | 配对记录 | 结论 |
|---|---|---|---|
| mlp-expanded-baseline | rev1；保存/导出正常外观；源码导入底栏 | rev1；正在处理；保存/导出 disabled | 底栏/控制状态不同 |
| mlp-drag-left | rev1；X66/Y316；已保存；越界警告 | rev2；X58/Y316；位置已调整 | 版本/位置/保存状态不同 |
| mlp-left-recovery-preview | rev2；X58/Y316；越界警告；无预览应用/取消 | recovery-preview；X110/Y316；无 warning；应用/取消 | 场景种类/位置/控制不同 |
| mlp-left-preview-ctrl-s | rev2；X110/Y316；预览应用/取消；保存/导出灰置；阻止保存底栏 | 同状态；preview SVG rev3、committed rev2 | 粗状态相符 |
| mlp-left-preview-cancel | rev2；X58/Y316；警告恢复；无预览应用/取消 | 同状态 | 粗状态相符 |
| mlp-left-repair-applied | rev2；仍预览应用/取消；保存/导出灰置 | committed rev3；应用完成；控制可用 | 场景种类/版本/控制不同 |
| mlp-left-repair-undo | rev4；X58/Y316；警告；撤销底栏 | 同状态 | 粗状态相符 |
| mlp-left-repair-redo | rev4；X58/Y316；警告；撤销底栏 | rev5；X110/Y316；无 warning；重做底栏 | 版本/位置/警告/底栏不同 |

cancel 后保留的“请先应用或取消位置修复预览，再保存画布”底栏在像素和配对记录中均存在，因此未作为不同步差异。预览场景 SVG rev3 与已提交/footer rev2 的区别按预览语义记录，不单独误判为版本错误。

46% 整页截图不足以认证小字可读性、每个端口连接的边界、论文发布审美、原生输入、性能或实际 presented paint。未运行浏览器操作、产品测试、构建或性能脚本；仅写本审核输出。

全部 24 个文件字节数、SHA-256、解析事实和逐图观察见同名 JSON。
