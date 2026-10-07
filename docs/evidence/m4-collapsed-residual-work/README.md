# M4 折叠残差路线修复工作区

本轮实现正式工程的通用视觉修复，不读取、导入或执行失败原型 runtime，不执行用户模型或安装依赖。M4 仍为 partial，真人记录为 0。旧 au3 矩阵、原始截图、seal 和独立末读保持冻结。

修复前 [snapshot](../before-m4-collapsed-residual/manifest.json) 保存 169 个可变输入及两份原 seal/末读回执，共 171 文件的精确字节；旧 seal 的 2883 绑定在复制前后完全一致。旧证据目录保持原样。后续审计必须逐项通过未变原路径或此 snapshot 解析旧绑定，不能把新 hash 写进旧回执。

当前evidence README/status更新前的原件另有 [补充快照attempt-2](before-current-evidence-doc-update-attempt-2/manifest.json)；首次仅复制索引后mkdir错误保留为partial，不充当完整manifest。

当前构建为 `index-Dzp9we5t.js` / `index-B6WbMowt.css`：JS447309 bytes，SHA256 `5ee22dbd8bc61cc586f499f132910adcf77aa55fe85fead1600aa206d46b149f`；CSS37136 bytes，SHA256 `172a09a8c147e53c3bef426cf76b59b8cc4893e891eb6e920aa7b25a0bb024e0`。Scene24038 bytes/SHA `46ef39a60cdc5778e49536007d3a0c7807d3e6cb26a5fadaa2a07d37a40be75a`，router46552 bytes/SHA `45dcc36189cfc2be0264a566b3349f15a8cff598de5e7156362c496558d35eb2`。实现说明见 [本轮报告](../../m4-collapsed-residual.md)。

当前候选只缩短forward residual到真实折叠代理的投影路线。源码和实际ScenePort的canonical主字段、bindings、edge IDs、proxy、方向和坐标均需一致。候选保留独立residual边、端口、角色、样式与canonical目标，检查完整障碍与每条其他边（含sameTensor及中间顶点交点），受既有工作预算限制。展开目标、证据不足、阻挡或预算不足仍用原路线。新pass的whole-polyline重叠按区间并集计量；[修正与反例](design/overlap-union-repair-attempt-1/README.md)保留原失败和冻结探针，不改独立oracle或旧证据。

[开发记录](design/README.md)中 CNN L0/L1 分别由 271.4/235.4 单位、4 弯折缩至 38 单位直线，其余七 frontier 路线保持一致。开发探针不是独立验收。

[独立baseline](acceptance/baseline/capture.json)先冻结九frontier的core与旧actual browser工件。最终 [target-attempt-3](checks/target-attempt-3/receipt.json)24/24、[suite-attempt-3](checks/suite-attempt-3/receipt.json)203/203，无skip；[build-attempt-2](checks/build-attempt-2/receipt.json)strict/build退出0，输入前后精确。各次attempt和专项/全套计数不相加，本轮不执行模型或重跑Python全套。

[视觉计划](visual-plan/README.md)要求新构建CNN L0–L2、彩色/黑白、85/180mm共12配置、局部图、保存、实际SVG及一次真实重开。[browser manifest](browser-after-union-manifest.json)绑定12配置/128文件（12fit＋9local）；[attempt-3独立readback](acceptance/browser-readback-attempt-3/report.json)12/12有界通过，882输入精确，[末读supplement](acceptance/browser-readback-attempt-3/final-readback-supplement.json)890输入精确并核两个L2block2局部/实际reopen三副本。[正式AI像素receipt](pixel-after-union-attempt-1/receipt.json)与[末读](pixel-after-union-attempt-1/final-readback.json)已冻结；[初版9/12](superseded-browser-partial.json)与相应raw/supplement保留为superseded。仅四份L2 85mm观察metadata.heightMm的5.68e−14末位差用独立公式/1e−10上界，其他metadata/完整XML在公开交互对当前core交互、实际出版对当前core出版的各自模式内精确；不表示交互/出版整XML或全部caption位置相同；attempt-2失败原件保留。开发探针不替代正式独立报告或人审。AI已实看21新JPEG/4旧L0，21新图可见状态匹配、151绑定未变、128实际文件inventory精确。L0外U消失且独立lane保留，L1标题入口复杂，L2黑白同色难追踪/长页仍在；5例仅fit、17%整页细节不足。只读helper142项为134true＋8节点子树精确比较false，[差异supplement](pixel-after-union-attempt-1/publication-node-difference-supplement.json)保留展开Repeat计数文字出版x+30（去交互按钮）的差异，文字/其余属性、边/端口/图例匹配；未改expected、未审出版像素，AI观察完成不认证美学/物理出版/真人。

旧au339矩阵、四向/history/保存链、作者链和observer性能诊断不能继承新build。17基础模块/3透明起点仍存在，未新增逐模块/运行认证；当前研究包未prepare/verify、真人0。出版实尺/字体硬件、持续presented性能、held-pointer取消、非空pin实际保护、研究者任务及其他已知移动/对齐问题仍开放，M4partial/M5未开始。

[服务生命周期回顾](service-lifecycle-record-attempt-1/receipt.json)缺startup原始stdout，仅解释root工具历史与观测时点；不承诺持续在线。
