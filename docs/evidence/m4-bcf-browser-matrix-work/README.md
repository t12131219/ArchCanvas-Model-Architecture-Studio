# Bc 完整浏览器矩阵：当前结果与采集合同

当前36基线＋Transformer/MLP/Residual CNN各1edited-after已正式collect至 [`../browser-visual-matrix-bcf-full/index.html`](../browser-visual-matrix-bcf-full/index.html)，9前沿、39case缺失为空；`artifactCoverage=complete`只表示材料覆盖。M4仍partial，真人研究使用者/出版审看者均0，39份人审模板pending。本轮没有修改产品、执行用户模型、安装依赖或重复Studio/Python产品全套测试。

优先问题仍是Transformer跨tensor交叉/重合、深层fit阅读尺寸和新手组合预制。AI代理已逐张打开39有效原生JPEG＋1排除图；深层Transformer14%/13%与CNN17%不能认证细文字/箭头美观。当前侧栏有17条目但无MLP/CNN/残差组合预制或Attention/序列搭建合同。具体结果及下一步见 [`../../m4-bcf-browser-matrix.md`](../../m4-bcf-browser-matrix.md)。

| 当前材料 | 结论与边界 |
| --- | --- |
| `captures-039.json` / 正式collection manifest | 36唯一baseline＋3edited；当前Bc构建，无历史图填充；human=false。 |
| `full-collection-execution.json` | 正式collect exit0，完整stdout在 `full-collection-log.txt`。 |
| `full-collection-byte-audit.json` | 39raw/package/collection链、234文件、39JPEG header、index/build/worker guard、既有89sealed文件保持一致；原完整审计后续journal断言exit1，不能称全程exit0。 |
| `pixel-review/final39-index.json` / `evidence-manifest.json` | 独立AI像素逐图观察；117raw bindings、78raw→case、234case→collection比较稳定；真人/物理尺寸/持续呈现未认证。 |
| `routing-quality/full-matrix-analysis/audit.json` / `manifest.json` | 39实际完整SVG两格式解析；canonical投影、端点/viewBox、browser/export geometry通过，0body/header intrusion、0U-turn；Transformer交叉/重合非零，不证明审美通过。 |
| `edited-journal-svg-audit.json` | 三模型undo→redo各1注释tspan；redo/saved/reopened原SVG相等；MLP/Transformer early before已含edit，visibleNodes0错误raw保留，实际unique节点为24/8/49。 |
| `completed-collection-summary.json` / `FINAL-REVIEW.md` | 17文件摘要绑定、已完成范围与失败边界；不替代独立pixel或routing seals。 |

本39矩阵不认证四向拖动/平移后的路由美观。本轮另在8982完成当前构建原生输入诊断，见 [`native-current/independent-audit-summary-1/README.md`](native-current/independent-audit-summary-1/README.md) 与[总报告](../../m4-bcf-browser-matrix.md)。长16操作的frame buffers各dropped4102，四pan的原validator失败保留，Event Timing匹配35/44、unique15、子集p95=3008ms；短四pan全buffer dropped0、4/4通过、8/12匹配/unique4/p95=24ms；MLP五toggle pilot只有2/5 valid和1 interaction/p95=4008ms；stress300三toggle均通过、unique3/p95=176ms，展开304nodes/302routes。分母不合并，rAF不能充作presented FPS或总体INP。

四向节点移动保留了左越父边界22无告警、上侵入可见标题区32及header穿线、下与GELU重叠14及edge3穿body的实际问题；公开SVG四undo除revision恢复，首次selection不同。短pan公开SVG/selection/frontier保持，相机按左右±40/上下±32 CSS px移动；browser窗口4547ms与工具wall41.6s分开。raw截断、长journal丢失、未知环境与空pins均不补造。8982由主代理Ctrl+C结束exit130，final log原字节见 `native-current/service-lifecycle.json`；8968交付视图保留，用户8765服务未动。

旧Transformer paper85 stale-href原始材料已排除，采用独立recapture；2个初始case为直接helper执行、后37个为bound-only worker执行。旧raw、首次build路径失败、旧before假设失败、既有prepared/independent/pixel/routing seals均保留。以下合同记录实际使用的采集方法；新增采集要用新case/index/output，不覆盖当前材料。

