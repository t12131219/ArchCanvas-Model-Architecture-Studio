# Fresh up / down / right 九张 PNG 独立核对

九张原始 PNG 已逐张 view_image(original)。4 张粗状态一致，5 张与同名 public 不一致；全部 before/after DOM 字节相同仍不能认证截图匹配。

| stem | 分类 | 差异 |
| --- | --- | --- |
| mlp-right-fresh | observed-coarse-state-consistent | 无粗状态差异 |
| mlp-right-pin-alias-saved | same-stem-image/public-mismatch | footerSaveFailureNotVisible |
| mlp-down-fresh | same-stem-image/public-mismatch | revision, targetY, warnings |
| mlp-down-preview-fresh | same-stem-image/public-mismatch | kind, targetY, warnings, previewBanner, saveExportDisabled |
| mlp-down-cancel-fresh | observed-coarse-state-consistent | 无粗状态差异 |
| mlp-down-applied-fresh | same-stem-image/public-mismatch | kind, revision, previewBanner, saveExportDisabled, footer |
| mlp-up-fresh | same-stem-image/public-mismatch | revision, footer, inspectorY |
| mlp-up-preview-fresh | observed-coarse-state-consistent | 无粗状态差异 |
| mlp-up-applied-fresh | observed-coarse-state-consistent | 无粗状态差异 |

right-pin-alias-saved 的 public 明确保存失败；画面仍显示先前无冲突 footer，不能把文件名、alias 或 pin 当保存成功。down-fresh 画面 rev15 / Y316 无警告，public rev16 / Y368 有警告；down-preview 图仍 drag 警告；down-applied 图仍 preview。没有独立确定工具、渲染或调度原因，不据此判断产品状态 bug。

36 原始文件 SHA256 末复核通过。此报告不修改原件、不认证字体、人审、美感、物理可读性或性能。
