# 最终采集绑定链独立审计

全部核对通过：352 frozen raw 文件与当前 bytes/SHA 完全一致；352 raw/stamped 映射中 313 份字节不变，39 份仅增加 screenshotDigest、browserSceneDigest，全部原始 JSON 值保留。浏览器 Scene 摘要用正式 semantic_svg_digest 只读计算。

39 条 stamp CLI 记录均 exit 0，stdout 精确等于 stamped receipt，stderr 为空。collect 记录 exit 0，stdout 字节精确等于 sealed manifest，stderr 为空。234 份 sealed 采集文件精确等于 stamped 对应六类文件。

36 baseline 覆盖全部 spec variants / 9 authored frontiers（Transformer 16、MLP 8、CNN 12）；三个模型各 1 edited，共 39 例。39 个明确 /api/exports/{id}/figure.svg 服务 ID 互异；117 份服务 SVG/receipt/document 与 raw 副本字节相同。39 条 journal 的 DOM、capturedAt、storage/visual revision、截图 SHA、export URL/artifact ID 精确匹配 raw。

外层 orchestration 的 exit 1 / post-success Path.returncode AttributeError 保留，正式 39 stamp + collect 成功记录与该外层错误分开。此次未重复命令。原进程历史来自绑定记录；本审计核对当前文件/记录的一致性。

输入绑定：
- `docs/evidence/m4-publication-matrix-work/raw-final-bindings.json` — 83700 bytes；SHA-256 `9986a4951effbda8109f06c917d98bc8bf3b969d24c54697668eb61d93af6f50`
- `docs/evidence/m4-publication-matrix-work/raw-to-stamped-bindings.json` — 313693 bytes；SHA-256 `cc623a1570a3f2c31e110eac839925057c5f716cb697322aa2c2befb3e2d71be`
- `docs/evidence/m4-publication-matrix-work/stamp-and-collect-commands.json` — 61721 bytes；SHA-256 `0dbf8824ea7b8d7c249d1d95b12b6ee394b04215672ccb9a7b0e152837407662`
- `docs/evidence/m4-publication-matrix-work/stamp-collect-orchestration-note.json` — 1120 bytes；SHA-256 `4ed9297a24ed108e60f486f30a24c6a0682769cf7f73e1287e30d2d6fa75066a`
- `docs/evidence/m4-publication-matrix-work/browser-journal.json` — 1538682 bytes；SHA-256 `9bc6317718fe8c66929439b0e7371ffd27fab75442ce0d796ab28f9e0c8bd107`
- `docs/evidence/m4-publication-matrix-work/matrix-collect.json` — 223429 bytes；SHA-256 `55df9000f42857bca9dc8ce2f75fe097b99ea90fae94ad077810225e05162593`
- `docs/evidence/m4-publication-matrix-work/matrix-collect.stderr.txt` — 0 bytes；SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- `docs/evidence/m4-publication-matrix-raw/captures.json` — 25740 bytes；SHA-256 `1929c84f5d4a7ba0a9e7acc2ce691ef721e3f29c2949fb623057709885152b6e`
- `docs/evidence/m4-publication-matrix-stamped/captures.json` — 25740 bytes；SHA-256 `1929c84f5d4a7ba0a9e7acc2ce691ef721e3f29c2949fb623057709885152b6e`
- `docs/evidence/browser-visual-matrix-publication-final/manifest.json` — 223429 bytes；SHA-256 `55df9000f42857bca9dc8ce2f75fe097b99ea90fae94ad077810225e05162593`
- `.archcanvas/browser-visual-matrix-publication-final/spec.json` — 79016 bytes；SHA-256 `847b40ea74b474c2853263abd9557971af9cf386ef1f51c8f3194e1ee1d45625`
- `scripts/browser_visual_matrix.py` — 32360 bytes；SHA-256 `6f79036c388a0a725d27a5f3e063eda1b13f7f370a95e735565cd3aff921afac`

冻结 raw 总 13644122 bytes；sealed 234 采集文件总 9695623 bytes。verified_spec 只读核验 21 implementation + 3 build + 72 core + 1 report = 97 绑定。末尾重读全部绑定工件，未发现漂移。

| 类别 | 数量 | 核对结果 |
| --- | ---: | --- |
| frozen raw | 352 | bytes/SHA exact |
| raw/stamped | 352 | 313 exact + 39 only digest additions |
| stamp CLI records | 39 | recorded exit 0 / exact stdout / empty stderr |
| collect CLI record | 1 | recorded exit 0 / stdout exact sealed manifest |
| sealed capture files | 234 | byte exact stamped |
| explicit service copy files | 117 | byte exact raw |
| browser journal | 39 | DOM/time/distinct revisions/shot SHA/URL/ID exact |
| frozen spec bindings | 97 | unchanged |

边界：只读字节和记录审计，不构成原采集/进程历史的独立现场见证。截图内容观察见独立像素报告；不认证人工验收、字形/字体、连线端点、原生性能或印样可读性。sealed 保持 pending-human-review / humanAcceptanceCertified=false。
