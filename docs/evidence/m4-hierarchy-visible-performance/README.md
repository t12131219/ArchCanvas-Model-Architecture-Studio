# 层级树优化构建的本轮原生诊断与控制页

当前（2026-10-05）`index-Cr_xKW9U.js`（SHA256 `1f4f51f9818e523916dacea184a7005fa7459bd3f2c4c8bfe6bfc83006e5be29`）与最终ce7 frontend 的[新版浏览器矩阵](../../m4-boundary-final-matrix.md)已完成真实UI采集：36 baseline＋三模型各一 edited-after，共39例/234工件、9 frontier；完整Scene/export重建与独立核对通过，artifactCoverage=complete，humanAcceptanceCertified=false。39张实际截图已有AI逐张观察，三组提交后的undo/redo/保存重开链另有完整SVG核对；这些不认证物理出版或真人。Studio88/88、Python62/62及额外21/21属于此前边界修正轮，本矩阵轮未重跑、未改产品源码/build。当前五席研究包61实施绑定、0真人；presented性能、活动取消、固定字体/硬件、人审与3–5真实任务仍未认证，M4保持partial、未进入M5。旧oI5矩阵/诊断/研究包仍属历史；[矩阵前归档](../before-boundary-final-matrix/manifest.json)保留更新前文档和完整3644绑定解析，旧seal不改。

本目录记录历史`index-oI5sT67U.js`的8897产品原生诊断、一次simple control、实际宿主visibility读数、五席研究包fresh verify以及8889交付文档恢复。目录名中的`visible`是最初实验意图；产品前后、控制前后capability均false，产品后的set(true)读数仍false，不能称可见性能测试通过。document visible/focus不能覆盖宿主读数。M4仍partial，持续presented性能、原生活动取消、固定字体/硬件、人工出版与研究者任务未认证。

[产品独立审计](independent-product-audit.md)/[JSON](independent-product-audit.json)（SHA256 `ef72dd873e53a1914082bbf87a0a8a7784aa893eaf3e58da403e548bbbc2391c`）冻结并复读23输入，fresh validator exit0、完整parsed output exact。raw为9,239,688 bytes，131个read ranges连续覆盖9,133,326 UTF16字符；原AX/native frame limit、v1错误getAttribute归因及修正v2转录均保留，不改raw或认证原工具读过程。

五请求全部成功：源码stress network由4→304个渲染前沿对象；可信左键手工具pan终点+40/+24 CSSpx且rev/SVG/frontier/pins/selection不变；指定Linear1 drag由client+30/+18经scale0.789091和4px网格成为canvas+40/+24，rev1→2，root/network宽各增加40；undo/redo除root data-revision与metadata revision两标量外完整SVG精确恢复。11SVG snapshot的sourceFacts、source/IR与正式architecture匹配，源码独立确认150对Linear/ReLU；未导入/执行模型。304对象frontier不意味着所有对象在viewport可读，本场景无pins，不计无关固定对象验收。

离散原生双向唯一配对为14eligible/13matched/5interactions，按每interaction最大duration仅计一次，matched subset p95=4008ms；drag pointerdown缺失保持null。它不是整个页面INP、代表性任务p95或连续input-to-paint。pan真实down→up窗口7001.3ms、8可信moves、9 rAF与7次几何变化；drag7095.1ms、8moves、11 rAF与6次变化。约7秒是自动化手势事实，不是人类耗时，rAF/DOM变化也不是presented FPS。全session start→stop回调约1.928Hz，混入准备/等待不能代表持续手势呈现。活动区间没有Esc/cancel/blur/lostcapture；普通up后的lostcapture和后续blur不算原生活动取消。

[控制页独立审计](independent-control-audit.md)/[JSON](independent-control-audit.json)（SHA256 `47bfe8fafd155cef6ddf5b01ba0a14b0083068217d3188ee101425de1dd7c789`）冻结16输入、末读全部稳定，fresh validator semantic字段exact；input/runtime/validator新时刻或临时路径metadata按声明排除对等，原saved绑定另外核对。一次timer窗20000.4ms，38rAF/37interval，p50/p95/max为983.2/999.9/1000.0ms，exact start→stop回调1.899962Hz；3可信target input匹配1interaction、maximum duration2008ms。三个pointerdown/up/click属于同一interaction，不是三项任务；单interaction的p95不代表页面或任务分布。presentedFrameRate/掉帧/continuousInputToPaint均null，未订阅longtask不能写成0。

控制页面没有React/SVG/model/Studio telemetry，但top-level与产品iframe、非同时/非随机采样存在差别。二者的低频支持环境/调度疑点，不能排除产品React/SVG替换/telemetry/renderer成本，也不能定位CUA、宿主、系统或产品因果。不能用控制页清除失败性能门，不能不断重采直到出现较快结果。hardwareConcurrency16不是锁定物理硬件，loadedFaces=[]不是解析字体文件绑定，截图未在此审计中做像素评审。

[visibility-readings](visibility-readings.json)保留实际phase读数，产品审计使用[冻结副本](product-audit-visibility-snapshot.json)而不追溯重绑定后续追加内容。[fresh研究verify](research-verify.txt)exit0只核冻结基线与实现：当时`.archcanvas/m4-research-trial-hierarchy-final`仍59实施绑定、五pristine、0分配/收集/真人，researchGate not_evaluated。

[恢复对比](restored-deliverable-comparison.json)记录8889同data-dir恢复MLP完整SVG SHA256 `62f83f6db697d38d6713cd7c50cc832a327844930a6bbe732988749c771962ee`与原交付原字节相同，唯一pin仍Linear1。初次pins比较把已解码数组与编码字符串比较而失败，修正两侧解码，原输入不变。[服务生命周期](service-lifecycle.json)保留原8889与矩阵8896观察到exit143/原因未知；8897收据保存后主动Ctrl-C退出130；8889恢复后随后poll也exit143/原因未知。恢复字节验证不是在线承诺，未宣称seal时服务可用。用户8765未触碰。

`service-raw.txt`与`deliverable-service-raw.txt`是日志源，冻结字节另存`service-cutoff.txt`/`deliverable-service-cutoff.txt`；矩阵日志cutoff位于相邻work目录。cutoff/工具转录不构成完整终端历史或退出原因证明。本轮完整矩阵和出版边界见[矩阵说明](../../m4-hierarchy-final-matrix.md)，新阶段验证另用[m4-hierarchy-final-verification.json](../m4-hierarchy-final-verification.json)，不覆盖旧seal/manifest/raw。
