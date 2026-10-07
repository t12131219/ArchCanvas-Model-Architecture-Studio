# M4：端口命中与连线方向

本阶段改善从零搭建的端口操作、纵向连线和输出显示。当前构建为 `index-ye7sAyyI.js` / `index-C769d2rm.css`，JS SHA256 `3e6fd1fea0cb5b3c286758e1bc6216e21e87f59ce0479e704faae80c5ed63164`，CSS SHA256 `4bd0d31a6e028cfa96e90eef56bdeb08b0cea5307e666033e55a23200ebf2646`。最终专项28/28、Studio264/264、strict TypeScript/Vite退出0；两次测试计数不相加。M4仍partial、M5未开始、真人0；本轮没有执行模型或安装依赖。

搭建端口现在有统一的圆点、间隙、文字命中区域，以及可聚焦的Enter/Space连接操作。连线按每个弱连通网络的主轴选择上下或左右端口，纵向四链由原先反复绕回侧边变为三条直线；新插入的独立网络不旋转既有网络。坐标、schema、节点/边身份、保存协议、连线语义和原排版不变。“按连接排版”实际使用横向rank，不是本次手动纵向草稿的来源。同一网络跨主轴阈值或合并网络仍可能换端口方向，没有持久方向或迟滞阈值；命中字宽是估算，不能认证任意长标签。

带已声明outputPath及显式displayAlias的Output保留别名标题，副标题显示`model output`。无别名仍保留实际return路径，包括合法`n_`键和嵌套路径。完整sourceFact、outputPath、源码和digest保持独立；不猜测ID来源或修改Python返回键。修复从正式合同和真实失败证据独立编写，没有采用失败Temp目录代码。

独立期望在[11项方向合同](evidence/m4-authoring-interaction-work/acceptance/flow-contract.json)中冻结：四节点x50/y70、224、378、532，三边端点(138,170)→(138,224)、(138,324)→(138,378)、(138,478)→(138,532)；并检查横向旧坐标、Add/Concat有序端口、遮挡诊断、逆向外法向、移动/history/JSON和独立分量。修复前原10项4通过6失败，中间全局方向11项10通过1失败，按分量修复后11/11。中间13项/27专项/263全套与初次隔离错误均保留，不作最终计数。Output独立6项与原路径3项9/9，保留修复前3/6。

最终[专项收据](evidence/m4-authoring-interaction-work/checks/target-attempt-2/receipt.json)、[全套收据](evidence/m4-authoring-interaction-work/checks/suite-attempt-2/receipt.json)和[构建收据](evidence/m4-authoring-interaction-work/checks/build-attempt-2/receipt.json)绑定执行前后相同输入。[独立检查复读](evidence/m4-authoring-interaction-work/acceptance/final-check-readback-attempt-1/report.json)核209去重输入/基础设施/实际输出，不重跑测试。[源边界审查](evidence/m4-authoring-interaction-work/acceptance/source-review-attempt-1/report.json)记录8项检查、64绑定；Python完整套件和独立完整发行本轮未重跑。

root通过CUA实际从空白搭建Input→Linear(16→8)→GELU→Output。第一边点文字中心，第二边拖圆点，第三边Enter/Space；重复producer拒绝，undo3→2、redo2→3，保存重开，横向排版再撤销，Linear右/左/上/下各16，另左50→34并撤销50。相机右/左/上/下各40，首个down在工具30秒超时中只移动15；Escape恢复up状态，再单独down40成功，失败保留。节点与路径由完整SVG核对；部分动作时视图裁剪是相机位置，不假称所有端口都可见，也不认证普遍的held-pointer取消。

双输入合并草稿实际通过palette/inspector建立InputA、InputB、Add、Concat、Output。事前构造为Add.left=A、Add.right=B、Concat.a=Add、Concat.b=A、Output=Concat。组中心点击、圆点拖动、文字点击和键盘分别连成五条边；不同输入端口和同源分支身份保留，保存与静态生成成功。三个起点实际MLP点击5/4、residualMLP点击6/6、CNN原生拖入8/7，全部保存；MLP/CNN静态生成，residual本轮没有生成。左库实际17基础模块含SiLU，不含Softmax，尚不支持Attention/LSTM。没有逐模块生成、运行/训练或真人新手认证。

