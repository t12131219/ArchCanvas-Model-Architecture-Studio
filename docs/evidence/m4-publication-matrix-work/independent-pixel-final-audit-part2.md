# 后 19 条截图独立末审

范围：captures.json indices 20–38；16 基线 + 3 edited，19 张原始 screenshot.jpg 均通过 tools.view_image(original) 逐张实际查看。仅写本报告和同名 JSON，未改 raw、代码或浏览器/服务，未 stamp。

结论：19 张均与对应 public DOM、Canvas、screen/export receipt 的模型/frontier、85/180 mm 页宽、paper/monochrome、footer rev 一致；整纸和 legend 可见、无 modal，未观察到图像滞后。三份 edited 均显示 legend 下方浅黄说明框和两行文字。

输入绑定：
- `docs/evidence/m4-publication-matrix-raw/captures.json` — 25740 bytes；SHA-256 `1929c84f5d4a7ba0a9e7acc2ce691ef721e3f29c2949fb623057709885152b6e`
- `docs/evidence/m4-publication-matrix-work/raw-final-bindings.json` — 83700 bytes；SHA-256 `9986a4951effbda8109f06c917d98bc8bf3b969d24c54697668eb61d93af6f50`

共绑定 171 个实际 raw 文件、4398756 bytes，全部与 raw-final-bindings.json 冻结 SHA-256/bytes 一致。JSON 保存每例 9 份文件绑定和身份交叉核验。

