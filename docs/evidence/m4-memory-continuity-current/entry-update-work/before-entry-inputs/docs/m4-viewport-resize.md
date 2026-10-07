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

[相机独立读回](evidence/m4-viewport-resize-current/independent-routing-agent/browser-camera-readback-final/report.json)133/133与[节点attempt4](evidence/m4-viewport-resize-current/independent-routing-agent/browser-node-readback-attempt-4/report.json)154/154是数据关系，不是133或154次用户成功。camera报告26份samples包含8份CXutz4Vh before；不能把前基准中心(350,456.639)当当前(350,405)来作相同条件改善比较。KAUB下11/12第一publicDOM还沿用旧translation，16/37初始reopen仍默认35,35,.9；screenshot后的公共DOM才恢复，四项initial失败明列。无presented frame时间戳，不认证first-paint continuity。

当前真实相机右/左/下/上各32CSSpx、Encoder下/上/左/右各24world＋每次undo，均有实际公共DOM。四次undo恢复全scene除revisionmetadata外exact，默认memory名称存在；垂直移仍切换display端口并绕远，canonical binding exact不能作为美观通过。最初node审计132/134因误要求display IDs在垂直移时exact，纠正后attempt2为134/134、增reopen与fit后attempt3为149/149、最终加43为154/154；原失败不覆写。authoring在视口改变后返回保持最终世界中心。

保存36的Canvas revision39、storage counter6；37初reopen默认90%，38settled才恢复100%中心(350,405)。[root有限观察](evidence/m4-viewport-resize-current/root-observation.json)亲看11/12/14/28/30/42/43：28JPGfooter31而DOM32，30JPGfooter33而DOM34，42raster100%而DOM54%。43settled时viewport783×526、fit54%，完整figure/legend/memory可见而文字仍小。稳定pre/post DOM字段仅证明那些字段，不能证明所有raster新鲜、全四向像素成功、首帧连续性或全域视觉质量。mask重叠/拥挤和memory外绕仍明确存在。

服务原临时workspace已不可用、旧handle缺失，开发恢复从前阶段savedrev31 envelope逐字复制到本stage runtime-workspace；[seedreceipt](evidence/m4-viewport-resize-current/runtime-seed-receipt.json)绑定原件与复制。当前URL为http://127.0.0.1:42938/；它属于开发验证服务，未启动任何研究席位。before07只有JSON无JPG、camera批处理timeout/reset、初按钮deadline失败和重试均留root记录。served JS只核公共asset filename与冻结/current字节，未独立HTTP取bytes。

[材料独立读回](evidence/m4-viewport-resize-current/independent-routing-agent/checks-readback-final/report.json)135/135读取已有logs、最终receipt、current112＋dist3＋publication11与3dist snapshot；不重跑检查，不认证HTTPserved bytes。[独立callback审计attempt3](evidence/m4-viewport-resize-current/independent-routing-agent/attempt-3/report.json)2954/2954使用独立中心方程、实际提取App callbacks与受控rAF/promise/lostcapture时序；React未挂载、ResizeObserver mocked，不证明paint。prior attempt2为2942/2943，其pan cancel先restore再resize导致两次setter，原一次setter期待为oracle错误；原失败保留。上述关系各自重叠/不同范围，不加成430产品测试。

[root材料末读](evidence/m4-viewport-resize-current/root-material-readback.json)八组有限byte关系bad[]：before143、implementation18、callbackseal15、cameraseal54、nodeseal39、research24＋586、current126。它核对具体文件字节，不认证功能或视觉通过。

## 可读300对象准备

[独立workload](evidence/m4-readable-grid-next-work/README.md)通过一条已有typed move，把冻结DenseStress300的source-backed output从(80,30346)移到(80,1756)，network保持(80,254)。root自然缩高、bounds从4588×30542缩到4588×1952；304node/302edge身份与300leaf事实保持。revision4→5、output active及两个saved frontiers的layout位移是允许变化；只有edge303路线变短，总中心线长度142405→113815世界单位。