此工作区只接受 `index-BcFxpKDY.js` / `index-NmgHfiF5.css` 当前构建的新采集，矩阵 spec 是 `.archcanvas/browser-visual-matrix-authoring-feedback-bcf/spec.json`，SHA `e1bbeee66de228eb2ad0ee4b901e0d41de2a9e87071c15da38118591a1bd224a`。需求为9个源码前沿、36基础配置，以及Transformer/MLP/Residual CNN各一份独立编辑后材料。

主代理独占CUA真实操作。辅助代理与 `capture_workflow.py` 不控制浏览器、不HTTP请求、不触发导出、不注入隐藏状态、不生成事件、不搜索替代导出、不填写真人审看。模板与helper准备成功本身不计作真实采集。此前矩阵图片与prepared席位不继承到本轮。

## 服务合同与状态

已确认的正式入口为：

```bash
PYTHONPATH=src .venv/bin/python -m archcanvas_cli serve \
  --port 8968 \
  --data-dir .archcanvas/m4-bcf-browser-matrix/documents \
  --studio-dir studio/dist
```

导出实际目录是上述 `documents` 的父目录下 `exports/<artifactId>`，不是 `documents/exports`。服务由主代理管理；本helper不启动服务或替换它的工作目录。主代理已经在tab44打开新服务，本轮不seed store，helper也没有seed命令。

## 每例最少观测

通过真实UI设置该例frontier/page，保存，导出整个文档，等待完成，读取**本例当前直接href**。关闭导出面板、fit并保存同一状态的公开DOM/SVG与原生截图。root必须在snapshot完成通知之前保持Canvas状态不变；快照后可切换下一例，package只使用冻结envelope。

每例在新目录 `raw/<case>/` 排他保存 `dom-observation.json`、`browser-scene.svg`、`screenshot.jpg`。原图返回字节是JPEG就原样保存为jpg；不能重编码或SVG转PNG充当截图。

| raw字段 | 实际公开来源与允许值 |
| --- | --- |
| `caseId` / `variantId` / `state` | 当前任务标识；case安全字符唯一；variant须spec中的一个；state仅baseline/edited。 |
| `capturedAt` / `studioUrl` | 实际ISO时间含时区；本轮URL `http://127.0.0.1:8968/`。 |
| `documentBinding` | `.publication-scene > svg` attributes和metadata中的documentId、revision、sourceDigest、irDigest；revision是非负整数。 |
| `pageSpec` | 当前UI观察widthMm=85或180、preset=paper或monochrome，必须匹配variant。 |
| `expandedIds` | 直接读取公开 `.publication-scene[data-expanded-ids]` 的JSON全部身份，不能仅推断可见的Collapse按钮。 |
| `environment` | 非空userAgent；viewportwidth/height与DPR为实际正有限值，不强制1280×720。建议固定实际viewport并记截图前后值。未知browserVersion/hardware为null、fontEvidence为空列表。 |
| `environmentProvenance` | UA若来自先前IAB观察，保留实际源路径/SHA/字段与scope；不得宣称是当次读取。 |
| `camera` | 实际 `.paper` transform（非空），当前scene的getBoundingClientRect的x/y为有限值，width/height正有限；可保留其他rect字段。 |
| `loadedBuildAssets` | 本次DOM加载的JS/CSSpath与URL：Bc JS与Nmg CSS，当前8968origin。 |
| `actualExport.observedUrl` | 本次完成后重新读取当前DOM的精确SVGhref。格式 `/api/exports/<32hex>/figure.svg`，当前origin，无query/fragment。 |
| `captureScope` / `limitations` | scope必须studio-viewport；保留unknown环境、来源和物理阅读限制。 |

`browser-scene.svg` 是当前 `.publication-scene > svg.outerHTML`，不是wrapper，也不是服务下载SVG。正式collect将独立重建interactive Scene逐XML核对它。完整raw结构见 `raw-observation-template.json`；模板中的null不能直接作证据。

