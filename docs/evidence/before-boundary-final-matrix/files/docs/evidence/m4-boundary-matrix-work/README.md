# 当前构建浏览器矩阵采集工作区

此目录只接收 `index-Cr_xKW9U.js` 与最终 Python frontend 的新证据。冻结矩阵是 `.archcanvas/browser-visual-matrix-boundary-final`，包含 36 个 baseline 变体、9 个展开 frontier，以及每个模型另存的 edited-after 要求。准备合同不会继承旧 39 例覆盖，也不证明像素内容、性能、活动取消、出版人审或真人任务。

正式 source/build、3644-binding seal 和旧目录保持冻结。这里的 `capture_workflow.py` 只封装操作者已经保存的当前字节。它调用正式项目现有的 `scripts/prepare_hierarchy_matrix_capture.py` 合同，不操作浏览器、不发 HTTP 请求、不触发导出、不注入状态、不搜索替代 artifact。旧 helper 只作为当前正式文件复制与拒绝合同；旧矩阵素材不会被用作新采集输入。

## 最少原始观测

每例先通过真实 UI 设置 frontier/page、保存、导出整个文档，并在导出完成后读取**本次当前直接链接**。通过只读 DOM 读取并另存 `raw/<case>/dom-observation.json` 与 `.publication-scene` 的完整 outerHTML `browser-scene.svg`；另存原生截图 `screenshot.jpg`。初始 JSON 不包含 `actualStoredEnvelope`，工具随后将生成带 snapshot 声明的新 JSON。

- `caseId`、当前 `variantId`、`state=baseline|edited`、实际 `capturedAt`（ISO 时区）、当前 `studioUrl`。
- 当前 SVG attributes/metadata 中的 `documentBinding={documentId,revision,sourceDigest,irDigest}`。
- 当前页面控制值 `pageSpec={widthMm,preset}`、完整 `expandedIds`，不得只留可见的一部分。
- `environment.userAgent`、实际 `viewport={width,height}`、`devicePixelRatio`。不知道的 `browserVersion` 与 `hardware` 显式为 null；`fontEvidence=[]` 表示未知。若 UA 来自此前同一 IAB 观测，必须保存原始出处/hash/scope 并在 limitations 中说明它不是当前 DOM 观测。系统硬件列表或构建文件不证明浏览器环境。
- `.paper` 实际 transform 和当前 Scene `getBoundingClientRect()` 的 `x,y,width,height`（可保留其余 rect 字段）。
- 实际加载的 JS/CSS `path,url`；本次精确 `actualExport.observedUrl`。
- `captureScope=studio-viewport` 和真实 `limitations`。

采集前固定真实 viewport，再 fit 并读取当前值。改变 viewport 前采的原始材料保留到独立 excluded 路径；不替换原文件，也不把它计作最终 baseline。

## 原生截图字节

按当前 CUA 文档调用截图。当前工具已返回 `Uint8Array`，操作者可使用允许的文件接口 `node:fs/promises.writeFile(absoluteNewPath, screenshotBytes, {flag:'wx'})` 排他保存**同一返回值的原始字节**；不要重编码、改尺寸或复用旧截图。相应截图调用及落盘记录需保留在原始 journal。

如果只能得到原生 tool image block 的 base64 `data`，将那个实际字段另存为新文本文件，再使用 `save-jpeg --base64-input <new-base64-file> --output <new.jpg>`。此命令只解码完整 JPEG 字节并新写 sidecar，不能独立证明原生来源。工具禁止猜截图 API；使用已返回的 documented API。

## 每例封装和索引

以下命令在正式工程 cwd 执行，所有 `<case>` 都指实际保存的新 case。`--raw` 为原始 DOM 文件；bind 不修改它。实例服务预计 `http://127.0.0.1:8906/`，实际 store 必须是 `/tmp/archcanvas-m4-boundary-matrix/documents`。

```bash
.venv/bin/python docs/evidence/m4-boundary-matrix-work/capture_workflow.py verify-frozen

.venv/bin/python docs/evidence/m4-boundary-matrix-work/capture_workflow.py bind-observation \
  --raw docs/evidence/m4-boundary-matrix-work/raw/<case>/dom-observation.json

.venv/bin/python docs/evidence/m4-boundary-matrix-work/capture_workflow.py case \
  --case <case> \
  --browser-scene docs/evidence/m4-boundary-matrix-work/raw/<case>/browser-scene.svg \
  --screenshot docs/evidence/m4-boundary-matrix-work/raw/<case>/screenshot.jpg

.venv/bin/python docs/evidence/m4-boundary-matrix-work/capture_workflow.py stamp --case <case>

.venv/bin/python docs/evidence/m4-boundary-matrix-work/capture_workflow.py index \
  --output docs/evidence/m4-boundary-matrix-work/captures-001.json
```

`bind-observation` 只按当前 DOM documentId 读取那一个保存 envelope，原样复制到 `bound-observations/<case>/actual-document-store.json`，同时新写 `{observedSourcePath,snapshotPath,copiedAt,sha256,bytes}` sidecar 与相同 `actualStoredEnvelope` 字段。时间为真实文件复制时刻。这个 receipt 是操作者直接文件复制声明，不是原生来源认证。

`case` 严格读取当前 URL 所指的 artifact ID。完整 export Canvas 必须与 snapshot 的 `document` 在**每个字段**都相等；文档、视觉 revision、source/IR、页、frontier、实际 SVG 和 export receipt 必须一致。不接受过期链接，不扫描 exports，不尝试同源/最近/唯一匹配回退。

`stamp` 仅新写 `screen-receipt-stamped.json` 的两项 hash；原 screen receipt 与 unstamped receipt 保持原字节。`index` 在所有 copied bytes、stamp 事实和唯一 baseline/case ID 检查通过后新写 `captures-NNN.json` 和独立 index receipt。索引必须直接位于这个工作区根目录，确保正式 collect 的所有路径在输入根内；更新时使用新编号，禁止覆盖旧索引。

之后才由 root 使用正式 `scripts/browser_visual_matrix.py collect --matrix .archcanvas/browser-visual-matrix-boundary-final --captures <new-index> --output <new-exclusive-directory>` 重建完整 scene 和 export。collect 的一致性检查仍不能替代实际截图审看、物理出版阅读或真人验收。

每个命令冻结读取的输入并在发布输出前复读；路径与字节 hash 保留在各 receipt。`preparation-guard.json` 是准备合同：36/9、spec、当前 seal、helper 与 workflow 字节被冻结。工具自检使用 `/tmp` 合成输入，明确不计真实 browser cases。
