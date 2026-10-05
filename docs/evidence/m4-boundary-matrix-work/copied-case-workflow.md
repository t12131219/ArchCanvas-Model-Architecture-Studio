# 采集时保存 envelope 的封装入口

此入口补充既有冻结工具，不修改 `capture_workflow.py` 或其 guard。根操作者在真实 CUA 采集函数中读取已知 `/tmp/archcanvas-m4-boundary-matrix/documents/<当前DOMdocumentId>.json`，将原始字节排他保存到同一 raw case 的 `actual-document-store.json`，新写相邻 `.receipt.json`，并在 raw JSON 中放入完全相同的 `actualStoredEnvelope`。

sidecar 精确内容为 `{observedSourcePath,snapshotPath,copiedAt,sha256,bytes}`；复制时刻带 ISO 时区。全部事实来自实际文件复制，不从后续当前 store 推断。随后可继续下一例 UI，live store 的合理更新不会丢失已复制案例。

```bash
.venv/bin/python docs/evidence/m4-boundary-matrix-work/package-copied-case.py \
  --raw docs/evidence/m4-boundary-matrix-work/raw/<case>/dom-observation.json \
  --browser-scene docs/evidence/m4-boundary-matrix-work/raw/<case>/browser-scene.svg \
  --screenshot docs/evidence/m4-boundary-matrix-work/raw/<case>/screenshot.jpg \
  --saved-envelope docs/evidence/m4-boundary-matrix-work/raw/<case>/actual-document-store.json

.venv/bin/python docs/evidence/m4-boundary-matrix-work/capture_workflow.py stamp --case <case>
```

该入口只读取所给原始材料、snapshot/sidecar 与本次 URL 精确 artifact 目录，不重新读取 live store，不发请求或搜索替代链接。完整复制 Canvas 必须与 exact export Canvas 相同，所有当前 DOM/source/IR/frontier/page/revision 仍须经过正式 helper 校验。case 目录、复制合同与独立 stamp/index 完全沿用原工具；额外 package receipt 保留新增 guard、raw 字节绑定与 `liveStoreReread=false`。

如果采集时未复制 envelope，而下一例已改写 live store，则保留这一失败案例到独立 excluded 路径并重采。不能使用新 store、猜旧内容、找其他 export 或修改 raw 来补证据。复制 receipt 本身是操作者直接文件复制声明，不单独认证原生截图、人类身份或审看。