历史UA源位于 `docs/evidence/m4-hierarchy-optimization/native-stress300-raw.json` 的 `/environment/userAgent`，SHA `8ad2e110e445d36b091025f98eac8215453dec05c3db78f3a0f21c386399bc5d`，原文为 `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36`。该字节与独立audit、历史已封矩阵provenance相符，出处核对见 `ua-provenance.json`。只复用这个历史字段；它不能证明当前浏览器身份或版本，当前viewport/DPR/fonts/hardware不从中继承。

## 快照、封装、stamp与collect

从正式工程cwd执行；所有case路径指root实际保存的新文件：

```bash
.venv/bin/python docs/evidence/m4-bcf-browser-matrix-work/capture_workflow.py verify-frozen
.venv/bin/python docs/evidence/m4-bcf-browser-matrix-work/capture_workflow.py snapshot \
  --raw docs/evidence/m4-bcf-browser-matrix-work/raw/<case>/dom-observation.json
.venv/bin/python docs/evidence/m4-bcf-browser-matrix-work/capture_workflow.py package \
  --raw docs/evidence/m4-bcf-browser-matrix-work/bound-observations/<case>/dom-observation.json \
  --saved-envelope docs/evidence/m4-bcf-browser-matrix-work/bound-observations/<case>/actual-document-store.json \
  --browser-scene docs/evidence/m4-bcf-browser-matrix-work/raw/<case>/browser-scene.svg \
  --screenshot docs/evidence/m4-bcf-browser-matrix-work/raw/<case>/screenshot.jpg
.venv/bin/python docs/evidence/m4-bcf-browser-matrix-work/capture_workflow.py stamp --case <case>
.venv/bin/python docs/evidence/m4-bcf-browser-matrix-work/capture_workflow.py index \
  --output docs/evidence/m4-bcf-browser-matrix-work/captures-039.json
```

snapshot只读DOM指定那一个store文档，核document/source/IR/revision/page/frontier，再按本次href精确定位export `document.json` 并要求完整Canvas相等。它把实际envelope原样保存并写 `{observedSourcePath,snapshotPath,copiedAt,sha256,bytes}` sidecar；新bound observation追加相同sidecar，原raw不改。旧href、错页、错frontier、未保存Canvas或状态变化会失败；没有最近/同源/唯一匹配回退。

package调用当前正式 `scripts/prepare_hierarchy_matrix_capture.py`：完整保存/导出Canvas相等、DOMmetadata与raw一致、whole-document export receipt、实际SVG字节及实际JS/CSS绑定必须成立。snapshot后只读冻结envelope，不再跟随live store。它保留原raw与输入bindings，拒覆盖或symlink。

stamp只在新的 `screen-receipt-stamped.json` 添加截图与Scene两项hash，原receipt/unstamped保留。index核复制字节、stamp只改两hash、uniquecase与uniquebaseline；索引必须直接在工作区根目录，正式collect的所有路径才能保持在输入根内。增加样本时使用新编号，不能覆盖旧index。

本轮已使用下列正式collector。再次采集时必须换成新的index与output路径，当前路径已有封存结果：

```bash
.venv/bin/python scripts/browser_visual_matrix.py collect \
  --matrix .archcanvas/browser-visual-matrix-authoring-feedback-bcf \
  --captures docs/evidence/m4-bcf-browser-matrix-work/captures-039.json \
  --output docs/evidence/browser-visual-matrix-bcf-full
```

collect重新构建interactive/publication Scene，精确核公开SVG DOM、export input digest及正式出版规范化SVG字节，生成联系表与空人审模板。输出路径必须全新。它核文件一致性，不认证截图像素、捕获时间/原生来源、环境字体、出版美学或真人任务；其humanAcceptanceCertified保持false，visualAcceptance待人工复核。

`preparation-guard.json` 绑定当前spec、70正式source/build、helper/正式合同、raw模板及UA出处，`verify-frozen`检查179份输入。helper没有读浏览器network或隐藏状态、也不从spec填造当次DOM字段。失败材料与root原始采集journal继续保留；新helper不会将它们改成通过。