| index | caseId | 可见页宽/配色 | footer rev | fit | 观察 |
| --- | --- | --- | --- | --- | --- |
| 20 | mlp-level1-paper-85-publication-ui | 85 mm / PAPER COLOR | 8 | 46% | MLP and network expanded; features → Linear 1 → GELU 2 → Dropout 3 → Linear 4 → output; nested network box visible. 无 modal；整纸/legend 可见，无滞后。 |
| 21 | mlp-level1-paper-180-publication-ui | 180 mm / PAPER COLOR | 9 | 46% | MLP and network expanded; same four operator cards inside network; width choice changed to 180 mm. 无 modal；整纸/legend 可见，无滞后。 |
| 22 | mlp-level1-monochrome-85-publication-ui | 85 mm / MONOCHROME | 11 | 46% | MLP and network expanded; four operator cards visible as white fills with dark outlines. 无 modal；整纸/legend 可见，无滞后。 |
| 23 | mlp-level1-monochrome-180-publication-ui | 180 mm / MONOCHROME | 12 | 46% | MLP and network expanded; white outlined four-card network, 180 mm choice visible. 无 modal；整纸/legend 可见，无滞后。 |
| 24 | residual_cnn-level0-paper-85-publication-ui | 85 mm / PAPER COLOR | 1 | 46% | ResidualCNN expanded; image, stem, collapsed blocks ×2, pool, flatten, classifier, output arranged vertically. 无 modal；整纸/legend 可见，无滞后。 |
| 25 | residual_cnn-level0-paper-180-publication-ui | 180 mm / PAPER COLOR | 2 | 46% | ResidualCNN expanded; blocks ×2 remains collapsed between stem and pool; 180 mm choice visible. 无 modal；整纸/legend 可见，无滞后。 |
| 26 | residual_cnn-level0-monochrome-85-publication-ui | 85 mm / MONOCHROME | 4 | 46% | ResidualCNN expanded with collapsed blocks ×2; node faces white with dark outlines. 无 modal；整纸/legend 可见，无滞后。 |
| 27 | residual_cnn-level0-monochrome-180-publication-ui | 180 mm / MONOCHROME | 5 | 46% | ResidualCNN expanded with collapsed blocks ×2; white node faces and 180 mm choice visible. 无 modal；整纸/legend 可见，无滞后。 |
| 28 | residual_cnn-level1-paper-85-publication-ui | 85 mm / PAPER COLOR | 8 | 38% | ResidualCNN and blocks expanded; two collapsed ResidualBlock cards enclosed by blocks, between stem and pool. 无 modal；整纸/legend 可见，无滞后。 |
| 29 | residual_cnn-level1-paper-180-publication-ui | 180 mm / PAPER COLOR | 9 | 38% | ResidualCNN and blocks expanded; ResidualBlock 1 and ResidualBlock 2 remain collapsed; 180 mm choice visible. 无 modal；整纸/legend 可见，无滞后。 |
| 30 | residual_cnn-level1-monochrome-85-publication-ui | 85 mm / MONOCHROME | 11 | 38% | ResidualCNN and blocks expanded; two collapsed white outlined ResidualBlock cards visible. 无 modal；整纸/legend 可见，无滞后。 |
| 31 | residual_cnn-level1-monochrome-180-publication-ui | 180 mm / MONOCHROME | 12 | 38% | ResidualCNN and blocks expanded; two collapsed white outlined block cards, 180 mm choice visible. 无 modal；整纸/legend 可见，无滞后。 |
| 32 | residual_cnn-level2-paper-85-publication-ui | 85 mm / PAPER COLOR | 16 | 17% | Tall CNN paper with two expanded ResidualBlock subcontainers and many colored inner operator cards; sidebar scrolled to activation/conv/norm/Add and ResidualBlock 2 entries. 无 modal；整纸/legend 可见，无滞后。 |
| 33 | residual_cnn-level2-paper-180-publication-ui | 180 mm / PAPER COLOR | 17 | 17% | Tall CNN paper retains two expanded inner blocks and colored operator chain; sidebar remains scrolled inside blocks; 180 mm choice visible. 无 modal；整纸/legend 可见，无滞后。 |
| 34 | residual_cnn-level2-monochrome-85-publication-ui | 85 mm / MONOCHROME | 19 | 17% | Tall CNN paper with both blocks expanded; inner cards are white outlined; sidebar shows activation/conv/norm/Add and ResidualBlock 2. 无 modal；整纸/legend 可见，无滞后。 |
| 35 | residual_cnn-level2-monochrome-180-publication-ui | 180 mm / MONOCHROME | 20 | 17% | Tall CNN paper with both blocks expanded and white inner cards; sidebar scrolled within blocks; 180 mm choice visible. 无 modal；整纸/legend 可见，无滞后。 |
| 36 | residual_cnn-level0-paper-180-publication-edited-reopened | 180 mm / PAPER COLOR | 32 | 42% | ResidualCNN L0 with collapsed blocks ×2 and bottom annotation below the legend; source selector visibly says imported model. 无 modal；整纸/legend 可见，无滞后。 |
| 37 | mlp-level1-paper-180-publication-edited-reopened | 180 mm / PAPER COLOR | 18 | 43% | MLP L1 with expanded network and four operator cards; annotation below legend; source selector visibly says imported model. 无 modal；整纸/legend 可见，无滞后。 |
| 38 | transformer-level0-paper-180-publication-edited-reopened | 180 mm / PAPER COLOR | 41 | 49% | Transformer L0 with three mask inputs, two token/embedding branches, collapsed encoder ×2 and decoder, output projection and output; annotation below legend; imported-model selector visible. 无 modal；整纸/legend 可见，无滞后。 |

编辑说明的精确 SVG tspan 断行（截图确认两行形态；不逐字认证细小字形）：

- index 36: `Each residual block combines transformed features with its skip` / `path. The note preserves model source.`

- index 37: `The network maps input features to class logits. Source evidence` / `stays unchanged.`

- index 38: `Encoder memory feeds decoder cross attention. Visual notes keep` / `canonical tensor bindings intact.`

Canvas 响应外层 revision 与 document.revision 分别保留，不能混用。截图 footer、DOM 和 receipts 一致的是 document.revision。

边界：CNN L2 整纸适配约 17%，不能据此认证细字、连线端点或字体。85/180 mm 使用相同视口适配，物理尺寸由文档/DOM/receipt 支持，不能从纸张像素宽度推定。本审计不构成人工审看、审美验收、印样可读性、字体字节认证或原生性能测试。