[attempt2](evidence/m4-readable-grid-next-work/independent-report-attempt-2.json)为658/658有限document/hash/中心线关系：无unrelated leaf body穿越、无没有共同端点peer的proper crossing/positive overlap。endpoint相关peer、外框contact、stroke/marker/glyph没有认证。第一attempt655/656因oracle误拒output派生localY而失败，原报告/script/log保留；产品/preparer输出未为此更改。

672×711下300叶完整几何入内但名义13单位字仅1.632CSSpx；3400×1900为9.362px，3800×2100为10.495px，均只是projection。42文件seal冻结26inputs并只绑定其命名历史core，不反向认证当前live renderer。未采browser timing、实际解析字体、硬件/遮挡、continuous输入或presentedFPS，不能关闭300可读对象性能门。

## 研究准备与尚未通过的门

[新研究readiness](evidence/m4-viewport-resize-current/research-readiness-independent/report.json)为`.archcanvas/m4-research-trial-viewport-resize-current`，manifest SHA256`df96b2b593fb28a35ceebe384ac475b8197b42874593592b30b291d3aa9b3723`，正式venv prepare/verify0。86implementation、4baseline、五pristine席位43621–43625；308/308仅准备关系。24旧包410文件exact，新包17文件未变；上一caption包正式verify实际exit1 stale并保留原包。未查端口可用性、开席位服务、分配或collect，真人0。

左库仍17基础模块＋3透明起点，未逐种生成或执行。历史三AI角色不变，审计者不计新参与者，AI不计真人。3–5真实研究者五步任务≤180秒/≥80%、实际85/180mm出版人审、字体嵌入/塑形、全域route弯折/交叉美观均未闭合。memory默认名已稳定，但dy14→15display端口仍令路线49→644.3世界单位；拒绝候选继续冻结，不以warning记为美观通过。

旧BTw连续输入/medium样本只按原条件读取，rAF不是实际呈现FPS。当前continuous≤50ms、medium p95<500ms、300可读object、pins/anchor、固定硬件/字体A/B×3、presented≥50FPS未认证。

[实际导出独审attempt2](evidence/m4-viewport-resize-current/actual-export-readback/independent-attempt-2/report.json)407/407核对两份真实UI whole180mm工件：PDF `2ad8dcbf5e9b476c87589b75510c9e9e`、SVG `c85f6ce14ac443f49b6ee5c75a765046`。两份document.json与savedCanvas39/storage6 full document2/2 exact；相对已保存31/storage5，除了document.revision31→39外，layout与其余document完全一致。full canonical49nodes/71edges、scene12nodes/12renderedbindings保留；25canonical可见/46hidden明确核对，而不是以12display edges当完整canonical数量。

物理whole尺寸180×208.285714mm，最低名义文字6.56018pt，PDF MediaBox510.23622×590.416186pt。初次[attempt1](evidence/m4-viewport-resize-current/actual-export-readback/independent-attempt-1/report.json)401/402有1项失败：oracle要求PDFheight直接等raw scene比例，忽略sharedSVG五位mm normalizedheight；[纠正说明](evidence/m4-viewport-resize-current/actual-export-readback/independent-attempt-2/oracle-correction.json)与原失败保留，产品未为此改变。独审155frozen input＋13output＝168条bindings、165distinct paths，SHA256 `b635116c80061d294d8650343ddd7239a51fd53d957fdf297eef43f2922880b6`。

这些是数据/事实/digest/XML/PDF关系，未审export像素、实际85mm、当前detail、解析字体/塑形/嵌入或物理真人出版；whole文字偏小与现存dy14→15display端口突变/路线美观仍未通过。旧CXutz4Vh revision31的三导出669/669维持原build范围，不加成新407。

正式工程从头实现、独立于Temp runtime/fallback，无新认证复用；未执行用户/生成模型、未semantic源码回写。13入口只更新current header，第二个`##`之后历史body exact；旧gold、failures、packages和旧stage原字节保留。后续源码/build变化不能沿用本阶段认证，应保留本包并准备新具名研究包。M4active/partial，M5not_started。