四链生成新的源码并打开新managed副本，保存/重开rev0、SVG导出180×196.638655462mm，实际UUID`a6ea97deb11a440fbc9aee3aacf1d340`。新sourceDigest`306378c82c52…`/irDigest`704b0c13…`与旧开场模型`c1cd…`/`45d5…`分开；[实际工件副本](evidence/m4-authoring-interaction-work/actual-artifacts-attempt-1/manifest.json)保存五份草稿及新project/source/document/export共11文件。已观察URL的只读HTTP JS/CSS与构建字节精确，不称直接读取browser cache。首个sandbox socket拒绝和后续读取分别保留。

[165原生文件清单](evidence/m4-authoring-interaction-work/browser-final-manifest-attempt-1.json)含14JPEG、13条事后操作声明与截图映射；声明不是同步OS遥测。kernel重置后早期observer误读`data-draft-node`而非端口`data-node`、旧闭包仍用旧reader，derived节点和路径为null；完整SVG仍在。新v2内联观察器恢复后续身份记录，不回填原件。JPEG和DOM双侧记录不保证每个像素一致：merge-fit图仅4边；名为merge-100的图实际73%且5边；pending图footer与DOM不一致；managed-final图仍含导出modal。旧截图全部保留，另有清晰managed补帧，不把错名帧当pass。

当前视觉限制明确：合并草稿不同producer在(614,220)交叉，Concat输入前叠线；MLP/CNN/residual的fit字号和多输入目标偏小；CNN保留跨两排长回线。端口身份正确不等于全局美观。Escape清除pending后footer仍保留待连接提示，pending截图时序差异原因未知。Transformer交叉/重叠、expanded标题绕行、深层长页、单色宽度4圆头填满dash间隙仍开放。最近的性能控制证据只有三个简单控制页记账；旧Studio观察保留各自历史构建范围，无当前Studio A/B、三次矩阵、presented FPS、物理出版或真人研究结论。

[上一BK阶段](m4-collapse-continuity.md)和[CG单色阶段](m4-monochrome-role.md)及原seal不改。此前1117绑定在改动前全部核对；[226可变路径快照](evidence/m4-authoring-interaction-work/before-implementation-attempt-1/manifest.json)用于解析旧source/docs/dist字节，未改旧seal。[机器状态](evidence/m4-human-review-handoff-status.json)记录当前合同和未过门；三个AI独立角色不能计作真人。

独立原生审查[46项有界检查](evidence/m4-authoring-interaction-work/acceptance/native-audit-attempt-1/report.json)全部通过：59搭建快照、195对边端点、1424/1424有效可见中心身份，无穿body；11失败observer快照不计命中成功。不同producer交叉在六份快照重复出现，strictCrossingFree明确false。[实际工件独审](evidence/m4-authoring-interaction-work/authoring-artifact-audit-attempt-1/README.md)6/6、33输入/副本精确，核AST/真实参数span/完整return路径/digest/新managed与实际SVG。首轮物理根height采用过严精度的5/6审查保留；按独立五位小数编码修正后通过，不修改产品或工件，也不认证实际印刷可读性。

[最终AI像素审查](evidence/m4-authoring-interaction-work/visual-review-attempt-1/final-review-receipt.json)亲看20图：全部14rawJPEG、5原生放大crop、1旧纵向参考；165原件和清单精确。69公开case、10配对仅去除采集时间后核对，不借DOM替换截图。简单纵向/横向三直线及清晰67%managed补帧的Output副标题有界改善；合并交叉、小目标、错名缩放/边数、pendingfooter和modal旧帧保留失败。四向平移没有独立对应JPEG，仅公有几何通过，完整四向视觉门仍开放。
