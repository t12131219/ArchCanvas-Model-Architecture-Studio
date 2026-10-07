# M4 连线说明关联、路径缩短与导出修复

本阶段使避障后的说明文字明确关联自己的 tensor 路线，保守减少多余弯折，并修复真实 Studio 导出遇到的验证阻断。当前资产为 `index-Divs1MJA.js` / `index--unhoRTb.css`。[最终统一检查 attempt 4](evidence/m4-caption-route-current/checks-final-attempt-4/receipt.json)：Studio **389/389**，0 fail/skip/cancel；严格 TypeScript/Vite exit 0；publication **11/11**，无 skip。105 个 source/test/config＋3 个 dist 共 **108** 条 exact bindings；另 **11** 条 publication inputs。Focused、独立审查关系与准备关系均不加到产品测试数量。M4 `partial`、M5 `not_started`、真人 **0**；[当前门状态](evidence/m4-current-gate-audit.json)保持性能、真人任务和出版人审未通过。

## 标签与所属路线

BTw 的 memory 标签可读，但与真正 Encoder→Decoder 的短水平路线相距56世界单位且没有关联线。本阶段采用一般规则：近旁无冲突、名义文字范围距所属 route≤18 的标签保位置；其余在原锚点±64候选中找安全位置，必要时生成≤48世界单位的直法向 guide。无法安全关联时保留文字并发出 diagnostic。Guide 避开正文、repeat 背板、展开标题、说明、其他文字和其他 route/guide；共享 tensor 也不许可接到别的 route。

总览 memory 保留 `M 281 444.1 H 316`，文字为 `(288.5,484.1)`，guide为 `(298.5,444.1)→(298.5,473.1)`、**29世界单位**。Root detail重新计算后为 `(273.5,496.1)`，guide `(283.5,456.1)→(283.5,485.1)`，同样29单位。Guide是单独的派生 `Scene.captionGuides`，width0.8、opacity0.65、无箭头、不可交互；不新增 canonical edge、tensor、port、sourceFact 或 Document/history字段。SVG metadata放在 `presentationDecorations`，不在 `renderedBindings`。

名义文字范围为9字号codepoint一em加padding，不是resolved-font或字形量测。有界工作预算、越界诊断和实现见[association contract](evidence/m4-caption-route-current/association-contract/README.md)。其早期输入采样与44专项结果保留原时点；不能覆盖后续发现的线宽反例。

## 路径缩短与独立反例

Final shortcut pass在旧 batch完成后尝试局部拼接和有限正交走廊。保持端点、首尾方向，保留 min(原首尾直段长度, 6) 的逃逸长度，长度与弯数都不增加且至少一项严格改善；检查障碍和与别的route、自身非相邻segment的具体 crossing/contact/overlap集合。删除旧交点不能交换成别处新增交点，未检查的候选不能被接受。预算是计算工作上限，不是耗时或帧率证明。

3个源模型的9个不同层级前沿共有198次route出现，实际改变3次：CNN L2 residual `edge:18` 长度849.4→831.4；Transformer L1 residual `edge:31` 长度197.2→54.2、弯4→2；Transformer L1 memory `edge:55` 长度434保持、弯4→2。共减少**161世界单位、4个弯**。9前沿不是9个模型，跨层级相同canonical不是新增tensor。历史清单实际21候选，未造第22项或宣称全采纳；Transformer L0 canonical route保持。[router记录](evidence/m4-caption-route-current/router-work/README.md)与[最终self审查](evidence/m4-caption-route-current/self-route-review/README.md)。

独立审查实际找到三类缺口并修复：later caption可进入先前guide线宽范围；foreign route与guide中心线分离但stroke envelope约0.60单位重叠；shortcut首段可穿过自身终点。前者原失败保留，foreign修前12项10pass/2fail、修后41/41；自身反例修前18/19、修后19/19。第一次抽取自身反例漏掉必要障碍，before也通过；该无效尝试保留，最终16障碍子集缩减才产生真实before fail。

[最终continuation独审](evidence/m4-caption-route-current/independent-review/continuation-review/report.json)覆盖36个document variant、148个概览/detail输出、2840个edge出现、43312对route，semantic/geometry失败0；183组stroke检查从11问题到0，21个caption和41个router对抗案例保持纯读和确定性；173次changed-route出现和16障碍子集没有新增自身关系。矩阵包含配色、宽度和detail重复，不是148模型或额外产品测试。名义butt-cap矩形检查不认证join、marker、抗锯齿、真实字形或全域几何。

旧Scene/SVG gold、manifest和失败保持原字节。当前历史比较仅归一化有意改变的派生路径、caption/guide/bounds/diagnostic，其余Scene与归一化SVG精确比较；实际新几何另用独立oracle核验。原10项旧断言失败与调整后55/55专项见[契约更新](evidence/m4-caption-route-current/test-contract-update/README.md)，不回写gold。

## 真实浏览器与导出

