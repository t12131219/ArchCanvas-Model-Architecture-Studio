# 初始 up / down / right 八张截图独立核对

八张原始 JPEG 已逐张通过 view_image(original) 实际查看。2 张与同名 public / DOM 粗状态一致，6 张存在修订号、footer、preview 或位置不一致。原件全部保留，不据局部位置正确判验收通过。

| stem | 分类 | 画面相对 public 的差异 |
| --- | --- | --- |
| mlp-drag-up | same-stem-image/public-mismatch | revision, footer, inspectorY |
| mlp-up-recovery-preview | observed-coarse-state-consistent | 无粗状态差异 |
| mlp-up-repair-applied | observed-coarse-state-consistent | 无粗状态差异 |
| mlp-drag-down | same-stem-image/public-mismatch | revision, footer |
| mlp-down-recovery-preview | same-stem-image/public-mismatch | kind, previewBanner, saveExportDisabled, targetY, warnings, footer |
| mlp-down-repair-applied | same-stem-image/public-mismatch | kind, revision, previewBanner, saveExportDisabled, footer |
| mlp-drag-right | same-stem-image/public-mismatch | revision, footer |
| mlp-right-no-repair | same-stem-image/public-mismatch | footer |

尤其 down-repair-applied 画面仍是 preview、rev8、保存导出禁用，而 public 是 committed rev9；down-recovery-preview 画面仍是 drag 警告、Y368，而 public preview 已 Y316。根因尚未独立确定。新 fresh capture 应新命名、另审，不能覆盖或补认旧图。

字段、观察、24 文件 SHA256 与边界见 JSON。此报告不认证人审、美感、物理可读性、像素端点或性能。
