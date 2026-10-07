# M4 最终边界构建浏览器矩阵

当前 `index-Cr_xKW9U.js` 与最终 frontend `ce7f7f733da28cb31ecff80ca029a53094e88f8451bffc3874f8167f80a07d00` 已重新完成真实浏览器采集：36 baseline＋三模型各一 edited-after，共 **39 例、234 件采集工件、9 个源码 frontier**。正式 [manifest](evidence/browser-visual-matrix-boundary-final/manifest.json) 的两份 missing 列表为空，`artifactCoverage=complete`、`visualAcceptance=pending-human-review`、`humanAcceptanceCertified=false`；[联系表](evidence/browser-visual-matrix-boundary-final/index.html)与[空白人审模板](evidence/browser-visual-matrix-boundary-final/review-template.json)供真实审看。这补齐当前版本的矩阵工件与编辑保存一致性，M4 仍 partial。

本轮没有修改产品源码或 build。JS SHA256 仍为 `1f4f51f9818e523916dacea184a7005fa7459bd3f2c4c8bfe6bfc83006e5be29`，CSS 为 `index-DK5lov-h.css`。此前 [边界修正](m4-boundary-corrections.md) 的 Studio88/88、Python62/62与额外21/21、TypeScript/build，以及独立副本11/28/3/9检查继续保持其精确日志范围；本矩阵轮未重跑、不累加测试数。旧 oI5 矩阵、性能和研究包不计当前覆盖。

九 frontier 是 Transformer L0/L1/L2/L3、MLP L0/L1、Residual CNN L0/L1/L2；每级保留完整祖先展开集合。它们与 paper/monochrome、85/180 mm 组合形成36 baseline。[冻结 spec](../.archcanvas/browser-visual-matrix-boundary-final/spec.json) 与 [实际采集索引](evidence/m4-boundary-matrix-work/captures-039.json)分别绑定预期和当次材料。三份编辑后案例只证明所记录的 paper180 配置，不宣称36种配置都完成了编辑历史、性能或研究者任务。

操作者在隔离8906服务中通过真实 UI 设 frontier/page、保存、生成 whole-document SVG，并逐例读取**本次当前 direct URL**。原生 JPEG、SVG outerHTML、DOM 与实际保存 envelope 单独落盘；大部分案例在采集函数中即时复制已知 store/document 文件及 `{observedSourcePath,snapshotPath,copiedAt,sha256,bytes}` sidecar，使下一例合理更新 live store 后仍可检查原始材料。[封装入口合同](evidence/m4-boundary-matrix-work/copied-case-workflow.md)只读取 exact URL 的 artifact，不发请求、不扫描替代导出、不修补 stale 链接。完整 export Canvas 与当次 envelope 的 `document`逐字段相同；复制声明是操作者直接文件复制记录，不独立认证原生来源。

正式 [collect 进程收据](evidence/m4-boundary-matrix-work/formal-collect-process.json)保留命令、退出状态及 stdout/stderr。独立 [完整矩阵重建](evidence/m4-boundary-matrix-work/independent-matrix-collection-final-audit.json)核96冻结implementation/build/core绑定、234件actual input exact copies、36份core preview与79件expected独立副本；39例均满足完整interactive XML、publication scene digest、normalized publication exact bytes及完整store/export Canvas相等。809项证据绑定经复读稳定；这是文件/结构一致性，不证明实际paint或出版美学。

三模型 [提交后history与重开核对](evidence/m4-boundary-matrix-work/independent-journal-three-final-audit.json)另绑定51项输入：CNN的clean round2 revision36→37→38→39，MLP20→21→22→23，Transformer49→50→51→52。Undo/redo仅排除 root `data-revision` 与 metadata revision 两个数值后，完整XML树恢复；redo→save→reopen包括revision的完整XML与DOM序列化字节相同。最终实际store Canvas重建完整DOM，exact export Canvas完整相等。CNN早期add/precommit、disabled Undo和旧journal原样保留，不充当干净提交history；source/IR与fixture bytes核对不等于全程监控所有源文件。

独立 [实际像素AI观察](evidence/m4-boundary-matrix-work/pixel-observations-final39-index.json)逐张查看39张最终截图，9批次、117项raw bindings在观察前后稳定。可见页宽/PAPER-MONO、模型轮廓、整纸和legend、无modal遮挡与当前记录一致；编辑说明可见一致。深层fit细字无法可靠读出，不能从tiny overview认证完整annotation正文、端口/shared/repeat语义、最终导出paint、物理出版可读性或真人意见。所有最终截图为1280×720；当前viewport与DPR1来自当次DOM，UA明确来自较早同一IAB记录，current UA未观测。解析字体和硬件仍未知。

初次固定viewport前截图、初次错误data-dir、服务中断fetch失败和缺即时snapshot的尝试保留在work excluded目录，不计39例。根操作者的 [实际服务生命周期](evidence/m4-boundary-matrix-work/service-lifecycle-final.json)记录初次99888退出0、中间50071未知原因退出143及恢复70410；恢复服务在全部39例保存后Ctrl-C，chunk `f0d265`、exit0。tab35已关闭，viewport override于`2026-10-05T03:57:13.882Z` reset；用户8765未触碰，不宣称矩阵服务在线。`ss`权限失败不能认证端口空闲。

当前 `.archcanvas/m4-research-trial-boundary-final` [五席准备](evidence/m4-boundary-corrections-work/research-current-preparation.json)与manifest保持原字节：61实施绑定、4baseline、8901–8905、0分配/收集/真人，席位服务未启动。本轮矩阵没有真人研究者、没有填写人审结论。固定字体/硬件的持续input→presented性能、活动held-down取消、六维真人出版审看、密集图真实尺寸阅读与3–5名真实研究者任务仍未认证；独立AI核对不能替代这些门。

在更新当前说明前，[本轮归档](evidence/before-boundary-final-matrix/manifest.json)已保存18 current Markdown、handoff status及work README，共20文件。旧3644-binding seal的完整字节SHA256 `7fecf8b0ba1e5befec1d43613f0c115f1fd84d0503460f6d59118bacd22e7533`保持不变；[historical resolution](evidence/before-boundary-final-matrix/historical-resolution.json)与[只读验证](evidence/before-boundary-final-matrix/verification.json)解析全部3644绑定，其中19转向归档、3625保留原路径。新证据的 seal由根任务另行生成，不回写旧hash或把独立审查报告放入自己的seal。
