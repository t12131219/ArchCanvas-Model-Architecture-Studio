# Hierarchy-final 浏览器矩阵 work 记录

当前（2026-10-05）`index-Cr_xKW9U.js`（SHA256 `1f4f51f9818e523916dacea184a7005fa7459bd3f2c4c8bfe6bfc83006e5be29`）与最终ce7 frontend 的[新版浏览器矩阵](../../m4-boundary-final-matrix.md)已完成真实UI采集：36 baseline＋三模型各一 edited-after，共39例/234工件、9 frontier；完整Scene/export重建与独立核对通过，artifactCoverage=complete，humanAcceptanceCertified=false。39张实际截图已有AI逐张观察，三组提交后的undo/redo/保存重开链另有完整SVG核对；这些不认证物理出版或真人。Studio88/88、Python62/62及额外21/21属于此前边界修正轮，本矩阵轮未重跑、未改产品源码/build。当前五席研究包61实施绑定、0真人；presented性能、活动取消、固定字体/硬件、人审与3–5真实任务仍未认证，M4保持partial、未进入M5。旧oI5矩阵/诊断/研究包仍属历史；[矩阵前归档](../before-boundary-final-matrix/manifest.json)保留更新前文档和完整3644绑定解析，旧seal不改。

本目录保留`index-oI5sT67U.js`构建在隔离8896服务的真实矩阵输入、当次导出、保存envelope快照、操作journal、helper/stamp/collect记录及独立审计。最终[collector manifest](../browser-visual-matrix-hierarchy-final/manifest.json) SHA256 `dcdc8dcc438f143611d31d9da812f5112d82525e63d40435dc07fa0de6cc6231`，36baseline＋三模型各一edited，39例/234工件，missing为空、coverage complete；人工仍pending/false。完整产品范围见[收尾说明](../../m4-hierarchy-final-matrix.md)。

`raw/<case>`是实际浏览器观察和原生JPEG；`cases/<case>`是helper复制的同一case工件与输入绑定，不是新截图。实际DOM读和原生截图来自CUA，页面evaluation只读取公开DOM。逐次操作完成、关闭导出并fit之后，第一张截图用于检查，后续独立调用才保存最终截图。core候选PNG/SVG只供spec与collector验证，未替代浏览器JPEG。

[helper合同](helper-readme.md)规定逐例读取当次实际直接链接，仅读取精确artifact ID的document/figure/receipt，不发请求、不扫描/回退、不修补旧链接。完整export Canvas与对应保存DocumentStore envelope逐字段相同。文件快照与sidecar注明复制源路径、时间、完整sha/bytes；它们是操作者的文件复制声明。helper冻结每个输入的单次字节序列并在输出前复读；stamp只补两hash，index验证未篡改、已stamp与唯一case ID，正式collect另行重建scene/export。合成自检的[最终16项](helper-snapshot-relative-check-result.json)不计真实case或人类验收。

正式[collect stdout](matrix-collect.stdout.txt)、[stderr](matrix-collect.stderr.txt)及[exit0](matrix-collect-process.json)保留本次执行结果。[字段审计JSON](independent-final-field-audit.json)（SHA256 `2fabd22ba323c8965450d2a50dd3f5c2686ddef8bdce3c844d0d3aa442f46fc2`）通过857项检查，1185输入冻结/复读不变，234文件与work字节一致，fresh core重建39完整DOM/39publication SVG；[审计说明](independent-final-field-audit.md)单列环境和来源边界。

[edited-journal](edited-journal)保留三模型说明文本的undo/redo、save/reopen及CNN后续重定位。三组文本undo/redo完整SVG只规范化两revision标量；最终save/reopen含revision原字节相同。MLP最终visual23/storage9，Transformer51/17，CNN45/15，源码/IR事实不变。[额外live-store审计](independent-current-live-store-audit.json)核三份当前实际envelope与最终case快照整字节相同，不认证history持久化。

以下尝试原样留存，未计最终39例：

- [首次PDF记录](first-pdf-observation.json)是figure.pdf，SVG矩阵不收录。
- `excluded/transformer-level0-paper-85-wrong-local-asset-path`保留错误本地asset路径观察。随后正确case单列；旧截图与最终同配置截图字节相同，不另计一次覆盖。
- `excluded/transformer-level0-paper-180-stale-export-closure`保留旧闭包链接。新case重新读取当次实际链接，没有文件侧替换或扫描修补。
- `excluded/residual_cnn-edited-before-reposition`保留24%fit、大段留白的旧编辑图。rev30`moved`与rev30`text-edited`整SVG相同，不证明已提交移动。rev34/40和latent前沿记录保留；后续真实说明重定位y2549→973、undo/redo和save/reopen才形成rev45/61%fit最终case。

独立[像素JSON](pixel-independent-review.json)（SHA256 `1add264f908aaffbd052ff44f88196f769f682bd8c8f75cec368ca8453641108`）逐张实看39final＋3excluded，42张观察前后与最终复读哈希稳定；[逐张说明](pixel-independent-review.md)记录1102×905尺寸、模型/页头/控件一致、无modal、整纸/图例/说明可见。密集Transformer L1/L2/L3和CNN L2 fit不能可靠逐字读取或判定所有端点，AI观察不给出版美感分或真人认证。viewport来自当前DOM，UA/DPR追溯先前同IAB8889raw；hardware/font bytes未知，local asset hash不是浏览器response bytes的独立证明。

[矩阵阶段visibility尝试](visibility-attempt.json)先false，set(true)立即仍false，创建新visible tab后一次读数为true；此事实不能代表后续测量会话一直显示。[本轮原生诊断](../m4-hierarchy-visible-performance/README.md)随后实测产品/控制capability前后false、set(true)仍false，五请求成功但14/13/5匹配子集p95=4008ms；simple control20,000.4ms窗38rAF、3input/1interaction/2008ms。两者分母不合并，控制慢不排除产品，目录名或display请求不认证可见/持续presented性能。

[service-raw.txt](service-raw.txt)保留服务日志，独立矩阵审计未把mutable日志当冻结输入；后来[生命周期转录](../m4-hierarchy-visible-performance/service-lifecycle.json)观察8896 exit143、原因未知，39例工件已在退出观察前保存。冻结日志为[service-cutoff.txt](service-cutoff.txt)，不证明完整终端历史或退出原因。计划门[只读审计](full-gate-audit.md)与[后续性能流程](performance-next-steps.md)是诊断要求，不能当已完成结果；需求审计的0-case状态属于收集前冻结时点，原1909输入按[明确路径解析](gate-audit-input-resolution.json)核原bytes，不改写为39-case审计。用户8765工作区没有参与本目录采集。

当前研究包仍五pristine、0分配/收集/真人；人工contact sheet/review模板已位于新的39例collector目录。旧DPwoy矩阵和旧研究包只认证历史版本。当前文档更新前的[15原件归档](../before-hierarchy-final-matrix/README.md)保存原verification字节与完整1872历史路径解析，不重封或覆盖旧凭据。
