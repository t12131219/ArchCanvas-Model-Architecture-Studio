# 最终构建39份实际浏览器工件观察

本目录绑定正式封存的 `browser-visual-matrix-zoom-full/manifest.json`，build为 `index-oH4Ot2L9.js` / `index-BO7yZQLO.css`。九个真实前沿×彩色/黑白×85/180mm的 **36份基础工件**齐全，另有CNN/MLP/Transformer各一份edited-save-reopen工件，共39。artifactCoverage=complete；`visualAcceptance=pending-human-review`、`humanAcceptanceCertified=false`。目录名不作通过证据，实际manifest和234份采集artifact的SHA-256、字节长度均另核通过。冻结spec verify仍unchanged。

AI操作员按实际落盘图片分批打开，39张均1280×720/DPR1，页头width/preset和整体展开形态正确、整页及图例可见、无残留弹窗，没有字节完全相同的截图。36基础图的可见page inspector active状态与页头匹配；3编辑后重开图在object inspector，不能声称看到了未显示的page控件。最后Transformer edited可见Research Encoder alias和fill差异；精准视觉改动由actualCanvas/DOM/publication重建核查。没有从tiny pixels推断源参数或逐字认证。

`report.json`绑定最终manifest、每张原图、DOM及build摘要。前38份AI观察来自保留的`browser-visual-pixel-observation-zoom-full-in-progress`，逐字节与最终seal重新匹配；最后一张直接打开sealed原图核查。三张header拼图是派生诊断，不能计为额外browser captures。

独立XML解析最终paper180 Transformer L0/L1/L2/L3实际viewBox为696×806、772×1698、892×2382、952×3166，可见canonical对象12/23/41/49。L2 projection y2086、encoder bottom2048、gap38；L3 y2870/bottom2832/gap38。L2完整包含decoder.feedforward，L3再加两个encoder.feedforward。L1另有更高的decoder列，projection与encoder的738差值不能认作空白高度。当前L3全文高598.6mm、最小文字5.360pt；仍需真实物理尺寸可读性与人工审美审看。

UA来源按真实字节另附 `prior-port8771-native-user-agent-source.json`：同IAB先前8771native observer，**不是8772 navigator读取，也不是本轮性能测量**。`prior-host-environment.json`与`prior-native-environment-context.json`是早期实际主机/Fontconfig及前一build环境查询；SHA与原位置见report。字体loaded/零externalresources不能证明resolved fallback字体或glyph fidelity，旧CPU/硬件上下文不能认证本轮GPU调度。

历史修复前39矩阵、当前代表4矩阵和采集进行中记录均保留。完整文件覆盖不能替代六维评分、真实研究者任务、每个配置都完成编辑流程、拖动中间帧率或nativeinput-to-paint；这些门保持各自证据与限制。