[root当前浏览器收据](evidence/m4-caption-route-current/final-browser/receipt.json)实际试了相机右/下/左/上各32px，以及选定leaf右/下/左/上各32世界单位、各方向undo/redo和baseline恢复。独立[gesture/storage复核](evidence/m4-caption-route-current/browser-gesture-final/report.json)515/515是public DOM/SVG与存储关系，不是连续手势像素或延迟认证。最终保存document revision20、storage counter3，相对原文档仅revision改变，source/IR/canonical事实原样。重开Scene和metadata相等，相机不保持，history不写存储。

Root亲审04与39稳定100%图及31黑白图，memory和无箭头guide可见；实际PDF raster也可见。03为DOM100%但仍68%旧像素，camera批量观察超时、首次locator/selector错误、export未settle控件与27生成中/28失败均保留。相同文件名不能自动证明截图和DOM同一paint时刻。

真实UI首次导出拒绝 `path.data-caption-guide-id`，这是集成产品缺口；[修复记录](evidence/m4-caption-route-current/export-integration-repair/report.json)保留browser失败、真实CLI exit2与before 11tests/7errors。Exporter只允许局部配对的guide ID/owner和inert属性，要求owner对应已渲染tensor edge、唯一装饰identity、无填充/箭头/执行或外部资源；不能泛开任意SVG属性。真实85/180mm×SVG/PDF/PNG六种输出保留，after11/11通过。

修复后UI实际生成同revision20的whole180SVG `ea42cd05c8a344348ed5751da24276ec`、root-detail180SVG `a0a6f9b4d5b74acfa9c9b032175c14ca`、root-detail180PDF `a6a82fd6101e451ab7e09caec69e035b`。[独立导出复核](evidence/m4-caption-route-current/browser-export-final/report.json) **178/178**，三个工件文档等于最终保存文档，两SVG含12canonical rendered bindings和49sourceFacts，guide独立且无arrow；PDF与detail共享scene/validated SVG digest。System Poppler确认180×297.189mm单页，bundled GLIBC_2.38失败保留。有限亲审像素与三个名义guide案例没有替代人审或字体嵌入认证。

Whole180最小文字6.60pt、detail180为7.42pt、whole85预览3.12pt；这是物理算术与建议，尚未通过85/180mm真人出版审看。

## 当前明确缺口与研究准备

Encoder下移24世界单位时memory文字与guide消失，tensor edge仍在、undo恢复。[独立调查](evidence/m4-caption-route-current/browser-caption-investigation/report.json)确认旧默认标签规则只在 `abs(source.y-target.y)<15` 时生成memory，先于placement；helper不能诊断空标签。同一旧规则在before/current、whole/detail的±14/±15/±16/±24与水平±24矩阵重现。相同阈值也切换display port侧；本阶段没有修改。可读标签与一般四方向稳定性仍未验收，不能把leaf四方向成功写成所有标签移动稳定。

本阶段没有新native/performance采样。历史BTw三匹配耗时160/72/160ms、p95160ms、rAF58.605395179Hz仍是旧版小子集；304DOM正文仅6视口相交、4完整入内。rAF不是实际呈现FPS，300真实可见对象、连续输入≤50ms、presented≥50fps、固定硬件/字体A/B×3、无关pins与锚点仍待证明。DuFX/D60旧失败保持。

[最终研究准备](evidence/m4-caption-route-current/research-export-final-preparation/report.json)新包 `.archcanvas/m4-research-trial-caption-route-export-current`，manifest SHA256 `009089b5dd5e0ed868a7b1ab34d842671ee9cb47ee5428640dbac675579cea82`。正式venv prepare/verify均exit0；84implementation＋4baseline，5pristine席位43571–43575，**296/296**仅独立冻结准备关系。未查端口、开席位服务、assignment或collect。旧22包376文件保持原字节；首caption-route包因exporter变更被官方verify拒绝stale，BTw也stale，不能改哈希续用。

历史AI试用仍是DuFX/CC91/B_XH三实际角色；审计者不新增模拟参与者，AI不是真人。左库17基础模块＋3透明网络起点未扩种类或逐种生成/执行认证。真人3–5位五步≤180秒任务、至少80%完成和85/180mm人审未完成，M4保持active/partial。

## 冻结边界

Attempt1统一检查有旧repeat SVG exact期待不再适合派生改变，以及root漏PYTHONPATH的publication invocation失败；attempt2仅root新831.4字面断言出现约1e-13浮点差，attempt3在该断言采用1e-9容差后389/9通过。之后实际浏览器暴露exporter白名单缺口才得到最终attempt4的389/11。原尝试、工具/oracle错误和真实产品错误分别保留，不能重写旧结果。

[126项before-change](evidence/m4-caption-route-current/before-change/manifest.json)保存原BTw源码/构建和全部入口字节。13个current header与gate更新只替换当前区，第二个 `##` 起历史正文完整保持。早期BTw/native/AI/研究包与本阶段首研究包不能继承为最终认证。Formal项目从头实现、独立于Temp，无runtime fallback或新认证复用，未执行生成模型、未作语义源码回写。
