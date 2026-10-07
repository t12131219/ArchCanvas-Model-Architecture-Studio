# 上轮 input 诊断：环境证据与下次控制

当前raw不证明后台节流，也不指认产品根因。22条visibility都是visible、topHasFocus都是true，但只在开始/停止/focus/blur/visibilitychange采样；不能认证持续呈现、桌面前台或无遮挡。

341个rAF时间戳间隔中181个≥950ms、160个<25ms，短间隔常是每秒两个callback的成对突发，不是持续60FPS。整体1.884、idle2.025都是callback cadence。首个产品pointerdown前只有4个rendered成员，66frames的65间隔已中位983.2ms；粗节奏不要求先展开304。callback时间戳age最大22.6ms，而实际observedAt相邻中位983ms，也不能由此指认具体浏览器调度政策。

10个matched EventTiming条目的processing为0–85.7ms，reported duration为1920–3000ms；pan处理0/1.2/6.5ms仍报3000ms。最长记录longtask111ms，reported after-processing余量1872.4–2998.6ms仅是算术分解，不是独立paint或routerCPU测量。分母仍14eligible/10matched/4interactions，四个missing不删，matched子集p95仍3000ms。

observer直接self-cost最大scene8.2/input5.5/frame0.3/performance0.6ms，类别嵌套不能相加。源码无1秒timer，大JSON.stringify和textarea写入在stop之后，onProgress默认no-op；这些事实不排除先前SVG复制/布局getter、GC或browser observer交付的间接扰动，也不能排除产品/系统工作。需要匹配A/B。外页720px高却有144px控件＋720pxiframe，iframe从y144延到864；内层viewport命中不证明完整屏幕可见，这也不是已证实的节流原因。

下一次按analysis.json中的五组控制执行：冻结新build/环境/字体证据与实际可见对象；保证前台无遮挡和正确外层尺寸，采样top/iframe可见性与lifecycle；同引擎20秒轻量control至少三组与产品交替；raf-only/full、小4节点/304rendered、可用时top-level/iframe匹配比较；持续输入需独立compositor/presentation trace或已知帧率的可见显示采集，工具不支持就继续限定为callback/DOM诊断。新control/helper或trace需单独版本与开销记录，当前仅有源代码，未执行。

本次只读旧raw/probe，所有输入前后精确；6个probe当前hash及3个旧build资产归档hash与raw.context一致。未重跑validator/test/build/model、不操作browser、不改旧证据或产品/docs/status。背景政策、观测器单独致因、呈现FPS/总体INP均未认证；route变短不作性能通过。
