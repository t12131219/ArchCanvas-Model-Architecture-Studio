# M4 当前交接：层级树优化构建

当前 JS 是 `index-oI5sT67U.js`，SHA256 `2c769087f0765ba47892e9f26f12a19e4336ec12573dce5859ac636e310f446c`。M4保持partial，不进入M5。[代码、验证与边界](m4-hierarchy-optimization.md)汇集85/85测试、正式副本检查、真实React更新、实际Studio编辑/保存重开与新构建原生输入诊断。自动化和agent复核均不是研究者或人工出版验收。

| 待完成门 | 当前状态 | 材料 |
|---|---|---|
| 当前完整浏览器矩阵 | 新spec已准备；collect为0/36基线＋0/3edited | [新spec](../.archcanvas/browser-visual-matrix-hierarchy-final/spec.json)、[候选36SVG一致性](evidence/m4-hierarchy-optimization/renderer-candidate-parity.json)；candidate不是浏览器截图 |
| 人工出版审看 | 新build无已完成矩阵或真人review | 原DPwoy [39例联系表](evidence/browser-visual-matrix-publication-final/index.html)及[模板](evidence/browser-visual-matrix-publication-final/review-template.json)可审原版本；不能认证新build |
| 原生性能、活动取消 | 新stress展开/pan通过；eligible6/matched3/interaction1/p95=2016ms；未取得新native active cancellation | [原生记录](evidence/m4-hierarchy-optimization/native-stress300-raw.json)、[validator](evidence/m4-hierarchy-optimization/native-stress300-validation.json)；持续输入仅DOM/rAF代理，需固定硬件/解析字体与实际呈现测量 |
| 3–5真实使用者任务 | 新五席pristine、0分配/收集/真人 | `.archcanvas/m4-research-trial-hierarchy-final`，59实施绑定、8891–8895，[verify](evidence/m4-hierarchy-optimization/research-verify.txt)只核版本与基线 |

旧publication-final五席包已实际[verify失败](evidence/m4-hierarchy-optimization/research-old-stale.txt)，不能分配新人。旧39例、末审、8888原生诊断及其真人pending状态继续保留原范围。[归档manifest](evidence/before-hierarchy-optimization/manifest.json)保存本轮修改前14文件，旧1532收据的变更路径按originalPath→archivePath核原bytes，不改旧hash。

新矩阵需在隔离storage中按[协议](browser-visual-matrix-protocol.md)采集36baseline与三模型各一edited，绑定当前build实际Canvas/DOM/截图/导出，再collect生成新manifest/review-template。最终出版验收由真实复核者记录实际尺寸、字体、路线、图例与黑白观察；没有新的矩阵或review就保持pending。

五席使用的是相同未编辑Transformer文档，只代表准备。manifest SHA256 `364eb60843ebaa89ed3b9e1270d1166f4ed62f06c4772a1158cf05cedfc5117c`。主持人核对环境并取得实际参与者后，才分配匿名participant code；不代替用户发邀请或填任务结果。

```bash
.venv/bin/python scripts/research_trial.py verify \
  --package .archcanvas/m4-research-trial-hierarchy-final

.venv/bin/python scripts/research_trial.py assign \
  --package .archcanvas/m4-research-trial-hierarchy-final \
  --slot S01 --participant-code R01 --kind researcher

PYTHONPATH=src .venv/bin/python -m archcanvas_cli serve \
  --port 8891 \
  --data-dir .archcanvas/m4-research-trial-hierarchy-final/slots/S01/workspace/documents
```

开启对应 `http://127.0.0.1:8891/?study=1` 后按[五步任务与评判](m4-research-protocol.md#任务与评判)执行，保留超时、误操作与放弃者。实际检查SVG/PDF的格式单列；自报summary与独立人审报告分别保存，不能升级collector的humanSuccessCertified=false。新构建实际MLP重开保持source/IR、alias/pin/layout与SVG，selection/history清空、camera改变，不承诺这些状态持久。
