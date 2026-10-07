# M4：折叠残差路线与重叠保护

当前构建为 `index-Dzp9we5t.js`（SHA256 `5ee22dbd8bc61cc586f499f132910adcf77aa55fe85fead1600aa206d46b149f`）与 `index-B6WbMowt.css`。本轮修正残差边指向真实折叠代理时的外绕路线，并补齐整条折线重叠的保护度量。正式实现保持从头构建；未使用失败原型runtime、执行用户模型或安装依赖。M4仍partial，M5未开始。

Scene只有在所有canonical分支都指向同一个被折叠的真实节点/输入端口时才提供目标证据。Router另核实际ScenePort、proxy、canonical bindings和端点；只为向前的bottom→top residual提出有限短路线。候选必须严格缩短、弯折不增加，保持端点/方向、独立边/端口/role/style和source/IR，不侵入相关body、背景卡片或祖先标题。与每条其他边分别核交叉和重叠，包括sameTensor；展开、证据不足、阻挡或预算不足时保留原路线。普通data/residual不会因共享tensor而合并。

开发探针发现重复经过同一区间时，原segment累计可能漏判实际重叠增长；最终保护只在新residual pass中对whole-polyline重叠区间求并集。此前反例和初版 `pYkr4gCc` 的9/12浏览器材料保留，不提升为当前验收。源码范围和修复前后原字节见 [修正记录](evidence/m4-collapsed-residual-work/design/overlap-union-repair-attempt-1/README.md)。它是有界路线改进，不认证全局最短、美观、全部交叉消除或性能。

[最终专项](evidence/m4-collapsed-residual-work/checks/target-attempt-3/receipt.json)24/24、[Studio全套](evidence/m4-collapsed-residual-work/checks/suite-attempt-3/receipt.json)203/203，均退出0且无skip；[strict/build](evidence/m4-collapsed-residual-work/checks/build-attempt-2/receipt.json)退出0，执行前后输入精确。专项与全套计数单列。本轮未重跑Python全套，也不把旧发行9项当成新完整发行字节。开发九frontier观察仅CNN L0 edge9和L1 edge18由271.4/235.4、4弯折缩为38、0弯折；其余七frontier路径不变。[独立readback](evidence/m4-collapsed-residual-work/acceptance/browser-readback-attempt-3/report.json)与[末读supplement](evidence/m4-collapsed-residual-work/acceptance/browser-readback-attempt-3/final-readback-supplement.json)已核当前源码/build、九baseline与实际12case；882/890输入复读精确，几何/语义/导出/保存范围通过。

新构建的 [CNN浏览器manifest](evidence/m4-collapsed-residual-work/browser-after-union-manifest.json)绑定L0–L2 × 彩色/黑白 ×85/180mm共12配置、128文件，包含12fit和9local图。实际保存envelope、UI选择的SVG/document/receipt以及L0paper180真实reload与新UUID再导出均有独立核对；末读另核两个L2 block2局部图和重开后的三份实际副本。

acceptance attempt-2因JSON页高末位差失败，原件保留；attempt-3为12/12有界通过。仅L2paper85/mono85的四份before/after观察metadata.heightMm比其SVG值少 `5.684341886080802e−14` mm，以独立viewBox公式核 `≤1e−10`；其余metadata和完整SVG XML按各自模式精确：公开交互SVG对当前core交互SVG、实际出版SVG对当前core出版SVG，不忽略或改写其他字段。这不表示交互与出版的整XML或所有caption位置相同。这项核对不包含像素美学、PDF/PNG、字体嵌入、完整39矩阵、drag/history或性能。

[正式AI像素收据](evidence/m4-collapsed-residual-work/pixel-after-union-attempt-1/receipt.json)与[末读](evidence/m4-collapsed-residual-work/pixel-after-union-attempt-1/final-readback.json)已冻结：逐图实看21张新JPEG与4张旧L0，21张新图可见状态匹配，151输入绑定未变、128实际文件inventory精确。L0外U路线消失且独立lane保留；L1 paper180局部图中的block1→2直lane可追踪，展开标题边界绕行仍复杂；L2 paper180/mono180分别有两处58%局部图展示完整skip进入不同Add端口，黑白同色更难追踪、长页仍在。五例只有fit（L1 paper85/mono85/mono180、L2 paper85/mono85），17%整页不足以认证细节。未观察到截图/状态失配；这是AI观察完成，未审看实际出版像素，不记美学、物理出版或真人通过。

只读helper共142项比较，134 true、8个节点子树精确比较false保留。[差异supplement](evidence/m4-collapsed-residual-work/pixel-after-union-attempt-1/publication-node-difference-supplement.json)确认这8例的展开Repeat计数文字“2× · independent”在出版版右移30 world units（L1 x287→317、L2 x347→377），同时去掉交互展开按钮；文字和其余保留属性相同，边/可见端口/图例匹配。没有改expected或把false改成通过，也没有跨模式整Scene字节一致的结论。

[服务回顾](evidence/m4-collapsed-residual-work/service-lifecycle-record-attempt-1/receipt.json)缺原始startup stdout，只记收据与实际工具观察时点，不重构原日志或承诺持续在线。旧au3的39例/234工件、三模型四向/history/保存链、作者链及observer诊断保持历史范围，不能继承为新renderer认证。17基础模块与3透明网络起点仍存在，逐模块浏览器和运行验收未新增。

[切换前快照](evidence/before-m4-collapsed-residual/manifest.json)保存171个可变输入/原seal/末读原件，旧seal的2883绑定按未变原路径或快照解析；旧raw、manifest、seal不回写。当前无新研究包prepare/verify，0分配/收集/真人，AI不计真人。持续presented性能、总体INP、held-pointer活动取消、非空pin实际保护、物理出版/字体/硬件、人审与3–5真人任务仍开放。完整证据入口见 [work README](evidence/m4-collapsed-residual-work/README.md)。
