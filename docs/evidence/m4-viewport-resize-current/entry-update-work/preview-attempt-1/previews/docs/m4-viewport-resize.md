# M4 视口尺寸与相机坐标协调

本轮修复实时视口改变后相机平移仍沿用旧尺寸的问题。正式构建 `index-_KAUBMcR.js` / `index--unhoRTb.css`；[统一收据](evidence/m4-viewport-resize-current/checks-final-attempt-2/receipt.json)为 Studio430/430、fail/skip/cancel0、strict TypeScript/Vite exit0、publication11/11skip0。112源码/测试/配置＋3dist为115条，另11publication输入；兼容测试引用的18历史core独立冻结，112不是完整传递依赖清单。M4partial、M5not_started、真人0。

## 触发与坐标契约

上一CXutz4Vh阶段capture38按883×786重开保持中心(350,405)，第一次回672×711的capture39却留下大视口平移，中心变(244.5,367.5)，再次稳定reload40才恢复。[旧阶段](m4-caption-stability-camera.md)与原失败没有被改为通过。本阶段变更前143项[原字节归档](evidence/m4-viewport-resize-current/before-change/manifest.json)保留旧App/core/tests/publication输入和18历史兼容core。

cameraViewport独立验证可用尺寸，并按宽高差的一半平移相机，保持中心的世界坐标与zoom。App以useLayoutEffect订阅当前实际元素；ResizeObserver交付使用flushSync提交匹配平移。没有ResizeObserver时window resize仅作有限fallback，不能发现所有浏览器窗口未变的内部尺寸改变。

持久化读已建立camera viewport anchor，避免DOM尺寸先变、observer未交付时保存错误中心。相机仍在UI/session状态，独立于CanvasDocument、undo历史、source/IR与publication scene。explicit fit、zoom、focus以及document初始化建立新anchor；旧document/element或load/intent票据不能应用到当前视图。

## 手势与初始化顺序

active pan、对象拖动、框选与port输入保持开始时的坐标映射；pointer终止/取消在实际结果之后协调resize。早于restore的空间手势使用用户当时看到的坐标并取消延迟restore。隐藏或暂时未挂载的初始化在有限frame重试后停止主动排队但保留合法ticket，后来可用observer/重挂载再续行；新显式intent会清pending。

[实现报告](evidence/m4-viewport-resize-current/implementation-work/report.json)与[focused attempt4](evidence/m4-viewport-resize-current/implementation-work/focused-attempt-4/receipt.json)记录45/45、其中21新增resize测试，strict0。测试读取实际App callback和useLayoutEffect本体，使用独立数值期望及正式typed undo断言；未挂载React，不认证真实observer调度、native pointer或paint。首次错误、attempt2/3和最终attempt4均保留；45是430的重叠范围，不能相加。

初始load仍可能先显示默认相机后再完成延迟初始化，本阶段不承诺zero first-frame load flicker。正确性还依赖最终版真实浏览器验证。

## 最终浏览器与材料范围

最终版真实 CUA resize、gesture、remount 与 save/reopen证据仍在采集；以下草案不把 callback 测试计为原生事件或绘制认证。

最终独立材料审计待落盘；本草案仅验证当前收据112＋3＋11共126绑定exact。

## 可读300对象准备

[独立workload](evidence/m4-readable-grid-next-work/README.md)通过一条已有typed move，把冻结DenseStress300的source-backed output从(80,30346)移到(80,1756)，network保持(80,254)。root自然缩高、bounds从4588×30542缩到4588×1952；304node/302edge身份与300leaf事实保持。revision4→5、output active及两个saved frontiers的layout位移是允许变化；只有edge303路线变短，总中心线长度142405→113815世界单位。

[attempt2](evidence/m4-readable-grid-next-work/independent-report-attempt-2.json)为658/658有限document/hash/中心线关系：无unrelated leaf body穿越、无没有共同端点peer的proper crossing/positive overlap。endpoint相关peer、外框contact、stroke/marker/glyph没有认证。第一attempt655/656因oracle误拒output派生localY而失败，原报告/script/log保留；产品/preparer输出未为此更改。

672×711下300叶完整几何入内但名义13单位字仅1.632CSSpx；3400×1900为9.362px，3800×2100为10.495px，均只是projection。42文件seal冻结26inputs并只绑定其命名历史core，不反向认证当前live renderer。未采browser timing、实际解析字体、硬件/遮挡、continuous输入或presentedFPS，不能关闭300可读对象性能门。

## 研究准备与尚未通过的门

[新研究readiness](evidence/m4-viewport-resize-current/research-readiness-independent/report.json)为`.archcanvas/m4-research-trial-viewport-resize-current`，manifest SHA256`df96b2b593fb28a35ceebe384ac475b8197b42874593592b30b291d3aa9b3723`，正式venv prepare/verify0。86implementation、4baseline、五pristine席位43621–43625；308/308仅准备关系。24旧包410文件exact，新包17文件未变；上一caption包正式verify实际exit1 stale并保留原包。未查端口可用性、开席位服务、分配或collect，真人0。

左库仍17基础模块＋3透明起点，未逐种生成或执行。历史三AI角色不变，审计者不计新参与者，AI不计真人。3–5真实研究者五步任务≤180秒/≥80%、实际85/180mm出版人审、字体嵌入/塑形、全域route弯折/交叉美观均未闭合。memory默认名已稳定，但dy14→15display端口仍令路线49→644.3世界单位；拒绝候选继续冻结，不以warning记为美观通过。

旧BTw连续输入/medium样本只按原条件读取，rAF不是实际呈现FPS。当前continuous≤50ms、medium p95<500ms、300可读object、pins/anchor、固定硬件/字体A/B×3、presented≥50FPS未认证。此前CXutz4Vh实际revision31整图180mmPDF/SVG与detailSVG的669/669是历史导出关系，最低整图6.56018pt/detail7.41862pt；85计算3.09786pt没有actual85工件。本轮未新导出或人审。

正式工程从头实现、独立于Temp runtime/fallback，无新认证复用；未执行用户/生成模型、未semantic源码回写。13入口只更新current header，第二个`##`之后历史body exact；旧gold、failures、packages和旧stage原字节保留。后续源码/build变化不能沿用本阶段认证，应保留本包并准备新具名研究包。M4active/partial，M5not_started。
