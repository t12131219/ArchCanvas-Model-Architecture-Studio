# ChS 当前研究准备与任务合同审查

这份补充与旧协议分开保存。当前产品为 `index-ChS0wIgb.js`，JS SHA256 `05019f89f0de0c0c622df7a2cc1a13ed58477c456244c97209a0f37db79139c9`。旧协议页顶层仍指向 Cr 构建、61 实施绑定、boundary-final 包及8901端口；这些是旧冻结范围，不能作为 ChS 开场路径。旧文档、包、799项seal及浏览器原件不改。

`research_trial.py prepare` 从正式 Transformer fixture 复制源码，通过 AST 分析及正式 core 创建 Canvas，冻结 Python/Studio/tool/build 字节，建立五个未分配席位；`verify` 只核这些冻结字节。它不开始计时，不运行模型，不安排参与者、不启动服务。此次新包为 `.archcanvas/m4-research-trial-chs-current`，登记8991–8995端口；实际可用性未测试，主持人开场前还需确认。准备时源、fixture、build和旧799封存绑定均有前后核对。

现有 StudyPanel 的五步仍覆盖计划§18.1/§18.5的同源 Transformer 制图任务：定位 Attention、编辑别名/样式/图例/说明、移动与pin及undo/redo、保存重开、导出并审看。它只读取 `.publication-scene` 的document/source/IR/revision与公开节点；`collect` 和汇总要求五步同一document/source/IR，并独立核保存/导出文件。因此这五步适合当前原有制图出口，不适合把17基础模块/3网络起点的搭建任务并入同一记录。

具体差异：搭建预制网络处于 draft-builder；StudyPanel不采集draft身份/节点/历史。生成源码后会成为另一个document/source/IR，把它混入原五步会被collector拒绝。五步文字也没有要求位置修复的预览/取消/应用，因此五步通过不表示这三个按钮的真人可用性通过。当前Python准备脚本不需要修改，这些限制应在新侧车说明和独立探索表中记录。

`check_research_trial.py` 是12项 automation 工件绑定反例的独立副本运行器，源码检查显示它覆盖拒绝覆盖、同一snapshot/Canvas/export、assignment和abandoned等关系。该脚本把testCount写为12，所读测试模块也有12个测试方法；本轮不重跑其suite、converter或模型。它不建立参与者身份、实际截图时刻、五步事实、字体或出版通过，automation不会计入真人分母。

新当前包开场前用以下命令核冻结内容；不对任何历史包编辑hash以延用，不重复prepare覆盖：

```bash
.venv/bin/python scripts/research_trial.py verify --package .archcanvas/m4-research-trial-chs-current
```

原五步仍用 `?study=1`，真实参与者到场后主持人才assign匿名代号并启动对应席位服务。Recorder每步是自报，保存/导出/截图需人审；放弃与超时留在分母。180秒和≥80%是原有目标，此次没有观测任务时间、成功率或真人结果。

建议用另行的可选探索表了解17+3和位置修复，计时独立，明确不改变原五步分母或原180秒判据。探索只在原五步记录和收集已结束后，在另外新建、独立保存的草稿/画布开展；不复用已收集席位的冻结工件。可以请实际参与者说明如何选择一种网络起点、辨认shape/dtype并修改单个模块，观察连接/输入错误提示，保存重开草稿及静态生成；不用一次任务冒称全部17模块已覆盖。位置修复探索分别观察自由移动冲突、preview不提交、cancel保留位置、apply一次undo/redo、pin拒绝及失败提示。预览必须先apply或cancel，再保存/导出。活动held-pointer原生取消与持续presented性能另行采集，修复“取消预览”不能替代这些性能门。

本补充是准备与提案；没有邀请、assign、服务、探索执行、参与者认证或人审结论。M4保持partial。
